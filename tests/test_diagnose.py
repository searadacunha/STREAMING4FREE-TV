from iptv4free import diagnose, health
from iptv4free.playlists import Entry, effective_url, parse_m3u, render_m3u

LOG = """﻿2026-11-08 16:36:02.881 T:1 info <general>: AddOnLog: pvr.iptvsimple: pvr.iptvsimple - GetChannelStreamProperties - Live Stream URL: http://149.62.177.107:9999/TFX/index.m3u8?token=SECRET
2026-11-08 16:36:02.895 T:1 info <general>: VideoPlayer::OpenFile: pvr://channels/tv/x/1@pvr.iptvsimple_1.pvr
2026-11-08 16:36:04.000 T:2 info <general>: Opening stream: 7 source: 256
2026-11-08 16:37:00.000 T:3 info <general>: CVideoPlayerAudio::Process - stream stalled
2026-11-08 16:37:12.000 T:3 info <general>: CVideoPlayerAudio::Process - stream stalled
2026-11-08 16:37:24.000 T:3 info <general>: CVideoPlayerAudio::Process - stream stalled
2026-11-08 16:37:36.000 T:3 info <general>: CVideoPlayerAudio::Process - stream stalled
2026-11-08 16:37:40.000 T:4 warning <general>: ActiveAE - large audio sync error: -89631.9
2026-11-08 16:38:04.000 T:1 info <general>: AddOnLog: pvr.iptvsimple: pvr.iptvsimple - GetChannelStreamProperties - Live Stream URL: http://149.62.177.107:9999/TF1/index.m3u8
2026-11-08 16:38:04.010 T:1 info <general>: VideoPlayer::OpenFile: pvr://channels/tv/x/1@pvr.iptvsimple_9.pvr
2026-11-08 16:38:06.010 T:2 info <general>: Opening stream: 7 source: 256
2026-11-08 16:39:06.010 T:1 info <general>: CVideoPlayer::CloseFile()
2026-11-08 16:40:00.000 T:1 info <general>: AddOnLog: pvr.iptvsimple: pvr.iptvsimple - GetChannelStreamProperties - Live Stream URL: http://99.27.51.147:8080/gulli/index.m3u8
2026-11-08 16:40:00.100 T:1 info <general>: VideoPlayer::OpenFile: pvr://channels/tv/x/1@pvr.iptvsimple_2.pvr
2026-11-08 16:40:02.100 T:2 info <general>: Opening stream: 0 source: 256
2026-11-08 17:00:02.100 T:1 info <general>: CVideoPlayer::CloseFile()
2026-11-08 17:01:00.000 T:1 info <general>: AddOnLog: pvr.iptvsimple: pvr.iptvsimple - GetChannelStreamProperties - Live Stream URL: https://jmp2.uk/plu-1.m3u8
2026-11-08 17:01:00.000 T:1 info <general>: VideoPlayer::OpenFile: pvr://channels/tv/x/1@pvr.iptvsimple_3.pvr
2026-11-08 17:01:23.000 T:2 info <general>: Opening stream: 7 source: 256
2026-11-08 17:02:00.000 T:1 info <general>: VideoPlayer::OpenFile: pvr://channels/tv/x/1@pvr.iptvsimple_4.pvr
2026-11-08 17:02:30.000 T:1 error <general>: OpenDemuxStream - Error creating demuxer
"""


def test_parse_log_sessions_hosts_and_counts():
    s = diagnose.parse_log(LOG)
    assert [x.host for x in s] == ["149.62.177.107:9999", "149.62.177.107:9999", "99.27.51.147:8080", "jmp2.uk", "?"]
    tfx, tf1, gulli, pluto, failed = s
    # zapping from full screen: the next OpenFile ends the session, no CloseFile in between
    assert (tfx.open_s, tfx.stalls, tfx.sync_errors, round(tfx.played_s)) == (1.105, 4, 1, 120)
    assert round(tf1.played_s) == 60
    assert gulli.stalls == 0 and round(gulli.played_s) == 1200
    assert pluto.open_s == 23.0 and failed.demux_error and failed.open_s is None


def test_findings_blame_the_source_when_another_server_plays_fine():
    st = diagnose.State(sessions=diagnose.parse_log(LOG), wifi={"rssi_dbm": "-34", "link_mbps": "650"},
                        mem_total_mb=1765, mem_available_mb=540, kodi_swap_mb=118,
                        top=[("org.xbmc.kodi", 48.0), ("com.google.android.katniss:interactor", 26.0)])
    found = {f.cause: f for f in diagnose.findings(st)}
    src = found["the source server delivers more slowly than the stream plays"]
    assert src.confidence == "high" and "149.62.177.107:9999" in src.evidence and "99.27.51.147" in src.evidence
    assert "slow channel start" in found and "jmp2.uk" in found["slow channel start"].evidence
    assert "streams that do not open" in found
    assert "katniss" in found["background CPU use"].evidence
    assert "memory pressure" not in found  # 540 MB available, 118 MB swapped: below the alarm
    text = diagnose.report(st)
    assert "SECRET" not in text and "/TFX/" not in text  # host only, never paths or tokens


def test_relay_urls_are_reported_by_source_host():
    relay = health.relay_module()
    url = relay.local_url("http://149.62.177.107:9999/TF1/index.m3u8?token=x")
    assert diagnose.host_of(url) == "149.62.177.107:9999 (relay)"


def test_parse_ping_and_top():
    mac = "20 packets transmitted, 20 packets received, 0.0% packet loss\nround-trip min/avg/max/stddev = 3.1/8.2/40.5/9.0 ms"
    tv = "10 packets transmitted, 10 received, 0% packet loss, time 2702ms\nrtt min/avg/max/mdev = 10.186/86.396/236.277/105.986 ms"
    assert diagnose.parse_ping(mac) == {"loss_pct": 0.0, "min_ms": 3.1, "avg_ms": 8.2, "max_ms": 40.5, "jitter_ms": 9.0}
    assert diagnose.parse_ping(tv)["jitter_ms"] == 105.986
    top = """Tasks: 1
  PID USER         PR  NI VIRT  RES  SHR S[%CPU] %MEM     TIME+ ARGS
Tasks: 302 total
  PID USER         PR  NI VIRT  RES  SHR S[%CPU] %MEM     TIME+ ARGS
 9381 u0_a113      10 -10 1.7G 203M  89M S 47.6  11.4  50:34.83 org.xbmc.kodi
 1546 u0_a58       20   0 1.8G  70M  44M S 26.0   3.9  41:24.11 com.google.android.katniss:interactor
20647 shell        20   0  17M 3.9M 2.9M R  1.6   0.2   0:00.10 top -b -n 2 -d 3 -m 14
"""
    assert diagnose.parse_top(top) == [("org.xbmc.kodi", 47.6), ("com.google.android.katniss:interactor", 26.0)]


def test_route_and_unroute_keep_kodi_identity(tmp_path):
    e = Entry("TFX", "http://149.62.177.107:9999/TFX/index.m3u8", {"tvg-chno": "8"},
              ["#EXTVLCOPT:http-user-agent=Mozilla/5.0 (X)"])
    book = health.HealthBook(tmp_path / "h.json")
    book.records[effective_url(e)] = {"verdict": "unstable", "variants": 1, "relay": {"verdict": "stable"}}
    (routed,), names = health.route([e], book)
    assert names == ["TFX"] and routed.url.startswith("http://127.0.0.1:52180/") and routed.url.endswith(".m3u8")
    assert routed.options == []  # the header now travels inside the relay URL
    back = health.unroute(routed)
    assert effective_url(back) == effective_url(e) and back.attrs == e.attrs
    # untouched: stable stream, never measured, or already relayed
    other = Entry("Gulli", "http://99.27.51.147:8080/g.m3u8", {})
    assert health.route([other, routed], book)[1] == []
    # round trip through M3U text
    again = parse_m3u(render_m3u([routed])).entries[0]
    assert health.unroute(again).url == e.url
