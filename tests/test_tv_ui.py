"""Kodi TV UI tests: synthetic PVR data, no Kodi runtime or network needed."""
import hashlib
import importlib.util
import json
import sys
import time
import types
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "kodi-addon" / "script.iptv4free"
MEDIA = ADDON / "resources" / "skins" / "Default" / "media"
WINDOW = ADDON / "resources" / "skins" / "Default" / "1080i" / "IPTV4FREE.xml"
LOGO = ROOT / "assets" / "branding" / "IPTV4FREE-original.png"
LOGO_SHA256 = "895a691c86d56185416257ce026c540e49b49aaedf438c98c5242dcee60485bf"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = load("iptv4free_tv_core", ADDON / "resources" / "lib" / "core.py")
# Programmes are placed around the real clock: default.py asks "what is on now" with time.time().
NOW = int(time.time()) // 60 * 60


def utc(epoch):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(epoch))


def channel(cid, name, number, title=None, start=NOW - 1800, end=NOW + 1800):
    # As on the TV: "thumbnail" is the programme's picture, "icon" the channel's tvg-logo.
    ch = {"channelid": cid, "label": name, "channelnumber": number,
          "thumbnail": f"http://epg.example/show{cid}.jpg", "icon": f"https://logo.example/{cid}.png"}
    if title:
        ch["broadcastnow"] = {"title": title, "starttime": utc(start), "endtime": utc(end)}
        ch["broadcastnext"] = {"title": f"After {title}", "starttime": utc(end), "endtime": utc(end + 3600)}
    return ch


CHANNELS = [channel(i, f"Channel {i}", i, f"Show {i}") for i in range(1, 251)]
CHANNELS[1] = channel(2, "SIC Notícias", 2)  # no EPG
CHANNELS[2]["icon"] = "Channel%203"  # no tvg-logo: IPTV Simple stores the URL-encoded name
CHANNELS.append({"channelid": 999, "label": "Hidden", "hidden": True})
GROUPS = [{"label": "All channels", "channelgroupid": 1}, {"label": "Portugal · Info", "channelgroupid": 2}]
BROADCASTS = [
    {"title": "Old", "starttime": utc(NOW - 7200), "endtime": utc(NOW - 3600)},
    {"title": "Later", "starttime": utc(NOW + 3600), "endtime": utc(NOW + 7200), "genre": ["News"]},
    {"title": "Live", "starttime": utc(NOW - 600), "endtime": utc(NOW + 3600), "plot": "Now on air"},
]


def fake_rpc(request, calls=None):
    data = json.loads(request)
    method, params = data["method"], data.get("params", {})
    if calls is not None:
        calls.append(method)
    if method == "PVR.GetChannelGroups":
        result = {"channelgroups": GROUPS}
    elif method == "PVR.GetChannels":
        rows = CHANNELS if params["channelgroupid"] == 1 else CHANNELS[:3]
        rows = [{k: v for k, v in c.items() if not k.startswith("broadcast") or k in params["properties"]}
                for c in rows]  # Kodi only returns the requested fields
        lim = params["limits"]
        result = {"channels": rows[lim["start"]:lim["end"]],
                  "limits": {"start": lim["start"], "end": min(lim["end"], len(rows)), "total": len(rows)}}
    elif method == "PVR.GetChannelDetails":
        result = {"channeldetails": next(c for c in CHANNELS if c["channelid"] == params["channelid"])}
    elif method == "PVR.GetBroadcasts":
        result = {"broadcasts": BROADCASTS}
    elif method == "Player.Open":
        result = "OK"
    else:
        return json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601}})
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result})


# ---------- PVR data layer ----------

def test_groups_split_by_country_and_category():
    groups = core.channel_groups(fake_rpc)
    assert core.default_group(groups)["channelgroupid"] == 1
    assert core.split_group("Portugal · Info") == ("PORTUGAL", "Info")
    assert core.split_group("All channels") == ("", "All channels")


def test_channels_are_paged_and_normalized():
    first, nxt, total = core.channels_page(fake_rpc, 1, 0, 120)
    assert (len(first), nxt, total) == (120, 120, 251)
    rest, nxt, _ = core.channels_page(fake_rpc, 1, 120, 300)
    assert nxt == 251
    assert [c["id"] for c in rest][-1] == 250  # the hidden channel is dropped
    assert len(first) + len(rest) == 250
    ch = core.normalize(CHANNELS[0], now=NOW)
    assert ch["now"] == "Show 1" and ch["next"] == "After Show 1"
    assert ch["progress"] == 50
    assert ch["now_time"] == f"{core.clock(NOW - 1800)} – {core.clock(NOW + 1800)}"
    assert ch["logo"] == "https://logo.example/1.png"  # the channel logo, never the programme picture
    assert core.normalize(CHANNELS[2], now=NOW)["logo"] == ""  # neutral fallback in the window
    assert core.logo("special://home/logo.png") and core.logo("/storage/x.png") and not core.logo(None)
    no_epg = core.normalize(CHANNELS[1], now=NOW)
    assert no_epg["now"] == "" and no_epg["progress"] == 0 and no_epg["now_time"] == ""


def test_count_label_fits_the_skin_fonts():
    assert core.count_label(300, 7883, True) == "300 sur 7883"
    assert core.count_label(148, 148, False) == "148 chaînes"
    assert core.count_label(1, 1, False) == "1 chaîne"
    assert len(core.count_label(7800, 9999, True)) <= 13  # ~177 px in MegaNexus' font12, box is 200 px


def test_search_and_favourites_by_name():
    index = core.channel_index(fake_rpc, 1)
    assert len(index) == 250 and index[0]["now"] == ""  # light fields only
    assert [c["id"] for c in core.filter_channels(index, search="notícias")] == [2]
    favs = core.filter_channels(index, favorites=["sic NOTÍCIAS"], only_favorites=True)
    assert [c["name"] for c in favs] == ["SIC Notícias"]
    assert core.with_programmes(fake_rpc, index[:1])[0]["now"] == "Show 1"


def test_schedule_keeps_current_and_upcoming_in_order():
    rows = core.schedule(fake_rpc, 1, now=NOW)
    assert [r["title"] for r in rows] == ["Live", "Later"]
    assert rows[0]["live"] and not rows[1]["live"]
    assert rows[0]["plot"] == "Now on air" and rows[1]["genre"] == "News"


def test_rpc_errors_raise():
    with pytest.raises(core.RpcError):
        core.rpc_call(fake_rpc, "unknown")
    with pytest.raises(core.RpcError):
        core.rpc_call(lambda _: "not json", "PVR.GetChannels")


def test_waits_for_pvr_started_by_a_cold_kodi():
    # As seen on the TV: PVR calls fail with -32100 for ~6 s after Kodi starts.
    replies = iter([{"error": {"code": -32100}}, {"result": {"available": False}}, {"result": {"available": True}}])
    waits = []
    transport = lambda _: json.dumps({"jsonrpc": "2.0", "id": 1, **next(replies)})
    assert core.wait_for_pvr(transport, lambda s: waits.append(s) or False)
    assert waits == [0.5, 0.5]
    never = lambda _: json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32100}})
    assert not core.wait_for_pvr(never, lambda s: False, timeout=2)
    assert not core.wait_for_pvr(never, lambda s: True)  # Kodi shutting down: stop at once


# ---------- official logo and Kodi files ----------

def test_official_logo_is_present_and_unchanged():
    assert hashlib.sha256(LOGO.read_bytes()).hexdigest() == LOGO_SHA256
    assert (MEDIA / "iptv4free-logo.png").read_bytes() == LOGO.read_bytes()


def test_kodi_icon_is_square_transparent_and_declared():
    from PIL import Image
    manifest = ET.parse(ADDON / "addon.xml").getroot()
    assert manifest.findtext(".//assets/icon") == "icon.png"
    with Image.open(ADDON / "icon.png") as icon:
        assert icon.size == (512, 512) and icon.mode == "RGBA"
        assert icon.getpixel((0, 0))[3] == 0 and icon.getpixel((511, 511))[3] == 0


def test_window_xml_controls_and_textures():
    tree = ET.parse(WINDOW)
    ids = {int(c.attrib["id"]) for c in tree.iter("control") if "id" in c.attrib}
    assert {9000, *range(100, 107), 300, 500, 599, 600}.issubset(ids)
    textures = {t.text for t in tree.iter() if t.tag in {"texture", "texturefocus", "texturebg", "midtexture"}
                and t.text and "$INFO" not in t.text}
    textures |= {t.get("fallback") for t in tree.iter("texture") if t.get("fallback")}
    assert textures and all(name.startswith("iptv4free-") for name in textures)
    for name in textures:
        assert (MEDIA / name).is_file(), name
    assert not list(ADDON.rglob("Font.xml"))  # Kodi only loads the active skin's fonts


def test_prepare_branding_keeps_source_and_fits_icon(tmp_path):
    from PIL import Image
    branding = load("prepare_branding", ROOT / "scripts" / "prepare_branding.py")
    source = tmp_path / "original.png"
    image = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
    image.paste((30, 50, 245, 255), (50, 20, 250, 80))
    image.save(source)
    header, icon = tmp_path / "media" / "logo.png", tmp_path / "addon" / "icon.png"
    assert branding.prepare_logo(source=source, header=header, icon=icon)
    assert header.read_bytes() == source.read_bytes()
    with Image.open(icon) as final:
        assert final.size == (512, 512) and final.getpixel((0, 0))[3] == 0
        box = final.getchannel("A").getbbox()
        assert box[2] - box[0] == 488 and abs((box[2] - box[0]) / (box[3] - box[1]) - 200 / 60) < 0.05
    assert not branding.prepare_logo(source=tmp_path / "missing.png", header=header, icon=icon)


def test_zip_is_complete_and_reproducible(tmp_path):
    builder = load("build_addon", ROOT / "scripts" / "build_addon.py")
    a = builder.build(tmp_path / "a")
    b = builder.build(tmp_path / "b")
    assert a.name == "script.iptv4free-0.4.0.zip"
    assert a.read_bytes() == b.read_bytes()
    with ZipFile(a) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        assert {f"script.iptv4free/{p}" for p in builder.REQUIRED} <= names
        assert archive.read("script.iptv4free/resources/skins/Default/media/iptv4free-logo.png") == LOGO.read_bytes()
        assert all(n.startswith("script.iptv4free/") for n in names)


# ---------- default.py against minimal Kodi stubs ----------

class Item:
    def __init__(self, label="", label2="", offscreen=False):
        self.label, self.label2, self.props, self.art = label, label2, {}, {}

    def setProperty(self, k, v): self.props[k] = v
    def getProperty(self, k): return self.props.get(k, "")
    def setArt(self, art): self.art = art
    def getLabel(self): return self.label
    def getLabel2(self): return self.label2


class ListControl:
    def __init__(self): self.items, self.pos = [], 0
    def reset(self): self.items, self.pos = [], 0
    def addItems(self, items): self.items.extend(items); self.pos = 0  # Kodi rebinds: back to row 1
    def size(self): return len(self.items)
    def getSelectedPosition(self): return self.pos if self.items else -1
    def getSelectedItem(self): return self.items[self.pos] if self.items else None
    def getListItem(self, i): return self.items[i]
    def selectItem(self, i): self.pos = i


@pytest.fixture
def ui(tmp_path, monkeypatch):
    calls, builtins = [], []
    state = {"playing": False}

    class Window:
        def __init__(self, *args):
            self.controls, self.props, self.focus, self.closed = {}, {}, None, False

        def getControl(self, cid): return self.controls.setdefault(cid, ListControl())
        def setProperty(self, k, v): self.props[k] = v
        def getProperty(self, k): return self.props.get(k, "")
        def clearProperty(self, k): self.props.pop(k, None)
        def setFocusId(self, cid): self.focus = cid
        def getFocusId(self):
            if self.focus is None:
                raise RuntimeError("no control has focus")
            return self.focus
        def close(self): self.closed = True

    class Player:
        def isPlaying(self): return state["playing"]
        def stop(self): state["playing"] = False

    home_window = Window()
    dialog = types.SimpleNamespace(contextmenu=lambda opts: 1, input=lambda *a: "notícias",
                                   notification=lambda *a: None, textviewer=lambda *a: None)
    stubs = {
        "xbmc": types.SimpleNamespace(
            executeJSONRPC=lambda req: fake_rpc(req, calls), executebuiltin=builtins.append,
            getCondVisibility=lambda c: state["playing"], log=lambda *a: None, sleep=lambda ms: None,
            getInfoLabel=lambda i: state.get("name", "") if state["playing"] else "",
            Player=Player, Monitor=lambda: types.SimpleNamespace(waitForAbort=lambda t: False),
            LOGINFO=1, LOGWARNING=2, LOGERROR=3),
        "xbmcaddon": types.SimpleNamespace(Addon=lambda: types.SimpleNamespace(
            getAddonInfo=lambda k: str(ADDON if k == "path" else tmp_path / "profile"))),
        "xbmcgui": types.SimpleNamespace(WindowXML=Window, ListItem=Item, Dialog=lambda: dialog,
                                         Window=lambda wid: home_window,
                                         getCurrentWindowId=lambda: 13000, NOTIFICATION_ERROR="error"),
        "xbmcvfs": types.SimpleNamespace(translatePath=lambda p: p),
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setitem(sys.modules, "core", core)
    default = load("iptv4free_default", ADDON / "default.py")
    home = default.TVHome("IPTV4FREE.xml", str(ADDON), "Default", "1080i")
    home.boot()
    home.onInit()
    return types.SimpleNamespace(home=home, calls=calls, builtins=builtins, state=state, m=default,
                                 flag=home_window.props)


def test_home_loads_groups_and_first_page(ui):
    home = ui.home
    assert "Loading" not in home.props and home.focus == 500
    assert [i.label for i in home.getControl(300).items] == ["Toutes les chaînes", "Info"]
    assert home.getControl(300).items[1].label2 == "PORTUGAL"
    assert home.getControl(500).size() == 250 and home.props["Count"] == "250 chaînes"
    first = home.getControl(500).items[0]
    assert first.label == "Channel 1" and first.props["number"] == "1" and first.art["thumb"] == "https://logo.example/1.png"


def test_remote_flow_programme_favourite_search_play_back(ui):
    home, m = ui.home, ui.m
    home.onClick(m.OPEN_PROGRAMME)                      # → on a channel
    assert home.focus == 600 and home.props["GuideFor"] == "1"
    assert [i.label2 for i in home.getControl(600).items][:1] == ["Live"]

    home.setFocusId(500)
    home.onAction(types.SimpleNamespace(getId=lambda: 117))  # MENU → "Ajouter aux favoris"
    assert json.loads(Path(home.fav_path).read_text(encoding="utf-8")) == ["Channel 1"]
    assert home.getControl(500).items[0].props["favorite"] == "true"
    home.onClick(m.FAVS)
    assert [i.label for i in home.getControl(500).items] == ["Channel 1"]
    assert home.getControl(500).items[0].label2 == "Show 1"  # now/next filled for short lists

    home.onClick(m.SEARCH)
    assert [i.label for i in home.getControl(500).items] == ["SIC Notícias"]

    ui.state.update(playing=True, name="Channel 1")
    home.onClick(500)
    assert ui.state["playing"] is False and ui.calls[-1] == "Player.Open"  # stop before switching
    home.on_started()
    assert ui.builtins[-1] == "ActivateWindow(fullscreenvideo)"

    ui.state.update(playing=True, name="SIC Notícias")  # OK on the channel already playing
    opens = ui.calls.count("Player.Open")
    home.onClick(500)
    assert ui.calls.count("Player.Open") == opens and ui.state["playing"]
    assert ui.builtins[-1] == "ActivateWindow(fullscreenvideo)"

    home.setFocusId(500)
    home.onAction(types.SimpleNamespace(getId=lambda: 92))
    assert home.focus == 100 and not home.closed
    home.onAction(types.SimpleNamespace(getId=lambda: 92))
    assert home.closed


def test_next_page_keeps_the_selected_row(ui, monkeypatch):
    home, m = ui.home, ui.m
    monkeypatch.setattr(m, "PAGE_SIZE", 100)
    home._show_group(core.channel_groups(fake_rpc)[0])
    assert home.getControl(500).size() == 100 and home.props["Count"] == "100 sur 251"
    home.getControl(500).selectItem(98)
    home.setFocusId(500)
    home.onAction(types.SimpleNamespace(getId=lambda: 4))  # Down near the end loads the next page
    assert home.getControl(500).size() == 200 and home.getControl(500).getSelectedPosition() == 98


def test_emptied_favourites_and_lost_focus_give_the_remote_a_way_out(ui):
    home, m = ui.home, ui.m
    home.setFocusId(500)
    home.onAction(types.SimpleNamespace(getId=lambda: 117))  # add Channel 1
    home.onClick(m.FAVS)
    home.setFocusId(500)
    home.onAction(types.SimpleNamespace(getId=lambda: 117))  # remove it from the Favoris view
    assert home.getControl(500).size() == 0 and home.focus == m.FAVS
    home.focus = None                                        # Kodi could not focus anything
    home.onAction(types.SimpleNamespace(getId=lambda: 1))
    assert home.focus == m.LIVE and not home.closed


def test_back_from_kodi_window_restores_lists_and_marks_playing(ui):
    home = ui.home
    home.getControl(500).reset()  # Kodi rebuilt the window while the guide was open
    ui.state.update(playing=True, name="SIC Notícias")  # and the user zapped in full screen
    home.onInit()
    assert home.getControl(500).size() == 250
    assert [i.label for i in home.getControl(500).items if i.props.get("playing") == "true"] == ["SIC Notícias"]


def test_back_from_guide_keeps_focus_and_failed_open_is_reported(ui):
    home, m = ui.home, ui.m
    home.onClick(m.GUIDE)
    assert ui.builtins[-1] == "ActivateWindow(TVGuide)"
    home.onInit()                       # Back from Kodi's guide
    assert home.focus == m.GUIDE
    home.onClick(500)                   # nothing was playing: open directly
    assert home.props["Status"].startswith("Ouverture de Channel 1")
    home.on_failed()                    # demuxer error: Kodi reports Stopped/Ended, the player is idle
    assert home.props["Status"] == "Lecture impossible : Channel 1"


def test_second_launch_reopens_the_running_window(ui):
    assert ui.flag["iptv4free.window"] == "13000"
    ui.m.main()                         # user starts IPTV4FREE again from Kodi's Home
    assert ui.builtins[-1] == "ActivateWindow(13000)"


def test_addon_server_answers_byte_ranges(tmp_path):
    """Kodi reads ZIPs with ranges; without them Kodi 21.3 crashed during "Install from zip file"."""
    import threading
    import urllib.request
    server_mod = load("serve_addon", ROOT / "scripts" / "serve_addon.py")
    (tmp_path / "a.zip").write_bytes(bytes(range(256)) * 4)
    server = server_mod.serve(0, tmp_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        def get(rng=None):
            req = urllib.request.Request(base + "/a.zip", headers={"Range": rng} if rng else {})
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.headers.get("Content-Range"), resp.read()
        assert get("bytes=10-19") == (206, "bytes 10-19/1024", bytes(range(10, 20)))
        assert get("bytes=-22")[1:] == ("bytes 1002-1023/1024", (bytes(range(256)) * 4)[-22:])
        assert get("bytes=1000-")[2] == (bytes(range(256)) * 4)[1000:]
        assert get()[0] == 200 and len(get()[2]) == 1024
        with urllib.request.urlopen(base + "/") as resp:
            assert b"a.zip" in resp.read()  # Kodi browses this listing as a file source
    finally:
        server.shutdown()
        server.server_close()
