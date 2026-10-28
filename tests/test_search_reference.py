"""The optimised engines against deliberately naive reference implementations
on a random synthetic corpus. Every optimisation must keep the same results."""

import random

import numpy as np
import pytest

from tanakh_explorer import hebrew as H
from tanakh_explorer.corpus.scope import resolve_scope
from tanakh_explorer.niqqud import parse_word
from tanakh_explorer.niqqud_gematria import NiqqudTable
from tanakh_explorer.search import service as S
from tanakh_explorer.search.positional import (Element, SearchSpec, UnitSpace, canonical_combo, combo_lut_for,
                                               run_search)

NT = NiqqudTable()


# --- reference model, built straight from the verse objects ------------------------
def ref_words(corpus, kq, maqaf):
    drop = "q" if kq == "ketiv" else "k"
    words = []  # (verse, [units])
    for vi, v in enumerate(corpus.verses):
        cur = None
        for a in v.atoms:
            if a.role == drop:
                continue
            units = parse_word(a.text)
            if cur is not None and maqaf == "join":
                cur[1].extend(units)
            else:
                cur = (vi, list(units))
                words.append(cur)
            if not (a.maqaf_after and maqaf == "join"):
                cur = None
    return words


def ref_units(corpus, words, unit):
    out = []  # (verse, word_idx, first_unit, last_unit)
    if unit == "letters":
        for wi, (v, us) in enumerate(words):
            for u in us:
                out.append((v, wi, u, u))
    elif unit == "words":
        for wi, (v, us) in enumerate(words):
            out.append((v, wi, us[0] if us else None, us[-1] if us else None))
    else:
        by_v = {}
        for wi, (v, us) in enumerate(words):
            by_v.setdefault(v, []).append((wi, us))
        for v in sorted(by_v):
            ws = by_v[v]
            letters = [u for _, us in ws for u in us]
            if ws:
                out.append((v, ws[0][0], letters[0] if letters else None, letters[-1] if letters else None))
    return out


def ref_search(corpus, units, elems, offsets, boundary, scope_mask, whole_word_words=None):
    rid, cur, prev = [], -1, False
    for m in scope_mask:
        if m and not prev:
            cur += 1
        rid.append(cur if m else -1)
        prev = m
    chapter = corpus.verse_chapter_id
    book = corpus.verse_book
    hits = []
    n = len(units)
    for s in range(n):
        if s + offsets[-1] >= n:
            break
        ok = True
        for (letters, combos, value, sel), o in zip(elems, offsets):
            v, wi, fu, lu = units[s + o]
            u = fu if sel == "first" else lu
            if u is None:
                ok = False
                break
            if letters is not None and H.FINAL_TO_REGULAR.get(u.char, u.char) not in letters:
                ok = False
            if combos is not None and canonical_combo(u.combo) not in combos:
                ok = False
            if value is not None and NT.combo_value(u.combo) != value:
                ok = False
        if not ok:
            continue
        v0, v1 = units[s][0], units[s + offsets[-1]][0]
        if rid[v0] < 0 or rid[v0] != rid[v1]:
            continue
        if boundary == "verse" and v0 != v1:
            continue
        if boundary == "chapter" and chapter[v0] != chapter[v1]:
            continue
        if boundary == "book" and book[v0] != book[v1]:
            continue
        if boundary == "word" and units[s][1] != units[s + offsets[-1]][1]:
            continue
        hits.append(s)
    return hits


SCOPES = [None, {"items": [{"type": "books", "value": ["Gen", "Ps"]}]},
          {"items": [{"type": "chapters", "book": "Gen", "from": 2, "to": 3}]}]


@pytest.mark.parametrize("unit", ["letters", "words", "verses"])
@pytest.mark.parametrize("kq,maqaf", [("ketiv", "split"), ("qere", "join")])
def test_positional_engine_matches_reference(synth, unit, kq, maqaf):
    rng = random.Random(hash((unit, kq, maqaf)) & 0xFFFF)
    layer = synth.layer(kq, maqaf)
    space = UnitSpace(synth, layer, unit)
    words = ref_words(synth, kq, maqaf)
    assert len(words) == layer.n_words
    units = ref_units(synth, words, unit)
    assert len(units) == space.n
    for trial in range(30):
        k = rng.randint(1, 4)
        skips = [rng.randint(1, 4) for _ in range(k - 1)]
        offsets = [0]
        for d in skips:
            offsets.append(offsets[-1] + d)
        if offsets[-1] >= space.n:
            continue
        # build the query from a real position so that matches exist
        s0 = rng.randrange(0, space.n - offsets[-1])
        elems_ref, elems = [], []
        mode = rng.choice(["letters", "niqqud", "both", "value"])
        for o in offsets:
            sel = rng.choice(["first", "last"])
            v, wi, fu, lu = units[s0 + o]
            u = fu if sel == "first" else lu
            if u is None:
                u = parse_word("א")[0]
            letters = combos = value = None
            el = Element(selector=sel)
            if mode in ("letters", "both"):
                letters = {H.FINAL_TO_REGULAR.get(u.char, u.char)}
                el.letters = H.letter_lut(u.char)
            if mode in ("niqqud", "both"):
                combos = {canonical_combo(u.combo)}
                el.combos = combo_lut_for(u.combo)
            if mode == "value":
                value = NT.combo_value(u.combo)
                el.value = value
            elems_ref.append((letters, combos, value, sel))
            elems.append(el)
        boundary = rng.choice(["none", "verse", "chapter", "book"] + (["word"] if unit == "letters" else []))
        scope_spec = rng.choice(SCOPES)
        scope = resolve_scope(synth, scope_spec)
        got = run_search(space, SearchSpec(elems, offsets, boundary=boundary), scope, NT).tolist()
        want = ref_search(synth, units, elems_ref, offsets, boundary, scope.mask.tolist())
        assert got == want, (unit, kq, maqaf, mode, offsets, boundary, scope_spec)


def test_variable_scan_matches_enumeration(synth):
    req = {"query": "אב", "unit": "letters", "skip_min": 1, "skip_max": 6, "layer": {"kq": "ketiv", "maqaf": "split"},
           "limit": 10_000}
    total = 0
    for d in range(1, 7):
        total += S.letter_search(synth, {**req, "skips": [d], "limit": 0})["total"]
    res = S.variable_skip_scan(synth, req)
    assert res["complete"] and res["total"] == total
    req3 = {**req, "query": "אבג", "skip_max": 4}
    total3 = sum(S.letter_search(synth, {**req3, "skips": [a, b], "limit": 0})["total"]
                 for a in range(1, 5) for b in range(1, 5))
    assert S.variable_skip_scan(synth, req3)["total"] == total3


def test_constant_scan_matches_individual_searches(synth):
    req = {"query": "את", "unit": "letters", "skip_min": 1, "skip_max": 15}
    res = S.constant_skip_scan(synth, req)
    for row in res["rows"]:
        assert row["count"] == S.letter_search(synth, {**req, "skips": [row["skip"]], "limit": 0})["total"]
    assert res["complete"]


def test_niqqud_sum_heads_reference(synth):
    layer = synth.layer("qere", "split")
    lut = NT.combo_lut()
    first_vals = [int(lut[layer.l_combo[layer.word_lstart[w]]]) if layer.word_len[w] else 0 for w in range(layer.n_words)]
    for target, length, skip in [(26, 3, 1), (36, 2, 2), (16, 4, 1)]:
        res = S.niqqud_sum_search(synth, {"target": target, "kind": "heads", "length": length, "skips": [skip],
                                          "layer": {"kq": "qere"}, "limit": 0})
        want = 0
        for s in range(layer.n_words - skip * (length - 1)):
            idx = [s + j * skip for j in range(length)]
            if all(layer.word_len[i] for i in idx) and sum(first_vals[i] for i in idx) == target:
                want += 1
        assert res["total"] == want


def test_in_verse_run_reference(synth):
    layer = synth.layer("qere", "split")
    from tanakh_explorer import gematria as G
    m = G.get("niqqud")
    wv = m.word_values(layer, {})
    for target in (16, 30, 46):
        res = S.niqqud_sum_search(synth, {"target": target, "kind": "in_verse", "sub": "run", "layer": {"kq": "qere"}, "limit": 0})
        want = 0
        for v in range(len(synth.verses)):
            s, n = int(layer.verse_wstart[v]), int(layer.verse_wcount[v])
            for i in range(s, s + n):
                for j in range(i + 1, s + n + 1):
                    if int(wv[i:j].sum()) == target:
                        want += 1
        assert res["total"] == want


def test_gematria_window_search_reference(synth):
    layer = synth.layer("ketiv", "split")
    from tanakh_explorer import gematria as G
    m = G.get("standard")
    wv = m.word_values(layer, {})
    target = int(wv[5] + wv[6])
    res = S.gematria_search(synth, {"target": target, "n_min": 2, "n_max": 2, "limit": 0})
    want = sum(1 for s in range(layer.n_words - 1)
               if int(wv[s] + wv[s + 1]) == target and layer.word_verse[s] == layer.word_verse[s + 1])
    assert res["total"] == want


def test_whole_word_letters_equals_word_index(synth):
    layer = synth.layer("ketiv", "split")
    word = next(w for w in layer.word_consonants if len(w) >= 2)
    res = S.letter_search(synth, {"query": word, "unit": "letters", "whole_word": True, "limit": 0})
    assert res["total"] == len(layer.word_index_by_consonants[H.normalize_finals(word)])


def test_final_letter_policy(synth):
    layer = synth.layer("ketiv", "split")
    word = next(w for w in layer.word_consonants if w[-1] in H.FINALS)
    fold = S.letter_search(synth, {"query": word[:-1] + H.FINAL_TO_REGULAR[word[-1]], "unit": "letters",
                                   "whole_word": True, "limit": 0})["total"]
    exact = S.letter_search(synth, {"query": word[:-1] + H.FINAL_TO_REGULAR[word[-1]], "unit": "letters",
                                    "whole_word": True, "finals": "exact", "limit": 0})["total"]
    assert fold >= 1
    assert exact < fold or exact == 0


def test_ketiv_and_qere_never_consecutive(synth):
    for kq, bad in (("ketiv", 2), ("qere", 1)):
        assert not (synth.layer(kq).word_role == bad).any()


def test_scope_ranges_do_not_join(synth):
    scope = resolve_scope(synth, {"items": [{"type": "chapters", "book": "Gen", "from": 1, "to": 1},
                                            {"type": "chapters", "book": "Gen", "from": 3, "to": 3}]})
    assert len(set(scope.range_id[scope.mask].tolist())) == 2
    assert np.all(scope.range_id[~scope.mask] == -1)
