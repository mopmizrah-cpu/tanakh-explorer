import pytest

from tanakh_explorer import hebrew as H
from tanakh_explorer.niqqud import decode_combo, encode_combo, parse_text, parse_word
from tanakh_explorer.niqqud_gematria import NiqqudTable, word_breakdown

VALUES = {
    "ַ": ("patah", 6), "ָ": ("qamats", 16), "ֵ": ("tsere", 20), "ֶ": ("segol", 30),
    "ְ": ("sheva", 20), "ֹ": ("holam", 10), "ִ": ("hiriq", 10), "ֻ": ("qubuts", 30),
    "ֲ": ("hataf_patah", 26), "ֳ": ("hataf_qamats", 36), "ֱ": ("hataf_segol", 50),
}


@pytest.mark.parametrize("mark,expected", list(VALUES.items()))
def test_each_vowel_value(mark, expected):
    name, value = expected
    units = parse_word("ב" + mark)
    assert units[0].vowels == (name,)
    assert NiqqudTable().combo_value(units[0].combo) == value


def test_shuruq_value_and_detection():
    units = parse_word("הוּא")
    assert [u.vowels for u in units] == [(), ("shuruq",), ()]
    assert word_breakdown(units)["total"] == 10
    assert parse_word("וּבְ")[0].vowels == ("shuruq",)


def test_hataf_values_are_single_units():
    assert word_breakdown(parse_word("אֱ"))["total"] == 50  # not 20 + 30 counted twice
    # sheva + segol written as two points on one letter is the same hataf segol
    assert parse_word("אְֶ")[0].vowels == ("hataf_segol",)
    assert word_breakdown(parse_word("אְֶ"))["total"] == 50


def test_marks_without_value():
    plain = word_breakdown(parse_word("בָּ"))["total"]
    assert plain == 16
    assert word_breakdown(parse_word("בָּֽ֑"))["total"] == 16  # meteg and accents add nothing
    assert word_breakdown(parse_word("שָׁ"))["total"] == 16  # shin dot is not a vowel
    assert word_breakdown(parse_word("ב"))["total"] == 0  # no vowel = 0
    assert parse_word("ב")[0].vowels == ()


def test_shalom():
    units = parse_word("שָׁלוֹם")
    assert [u.vowels for u in units] == [("qamats",), (), ("holam",), ()]
    assert word_breakdown(units)["total"] == 26


def test_consonantal_vav_and_unclear():
    units = parse_word("וַיְצַוּוּ")
    assert units[3].vowels == () and "consonantal_vav" in units[3].flags
    assert units[4].vowels == ("shuruq",)
    units = parse_word("הַוּוֹת")
    assert units[1].vowels == () and "consonantal_vav" in units[1].flags
    # a vav with dagesh after a pointed letter and no vav after it: not decided, flagged
    units = parse_word("קַוּ")
    assert units[1].vowels == ("vav_dagesh_unclear",) and "needs_review" in units[1].flags


def test_vav_with_vowel_is_not_shuruq():
    units = parse_word("צִוָּה")
    assert units[1].vowels == ("qamats",)


def test_two_vowels_on_one_letter():
    units = parse_word("יְרוּשָׁלַ͏ִם")
    assert units[4].vowels == ("patah", "hiriq")
    assert NiqqudTable().combo_value(units[4].combo) == 16


def test_qamats_qatan_configurable():
    u = parse_word("כׇּל")[0]
    assert u.vowels == ("qamats_qatan",)
    assert NiqqudTable().combo_value(u.combo) == 16
    assert NiqqudTable.from_overrides({"qamats_qatan": 99}).combo_value(u.combo) == 99


def test_holam_haser_for_vav_is_holam():
    assert parse_word("מִצְוֺת")[2].vowels == ("holam",)


def test_combo_roundtrip():
    for vs in [(), ("qamats",), ("patah", "hiriq"), ("shuruq",)]:
        assert decode_combo(encode_combo(vs)) == vs


def test_marks_stay_on_their_letter():
    units = parse_word("בְּרֵאשִׁית")
    assert "".join(u.text for u in units) == "בְּרֵאשִׁית"
    assert H.letters_only("בְּרֵאשִׁית") == "בראשית"


def test_parse_text_splits_on_maqaf():
    assert len(parse_text("כׇּל־הָעָם")) == 2
