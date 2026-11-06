import gzip
import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

TESTS = Path(__file__).parent
SEGMENT = b"\x47" * 4096  # MPEG-TS sync bytes

EPG_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="Alpha.xx"><display-name>Alpha</display-name></channel>
  <channel id="BetaNews.xx"><display-name>Beta News</display-name></channel>
  <channel id="Gamma.xx"><display-name>Gamma TV</display-name></channel>
  <programme channel="Alpha.xx" start="20260101000000 +0000"><title>Show</title></programme>
</tv>
"""


class Handler(BaseHTTPRequestHandler):
    routes: dict = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        route = self.routes.get(self.path.split("?")[0])
        if route is None:
            self.send_error(404)
            return
        status, body, need_ua = route
        if need_ua and self.headers.get("User-Agent") != need_ua:
            self.send_error(403)
            return
        if status == "slow":
            time.sleep(3)
            status = 200
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def playlist(*entries: str) -> bytes:
    return ("#EXTM3U\n" + "\n".join(entries) + "\n").encode()


@pytest.fixture(scope="session")
def http_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{server.server_port}"
    media = playlist("#EXT-X-TARGETDURATION:6", "#EXTINF:6,", "seg1.ts", "#EXTINF:6,", "seg2.ts")
    Handler.routes = {
        "/master.m3u8": (200, playlist("#EXT-X-STREAM-INF:BANDWIDTH=1", "v/index.m3u8"), None),
        "/v/index.m3u8": (200, media, None),
        "/v/seg2.ts": (200, SEGMENT, None),
        "/direct.ts": (200, SEGMENT, None),
        "/tiny.ts": (200, b"x" * 10, None),
        "/slow.ts": ("slow", SEGMENT, None),
        "/empty.m3u8": (200, b"#EXTM3U\n#EXT-X-TARGETDURATION:6\n", None),
        "/nomaster.m3u8": (200, b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\n", None),
        "/dash.mpd": (200, b'<?xml version="1.0"?><MPD type="dynamic"></MPD>', None),
        "/ua/index.m3u8": (200, media, "Special/1.0"),
        "/ua/seg2.ts": (200, SEGMENT, "Special/1.0"),
        "/epg.xml.gz": (200, gzip.compress(EPG_XML), None),
    }
    Handler.routes["/fr.m3u"] = (200, playlist(
        '#EXTINF:-1 tvg-id="Alpha.xx@SD" tvg-logo="http://logo/a.png" group-title="General",Alpha (720p)',
        f"{base}/master.m3u8",
        '#EXTINF:-1 tvg-id="Alpha.xx@HD" group-title="General",Alpha HD (1080p)',
        f"{base}/direct.ts?hd",
        '#EXTINF:-1 tvg-id="BetaNews.xx" group-title="News",Beta News [Geo-blocked]',
        f"{base}/dash.mpd",
        '#EXTINF:-1 tvg-id="Dead.xx" group-title="News",Dead Channel',
        f"{base}/missing.m3u8",
        '#EXTINF:-1 group-title="Music",Special UA',
        "#EXTVLCOPT:http-user-agent=Special/1.0",
        f"{base}/ua/index.m3u8",
    ), None)
    Handler.routes["/world.m3u"] = (200, playlist(
        '#EXTINF:-1 tvg-id="Alpha.xx@SD" group-title="General",Alpha (720p)',
        f"{base}/master.m3u8",
        '#EXTINF:-1 tvg-id="Gamma.xx" group-title="Sports",Gamma TV',
        f"{base}/direct.ts?gamma",
        '#EXTINF:-1 group-title="Shop",Shopping',
        f"{base}/direct.ts?shop",
        '#EXTINF:-1 group-title="Undefined",Mystery',
        f"{base}/direct.ts?mystery",
    ), None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield base
    server.shutdown()


@pytest.fixture
def fake_tv(tmp_path):
    root = tmp_path / "tv"
    root.mkdir()
    wrapper = tmp_path / "adb"
    wrapper.write_text(f'#!/bin/sh\nFAKE_ADB_ROOT="{root}" exec "{sys.executable}" '
                       f'"{TESTS / "fake_adb.py"}" "$@"\n')
    wrapper.chmod(0o755)
    return root, str(wrapper)


class FakeKodi:
    """JSON-RPC TCP server answering like Kodi, with a notification before each reply."""

    def __init__(self):
        self.calls: list[str] = []
        self.playing = False
        self.addon_enabled = True
        self.addons: dict[str, dict] = {}  # other installed add-ons: id -> {"version", "enabled"}
        self.settings = {"lookandfeel.skin": "skin.estuary"}
        self.hang: set[str] = set()  # methods that never answer in time (frozen Kodi)
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                req = json.loads(conn.recv(65536))
                self.calls.append(req["method"])
                params = req.get("params", {})
                if req["method"] in self.hang:
                    time.sleep(1)
                    continue
                addon = params.get("addonid")
                if addon and addon != "pvr.iptvsimple" and addon not in self.addons:
                    reply = {"jsonrpc": "2.0", "id": req["id"],
                             "error": {"code": -32602, "message": "Invalid params."}}
                    conn.sendall(json.dumps(reply).encode())
                    continue
                if req["method"] == "Addons.SetAddonEnabled":
                    self.addons[addon]["enabled"] = params["enabled"]
                result = {
                    "JSONRPC.Ping": "pong",
                    "Player.GetActivePlayers": [{"playerid": 1}] if self.playing else [],
                    "Application.Quit": "OK",
                    "Addons.GetAddonDetails": {"addon": self.addons[addon] if addon in self.addons
                                               else {"enabled": self.addon_enabled,
                                                     "version": "21.11.0"}},
                    "Addons.SetAddonEnabled": "OK",
                    "Settings.GetSettingValue": {"value": self.settings.get(params.get("setting"))},
                    "PVR.GetChannelGroups": {"channelgroups": [{"channelgroupid": 1}]},
                    "PVR.GetChannels": {"limits": {"total": 4}},
                }.get(req["method"])
                note = {"jsonrpc": "2.0", "method": "GUI.OnScreensaverDeactivated", "params": {}}
                reply = {"jsonrpc": "2.0", "id": req["id"], "result": result}
                # notification and reply in one packet: the client must split them
                conn.sendall((json.dumps(note) + json.dumps(reply)).encode())

    def close(self):
        self.sock.close()


@pytest.fixture
def fake_kodi():
    k = FakeKodi()
    yield k
    k.close()


@pytest.fixture
def make_config(tmp_path):
    def make(lineups: str, **sections) -> Path:
        tv = {"address": '"192.0.2.10:5555"', "adb": '"adb"', "adb_timeout": "10"}
        tv.update(sections.pop("tv", {}))
        text = "[tv]\n" + "".join(f"{k} = {v}\n" for k, v in tv.items())
        text += f'[paths]\nstate_dir = "{tmp_path / "state"}"\noutput_dir = "{tmp_path / "out"}"\n'
        for name, values in sections.items():
            text += f"[{name}]\n" + "".join(f"{k} = {v}\n" for k, v in values.items())
        path = tmp_path / "iptv4free.toml"
        path.write_text(text + lineups)
        return path
    return make
