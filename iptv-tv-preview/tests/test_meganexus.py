import hashlib
import json

import pytest
from conftest import Handler

from iptv4free import meganexus
from iptv4free.adb import Adb
from iptv4free.cli import main
from iptv4free.config import load_config
from iptv4free.kodi import KodiRpc

ZIP = b"PK official repository zip"
USERDATA = "sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata"
SKIN = '<settings version="2">\n    <setting id="lookandfeel.skin" default="true">{}</setting>\n</settings>\n'
INSTALLED = {"plugin.video.meganexus": "9.0.9", "script.meganexus": "9.0.9", "skin.meganexus": "9.0.9"}


@pytest.fixture
def release(http_server, monkeypatch):
    def publish(data=ZIP, digest="sha256:" + hashlib.sha256(ZIP).hexdigest()):
        Handler.routes["/repository.meganexus-2.0.0.zip"] = (200, data, None)   # what Kodi gets
        Handler.routes["/release.json"] = (200, json.dumps({"tag_name": "v9.1.0", "assets": [
            {"name": "MegaNexus-Complete-9.1.0.zip", "digest": "sha256:" + "0" * 64},
            {"name": "repository.meganexus-2.0.0.zip", "digest": digest},
        ]}).encode(), None)
    monkeypatch.setattr(meganexus, "RELEASE_API", f"{http_server}/release.json")
    monkeypatch.setattr(meganexus, "SOURCE", f"{http_server}/")
    publish()
    return publish


@pytest.fixture
def env(make_config, fake_tv, fake_kodi):
    root, adb_path = fake_tv
    ud = root / USERDATA
    for path, content in {"guisettings.xml": SKIN.format("skin.estuary"),
                          "Thumbnails/0/poster.jpg": "jpg", "Database/TV46.db": "db",
                          "addon_data/pvr.iptvsimple/instance-settings-1.xml": "<settings/>"}.items():
        (ud / path).parent.mkdir(parents=True, exist_ok=True)
        (ud / path).write_text(content)
    (root / "sdcard/Download/iptv4free").mkdir(parents=True)
    (root / "sdcard/Download/iptv4free/fr.m3u").write_text("#EXTM3U\n")
    cfg = make_config('[[lineup]]\nid = "fr"\nsources = ["http://x"]\n'
                      '[[lineup]]\nid = "pt"\nsources = ["http://y"]\n',
                      tv={"adb": f'"{adb_path}"', "forward_port": str(fake_kodi.port)})
    config = load_config(cfg)
    lines: list[str] = []
    return config, Adb(config.adb, config.tv_address, 10), root, lines, fake_kodi, str(cfg)


def test_repository_zip_must_match_github_digest(release, tmp_path):
    assert meganexus.fetch_repository_zip(tmp_path / "a").read_bytes() == ZIP
    release(data=b"tampered")
    with pytest.raises(meganexus.MegaNexusError, match="checksum mismatch"):
        meganexus.fetch_repository_zip(tmp_path / "b")
    assert not (tmp_path / "b" / "repository.meganexus-2.0.0.zip").exists()
    release(digest="")
    with pytest.raises(meganexus.MegaNexusError, match="no SHA-256"):
        meganexus.fetch_repository_zip(tmp_path / "c")


def test_setup_backs_up_kodi_then_stages_the_zip(env, release):
    config, adb, root, lines, k, _ = env
    assert meganexus.setup(config, adb, out=lines.append) == 0
    b = meganexus.backups(config)[-1]
    assert (b / "userdata/guisettings.xml").read_text() == SKIN.format("skin.estuary")
    assert (b / "userdata/Database/TV46.db").exists() and (b / "playlists/fr.m3u").exists()
    assert not (b / "userdata/Thumbnails").exists() and not (b / "playlists/pt.m3u").exists()
    assert len((b / "SHA256SUMS").read_text().splitlines()) == 4
    out = "\n".join(lines)
    assert "repository.meganexus-2.0.0.zip: SHA-256 matches the latest GitHub release" in out
    assert "Install from zip file > MegaNexus > repository.meganexus-2.0.0.zip" in out

    (root / "no-kodi").touch()
    assert meganexus.setup(config, adb, out=lines.append) == meganexus.EXIT_REFUSED
    assert "needs Kodi 21 or 22" in lines[-1]


def test_doctor_reports_meganexus_and_iptv(env, release):
    config, adb, root, lines, k, _ = env
    k.addons = {a: {"version": v, "enabled": True} for a, v in INSTALLED.items()}
    k.settings["lookandfeel.skin"] = "skin.meganexus"
    assert meganexus.doctor(config, adb, out=lines.append) == 0
    out = "\n".join(lines)
    assert "[ OK ] TV 192.0.2.10:5555: armeabi-v7a, MegaNexus native build android-armv7" in out
    assert "[WARN] RAM 1.8 GB, 654 MB available" in out
    assert "[ OK ] plugin.video.meganexus 9.0.9 enabled" in out
    assert "[WARN] MegaNexus 9.0.9 installed, 9.1.0 released" in out
    assert "[ OK ] Kodi skin: skin.meganexus" in out
    assert "[ OK ] IPTV Simple Client: 4 TV channels in Kodi" in out
    assert "[ OK ] Kodi uses 170 MB of RAM" in out


def test_rollback_restores_settings_and_turns_meganexus_off(env, release, capsys):
    config, adb, root, lines, k, cfg = env
    assert meganexus.setup(config, adb, out=lines.append) == 0
    gui = root / USERDATA / "guisettings.xml"
    gui.write_text(SKIN.format("skin.meganexus"))                       # what the install changes
    k.addons = {a: {"version": v, "enabled": True} for a, v in INSTALLED.items()}

    assert meganexus.rollback(config, adb, dry_run=True, out=lines.append) == 0
    assert "1 settings file(s) to restore" in "\n".join(lines) and "skin.meganexus" in gui.read_text()

    k.playing = True                                                   # never interrupt playback
    assert meganexus.rollback(config, adb, out=lines.append) == meganexus.EXIT_REFUSED
    assert "skin.meganexus" in gui.read_text() and "Application.Quit" not in k.calls

    k.playing = False
    assert meganexus.rollback(config, adb, out=lines.append, wait=10) == 0
    assert gui.read_text() == SKIN.format("skin.estuary")
    assert "Application.Quit" in k.calls
    assert not any(a["enabled"] for a in k.addons.values())
    assert not (root / "sdcard/Download/iptv4free/meganexus/.restore").exists()

    k.settings["lookandfeel.skin"] = "skin.meganexus"                  # Kodi kept another skin
    assert meganexus.rollback(config, adb, out=lines.append, wait=10) == 1

    assert main(["--config", cfg, "meganexus", "rollback", "--list"]) == 0
    assert capsys.readouterr().out.strip() == meganexus.backups(config)[-1].name


def test_rollback_without_backup(env):
    config, adb, root, lines, k, _ = env
    assert meganexus.rollback(config, adb, out=lines.append) == 1
    assert "No MegaNexus backup" in lines[-1]


def test_rollback_of_a_frozen_kodi_needs_force(env, release, monkeypatch):
    config, adb, root, lines, k, _ = env
    assert meganexus.setup(config, adb, out=lines.append) == 0
    gui = root / USERDATA / "guisettings.xml"
    gui.write_text(SKIN.format("skin.meganexus"))
    k.addons = {a: {"version": v, "enabled": True} for a, v in INSTALLED.items()}
    k.hang = {"Player.GetActivePlayers"}                     # answers the ping, nothing else
    monkeypatch.setattr(meganexus, "connect_rpc", lambda adb, config: (
        adb.forward(config.forward_port, config.jsonrpc_port),
        KodiRpc("127.0.0.1", config.forward_port, timeout=0.5))[1])
    assert meganexus.rollback(config, adb, out=lines.append) == meganexus.EXIT_REFUSED
    assert "--force" in lines[-1] and "skin.meganexus" in gui.read_text()

    assert meganexus.rollback(config, adb, force=True, out=lines.append, wait=10) == 0
    assert any("will be stopped (--force)" in x for x in lines)
    assert gui.read_text() == SKIN.format("skin.estuary")
    assert not any(a["enabled"] for a in k.addons.values())


def test_running_kodi_that_ignores_the_ping_is_never_killed_without_force(env, release, monkeypatch):
    config, adb, root, lines, k, _ = env
    assert meganexus.setup(config, adb, out=lines.append) == 0
    (root / USERDATA / "guisettings.xml").write_text(SKIN.format("skin.meganexus"))
    (root / "kodi-pid").touch()
    monkeypatch.setattr(meganexus, "connect_rpc", lambda adb, config: None)
    assert meganexus.rollback(config, adb, out=lines.append) == meganexus.EXIT_REFUSED
    assert "skin.meganexus" in (root / USERDATA / "guisettings.xml").read_text()
    assert meganexus.doctor(config, adb, out=lines.append) == 1
    assert "[FAIL] Kodi runs but does not answer" in lines[-1]
