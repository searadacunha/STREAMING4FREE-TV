"""XMLTV guide download and channel matching.

Only the <channel> list of the guide is read here, to map playlist entries to guide ids.
The guide itself is downloaded by Kodi on the TV from the same URL.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import logging
import re
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


def match_key(name: str) -> str:
    """Loose key for comparing channel names: accents, case, punctuation and quality tags dropped."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r"\b(hd|sd|fhd|uhd|4k)\b", "", s)
    return re.sub(r"[^a-z0-9+]", "", s)


@dataclass
class EpgIndex:
    ids: dict[str, str] = field(default_factory=dict)    # lowercased id -> id
    names: dict[str, str] = field(default_factory=dict)  # match_key(display-name) -> id

    def __len__(self) -> int:
        return len(self.ids)


def parse_channels(data: bytes) -> EpgIndex:
    """Read <channel> elements from XMLTV bytes (plain or gzip). Stops at the first programme."""
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    index = EpgIndex()
    for _, elem in ET.iterparse(io.BytesIO(data), events=("end",)):
        if elem.tag == "programme":
            break  # XMLTV lists channels before programmes
        if elem.tag != "channel":
            continue
        cid = elem.get("id", "").strip()
        if cid:
            index.ids.setdefault(cid.lower(), cid)
            for dn in elem.iter("display-name"):
                if dn.text and match_key(dn.text):
                    index.names.setdefault(match_key(dn.text), cid)
        elem.clear()
    return index


def load_index(url: str, cache_dir: Path, max_age_hours: float, timeout: float,
               user_agent: str) -> EpgIndex | None:
    """Channel index for an EPG URL, using a cached copy younger than max_age_hours.

    A failed download falls back to the cached copy of any age; with no copy at all the
    lineup is built without guide mapping (returns None) instead of failing the build.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".xmltv")
    fresh = cached.exists() and time.time() - cached.stat().st_mtime < max_age_hours * 3600
    if not fresh:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(req, timeout=max(timeout, 60)) as resp:
                data = resp.read()
            tmp = cached.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(cached)
        except OSError as e:
            if not cached.exists():
                log.warning("EPG %s unavailable (%s): building without guide mapping", url, e)
                return None
            log.warning("EPG %s unavailable (%s): using cached copy", url, e)
    try:
        return parse_channels(cached.read_bytes())
    except (ET.ParseError, OSError, EOFError) as e:
        log.warning("EPG %s unreadable (%s): building without guide mapping", url, e)
        return None


def match(name: str, tvg_id: str, aliases: dict[str, str], index: EpgIndex) -> str | None:
    """Guide id for a channel: explicit alias, then tvg-id, then display name."""
    key = match_key(name)
    alias = {match_key(k): v for k, v in aliases.items()}.get(key)
    if alias:
        return alias
    base = tvg_id.split("@")[0].strip().lower()  # iptv-org ids carry a feed suffix: "TF1.fr@SD"
    if base and base in index.ids:
        return index.ids[base]
    return index.names.get(key)
