"""Android TV launcher static contract; no Android SDK or device required."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "android-tv-launcher/app"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def test_leanback_launcher_is_separate_from_kodi():
    manifest = ET.parse(APP / "src/main/AndroidManifest.xml").getroot()
    filters = manifest.findall("./application/activity/intent-filter")
    assert any(any(c.get(ANDROID + "name") == "android.intent.category.LEANBACK_LAUNCHER"
                   for c in f.findall("category")) for f in filters)
    assert manifest.find("./application").get(ANDROID + "label") == "@string/app_name"
    assert manifest.find("./application").get(ANDROID + "banner") == "@drawable/iptv4free_tv_banner"
    assert manifest.find("./application").get(ANDROID + "icon") == "@drawable/iptv4free_launcher_icon"
    assert "org.xbmc.kodi" in (APP / "src/main/java/com/iptv4free/launcher/MainActivity.java").read_text()


def test_launcher_executes_existing_addon_only():
    code = (APP / "src/main/java/com/iptv4free/launcher/MainActivity.java").read_text()
    gradle = (APP / "build.gradle").read_text()
    assert "com.iptv4free.launcher" in gradle
    assert '"Addons.ExecuteAddon"' in code
    assert '"script.iptv4free"' in code
    assert '"127.0.0.1"' in code
    assert "getLeanbackLaunchIntentForPackage" in code
    assert "force-stop" not in code and "setComponentEnabledSetting" not in code


def test_logo_source_and_generator_exist():
    assert (ROOT / "assets/branding/IPTV4FREE-original.png").is_file()
    script = (ROOT / "scripts/prepare_android_launcher.py").read_text()
    assert "IPTV4FREE-original.png" in script
    assert "iptv4free_tv_banner.png" in script
    assert "iptv4free_launcher_icon.png" in script
