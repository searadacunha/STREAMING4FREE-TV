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
    # The add-on returns to the TV home when opened from the tile; an error screen never relaunches Kodi.
    assert 'new JSONArray().put("android")' in code
    assert "!intent.getBooleanExtra(SHOW_ERROR, false)" in code
    assert '!found.optBoolean("enabled")' in code


def test_logo_source_and_generator_exist():
    assert (ROOT / "assets/branding/IPTV4FREE-original.png").is_file()
    script = (ROOT / "scripts/prepare_android_launcher.py").read_text()
    assert "IPTV4FREE-original.png" in script
    assert "iptv4free_tv_banner.png" in script
    assert "iptv4free_launcher_icon.png" in script


def test_cover_hides_kodi_while_it_starts():
    manifest = (APP / "src/main/AndroidManifest.xml").read_text()
    code = (APP / "src/main/java/com/iptv4free/launcher/MainActivity.java").read_text()
    assert "android.permission.SYSTEM_ALERT_WINDOW" in manifest
    assert 'android:theme="@style/IPTV4FREE.Splash"' in manifest
    styles = (APP / "src/main/res/values/styles.xml").read_text()
    assert '"android:windowBackground">@drawable/iptv4free_splash<' in styles
    splash = (APP / "src/main/res/drawable/iptv4free_splash.xml").read_text()
    assert "@drawable/iptv4free_logo_original" in splash and "@android:color/black" in splash
    # Kodi starts only under the drawn cover; no access -> previous behaviour, never a dead tile.
    assert "TYPE_APPLICATION_OVERLAY" in code and "Settings.canDrawOverlays(this)" in code
    assert "if (!showCover(this::startKodi)) startKodi();" in code
    # The TV home key removes the cover at once; remote keys never reach Kodi's menus unseen.
    assert "Intent.ACTION_CLOSE_SYSTEM_DIALOGS" in code and '"homekey".equals(reason)' in code
    assert "public boolean dispatchKeyEvent(KeyEvent event)" in code


def test_cover_waits_for_the_addon_window_it_knows():
    """The launcher reads what the add-on sets: a renamed property would leave the cover up 15 s."""
    code = (APP / "src/main/java/com/iptv4free/launcher/MainActivity.java").read_text()
    addon = (ROOT / "kodi-addon/script.iptv4free/default.py").read_text()
    skin = (ROOT / "kodi-addon/script.iptv4free/resources/skins/Default/1080i/IPTV4FREE.xml").read_text()
    assert '"Window(Home).Property(iptv4free.window)"' in code
    assert 'HOME, RUNNING = xbmcgui.Window(10000), "iptv4free.window"' in addon
    assert "HOME.setProperty(RUNNING, str(self.wid))" in addon
    assert ".Property(Loading),true)" in code and 'self.setProperty("Loading", "true")' in addon
    # The add-on's loading view draws the same logo at the same place as the launcher's splash.
    assert "<left>420</left><top>120</top><width>1080</width><height>720</height>" in skin
    splash = (APP / "src/main/res/drawable/iptv4free_splash.xml").read_text()
    assert 'android:top="60dp"' in splash and 'android:width="540dp"' in splash


def test_splash_uses_the_original_logo_bytes(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("prep", ROOT / "scripts/prepare_android_launcher.py")
    prep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prep)
    monkeypatch.setattr(prep, "OUT", tmp_path)
    prep.main()
    original = (ROOT / "assets/branding/IPTV4FREE-original.png").read_bytes()
    assert (tmp_path / "iptv4free_logo_original.png").read_bytes() == original
