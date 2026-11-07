"""Serve dist/ on the local network so Kodi can "Install from zip file" over Wi-Fi.

Kodi reads ZIP files over HTTP with byte ranges. `python3 -m http.server` ignores them, and
Kodi 21.3 then fails to read the ZIP and can crash. This server answers ranges.

Usage: python3 scripts/serve_addon.py [port]      (default 8780; stop with Ctrl+C after install)
"""
import os
import re
import socket
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIST = Path(__file__).resolve().parents[1] / "dist"


class RangeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        self._remaining = None
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
        path = self.translate_path(self.path)
        if not match or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        first, last = match.groups()
        if first:
            start, end = int(first), min(int(last) if last else size - 1, size - 1)
        else:  # "bytes=-N": the last N bytes (how a ZIP's central directory is read)
            start, end = max(0, size - int(last or 0)), size - 1
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        handle = open(path, "rb")
        handle.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._remaining = end - start + 1
        return handle

    def copyfile(self, source, outputfile):
        if self._remaining is None:
            return super().copyfile(source, outputfile)
        while self._remaining > 0:
            chunk = source.read(min(65536, self._remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            self._remaining -= len(chunk)


def lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 80))  # no packet is sent; picks the LAN interface
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def serve(port: int = 8780, directory: Path = DIST) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("0.0.0.0", port), partial(RangeHandler, directory=str(directory)))


if __name__ == "__main__":
    server = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8780)
    print(f"Kodi source: http://{lan_ip()}:{server.server_address[1]}/  (serving {DIST}, Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
