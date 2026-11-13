"""M3U parsing and rendering, and how Kodi's IPTV Simple Client will see each entry."""
from __future__ import annotations

import urllib.request
from dataclasses import dataclass, field

# Attribute order used when writing playlists, so output is byte-for-byte deterministic.
ATTR_ORDER = ("tvg-id", "tvg-chno", "tvg-name", "tvg-logo", "group-title")


@dataclass
class Entry:
    name: str
    url: str
    attrs: dict[str, str] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)  # raw #EXTVLCOPT / #KODIPROP lines


@dataclass
class ParseResult:
    entries: list[Entry]
    skipped: list[tuple[int, str]]  # (line number, reason)


def _parse_extinf(body: str) -> tuple[dict[str, str], str]:
    """Parse what follows '#EXTINF:' into (attributes, display name).

    Attribute values may contain commas and spaces when quoted, so the name starts at the
    first comma that is outside an attribute, not at the first comma of the line.
    """
    i, n = 0, len(body)
    while i < n and body[i] not in " ,":  # duration, ignored
        i += 1
    attrs: dict[str, str] = {}
    while i < n:
        c = body[i]
        if c == ",":
            return attrs, body[i + 1:].strip()
        if c.isspace():
            i += 1
            continue
        start = i
        while i < n and body[i] not in "=, ":
            i += 1
        key = body[start:i].lower()
        if i < n and body[i] == "=":
            i += 1
            if i < n and body[i] == '"':
                end = body.find('"', i + 1)
                if end == -1:
                    raise ValueError("unterminated quoted attribute")
                value, i = body[i + 1:end], end + 1
            else:
                start = i
                while i < n and body[i] not in " ,":
                    i += 1
                value = body[start:i]
            if key:
                attrs[key] = value
    raise ValueError("no ',' before the channel name")


def parse_m3u(text: str) -> ParseResult:
    """Parse an extended M3U playlist. Malformed entries are skipped and reported, never fatal."""
    entries: list[Entry] = []
    skipped: list[tuple[int, str]] = []
    pending: Entry | None = None
    pending_line = 0
    for lineno, raw in enumerate(text.lstrip("﻿").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF:"):
            if pending:
                skipped.append((pending_line, "EXTINF without URL"))
            pending = None
            try:
                attrs, name = _parse_extinf(line[len("#EXTINF:"):])
            except ValueError as e:
                skipped.append((lineno, f"bad EXTINF: {e}"))
                continue
            name = name or attrs.get("tvg-name", "")
            if not name:
                skipped.append((lineno, "EXTINF without a channel name"))
                continue
            pending, pending_line = Entry(name=name, url="", attrs=attrs), lineno
        elif line.startswith(("#EXTVLCOPT", "#KODIPROP:")):
            if pending:
                pending.options.append(line)
        elif line.startswith("#EXTGRP:"):
            if pending:
                pending.attrs.setdefault("group-title", line[len("#EXTGRP:"):].strip())
        elif line.startswith("#"):
            continue
        elif pending is None:
            skipped.append((lineno, "URL without EXTINF"))
        elif "://" not in line:
            skipped.append((lineno, f"not a URL: {line[:60]}"))
            pending = None
        else:
            pending.url = line
            entries.append(pending)
            pending = None
    if pending:
        skipped.append((pending_line, "EXTINF without URL"))
    return ParseResult(entries, skipped)


def render_m3u(entries: list[Entry]) -> str:
    out = ["#EXTM3U"]
    for e in entries:
        keys = [k for k in ATTR_ORDER if e.attrs.get(k)]
        keys += sorted(k for k in e.attrs if k not in ATTR_ORDER and e.attrs[k])
        # M3U has no escape for '"' inside attribute values
        attrs = " ".join(f'{k}="{e.attrs[k].replace(chr(34), chr(39))}"' for k in keys)
        name = " ".join(e.name.split())
        out.append(f"#EXTINF:-1 {attrs},{name}" if attrs else f"#EXTINF:-1,{name}")
        out.extend(e.options)
        out.append(e.url)
    return "\n".join(out) + "\n"


def stream_properties(entry: Entry) -> dict[str, str]:
    """Stream properties as IPTV Simple Client reads them from the option lines.

    #EXTVLCOPT values stop at the first space and only three are accepted; #KODIPROP
    values are taken whole. A later line overrides an earlier one.
    """
    props: dict[str, str] = {}
    for line in entry.options:
        if line.startswith("#KODIPROP:"):
            value = line[len("#KODIPROP:"):]
        elif line.startswith("#EXTVLCOPT:"):
            value = line[len("#EXTVLCOPT:"):].split(" ", 1)[0]
        else:
            continue
        key, sep, val = value.partition("=")
        key = key.lower()
        if not sep or (line.startswith("#EXTVLCOPT:") and
                       key not in ("http-user-agent", "http-referrer", "program")):
            continue
        props[key] = val
    return props


def effective_url(entry: Entry) -> str:
    """The stream URL IPTV Simple Client ends up with: headers are appended after '|'."""
    url = entry.url
    if not url.startswith(("http://", "https://")):
        return url
    props = stream_properties(entry)
    for prop, header in (("http-user-agent", "user-agent"), ("http-referrer", "referer")):
        value = props.get(prop)
        if not value:
            continue
        pipe = url.find("|")
        if pipe == -1:
            url = f"{url}|{header}={value}"
        elif f"{header}=" not in url[pipe + 1:]:
            url = f"{url}&{header}={value}"
    return url


def kodi_identity(entry: Entry) -> str:
    """Key under which Kodi stores the channel: IPTV Simple hashes name + effective URL.

    Any change to either one makes Kodi delete the channel and create a new one.
    """
    return entry.name + "\n" + effective_url(entry)


def request_parts(entry: Entry) -> tuple[str, dict[str, str]]:
    """Split the effective URL into (URL to fetch, HTTP headers), as Kodi would send them."""
    url, _, options = effective_url(entry).partition("|")
    headers: dict[str, str] = {}
    for item in options.split("&") if options else []:
        key, _, value = item.partition("=")
        key = key.strip().lower()
        if key == "user-agent":
            headers["User-Agent"] = urllib.request.unquote(value)
        elif key in ("referer", "referrer"):
            headers["Referer"] = urllib.request.unquote(value)
    return url, headers


def fetch_text(url: str, timeout: float, user_agent: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")
