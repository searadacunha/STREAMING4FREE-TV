import random

from iptv4free import epg
from iptv4free.channels import build_lineup, clean_name, resolution, validate
from iptv4free.config import Config, Lineup
from iptv4free.playlists import Entry
from iptv4free.updates import NumberBook


def cfg(*lineups):
    return Config(path=None, lineups=tuple(lineups))


def e(name, url, gid="", cat="", **attrs):
    a = {"group-title": cat, **attrs}
    if gid:
        a["tvg-id"] = gid
    return Entry(name, url, a)


def build(lineup, entries, tmp_path, alive=lambda e: True, used=None, index=None, nxt=None):
    book = NumberBook(tmp_path / "numbers.json")
    return build_lineup(lineup, entries, cfg(lineup), alive, set() if used is None else used,
                        index, book, nxt), book


def test_clean_name():
    assert clean_name("TMC HD (1080p) [Geo-blocked]") == "TMC"
    assert clean_name("RTP 1 (720p) [Not 24/7]") == "RTP 1"
    assert clean_name("AXN Movies (Portugal) (720p)") == "AXN Movies (Portugal)"
    assert clean_name("HD") == "HD"  # never empties a name
    assert resolution("X (1080p)") == 1080 and resolution("X") == 0


def test_duplicates_keep_best_resolution_and_cross_lineup_priority(tmp_path):
    lu = Lineup("fr", "France", ("s",))
    entries = [
        e("Alpha (720p)", "http://a/720", "Alpha.fr@SD"),
        e("Alpha HD (1080p)", "http://a/1080", "Alpha.fr@HD"),
        e("Beta", "http://b/1", "Beta.fr"),
        e("Beta", "http://b/0", "Beta.fr"),         # same resolution: smallest URL wins
        e("Gamma", "http://taken", "Gamma.fr"),
        e("Dead", "http://dead"),
    ]
    used = {"http://taken"}
    (out, rep), _ = build(lu, entries, tmp_path, alive=lambda x: x.url != "http://dead", used=used)
    assert [(x.name, x.url) for x in out] == [("Alpha", "http://a/1080"), ("Beta", "http://b/0")]
    assert (rep.duplicates, rep.taken_by_earlier_lineup, rep.dead) == (2, 1, 1)
    assert {"http://a/1080", "http://b/0"} <= used


def test_duplicates_prefer_measured_reliability_then_resolution(tmp_path):
    lu = Lineup("fr", "France", ("s",))
    entries = [
        e("Alpha (1080p)", "http://a/fhd-flaky", "Alpha.fr"),
        e("Alpha (720p)", "http://a/hd-stable", "Alpha.fr"),
        e("Beta (1080p)", "http://b/fhd-unmeasured", "Beta.fr"),
        e("Beta (720p)", "http://b/hd-stable", "Beta.fr"),
        e("Gamma (1080p)", "http://g/fhd-stable", "Gamma.fr"),
        e("Gamma (720p)", "http://g/hd-stable", "Gamma.fr"),
    ]
    verdicts = {"http://a/fhd-flaky": "unstable", "http://a/hd-stable": "stable",
                "http://b/hd-stable": "stable", "http://g/fhd-stable": "stable",
                "http://g/hd-stable": "stable"}
    book = NumberBook(tmp_path / "numbers.json")
    for order in (entries, entries[::-1]):
        out, _ = build_lineup(lu, order, cfg(lu), lambda x: True, set(), None, book,
                              verdict=lambda x: verdicts.get(x.url))
        assert [x.url for x in out] == ["http://a/hd-stable",       # measured unstable FHD loses
                                        "http://b/fhd-unmeasured",  # no measure: resolution decides
                                        "http://g/fhd-stable"]      # both stable: FHD kept


def test_output_does_not_depend_on_input_order(tmp_path):
    lu = Lineup("w", "World", ("s",), favorites=("Zeta",), by_category=True)
    entries = [e(f"Ch {i:03d}", f"http://x/{i}", cat=random.choice(["News", "Music", "Shop", ""]))
               for i in range(60)]
    entries += [e("Zeta", "http://z/1"), e("Dup", "http://d/2"), e("Dup", "http://d/1")]
    (first, _), _ = build(lu, list(entries), tmp_path / "a")
    for seed in range(5):
        shuffled = list(entries)
        random.Random(seed).shuffle(shuffled)
        (out, _), _ = build(lu, shuffled, tmp_path / f"b{seed}")
        assert [(x.name, x.url, x.attrs) for x in out] == [(x.name, x.url, x.attrs) for x in first]


def test_favorites_first_numbered_and_grouped(tmp_path):
    lu = Lineup("fr", "France", ("s",), favorites=("France 2", "TF1", "Missing"), first_number=1)
    entries = [e("Zed", "http://z"), e("TF1 (1080p)", "http://tf1"), e("France 2", "http://f2"),
               e("TF1 HD", "http://tf1hd", gid="Other.fr")]
    (out, rep), _ = build(lu, entries, tmp_path)
    assert [x.name for x in out[:2]] == ["France 2", "TF1"]
    assert [x.attrs["tvg-chno"] for x in out[:2]] == ["1", "2"]
    assert out[0].attrs["group-title"] == "France · Favorites;France · All"
    assert out[2].attrs["group-title"] == "France · All"  # the second "TF1" is not a favorite
    assert int(out[2].attrs["tvg-chno"]) >= 4             # after the 3 favorite slots
    assert rep.favorites_found == ["France 2", "TF1"] and rep.favorites_missing == ["Missing"]


def test_categories_buckets_order_and_exclusion(tmp_path):
    lu = Lineup("w", "World", ("s",), by_category=True, exclude_categories=("Shop",))
    entries = [e("M", "http://m", cat="Music"), e("N", "http://n", cat="News;Business"),
               e("S", "http://s", cat="Shop"), e("U", "http://u", cat="Undefined")]
    (out, rep), _ = build(lu, entries, tmp_path)
    assert [(x.name, x.attrs["group-title"]) for x in out] == [
        ("N", "World · News"), ("M", "World · Music"), ("U", "World · Other")]
    assert rep.excluded_category == 1


def test_numbers_are_stable_across_rebuilds(tmp_path):
    lu = Lineup("w", "World", ("s",), first_number=100)
    book_path = tmp_path / "n.json"
    run1 = [e("B", "http://b"), e("C", "http://c")]
    book = NumberBook(book_path)
    out1, _ = build_lineup(lu, run1, cfg(lu), lambda x: True, set(), None, book)
    book.save()
    numbers1 = {x.name: x.attrs["tvg-chno"] for x in out1}
    # "A" appears and sorts first; B and C must keep their numbers, B disappearing frees nothing
    out2, _ = build_lineup(lu, [e("A", "http://a"), e("C", "http://c")], cfg(lu),
                           lambda x: True, set(), None, NumberBook(book_path))
    numbers2 = {x.name: x.attrs["tvg-chno"] for x in out2}
    assert numbers2["C"] == numbers1["C"]
    assert numbers2["A"] not in numbers1.values()


def test_numbering_overflow_reported(tmp_path):
    lu = Lineup("fr", "France", ("s",), first_number=1)
    (_, rep), _ = build(lu, [e(f"C{i}", f"http://{i}") for i in range(5)], tmp_path, nxt=3)
    assert rep.numbering_overflow


def test_epg_mapping_by_id_alias_and_name(tmp_path):
    index = epg.EpgIndex(ids={"alpha.fr": "Alpha.fr", "nt1.fr": "NT1.fr"},
                         names={"betanews": "BetaNews.fr"})
    lu = Lineup("fr", "France", ("s",), epg_aliases={"TFX": "NT1.fr"})
    entries = [e("Alpha", "http://a", "Alpha.fr@SD"), e("Beta News (720p)", "http://b"),
               e("TFX", "http://t"), e("Unknown", "http://u", "Nope.fr")]
    (out, rep), _ = build(lu, entries, tmp_path, index=index)
    assert {x.name: x.attrs["tvg-id"] for x in out} == {
        "Alpha": "Alpha.fr", "Beta News": "BetaNews.fr", "TFX": "NT1.fr", "Unknown": "Nope.fr"}
    assert rep.with_epg == 3


def test_validate_catches_bad_output():
    good = Entry("A", "http://a", {"tvg-chno": "1"})
    assert validate([good]) == []
    assert validate([]) == ["lineup is empty"]
    problems = validate([good, Entry("A", "http://a", {"tvg-chno": "1"}), Entry("", "nourl")])
    assert any("duplicate channel number" in p for p in problems)
    assert any("duplicate channel" in p for p in problems)
    assert any("invalid entry" in p for p in problems)
