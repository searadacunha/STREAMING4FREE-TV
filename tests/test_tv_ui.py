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



def test_uploaded_branding_source_generates_kodi_icon(tmp_path):
    from PIL import Image
    from scripts.prepare_branding import prepare_logo
    source = tmp_path / "original.png"
    image = Image.new("RGBA", (120, 80), (0, 0, 0, 0))
    for x in range(20, 100):
        for y in range(15, 65):
            image.putpixel((x, y), (30, 50, 245, 255))
    image.save(source)
    header = tmp_path / "media" / "iptv4free-logo.png"
    icon = tmp_path / "addon" / "icon.png"
    assert prepare_logo(source=source, header=header, icon=icon)
    assert header.read_bytes() == source.read_bytes()  # exact logo, unchanged
    with Image.open(icon) as final:
        assert final.size == (512, 512)
        assert final.mode == "RGBA"
        assert final.getpixel((0, 0))[3] == 0
    assert not prepare_logo(source=tmp_path / "missing.png", header=header, icon=icon)
