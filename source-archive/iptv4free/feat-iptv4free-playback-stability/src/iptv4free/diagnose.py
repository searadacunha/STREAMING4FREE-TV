"""`iptv4free playback-diagnose`: read-only report on how live TV plays on the TV.

It reads Kodi's log, what Kodi is playing, memory, CPU and the Wi-Fi link, then names the
likely causes with a confidence level. Nothing is changed on the TV and playback is not
touched. Stream URLs are reduced to their host name: tokens and playlist paths are never
printed or saved.
"""
from __future__ import annotations

import re
import shlex
import subprocess
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime

from .adb import Adb, AdbError
from .config import Config
from .kodi import KodiError, connect_rpc

KODI_LOG = "/sdcard/Android/data/{pkg}/files/.kodi/temp/kodi.log"
LABELS = ["VideoPlayer.ChannelName", "VideoPlayer.VideoResolution", "VideoPlayer.VideoCodec",
          "VideoPlayer.AudioCodec", "Player.Process(videodecoder)", "Player.Process(audiodecoder)",
          "Player.Process(videofps)", "Player.Time"]
SLOW_OPEN = 10.0     # seconds between OpenFile and the first stream
STALLS_PER_10MIN = 3  # above this a session is "interrupted" (TFX: 22, Gulli: 0.4 on 08/11)


@dataclass
class Session:
    start: datetime
    host: str = "?"
    open_s: float | None = None
    played_s: float = 0.0
    stalls: int = 0
    sync_errors: int = 0
    demux_error: bool = False
    relay_errors: int = 0

    @property
    def stall_rate(self) -> float:
        """Stalls per 10 minutes of playback."""
        return self.stalls * 600 / self.played_s if self.played_s >= 60 else 0.0


def host_of(url: str) -> str:
    """Host of a stream URL; for the local relay, the host of the source it carries."""
    url = url.split("|", 1)[0]
    parts = urllib.parse.urlsplit(url)
    if parts.hostname == "127.0.0.1" and parts.port == 52180:
        try:
            from .health import relay_module
            return host_of(relay_module().decode(parts.path.split("/")[1])[0]) + " (relay)"
        except Exception:
            return "relay"
    return f"{parts.hostname}:{parts.port}" if parts.port else (parts.hostname or "?")


def _ts(line: str) -> datetime | None:
    try:
        return datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return None


def parse_log(text: str) -> list[Session]:
    """One Session per VideoPlayer::OpenFile, with what Kodi logged until it closed."""
    sessions: list[Session] = []
    cur: Session | None = None
    pending_host = "?"
    last_ts = None
    for raw in text.lstrip("﻿").splitlines():
        t = _ts(raw)
        if t is None:
            continue
        last_ts = t
        if "Live Stream URL:" in raw:
            pending_host = host_of(raw.rsplit("Live Stream URL:", 1)[1].strip())
        elif "VideoPlayer::OpenFile" in raw:
            if cur is not None and cur.open_s is not None and not cur.played_s:
                cur.played_s = (t - cur.start).total_seconds() - cur.open_s  # zapped: no CloseFile
            cur = Session(start=t, host=pending_host)
            pending_host = "?"
            sessions.append(cur)
        elif cur is None:
            continue
        elif "Opening stream:" in raw and cur.open_s is None:
            cur.open_s = (t - cur.start).total_seconds()
        elif "stream stalled" in raw:
            cur.stalls += 1
        elif "large audio sync error" in raw:
            cur.sync_errors += 1
        elif "Error creating demuxer" in raw:
            cur.demux_error = True
        elif "IPTV4FREE relay:" in raw:
            cur.relay_errors += 1
        elif "CVideoPlayer::CloseFile()" in raw and cur.open_s is not None and not cur.played_s:
            cur.played_s = (t - cur.start).total_seconds() - cur.open_s
    if cur is not None and cur.open_s is not None and not cur.played_s and last_ts:
        cur.played_s = (last_ts - cur.start).total_seconds() - cur.open_s  # still playing
    return sessions


@dataclass
class Finding:
    cause: str
    confidence: str  # high | medium | low
    evidence: str
    action: str


@dataclass
class State:
    kodi_running: bool = False
    kodi_version: str = ""
    addon_version: str = ""
    relay_listening: bool | None = None
    playing: dict = field(default_factory=dict)
    mem_total_mb: int = 0
    mem_available_mb: int = 0
    swap_used_mb: int = 0
    kodi_rss_mb: int = 0
    kodi_swap_mb: int = 0
    top: list[tuple[str, float]] = field(default_factory=list)  # (process, %CPU, 400 % = 4 cores)
    wifi: dict = field(default_factory=dict)
    ping_tv: dict = field(default_factory=dict)        # Mac -> TV (LAN)
    ping_internet: dict = field(default_factory=dict)  # TV -> 1.1.1.1 (not the IPTV servers)
    sessions: list[Session] = field(default_factory=list)
    health: dict = field(default_factory=dict)         # host -> verdict counts from health.json


def _kb(text: str, key: str) -> int:
    m = re.search(rf"^{key}:\s+(\d+)", text, re.M)
    return int(m.group(1)) if m else 0


def parse_ping(text: str) -> dict:
    """Loss, average and jitter (mdev) from ping's summary lines (macOS or Android)."""
    out = {}
    m = re.search(r"([\d.]+)% packet loss", text)
    if m:
        out["loss_pct"] = float(m.group(1))
    m = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", text)
    if m:
        out.update(min_ms=float(m.group(1)), avg_ms=float(m.group(2)), max_ms=float(m.group(3)),
                   jitter_ms=float(m.group(4)))
    return out


def parse_top(text: str, skip=("top", "sh")) -> list[tuple[str, float]]:
    """(process, %CPU) from the last sample of `top -b -n 2`; 400 % = four busy cores."""
    block = text.split("Tasks:")[-1]
    rows = []
    for line in block.splitlines():
        p = line.split()
        if len(p) >= 12 and p[0].isdigit():
            try:
                cpu = float(p[8])
            except ValueError:
                continue
            name = p[11].split("/")[-1]
            if name not in skip:
                rows.append((name, cpu))
    return sorted(rows, key=lambda r: -r[1])[:5]


def collect(config: Config, adb: Adb, ping=True) -> State:
    s = State()
    pkg = config.kodi_package
    pid = adb.shell(f"pidof {pkg}", check=False).strip().split(" ")[0]
    s.kodi_running = bool(pid)
    meminfo = adb.shell("cat /proc/meminfo", check=False)
    s.mem_total_mb, s.mem_available_mb = _kb(meminfo, "MemTotal") // 1024, _kb(meminfo, "MemAvailable") // 1024
    s.swap_used_mb = (_kb(meminfo, "SwapTotal") - _kb(meminfo, "SwapFree")) // 1024
    if pid:
        status = adb.shell(f"cat /proc/{pid}/status", check=False)
        s.kodi_rss_mb, s.kodi_swap_mb = _kb(status, "VmRSS") // 1024, _kb(status, "VmSwap") // 1024
    s.top = parse_top(adb.shell("top -b -n 2 -d 2 -m 8", check=False, timeout=20))
    wifi = adb.shell("dumpsys wifi | grep -m1 mWifiInfo", check=False)
    for key, pat in (("rssi_dbm", r"RSSI: (-?\d+)"), ("link_mbps", r"Link speed: (\d+)Mbps"),
                     ("standard", r"Wi-Fi standard: (\w+)")):
        m = re.search(pat, wifi)
        if m:
            s.wifi[key] = m.group(1)
    dev = adb.shell("cat /proc/net/dev", check=False)
    m = re.search(r"wlan0:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", dev)
    if m:
        s.wifi["rx_packets"], s.wifi["rx_errors"], s.wifi["rx_drops"] = int(m.group(2)), int(m.group(3)), int(m.group(4))
    tcp = adb.shell("cat /proc/net/tcp", check=False)  # local relay: 127.0.0.1:52180, state 0A = LISTEN
    s.relay_listening = "0100007F:CBD4 00000000:0000 0A" in tcp
    if ping:
        ip = config.tv_address.split(":")[0]
        if re.fullmatch(r"[\d.]+", ip or ""):
            r = subprocess.run(["ping", "-c", "20", "-i", "0.2", ip], capture_output=True, text=True, timeout=30)
            s.ping_tv = parse_ping(r.stdout)
        s.ping_internet = parse_ping(adb.shell("ping -c 10 -i 0.3 1.1.1.1", check=False, timeout=30))
    log = adb.shell(f"cat {shlex.quote(KODI_LOG.format(pkg=pkg))}", check=False, timeout=60)
    s.sessions = parse_log(log)
    rpc = connect_rpc(adb, config) if pid else None
    if rpc:
        try:
            s.kodi_version = rpc.call("Application.GetProperties", {"properties": ["version"]})["version"]
            s.kodi_version = f"{s.kodi_version['major']}.{s.kodi_version['minor']}"
            s.addon_version = (rpc.call("Addons.GetAddonDetails", {"addonid": "script.iptv4free",
                               "properties": ["version", "enabled"]}) or {}).get("addon", {}).get("version", "")
            if rpc.call("Player.GetActivePlayers"):
                s.playing = rpc.call("XBMC.GetInfoLabels", {"labels": LABELS})
        except (OSError, KodiError):
            pass
    return s


def health_by_host(records: dict) -> dict:
    """Sustained-check verdicts (health.json) grouped by host."""
    out: dict[str, dict[str, int]] = {}
    for key, r in records.items():
        host = host_of(key)
        out.setdefault(host, {}).setdefault(r.get("verdict", "?"), 0)
        out[host][r.get("verdict", "?")] += 1
    return out


def findings(s: State) -> list[Finding]:
    out: list[Finding] = []
    played = [x for x in s.sessions if x.played_s >= 60]
    by_host: dict[str, list[Session]] = {}
    for x in played:
        by_host.setdefault(x.host.replace(" (relay)", ""), []).append(x)
    bad = {h: v for h, v in by_host.items()
           if sum(x.stalls for x in v) * 600 / sum(x.played_s for x in v) > STALLS_PER_10MIN}
    good = {h: v for h, v in by_host.items() if h not in bad}
    wifi_ok = int(s.wifi.get("rssi_dbm", -100)) > -67 and int(s.wifi.get("link_mbps", 0)) >= 100
    for host, v in sorted(bad.items()):
        rate = sum(x.stalls for x in v) * 600 / sum(x.played_s for x in v)
        measured = s.health.get(host, {})
        conf = "high" if (good and wifi_ok) or measured.get("unstable") else "medium"
        why = [f"{rate:.0f} stalls per 10 min over {sum(x.played_s for x in v) / 60:.0f} min on {host}"]
        if good:
            why.append(f"same TV and Wi-Fi play {', '.join(sorted(good)[:3])} without interruptions")
        if measured:
            why.append(f"sustained check from the Mac: {measured}")
        relayed = any("(relay)" in x.host for x in v)
        out.append(Finding(
            "the source server delivers more slowly than the stream plays", conf, "; ".join(why),
            "already through the relay: compare sources with `iptv4free health`, prefer another source"
            if relayed else
            "run `iptv4free health` on these channels; if the relay helps, route them through it "
            "(`relay = true`, add-on 0.4.0)"))
    if bad and not good and not wifi_ok:
        out.append(Finding("weak Wi-Fi link", "medium", f"Wi-Fi {s.wifi}", "move the box or the TV, or use a cable"))
    slow = [x for x in s.sessions if x.open_s and x.open_s > SLOW_OPEN]
    if slow:
        hosts = sorted({x.host for x in slow})
        out.append(Finding(
            "slow channel start", "medium",
            f"{len(slow)} openings above {SLOW_OPEN:.0f} s (max {max(x.open_s for x in slow):.0f} s) on {', '.join(hosts[:4])}",
            "multi-variant masters (Pluto, Samsung...): Kodi opens every variant; the relay serves only "
            "the best one (18.6 s -> 5.8 s measured)"))
    failed = [x for x in s.sessions if x.demux_error]
    if failed:
        out.append(Finding("streams that do not open", "medium",
                           f"{len(failed)} 'Error creating demuxer' on {', '.join(sorted({x.host for x in failed})[:4])}",
                           "the source is down or blocked; `iptv4free scan` drops it after 3 failed scans"))
    if any(x.relay_errors for x in s.sessions):
        n = sum(x.relay_errors for x in s.sessions)
        out.append(Finding("relay errors", "high", f"{n} 'IPTV4FREE relay:' lines in kodi.log",
                           "read them in kodi.log; roll back with `iptv4free rollback` if channels fail"))
    if s.relay_listening is False and any("(relay)" in x.host for x in s.sessions):
        out.append(Finding("relay not running", "high", "relayed channels but nothing listens on 127.0.0.1:52180",
                           "enable the IPTV4FREE add-on (0.4.0+) and restart Kodi"))
    if s.mem_available_mb and (s.mem_available_mb < 250 or s.kodi_swap_mb > 150):
        out.append(Finding("memory pressure", "medium",
                           f"{s.mem_available_mb} MB available of {s.mem_total_mb}, Kodi {s.kodi_rss_mb} MB in RAM "
                           f"+ {s.kodi_swap_mb} MB swapped",
                           "close apps left in the background (Android TV keeps them in memory)"))
    hogs = [(n, c) for n, c in s.top if c >= 20 and "kodi" not in n]
    if hogs:
        out.append(Finding("background CPU use", "low",
                           ", ".join(f"{n} {c:.0f}%" for n, c in hogs) + " (400% = four cores)",
                           "menus may respond slower; playback has spare CPU if the total stays well below 400%"))
    if s.ping_tv.get("loss_pct", 0) >= 2 or s.ping_tv.get("jitter_ms", 0) > 30:
        out.append(Finding("unstable local Wi-Fi", "medium", f"Mac -> TV ping {s.ping_tv}",
                           "check the box channel and interference"))
    return out


def report(s: State) -> str:
    lines = ["IPTV4FREE playback diagnosis", "=" * 28,
             f"Kodi: {'running' if s.kodi_running else 'not running'} {s.kodi_version}; "
             f"IPTV4FREE add-on {s.addon_version or '?'}; relay {'listening' if s.relay_listening else 'not listening'}",
             f"Memory: {s.mem_available_mb} MB available of {s.mem_total_mb} MB, swap used {s.swap_used_mb} MB; "
             f"Kodi {s.kodi_rss_mb} MB + {s.kodi_swap_mb} MB swapped",
             "CPU (last 2 s, 400% = 4 cores): " + ", ".join(f"{n} {c:.0f}%" for n, c in s.top),
             f"Wi-Fi: {s.wifi}",
             f"Ping Mac -> TV: {s.ping_tv or 'not measured'}",
             f"Ping TV -> 1.1.1.1: {s.ping_internet or 'not measured'} (says nothing about the IPTV servers)"]
    if s.playing:
        p = s.playing
        lines.append(f"Playing: {p.get('VideoPlayer.ChannelName')} {p.get('VideoPlayer.VideoResolution')}p "
                     f"{p.get('VideoPlayer.VideoCodec')}/{p.get('VideoPlayer.AudioCodec')}, video decoder "
                     f"{p.get('Player.Process(videodecoder)')}, audio decoder {p.get('Player.Process(audiodecoder)')}")
    lines += ["", "Sessions in kodi.log (host only):"]
    for x in s.sessions[-15:]:
        lines.append(f"  {x.start:%d/%m %H:%M} {x.host:34s} open {'-' if x.open_s is None else f'{x.open_s:.1f}s':>6} "
                     f"played {x.played_s / 60:5.1f} min, {x.stalls} stalls"
                     + (" (%.0f/10 min)" % x.stall_rate if x.stall_rate else "")
                     + (", did not open" if x.demux_error and x.open_s is None else ""))
    lines += ["", "Likely causes:"]
    found = findings(s)
    if not found:
        lines.append("  nothing abnormal in the log and the measurements")
    for f in found:
        lines += [f"  [{f.confidence}] {f.cause}", f"      evidence: {f.evidence}", f"      action: {f.action}"]
    return "\n".join(lines)


def run(config: Config, adb: Adb, out=print, ping=True) -> int:
    from .health import HealthBook
    adb.connect()
    try:
        s = collect(config, adb, ping)
    except AdbError as e:
        out(f"TV not reachable: {e}")
        return 1
    s.health = health_by_host(HealthBook(config.state_dir / "health.json").records)
    text = report(s)
    out(text)
    dest = config.state_dir / "diagnostics" / time.strftime("%Y%m%d-%H%M%S.txt")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text + "\n", encoding="utf-8")
    out(f"\nSaved to {dest} (stays on this Mac)")
    return 0
