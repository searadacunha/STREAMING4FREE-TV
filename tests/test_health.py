from iptv4free import health
from iptv4free.scanner import Target


def test_replay_counts_stalls_only_when_the_buffer_runs_dry():
    # three segments of 5 s land together at t=0, then one every 5 s: never stalls
    smooth = [(0, 5), (0, 5), (0, 5), (5, 5), (10, 5), (15, 5)]
    assert health.replay(smooth, 0) == (0, 0.0)
    # one 5 s segment, the next lands at t=8: 3 s stalled, then on time again
    late = [(0, 5), (8, 5), (13, 5)]
    assert health.replay(late, 0) == (1, 3.0)


def test_parse_media_playlist_and_best_variant():
    seq, target, segs, ended = health.parse_media_playlist(
        "http://h/a/mono.m3u8",
        "#EXTM3U\n#EXT-X-TARGETDURATION:7\n#EXT-X-MEDIA-SEQUENCE:41\n#EXTINF:5.6,\n1.ts\n#EXTINF:5,\n2.ts\n")
    assert (seq, target, ended) == (41, 7.0, False)
    assert segs == [(41, 5.6, "http://h/a/1.ts"), (42, 5.0, "http://h/a/2.ts")]
    master = ("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360\nlow.m3u8\n"
              "#EXT-X-STREAM-INF:RESOLUTION=1920x1080,BANDWIDTH=5980000\nhigh.m3u8\n")
    assert health.best_variant("http://h/x/master.m3u8", master) == ("http://h/x/high.m3u8", 5980000.0)


class FakeLive:
    """A live HLS server on a fake clock: one 5 s segment every 5 s, 4 in the window,
    each download taking `dl(seq)` seconds."""

    def __init__(self, dl=lambda seq: 0.2, fail=()):
        self.now, self.dl, self.fail = 100.0, dl, set(fail)

    def clock(self):
        return self.now

    def sleep(self, s):
        self.now += s

    def fetch(self, url, headers, limit, timeout):
        if url.endswith(".m3u8"):
            newest = int(self.now // 5)
            body = "#EXTM3U\n#EXT-X-TARGETDURATION:5\n#EXT-X-MEDIA-SEQUENCE:%d\n" % (newest - 3)
            body += "".join("#EXTINF:5,\n%d.ts\n" % s for s in range(newest - 3, newest + 1))
            return url, body.encode()
        seq = int(url.rsplit("/", 1)[1][:-3])
        self.now += self.dl(seq)
        if seq in self.fail:
            raise TimeoutError("timed out")
        return url, b"\x47" * 1_000_000


def run(server, seconds=120):
    t = Target("k", "http://h/live/index.m3u8", ())
    return health.check(t, seconds, fetch=server.fetch, clock=server.clock, sleep=server.sleep)


def test_hls_follow_stable_stream():
    h = run(FakeLive())
    assert h.kind == "hls" and h.verdict == "stable", h
    assert h.stalls == 0 and h.missed == 0 and h.errors == 0
    assert h.segments >= 25 and h.speed_p10 > 30e6


def test_hls_follow_slow_server_is_unstable():
    h = run(FakeLive(dl=lambda seq: 7.0))  # every 5 s segment takes 7 s to download
    assert h.verdict == "unstable" and h.stalls > 3 and h.slow_segments == h.segments, h


def test_hls_follow_counts_errors_and_dead_streams():
    h = run(FakeLive(fail={s for s in range(0, 10**6, 3)}))
    assert h.errors > health.MAX_ERRORS and h.verdict == "unstable", h

    def refuse(url, headers, limit, timeout):
        raise OSError("connection refused")
    dead = health.check(Target("k", "http://h/x.m3u8", ()), 60, fetch=refuse)
    assert dead.verdict == "dead" and "OSError" in dead.detail


def test_health_book_round_trip(tmp_path):
    book = health.HealthBook(tmp_path / "health.json")
    book.record(run(FakeLive(dl=lambda seq: 7.0), seconds=60))
    book.save()
    again = health.HealthBook(tmp_path / "health.json")
    assert again.verdict("k") == "unstable" and again.verdict("other") is None
