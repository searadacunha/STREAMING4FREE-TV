"""Local HLS relay for streams that Kodi cannot fetch fast enough on its own.

Two problems were measured on the TV (08/11/2026):
- some servers cap each HTTP connection (~3.9 Mb/s on the relay that carries TF1 or TFX)
  below the stream's bitrate (4.8 Mb/s average, 8 Mb/s peaks): Kodi downloads a segment on
  one connection, the queue runs dry, the picture freezes every 10-13 s;
- multi-variant masters (Pluto TV, Samsung TV Plus...): Kodi's FFmpeg opens every variant
  before choosing one, so a channel takes 20-30 s to start.

The relay serves each segment by fetching byte ranges over several connections at once and
hands back masters reduced to the variant Kodi would pick (the highest bandwidth). Nothing
is cached: playlists are fetched from the source on every request, so signed URLs and
their expiry are untouched. It listens on 127.0.0.1 only. Pure standard library, no Kodi
import, so the same file runs in Kodi and in the tests.
"""
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 52180
PARTS = 4                    # parallel connections per segment (~4x the per-connection cap)
PART_SIZE = 768 * 1024
TIMEOUT = 15
PLAYLIST_LIMIT = 2 * 1024 * 1024
HLS_TYPE = "application/vnd.apple.mpegurl"


def log(message):
    """Replaced by the Kodi service with xbmc.log; silent in tests."""


def encode(url, headers=None):
    """Token carrying the source URL and its HTTP headers (the M3U builder uses the same)."""
    raw = json.dumps({"u": url, "h": headers or {}}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(token):
    data = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    url, headers = data["u"], data.get("h") or {}
    if not url.startswith(("http://", "https://")) or not isinstance(headers, dict):
        raise ValueError("not an http(s) source")
    return url, {str(k): str(v) for k, v in headers.items()}


def local_url(url, headers=None, name="index.m3u8", port=PORT):
    return "http://127.0.0.1:%d/%s/%s" % (port, encode(url, headers), name)


def _name(uri, default):
    """Last path element, so FFmpeg sees the same extension as the source (.ts, .m4s, .aac...)."""
    last = urllib.parse.urlsplit(uri).path.rsplit("/", 1)[-1]
    return last if "." in last and len(last) < 80 else default


def _attrs(line):
    out, i = {}, line.find(":") + 1
    for part in _split_attrs(line[i:]):
        key, _, value = part.partition("=")
        out[key.strip()] = value.strip().strip('"')
    return out


def _split_attrs(text):
    parts, cur, quoted = [], "", False
    for c in text:
        if c == '"':
            quoted = not quoted
        if c == "," and not quoted:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    return parts + [cur] if cur else parts


def _rewrite_uri_attr(line, base, headers, port, default):
    start = line.find('URI="')
    if start < 0:
        return line
    start += 5
    end = line.find('"', start)
    absolute = urllib.parse.urljoin(base, line[start:end])
    return line[:start] + local_url(absolute, headers, _name(absolute, default), port) + line[end:]


def rewrite_playlist(text, base, headers, port=PORT):
    """Master: keep only the highest-bandwidth variant and the renditions it uses.
    Media playlist: point every segment, key and init section at the relay."""
    lines = [ln.strip() for ln in text.splitlines()]
    if any(ln.startswith("#EXT-X-STREAM-INF") for ln in lines):
        best, best_bw = None, -1.0
        for i, ln in enumerate(lines):
            if ln.startswith("#EXT-X-STREAM-INF"):
                uri = next((x for x in lines[i + 1:] if x and not x.startswith("#")), None)
                bw = float(_attrs(ln).get("BANDWIDTH", "0") or 0)
                if uri and bw > best_bw:
                    best, best_bw = (ln, uri), bw
        if best is None:
            return text
        groups = {v for k, v in _attrs(best[0]).items() if k in ("AUDIO", "SUBTITLES", "VIDEO")}
        out = []
        for ln in lines:
            if ln.startswith("#EXT-X-MEDIA:"):
                if _attrs(ln).get("GROUP-ID") in groups:
                    out.append(_rewrite_uri_attr(ln, base, headers, port, "media.m3u8"))
            elif ln.startswith(("#EXTM3U", "#EXT-X-VERSION", "#EXT-X-INDEPENDENT", "#EXT-X-START")):
                out.append(ln)
        absolute = urllib.parse.urljoin(base, best[1])
        out += [best[0], local_url(absolute, headers, _name(absolute, "variant.m3u8"), port)]
        return "\n".join(out) + "\n"
    out = []
    for ln in lines:
        if ln.startswith(("#EXT-X-KEY", "#EXT-X-MAP")):
            out.append(_rewrite_uri_attr(ln, base, headers, port,
                                         "init.mp4" if ln.startswith("#EXT-X-MAP") else "key.bin"))
        elif ln and not ln.startswith("#"):
            absolute = urllib.parse.urljoin(base, ln)
            out.append(local_url(absolute, headers, _name(absolute, "segment.ts"), port))
        else:
            out.append(ln)
    return "\n".join(out) + "\n"


def _open(url, headers, rng=None):
    h = dict(headers)
    if rng:
        h["Range"] = "bytes=%d-%d" % rng
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=TIMEOUT)


def _part(url, headers, rng):
    for attempt in (1, 2):
        try:
            with _open(url, headers, rng) as resp:
                data = resp.read()
            if resp.status == 206 and len(data) == rng[1] - rng[0] + 1:
                return data
        except (OSError, urllib.error.URLError):
            if attempt == 2:
                raise
    raise OSError("range %d-%d not delivered" % rng)


def _total(content_range):
    try:
        return int(content_range.rsplit("/", 1)[1])
    except (AttributeError, IndexError, ValueError):
        return None


def _asked(value):
    """(first byte, last byte or None) of a player's Range header; (0, None) without one."""
    try:
        a, _, b = value.split("=", 1)[1].split(",")[0].strip().partition("-")
        return int(a), (int(b) if b else None)
    except (AttributeError, IndexError, ValueError):
        return 0, None


class ClientGone(Exception):
    """The player hung up (channel change, stop, FFmpeg probing): not a source error."""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "IPTV4FREE-relay"

    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            token, _, name = self.path.lstrip("/").partition("/")
            url, headers = decode(token)
        except (ValueError, KeyError, TypeError):
            return self._fail(400)
        self.started = False
        try:
            if name.endswith(".m3u8"):
                self._playlist(url, headers)
            else:
                self._media(url, headers)
        except ClientGone:
            self.close_connection = True
        except (OSError, urllib.error.URLError) as e:
            # host only: source URLs may carry tokens
            log("%s from %s (%s)" % (type(e).__name__, urllib.parse.urlsplit(url).hostname, str(e)[:80]))
            if self.started:  # headers already sent: only a cut connection tells the player
                self.close_connection = True
            else:
                self._fail(e.code if isinstance(e, urllib.error.HTTPError) else 502)

    def _begin(self, ctype, length=None, status=200, content_range=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        if content_range:
            self.send_header("Content-Range", content_range)
        if length is None:
            self.send_header("Connection", "close")
            self.close_connection = True
        else:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.started = True

    def _fail(self, code):
        try:
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except OSError:
            pass  # the client already left

    def _send(self, data):
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError) as e:
            raise ClientGone() from e

    def _copy(self, resp):
        sent = 0
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                return sent
            self._send(chunk)
            sent += len(chunk)

    def _playlist(self, url, headers):
        with _open(url, headers) as resp:
            final, body = resp.geturl(), resp.read(PLAYLIST_LIMIT)
        text = body.decode("utf-8", "replace")
        out = (rewrite_playlist(text, final, headers, self.server.server_address[1])
               if text.lstrip("\ufeff").startswith("#EXTM3U") else text).encode("utf-8")
        self._begin(HLS_TYPE, len(out))
        self._send(out)

    def _media(self, url, headers):
        """Segment: first range on this thread, the others on PARTS - 1 more connections,
        sent back in order as they land. FFmpeg always asks "Range: bytes=0-": an open
        range is served this way too; only a closed one (EXT-X-BYTERANGE) is passed through."""
        start, last = _asked(self.headers.get("Range"))
        if last is not None:
            with _open(url, headers, (start, last)) as resp:
                self._begin(resp.headers.get("Content-Type", "video/mp2t"),
                            resp.headers.get("Content-Length"), resp.status,
                            resp.headers.get("Content-Range"))
                self._copy(resp)
            return
        with _open(url, headers, (start, start + PART_SIZE - 1)) as resp:
            total = _total(resp.headers.get("Content-Range")) if resp.status == 206 else None
            ctype = resp.headers.get("Content-Type", "video/mp2t")
            if total is None:  # no range support: plain pass-through of the whole file
                length = resp.headers.get("Content-Length")
                self._begin(ctype, int(length) if length and length.isdigit() else None)
                self._copy(resp)
                return
            pool, rest = ThreadPoolExecutor(max_workers=PARTS - 1), []
            try:
                rest = [pool.submit(_part, url, headers, (s, min(s + PART_SIZE, total) - 1))
                        for s in range(start + PART_SIZE, total, PART_SIZE)]
                if start:
                    self._begin(ctype, total - start, 206, "bytes %d-%d/%d" % (start, total - 1, total))
                else:
                    self._begin(ctype, total)  # the player starts reading while the ranges arrive
                if self._copy(resp) != min(PART_SIZE, total - start):
                    raise OSError("first range cut short")
                for f in rest:
                    self._send(f.result())
            finally:
                for f in rest:
                    f.cancel()  # player gone or a range failed: drop what has not started
                pool.shutdown(wait=False)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], ConnectionError):  # Kodi hangs up on every stop
            super().handle_error(request, client_address)


def serve(port=PORT):
    """Bind on loopback only; the caller runs serve_forever() and shutdown()."""
    return Server(("127.0.0.1", port), Handler)
