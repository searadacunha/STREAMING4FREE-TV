"""MegaNexus, a Kodi interface, on the IPTV4FREE TV: diagnostics, preparation, rollback.

MegaNexus is not redistributed here (its license forbids it). `setup` backs up Kodi's
settings and checks that the repository zip Kodi will download from the official source
matches the SHA-256 GitHub publishes for the latest release; Kodi installs MegaNexus from
that repository. IPTV4FREE's channels stay in IPTV Simple Client, which MegaNexus' Channels
screen reads directly.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shlex
import time
import urllib.request
from pathlib import Path

from .adb import Adb, AdbError
from .config import Config
from .doctor import Report
from .kodi import KodiError, KodiRpc, connect_rpc

log = logging.getLogger(__name__)

RELEASE_API = "https://api.github.com/repos/MegaNexusMediaPlayer/MegaNexus/releases/latest"
SOURCE = "https://meganexusmediaplayer.github.io/MegaNexus/"  # the source Kodi installs from
# Disable order: what depends on an add-on goes first.
ADDONS = ("screensaver.meganexus", "skin.meganexus", "script.meganexus",
          "plugin.video.meganexus", "vfs.meganexus", "repository.meganexus")
NATIVE = {"armeabi-v7a": "android-armv7", "arm64-v8a": "android-aarch64"}  # vfs.meganexus builds
KODI_MAJORS = (21, 22)
SMALL_RAM_KB = 2_500_000  # a "2 GB" box reports about 1.8 GB of MemTotal
EXIT_REFUSED = 3


class MegaNexusError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _q(path: str) -> str:
    return shlex.quote(path)


def userdata_dir(config: Config) -> str:
    return f"/sdcard/Android/data/{config.kodi_package}/files/.kodi/userdata"


def _stage_dir(config: Config) -> str:
    return f"{config.remote_dir.rstrip('/')}/meganexus"


def _kodi_major(version: str | None) -> int | None:
    m = re.match(r"(\d+)\.", version or "")
    return int(m.group(1)) if m else None


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_repository_zip(dest_dir: Path) -> Path:
    """Download the repository zip from the source Kodi uses; it must match the SHA-256
    GitHub publishes for the latest release."""
    release = _get_json(RELEASE_API)
    asset = next((a for a in release.get("assets", [])
                  if re.fullmatch(r"repository\.meganexus-[\d.]+\.zip", a.get("name", ""))), None)
    if asset is None:
        raise MegaNexusError(f"no repository add-on in MegaNexus release {release.get('tag_name')}")
    algo, _, expected = (asset.get("digest") or "").partition(":")
    if algo != "sha256" or len(expected) != 64:
        raise MegaNexusError(f"{asset['name']}: GitHub publishes no SHA-256 for it; not using it")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / asset["name"]
    if path.exists() and _sha(path) == expected:
        return path
    with urllib.request.urlopen(SOURCE + asset["name"], timeout=120) as resp:
        data = resp.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise MegaNexusError(f"{SOURCE}{asset['name']}: checksum mismatch with the GitHub release "
                             f"(expected {expected}, got {actual}); do not install it")
    path.write_bytes(data)
    return path


def latest_version() -> str | None:
    """Version of the latest MegaNexus release, None when GitHub cannot be reached."""
    try:
        return _get_json(RELEASE_API).get("tag_name", "").lstrip("v") or None
    except (OSError, ValueError):
        return None


def _push_verified(adb: Adb, local: Path, remote: str) -> None:
    adb.shell(f"mkdir -p {_q(remote.rsplit('/', 1)[0])}")
    adb.push(str(local), remote)
    if adb.sha256(remote) != _sha(local):
        adb.shell(f"rm -f {_q(remote)}", check=False)
        raise MegaNexusError(f"{remote}: upload corrupted (checksum mismatch)")


# --- backup -------------------------------------------------------------------------------

def backups(config: Config) -> list[Path]:
    root = config.state_dir / "meganexus" / "backups"
    return sorted(d for d in root.iterdir() if d.is_dir()) if root.exists() else []


def backup(config: Config, adb: Adb) -> Path:
    """Copy Kodi's userdata (without the thumbnail cache) and the lineup playlists to the computer."""
    root = config.state_dir / "meganexus" / "backups"
    dest = root / time.strftime("%Y%m%d-%H%M%S")
    n = 1
    while dest.exists():
        n += 1
        dest = root / f"{time.strftime('%Y%m%d-%H%M%S')}-{n}"
    (dest / "userdata").mkdir(parents=True)
    userdata = userdata_dir(config)
    names = adb.shell(f"ls -1 {_q(userdata)}").split()
    if "guisettings.xml" not in names:
        raise MegaNexusError(f"no Kodi settings in {userdata}: open Kodi once first")
    for name in names:
        if name != "Thumbnails":  # a cache Kodi rebuilds; it can hold thousands of posters
            adb.pull(f"{userdata}/{name}", str(dest / "userdata" / name))
    for lineup in config.lineups:
        if adb.exists(config.remote_path(lineup)):
            (dest / "playlists").mkdir(exist_ok=True)
            adb.pull(config.remote_path(lineup), str(dest / "playlists" / f"{lineup.id}.m3u"))
    sums = [f"{_sha(p)}  {p.relative_to(dest)}" for p in sorted(dest.rglob("*")) if p.is_file()]
    (dest / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    return dest


def _setting(guisettings: Path, key: str) -> str | None:
    m = re.search(rf'<setting id="{re.escape(key)}"[^>]*>([^<]*)</setting>',
                  guisettings.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


# --- setup --------------------------------------------------------------------------------

def instructions(zip_name: str) -> str:
    return "\n".join([
        "One-time MegaNexus installation, with the TV remote (Kodi menus in English):",
        "  1. Settings > System > Add-ons > Unknown sources: on, then Yes. Kodi installs zip",
        "     files only with this on, and ignores it when set through JSON-RPC.",
        f"  2. Settings > File manager > Add source > <None>: type {SOURCE}",
        "     and keep the name MegaNexus. (A zip copied with adb stays invisible to Kodi:",
        "     Android 11 and later hide other apps' non-media files.)",
        f"  3. Add-ons > Install from zip file > MegaNexus > {zip_name}",
        "  4. Add-ons > Install from repository > MegaNexus Repository > Video add-ons >",
        "     MegaNexus Hub > Install. Interface, skin and screensaver follow by themselves.",
        "  5. When Kodi asks 'Keep this skin?', answer Yes within about 10 seconds; if it",
        "     expired, open MegaNexus again from Add-ons and answer Yes.",
        "  6. Welcome screen: 'Start simple' needs no account.",
        "  7. HUB Settings > Profiles > Who's watching when Kodi starts: Off (Kodi froze on",
        "     that screen on a 2 GB TV). To open Kodi on the MegaNexus HUB: Kodi Settings >",
        "     Interface > Skin > Startup window: Home.",
        "  8. Leave Channels > IPTV setup empty: Channels already shows Kodi's channels.",
        "  9. Run `iptv4free meganexus doctor`, then restart Kodi once and check it opens.",
        "To undo it: `iptv4free meganexus rollback` (add --force if Kodi is frozen).",
    ])


def setup(config: Config, adb: Adb, out=print) -> int:
    """Check the TV, back up Kodi, check the official repository zip, print the steps."""
    adb.connect()
    abi = adb.getprop("ro.product.cpu.abi")
    version = adb.package_version(config.kodi_package)
    problems = []
    if abi not in NATIVE:
        problems.append(f"MegaNexus publishes no native add-on for {abi!r}")
    if _kodi_major(version) not in KODI_MAJORS:
        problems.append(f"MegaNexus needs Kodi 21 or 22 (installed: {version or 'none'})")
    if problems:
        for msg in problems:
            out(f"REFUSED: {msg}")
        return EXIT_REFUSED
    dest = backup(config, adb)
    out(f"Backup of Kodi's settings and playlists: {dest}")
    zip_path = fetch_repository_zip(config.state_dir / "downloads")
    out(f"{SOURCE}{zip_path.name}: SHA-256 matches the latest GitHub release")
    out(instructions(zip_path.name))
    return 0


# --- doctor -------------------------------------------------------------------------------

def installed_addons(rpc: KodiRpc) -> dict[str, dict]:
    found = {}
    for addon in ADDONS:
        try:
            found[addon] = rpc.call("Addons.GetAddonDetails",
                                    {"addonid": addon, "properties": ["version", "enabled"]})["addon"]
        except KodiError:
            pass  # Kodi answers "Invalid params" for an add-on that is not installed
    return found


def doctor(config: Config, adb: Adb, out=print) -> int:
    """Read-only: can this TV run MegaNexus, is it installed, and is IPTV still there."""
    r = Report(out)
    try:
        adb.connect()
        abi = adb.getprop("ro.product.cpu.abi")
        if abi in NATIVE:
            r.ok(f"TV {adb.serial}: {abi}, MegaNexus native build {NATIVE[abi]}")
        else:
            r.fail(f"TV {adb.serial}: MegaNexus publishes no native add-on for {abi!r}")
        mem = dict(re.findall(r"^(\w+):\s+(\d+) kB", adb.shell("cat /proc/meminfo"), re.M))
        total, avail = int(mem.get("MemTotal", 0)), int(mem.get("MemAvailable", 0))
        ram = f"RAM {total / 1e6:.1f} GB, {avail // 1024} MB available"
        if total < SMALL_RAM_KB:
            r.warn(f"{ram}: if MegaNexus is slow, set HUB Settings > Performance & image "
                   "cache > Memory for posters and catalogs to 128 MB")
        else:
            r.ok(ram)
        df = adb.shell("df -k /sdcard").strip().splitlines()[-1].split()
        free_mb = int(df[3]) // 1024 if len(df) > 3 and df[3].isdigit() else 0
        (r.ok if free_mb >= 500 else r.warn)(f"{free_mb} MB free on the TV storage")
        version = adb.package_version(config.kodi_package)
        if _kodi_major(version) in KODI_MAJORS:
            r.ok(f"Kodi {version}")
        else:
            r.fail(f"MegaNexus needs Kodi 21 or 22 (installed: {version or 'none'})")
            return 1
        rpc = connect_rpc(adb, config)
    except AdbError as e:
        r.fail(str(e))
        return 1
    if rpc is None:
        if _kodi_running(adb, config):
            r.fail("Kodi runs but does not answer (frozen?). If nothing is playing: "
                   "`iptv4free meganexus rollback --force`")
        else:
            r.warn("Kodi is not running: start it to check the MegaNexus add-ons")
        return 1 if r.failed else 0
    try:
        addons = installed_addons(rpc)
        hub = addons.get("plugin.video.meganexus")
        if not hub:
            r.warn("MegaNexus is not installed: run `iptv4free meganexus setup`")
        for addon_id, info in addons.items():
            (r.ok if info.get("enabled") else r.warn)(
                f"{addon_id} {info.get('version')} {'enabled' if info.get('enabled') else 'disabled'}")
        latest = latest_version()
        if hub and latest and hub.get("version") != latest:
            r.warn(f"MegaNexus {hub.get('version')} installed, {latest} released: Kodi updates it "
                   "from the MegaNexus repository")
        skin = rpc.call("Settings.GetSettingValue", {"setting": "lookandfeel.skin"})["value"]
        (r.ok if skin == "skin.meganexus" or not hub else r.warn)(f"Kodi skin: {skin}")
        groups = rpc.call("PVR.GetChannelGroups", {"channeltype": "tv"})["channelgroups"]
        total_channels = rpc.call("PVR.GetChannels", {
            "channelgroupid": groups[0]["channelgroupid"], "limits": {"start": 0, "end": 1}
        })["limits"]["total"] if groups else 0
        (r.ok if total_channels else r.warn)(f"IPTV Simple Client: {total_channels} TV channels in Kodi")
        pss = re.search(r"TOTAL PSS:\s+(\d+)", adb.shell(
            f"dumpsys meminfo {_q(config.kodi_package)}", check=False))
        if pss:
            r.ok(f"Kodi uses {int(pss.group(1)) // 1024} MB of RAM")
    except (KodiError, OSError, KeyError, IndexError) as e:
        r.warn(f"Kodi JSON-RPC: {e}")
    except AdbError as e:
        r.fail(str(e))
    return 1 if r.failed else 0


# --- rollback -----------------------------------------------------------------------------

def _changed_files(config: Config, adb: Adb, chosen: Path) -> tuple[list[tuple[Path, str]], list[str]]:
    """Settings files (*.xml) of the backup that differ on the TV, and those the TV no longer has."""
    changed, gone = [], []
    root = chosen / "userdata"
    for local in sorted(root.rglob("*.xml")):
        remote = f"{userdata_dir(config)}/{local.relative_to(root).as_posix()}"
        if not adb.exists(remote):
            gone.append(remote)
        elif adb.sha256(remote) != _sha(local):
            changed.append((local, remote))
    return changed, gone


def _overwrite(config: Config, adb: Adb, local: Path, remote: str) -> None:
    """Kodi's folder lets adb replace a file but not create one: stage it, then copy over."""
    stage = f"{_stage_dir(config)}/.restore"
    _push_verified(adb, local, stage)
    adb.shell(f"cp {_q(stage)} {_q(remote)}")
    adb.shell(f"rm -f {_q(stage)}", check=False)
    if adb.sha256(remote) != _sha(local):
        raise MegaNexusError(f"{remote}: restored copy does not match the backup")


def _kodi_running(adb: Adb, config: Config) -> bool:
    return bool(adb.shell(f"pidof {_q(config.kodi_package)}", check=False).strip())


def _wait_rpc(adb: Adb, config: Config, seconds: float) -> KodiRpc | None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        rpc = connect_rpc(adb, config)
        if rpc is not None:
            return rpc
        time.sleep(3)
    return None


def rollback(config: Config, adb: Adb, name: str | None = None, *, dry_run: bool = False,
             force: bool = False, out=print, wait: float = 120) -> int:
    """Put back Kodi's settings files from a backup and turn the MegaNexus add-ons off."""
    available = backups(config)
    chosen = next((b for b in available if b.name == name), None) if name else (
        available[-1] if available else None)
    if chosen is None:
        out(f"Backup {name!r} not found." if name else "No MegaNexus backup: nothing to roll back.")
        return 1
    adb.connect()
    changed, gone = _changed_files(config, adb, chosen)
    out(f"Rollback to {chosen.name}: {len(changed)} settings file(s) to restore")
    for _, remote in changed:
        out(f"  {remote}")
    for remote in gone:
        out(f"  not on the TV any more, left as is: {remote}")
    rpc = connect_rpc(adb, config)
    frozen = rpc is None and _kodi_running(adb, config)  # the app runs, JSON-RPC is silent
    if rpc is not None:
        try:
            if rpc.call("Player.GetActivePlayers"):
                out("REFUSED: Kodi is playing. Stop playback, then run the rollback again.")
                return EXIT_REFUSED
        except OSError:  # answers the ping, not the player: Kodi is stuck
            frozen, rpc = True, None
    if frozen:
        if not force:
            out("REFUSED: Kodi does not answer. If it is frozen and nothing is playing, "
                "run the rollback again with --force to restart it.")
            return EXIT_REFUSED
        out("Kodi does not answer: it will be stopped (--force).")
    if dry_run:
        out("Dry run: nothing was changed on the TV.")
        return 0
    if changed or rpc is None:
        if rpc is not None:
            try:
                rpc.call("Application.Quit")  # Kodi writes its settings on exit: quit first
            except (OSError, KodiError):
                pass
            for _ in range(20):
                if not _kodi_running(adb, config):
                    break
                time.sleep(1)
        adb.shell(f"am force-stop {_q(config.kodi_package)}", check=False)
        for local, remote in changed:
            _overwrite(config, adb, local, remote)
        # Kodi's JSON-RPC only starts once its window is in front, not behind a screensaver
        adb.shell("input keyevent KEYCODE_WAKEUP", check=False)
        adb.shell(f"monkey -p {_q(config.kodi_package)} 1", check=False)
        rpc = _wait_rpc(adb, config, wait)
    if rpc is None:
        out("Settings restored, but Kodi did not answer after the restart. Open Kodi, then "
            "Add-ons > My add-ons: disable MegaNexus Hub, MegaNexus, MegaNexus Skin and "
            "MegaNexus Screensaver.")
        return 1
    for addon_id, info in installed_addons(rpc).items():
        if info.get("enabled"):
            rpc.call("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": False})
            out(f"  {addon_id}: disabled")
    skin = rpc.call("Settings.GetSettingValue", {"setting": "lookandfeel.skin"})["value"]
    expected = _setting(chosen / "userdata" / "guisettings.xml", "lookandfeel.skin")
    out(f"Kodi skin: {skin}")
    if expected and skin != expected:
        out(f"Expected {expected} as in the backup; set it in Settings > Interface > Skin.")
        return 1
    out("Rollback done. Re-enable MegaNexus in Add-ons > My add-ons to use it again.")
    return 0
