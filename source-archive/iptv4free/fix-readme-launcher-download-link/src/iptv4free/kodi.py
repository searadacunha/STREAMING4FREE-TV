"""Kodi side: JSON-RPC, restarts, official APK installation, one-time setup instructions."""
from __future__ import annotations

import hashlib
import itertools
import json
import logging
import re
import socket
import time
import urllib.request
from pathlib import Path

from .adb import Adb, AdbError
from .config import Config

log = logging.getLogger(__name__)

MIRROR = "https://mirrors.kodi.tv/releases/android"
# Android primary ABI -> directory on the Kodi mirror
ABI_DIRS = {"armeabi-v7a": "arm", "arm64-v8a": "arm64-v8a", "x86": "x86"}


class KodiError(RuntimeError):
    pass


class KodiRpc:
    """JSON-RPC over Kodi's raw TCP interface (port 9090, reachable through `adb forward`).

    Kodi pushes notifications on the same socket, so replies are matched by request id.
    """

    _ids = itertools.count(1)

    def __init__(self, host: str, port: int, timeout: float = 15.0):
        self.host, self.port, self.timeout = host, port, timeout

    def call(self, method: str, params: dict | None = None):
        rid = next(self._ids)
        request = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}
        decoder, buf = json.JSONDecoder(), ""
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall(json.dumps(request).encode())
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    raise KodiError(f"{method}: connection closed by Kodi")
                buf += chunk.decode("utf-8", "replace")
                while buf.strip():
                    try:
                        obj, end = decoder.raw_decode(buf.lstrip())
                    except ValueError:
                        break  # partial message, read more
                    buf = buf.lstrip()[end:]
                    if obj.get("id") == rid:
                        if "error" in obj:
                            raise KodiError(f"{method}: {obj['error'].get('message', obj['error'])}")
                        return obj.get("result")


def connect_rpc(adb: Adb, config: Config) -> KodiRpc | None:
    """Forward the JSON-RPC port and ping Kodi. None if Kodi is not running."""
    adb.forward(config.forward_port, config.jsonrpc_port)
    rpc = KodiRpc("127.0.0.1", config.forward_port)
    try:
        return rpc if rpc.call("JSONRPC.Ping") == "pong" else None
    except (OSError, KodiError):
        return None


def _wait_stopped(adb: Adb, package: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not adb.shell(f"pidof {package}", check=False).strip():
            return True
        time.sleep(1)
    return False


def restart(adb: Adb, config: Config, policy: str) -> str:
    """Restart Kodi so IPTV Simple reloads its playlists. Returns what happened.

    'auto' restarts only a running, idle Kodi; 'always' restarts even during playback.
    Kodi saves its settings only on a clean exit, so it is asked to quit before any kill.
    """
    if policy == "never":
        return "Kodi not restarted (policy: never); new playlists load at its next start"
    rpc = connect_rpc(adb, config)
    if rpc is None and policy == "auto":
        return "Kodi is not running; new playlists load when it starts"
    if rpc is not None:
        if policy == "auto" and rpc.call("Player.GetActivePlayers"):
            return "Kodi is playing; not restarted. New playlists load at its next start"
        try:
            rpc.call("Application.Quit")
        except (OSError, KodiError):
            pass  # Kodi may close the socket while quitting
        _wait_stopped(adb, config.kodi_package, 20)
    adb.shell(f"am force-stop {config.kodi_package}", check=False)
    adb.shell(f"monkey -p {config.kodi_package} 1", check=False)
    return "Kodi restarted"


def _version_key(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("."))


def find_apk(abi: str, version: str = "latest", listing: str | None = None) -> str:
    """URL of the official Kodi APK for an ABI. `listing` is the mirror page (for tests)."""
    if abi not in ABI_DIRS:
        raise KodiError(f"no official Kodi build for ABI {abi!r} (supported: {list(ABI_DIRS)})")
    base = f"{MIRROR}/{ABI_DIRS[abi]}/"
    if listing is None:
        with urllib.request.urlopen(base, timeout=30) as resp:
            listing = resp.read().decode("utf-8", "replace")
    pattern = re.compile(rf'href="(kodi-(\d+(?:\.\d+)+)-([A-Za-z]+)-{re.escape(abi)}\.apk)"')
    builds = {m.group(2): m.group(1) for m in pattern.finditer(listing)}
    if not builds:
        raise KodiError(f"no Kodi APK found at {base}")
    pick = max(builds, key=_version_key) if version == "latest" else version
    if pick not in builds:
        raise KodiError(f"Kodi {version} not found for {abi}; available: {sorted(builds)}")
    return base + builds[pick]


def download_apk(url: str, dest_dir: Path) -> Path:
    """Download an APK and check it against the mirror's published SHA-256."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    apk = dest_dir / url.rsplit("/", 1)[1]
    with urllib.request.urlopen(url + ".sha256", timeout=30) as resp:
        expected = resp.read().decode().split()[0].lower()
    if not apk.exists() or hashlib.sha256(apk.read_bytes()).hexdigest() != expected:
        tmp = apk.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=120) as resp, open(tmp, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
        actual = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if actual != expected:
            tmp.unlink()
            raise KodiError(f"checksum mismatch for {url}: expected {expected}, got {actual}")
        tmp.replace(apk)
    return apk


def install_kodi(adb: Adb, config: Config, version: str = "latest") -> str:
    abi = adb.getprop("ro.product.cpu.abi")
    url = find_apk(abi, version)
    apk = download_apk(url, config.state_dir / "downloads")
    log.info("installing %s", apk.name)
    adb.install(str(apk))
    installed = adb.package_version(config.kodi_package)
    if not installed:
        raise AdbError("Kodi installation did not complete")
    return installed


def instructions(config: Config) -> str:
    """One-time Kodi configuration. Kodi keeps add-on settings in app-private storage,
    which adb cannot write, so these steps are done once with the TV remote."""
    lines = [
        "One-time Kodi configuration (with the TV remote, Kodi in English):",
        "  1. Add-ons > Install from repository > Kodi Add-on repository > PVR clients >",
        "     IPTV Simple Client > Install (accept the additional add-ons).",
        "  2. Add-ons > My add-ons > PVR clients > IPTV Simple Client > Configure.",
        "     Edit the existing configuration for the first lineup, then",
        "     'Add add-on configuration' for each other lineup:",
    ]
    for i, lu in enumerate(config.lineups, 1):
        lines += [
            f"     [{i}] Name: {lu.name}",
            "         General > Location: Remote path (Internet address)",
            f"         General > M3U playlist URL: {config.kodi_path(lu)}",
        ]
        if lu.epg:
            lines.append(f"         EPG > XMLTV URL: {lu.epg}")
    lines += [
        "  3. Optional, Settings > PVR & Live TV > General > Client priorities:",
        "     give the first lineup the highest number so its channels are listed first.",
        "  4. Restart Kodi, then run `iptv4free doctor`.",
    ]
    return "\n".join(lines)
