import time

from iptv4free.scanner import Target, probe, scan


def t(url, **headers):
    return Target(url, url, tuple(headers.items()))


def test_probe_outcomes(http_server):
    cases = {
        "/master.m3u8": (True, "HLS segment"),
        "/v/index.m3u8": (True, "HLS segment"),
        "/direct.ts": (True, "direct stream"),
        "/dash.mpd": (True, "DASH"),
        "/tiny.ts": (False, "direct stream, 10 bytes"),
        "/missing.m3u8": (False, "HTTPError"),
        "/empty.m3u8": (False, "without segments"),
        "/nomaster.m3u8": (False, "without variants"),
    }
    for path, (ok, detail) in cases.items():
        r = probe(t(http_server + path), timeout=2)
        assert r.ok is ok and detail in r.detail, (path, r)


def test_probe_sends_stream_headers_and_default_agent(http_server):
    url = http_server + "/ua/index.m3u8"
    assert not probe(t(url), 2, default_user_agent="Kodi").ok
    assert probe(t(url, **{"User-Agent": "Special/1.0"}), 2, default_user_agent="Kodi").ok
    assert probe(t(url), 2, default_user_agent="Special/1.0").ok


def test_probe_timeout_is_enforced(http_server):
    start = time.monotonic()
    r = probe(t(http_server + "/slow.ts"), timeout=0.5)
    assert not r.ok and time.monotonic() - start < 2.5


def test_probe_unreachable_host():
    r = probe(t("http://127.0.0.1:9/x.m3u8"), timeout=1)
    assert not r.ok


def test_scan_keeps_input_order_and_reports_progress(http_server):
    targets = [t(http_server + p) for p in ("/direct.ts", "/missing.m3u8", "/dash.mpd")] * 5
    seen = []
    results = scan(targets, timeout=2, workers=4, progress=lambda d, n: seen.append((d, n)))
    assert [r.key for r in results] == [x.key for x in targets]
    assert [r.ok for r in results[:3]] == [True, False, True]
    assert seen[-1] == (15, 15) and len(seen) == 15
