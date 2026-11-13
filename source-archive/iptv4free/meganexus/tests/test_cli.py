import pytest

from iptv4free import kodi
from iptv4free.adb import Adb
from iptv4free.cli import main
from iptv4free.config import ConfigError, load_config
from iptv4free.playlists import parse_m3u


@pytest.fixture
def setup_env(http_server, make_config, fake_tv, tmp_path):
    root, adb_path = fake_tv
    lineups = (
        f'[[lineup]]\nid = "fr"\nname = "France"\nsources = ["{http_server}/fr.m3u"]\n'
        f'epg = "{http_server}/epg.xml.gz"\nfavorites = ["Beta News", "Alpha"]\nfirst_number = 1\n'
        f'[[lineup]]\nid = "world"\nname = "World"\nsources = ["{http_server}/world.m3u"]\n'
        'first_number = 100\nby_category = true\nexclude_categories = ["Shop"]\n'
    )
    cfg = make_config(lineups, tv={"adb": f'"{adb_path}"', "forward_port": "9"},
                      scan={"timeout": "2", "workers": "4"}, safety={"max_changes": "3"})
    return str(cfg), root, tmp_path


def run(cfg, *args):
    return main(["--config", cfg, *args])


def test_full_cycle(setup_env, capsys):
    cfg, root, tmp_path = setup_env
    assert run(cfg, "build") == 1
    assert "run `iptv4free scan` first" in capsys.readouterr().err

    assert run(cfg, "scan") == 0
    assert "Scanned 8 streams" in capsys.readouterr().out

    assert run(cfg, "build") == 0
    fr = parse_m3u((tmp_path / "out" / "fr.m3u").read_text()).entries
    assert [(e.name, e.attrs["tvg-chno"], e.attrs.get("tvg-id", "")) for e in fr] == [
        ("Beta News", "1", "BetaNews.xx"), ("Alpha", "2", "Alpha.xx"), ("Special UA", "3", "")]
    assert fr[1].url.endswith("/direct.ts?hd")                   # best resolution kept
    assert fr[2].options == ["#EXTVLCOPT:http-user-agent=Special/1.0"]
    world = parse_m3u((tmp_path / "out" / "world.m3u").read_text()).entries
    # Alpha already belongs to France (even its 720p variant); Shop excluded
    assert [(e.name, e.attrs["group-title"]) for e in world] == [
        ("Gamma TV", "World · Sports"), ("Mystery", "World · Other")]

    assert run(cfg, "deploy") == 3                                 # 5 new channels > max_changes 3
    assert "first deployment" in capsys.readouterr().out
    assert run(cfg, "deploy", "--allow-large-update", "--restart", "never") == 0
    assert (root / "sdcard/Download/iptv4free/fr.m3u").exists()

    assert run(cfg, "doctor") == 0
    out = capsys.readouterr().out
    assert "[ OK ] Kodi 21.3 installed" in out and "up to date" in out
    assert "[WARN] Kodi is not running" in out

    assert run(cfg, "update", "--dry-run") == 0
    assert "TV already up to date." in capsys.readouterr().out

    assert run(cfg, "rollback") == 1                               # nothing deployed over yet
    assert run(cfg, "rollback", "--list") == 0


def test_setup_without_kodi_prints_instructions(setup_env, capsys):
    cfg, root, _ = setup_env
    (root / "no-kodi").touch()
    assert run(cfg, "setup") == 0
    out = capsys.readouterr().out
    assert "Kodi is not installed" in out and "IPTV Simple Client" in out
    assert run(cfg, "doctor") == 1
    assert "[FAIL] Kodi (org.xbmc.kodi) is not installed" in capsys.readouterr().out


def test_install_kodi_verifies_and_installs(setup_env, monkeypatch, tmp_path):
    cfg, root, _ = setup_env
    (root / "no-kodi").touch()
    apk = tmp_path / "kodi.apk"
    apk.write_bytes(b"apk")
    seen = {}
    monkeypatch.setattr(kodi, "find_apk", lambda abi, version: seen.setdefault("abi", abi) and "u")
    monkeypatch.setattr(kodi, "download_apk", lambda url, dest: apk)
    config = load_config(cfg)
    assert kodi.install_kodi(Adb(config.adb, config.tv_address), config) == "21.3"
    assert seen["abi"] == "armeabi-v7a"
    assert f"install -r {apk}" in (root / "commands.log").read_text()


def test_tv_unreachable_is_a_clean_error(setup_env, capsys):
    cfg, root, _ = setup_env
    (root / "offline").touch()
    assert run(cfg, "setup") == 1
    assert "not ready" in capsys.readouterr().err


def test_missing_config_hint(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("IPTV4FREE_CONFIG", raising=False)
    assert main(["--config", str(tmp_path / "nope.toml"), "doctor"]) == 1
    assert "cp config/example.toml" in capsys.readouterr().err


@pytest.mark.parametrize("body, message", [
    ("[tv\n", "Expected"),
    ("", "at least one"),
    ('[[lineup]]\nid = "Bad Id"\nsources = ["x"]\n', "lowercase"),
    ('[[lineup]]\nid = "a"\nsources = []\n', "no sources"),
    ('[[lineup]]\nid = "a"\nsources = ["x"]\n[[lineup]]\nid = "a"\nsources = ["y"]\n', "duplicate"),
    ('[safety]\nrestart_kodi = "maybe"\n[[lineup]]\nid = "a"\nsources = ["x"]\n', "restart_kodi"),
    ('[scan]\nworkers = "many"\n[[lineup]]\nid = "a"\nsources = ["x"]\n', "type int"),
])
def test_config_validation(tmp_path, body, message):
    p = tmp_path / "c.toml"
    p.write_text(body)
    with pytest.raises(ConfigError, match=message):
        load_config(p)


def test_env_overrides_tv_address(tmp_path, monkeypatch):
    p = tmp_path / "c.toml"
    p.write_text('[tv]\naddress = "192.0.2.10:5555"\n[[lineup]]\nid = "a"\nsources = ["x"]\n')
    monkeypatch.setenv("IPTV4FREE_TV", "192.0.2.99:5555")
    assert load_config(p).tv_address == "192.0.2.99:5555"


def test_example_config_is_valid():
    from pathlib import Path
    config = load_config(Path(__file__).parent.parent / "config" / "example.toml")
    assert [lu.id for lu in config.lineups] == ["france", "portugal", "world"]
