"""Read-only diagnostics. Nothing here changes the TV or Kodi."""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

from .adb import Adb, AdbError
from .config import Config
from .kodi import KodiError, connect_rpc
from .playlists import parse_m3u
from .updates import ScanHistory


class Report:
    def __init__(self, out=print):
        self.out, self.failed = out, False

    def ok(self, msg: str) -> None:
        self.out(f"[ OK ] {msg}")

    def warn(self, msg: str) -> None:
        self.out(f"[WARN] {msg}")

    def fail(self, msg: str) -> None:
        self.failed = True
        self.out(f"[FAIL] {msg}")


def _local(config: Config, r: Report) -> int:
    r.ok(f"config {config.path}: {len(config.lineups)} lineup(s)")
    history = ScanHistory(config.state_dir / "scan-history.json")
    if history.streams:
        last = max(s.get("checked", 0) for s in history.streams.values())
        alive = sum(history.alive(k, config.max_failed_scans) for k in history.streams)
        age = (time.time() - last) / 3600
        r.ok(f"scan history: {len(history.streams)} streams, {alive} alive, last scan {age:.1f} h ago")
    else:
        r.warn("no scan yet: run `iptv4free scan`")
    total = 0
    for lu in config.lineups:
        built = config.output_dir / f"{lu.id}.m3u"
        if built.exists():
            n = len(parse_m3u(built.read_text(encoding="utf-8")).entries)
            total += n
            r.ok(f"built playlist {lu.id}: {n} channels")
        else:
            r.warn(f"no built playlist for {lu.id}: run `iptv4free build`")
    return total


def run(config: Config, adb: Adb, out=print) -> int:
    r = Report(out)
    local_total = _local(config, r)

    if not (shutil.which(config.adb) or Path(config.adb).exists()):
        r.fail(f"adb not found ({config.adb}); install Android platform-tools")
        return 1
    try:
        adb.connect()
    except AdbError as e:
        r.fail(str(e))
        return 1
    try:
        release, abi = adb.getprop("ro.build.version.release"), adb.getprop("ro.product.cpu.abi")
        r.ok(f"TV {adb.serial}: Android {release}, {abi}")
        version = adb.package_version(config.kodi_package)
        if not version:
            r.fail(f"Kodi ({config.kodi_package}) is not installed: run `iptv4free setup --install-kodi`")
            return 1
        r.ok(f"Kodi {version} installed")
        perms = adb.shell(f"dumpsys package {config.kodi_package} | grep 'READ_EXTERNAL_STORAGE: granted'",
                          check=False)
        if "granted=true" in perms:
            r.ok("Kodi may read shared storage")
        else:
            r.warn("Kodi has not been granted storage access; open Kodi once and accept the "
                   "permission prompt, or it cannot read the playlists")
        for lu in config.lineups:
            remote = config.remote_path(lu)
            built = config.output_dir / f"{lu.id}.m3u"
            if not adb.exists(remote):
                r.warn(f"{remote} not on the TV yet: run `iptv4free deploy`")
            elif built.exists() and adb.sha256(remote) != hashlib.sha256(built.read_bytes()).hexdigest():
                r.warn(f"{remote} differs from the latest build: run `iptv4free deploy`")
            else:
                r.ok(f"{remote} present" + (" and up to date" if built.exists() else ""))
    except AdbError as e:
        r.fail(str(e))
        return 1

    try:
        rpc = connect_rpc(adb, config)
    except AdbError as e:
        r.warn(f"cannot forward Kodi JSON-RPC: {e}")
        rpc = None
    if rpc is None:
        r.warn("Kodi is not running: start it on the TV to check IPTV Simple Client")
        return 1 if r.failed else 0
    try:
        addon = rpc.call("Addons.GetAddonDetails",
                         {"addonid": "pvr.iptvsimple", "properties": ["enabled", "version"]})["addon"]
        if addon.get("enabled"):
            r.ok(f"IPTV Simple Client {addon.get('version')} enabled")
        else:
            r.fail("IPTV Simple Client is installed but disabled")
        groups = rpc.call("PVR.GetChannelGroups", {"channeltype": "tv"})["channelgroups"]
        if groups:
            first = rpc.call("PVR.GetChannels", {"channelgroupid": groups[0]["channelgroupid"],
                                                 "limits": {"start": 0, "end": 1}})
            r.ok(f"Kodi lists {first['limits']['total']} TV channels "
                 f"({local_total} in the local build)")
        else:
            r.warn("Kodi has no TV channels yet: configure IPTV Simple Client (`iptv4free setup`)")
    except KodiError as e:
        if "addon" in str(e).lower() or "invalid params" in str(e).lower():
            r.fail("IPTV Simple Client is not installed: see `iptv4free setup`")
        else:
            r.warn(f"Kodi JSON-RPC: {e}")
    except OSError as e:
        r.warn(f"Kodi JSON-RPC: {e}")
    return 1 if r.failed else 0
