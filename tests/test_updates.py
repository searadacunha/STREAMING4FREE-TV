import json

import pytest

from iptv4free.playlists import Entry
from iptv4free.updates import NumberBook, ScanHistory, atomic_write, changeset


def test_atomic_write_replaces_and_leaves_no_temp(tmp_path):
    target = tmp_path / "sub" / "f.txt"
    atomic_write(target, "one")
    atomic_write(target, b"two")
    assert target.read_text() == "two"
    assert [p.name for p in target.parent.iterdir()] == ["f.txt"]


def test_atomic_write_keeps_old_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "f.txt"
    target.write_text("old")

    def boom(*a):
        raise OSError("disk full")
    monkeypatch.setattr("iptv4free.updates.os.replace", boom)
    with pytest.raises(OSError):
        atomic_write(target, "new")
    assert target.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["f.txt"]


def test_scan_history_hysteresis(tmp_path):
    h = ScanHistory(tmp_path / "h.json")
    assert not h.alive("u", 3)                    # never seen
    h.record("never-ok", False, "404")
    assert not h.alive("never-ok", 3)             # never worked: not added
    h.record("u", True, "ok")
    for i in range(2):
        h.record("u", False, "timeout")
        assert h.alive("u", 3)                    # one or two failures keep it
    h.record("u", False, "timeout")
    assert not h.alive("u", 3)                    # third failure in a row removes it
    h.record("u", True, "ok")
    assert h.alive("u", 3)
    h.save()
    again = ScanHistory(tmp_path / "h.json")
    assert again.alive("u", 3) and json.loads((tmp_path / "h.json").read_text())["u"]["fail_streak"] == 0


def test_number_book_stable_and_persisted(tmp_path):
    b = NumberBook(tmp_path / "n.json")
    assert b.assign("fr", "a", 10) == 10
    assert b.assign("fr", "b", 10) == 11
    assert b.assign("fr", "a", 10) == 10
    assert b.assign("pt", "a", 500) == 500
    b.save()
    assert NumberBook(tmp_path / "n.json").assign("fr", "c", 10) == 12


def test_changeset_counts_what_kodi_rewrites():
    old = [Entry("A", "http://a"), Entry("B", "http://b"), Entry("C", "http://c")]
    new = [Entry("A", "http://a", {"tvg-logo": "changed"}),  # same identity
           Entry("B renamed", "http://b"),                    # rename = remove + add
           Entry("D", "http://d")]
    c = changeset(old, new)
    assert (len(c.added), len(c.removed), c.kept, c.size) == (2, 2, 1, 4)
    assert c.old_count == 3 and c.new_count == 3
    assert changeset([], new).size == 3
