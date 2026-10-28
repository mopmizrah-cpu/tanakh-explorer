"""Letter × niqqud analysis over any scope.

Rows are letters (22, or 27 with final forms kept apart); columns are the
vowel classes plus "no vowel" and "several vowels on one letter". Every cell
can be opened to list the matching occurrences.
"""

from __future__ import annotations

import numpy as np

from .. import hebrew as H
from ..corpus.books import BOOKS
from ..corpus.scope import resolve_scope
from ..gematria import get as get_method
from ..niqqud import VOWEL_CLASSES, VOWEL_HEBREW, combo_hebrew
from ..niqqud_gematria import NiqqudTable
from ..search.results import build_display

COLUMNS = ["patah", "qamats", "qamats_qatan", "tsere", "segol", "holam", "hiriq", "sheva", "qubuts",
           "shuruq", "hataf_patah", "hataf_qamats", "hataf_segol", "vav_dagesh_unclear", "multiple", "none"]
COLUMN_HE = {**VOWEL_HEBREW, "multiple": "כמה תנועות על אות אחת", "none": "ללא תנועה מסומנת"}
POSITIONS = {"any": "כל מיקום", "first": "אות ראשונה במילה", "middle": "אמצע מילה", "last": "אות אחרונה במילה"}


def _column_of_combo() -> np.ndarray:
    """Column index for every combination id."""
    from ..niqqud import MAX_COMBO
    out = np.full(MAX_COMBO, COLUMNS.index("multiple"), dtype=np.int16)
    out[0] = COLUMNS.index("none")
    for name, idx, _ in VOWEL_CLASSES:
        out[idx] = COLUMNS.index(name)
    return out


_COL = _column_of_combo()


def _selection(corpus, req):
    lay = req.get("layer") or {}
    # niqqud statistics default to the qere layer, where every word is pointed
    layer = corpus.layer(lay.get("kq", "qere"), lay.get("maqaf", "split"))
    scope = resolve_scope(corpus, req.get("scope"))
    sel = scope.mask[layer.l_verse]
    pos = req.get("position", "any")
    if pos != "any":
        p = layer.l_pos
        n = layer.word_len[layer.l_word]
        if pos == "first":
            sel &= p == 0
        elif pos == "last":
            sel &= p == n - 1
        elif pos == "middle":
            sel &= (p > 0) & (p < n - 1)
        else:
            raise ValueError(pos)
    return layer, scope, sel


def letter_table(corpus, req: dict) -> dict:
    layer, scope, sel = _selection(corpus, req)
    ntable = NiqqudTable.from_overrides(req.get("niqqud_values"))
    separate_finals = bool(req.get("separate_finals", False))
    codes = layer.l_code if separate_finals else layer.l_base
    n_rows = 27 if separate_finals else 22
    cols = _COL[layer.l_combo]
    idx = codes[sel].astype(np.int64) * len(COLUMNS) + cols[sel]
    counts = np.bincount(idx, minlength=n_rows * len(COLUMNS)).reshape(n_rows, len(COLUMNS))
    nval = ntable.combo_lut()[layer.l_combo]
    std = get_method("standard").letter_array(layer, {}, ntable)
    rows = []
    for r in range(n_rows):
        m = sel & (codes == r)
        niq = int(nval[m].sum())
        g = int(std[m].sum())
        rows.append({
            "letter": H.ALL_LETTERS[r], "total": int(counts[r].sum()),
            "cells": {c: int(counts[r, j]) for j, c in enumerate(COLUMNS)},
            "niqqud_sum": niq, "gematria_sum": g, "combined_sum": niq + g,
        })
    col_totals = {c: int(counts[:, j].sum()) for j, c in enumerate(COLUMNS)}
    total = int(sel.sum())
    return {
        "rows": rows, "columns": [{"id": c, "name_he": COLUMN_HE[c]} for c in COLUMNS],
        "column_totals": col_totals, "total_letters": total,
        "frequency": {c: (v / total if total else 0.0) for c, v in col_totals.items()},
        "niqqud_sum": int(nval[sel].sum()), "gematria_sum": int(std[sel].sum()),
        "combined_sum": int(nval[sel].sum() + std[sel].sum()),
        "settings": {"scope_he": scope.description, "scope": scope.spec, "position": req.get("position", "any"),
                     "position_he": POSITIONS[req.get("position", "any")],
                     "layer": {"kq": layer.kq, "maqaf": layer.maqaf}, "separate_finals": separate_finals,
                     "niqqud_table": ntable.values},
    }


def letter_summary(corpus, req: dict) -> dict:
    """Everything about the niqqud under one letter in a scope: a count for
    every vowel, its share, its niqqud value and sum, and a per-book
    breakdown. With ``separate_finals`` the final form (ם) is counted apart
    from the regular one (מ); otherwise both are counted together."""
    letter = H.letters_only(req.get("letter", ""))[:1]
    if not letter:
        raise ValueError("יש להזין אות עברית אחת")
    separate = bool(req.get("separate_finals", False))
    layer, scope, sel = _selection(corpus, req)
    ntable = NiqqudTable.from_overrides(req.get("niqqud_values"))
    if separate:
        sel = sel & (layer.l_code == H.LETTER_CODE[letter])
        shown = letter
    else:
        sel = sel & (layer.l_base == H.base_index(letter))
        reg = H.FINAL_TO_REGULAR.get(letter, letter)
        fin = H.REGULAR_TO_FINAL.get(reg)
        shown = reg + (f" / {fin}" if fin else "")
    total = int(sel.sum())
    cols = _COL[layer.l_combo]
    counts = np.bincount(cols[sel], minlength=len(COLUMNS))
    nval = ntable.combo_lut()[layer.l_combo]
    sums = np.bincount(cols[sel], weights=nval[sel], minlength=len(COLUMNS))
    single_value = {c: ntable.values[c] for c in COLUMNS if c in ntable.values}
    rows = []
    for j, c in enumerate(COLUMNS):
        rows.append({"column": c, "name_he": COLUMN_HE[c], "count": int(counts[j]),
                     "share": float(counts[j] / total) if total else 0.0,
                     "value": single_value.get(c, 0 if c == "none" else None),
                     "niqqud_sum": int(sums[j])})
    # letters inside ketiv words that the source leaves unpointed
    unpointed = int((sel & (layer.word_role[layer.l_word] == 1)).sum())
    books = corpus.verse_book[layer.l_verse[sel]]
    bycols = cols[sel]
    by_book = []
    for b in np.unique(books).tolist():
        m = books == b
        bc = np.bincount(bycols[m], minlength=len(COLUMNS))
        by_book.append({"book": BOOKS[b].osis, "he": BOOKS[b].he, "total": int(m.sum()),
                        "cells": {c: int(bc[j]) for j, c in enumerate(COLUMNS)}})
    std = get_method("standard").letter_array(layer, {}, ntable)
    return {
        "letter": shown, "total": total, "rows": rows,
        "niqqud_sum": int(nval[sel].sum()), "gematria_sum": int(std[sel].sum()),
        "unpointed_ketiv": unpointed, "by_book": by_book,
        "settings": {"scope_he": scope.description, "position_he": POSITIONS[req.get("position", "any")],
                     "layer": {"kq": layer.kq, "maqaf": layer.maqaf},
                     "layer_he": "כתיב" if layer.kq == "ketiv" else "קרי", "separate_finals": separate,
                     "niqqud_table": ntable.values},
    }


def _cell_mask(corpus, req):
    layer, scope, sel = _selection(corpus, req)
    letter = req.get("letter")
    col = req.get("column")
    if letter:
        if req.get("separate_finals"):
            sel &= layer.l_code == H.LETTER_CODE[letter]
        else:
            sel &= layer.l_base == H.base_index(letter)
    if col:
        sel &= _COL[layer.l_combo] == COLUMNS.index(col)
    return layer, scope, sel


def cell_occurrences(corpus, req: dict) -> dict:
    layer, scope, sel = _cell_mask(corpus, req)
    hits = np.nonzero(sel)[0]
    limit, offset = min(int(req.get("limit", 50)), 500), int(req.get("offset", 0))
    out = []
    for li in hits[offset:offset + limit].tolist():
        w = int(layer.l_word[li])
        out.append({"letter_index": li, "word": layer.word_text[w], "ref": corpus.ref(int(layer.word_verse[w])),
                    "vowels_he": combo_hebrew(int(layer.l_combo[li])),
                    "display": build_display(corpus, layer, [li])})
    return {"total": int(len(hits)), "results": out}


def distribution(corpus, req: dict) -> dict:
    """Counts of the selected letter/vowel per book or per chapter, and by
    position in the word."""
    layer, scope, sel = _cell_mask(corpus, req)
    by = req.get("by", "book")
    verses = layer.l_verse[sel]
    if by == "book":
        books = corpus.verse_book[verses]
        cnt = np.bincount(books, minlength=len(BOOKS))
        allc = np.bincount(corpus.verse_book[layer.l_verse[_selection(corpus, req)[2]]], minlength=len(BOOKS))
        rows = [{"key": BOOKS[i].osis, "label": BOOKS[i].he, "count": int(cnt[i]), "of_letters": int(allc[i]),
                 "rate": float(cnt[i] / allc[i]) if allc[i] else 0.0} for i in range(len(BOOKS)) if allc[i]]
    elif by == "chapter":
        ch = corpus.verse_chapter_id[verses]
        cnt = np.bincount(ch, minlength=int(corpus.verse_chapter_id.max()) + 1)
        rows = []
        first_verse = {}
        for vi in range(len(corpus.verses)):
            first_verse.setdefault(int(corpus.verse_chapter_id[vi]), vi)
        for c in np.nonzero(cnt)[0].tolist():
            r = corpus.ref(first_verse[c])
            rows.append({"key": c, "label": f"{r['book_he']} {r['ref_he'].split()[-1].split(':')[0]}", "count": int(cnt[c])})
    elif by == "position":
        p = layer.l_pos[sel]
        n = layer.word_len[layer.l_word[sel]]
        rows = [{"key": "first", "label": POSITIONS["first"], "count": int((p == 0).sum())},
                {"key": "middle", "label": POSITIONS["middle"], "count": int(((p > 0) & (p < n - 1)).sum())},
                {"key": "last", "label": POSITIONS["last"], "count": int(((p == n - 1) & (n > 1)).sum())},
                {"key": "single", "label": "מילה בת אות אחת", "count": int(((n == 1)).sum())}]
    else:
        raise ValueError(by)
    return {"by": by, "rows": rows, "total": int(sel.sum())}


def compare(corpus, req: dict) -> dict:
    a = letter_table(corpus, {**req, "scope": req.get("scope_a")})
    b = letter_table(corpus, {**req, "scope": req.get("scope_b")})
    letter = req.get("letter")
    rows = []
    for ra, rb in zip(a["rows"], b["rows"]):
        if letter and H.FINAL_TO_REGULAR.get(ra["letter"], ra["letter"]) != H.FINAL_TO_REGULAR.get(letter, letter):
            continue
        cells = {}
        for c in COLUMNS:
            fa = ra["cells"][c] / ra["total"] if ra["total"] else 0.0
            fb = rb["cells"][c] / rb["total"] if rb["total"] else 0.0
            cells[c] = {"a": ra["cells"][c], "b": rb["cells"][c], "share_a": fa, "share_b": fb, "diff": fa - fb}
        rows.append({"letter": ra["letter"], "total_a": ra["total"], "total_b": rb["total"], "cells": cells})
    return {"rows": rows, "columns": a["columns"], "scope_a": a["settings"]["scope_he"],
            "scope_b": b["settings"]["scope_he"], "totals": {"a": a["total_letters"], "b": b["total_letters"]}}


def summary(corpus, req: dict) -> dict:
    """Totals for a scope: verses, words, letters and their sums."""
    layer, scope, sel = _selection(corpus, {**req, "position": "any"})
    ntable = NiqqudTable.from_overrides(req.get("niqqud_values"))
    wsel = scope.mask[layer.word_verse]
    std = get_method("standard").letter_array(layer, {}, ntable)
    nval = ntable.combo_lut()[layer.l_combo]
    flags = layer.l_flags[sel]
    return {
        "scope_he": scope.description, "verses": scope.n_verses,
        "chapters": int(len(np.unique(corpus.verse_chapter_id[scope.mask]))),
        "words": int(wsel.sum()), "letters": int(sel.sum()),
        "gematria_sum": int(std[sel].sum()), "niqqud_sum": int(nval[sel].sum()),
        "large_letters": int((flags & 1 != 0).sum()), "small_letters": int((flags & 2 != 0).sum()),
        "hung_letters": int((flags & 4 != 0).sum()), "dotted_letters": int((flags & 24 != 0).sum()),
        "letter_counts": {H.ALEPHBET[i]: int(c) for i, c in enumerate(np.bincount(layer.l_base[sel], minlength=22))},
        "layer": {"kq": layer.kq, "maqaf": layer.maqaf},
    }
