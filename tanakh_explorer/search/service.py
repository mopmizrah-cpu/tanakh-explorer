"""High-level search functions. Each takes a plain ``dict`` request (as sent
by the API) and returns a JSON-serialisable ``dict`` that records the exact
settings used, so every result can be reproduced.

Common request fields
---------------------
``layer``   {"kq": "ketiv"|"qere", "maqaf": "split"|"join"}
``scope``   scope spec (see :mod:`tanakh_explorer.corpus.scope`)
``finals``  "fold" (ם matches מ, the default) or "exact"
``niqqud_values``  overrides of the niqqud value table
``limit`` / ``offset``  paging of the displayed results (the total is always exact)
"""

from __future__ import annotations

import time

import numpy as np

from .. import hebrew as H
from ..corpus.scope import resolve_scope
from ..gematria import get as get_method
from ..gematria import REGISTRY as GEMATRIA
from ..niqqud import combo_hebrew, parse_text
from ..niqqud_gematria import NiqqudTable
from ..transformations import ARTICULATION
from ..transformations import REGISTRY as TRANSFORMS
from ..transformations import get as get_transform
from .positional import (Element, SearchSpec, UnitSpace, combo_lut_for, letter_elements,
                         offsets_from_skips, run_search)
from .results import positional_results, span_result

MAX_LIMIT = 1000

_spaces: dict = {}


def _ctx(corpus, req: dict):
    lay = req.get("layer") or {}
    layer = corpus.layer(lay.get("kq", "ketiv"), lay.get("maqaf", "split"))
    scope = resolve_scope(corpus, req.get("scope"))
    ntable = NiqqudTable.from_overrides(req.get("niqqud_values"))
    exact = req.get("finals", "fold") == "exact"
    limit = min(int(req.get("limit", 100)), MAX_LIMIT)
    offset = int(req.get("offset", 0))
    return layer, scope, ntable, exact, limit, offset


def space_for(corpus, layer, unit: str) -> UnitSpace:
    key = (id(corpus), layer.kq, layer.maqaf, unit)
    if key not in _spaces:
        _spaces[key] = UnitSpace(corpus, layer, unit)
    return _spaces[key]


def _settings(req: dict, layer, scope, extra: dict | None = None) -> dict:
    s = {
        "layer": {"kq": layer.kq, "maqaf": layer.maqaf},
        "layer_he": ("כתיב" if layer.kq == "ketiv" else "קרי") + " · " +
                    ("מקף מפריד בין מילים" if layer.maqaf == "split" else "צירוף במקף = מילה אחת"),
        "scope": scope.spec, "scope_he": scope.description, "finals": req.get("finals", "fold"),
    }
    s.update(extra or {})
    return s


def _skips(req: dict, k: int) -> tuple[list[int], str]:
    skips = req.get("skips") or [1]
    skips = [int(x) for x in skips]
    offs = offsets_from_skips(skips, k)
    if len(set(skips)) <= 1:
        label = f"דילוג קבוע: {skips[0]}" if skips[0] != 1 else "רצף (ללא דילוג)"
    else:
        label = "דילוג משתנה: " + ", ".join(map(str, skips))
    return offs, label


# ----------------------------------------------------------------------------
# letter searches: acrostics, verse acrostics, letter sequences, skips
# ----------------------------------------------------------------------------

def letter_search(corpus, req: dict) -> dict:
    t0 = time.time()
    layer, scope, ntable, exact, limit, offset = _ctx(corpus, req)
    query = H.letters_only(req.get("query", ""))
    if not query:
        raise ValueError("יש להזין מילת חיפוש בעברית")
    unit = req.get("unit", "words")
    selector = req.get("selector", "first")
    selectors = req.get("selectors") if selector == "mixed" else None
    if selectors and len(selectors) != len(query):
        raise ValueError("יש לבחור מיקום (ראש/סוף) לכל אות")
    groups = None
    if req.get("letter_groups") == "articulation":
        groups = {}
        for _, letters in ARTICULATION.values():
            for ch in letters:
                groups[ch] = letters
    elements = letter_elements(query, exact, selector if selector != "mixed" else "first", selectors, groups)
    offs, skip_label = _skips(req, len(elements))
    boundary = req.get("boundary", "none")
    spec = SearchSpec(elements, offs, boundary=boundary, anchor=req.get("anchor") or None,
                      anchor_skip=int(req.get("anchor_skip", 0)), whole_word=bool(req.get("whole_word")))
    space = space_for(corpus, layer, unit)
    starts = run_search(space, spec, scope, ntable)
    results = positional_results(corpus, layer, space, starts, offs, elements, limit, offset,
                                 ntable=ntable, skip_label=skip_label)
    total = int(len(starts))
    rev_total = 0
    if req.get("reverse"):
        rev_el = list(reversed(elements))
        rspec = SearchSpec(rev_el, offs, boundary=boundary, whole_word=spec.whole_word)
        rstarts = run_search(space, rspec, scope, ntable)
        rev_total = int(len(rstarts))
        room = max(limit - len(results), 0)
        results += positional_results(corpus, layer, space, rstarts, offs, rev_el, room,
                                      max(offset - total, 0), reverse=True, ntable=ntable, skip_label=skip_label)
    return {
        "total": total + rev_total, "total_forward": total, "total_reverse": rev_total,
        "results": results,
        "settings": _settings(req, layer, scope, {
            "query": query, "unit": unit, "selector": selector, "selectors": selectors,
            "skips": req.get("skips") or [1], "offsets": offs, "boundary": boundary,
            "anchor": req.get("anchor"), "anchor_skip": req.get("anchor_skip", 0),
            "letter_groups": req.get("letter_groups"), "reverse": bool(req.get("reverse")),
            "skip_definition": "דילוג d = היחידות שנבחרו מרוחקות d מקומות זו מזו (d=1 רצוף)",
        }),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
    }


def phrase_search(corpus, req: dict) -> dict:
    """Whole words in sequence (with optional skips between the words)."""
    layer, scope, ntable, exact, limit, offset = _ctx(corpus, req)
    words = [H.letters_only(w) for w in req.get("query", "").replace(H.MAQAF, " ").split()]
    words = [w for w in words if w]
    if not words:
        raise ValueError("יש להזין מילים")
    ids, index = layer.word_types(exact)
    elements = []
    for w in words:
        key = w if exact else H.normalize_finals(w)
        elements.append(Element(word_type=index.get(key, -2), label=w))
    offs, skip_label = _skips(req, len(elements))
    space = space_for(corpus, layer, "words")
    spec = SearchSpec(elements, offs, boundary=req.get("boundary", "none"))
    starts = run_search(space, spec, scope, ntable, word_type_ids=ids)
    res = []
    for s in starts[offset:offset + limit].tolist():
        ws = [s + o for o in offs]
        r = span_result(corpus, layer, ws[0], ws[-1] + 1, steps=[skip_label])
        r["words"] = ws
        res.append(r)
    return {"total": int(len(starts)), "results": res,
            "settings": _settings(req, layer, scope, {"query": words, "skips": req.get("skips") or [1]})}


# ----------------------------------------------------------------------------
# skip scans
# ----------------------------------------------------------------------------

def estimate_scan(corpus, req: dict) -> dict:
    layer, scope, ntable, exact, _, _ = _ctx(corpus, req)
    query = H.letters_only(req.get("query", ""))
    k = len(query)
    unit = req.get("unit", "words")
    space = space_for(corpus, layer, unit)
    n_units = int((scope.range_id[space.verse_of] >= 0).sum())
    lo, hi = int(req.get("skip_min", 1)), int(req.get("skip_max", 50))
    r = hi - lo + 1
    if req.get("variable"):
        paths = r ** max(k - 1, 0)
    else:
        paths = r
    elements = letter_elements(query, exact, req.get("selector", "first"))
    freqs = [float(space.element_match(e, ntable).mean()) for e in elements]
    expected = n_units * paths * float(np.prod(freqs)) if freqs else 0.0
    return {
        "letters": k, "units_in_scope": n_units, "skip_range": [lo, hi], "variable": bool(req.get("variable")),
        "skip_patterns": int(paths), "positions_times_patterns": int(n_units) * int(paths),
        "expected_matches_estimate": expected,
        "explanation": (f"{'דילוגים משתנים' if req.get('variable') else 'דילוג קבוע'}: "
                        f"{r} ערכי דילוג{' לכל מרווח' if req.get('variable') else ''} → {paths:,} תבניות דילוג; "
                        f"× {n_units:,} נקודות התחלה = {n_units * paths:,} בדיקות. "
                        f"אומדן התאמות (לפי שכיחות האותיות): {expected:,.1f}"),
    }


def constant_skip_scan(corpus, req: dict, progress=None, cancel=None, resume_from: int | None = None) -> dict:
    """Check every constant skip in [skip_min, skip_max]. Returns counts per
    skip and the first results for each skip."""
    layer, scope, ntable, exact, limit, _ = _ctx(corpus, req)
    query = H.letters_only(req.get("query", ""))
    unit = req.get("unit", "words")
    selector = req.get("selector", "first")
    elements = letter_elements(query, exact, selector)
    space = space_for(corpus, layer, unit)
    matches = [space.element_match(e, ntable) for e in elements]
    lo, hi = int(req.get("skip_min", 1)), int(req.get("skip_max", 50))
    per_result = int(req.get("results_per_skip", 5))
    boundary = req.get("boundary", "none")
    rows, total = [], 0
    start_d = resume_from if resume_from is not None else lo
    directions = [("forward", elements, matches)]
    if req.get("reverse"):
        directions.append(("reverse", list(reversed(elements)), list(reversed(matches))))
    for d in range(start_d, hi + 1):
        if cancel and cancel():
            return {"status": "cancelled", "next_skip": d, "rows": rows, "total": total}
        for name, els, ms in directions:
            offs = [j * d for j in range(len(els))]
            starts = run_search(space, SearchSpec(els, offs, boundary=boundary), scope, ntable, matches=ms)
            if len(starts):
                total += len(starts)
                rows.append({"skip": d, "direction": name, "count": int(len(starts)),
                             "results": positional_results(corpus, layer, space, starts, offs, els, per_result,
                                                           reverse=name == "reverse", ntable=ntable,
                                                           skip_label=f"דילוג קבוע: {d}")})
        if progress:
            progress((d - lo + 1) / (hi - lo + 1), d)
    return {"status": "done", "rows": rows, "total": total, "complete": True,
            "settings": _settings(req, layer, scope, {"query": query, "unit": unit, "selector": selector,
                                                     "skip_range": [lo, hi], "boundary": boundary})}


def variable_skip_scan(corpus, req: dict, progress=None, cancel=None, max_rows: int = 5_000_000,
                       state: dict | None = None) -> dict:
    """Every combination of skips in [skip_min, skip_max] for every gap.

    Vectorised breadth-first expansion: positions matching letter 1, then
    every reachable position of letter 2, and so on. A path is dropped as soon
    as a letter fails, so the work is proportional to the partial matches,
    not to the number of skip combinations.
    """
    layer, scope, ntable, exact, limit, _ = _ctx(corpus, req)
    query = H.letters_only(req.get("query", ""))
    unit = req.get("unit", "words")
    elements = letter_elements(query, exact, req.get("selector", "first"))
    space = space_for(corpus, layer, unit)
    matches = [space.element_match(e, ntable) for e in elements]
    lo, hi = int(req.get("skip_min", 1)), int(req.get("skip_max", 20))
    d = np.arange(lo, hi + 1, dtype=np.int64)
    n = space.n
    rid = scope.range_id[space.verse_of]
    g = space.group(req.get("boundary", "none"))
    starts0 = np.nonzero(matches[0] & (rid >= 0))[0]
    chunk = max(1, int(req.get("chunk", 2000)))
    state = state if state is not None else {}
    found_paths = state.setdefault("found_paths", [])
    total = state.get("total", 0)
    truncated = state.get("truncated", False)
    n_chunks = (len(starts0) + chunk - 1) // chunk
    for ci in range(state.get("next_chunk", 0), n_chunks):
        if cancel and cancel():
            state.update(next_chunk=ci, total=total, truncated=truncated)
            return {"status": "cancelled", "total_so_far": total, "state": state}
        st = starts0[ci * chunk:(ci + 1) * chunk]
        paths = st[:, None]
        for j in range(1, len(elements)):
            nxt = paths[:, -1:] + d[None, :]
            rep = np.repeat(paths, len(d), axis=0)
            nxt = nxt.reshape(-1)
            ok = nxt < n
            rep, nxt = rep[ok], nxt[ok]
            ok = matches[j][nxt] & (rid[nxt] == rid[rep[:, 0]])
            if g is not None:
                ok &= g[nxt] == g[rep[:, 0]]
            paths = np.concatenate([rep[ok], nxt[ok][:, None]], axis=1)
            if len(paths) > max_rows:
                truncated = True
                paths = paths[:max_rows]
        total += len(paths)
        if len(found_paths) < limit and len(paths):
            found_paths.extend(paths[: limit - len(found_paths)].tolist())
        state.update(next_chunk=ci + 1, total=total, truncated=truncated)
        if progress:
            progress((ci + 1) / max(n_chunks, 1), ci)
    results = []
    for path in found_paths:
        offs = [p - path[0] for p in path]
        skips = [offs[i + 1] - offs[i] for i in range(len(offs) - 1)]
        r = positional_results(corpus, layer, space, np.array([path[0]]), offs, elements, 1, ntable=ntable,
                               skip_label="דילוגים: " + ", ".join(map(str, skips)))[0]
        r["skips"] = skips
        results.append(r)
    return {"status": "done", "total": int(total), "complete": not truncated, "results": results,
            "settings": _settings(req, layer, scope, {"query": query, "unit": unit, "skip_range": [lo, hi],
                                                     "variable": True})}


# ----------------------------------------------------------------------------
# niqqud searches
# ----------------------------------------------------------------------------

def parse_query_niqqud(text: str, ntable: NiqqudTable) -> list[dict]:
    words = parse_text(text)
    units = [u for w in words for u in w]
    return [{"letter": u.char, "combo": u.combo, "vowels_he": combo_hebrew(u.combo),
             "value": ntable.combo_value(u.combo), "flags": sorted(u.flags)} for u in units]


def niqqud_elements(qunits: list[dict], match: str, exact_finals: bool, merge_qq: bool,
                    selector: str = "first") -> list[Element]:
    els = []
    for q in qunits:
        el = Element(selector=selector, label=f"{q['letter']} · {q['vowels_he']}")
        if match in ("letters", "letters_niqqud", "letters_value"):
            el.letters = H.letter_lut(q["letter"], exact_finals)
        if match in ("niqqud", "letters_niqqud"):
            el.combos = combo_lut_for(q["combo"], merge_qq)
        if match in ("value", "letters_value"):
            el.value = q["value"]
        els.append(el)
    return els


def niqqud_search(corpus, req: dict) -> dict:
    """Search the niqqud of a pointed query word along word heads/tails,
    verse heads/tails, or letters (whole words or anywhere)."""
    t0 = time.time()
    layer, scope, ntable, exact, limit, offset = _ctx(corpus, req)
    qunits = parse_query_niqqud(req.get("query", ""), ntable)
    if not qunits:
        raise ValueError("יש להזין מילה מנוקדת")
    match = req.get("match", "niqqud")
    unit = req.get("unit", "words")
    selector = req.get("selector", "first")
    merge_qq = req.get("merge_qamats_qatan", True)
    elements = niqqud_elements(qunits, match, exact, merge_qq, selector)
    offs, skip_label = _skips(req, len(elements))
    space = space_for(corpus, layer, unit)
    spec = SearchSpec(elements, offs, boundary=req.get("boundary", "none"),
                      whole_word=bool(req.get("whole_word")), full_verse=bool(req.get("full_verse")),
                      anchor=req.get("anchor") or None, anchor_skip=int(req.get("anchor_skip", 0)))
    starts = run_search(space, spec, scope, ntable)
    results = positional_results(corpus, layer, space, starts, offs, elements, limit, offset,
                                 ntable=ntable, skip_label=skip_label)
    match_he = {"niqqud": "ניקוד בלבד (ללא תלות באותיות)", "letters_niqqud": "אותיות וניקוד יחד",
                "value": "ערכי ניקוד לפי הסדר", "letters_value": "אותיות + ערכי ניקוד",
                "letters": "אותיות בלבד"}[match]
    return {
        "total": int(len(starts)), "results": results, "query_analysis": qunits,
        "query_signature": [q["combo"] for q in qunits],
        "query_values": [q["value"] for q in qunits],
        "settings": _settings(req, layer, scope, {
            "unit": unit, "selector": selector, "match": match, "match_he": match_he,
            "merge_qamats_qatan": merge_qq, "skips": req.get("skips") or [1], "offsets": offs,
            "boundary": req.get("boundary", "none"), "whole_word": bool(req.get("whole_word")),
            "full_verse": bool(req.get("full_verse")), "niqqud_table": ntable.values}),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
    }


def _unit_values(space, layer, selector, ntable) -> np.ndarray:
    lut = ntable.combo_lut()
    L = space.letter_of[selector]
    return np.where(L >= 0, lut[layer.l_combo[np.maximum(L, 0)]], 0).astype(np.int64)


def _letter_values(method_id, params, layer, ntable):
    m = get_method(method_id)
    return m, m.resolve(params), m.letter_array(layer, m.resolve(params), ntable)


def niqqud_sum_search(corpus, req: dict) -> dict:
    """Searches by the *sum* of niqqud values.

    ``kind``:
      * ``word``         — words whose niqqud sum equals the target;
      * ``heads``        — runs of word heads (or tails) whose niqqud values sum to the target;
      * ``verse_heads``  — runs of verse heads/tails, with skips;
      * ``in_verse``     — inside verses: ``verse_total`` / ``run`` / ``single_word`` / ``word_heads`` / ``word_tails``.

    ``compare``: ``niqqud`` (corpus niqqud gematria, the default) or
    ``letters`` (corpus letter gematria, standard method) — the two kinds of
    results are always labelled separately.
    The target is the niqqud sum of ``query`` unless ``target`` is given.
    """
    t0 = time.time()
    layer, scope, ntable, exact, limit, offset = _ctx(corpus, req)
    qunits = parse_query_niqqud(req.get("query", ""), ntable) if req.get("query") else []
    target = int(req["target"]) if req.get("target") not in (None, "") else sum(q["value"] for q in qunits)
    kind = req.get("kind", "word")
    compare = req.get("compare", "niqqud")
    method_id = "niqqud" if compare == "niqqud" else req.get("letters_method", "standard")
    m = get_method(method_id)
    p = m.resolve(req.get("method_params"))
    lv = m.letter_array(layer, p, ntable)
    rid = scope.range_id
    results, total = [], 0
    label = {"niqqud": "גימטריית ניקוד מול גימטריית ניקוד", "letters": "גימטריית ניקוד מול גימטריית אותיות"}[compare]
    if kind == "word":
        vals = m.span_values(layer, np.arange(layer.n_words), np.arange(1, layer.n_words + 1), p, ntable, lv)
        ok = (vals == target) & (rid[layer.word_verse] >= 0)
        hits = np.nonzero(ok)[0]
        total = len(hits)
        for w in hits[offset:offset + limit].tolist():
            calc = m.compute(parse_text(layer.word_text[w], layer.maqaf == "join"), p, ntable)
            results.append(span_result(corpus, layer, w, w + 1, int(vals[w]), calc["steps"]))
    elif kind in ("heads", "verse_heads"):
        unit = "words" if kind == "heads" else "verses"
        selector = req.get("selector", "first")
        space = space_for(corpus, layer, unit)
        if compare == "niqqud":
            uv = _unit_values(space, layer, selector, ntable)
        else:
            L = space.letter_of[selector]
            uv = np.where(L >= 0, lv[np.maximum(L, 0)], 0)
        length = int(req.get("length") or len(qunits) or 1)
        offs, skip_label = _skips(req, length)
        n = space.n
        last = offs[-1]
        cand = np.arange(max(n - last, 0))
        sums = np.zeros(len(cand), dtype=np.int64)
        for o in offs:
            sums += uv[cand + o]
        urid = rid[space.verse_of]
        ok = (sums == target) & (urid[cand] >= 0) & (urid[cand] == urid[cand + last])
        g = space.group(req.get("boundary", "none"))
        if g is not None:
            ok &= g[cand] == g[cand + last]
        hits = cand[ok]
        total = len(hits)
        els = [Element(selector=selector) for _ in offs]
        results = positional_results(corpus, layer, space, hits, offs, els, limit, offset, ntable=ntable,
                                     skip_label=skip_label)
        for r in results:
            vals = [int(uv[u]) for u in r["units"]]
            r["steps"].append("ערכים: " + " + ".join(map(str, vals)) + f" = {sum(vals)}")
    elif kind == "in_verse":
        sub = req.get("sub", "verse_total")
        results, total = _in_verse(corpus, layer, m, p, ntable, lv, target, sub, scope, limit, offset)
    else:
        raise ValueError(f"unknown kind {kind}")
    return {"total": int(total), "target": target, "results": results, "query_analysis": qunits,
            "comparison": label,
            "settings": _settings(req, layer, scope, {"kind": kind, "compare": compare, "method": method_id,
                                                     "sub": req.get("sub"), "skips": req.get("skips") or [1],
                                                     "niqqud_table": ntable.values}),
            "elapsed_ms": round((time.time() - t0) * 1000, 1)}


def _in_verse(corpus, layer, m, p, ntable, lv, target, sub, scope, limit, offset):
    """Searches inside each verse (spec section 10, search 4)."""
    ws, wc = layer.verse_wstart, layer.verse_wcount
    in_scope = scope.mask & (wc > 0)
    vidx = np.nonzero(in_scope)[0]
    word_vals = m.span_values(layer, np.arange(layer.n_words), np.arange(1, layer.n_words + 1), p, ntable, lv)
    hits: list[tuple[int, int, int]] = []  # (verse, w0, w1)
    if sub == "verse_total":
        vals = m.span_values(layer, ws[vidx], ws[vidx] + wc[vidx], p, ntable, lv)
        hits = [(int(v), int(ws[v]), int(ws[v] + wc[v])) for v in vidx[vals == target]]
    elif sub == "single_word":
        for w in np.nonzero(word_vals == target)[0].tolist():
            v = int(layer.word_verse[w])
            if in_scope[v]:
                hits.append((v, w, w + 1))
    elif sub in ("word_heads", "word_tails"):
        sel = layer.word_first if sub == "word_heads" else layer.word_last
        per_word = lv[sel]
        cs = np.concatenate([[0], np.cumsum(per_word)])
        vals = cs[ws[vidx] + wc[vidx]] - cs[ws[vidx]]
        hits = [(int(v), int(ws[v]), int(ws[v] + wc[v])) for v in vidx[vals == target]]
    elif sub == "run":
        if m.post is not None or m.weighting(p) != "none":
            raise ValueError("חיפוש רצף מילים בתוך פסוק נתמך לשיטות חיבוריות בלבד")
        cs = np.concatenate([[0], np.cumsum(word_vals)]).tolist()
        for v in vidx.tolist():
            s, e = int(ws[v]), int(ws[v] + wc[v])
            seen: dict[int, list[int]] = {}
            for j in range(s, e + 1):
                for i in seen.get(cs[j] - target, []):
                    if j > i:
                        hits.append((v, i, j))
                seen.setdefault(cs[j], []).append(j)
    else:
        raise ValueError(f"unknown in-verse search {sub}")
    out = []
    for v, w0, w1 in hits[offset:offset + limit]:
        steps = [f"{layer.word_text[w]} = {int(word_vals[w])}" for w in range(w0, w1)][:40]
        if sub in ("word_heads", "word_tails"):
            sel = layer.word_first if sub == "word_heads" else layer.word_last
            steps = [f"{layer.word_text[w]}: {H.ALL_LETTERS[int(layer.l_code[sel[w]])]} = {int(lv[sel[w]])}"
                     for w in range(w0, w1)]
        r = span_result(corpus, layer, w0, w1, None, steps)
        r["value"] = target
        out.append(r)
    return out, len(hits)


# ----------------------------------------------------------------------------
# gematria
# ----------------------------------------------------------------------------

def gematria_value(text: str, method_id: str, params: dict | None = None, ntable: NiqqudTable | None = None,
                   join_maqaf: bool = False) -> dict:
    m = get_method(method_id)
    out = m.compute(parse_text(text, join_maqaf), params, ntable)
    out["name_he"] = m.name_he
    return out


def gematria_search(corpus, req: dict) -> dict:
    """Words, runs of n words, or whole verses whose value equals the target."""
    t0 = time.time()
    layer, scope, ntable, exact, limit, offset = _ctx(corpus, req)
    method_id = req.get("method", "standard")
    m = get_method(method_id)
    p = m.resolve(req.get("params"))
    query_calc = None
    if req.get("target") not in (None, ""):
        target = int(req["target"])
    else:
        src_method = req.get("query_method", method_id)
        query_calc = gematria_value(req.get("query", ""), src_method, req.get("query_params", req.get("params")), ntable,
                                    layer.maqaf == "join")
        target = query_calc["value"]
    span = req.get("span", "words")
    lv = m.letter_array(layer, p, ntable)
    hits: list[tuple[int, int]] = []
    counts = {}
    if span == "verse":
        ws, wc = layer.verse_wstart, layer.verse_wcount
        vidx = np.nonzero(scope.mask & (wc > 0))[0]
        vals = m.span_values(layer, ws[vidx], ws[vidx] + wc[vidx], p, ntable, lv)
        hits = [(int(ws[v]), int(ws[v] + wc[v])) for v in vidx[np.asarray(vals == target, dtype=bool)]]
        counts["verse"] = len(hits)
    else:
        n_min, n_max = int(req.get("n_min", 1)), int(req.get("n_max", req.get("n_min", 1)))
        cross = bool(req.get("cross_verses", False))
        wrid = scope.range_id[layer.word_verse]
        for n in range(n_min, n_max + 1):
            if n > layer.n_words:
                break
            starts = np.arange(layer.n_words - n + 1)
            vals = m.span_values(layer, starts, starts + n, p, ntable, lv)
            ok = np.asarray(vals == target, dtype=bool) & (wrid[starts] >= 0) & (wrid[starts] == wrid[starts + n - 1])
            if not cross:
                ok &= layer.word_verse[starts] == layer.word_verse[starts + n - 1]
            hs = starts[ok]
            counts[n] = int(len(hs))
            hits.extend((int(s), int(s) + n) for s in hs)
    results = []
    for w0, w1 in hits[offset:offset + limit]:
        calc = m.compute(parse_text(" ".join(layer.word_text[w] for w in range(w0, w1)), layer.maqaf == "join"), p, ntable)
        results.append(span_result(corpus, layer, w0, w1, calc["value"], calc["steps"]))
    return {"total": len(hits), "counts_by_length": counts, "target": target, "query_calculation": query_calc,
            "method": m.to_dict(), "results": results,
            "settings": _settings(req, layer, scope, {"method": method_id, "params": p, "span": span,
                                                     "n_min": req.get("n_min", 1), "n_max": req.get("n_max", req.get("n_min", 1)),
                                                     "cross_verses": bool(req.get("cross_verses", False))}),
            "elapsed_ms": round((time.time() - t0) * 1000, 1)}


def gematria_all(corpus, req: dict) -> dict:
    """The query's value in every selected method and the number of matching
    words (and runs of words) in the scope, per method."""
    t0 = time.time()
    layer, scope, ntable, exact, _, _ = _ctx(corpus, req)
    methods = req.get("methods") or [k for k, m in GEMATRIA.items() if m.category != "custom"] + \
        [k for k, m in GEMATRIA.items() if m.category == "custom"]
    n_max = int(req.get("n_max", 1))
    query = req.get("query", "")
    words = parse_text(query, layer.maqaf == "join")
    if not words:
        raise ValueError("יש להזין מילה או ביטוי")
    wrid = scope.range_id[layer.word_verse]
    rows = []
    for mid in methods:
        m = get_method(mid)
        p = m.resolve((req.get("params") or {}).get(mid))
        calc = m.compute(words, p, ntable)
        target = calc["value"]
        lv = m.letter_array(layer, p, ntable)
        counts = {}
        for n in range(1, n_max + 1):
            starts = np.arange(layer.n_words - n + 1)
            vals = m.span_values(layer, starts, starts + n, p, ntable, lv)
            ok = np.asarray(vals == target, dtype=bool) & (wrid[starts] >= 0) & \
                (layer.word_verse[starts] == layer.word_verse[starts + n - 1])
            counts[n] = int(ok.sum())
        rows.append({"method": mid, "name_he": m.name_he, "category": m.category, "value": target,
                     "counts": counts, "total": sum(counts.values()), "steps": calc["steps"], "params": p})
    return {"rows": rows, "complete": True, "methods_checked": len(rows),
            "settings": _settings(req, layer, scope, {"query": query, "n_max": n_max}),
            "elapsed_ms": round((time.time() - t0) * 1000, 1)}


# ----------------------------------------------------------------------------
# transformations
# ----------------------------------------------------------------------------

def transform_text(text: str, tid: str, params: dict | None = None) -> dict:
    t = get_transform(tid)
    out = t.apply(text, params)
    return {"id": tid, "name_he": t.name_he, "input": text, "output": out, "params": t.resolve(params),
            "table": t.table(params)}


SEARCH_MODES = {
    "word": ("מילה שלמה", {"unit": "letters", "whole_word": True}),
    "sequence": ("רצף אותיות", {"unit": "letters"}),
    "heads": ("ראשי תיבות", {"unit": "words", "selector": "first"}),
    "tails": ("סופי תיבות", {"unit": "words", "selector": "last"}),
    "verse_heads": ("ראשי פסוקים", {"unit": "verses", "selector": "first"}),
    "verse_tails": ("סופי פסוקים", {"unit": "verses", "selector": "last"}),
}


def search_by_mode(corpus, req: dict, query: str) -> dict:
    mode = req.get("search_mode", "word")
    if mode not in SEARCH_MODES:
        raise ValueError(f"unknown search mode {mode}")
    sub = dict(req)
    sub.update(SEARCH_MODES[mode][1])
    sub["query"] = query
    return letter_search(corpus, sub)


def transform_search(corpus, req: dict) -> dict:
    tr = transform_text(req.get("query", ""), req.get("transformation", "atbash"), req.get("transform_params"))
    res = search_by_mode(corpus, req, H.letters_only(tr["output"]))
    res["transformation"] = tr
    return res


def transform_all(corpus, req: dict) -> dict:
    """Apply every transformation (and every one of the 22 cyclic shifts) and
    count the matches of the selected search mode."""
    t0 = time.time()
    query = req.get("query", "")
    variants: list[tuple[str, str, dict]] = []
    for tid, t in TRANSFORMS.items():
        if tid in ("shift",):
            continue
        variants.append((tid, t.name_he, {}))
    if req.get("include_shifts", True):
        for n in range(1, 22):
            variants.append(("shift", f"הזזה מחזורית קדימה ב־{n}", {"n": n, "cyclic": True, "finals": "normalize"}))
    rows = []
    for tid, name, params in variants:
        tr = transform_text(query, tid, params)
        q = H.letters_only(tr["output"])
        sub = dict(req)
        sub["limit"] = 0
        res = search_by_mode(corpus, sub, q)
        rows.append({"transformation": tid, "name_he": name, "params": params, "output": tr["output"],
                     "count": res["total"]})
    return {"rows": rows, "complete": True, "variants_checked": len(rows),
            "search_mode": req.get("search_mode", "word"),
            "search_mode_he": SEARCH_MODES[req.get("search_mode", "word")][0],
            "elapsed_ms": round((time.time() - t0) * 1000, 1)}


def all_shifts(text: str, finals: str = "keep") -> list[dict]:
    t = get_transform("shift")
    return [{"n": n, "output": t.apply(text, {"n": n, "cyclic": True, "finals": finals})} for n in range(22)]
