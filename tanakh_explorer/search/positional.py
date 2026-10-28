"""The positional search engine.

Every acrostic, skip and niqqud-sequence search reduces to one question:
*at which start positions s does element j match at position s + o_j, for
all j?* — over a sequence of **units**:

* ``letters`` — every letter of the layer, in order;
* ``words``   — every word; each element looks at the word's ``first`` or
  ``last`` letter (ראשי / סופי תיבות);
* ``verses``  — every non-empty verse; ``first`` / ``last`` letter of the
  verse (ראשי / סופי פסוקים).

Distance convention: a skip ``d`` means the selected units are ``d``
positions apart in the unit sequence — ``d = 1`` is consecutive units,
``d = 5`` takes every fifth unit (four units are passed over). Offsets are
cumulative: skips ``[5, 10, 5]`` give offsets ``[0, 5, 15, 20]``.

Boundaries: a match always lies inside one contiguous range of the chosen
scope; optionally it must also stay inside one word / verse / chapter /
book. A *start skip* places the first element ``d0`` units after an anchor
(the start of each scope range, verse or chapter) instead of sliding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

import numpy as np

from .. import hebrew as H
from ..niqqud import MAX_COMBO, VOWEL_NAME, decode_combo, encode_combo
from ..niqqud_gematria import NiqqudTable

UNITS = ("letters", "words", "verses")
BOUNDARIES = ("none", "word", "verse", "chapter", "book")


@dataclass
class Element:
    """What one position of the query has to match. ``None`` = no constraint."""

    letters: np.ndarray | None = None  # bool[27] over letter codes
    combos: np.ndarray | None = None  # bool[MAX_COMBO] over vowel combinations
    value: int | None = None  # niqqud value of the letter's vowels
    word_type: int | None = None  # whole-word identity (phrase search)
    selector: str = "first"  # first | last (for word and verse units)
    label: str = ""

    def describe(self) -> str:
        return self.label


class UnitSpace:
    """Unit sequence of one layer, with the arrays needed for matching."""

    def __init__(self, corpus, layer, unit: str):
        if unit not in UNITS:
            raise ValueError(f"unknown unit {unit}")
        self.corpus, self.layer, self.unit = corpus, layer, unit
        if unit == "letters":
            n = layer.n_letters
            idx = np.arange(n, dtype=np.int64)
            self.letter_of = {"first": idx, "last": idx}
            self.verse_of = layer.l_verse.astype(np.int64)
            self.word_of = layer.l_word.astype(np.int64)
        elif unit == "words":
            self.letter_of = {"first": layer.word_first.astype(np.int64), "last": layer.word_last.astype(np.int64)}
            self.verse_of = layer.word_verse.astype(np.int64)
            self.word_of = np.arange(layer.n_words, dtype=np.int64)
            # words without letters cannot carry a first/last letter
            empty = layer.word_len == 0
            if empty.any():
                for k in self.letter_of:
                    self.letter_of[k] = np.where(empty, -1, self.letter_of[k])
        else:
            ne = layer.verse_nonempty
            self.letter_of = {"first": layer.verse_first_letter[ne], "last": layer.verse_last_letter[ne]}
            self.verse_of = ne.astype(np.int64)
            self.word_of = layer.verse_wstart[ne].astype(np.int64)
        self.n = len(self.verse_of)

    @cached_property
    def chapter_of(self):
        return self.corpus.verse_chapter_id[self.verse_of]

    @cached_property
    def book_of(self):
        return self.corpus.verse_book[self.verse_of]

    def group(self, boundary: str) -> np.ndarray | None:
        if boundary == "none":
            return None
        if boundary == "word":
            if self.unit != "letters":
                raise ValueError("a word boundary applies only to letter units")
            return self.word_of
        if boundary == "verse":
            return self.verse_of
        if boundary == "chapter":
            return self.chapter_of
        if boundary == "book":
            return self.book_of
        raise ValueError(f"unknown boundary {boundary}")

    def element_match(self, el: Element, ntable: NiqqudTable | None = None, word_type_ids=None) -> np.ndarray:
        L = self.letter_of[el.selector]
        valid = L >= 0
        Ls = np.where(valid, L, 0)
        m = valid.copy()
        lay = self.layer
        if el.letters is not None:
            m &= el.letters[lay.l_code[Ls]]
        if el.combos is not None:
            m &= el.combos[lay.l_combo[Ls]]
        if el.value is not None:
            lut = (ntable or NiqqudTable()).combo_lut()
            m &= lut[lay.l_combo[Ls]] == el.value
        if el.word_type is not None:
            if self.unit != "words":
                raise ValueError("word-type elements need word units")
            m &= word_type_ids == el.word_type
        return m


@dataclass
class SearchSpec:
    elements: list[Element]
    offsets: list[int]  # cumulative, offsets[0] == 0
    boundary: str = "none"
    anchor: str | None = None  # None | scope | verse | chapter
    anchor_skip: int = 0  # distance of the first element from the anchor
    whole_word: bool = False  # letters unit: the match is exactly one whole word
    full_verse: bool = False  # words unit: the match covers exactly one whole verse
    meta: dict = field(default_factory=dict)


def offsets_from_skips(skips: list[int], k: int) -> list[int]:
    """Skips between consecutive elements -> cumulative offsets.

    ``skips`` has ``k-1`` entries (variable skips) or one entry (constant)."""
    if k <= 0:
        raise ValueError("empty query")
    if len(skips) == 1:
        skips = skips * (k - 1)
    if len(skips) != k - 1:
        raise ValueError(f"expected {k - 1} skips, got {len(skips)}")
    if any(int(s) < 1 for s in skips):
        raise ValueError("skips must be positive (use the reverse option for backward search)")
    out = [0]
    for s in skips:
        out.append(out[-1] + int(s))
    return out


def run_search(space: UnitSpace, spec: SearchSpec, scope, ntable=None, matches=None,
               word_type_ids=None) -> np.ndarray:
    """Return the array of start positions (unit indices) of all matches."""
    k = len(spec.elements)
    offs = np.asarray(spec.offsets, dtype=np.int64)
    if matches is None:
        matches = [space.element_match(e, ntable, word_type_ids) for e in spec.elements]
    n = space.n
    rid = scope.range_id[space.verse_of]
    if spec.anchor:
        cand = _anchors(space, scope, spec.anchor) + spec.anchor_skip
        cand = cand[(cand >= 0) & (cand < n)]
        cand = cand[matches[0][cand]]
    else:
        cand = np.nonzero(matches[0])[0]
    last = int(offs[-1])
    cand = cand[cand + last < n]
    for j in range(1, k):
        cand = cand[matches[j][cand + offs[j]]]
    # scope: first and last unit in the same scope range (ranges are contiguous)
    end = cand + last
    ok = (rid[cand] >= 0) & (rid[cand] == rid[end])
    if spec.anchor:
        # the anchor itself must lie in the same scope range as the match
        a = cand - spec.anchor_skip
        ok &= rid[a] == rid[cand]
    g = space.group(spec.boundary)
    if g is not None:
        ok &= g[cand] == g[end]
    cand = cand[ok]
    if spec.whole_word:
        lay = space.layer
        w = space.word_of[cand]
        cand = cand[(lay.word_lstart[w] == cand) & (lay.word_len[w] == last + 1)]
    if spec.full_verse:
        lay = space.layer
        v = space.verse_of[cand]
        cand = cand[(lay.verse_wstart[v] == cand) & (lay.verse_wcount[v] == last + 1)]
    return cand


def _anchors(space: UnitSpace, scope, anchor: str) -> np.ndarray:
    """Unit index of every anchor point inside the scope."""
    inside = scope.range_id[space.verse_of] >= 0
    if anchor == "scope":
        key = scope.range_id[space.verse_of]
    elif anchor == "verse":
        key = space.verse_of
    elif anchor == "chapter":
        key = space.chapter_of
    else:
        raise ValueError(f"unknown anchor {anchor}")
    first = np.ones(space.n, dtype=bool)
    first[1:] = key[1:] != key[:-1]
    return np.nonzero(first & inside)[0]


# --- building elements ------------------------------------------------------------


def _valid_combo(code: int) -> bool:
    while code:
        d = code % 16
        if d == 0 or d not in VOWEL_NAME:
            return False
        code //= 16
    return True


def canonical_combo(code: int, merge_qamats_qatan: bool = True) -> int:
    if not _valid_combo(code):
        return -1  # an id no letter can carry
    vs = decode_combo(code)
    if merge_qamats_qatan:
        vs = tuple("qamats" if v == "qamats_qatan" else v for v in vs)
    return encode_combo(vs)


_CANON_CACHE: dict[bool, np.ndarray] = {}


def combo_canon_table(merge_qamats_qatan: bool = True) -> np.ndarray:
    if merge_qamats_qatan not in _CANON_CACHE:
        _CANON_CACHE[merge_qamats_qatan] = np.array(
            [canonical_combo(c, merge_qamats_qatan) for c in range(MAX_COMBO)], dtype=np.int32)
    return _CANON_CACHE[merge_qamats_qatan]


def combo_lut_for(code: int, merge_qamats_qatan: bool = True) -> np.ndarray:
    canon = combo_canon_table(merge_qamats_qatan)
    return canon == canon[code]


def letter_elements(text: str, exact_finals: bool = False, selector: str = "first",
                    selectors: list[str] | None = None, groups: dict | None = None) -> list[Element]:
    """One element per letter of ``text``. ``groups`` maps a letter to a set of
    letters it may match (e.g. articulation groups)."""
    letters = [ch for ch in text if ch in H.LETTER_CODE]
    out = []
    for i, ch in enumerate(letters):
        allowed = groups.get(H.FINAL_TO_REGULAR.get(ch, ch), ch) if groups else ch
        sel = selectors[i] if selectors else selector
        out.append(Element(letters=H.letter_lut(allowed, exact_finals), selector=sel, label=ch))
    return out
