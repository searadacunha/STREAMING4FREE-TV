import pytest

from iptv4free import deploy, kodi
from iptv4free.adb import Adb, AdbError
from iptv4free.config import load_config
from iptv4free.playlists import Entry, render_m3u

LINEUP = '[[lineup]]\nid = "fr"\nname = "France"\nsources = ["http://x/fr.m3u"]\n'
REMOTE = "sdcard/Download/iptv4free/fr.m3u"


def playlist(path, names):
    entries = [Entry(n, f"http://s/{n}", {"tvg-chno": str(i)}) for i, n in enumerate(names, 1)]
    path.write_text(render_m3u(entries))
    return path


@pytest.fixture
def env(tmp_path, make_config, fake_tv, fake_kodi):
    root, adb_path = fake_tv
    cfg_path = make_config(LINEUP, tv={"adb": f'"{adb_path}"', "forward_port": str(fake_kodi.port)},
                           safety={"max_changes": "4", "backups": "2"})
    config = load_config(cfg_path)
    adb = Adb(config.adb, config.tv_address, 10)
    lines = []
    return config, adb, root, lines.append, lines, fake_kodi


def test_first_deploy_needs_override_then_uploads_atomically(env, tmp_path):
    config, adb, root, out, lines, k = env
    built = playlist(tmp_path / "fr.m3u", list("ABCDEF"))
    assert deploy.apply(config, adb, {"fr": built}, out=out) == deploy.EXIT_REFUSED
    assert not (root / REMOTE).exists()
    assert any("first deployment" in x for x in lines)

    assert deploy.apply(config, adb, {"fr": built}, dry_run=True, allow_large=True, out=out) == 0
    assert not (root / REMOTE).exists()

    assert deploy.apply(config, adb, {"fr": built}, allow_large=True, restart_policy="never",
                        out=out) == 0
    assert (root / REMOTE).read_bytes() == built.read_bytes()
    log = (root / "commands.log").read_text()
    assert f"push {built} /{REMOTE}.uploading" in log and f"mv -f /{REMOTE}.uploading /{REMOTE}" in log
    assert not (root / (REMOTE + ".uploading")).exists()
    assert k.calls == []  # policy never: Kodi untouched


def test_unchanged_small_change_backup_rollback_and_pruning(env, tmp_path):
    config, adb, root, out, lines, k = env
    v1 = playlist(tmp_path / "v1.m3u", list("ABCDEF"))
    deploy.apply(config, adb, {"fr": v1}, allow_large=True, restart_policy="never", out=out)

    lines.clear()
    assert deploy.apply(config, adb, {"fr": v1}, restart_policy="never", out=out) == 0
    assert "TV already up to date." in lines

    v2 = playlist(tmp_path / "v2.m3u", list("ABCDEG"))  # F -> G: 2 changes, under the limit
    assert deploy.apply(config, adb, {"fr": v2}, restart_policy="never", out=out) == 0
    assert (root / REMOTE).read_bytes() == v2.read_bytes()
    [b1] = deploy.backups(config)
    assert (b1 / "fr.m3u").read_bytes() == v1.read_bytes()

    assert deploy.rollback(config, adb, restart_policy="never", out=out) == 0
    assert (root / REMOTE).read_bytes() == v1.read_bytes()

    v3 = playlist(tmp_path / "v3.m3u", list("ABCDEH"))
    deploy.apply(config, adb, {"fr": v3}, restart_policy="never", out=out)
    assert len(deploy.backups(config)) == 2  # pruned to safety.backups


def test_large_change_and_shrink_are_refused(env, tmp_path):
    config, adb, root, out, lines, k = env
    v1 = playlist(tmp_path / "v1.m3u", list("ABCDEFGH"))
    deploy.apply(config, adb, {"fr": v1}, allow_large=True, restart_policy="never", out=out)

    renamed = playlist(tmp_path / "r.m3u", [x.lower() for x in "ABCDEFGH"])  # 16 changes
    lines.clear()
    assert deploy.apply(config, adb, {"fr": renamed}, out=out) == deploy.EXIT_REFUSED
    assert any("exceed safety.max_changes" in x for x in lines)

    shrunk = playlist(tmp_path / "s.m3u", list("AB"))  # 6 removals > 4 and below 50 %
    lines.clear()
    assert deploy.apply(config, adb, {"fr": shrunk}, out=out) == deploy.EXIT_REFUSED
    assert any("min_keep_ratio" in x for x in lines)
    assert (root / REMOTE).read_bytes() == v1.read_bytes()


def test_invalid_build_is_refused_even_with_override(env, tmp_path):
    config, adb, root, out, lines, k = env
    bad = tmp_path / "bad.m3u"
    bad.write_text("#EXTM3U\n")
    assert deploy.apply(config, adb, {"fr": bad}, allow_large=True, out=out) == deploy.EXIT_REFUSED
    assert any("lineup is empty" in x for x in lines)


def test_corrupted_upload_leaves_tv_file_untouched(env, tmp_path):
    config, adb, root, out, lines, k = env
    v1 = playlist(tmp_path / "v1.m3u", list("ABC"))
    deploy.apply(config, adb, {"fr": v1}, allow_large=True, restart_policy="never", out=out)
    (root / "corrupt").touch()
    v2 = playlist(tmp_path / "v2.m3u", list("ABD"))
    with pytest.raises(deploy.DeployError, match="checksum mismatch"):
        deploy.apply(config, adb, {"fr": v2}, restart_policy="never", out=out)
    assert (root / REMOTE).read_bytes() == v1.read_bytes()
    assert not (root / (REMOTE + ".uploading")).exists()


def test_adb_offline_and_frozen_tv_fail_cleanly(env, tmp_path):
    config, adb, root, out, lines, k = env
    built = playlist(tmp_path / "fr.m3u", list("AB"))
    (root / "offline").touch()
    with pytest.raises(AdbError, match="not ready"):
        deploy.apply(config, adb, {"fr": built}, out=out)
    (root / "offline").unlink()
    (root / "hang").touch()
    slow = Adb(config.adb, config.tv_address, timeout=1)
    with pytest.raises(AdbError, match="timed out"):
        slow.connect()


def test_missing_adb_binary():
    with pytest.raises(AdbError, match="adb not found"):
        Adb("/nonexistent/adb", "192.0.2.10:5555").connect()
    with pytest.raises(AdbError, match="no TV address"):
        Adb("adb", "")


def test_restart_policies(env):
    config, adb, root, out, lines, k = env
    assert "policy: never" in kodi.restart(adb, config, "never")
    assert k.calls == []
    k.playing = True
    assert "playing" in kodi.restart(adb, config, "auto")
    assert "Application.Quit" not in k.calls
    k.playing = False
    assert kodi.restart(adb, config, "auto") == "Kodi restarted"
    assert "Application.Quit" in k.calls
    log = (root / "commands.log").read_text()
    assert "am force-stop org.xbmc.kodi" in log and "monkey -p org.xbmc.kodi 1" in log


def test_restart_auto_when_kodi_not_running(tmp_path, make_config, fake_tv):
    root, adb_path = fake_tv
    config = load_config(make_config(LINEUP, tv={"adb": f'"{adb_path}"', "forward_port": "9"}))
    adb = Adb(config.adb, config.tv_address, 10)
    assert "not running" in kodi.restart(adb, config, "auto")
    assert "monkey" not in (root / "commands.log").read_text()
