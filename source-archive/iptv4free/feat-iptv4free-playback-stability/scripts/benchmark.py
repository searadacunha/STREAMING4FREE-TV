#!/usr/bin/env python3
"""Reproducible local benchmark of the processing pipeline on a synthetic playlist.

usage: python scripts/benchmark.py [CHANNELS]   (default 10000)
No network, no TV: measures parsing, lineup building, rendering and changeset computation.
"""
import random
import sys
import tempfile
import time
from pathlib import Path

from iptv4free.channels import build_lineup
from iptv4free.config import Config, Lineup
from iptv4free.playlists import Entry, parse_m3u, render_m3u
from iptv4free.updates import NumberBook, changeset

CATEGORIES = ["News", "Sports", "Movies", "Kids", "Music", "General", "Religious", "Undefined"]


def synthetic(n: int, seed: int) -> str:
    rng = random.Random(seed)
    lines = ["#EXTM3U"]
    for i in range(n):
        res = rng.choice(["(1080p)", "(720p)", "(576p)", ""])
        cat = rng.choice(CATEGORIES)
        lines.append(f'#EXTINF:-1 tvg-id="Ch{i}.xx@SD" tvg-logo="https://example.com/{i}.png" '
                     f'group-title="{cat}",Channel {i} {res}')
        if i % 10 == 0:
            lines.append("#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Example)")
        lines.append(f"https://example.com/live/{i}/index.m3u8")
    return "\n".join(lines) + "\n"


def timed(label: str, fn):
    start = time.perf_counter()
    result = fn()
    print(f"{label:<44} {1000 * (time.perf_counter() - start):8.1f} ms")
    return result


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
    text = synthetic(n, seed=1)
    lineup = Lineup("world", "World", ("synthetic",), by_category=True, first_number=1000)
    config = Config(path=Path("."), lineups=(lineup,))
    print(f"{n} synthetic channels, Python {sys.version.split()[0]}")
    entries = timed("parse M3U", lambda: parse_m3u(text).entries)
    with tempfile.TemporaryDirectory() as tmp:
        book = NumberBook(Path(tmp) / "numbers.json")
        built, _ = timed("build lineup (dedupe, group, order, number)",
                         lambda: build_lineup(lineup, entries, config, lambda e: True, set(),
                                              None, book))
    out = timed("render M3U", lambda: render_m3u(built))
    changed = [Entry(e.name + " x", e.url, e.attrs, e.options) if i % 100 == 0 else e
               for i, e in enumerate(built)]
    c = timed("changeset (1% renamed)", lambda: changeset(built, changed))
    print(f"output {len(built)} channels, {len(out) // 1024} KiB; changeset size {c.size}")


if __name__ == "__main__":
    main()
