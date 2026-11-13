import pytest

from iptv4free import kodi
from iptv4free.config import load_config

LISTING = """
<a href="kodi-21.2-Omega-armeabi-v7a.apk">x</a>
<a href="kodi-21.3-Omega-armeabi-v7a.apk">x</a>
<a href="kodi-21.3-Omega-armeabi-v7a.apk.sha256">x</a>
<a href="kodi-20.5-Nexus-armeabi-v7a.apk">x</a>
<a href="kodi-21.10-Omega-armeabi-v7a.apk">x</a>
"""


def test_rpc_skips_notifications(fake_kodi):
    rpc = kodi.KodiRpc("127.0.0.1", fake_kodi.port, timeout=5)
    assert rpc.call("JSONRPC.Ping") == "pong"
    assert rpc.call("PVR.GetChannels")["limits"]["total"] == 4


def test_find_apk_picks_latest_or_requested_version():
    base = "https://mirrors.kodi.tv/releases/android/arm/"
    assert kodi.find_apk("armeabi-v7a", listing=LISTING) == base + "kodi-21.10-Omega-armeabi-v7a.apk"
    assert kodi.find_apk("armeabi-v7a", "20.5", LISTING) == base + "kodi-20.5-Nexus-armeabi-v7a.apk"
    with pytest.raises(kodi.KodiError, match="not found"):
        kodi.find_apk("armeabi-v7a", "19.0", LISTING)
    with pytest.raises(kodi.KodiError, match="no official Kodi build"):
        kodi.find_apk("mips")
    with pytest.raises(kodi.KodiError, match="no Kodi APK"):
        kodi.find_apk("arm64-v8a", listing="<html></html>")


def test_instructions_list_every_lineup(make_config):
    config = load_config(make_config(
        '[[lineup]]\nid = "fr"\nname = "France"\nsources = ["http://x"]\nepg = "http://e/g.xml"\n'
        '[[lineup]]\nid = "w"\nsources = ["http://y"]\n'))
    text = kodi.instructions(config)
    assert "M3U playlist URL: /storage/emulated/0/Download/iptv4free/fr.m3u" in text
    assert "XMLTV URL: http://e/g.xml" in text
    assert "Name: W" in text and text.count("M3U playlist URL") == 2
