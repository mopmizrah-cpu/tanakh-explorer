import pytest

from tanakh_explorer import hebrew as H
from tanakh_explorer import transformations as X

AB = H.ALEPHBET


def m(tid, **params):
    return X.get(tid).mapping(params or None)


def test_atbash_full_table():
    t = m("atbash")
    for i, ch in enumerate(AB):
        assert t[ch] == AB[21 - i]
    assert X.get("atbash").apply("ששך") == "בבל"


def test_albam_pairs():
    t = m("albam")
    assert [t[c] for c in "אבגדה"] == list("למנסע")
    assert t["כ"] == "ת"


def test_achbi():
    t = m("achbi")
    assert (t["א"], t["ב"], t["ג"], t["ל"], t["מ"]) == ("כ", "י", "ט", "ת", "ש")
    assert t["ו"] == "ו" and t["פ"] == "פ"  # middle of each half


def test_split_alef_yod():
    t = m("split_alef_yod")
    assert (t["א"], t["ה"], t["ו"], t["כ"], t["ע"], t["פ"]) == ("י", "ו", "ה", "ת", "פ", "ע")
    assert X.get("split_alef_yod").category == "user_defined"


def test_atbach_variants():
    t = m("atbach")
    pairs = [("א", "ט"), ("ב", "ח"), ("ג", "ז"), ("ד", "ו"), ("י", "צ"), ("כ", "פ"), ("ל", "ע"), ("מ", "ס"),
             ("ק", "ת"), ("ר", "ש"), ("ה", "נ")]
    for a, b in pairs:
        assert t[a] == b and t[b] == a
    t2 = m("atbach", he_nun="fixed")
    assert t2["ה"] == "ה" and t2["נ"] == "נ"
    g = m("atbach_gadol")
    assert g["ק"] == "ץ" and g["ת"] == "ם" and g["ך"] == "ך"


INVOLUTIONS = ["atbash", "albam", "achbi", "split_alef_yod", "atbach", "atbach_gadol"]


@pytest.mark.parametrize("tid", INVOLUTIONS)
def test_involution_property(tid):
    t = m(tid)
    for ch in H.ALL_LETTERS:
        if ch in H.FINALS and X.get(tid).resolve(None)["finals"] != "own":
            continue
        assert t[t[ch]] == ch
    assert X.get(tid).to_dict()["involution"]


def test_achas_betah_cycles():
    fwd, back = m("achas_betah"), m("achas_betah", direction="backward")
    assert (fwd["א"], fwd["ח"], fwd["ס"]) == ("ח", "ס", "א")
    assert fwd["ת"] == "ת"
    for ch in AB:
        assert back[fwd[ch]] == ch
        assert fwd[fwd[fwd[ch]]] == ch
    assert not X.get("achas_betah").to_dict()["involution"]


def test_ayak_bachar():
    t = m("ayak_bachar")
    assert (t["א"], t["י"], t["ק"]) == ("י", "ק", "א")
    assert (t["ה"], t["נ"], t["ך"]) == ("נ", "ך", "ה")
    nf = m("ayak_bachar", finals_mode="no_finals", finals="normalize")
    assert nf["ה"] == "נ" and nf["נ"] == "ה"


def test_shift_forward_and_back():
    t = X.get("shift")
    assert t.apply("אבג", {"n": 1}) == "בגד"
    assert t.apply("ת", {"n": 1, "cyclic": True}) == "א"
    assert t.apply("ת", {"n": 1, "cyclic": False}) == "ת"
    assert t.apply("ם", {"n": 3}) == "ם"  # final letters unchanged by default
    assert t.apply("מ", {"n": 1, "direction": "backward"}) == "ל"
    assert X.get("avgad").apply("אבת") == "בגת"
    assert X.get("shift_back").apply("אבג") == "אאב"
    assert X.get("shift_back").apply("א", {"cyclic": True}) == "ת"


def test_all_shifts_unique():
    t = X.get("shift")
    outs = {t.apply("אבגדהוזחטיכלמנסעפצקרשת", {"n": n, "cyclic": True}) for n in range(22)}
    assert len(outs) == 22


def test_niqqud_stays_on_position_and_shin_dot_dropped():
    out = X.get("atbash").apply("שָׁלוֹם")
    assert out == "בָכפֹי"
    assert X.get("albam").apply("בְּ") == "מְּ"


def test_word_end_finals():
    assert X.get("atbash").apply("ששך") == "בבל"
    assert X.get("albam").apply("דב") == "סם"


def test_articulation_groups_cover_alphabet():
    letters = "".join(g["letters"] for g in X.articulation_groups())
    assert sorted(letters) == sorted(AB)


def test_metadata_complete():
    for tid, t in X.REGISTRY.items():
        d = t.to_dict()
        assert d["name_he"] and d["description_he"] and d["source_he"]
        assert len(t.table()) == 27
