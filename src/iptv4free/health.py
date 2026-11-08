"""Sustained stream checks: what a viewer would live through over several minutes.

`scanner` proves a stream answers (a few KB). This module follows a stream like a player
does: it reloads the HLS media playlist, downloads every new segment in full, and replays
the download times through a small player buffer to count the stalls a viewer would see.
Direct streams (MPEG-TS over HTTP) are read continuously and gaps in the data are counted.

Run it on a few channels at a time (favourites, channels with several sources), never on a
whole lineup at once, and not while the same connection is used to watch TV.
"""
from __future__ import annotations

import functools
import importlib.util
import json
import ssl
import threading
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .playlists import Entry, request_parts, effective_url
from .scanner import PLAYLIST_LIMIT, Target
from .updates import atomic_write

SEGMENT_LIMIT = 64 * 1024 * 1024
START_SEGMENTS = 3       # like FFmpeg's live_start_index=-3: start three segments from the live edge
GAP_SECONDS = 2.0        # direct streams: no data for this long is counted as a stall
CHUNK = 64 * 1024
# A stream is "unstable" if a player would have stalled more than this share of the time,
# or if requests failed this often. Measured on the TV (08/11): Gulli 2 stalls/56 min was
# watchable, TFX 140 stalls/63 min was not; 1 % of the time is ~3 s per 5 min.
MAX_STALL_RATIO = 0.01
MAX_ERRORS = 3


@dataclass
class Health:
    key: str
    kind: str = "error"            # hls | direct | dash | error
    seconds: float = 0.0           # how long the stream was followed
    startup: float | None = None   # seconds until the first media could play (None: never)
    segments: int = 0
    missed: int = 0                # segments that left the playlist before being fetched
    errors: int = 0                # HTTP errors and timeouts
    stalls: int = 0
    stall_seconds: float = 0.0
    variants: int = 0              # variants in the HLS master (Kodi's FFmpeg opens them all)
    bitrate: float = 0.0           # bits/s: declared BANDWIDTH, or measured for direct streams
    speed_p10: float = 0.0         # bits/s, 10th percentile of segment download speed
    slow_segments: int = 0         # downloads that took longer than the segment lasts
    detail: str = ""
    checked: float = field(default_factory=time.time)

    @property
    def verdict(self) -> str:
        if self.startup is None:
            return "dead"
        if self.kind == "dash":
            return "unknown"
        watched = max(self.seconds - self.startup, 1.0)
        if self.stall_seconds / watched > MAX_STALL_RATIO or self.errors > MAX_ERRORS or self.missed:
            return "unstable"
        return "stable"


Fetch = Callable[[str, dict, int, float], tuple[str, bytes]]


def _fetch(url: str, headers: dict, limit: int, timeout: float) -> tuple[str, bytes]:
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.geturl(), resp.read(limit)


def parse_media_playlist(base: str, text: str) -> tuple[int, float, list[tuple[int, float, str]], bool]:
    """(media sequence, target duration, [(sequence, duration, url)], ended)."""
    seq, target, ended, dur = 0, 0.0, False, None
    segments = []
    for line in (ln.strip() for ln in text.splitlines()):
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            seq = int(line.split(":", 1)[1])
        elif line.startswith("#EXT-X-TARGETDURATION:"):
            target = float(line.split(":", 1)[1])
        elif line.startswith("#EXTINF:"):
            dur = float(line[8:].split(",", 1)[0] or 0)
        elif line.startswith("#EXT-X-ENDLIST"):
            ended = True
        elif line and not line.startswith("#"):
            segments.append((seq + len(segments), dur or target, urllib.parse.urljoin(base, line)))
            dur = None
    return seq, target, segments, ended


def best_variant(base: str, text: str) -> tuple[str, float] | None:
    """Highest-bandwidth variant of an HLS master playlist, as Kodi's FFmpeg picks it."""
    best = None
    lines = [ln.strip() for ln in text.splitlines()]
    for i, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF:"):
            continue
        bw = 0.0
        for part in line.split(":", 1)[1].split(","):
            k, _, v = part.partition("=")
            if k == "BANDWIDTH" and v.isdigit():
                bw = float(v)
        uri = next((ln for ln in lines[i + 1:] if ln and not ln.startswith("#")), None)
        if uri and (best is None or bw > best[1]):
            best = (urllib.parse.urljoin(base, uri), bw)
    return best


def replay(arrivals: list[tuple[float, float]], start: float, end: float | None = None) -> tuple[int, float]:
    """Stalls a player sees. `arrivals` = (time the segment finished downloading, its duration),
    in playback order; playback starts at `start` and resumes as soon as the next segment lands.
    With `end`, a buffer that runs dry before the end of the test counts as a stall too."""
    stalls, stalled, clock, buffered = 0, 0.0, start, 0.0  # `buffered` s of media play from `clock`
    for t, dur in arrivals:
        if t > clock + buffered and t > start:  # the buffer ran dry before this segment arrived
            stalls += 1
            stalled += t - (clock + buffered)
            clock, buffered = t, 0.0
        elif t > clock:
            buffered -= t - clock
            clock = t
        buffered += dur
    if end is not None and end > clock + buffered:  # downloads stopped: the picture froze
        stalls += 1
        stalled += end - (clock + buffered)
    return stalls, stalled


def check_hls(h: Health, url: str, headers: dict, seconds: float, timeout: float,
              fetch: Fetch, clock: Callable[[], float], sleep: Callable[[float], None]) -> Health:
    h.kind = "hls"
    t0 = clock()
    final, body = fetch(url, headers, PLAYLIST_LIMIT, timeout)
    text = body.decode("utf-8", "replace")
    if "#EXT-X-STREAM-INF" in text:
        h.variants = text.count("#EXT-X-STREAM-INF")
        variant = best_variant(final, text)
        if not variant:
            h.detail = "master playlist without variants"
            return h
        url, h.bitrate = variant
        final, body = fetch(url, headers, PLAYLIST_LIMIT, timeout)
        text = body.decode("utf-8", "replace")
    last_seq, arrivals, speeds, first = None, [], [], None
    while True:
        _, target, segments, ended = parse_media_playlist(final, text)
        if not segments:
            h.detail = "media playlist without segments"
            break
        if last_seq is None:
            todo = segments[-START_SEGMENTS:]
        else:
            todo = [s for s in segments if s[0] > last_seq]
            if todo and todo[0][0] > last_seq + 1:
                h.missed += todo[0][0] - last_seq - 1
        for seq, dur, seg_url in todo:
            started = clock()
            try:
                _, data = fetch(seg_url, headers, SEGMENT_LIMIT, timeout)
            except (OSError, urllib.error.URLError) as e:
                h.errors += 1
                h.detail = f"segment: {type(e).__name__}"
                last_seq = seq
                continue
            took = max(clock() - started, 1e-3)
            arrivals.append((clock(), dur))
            if first is None:
                first = clock()
                h.startup = first - t0
            speeds.append(len(data) * 8 / took)
            h.slow_segments += took > dur
            h.segments += 1
            last_seq = seq
        if ended or clock() - t0 >= seconds:
            break
        sleep(max(0.5, (target or 6) / 2))
        try:
            final, body = fetch(url, headers, PLAYLIST_LIMIT, timeout)
            text = body.decode("utf-8", "replace")
        except (OSError, urllib.error.URLError) as e:
            h.errors += 1
            h.detail = f"playlist: {type(e).__name__}"
            sleep(1.0)
    h.seconds = clock() - t0
    if first is not None:
        h.stalls, h.stall_seconds = replay(arrivals, first, None if ended else clock())
        h.speed_p10 = statistics.quantiles(speeds, n=10)[0] if len(speeds) >= 2 else speeds[0]
    return h


def check_direct(h: Health, url: str, headers: dict, seconds: float, timeout: float,
                 clock: Callable[[], float], sleep: Callable[[float], None]) -> Health:
    """Read a continuous stream; a gap of GAP_SECONDS without data counts as a stall."""
    h.kind = "direct"
    t0 = clock()
    total, last = 0, None
    while clock() - t0 < seconds:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
                while clock() - t0 < seconds:
                    chunk = resp.read(CHUNK)
                    now = clock()
                    if not chunk:
                        break
                    if last is None:
                        h.startup = now - t0
                    elif now - last >= GAP_SECONDS:
                        h.stalls += 1
                        h.stall_seconds += now - last
                    last = now
                    total += len(chunk)
        except (OSError, urllib.error.URLError) as e:
            h.errors += 1
            h.detail = f"{type(e).__name__}: {str(e)[:80]}"
            if h.errors > MAX_ERRORS:
                break
            sleep(1.0)
    h.seconds = clock() - t0
    if h.startup is not None:
        h.bitrate = total * 8 / max(h.seconds - h.startup, 1.0)
    return h


def check(target: Target, seconds: float, timeout: float = 10.0, default_user_agent: str = "",
          fetch: Fetch = _fetch, clock: Callable[[], float] = time.monotonic,
          sleep: Callable[[float], None] = time.sleep) -> Health:
    headers = dict(target.headers)
    if default_user_agent:
        headers.setdefault("User-Agent", default_user_agent)
    h = Health(target.key)
    try:
        final, head = fetch(target.url, headers, 4096, timeout)
        if head.lstrip().startswith(b"#EXTM3U"):
            return check_hls(h, target.url, headers, seconds, timeout, fetch, clock, sleep)
        if b"<MPD" in head:
            h.kind, h.startup, h.detail = "dash", 0.0, "DASH: not followed (inputstream.adaptive buffers it)"
            return h
        return check_direct(h, target.url, headers, seconds, timeout, clock, sleep)
    except Exception as e:  # any failure means "not watchable"; keep the reason
        h.detail = f"{type(e).__name__}: {str(e)[:120]}"
        return h


def check_many(targets: Iterable[Target], seconds: float, workers: int = 2, timeout: float = 10.0,
               default_user_agent: str = "") -> list[Health]:
    """A few streams at a time: each one downloads at full bitrate for `seconds`."""
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(lambda t: check(t, seconds, timeout, default_user_agent), targets))


class HealthBook:
    """Last sustained check per stream (effective URL), kept in the state directory."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.records: dict[str, dict] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.records = {}

    def record(self, h: Health, relayed: Health | None = None) -> None:
        self.records[h.key] = {**asdict(h), "verdict": h.verdict}
        if relayed is not None:
            self.records[h.key]["relay"] = {**asdict(relayed), "verdict": relayed.verdict}

    def verdict(self, key: str, max_age_days: float = 14) -> str | None:
        """'stable', 'unstable', 'dead', 'unknown', or None if never measured (or too old)."""
        r = self.records.get(key)
        if not r or time.time() - r.get("checked", 0) > max_age_days * 86400:
            return None
        return r.get("verdict")

    def save(self) -> None:
        atomic_write(self.path, json.dumps(self.records, indent=0, sort_keys=True))


@functools.cache
def relay_module():
    """The Kodi add-on's relay, loaded from this checkout: one copy of the code for the TV
    and for the measurements on the Mac."""
    path = (Path(__file__).resolve().parents[2] / "kodi-addon" / "script.iptv4free"
            / "resources" / "lib" / "relay.py")
    if not path.is_file():
        raise RuntimeError(f"relay.py not found at {path}: run from an IPTV4FREE checkout")
    spec = importlib.util.spec_from_file_location("iptv4free_addon_relay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worth_relaying(h: Health) -> bool:
    """Only streams that showed a problem the relay addresses get the A/B test."""
    return h.kind == "hls" and (h.verdict == "unstable" or h.variants >= 2)


def check_with_relay(target: Target, seconds: float, timeout: float = 10.0,
                     default_user_agent: str = "") -> tuple[Health, Health | None]:
    """Direct follow, then the same stream through a local copy of the TV relay if useful."""
    direct = check(target, seconds, timeout, default_user_agent)
    if not worth_relaying(direct):
        return direct, None
    relay = relay_module()
    server = relay.serve(port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        headers = dict(target.headers)
        if default_user_agent:
            headers.setdefault("User-Agent", default_user_agent)
        local = relay.local_url(target.url, headers, port=server.server_address[1])
        relayed = check(Target(target.key, local, ()), seconds, timeout)
    finally:
        server.shutdown()
        server.server_close()
    return direct, relayed


def relay_helps(record: dict | None) -> bool:
    """Route through the TV relay only what was measured better through it: a stream that
    stalls directly and not through the relay, or a multi-variant master (Kodi opens every
    variant: 18.6 s -> 5.8 s measured for a Pluto TV channel) that plays fine through it."""
    if not record or not record.get("relay"):
        return False
    if record["relay"].get("verdict") != "stable":
        return False
    return record.get("verdict") == "unstable" or record.get("variants", 0) >= 2


def route(entries: list[Entry], book: "HealthBook", port: int | None = None) -> tuple[list[Entry], list[str]]:
    """Point the entries the relay helps at the relay on the TV (127.0.0.1). The source URL
    and its HTTP headers travel inside the relay URL, so #EXTVLCOPT header lines go away."""
    relay = relay_module()
    out, routed = [], []
    for e in entries:
        if e.url.startswith("http://127.0.0.1:") or not relay_helps(book.records.get(effective_url(e))):
            out.append(e)
            continue
        url, headers = request_parts(e)
        options = [o for o in e.options if not o.lower().startswith(
            ("#extvlcopt:http-user-agent", "#extvlcopt:http-referrer"))]
        out.append(Entry(name=e.name, url=relay.local_url(url, headers, port=port or relay.PORT),
                         attrs=dict(e.attrs), options=options))
        routed.append(e.name)
    return out, routed


def unroute(entry: Entry) -> Entry:
    """The entry as it was before `route`: source URL, header lines back (identity kept)."""
    if not entry.url.startswith("http://127.0.0.1:"):
        return entry
    url, headers = relay_module().decode(urllib.parse.urlsplit(entry.url).path.split("/")[1])
    options = [f"#EXTVLCOPT:http-user-agent={v}" for k, v in headers.items() if k.lower() == "user-agent"]
    options += [f"#EXTVLCOPT:http-referrer={v}" for k, v in headers.items() if k.lower() == "referer"]
    return Entry(name=entry.name, url=url, attrs=dict(entry.attrs), options=options + entry.options)
