"""Command line interface."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__, deploy, diagnose, doctor, health, kodi, meganexus, pipeline
from .adb import Adb, AdbError
from .config import RESTART_POLICIES, Config, ConfigError, load_config

log = logging.getLogger("iptv4free")


def _config_path(arg: str | None) -> Path:
    return Path(arg or os.environ.get("IPTV4FREE_CONFIG") or "iptv4free.toml")


def _logging(config: Config, verbose: bool) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(console)
    config.state_dir.mkdir(parents=True, exist_ok=True)
    logfile = logging.FileHandler(config.state_dir / "iptv4free.log", encoding="utf-8")
    logfile.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(logfile)


def _adb(config: Config) -> Adb:
    return Adb(config.adb, config.tv_address, config.adb_timeout)


def _progress(done: int, total: int) -> None:
    step = max(total // 10, 1)
    if done == total or done % step == 0:
        print(f"  probed {done}/{total}", file=sys.stderr, flush=True)


def cmd_setup(config: Config, args) -> int:
    adb = _adb(config)
    adb.connect()
    print(f"TV {adb.serial}: Android {adb.getprop('ro.build.version.release')}, "
          f"ABI {adb.getprop('ro.product.cpu.abi')}")
    version = adb.package_version(config.kodi_package)
    if version:
        print(f"Kodi {version} is installed.")
    elif args.install_kodi:
        print("Installing Kodi from the official mirror (mirrors.kodi.tv)...")
        print(f"Kodi {kodi.install_kodi(adb, config, args.kodi_version)} installed.")
        print("Open Kodi once on the TV and accept the storage permission prompt.")
    else:
        print("Kodi is not installed. Run `iptv4free setup --install-kodi` to install the "
              "official APK, or install Kodi from the Google Play Store.")
    print()
    print(kodi.instructions(config))
    return 0


def cmd_scan(config: Config, args) -> int:
    s = pipeline.run_scan(config, _progress)
    print(f"Scanned {s.streams} streams in {s.seconds:.0f} s: {s.alive} alive. "
          f"Sources refreshed: {s.sources_refreshed}, kept from previous scan: {s.sources_stale}.")
    return 0


def cmd_build(config: Config, args) -> int:
    for lid, (path, rep) in pipeline.run_build(config).items():
        print(f"{lid}: {rep.channels} channels ({rep.with_epg} with EPG) -> {path}")
        print(f"  {rep.source_entries} source entries: {rep.dead} not alive, "
              f"{rep.duplicates} duplicates, {rep.taken_by_earlier_lineup} in an earlier lineup, "
              f"{rep.excluded_category} excluded by category")
        if rep.favorites_missing:
            print(f"  favorites not found: {', '.join(rep.favorites_missing)}")
    return 0


def _built_files(config: Config) -> dict[str, Path]:
    files = {lu.id: config.output_dir / f"{lu.id}.m3u" for lu in config.lineups}
    missing = [lid for lid, p in files.items() if not p.exists()]
    if missing:
        raise pipeline.PipelineError(f"not built yet: {', '.join(missing)}; run `iptv4free build`")
    return files


def cmd_deploy(config: Config, args) -> int:
    return deploy.apply(config, _adb(config), _built_files(config), dry_run=args.dry_run,
                        allow_large=args.allow_large_update, restart_policy=args.restart)


def cmd_rollback(config: Config, args) -> int:
    if args.list:
        for b in deploy.backups(config):
            print(f"{b.name}: {', '.join(sorted(f.stem for f in b.glob('*.m3u')))}")
        return 0
    return deploy.rollback(config, _adb(config), args.backup, dry_run=args.dry_run,
                           restart_policy=args.restart)


def cmd_doctor(config: Config, args) -> int:
    return doctor.run(config, _adb(config))


def cmd_meganexus_doctor(config: Config, args) -> int:
    return meganexus.doctor(config, _adb(config))


def cmd_meganexus_setup(config: Config, args) -> int:
    return meganexus.setup(config, _adb(config))


def cmd_meganexus_rollback(config: Config, args) -> int:
    if args.list:
        for b in meganexus.backups(config):
            print(b.name)
        return 0
    return meganexus.rollback(config, _adb(config), args.backup, dry_run=args.dry_run,
                              force=args.force)


def _health_targets(config: Config, args) -> list[tuple[str, "scanner.Target"]]:
    """(channel name, target) to follow: favourites of the given or built playlists, the
    channels named with --channel, and with --duplicates every alive source of a channel
    that has several (what `build` chooses between)."""
    from .channels import clean_name
    from .epg import match_key
    from .playlists import effective_url, parse_m3u, request_parts
    from .scanner import Target
    files = [Path(f) for f in args.playlist] or [config.output_dir / f"{lu.id}.m3u" for lu in config.lineups]
    wanted = {match_key(n) for n in args.channel}
    picked: dict[str, tuple[str, Target]] = {}

    def add(e):
        e = health.unroute(e)
        key = effective_url(e)
        url, headers = request_parts(e)
        picked.setdefault(key, (e.name, Target(key, url, tuple(sorted(headers.items())))))
    for f in files:
        if not f.exists():
            continue
        for e in parse_m3u(f.read_text(encoding="utf-8")).entries:
            groups = e.attrs.get("group-title", "")
            if (match_key(clean_name(e.name)) in wanted if wanted
                    else config.favorites_label.casefold() in groups.casefold()):
                add(e)
    if args.duplicates:
        history = pipeline._history(config)
        for lineup in config.lineups:
            by_key: dict = {}
            for e in pipeline.lineup_entries(config, lineup):
                if history.alive(effective_url(e), config.max_failed_scans):
                    k = (match_key(clean_name(e.name)), e.attrs.get("tvg-id", "").split("@")[0].lower())
                    by_key.setdefault(k, {})[e.url] = e
            for found in by_key.values():
                if len(found) > 1:
                    for e in found.values():
                        add(e)
    return list(picked.values())


def cmd_health(config: Config, args) -> int:
    targets = _health_targets(config, args)
    if not targets:
        print("nothing to follow: give --playlist, --channel or --duplicates (favourites are "
              f"the entries whose group contains '{config.favorites_label}')")
        return 1
    minutes = len(targets) * args.seconds / args.workers / 60
    print(f"Following {len(targets)} streams for {args.seconds:.0f} s each, {args.workers} at a time: "
          f"about {minutes:.0f} to {2 * minutes:.0f} min (the relay A/B doubles the time when it runs).")
    book = health.HealthBook(config.state_dir / "health.json")
    import itertools
    import threading
    import urllib.parse
    from concurrent.futures import ThreadPoolExecutor
    # Two streams of one server followed at once share what it gives one address: one at a
    # time per host (TF1 measured 5.2 Mb/s through the relay next to two others, TFX alone 9.0).
    locks: dict[str, threading.Lock] = {}
    by_host: dict[str, list] = {}
    for name, t in targets:
        host = urllib.parse.urlsplit(t.url).netloc
        locks.setdefault(host, threading.Lock())
        by_host.setdefault(host, []).append((name, t, locks[host]))
    order = [job for group in itertools.zip_longest(*by_host.values()) for job in group if job]

    def follow(t, lock):
        with lock:
            return health.check_with_relay(t, args.seconds, 10.0, config.user_agent)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [(name, pool.submit(follow, t, lock)) for name, t, lock in order]
        for name, job in jobs:
            direct, relayed = job.result()
            book.record(direct, relayed)
            book.save()
            line = (f"  {name[:28]:28s} {direct.verdict:8s} {direct.stalls} stalls "
                    f"{direct.stall_seconds:.0f} s, speed p10 {direct.speed_p10 / 1e6:.1f} Mb/s "
                    f"for {direct.bitrate / 1e6:.1f} Mb/s, {direct.variants} variants")
            if relayed:
                line += (f" | relay: {relayed.verdict}, {relayed.stalls} stalls, "
                         f"p10 {relayed.speed_p10 / 1e6:.1f} Mb/s")
            if health.relay_helps(book.records[direct.key]):
                line += "  -> relay helps"
            print(line, flush=True)
    print(f"Saved to {book.path}")
    return 0


def cmd_tune(config: Config, args) -> int:
    """Rewrite existing playlists so the channels the relay helps go through it (or back)."""
    from .playlists import parse_m3u, render_m3u
    from .updates import atomic_write
    book = health.HealthBook(config.state_dir / "health.json")
    out_dir = Path(args.out)
    for f in (Path(p) for p in args.playlist):
        entries = parse_m3u(f.read_text(encoding="utf-8")).entries
        if args.undo:
            new = [health.unroute(e) for e in entries]
            changed = [e.name for e, n in zip(entries, new) if n is not e]
        else:
            new, changed = health.route(entries, book)
        atomic_write(out_dir / f.name, render_m3u(new))
        verb = "back to the source" if args.undo else "through the relay"
        print(f"{f.name}: {len(changed)} of {len(entries)} channels {verb}"
              + (f": {', '.join(changed[:12])}{' ...' if len(changed) > 12 else ''}" if changed else ""))
    return 0


def cmd_playback_diagnose(config: Config, args) -> int:
    return diagnose.run(config, _adb(config), ping=not args.no_ping)


def cmd_update(config: Config, args) -> int:
    cmd_scan(config, args)
    cmd_build(config, args)
    return cmd_deploy(config, args)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="iptv4free", description="Free IPTV automation for "
                                "Android TV, built around Kodi.")
    p.add_argument("--config", help="config file (default: $IPTV4FREE_CONFIG or ./iptv4free.toml)")
    p.add_argument("-v", "--verbose", action="store_true", help="debug output")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("setup", help="check the TV, optionally install Kodi, print Kodi setup steps")
    s.add_argument("--install-kodi", action="store_true",
                   help="download the official Kodi APK (checksum verified) and install it")
    s.add_argument("--kodi-version", default="latest", help="e.g. 21.3 (default: latest)")
    s.set_defaults(func=cmd_setup)

    sub.add_parser("scan", help="download sources and test every stream").set_defaults(func=cmd_scan)
    sub.add_parser("build", help="generate the lineup playlists").set_defaults(func=cmd_build)

    def deploy_flags(sp):
        sp.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
        sp.add_argument("--allow-large-update", action="store_true",
                        help="allow more than safety.max_changes channel changes")
        sp.add_argument("--restart", choices=RESTART_POLICIES,
                        help="restart Kodi after upload (default: safety.restart_kodi)")

    d = sub.add_parser("deploy", help="upload built playlists to the TV, with safety checks")
    deploy_flags(d)
    d.set_defaults(func=cmd_deploy)

    r = sub.add_parser("rollback", help="restore the playlists saved before a deployment")
    r.add_argument("--backup", help="backup name (default: latest)")
    r.add_argument("--list", action="store_true", help="list backups")
    r.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    r.add_argument("--restart", choices=RESTART_POLICIES)
    r.set_defaults(func=cmd_rollback)

    sub.add_parser("doctor", help="read-only diagnostics").set_defaults(func=cmd_doctor)

    h = sub.add_parser("health", help="follow a few streams like a player for minutes "
                       "(stalls, speed), with and without the relay")
    h.add_argument("--playlist", action="append", default=[], help="M3U to read (default: built playlists)")
    h.add_argument("--channel", action="append", default=[], help="channel name (repeatable)")
    h.add_argument("--duplicates", action="store_true",
                   help="also every alive source of the channels that have several (needs `scan`)")
    h.add_argument("--seconds", type=float, default=120, help="per stream (default 120)")
    h.add_argument("--workers", type=int, default=2, help="streams followed at once (default 2)")
    h.set_defaults(func=cmd_health)

    t = sub.add_parser("tune", help="route the channels `health` found better through the relay "
                       "in existing playlists (or --undo)")
    t.add_argument("playlist", nargs="+")
    t.add_argument("--out", required=True, help="directory for the rewritten playlists")
    t.add_argument("--undo", action="store_true", help="put every relayed channel back on its source")
    t.set_defaults(func=cmd_tune)

    pd = sub.add_parser("playback-diagnose", help="read-only report: Kodi, memory, Wi-Fi, "
                        "stalls and slow starts per server, likely causes")
    pd.add_argument("--no-ping", action="store_true", help="skip the ping measurements")
    pd.set_defaults(func=cmd_playback_diagnose)

    u = sub.add_parser("update", help="scan, build and deploy")
    deploy_flags(u)
    u.set_defaults(func=cmd_update)

    m = sub.add_parser("meganexus", help="MegaNexus interface for Kodi: doctor, setup, rollback")
    msub = m.add_subparsers(dest="action", required=True)
    msub.add_parser("doctor", help="read-only checks for MegaNexus").set_defaults(
        func=cmd_meganexus_doctor)
    msub.add_parser("setup", help="back up Kodi, check the official MegaNexus repository "
                    "zip, print the install steps").set_defaults(func=cmd_meganexus_setup)
    mr = msub.add_parser("rollback", help="restore Kodi's settings from a backup and turn "
                         "MegaNexus off")
    mr.add_argument("--backup", help="backup name (default: latest)")
    mr.add_argument("--list", action="store_true", help="list backups")
    mr.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    mr.add_argument("--force", action="store_true",
                    help="restart Kodi even if it does not answer (frozen)")
    mr.set_defaults(func=cmd_meganexus_rollback)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(_config_path(args.config))
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        if "not found" in str(e):
            print("hint: cp config/example.toml iptv4free.toml", file=sys.stderr)
        return 1
    _logging(config, args.verbose)
    try:
        return args.func(config, args)
    except (AdbError, kodi.KodiError, pipeline.PipelineError, deploy.DeployError,
            meganexus.MegaNexusError, OSError) as e:
        log.debug("command failed", exc_info=True)
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
