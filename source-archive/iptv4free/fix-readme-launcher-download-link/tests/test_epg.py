import gzip
import hashlib
import os
import time

from conftest import EPG_XML

from iptv4free import epg


def test_parse_channels_plain_and_gzip():
    for data in (EPG_XML, gzip.compress(EPG_XML)):
        index = epg.parse_channels(data)
        assert len(index) == 3
        assert index.ids["betanews.xx"] == "BetaNews.xx"
        assert index.names[epg.match_key("Gamma TV")] == "Gamma.xx"


def test_match_order_alias_then_id_then_name():
    index = epg.parse_channels(EPG_XML)
    assert epg.match("Whatever", "Alpha.xx@SD", {}, index) == "Alpha.xx"
    assert epg.match("Beta News (1080p)", "", {}, index) == "BetaNews.xx"
    assert epg.match("Alpha", "Alpha.xx", {"alpha": "Forced.xx"}, index) == "Forced.xx"
    assert epg.match("Nobody", "Nobody.xx", {}, index) is None


def _cache_file(cache_dir, url):
    return cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".xmltv")


def test_load_index_downloads_and_caches(http_server, tmp_path):
    url = f"{http_server}/epg.xml.gz"
    index = epg.load_index(url, tmp_path, 12, 5, "test")
    assert index is not None and len(index) == 3
    assert _cache_file(tmp_path, url).exists()


def test_load_index_falls_back_to_stale_cache_when_download_fails(tmp_path):
    url = "http://127.0.0.1:9/unreachable.xml.gz"
    cached = _cache_file(tmp_path, url)
    cached.write_bytes(gzip.compress(EPG_XML))
    os.utime(cached, (time.time() - 48 * 3600,) * 2)
    index = epg.load_index(url, tmp_path, 12, 2, "test")
    assert index is not None and len(index) == 3


def test_load_index_without_cache_or_with_corrupt_cache_returns_none(tmp_path):
    assert epg.load_index("http://127.0.0.1:9/x.xml", tmp_path, 12, 2, "test") is None
    url = "http://127.0.0.1:9/corrupt.xml"
    _cache_file(tmp_path, url).write_bytes(b"<tv><chan")  # fresh but unreadable
    assert epg.load_index(url, tmp_path, 12, 2, "test") is None
