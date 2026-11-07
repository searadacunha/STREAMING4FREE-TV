"""Pure helpers for the IPTV4FREE Kodi home; no Kodi imports (unit-testable)."""
from __future__ import annotations

import json


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


def default_group(groups: list[dict]) -> dict | None:
    if not groups:
        return None
    return next((g for g in groups if g.get("label", "").casefold() in
                 {"all channels", "toutes les chaînes", "todos os canais"}), groups[0])


def channels_for_group(transport, group_id: int, max_results: int = 300, batch: int = 100) -> list[dict]:
    """Bounded pagination keeps memory use reasonable on low-RAM Android TVs."""
    result = []
    for start in range(0, max_results, batch):
        data = rpc_call(transport, "PVR.GetChannels", {
            "channelgroupid": group_id,
            "properties": ["thumbnail", "channelnumber", "broadcastnow", "hidden"],
            "limits": {"start": start, "end": min(start + batch, max_results)},
        })
        page = data.get("channels", [])
        for ch in page:
            if ch.get("hidden") or not isinstance(ch.get("channelid"), int):
                continue
            broadcast = ch.get("broadcastnow") or {}
            if not isinstance(broadcast, dict):
                broadcast = {}
            number = ch.get("channelnumber", "")
            if isinstance(number, dict):
                number = number.get("channelnumber", "")
            result.append({
                "id": ch["channelid"],
                "name": str(ch.get("label") or ch.get("channel") or "Chaîne").strip(),
                "number": str(number),
                "thumb": ch.get("thumbnail") or "",
                "now": str(broadcast.get("title") or "Programme indisponible"),
            })
        if len(page) < batch or len(result) >= max_results:
            break
    return result


def filter_channels(channels: list[dict], *, search: str = "", favorites=(), only_favorites=False) -> list[dict]:
    needle = search.casefold().strip()
    favorite_ids = {int(i) for i in favorites if str(i).isdigit()}
    return [ch for ch in channels if (not only_favorites or ch["id"] in favorite_ids)
            and (not needle or needle in (ch["name"] + " " + ch["now"]).casefold())]
