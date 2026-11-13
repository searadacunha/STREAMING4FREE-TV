from iptv4free.playlists import (Entry, effective_url, kodi_identity, parse_m3u, render_m3u,
                                 request_parts, stream_properties)


def test_parse_basic_and_quoted_commas():
    text = (
        "#EXTM3U\n"
        '#EXTINF:-1 tvg-id="A.fr" http-user-agent="Mozilla/5.0 (X11; Linux, like Gecko)" '
        'group-title="News;Business",Channel A, the first (1080p)\n'
        "#EXTVLCOPT:http-user-agent=Mozilla/5.0 (X11)\n"
        "https://example.com/a.m3u8\n"
    )
    r = parse_m3u(text)
    assert not r.skipped
    [e] = r.entries
    assert e.name == "Channel A, the first (1080p)"
    assert e.attrs["tvg-id"] == "A.fr"
    assert e.attrs["group-title"] == "News;Business"
    assert e.options == ["#EXTVLCOPT:http-user-agent=Mozilla/5.0 (X11)"]
    assert e.url == "https://example.com/a.m3u8"


def test_parse_malformed_playlist_is_reported_not_fatal():
    text = (
        "﻿#EXTINF:-1 tvg-id=\"x\",No URL\r\n"          # EXTINF without URL
        "#EXTINF:-1 tvg-id=\"x,Broken quote\r\n"           # unterminated quote
        "http://example.com/orphan.ts\r\n"                 # URL without EXTINF
        "#EXTINF:-1 tvg-name=\"From tvg-name\",\r\n"        # empty name, falls back
        "http://example.com/ok.ts\r\n"
        "#EXTINF:-1,Not a url\r\n"
        "just text\r\n"
        "#EXTINF:-1 TVG-ID=Upper group-title=Plain,Unquoted attrs\r\n"
        "#EXTGRP:Ignored because group-title is set\r\n"
        "rtmp://example.com/live\r\n"
        "#EXTINF:-1,Last without url\r\n"
    )
    r = parse_m3u(text)
    assert [e.name for e in r.entries] == ["From tvg-name", "Unquoted attrs"]
    assert r.entries[1].attrs == {"tvg-id": "Upper", "group-title": "Plain"}
    reasons = [reason for _, reason in r.skipped]
    assert "EXTINF without URL" in reasons
    assert any(x.startswith("bad EXTINF") for x in reasons)
    assert "URL without EXTINF" in reasons
    assert any(x.startswith("not a URL") for x in reasons)
    assert reasons.count("EXTINF without URL") == 2


def test_extgrp_sets_group_when_missing():
    r = parse_m3u("#EXTINF:-1,A\n#EXTGRP:Sports\nhttp://x/a\n")
    assert r.entries[0].attrs["group-title"] == "Sports"


def test_render_is_deterministic_and_round_trips():
    e = Entry("Name  with  spaces", "http://x/a",
              {"group-title": 'G "q"', "tvg-logo": "", "zz": "1", "tvg-id": "I"},
              ["#EXTVLCOPT:http-referrer=http://r/"])
    text = render_m3u([e])
    assert text == ('#EXTM3U\n#EXTINF:-1 tvg-id="I" group-title="G \'q\'" zz="1",Name with spaces\n'
                    "#EXTVLCOPT:http-referrer=http://r/\nhttp://x/a\n")
    again = parse_m3u(text).entries[0]
    assert (again.name, again.url, again.options) == ("Name with spaces", "http://x/a", e.options)


def test_extvlcopt_values_stop_at_first_space_like_iptv_simple():
    e = Entry("A", "http://x/a", options=[
        "#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0)",
        "#EXTVLCOPT:network-caching=1000",  # not accepted by IPTV Simple
        "#KODIPROP:inputstream=inputstream.adaptive",
    ])
    assert stream_properties(e) == {"http-user-agent": "Mozilla/5.0",
                                    "inputstream": "inputstream.adaptive"}
    assert effective_url(e) == "http://x/a|user-agent=Mozilla/5.0"


def test_kodiprop_keeps_whole_value_and_referrer_appended():
    e = Entry("A", "https://x/a", options=[
        "#KODIPROP:http-user-agent=Agent 1.0", "#EXTVLCOPT:http-referrer=https://ref/"])
    assert effective_url(e) == "https://x/a|user-agent=Agent 1.0&referer=https://ref/"
    assert request_parts(e) == ("https://x/a", {"User-Agent": "Agent 1.0",
                                                "Referer": "https://ref/"})


def test_existing_pipe_options_are_not_duplicated():
    e = Entry("A", "http://x/a|user-agent=Mine", options=["#EXTVLCOPT:http-user-agent=Other"])
    assert effective_url(e) == "http://x/a|user-agent=Mine"
    assert request_parts(e)[1] == {"User-Agent": "Mine"}


def test_identity_changes_with_name_url_or_header_but_not_logo():
    base = Entry("A", "http://x/a", {"tvg-logo": "1"})
    assert kodi_identity(base) == kodi_identity(Entry("A", "http://x/a", {"tvg-logo": "2"}))
    assert kodi_identity(base) != kodi_identity(Entry("B", "http://x/a"))
    assert kodi_identity(base) != kodi_identity(Entry("A", "http://x/b"))
    assert kodi_identity(base) != kodi_identity(
        Entry("A", "http://x/a", options=["#EXTVLCOPT:http-user-agent=UA"]))


def test_non_http_urls_get_no_headers():
    e = Entry("A", "rtmp://x/a", options=["#EXTVLCOPT:http-user-agent=UA"])
    assert effective_url(e) == "rtmp://x/a"


def test_fetch_text_accepts_local_files(tmp_path):
    from iptv4free.playlists import fetch_text
    f = tmp_path / "mine.m3u"
    f.write_text("#EXTM3U\n#EXTINF:-1,Local\nhttp://x/a\n")
    assert parse_m3u(fetch_text(f.as_uri(), 5, "test")).entries[0].name == "Local"
