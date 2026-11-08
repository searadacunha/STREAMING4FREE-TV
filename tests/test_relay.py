"""Local HLS relay of the Kodi add-on, against a fake source that caps each connection."""
import importlib.util
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "iptv4free_relay", ROOT / "kodi-addon" / "script.iptv4free" / "resources" / "lib" / "relay.py")
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)

SEGMENT = bytes(range(256)) * 12_000  # 3 MB, every byte position checkable
CAP = 4_000_000  # bytes/s per connection


class Source(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    ranges = True
    seen_agents: list = []
    open_now = peak = 0
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def do_GET(self):
        with Source.lock:
            Source.open_now += 1
            Source.peak = max(Source.peak, Source.open_now)
        try:
            self._get()
        finally:
            with Source.lock:
                Source.open_now -= 1

    def _get(self):
        Source.seen_agents.append(self.headers.get("User-Agent"))
        if self.path == "/live/master.m3u8":
            body = ("#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID=\"aud\",NAME=\"fr\",URI=\"a/fr.m3u8\"\n"
                    "#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID=\"other\",NAME=\"x\",URI=\"a/x.m3u8\"\n"
                    "#EXT-X-STREAM-INF:BANDWIDTH=800000,AUDIO=\"other\"\nlow/index.m3u8\n"
                    "#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,AUDIO=\"aud\"\nhigh/index.m3u8\n").encode()
            return self._send(200, body, "application/vnd.apple.mpegurl")
        if self.path == "/live/high/index.m3u8":
            body = (b"#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXT-X-MEDIA-SEQUENCE:7\n"
                    b"#EXT-X-KEY:METHOD=AES-128,URI=\"../key\"\n#EXTINF:6,\n7.ts\n")
            return self._send(200, body, "application/vnd.apple.mpegurl")
        if self.path == "/live/high/7.ts":
            rng = self.headers.get("Range")
            if rng and Source.ranges:
                a, b = (int(x) for x in rng.split("=")[1].split("-"))
                b = min(b, len(SEGMENT) - 1)
                return self._send(206, SEGMENT[a:b + 1], "video/mp2t",
                                  {"Content-Range": f"bytes {a}-{b}/{len(SEGMENT)}"})
            return self._send(200, SEGMENT, "video/mp2t")
        self._send(404, b"", "text/plain")

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        for i in range(0, len(body), 64 * 1024):  # per-connection speed cap
            time.sleep(64 * 1024 / CAP)
            self.wfile.write(body[i:i + 64 * 1024])


@pytest.fixture
def servers():
    src = ThreadingHTTPServer(("127.0.0.1", 0), Source)
    rel = relay.serve(port=0)
    for s in (src, rel):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    Source.ranges, Source.seen_agents, Source.peak = True, [], 0
    yield f"http://127.0.0.1:{src.server_address[1]}", rel.server_address[1]
    for s in (src, rel):
        s.shutdown()
        s.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return r.status, r.read()


def test_token_round_trip_and_rejects_non_http():
    url, headers = "https://h/x.m3u8?token=a&b=1", {"User-Agent": "UA/1", "Referer": "https://r/"}
    assert relay.decode(relay.encode(url, headers)) == (url, headers)
    with pytest.raises(ValueError):
        relay.decode(relay.encode("file:///etc/passwd"))


def test_master_keeps_best_variant_and_its_audio(servers):
    src, port = servers
    status, body = get(relay.local_url(src + "/live/master.m3u8", {"User-Agent": "UA/1"}, port=port))
    text = body.decode()
    assert status == 200 and text.count("#EXT-X-STREAM-INF") == 1 and "BANDWIDTH=5000000" in text
    assert 'GROUP-ID="aud"' in text and 'GROUP-ID="other"' not in text
    variant = [ln for ln in text.splitlines() if ln.startswith("http://127.0.0.1")][-1]
    assert relay.decode(variant.split("/")[3]) == (src + "/live/high/index.m3u8", {"User-Agent": "UA/1"})
    # media playlist: segment and key point at the relay, absolute source URLs inside
    media = get(variant)[1].decode()
    seg = [ln for ln in media.splitlines() if ln.startswith("http://127.0.0.1")][0]
    assert seg.endswith("/7.ts") and relay.decode(seg.split("/")[3])[0] == src + "/live/high/7.ts"
    key = media.split('URI="')[1].split('"')[0]
    assert relay.decode(key.split("/")[3])[0] == src + "/live/key"
    assert set(Source.seen_agents) == {"UA/1"}  # the source's headers reach the source


def test_segment_arrives_whole_and_faster_than_one_connection(servers):
    src, port = servers
    url = relay.local_url(src + "/live/high/7.ts", port=port, name="7.ts")
    start = time.monotonic()
    status, body = get(url)
    took = time.monotonic() - start
    assert status == 200 and body == SEGMENT
    one_connection = len(SEGMENT) / CAP  # ~0.75 s
    assert took < one_connection * 0.7, took


def test_segment_without_range_support_passes_through(servers):
    src, port = servers
    Source.ranges = False
    status, body = get(relay.local_url(src + "/live/high/7.ts", port=port, name="7.ts"))
    assert status == 200 and body == SEGMENT


def test_ffmpeg_open_range_still_uses_parallel_ranges(servers):
    src, port = servers  # Kodi's FFmpeg sends "Range: bytes=0-" on every request
    url = relay.local_url(src + "/live/high/7.ts", port=port, name="7.ts")
    start = time.monotonic()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-"}), timeout=20) as r:
        assert r.status == 200 and r.read() == SEGMENT
    assert time.monotonic() - start < len(SEGMENT) / CAP * 0.7
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=1000000-"}), timeout=20) as r:
        assert r.status == 206 and r.read() == SEGMENT[1000000:]
        assert r.headers["Content-Range"] == f"bytes 1000000-{len(SEGMENT) - 1}/{len(SEGMENT)}"


def test_player_byte_range_is_passed_through(servers):
    src, port = servers  # EXT-X-BYTERANGE: the player asks for one slice of a file
    req = urllib.request.Request(relay.local_url(src + "/live/high/7.ts", port=port, name="7.ts"),
                                 headers={"Range": "bytes=1000-1999"})
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 206 and r.read() == SEGMENT[1000:2000]
        assert r.headers["Content-Range"] == f"bytes 1000-1999/{len(SEGMENT)}"
    assert relay._asked("bytes=-500")[0] is None  # suffix range: passed through as well


def test_source_errors_are_passed_on(servers):
    src, port = servers
    with pytest.raises(urllib.error.HTTPError) as e:
        get(relay.local_url(src + "/live/missing.m3u8", port=port))
    assert e.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as e:
        get(f"http://127.0.0.1:{port}/not-a-token/index.m3u8")
    assert e.value.code == 400


def test_relay_listens_on_loopback_only():
    server = relay.serve(port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def test_connections_to_one_server_stay_bounded(servers):
    src, port = servers  # three segments asked at once, as FFmpeg does when it reads ahead
    from concurrent.futures import ThreadPoolExecutor
    url = relay.local_url(src + "/live/high/7.ts", port=port, name="7.ts")
    with ThreadPoolExecutor(3) as pool:
        bodies = list(pool.map(lambda _: get(url)[1], range(3)))
    assert bodies == [SEGMENT] * 3
    assert Source.peak <= 3 + (relay.PARTS - 1), Source.peak  # one first range per request + shared parts
