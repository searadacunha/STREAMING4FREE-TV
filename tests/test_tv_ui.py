"""Kodi TV UI tests: synthetic PVR data, no Kodi runtime or network needed."""
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "kodi-addon" / "script.iptv4free"
CORE = ADDON / "resources" / "lib" / "core.py"
spec = importlib.util.spec_from_file_location("iptv4free_tv_core", CORE)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def fake_rpc(request):
    data = json.loads(request)
    if data["method"] == "PVR.GetChannelGroups":
        result = {"channelgroups": [
            {"label": "Portugal", "channelgroupid": 2},
            {"label": "All channels", "channelgroupid": 1},
        ]}
    elif data["method"] == "PVR.GetChannels":
        start = data["params"]["limits"]["start"]
        channels = [
            {"channelid": 7, "label": "RTP 1", "channelnumber": 1,
             "thumbnail": "image://test", "broadcastnow": {"title": "Journal"}},
            {"channelid": 8, "label": "SIC", "channelnumber": 2, "broadcastnow": None},
            {"channelid": 9, "label": "Hidden", "hidden": True},
        ]
        result = {"channels": channels[start:start + 100]}
    else:
        return json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601}})
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result})


def test_groups_and_pvr_channels():
    groups = core.channel_groups(fake_rpc)
    assert core.default_group(groups)["channelgroupid"] == 1
    channels = core.channels_for_group(fake_rpc, 1)
    assert [c["name"] for c in channels] == ["RTP 1", "SIC"]
    assert channels[0]["now"] == "Journal"
    assert channels[1]["now"] == "Programme indisponible"


def test_search_and_favorites():
    channels = core.channels_for_group(fake_rpc, 1)
    assert [c["id"] for c in core.filter_channels(channels, favorites=["8"], only_favorites=True)] == [8]
    assert [c["id"] for c in core.filter_channels(channels, search="journal")] == [7]
    assert core.filter_channels(channels, search="not-present") == []


def test_rpc_rejects_invalid_calls():
    try:
        core.rpc_call(fake_rpc, "unknown")
        assert False, "Expected RpcError"
    except core.RpcError:
        pass


def test_kodi_manifest_and_ui_files():
    for path in ADDON.rglob("*.xml"):
        ET.parse(path)
    xml = ET.parse(ADDON / "resources/skins/Default/1080i/IPTV4FREE.xml")
    ids = {int(c.attrib["id"]) for c in xml.iter("control") if "id" in c.attrib}
    assert {100, 101, 102, 103, 104, 105, 107, 108, 109, 500}.issubset(ids)
    for image in ("pixel.png", "backdrop.png"):
        assert (ADDON / "resources/skins/Default/media" / image).stat().st_size > 0
