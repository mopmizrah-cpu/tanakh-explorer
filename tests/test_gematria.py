import random

import numpy as np
import pytest

from tanakh_explorer import gematria as G
from tanakh_explorer.niqqud import parse_text


def val(method, text, **params):
    return G.get(method).compute(text, params or None)["value"]


def test_standard_shalom():
    assert val("standard", "שלום") == 376
    assert val("standard", "שלומ") == 376  # final forms take the regular value


def test_finals_standard_vs_gadol():
    for f, v in zip("ךםןףץ", (500, 600, 700, 800, 900)):
        assert val("gadol", f) == v
    for f, v in zip("ךםןףץ", (20, 40, 50, 80, 90)):
        assert val("standard", f) == v
    assert val("gadol", "שלום") == 936


def test_katan_and_reduced_are_distinct():
    assert val("katan", "שלום") == 3 + 3 + 6 + 4  # 16
    assert val("katan_reduced", "שלום") == 7  # 16 -> 7
    assert val("katan", "ך", finals="gadol") == 5
    assert val("katan_reduced", "") == 0


def test_kolel():
    assert val("kolel", "שלום") == 377
    assert val("kolel", "שלום עליכם", scope="phrase") == 376 + 170 + 1
    assert val("kolel", "שלום עליכם", scope="word") == 376 + 170 + 2


def test_ordinal():
    assert val("ordinal", "א") == 1 and val("ordinal", "ת") == 22
    assert val("ordinal", "ם") == 13
    assert val("ordinal", "ם", finals="extended") == 24


def test_milui_presets():
    assert val("milui", "יהוה", preset="yudin") == 72
    assert val("milui", "יהוה", preset="sag") == 63
    assert val("milui", "יהוה", preset="alfin") == 45
    assert val("milui", "יהוה", preset="hehin") == 52
    assert val("milui", "א") == 111
    assert val("milui", "ה", custom={"ה": "הה"}) == 10


def test_milui_demilui_and_neelam():
    # א -> אלף -> אלף למד פא
    assert val("milui_demilui", "א", depth=2) == 111 + 74 + 81
    assert val("milui_demilui", "א", depth=1) == val("milui", "א")
    assert val("neelam", "א") == 110  # לף


def test_kidmi_and_meshulash_ids():
    assert [val("kidmi", c) for c in "אבגד"] == [1, 3, 6, 10]
    assert val("kidmi", "ת") == 1495
    assert val("meshulash_kidmi", "ג") == 6
    assert val("meshulash_cube", "ג") == 27
    assert G.get("meshulash_kidmi").formula_he != G.get("meshulash_cube").formula_he


def test_squares_vs_square_of_sum():
    assert val("prati", "בג") == 4 + 9
    assert val("merubah_klali", "בג") == 25


def test_boneh_and_achor():
    assert val("boneh", "אבג") == 10
    assert val("boneh", "יהוה") == 72
    assert val("achor", "אבג") == 1 * 1 + 2 * 2 + 3 * 3
    assert val("achor", "אב גד", reset="word") == (1 + 4) + (3 + 8)
    assert val("achor", "אב גד", reset="phrase") == 1 + 4 + 9 + 16


def test_mosafi_vs_words():
    assert val("mosafi", "שלום עליכם") == 376 + 170 + 9
    assert val("with_words", "שלום עליכם") == 376 + 170 + 2


def test_mispari():
    assert val("mispari", "א") == 13  # אחד
    assert val("mispari", "א", gender="fem") == 409  # אחת


def test_powers():
    assert val("power_letters", "בג", power=3) == 8 + 27
    assert val("power_total", "בג", power=3) == 125


def test_niqqud_methods():
    assert val("niqqud", "שָׁלוֹם") == 26
    assert val("letters_plus_niqqud", "שָׁלוֹם") == 376 + 26


def test_unique_ids_and_metadata():
    for mid, m in G.REGISTRY.items():
        assert m.id == mid
        assert m.name_he and m.formula_he and m.source_he and m.finals_he
        assert m.category in ("traditional", "mathematical", "niqqud", "custom")


def test_custom_method():
    m = G.register_custom("unit_test", "בדיקה", {c: 1 for c in "אבגדהוזחטיכלמנסעפצקרשת"})
    try:
        assert m.category == "custom"
        assert val("custom:unit_test", "שלום") == 4
    finally:
        G.remove_custom("unit_test")


@pytest.mark.parametrize("mid", sorted(k for k in G.REGISTRY if not k.startswith("custom:")))
def test_vectorised_equals_scalar(synth, mid):
    """The vectorised corpus computation must agree with the calculator."""
    m = G.get(mid)
    rng = random.Random(1)
    for maqaf in ("split", "join"):
        layer = synth.layer("qere", maqaf)
        p = m.resolve(None)
        for n in (1, 2, 3):
            starts = np.array(sorted(rng.sample(range(layer.n_words - n), 25)))
            vals = m.span_values(layer, starts, starts + n, p)
            for s, v in zip(starts.tolist(), np.asarray(vals).tolist()):
                text = " ".join(layer.word_text[w] for w in range(s, s + n))
                words = parse_text(text, join_maqaf=maqaf == "join")
                assert sum(len(w) for w in words) == int(layer.word_lstart[s + n - 1] + layer.word_len[s + n - 1] - layer.word_lstart[s])
                assert int(v) == m.compute(words, p)["value"], (mid, text)


def test_positional_methods_phrase_reset_vectorised(synth):
    layer = synth.layer("qere", "split")
    for mid in ("achor", "boneh"):
        m = G.get(mid)
        p = m.resolve({"reset": "phrase"})
        starts = np.arange(0, 40)
        vals = m.span_values(layer, starts, starts + 3, p)
        for s, v in zip(starts.tolist(), vals.tolist()):
            text = " ".join(layer.word_text[w] for w in range(s, s + 3))
            assert v == m.compute(text, p)["value"]
