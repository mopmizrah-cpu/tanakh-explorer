"""Tests on the full Tanakh (skipped when the data has not been downloaded)."""

import numpy as np

from tanakh_explorer import hebrew as H
from tanakh_explorer.corpus.books import BOOK_INDEX
from tanakh_explorer.corpus.scope import resolve_scope
from tanakh_explorer.corpus.sections import masoretic_sections, weekly_parashot
from tanakh_explorer.search import service as S


def test_structure_counts(corpus):
    assert len(corpus.verses) == 23202
    assert len({(v.book, v.chapter) for v in corpus.verses}) == 929
    assert len({v.book for v in corpus.verses}) == 39


def test_genesis_1_1(corpus):
    L = corpus.layer()
    s = int(L.verse_wstart[0])
    assert L.word_consonants[s:s + 7] == ["בראשית", "ברא", "אלהים", "את", "השמים", "ואת", "הארץ"]
    assert int(L.word_lstart[s + 7]) == 28  # 28 letters in Gen 1:1


def test_large_bet_of_bereshit(corpus):
    L = corpus.layer()
    assert L.l_flags[0] & 1  # large letter


def test_parasha_markers_are_not_letters(corpus):
    # Gen 1:5 ends a petuha; the marker must not add a פ to the verse
    L = corpus.layer()
    vi = corpus.verse_index["Gen.1.5"]
    s, n = int(L.verse_wstart[vi]), int(L.verse_wcount[vi])
    assert L.word_consonants[s + n - 1] == "אחד"
    assert corpus.verses[vi + 1].markers_before == ["pe2"]


def test_ketiv_qere_lam_1_18(corpus):
    vi = corpus.verse_index["Lam.1.18"]
    for kq, expect in (("ketiv", "עמים"), ("qere", "העמים")):
        L = corpus.layer(kq)
        s, n = int(L.verse_wstart[vi]), int(L.verse_wcount[vi])
        assert expect in L.word_consonants[s:s + n]
        other = "העמים" if kq == "ketiv" else "עמים"
        assert other not in L.word_consonants[s:s + n]


def test_maqaf_modes(corpus):
    split, join = corpus.layer("ketiv", "split"), corpus.layer("ketiv", "join")
    assert split.n_letters == join.n_letters
    assert join.n_words < split.n_words


def test_weekly_and_masoretic(corpus):
    ps = weekly_parashot(corpus)
    assert len(ps) == 54 and ps[0].name == "בראשית" and ps[-1].name == "וזאת הברכה"
    secs = masoretic_sections(corpus)
    assert {s.kind for s in secs} == {"petuha", "setuma", "book_start"}


def test_scope_torah(corpus):
    sc = resolve_scope(corpus, {"items": [{"type": "section", "value": "torah"}]})
    assert sc.n_verses == int(np.isin(corpus.verse_book, [BOOK_INDEX[b] for b in ("Gen", "Exod", "Lev", "Num", "Deut")]).sum())


def test_known_searches(corpus):
    assert S.gematria_search(corpus, {"query": "שלום", "limit": 0})["total"] > 0
    r = S.letter_search(corpus, {"query": "בראשית", "unit": "letters", "whole_word": True, "limit": 1})
    assert r["total"] >= 1 and r["results"][0]["from"]["osis"] == "Gen.1.1"
    # Atbash: ששך = בבל (Jeremiah 25:26, 51:41)
    r = S.transform_search(corpus, {"query": "בבל", "transformation": "atbash", "search_mode": "word", "limit": 5})
    assert r["transformation"]["output"] == "ששך"
    assert {x["from"]["osis"] for x in r["results"]} == {"Jer.25.26", "Jer.51.41"}


def test_niqqud_heads_full_verse(corpus):
    vi = corpus.verse_index["Gen.1.1"]
    L = corpus.layer("qere")
    s, n = int(L.verse_wstart[vi]), int(L.verse_wcount[vi])
    heads = "".join(L.word_text[w][: int(L.l_cend[L.word_lstart[w]])] for w in range(s, s + n))
    r = S.niqqud_search(corpus, {"query": heads, "unit": "words", "match": "letters_niqqud", "boundary": "verse",
                                 "full_verse": True, "layer": {"kq": "qere"}, "limit": 5})
    assert "Gen.1.1" in {x["from"]["osis"] for x in r["results"]}


def test_letters_never_include_marks(corpus):
    L = corpus.layer()
    assert int(L.l_code.max()) < H.N_CODES
