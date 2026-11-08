"""Pure helpers for the IPTV4FREE Kodi home; no Kodi imports (unit-testable)."""
from __future__ import annotations

import calendar
import json
import time

# "icon" is the channel logo (tvg-logo); "thumbnail" is the current programme's picture.
FULL = ["icon", "channelnumber", "broadcastnow", "broadcastnext", "hidden"]
LIGHT = ["icon", "channelnumber", "hidden"]
ALL_LABELS = {"all channels", "toutes les chaînes", "todos os canais", "todos los canales"}


class RpcError(RuntimeError):
    pass


def rpc_call(transport, method: str, params: dict | None = None):
    """Kodi local JSON-RPC. transport(request_json) -> response_json."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
    try:
        response = json.loads(transport(payload))
    except (TypeError, ValueError) as exc:
        raise RpcError(f"Invalid Kodi response for {method}") from exc
    if not isinstance(response, dict) or "error" in response or "result" not in response:
        raise RpcError(f"Kodi rejected {method}: {response.get('error') if isinstance(response, dict) else 'invalid response'}")
    return response["result"]


def channel_groups(transport) -> list[dict]:
    result = rpc_call(transport, "PVR.GetChannelGroups", {"channeltype": "tv"})
    return [g for g in result.get("channelgroups", [])
            if isinstance(g, dict) and isinstance(g.get("channelgroupid"), int)]


def is_all_group(group: dict) -> bool:
    return str(group.get("label", "")).casefold() in ALL_LABELS


def default_group(groups: list[dict]) -> dict | None:
    if not groups:
        return None
    return next((g for g in groups if is_all_group(g)), groups[0])


def split_group(label: str) -> tuple[str, str]:
    """'France · Info' -> ('FRANCE', 'Info'): IPTV4FREE names groups '<country> · <category>'."""
    country, sep, category = str(label).partition(" · ")
    return (country.strip().upper(), category.strip()) if sep else ("", country.strip())


def group_names(group: dict) -> tuple[str, str]:
    """(country, label) shown for a group; Kodi's internal all-channels group is named in French."""
    return ("", "Toutes les chaînes") if is_all_group(group) else split_group(group.get("label", ""))


def utc_to_epoch(value) -> float | None:
    """Kodi PVR JSON-RPC dates are UTC 'YYYY-MM-DD HH:MM:SS'."""
    try:
        return float(calendar.timegm(time.strptime(str(value), "%Y-%m-%d %H:%M:%S")))
    except (TypeError, ValueError):
        return None


def clock(epoch: float | None) -> str:
    return time.strftime("%H:%M", time.localtime(epoch)) if epoch is not None else ""


def time_range(start, end) -> str:
    a, b = clock(utc_to_epoch(start)), clock(utc_to_epoch(end))
    return f"{a} – {b}" if a and b else ""


def progress(start, end, now: float) -> int:
    a, b = utc_to_epoch(start), utc_to_epoch(end)
    if a is None or b is None or b <= a:
        return 0
    return max(0, min(100, int(100 * (now - a) / (b - a))))


def logo(icon) -> str:
    """Channel logo or "" (neutral fallback). Without tvg-logo, IPTV Simple puts the URL-encoded name here."""
    icon = str(icon or "")
    return icon if "://" in icon or icon.startswith("/") else ""


def count_label(shown: int, total: int, more: bool) -> str:
    """'300 sur 7883' / '148 chaînes': at most 13 characters, about 177 px in MegaNexus' font12.

    shortcut: no thousands separator so "7800 sur 7883" fits the 200 px box; widen it past 9999 channels.
    """
    return f"{shown} sur {total}" if more else f"{shown} chaîne{'s' if shown > 1 else ''}"


def _broadcast(value) -> dict:
    return value if isinstance(value, dict) else {}


def normalize(ch: dict, now: float | None = None) -> dict | None:
    """One PVR channel -> flat dict for list items, or None if hidden/invalid."""
    if ch.get("hidden") or not isinstance(ch.get("channelid"), int):
        return None
    now = time.time() if now is None else now
    number = ch.get("channelnumber", "")
    if isinstance(number, dict):
        number = number.get("channelnumber", "")
    cur, nxt = _broadcast(ch.get("broadcastnow")), _broadcast(ch.get("broadcastnext"))
    return {
        "id": ch["channelid"],
        "name": str(ch.get("label") or ch.get("channel") or "Chaîne").strip(),
        "number": str(number or ""),
        "logo": logo(ch.get("icon")),
        "now": str(cur.get("title") or ""),
        "now_time": time_range(cur.get("starttime"), cur.get("endtime")),
        "progress": progress(cur.get("starttime"), cur.get("endtime"), now) if cur else 0,
        "next": str(nxt.get("title") or ""),
        "next_time": time_range(nxt.get("starttime"), nxt.get("endtime")),
    }


def channels_page(transport, group_id: int, start: int = 0, count: int = 300,
                  properties=FULL) -> tuple[list[dict], int, int]:
    """Channels [start, start+count) of a group in ONE call -> (channels, next_start, total).

    On the TV every call costs ~0.35 s whatever its size (Kodi rebuilds the group), while 7,883
    light channels in one call take 1.1 s: never split a page. next_start counts raw PVR rows
    (hidden ones included), so paging never re-reads a row."""
    data = rpc_call(transport, "PVR.GetChannels", {
        "channelgroupid": group_id, "properties": list(properties),
        "limits": {"start": start, "end": start + count},
    })
    page = data.get("channels") or []
    total = int((data.get("limits") or {}).get("total", start + len(page)))
    return [c for c in map(normalize, page) if c], start + len(page), total


def channel_index(transport, group_id: int, cap: int = 20000) -> list[dict]:
    """Every channel of a group with light fields only (search, favourites)."""
    return channels_page(transport, group_id, 0, cap, properties=LIGHT)[0]


def with_programmes(transport, channels: list[dict]) -> list[dict]:
    """Fill now/next for a short list (search results, favourites) one call per channel."""
    out = []
    for ch in channels:
        try:
            data = rpc_call(transport, "PVR.GetChannelDetails",
                            {"channelid": ch["id"], "properties": FULL})
            out.append(normalize(data.get("channeldetails") or {}) or ch)
        except RpcError:
            out.append(ch)
    return out


def filter_channels(channels: list[dict], *, search: str = "", favorites=(), only_favorites=False) -> list[dict]:
    needle = search.casefold().strip()
    names = {str(n).casefold() for n in favorites}
    return [ch for ch in channels if (not only_favorites or ch["name"].casefold() in names)
            and (not needle or needle in ch["name"].casefold())]


def schedule(transport, channel_id: int, now: float | None = None, limit: int = 12) -> list[dict]:
    """Current and upcoming programmes of one channel (the per-channel TV guide)."""
    now = time.time() if now is None else now
    data = rpc_call(transport, "PVR.GetBroadcasts", {
        "channelid": channel_id, "properties": ["title", "starttime", "endtime", "plot", "genre"]})
    rows = []
    for b in data.get("broadcasts") or []:
        end = utc_to_epoch(b.get("endtime"))
        if end is None or end <= now:
            continue
        start = utc_to_epoch(b.get("starttime"))
        genre = b.get("genre")
        rows.append({
            "start": start or 0,
            "time": time_range(b.get("starttime"), b.get("endtime")),
            "title": str(b.get("title") or b.get("label") or "Programme"),
            "plot": str(b.get("plot") or ""),
            "genre": " / ".join(genre) if isinstance(genre, list) else str(genre or ""),
            "live": start is not None and start <= now,
        })
    rows.sort(key=lambda r: r["start"])
    return rows[:limit]
