"""Thin wrapper around the adb command line. Every call has a timeout.

A busy or frozen TV can leave adb waiting forever; a timeout turns that into a clear error.
"""
from __future__ import annotations

import logging
import shlex
import subprocess

log = logging.getLogger(__name__)


class AdbError(RuntimeError):
    pass


class Adb:
    def __init__(self, adb: str, serial: str, timeout: float = 30.0):
        if not serial:
            raise AdbError("no TV address configured: set [tv] address or IPTV4FREE_TV")
        self.adb, self.serial, self.timeout = adb, serial, timeout

    def _run(self, args: list[str], timeout: float | None = None, check: bool = True) -> str:
        cmd = [self.adb, *args]
        log.debug("adb: %s", " ".join(cmd))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout or self.timeout)
        except FileNotFoundError:
            raise AdbError(f"adb not found ({self.adb}); install Android platform-tools") from None
        except subprocess.TimeoutExpired:
            raise AdbError(f"adb timed out after {timeout or self.timeout:.0f}s: "
                           f"{' '.join(args[:4])}. The TV may be busy or frozen; retry, "
                           "or restart the TV if it stays unresponsive") from None
        out = (proc.stdout or "") + (proc.stderr or "")
        # adb shell returns the remote status; some adb versions print errors with status 0
        if check and (proc.returncode != 0 or out.lstrip().startswith(("error:", "adb: error"))):
            raise AdbError(f"adb {' '.join(args[:4])} failed: {out.strip()[:300]}")
        return proc.stdout or ""

    def connect(self) -> None:
        """Connect over the network (host:port serials) and require an authorized device."""
        if ":" in self.serial:
            out = self._run(["connect", self.serial], check=False)
            if "connected" not in out and "already" not in out:
                log.debug("adb connect said: %s", out.strip())
        state = self._run(["-s", self.serial, "get-state"], check=False).strip()
        if state != "device":
            raise AdbError(
                f"TV {self.serial} is not ready (state: {state or 'unreachable'}). Check that "
                "it is on, on the same network, and that USB/network debugging is authorized")

    def shell(self, command: str, timeout: float | None = None, check: bool = True) -> str:
        return self._run(["-s", self.serial, "shell", command], timeout, check)

    def push(self, local: str, remote: str) -> None:
        self._run(["-s", self.serial, "push", local, remote], timeout=max(self.timeout, 120))

    def pull(self, remote: str, local: str) -> None:
        self._run(["-s", self.serial, "pull", remote, local], timeout=max(self.timeout, 120))

    def forward(self, local_port: int, remote_port: int) -> None:
        self._run(["-s", self.serial, "forward", f"tcp:{local_port}", f"tcp:{remote_port}"])

    def install(self, apk: str) -> None:
        self._run(["-s", self.serial, "install", "-r", apk], timeout=max(self.timeout, 600))

    def exists(self, path: str) -> bool:
        return self.shell(f"[ -e {shlex.quote(path)} ] && echo yes || echo no").strip() == "yes"

    def sha256(self, path: str) -> str:
        out = self.shell(f"sha256sum {shlex.quote(path)}").split()
        if not out or len(out[0]) != 64:
            raise AdbError(f"cannot checksum {path} on the TV: {' '.join(out)[:100]}")
        return out[0]

    def getprop(self, name: str) -> str:
        return self.shell(f"getprop {shlex.quote(name)}").strip()

    def package_version(self, package: str) -> str | None:
        """versionName of an installed package, None if not installed."""
        out = self.shell(f"dumpsys package {shlex.quote(package)} | grep -m1 versionName",
                         check=False).strip()
        return out.split("=", 1)[1].strip() if "versionName=" in out else None
