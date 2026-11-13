"""scan and build steps.

`scan` downloads every source playlist, keeps a snapshot, and probes each unique stream
once. `build` works only from those snapshots and the scan history, so its output is
reproducible and does not depend on network conditions at build time (except EPG lists).
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import epg, health, scanner
from .channels import LineupReport, build_lineup, validate
from .config import Config, Lineup
from .playlists import Entry, effective_url, fetch_text, parse_m3u, render_m3u, request_parts
from .updates import NumberBook, ScanHistory, atomic_write

log = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    pass


def _snapshot(config: Config, url: str) -> Path:
    return config.state_dir / "sources" / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".m3u")


def _history(config: Config) -> ScanHistory:
    return ScanHistory(config.state_dir / "scan-history.json")


def lineup_entries(config: Config, lineup: Lineup) -> list[Entry]:
    entries: list[Entry] = []
    for url in lineup.sources:
        snap = _snapshot(config, url)
        if not snap.exists():
            raise PipelineError(f"no snapshot of {url}; run `iptv4free scan` first")
        result = parse_m3u(snap.read_text(encoding="utf-8"))
        if result.skipped:
            log.info("%s: %d malformed lines skipped", url, len(result.skipped))
        entries.extend(result.entries)
    return entries


@dataclass
class ScanSummary:
    sources_refreshed: int
    sources_stale: int
    streams: int
    alive: int
    seconds: float


def run_scan(config: Config, progress: Callable[[int, int], None] | None = None) -> ScanSummary:
    started = time.monotonic()
    refreshed = stale = 0
    for url in dict.fromkeys(u for lu in config.lineups for u in lu.sources):
        snap = _snapshot(config, url)
        try:
            text = fetch_text(url, max(config.scan_timeout, 30), config.user_agent)
        except OSError as e:
            if not snap.exists():
                raise PipelineError(f"cannot download {url}: {e}") from None
            log.warning("cannot download %s (%s): using the previous snapshot", url, e)
            stale += 1
            continue
        if not parse_m3u(text).entries:
            if not snap.exists():
                raise PipelineError(f"{url} contains no playable entries")
            log.warning("%s returned no entries: keeping the previous snapshot", url)
            stale += 1
            continue
        atomic_write(snap, text)
        refreshed += 1

    targets: dict[str, scanner.Target] = {}
    for lineup in config.lineups:
        for e in lineup_entries(config, lineup):
            key = effective_url(e)
            if key not in targets:
                url, headers = request_parts(e)
                targets[key] = scanner.Target(key, url, tuple(sorted(headers.items())))

    results = scanner.scan(targets.values(), config.scan_timeout, config.scan_workers,
                           config.user_agent, progress)
    history = _history(config)
    now = time.time()
    for r in results:
        history.record(r.key, r.ok, r.detail, now)
    history.save()
    return ScanSummary(refreshed, stale, len(results), sum(r.ok for r in results),
                       time.monotonic() - started)


def run_build(config: Config) -> dict[str, tuple[Path, LineupReport]]:
    history = _history(config)
    if not history.streams:
        raise PipelineError("no scan results yet; run `iptv4free scan` first")
    numbers = NumberBook(config.state_dir / "channel-numbers.json")
    book = health.HealthBook(config.state_dir / "health.json")
    used_urls: set[str] = set()
    starts = sorted({lu.first_number for lu in config.lineups})
    built: dict[str, tuple[Path, LineupReport]] = {}
    for lineup in config.lineups:
        index = None
        if lineup.epg:
            index = epg.load_index(lineup.epg, config.state_dir / "epg",
                                   config.epg_max_age_hours, config.scan_timeout,
                                   config.user_agent)
        nxt = next((s for s in starts if s > lineup.first_number), None)
        entries, report = build_lineup(
            lineup, lineup_entries(config, lineup), config,
            lambda e: history.alive(effective_url(e), config.max_failed_scans),
            used_urls, index, numbers, nxt, lambda e: book.verdict(effective_url(e)))
        if config.relay:
            entries, routed = health.route(entries, book)
            if routed:
                log.info("%s: %d channels through the TV relay: %s", lineup.id, len(routed),
                         ", ".join(routed))
        problems = validate(entries)
        if problems:
            raise PipelineError(f"{lineup.id}: " + "; ".join(problems[:5]))
        if report.numbering_overflow:
            log.warning("%s: channel numbers reach the next lineup's first_number; "
                        "raise the gap between first_number values", lineup.id)
        out = config.output_dir / f"{lineup.id}.m3u"
        atomic_write(out, render_m3u(entries))
        built[lineup.id] = (out, report)
    numbers.save()
    return built
