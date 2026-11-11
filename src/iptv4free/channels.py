"""Turn source entries into ordered, numbered, grouped lineups."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from . import epg
from .config import Config, Lineup
from .playlists import Entry
from .updates import NumberBook

_RESOLUTION = re.compile(r"\((\d{3,4})[pi]\)")
_TAGS = re.compile(r"\s*(\(\d{3,4}[pi]\)|\[[^\]]*\])")
_QUALITY_SUFFIX = re.compile(r"\s+(HD|SD|FHD|UHD|4K)$", re.IGNORECASE)


def clean_name(raw: str) -> str:
    """'TMC HD (1080p) [Geo-blocked]' -> 'TMC'. Keeps country hints such as '(Portugal)'."""
    name = " ".join(_TAGS.sub("", raw).split())
    return _QUALITY_SUFFIX.sub("", name) or name or " ".join(raw.split())


def resolution(raw: str) -> int:
    m = _RESOLUTION.search(raw)
    return int(m.group(1)) if m else 0


@dataclass
class LineupReport:
    source_entries: int = 0
    dead: int = 0
    duplicates: int = 0
    taken_by_earlier_lineup: int = 0
    excluded_category: int = 0
    channels: int = 0
    with_epg: int = 0
    favorites_found: list[str] = field(default_factory=list)
    favorites_missing: list[str] = field(default_factory=list)
    numbering_overflow: bool = False


def _bucket(entry: Entry, config: Config) -> str:
    category = entry.attrs.get("group-title", "").split(";")[0].strip()
    for group, cats in config.category_groups.items():
        if category in cats:
            return group
    return config.other_label


def build_lineup(lineup: Lineup, entries: list[Entry], config: Config,
                 alive: Callable[[Entry], bool], used_urls: set[str],
                 epg_index: epg.EpgIndex | None, numbers: NumberBook,
                 next_first_number: int | None = None) -> tuple[list[Entry], LineupReport]:
    """Filter, deduplicate, group, order and number one lineup.

    The output depends only on the set of input entries, not on their order: duplicates
    keep the highest resolution (ties: smallest URL) and rows are sorted on stable keys.
    `used_urls` carries URLs taken by earlier lineups, which have priority.
    """
    rep = LineupReport(source_entries=len(entries))
    best: dict[tuple[str, str], tuple[int, Entry]] = {}
    consumed: set[str] = set()  # duplicates dropped here must not resurface in a later lineup
    for src in entries:
        if not alive(src):
            rep.dead += 1
            continue
        if src.url in used_urls:
            rep.taken_by_earlier_lineup += 1
            continue
        categories = {c.strip() for c in src.attrs.get("group-title", "").split(";")}
        if categories & set(lineup.exclude_categories):
            rep.excluded_category += 1
            continue
        consumed.add(src.url)
        name = clean_name(src.name)
        key = (epg.match_key(name), src.attrs.get("tvg-id", "").split("@")[0].lower())
        res = resolution(src.name)
        if key in best:
            rep.duplicates += 1
            kept_res, kept = best[key]
            if res < kept_res or (res == kept_res and src.url >= kept.url):
                continue
        best[key] = (res, Entry(name=name, url=src.url, attrs=dict(src.attrs),
                                options=list(src.options)))

    fav_keys = [epg.match_key(f) for f in lineup.favorites]
    group_order = [*config.category_groups, config.other_label]
    rows = []
    taken_favs: set[int] = set()
    for (mkey, tvg_base), (_, e) in sorted(best.items(), key=lambda kv: (kv[0], kv[1][1].url)):
        fav = fav_keys.index(mkey) if mkey in fav_keys else None
        if fav in taken_favs:
            fav = None  # a favorite name is given to one channel only
        if fav is not None:
            taken_favs.add(fav)
        bucket = _bucket(e, config) if lineup.by_category else ""
        rank = group_order.index(bucket) if bucket in group_order else len(group_order)
        rows.append(((fav is None, fav or 0, rank, mkey, e.url), fav, bucket, mkey, tvg_base, e))
    rows.sort(key=lambda r: r[0])

    out: list[Entry] = []
    first_free = lineup.first_number + len(lineup.favorites)
    used_urls |= consumed
    for _, fav, bucket, mkey, tvg_base, e in rows:
        groups = [f"{lineup.name} · {config.favorites_label}"] if fav is not None else []
        groups.append(f"{lineup.name} · {bucket}" if lineup.by_category
                      else f"{lineup.name} · {config.all_label}")
        number = (lineup.first_number + fav if fav is not None
                  else numbers.assign(lineup.id, f"{mkey}|{tvg_base}", first_free))
        if next_first_number is not None and number >= next_first_number:
            rep.numbering_overflow = True
        guide = (epg.match(e.name, e.attrs.get("tvg-id", ""), lineup.epg_aliases, epg_index)
                 if epg_index else None)
        rep.with_epg += guide is not None
        attrs = {"tvg-id": guide or e.attrs.get("tvg-id", ""), "tvg-chno": str(number),
                 "tvg-logo": e.attrs.get("tvg-logo", ""), "group-title": ";".join(groups)}
        out.append(Entry(name=e.name, url=e.url, attrs=attrs, options=e.options))

    rep.channels = len(out)
    rep.favorites_found = [lineup.favorites[i] for i in sorted(taken_favs)]
    rep.favorites_missing = [f for i, f in enumerate(lineup.favorites) if i not in taken_favs]
    return out, rep


def validate(entries: list[Entry]) -> list[str]:
    """Problems that must block a deployment."""
    problems = []
    if not entries:
        problems.append("lineup is empty")
    seen_numbers: set[str] = set()
    seen_ids: set[tuple[str, str]] = set()
    for e in entries:
        if "://" not in e.url or "\n" in e.url or not e.name.strip():
            problems.append(f"invalid entry: {e.name!r} {e.url!r}")
        num = e.attrs.get("tvg-chno", "")
        if num in seen_numbers:
            problems.append(f"duplicate channel number {num} ({e.name})")
        seen_numbers.add(num)
        ident = (e.name, e.url)
        if ident in seen_ids:
            problems.append(f"duplicate channel {e.name!r}")
        seen_ids.add(ident)
    return problems
