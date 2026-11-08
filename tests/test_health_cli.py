import threading
import time
import urllib.parse

from iptv4free import cli, health
from iptv4free.playlists import parse_m3u

LINEUP = '[[lineup]]\nid = "fr"\nname = "France"\nsources = ["http://src/fr.m3u"]\n'
PLAYLIST = """#EXTM3U
#EXTINF:-1 group-title="France · Favoris;France · Toutes",A1
http://a.example/1.m3u8
#EXTINF:-1 group-title="France · Favoris;France · Toutes",A2
http://a.example/2.m3u8
#EXTINF:-1 group-title="France · Favoris;France · Toutes",B1
http://b.example/1.m3u8
#EXTINF:-1 group-title="France · Favoris;France · Toutes",B2
#EXTVLCOPT:http-user-agent=UA/1
http://b.example/2.m3u8
#EXTINF:-1 group-title="France · Toutes",Other
http://c.example/1.m3u8
"""


def test_health_follows_one_stream_per_host_and_tune_round_trip(make_config, tmp_path, monkeypatch, capsys):
    cfg = make_config(LINEUP, labels={"favorites": '"Favoris"'})
    m3u = tmp_path / "france.m3u"
    m3u.write_text(PLAYLIST)
    busy, overlap, seen = {}, [], []
    guard = threading.Lock()

    def fake(target, seconds, timeout, ua):
        host = urllib.parse.urlsplit(target.url).netloc
        with guard:
            if busy.get(host):
                overlap.append(host)
            busy[host] = True
            seen.append(target.url)
        time.sleep(0.05)
        with guard:
            busy[host] = False
        bad = target.url.startswith("http://a.")  # host a: stalls directly, fine through the relay
        h = health.Health(target.key, kind="hls", startup=1.0, seconds=seconds, variants=1,
                          stalls=5 if bad else 0, stall_seconds=30.0 if bad else 0.0)
        return h, (health.Health(target.key, kind="hls", startup=1.0, seconds=seconds) if bad else None)
    monkeypatch.setattr(health, "check_with_relay", fake)

    assert cli.main(["--config", str(cfg), "health", "--playlist", str(m3u), "--workers", "4"]) == 0
    assert overlap == [] and len(seen) == 4 and "http://c.example/1.m3u8" not in seen  # favourites only
    assert "relay helps" in capsys.readouterr().out

    out = tmp_path / "tuned"
    assert cli.main(["--config", str(cfg), "tune", str(m3u), "--out", str(out)]) == 0
    tuned = parse_m3u((out / "france.m3u").read_text()).entries
    assert [e.url.startswith("http://127.0.0.1:52180/") for e in tuned] == [True, True, False, False, False]
    assert cli.main(["--config", str(cfg), "tune", str(out / "france.m3u"), "--undo", "--out", str(tmp_path / "back")]) == 0
    assert (tmp_path / "back" / "france.m3u").read_text() == m3u.read_text()
