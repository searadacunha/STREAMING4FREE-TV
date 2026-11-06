"""Concurrent stream validation.

A stream counts as alive only if real media bytes come back: for HLS the master playlist,
one variant and the newest segment are fetched; DASH manifests and direct streams are
fetched directly. Headers are the ones Kodi will send (see playlists.request_parts).
"""
from __future__ import annotations

import ssl
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Iterable

PLAYLIST_LIMIT = 512 * 1024
MEDIA_PROBE_BYTES = 64 * 1024
MIN_MEDIA_BYTES = 1024


@dataclass(frozen=True)
class Target:
    key: str  # effective URL (URL + Kodi header options), unique per stream
    url: str
    headers: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Result:
    key: str
    ok: bool
    detail: str


def _get(url: str, headers: dict[str, str], limit: int, timeout: float,
         ctx: ssl.SSLContext) -> tuple[str, bytes]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.geturl(), resp.read(limit)


def _uris(base: str, text: str, after_tag: str | None) -> list[str]:
    """URIs of an HLS playlist: those following `after_tag` lines, or all media URIs."""
    lines = [ln.strip() for ln in text.splitlines()]
    found = []
    for i, line in enumerate(lines):
        if not line or line.startswith("#"):
            continue
        if after_tag is None or (i > 0 and lines[i - 1].startswith(after_tag)):
            found.append(urllib.parse.urljoin(base, line))
    return found


def probe(target: Target, timeout: float, default_user_agent: str = "") -> Result:
    headers = dict(target.headers)
    if default_user_agent:
        headers.setdefault("User-Agent", default_user_agent)
    ctx = ssl.create_default_context()  # certificates verified, as Kodi does
    try:
        final, body = _get(target.url, headers, PLAYLIST_LIMIT, timeout, ctx)
        if not body.lstrip().startswith(b"#EXTM3U"):
            if b"<MPD" in body[:4096]:
                return Result(target.key, True, "DASH manifest")
            ok = len(body) >= MIN_MEDIA_BYTES
            return Result(target.key, ok, f"direct stream, {len(body)} bytes")
        text = body.decode("utf-8", "replace")
        if "#EXT-X-STREAM-INF" in text:
            variants = _uris(final, text, "#EXT-X-STREAM-INF")
            if not variants:
                return Result(target.key, False, "HLS master playlist without variants")
            final, body = _get(variants[0], headers, PLAYLIST_LIMIT, timeout, ctx)
            text = body.decode("utf-8", "replace")
        segments = _uris(final, text, None)
        if not segments:
            return Result(target.key, False, "HLS media playlist without segments")
        _, data = _get(segments[-1], headers, MEDIA_PROBE_BYTES, timeout, ctx)
        ok = len(data) >= MIN_MEDIA_BYTES
        return Result(target.key, ok, f"HLS segment, {len(data)} bytes")
    except Exception as e:  # every failure mode means "not watchable"; keep the reason
        return Result(target.key, False, f"{type(e).__name__}: {str(e)[:120]}")


def scan(targets: Iterable[Target], timeout: float, workers: int, default_user_agent: str = "",
         progress: Callable[[int, int], None] | None = None) -> list[Result]:
    """Probe every target concurrently. Results come back in input order."""
    targets = list(targets)
    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        it = pool.map(lambda t: probe(t, timeout, default_user_agent), targets)
        for done, result in enumerate(it, 1):
            results.append(result)
            if progress:
                progress(done, len(targets))
    return results
