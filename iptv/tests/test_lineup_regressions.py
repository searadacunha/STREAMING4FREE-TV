"""Regressions: each test below failed before the fix that came with it."""
from iptv4free import epg
from iptv4free.channels import build_lineup, validate
from iptv4free.config import Config, Lineup
from iptv4free.playlists import Entry, parse_m3u
from iptv4free.updates import NumberBook


def e(name, url, cat=""):
    return Entry(name, url, {"group-title": cat})


def build(lineup, entries, book_path):
    book = NumberBook(book_path)
    out, rep = build_lineup(lineup, entries, Config(path=None, lineups=(lineup,)),
                            lambda x: True, set(), None, book)
    book.save()
    return out, rep


def numbers(out):
    return {x.name: int(x.attrs["tvg-chno"]) for x in out}


def test_adding_a_favorite_later_never_duplicates_a_channel_number(tmp_path):
    entries = [e(n, f"http://s/{n}") for n in "ABCD"]
    book = tmp_path / "numbers.json"
    first, _ = build(Lineup("fr", "France", ("s",), favorites=("A", "B"), first_number=1), entries, book)
    assert numbers(first) == {"A": 1, "B": 2, "C": 3, "D": 4}
    later, _ = build(Lineup("fr", "France", ("s",), favorites=("A", "B", "D"), first_number=1), entries, book)
    assert validate(later) == []
    assert numbers(later) == {"A": 1, "B": 2, "D": 3, "C": 5}  # 3 now belongs to the third favorite


def test_raising_first_number_never_duplicates_a_channel_number(tmp_path):
    entries = [e(n, f"http://s/{n}") for n in "ABCD"]
    book = tmp_path / "numbers.json"
    build(Lineup("fr", "France", ("s",), favorites=("A", "B"), first_number=1), entries, book)
    later, _ = build(Lineup("fr", "France", ("s",), favorites=("A", "B"), first_number=3), entries, book)
    assert validate(later) == []
    assert numbers(later) == {"A": 3, "B": 4, "C": 5, "D": 6}


def test_channels_named_in_non_latin_scripts_are_not_merged(tmp_path):
    names = ["Первый канал", "Домашний", "Россия 1", "Россия 24", "الجزيرة", "湖南卫视", "ΕΡΤ"]
    keys = {epg.match_key(n) for n in names}
    assert len(keys) == len(names) and "" not in keys
    entries = [e(n, f"http://s/{i}") for i, n in enumerate(names)]
    out, rep = build(Lineup("w", "World", ("s",)), entries, tmp_path / "numbers.json")
    assert sorted(x.name for x in out) == sorted(names)
    assert rep.duplicates == 0


def test_match_key_is_unchanged_for_latin_names():
    assert epg.match_key("TF1 Séries Films HD (1080p) [Geo-blocked]") == "tf1seriesfilms"
    assert epg.match_key("Canal+ Sport") == "canal+sport"


def test_a_channel_is_excluded_when_any_of_its_categories_is_excluded(tmp_path):
    lineup = Lineup("w", "World", ("s",), exclude_categories=("Shop", "XXX"))
    entries = [e("News", "http://s/1", "News"), e("Shop", "http://s/2", "Shop"),
               e("Lifestyle shop", "http://s/3", "Lifestyle;Shop"),
               e("Adult", "http://s/4", "Entertainment; XXX")]
    out, rep = build(lineup, entries, tmp_path / "numbers.json")
    assert [x.name for x in out] == ["News"]
    assert rep.excluded_category == 3


def test_unicode_separators_inside_a_name_do_not_drop_the_channel():
    for separator in (" ", "\x85", "\x0c"):
        text = f'#EXTM3U\r\n#EXTINF:-1 tvg-id="A.fr",Name{separator}Part2\r\nhttp://x/a\r\n'
        result = parse_m3u(text)
        assert [(x.name.split(), x.url) for x in result.entries] == [(["Name", "Part2"], "http://x/a")]
        assert result.skipped == []
