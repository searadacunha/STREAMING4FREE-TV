"""Command line interface."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__, deploy, doctor, kodi, pipeline
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

    u = sub.add_parser("update", help="scan, build and deploy")
    deploy_flags(u)
    u.set_defaults(func=cmd_update)
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
    except (AdbError, kodi.KodiError, pipeline.PipelineError, deploy.DeployError, OSError) as e:
        log.debug("command failed", exc_info=True)
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
