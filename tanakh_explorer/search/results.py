"""Turn raw match positions into transparent, displayable results.

Every result names the verses and words involved, the letters found, the
exact character spans to highlight inside each pointed word, and a list of
explanation steps ("how was this computed").
"""

from __future__ import annotations

import numpy as np

from .. import hebrew as H
from ..niqqud import combo_hebrew
from ..niqqud_gematria import NiqqudTable


def letter_info(corpus, layer, li: int, ntable: NiqqudTable | None = None) -> dict:
    w = int(layer.l_word[li])
    v = int(layer.word_verse[w])
    combo = int(layer.l_combo[li])
    nt = ntable or NiqqudTable()
    return {
        "letter_index": int(li), "word": w, "verse": v,
        "char": H.ALL_LETTERS[int(layer.l_code[li])],
        "pointed": layer.word_text[w][int(layer.l_cstart[li]):int(layer.l_cend[li])],
        "vowels_he": combo_hebrew(combo), "niqqud_value": nt.combo_value(combo),
        "pos_in_word": int(li - layer.word_lstart[w]) + 1,
    }


def verse_block(corpus, layer, vi: int, highlight: dict[int, list[tuple[int, int]]],
                word_marks: set[int] | None = None) -> dict:
    s, n = int(layer.verse_wstart[vi]), int(layer.verse_wcount[vi])
    words = []
    for w in range(s, s + n):
        words.append({
            "w": w, "text": layer.word_text[w],
            "hl": highlight.get(w, []), "maqaf": bool(layer.word_maqaf[w]),
            "mark": bool(word_marks and w in word_marks),
        })
    return {"ref": corpus.ref(vi), "words": words}


def build_display(corpus, layer, letter_indices: list[int], extra_words: list[int] | None = None,
                  max_verses: int = 12) -> list[dict]:
    """Verses touched by the given letters (and words), with highlight spans."""
    hl: dict[int, list[tuple[int, int]]] = {}
    verses: list[int] = []
    for li in letter_indices:
        w = int(layer.l_word[li])
        hl.setdefault(w, []).append((int(layer.l_cstart[li]), int(layer.l_cend[li])))
        v = int(layer.word_verse[w])
        if v not in verses:
            verses.append(v)
    marks = set(extra_words or [])
    for w in marks:
        v = int(layer.word_verse[w])
        if v not in verses:
            verses.append(v)
    verses.sort()
    blocks = [verse_block(corpus, layer, v, hl, marks) for v in verses[:max_verses]]
    if len(verses) > max_verses:
        blocks.append({"more": len(verses) - max_verses})
    return blocks


def positional_results(corpus, layer, space, starts: np.ndarray, offsets: list[int], elements,
                       limit: int = 200, offset: int = 0, reverse: bool = False,
                       ntable: NiqqudTable | None = None, skip_label: str = "") -> list[dict]:
    out = []
    unit_name = {"letters": "אות", "words": "מילה", "verses": "פסוק"}[space.unit]
    for s in starts[offset:offset + limit].tolist():
        letters, units = [], []
        steps = []
        for j, (o, el) in enumerate(zip(offsets, elements)):
            u = s + o
            li = int(space.letter_of[el.selector][u])
            letters.append(li)
            units.append(int(u))
            info = letter_info(corpus, layer, li, ntable)
            where = corpus.ref(info["verse"])["ref_he"]
            sel = "" if space.unit == "letters" else (" — אות ראשונה" if el.selector == "first" else " — אות אחרונה")
            steps.append(f"{j + 1}. {unit_name} מס׳ {u + 1} ({where}{sel}): «{info['pointed']}» "
                         f"= {info['char']} · {info['vowels_he']}")
        found = "".join(H.ALL_LETTERS[int(layer.l_code[li])] for li in letters)
        if reverse:
            steps.append("החיפוש בוצע בכיוון הפוך (מסוף לתחילה)")
        if skip_label:
            steps.append(skip_label)
        first_v = int(layer.l_verse[letters[0]])
        last_v = int(layer.l_verse[letters[-1]])
        words = sorted({int(layer.l_word[li]) for li in letters})
        out.append({
            "start": int(s), "units": units, "letters": letters, "found": found,
            "from": corpus.ref(first_v), "to": corpus.ref(last_v),
            "words": words,
            "display": build_display(corpus, layer, letters),
            "steps": steps,
        })
    return out


def span_result(corpus, layer, w0: int, w1: int, value=None, steps=None) -> dict:
    """A run of whole words [w0, w1)."""
    letters = list(range(int(layer.word_lstart[w0]), int(layer.word_lstart[w1 - 1] + layer.word_len[w1 - 1])))
    words = list(range(w0, w1))
    v0, v1 = int(layer.word_verse[w0]), int(layer.word_verse[w1 - 1])
    hl_words = {w: [(0, len(layer.word_text[w]))] for w in words}
    blocks = [verse_block(corpus, layer, v, hl_words) for v in range(v0, v1 + 1)][:6]
    return {
        "start": w0, "words": words, "letters_count": len(letters),
        "found": " ".join(layer.word_text[w] for w in words),
        "consonants": " ".join(layer.word_consonants[w] for w in words),
        "from": corpus.ref(v0), "to": corpus.ref(v1), "value": None if value is None else int(value),
        "display": blocks, "steps": steps or [],
    }
