"""The searchable corpus: NumPy arrays over verses, words and letters.

Two independent choices define a *layer* of the text:

* ``kq``    — ``"ketiv"`` (the written text; letters of the ketiv, which MAM
  leaves unpointed) or ``"qere"`` (the read text, pointed);
* ``maqaf`` — ``"split"`` (every atom between spaces/maqaf is a word, the
  usual basis of word counts) or ``"join"`` (a maqaf compound is one word).

Outside ketiv/qere pairs the two kq layers are identical. A layer never
contains both the ketiv and the qere of the same pair, so they are never
treated as two consecutive words. The choice is recorded with every result.

Letter arrays exclude everything that is not a Hebrew letter: niqqud,
cantillation, maqaf, sof pasuq, paseq, parashah markers, verse/chapter
numbers and titles never enter them.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np

from .. import hebrew as H
from ..niqqud import classify_word, split_letters
from .books import BOOK_INDEX, BOOKS
from .structure import Verse

FLAG_BITS = {"large": 1, "small": 2, "hung": 4, "dot_above": 8, "dot_below": 16, "needs_review": 32,
             "consonantal_vav": 64}
ROLE_CODE = {"both": 0, "k": 1, "q": 2}
KQ_MODES = ("ketiv", "qere")
MAQAF_MODES = ("split", "join")


@dataclass
class Layer:
    kq: str
    maqaf: str
    # words
    word_verse: np.ndarray  # int32, verse index of each word
    word_text: list[str]  # display text of each word (pointed, with cantillation)
    word_role: np.ndarray  # uint8 0=both 1=ketiv 2=qere
    word_maqaf: np.ndarray  # bool, joined to the next word by maqaf (display only)
    word_lstart: np.ndarray  # int32, index of first letter
    word_len: np.ndarray  # int32, number of letters
    # letters
    l_code: np.ndarray  # uint8 0..26
    l_base: np.ndarray  # uint8 0..21
    l_combo: np.ndarray  # int16 vowel-combination id
    l_flags: np.ndarray  # uint8 bitmask, see FLAG_BITS
    l_word: np.ndarray  # int32
    l_cstart: np.ndarray  # int32 char offset in the word's display text
    l_cend: np.ndarray
    # verses
    verse_wstart: np.ndarray  # int32
    verse_wcount: np.ndarray  # int32

    @property
    def n_words(self) -> int:
        return len(self.word_verse)

    @property
    def n_letters(self) -> int:
        return len(self.l_code)

    @cached_property
    def l_verse(self) -> np.ndarray:
        return self.word_verse[self.l_word]

    @cached_property
    def l_pos(self) -> np.ndarray:
        """Position of each letter within its word, 0-based."""
        return (np.arange(self.n_letters) - self.word_lstart[self.l_word]).astype(np.int32)

    @cached_property
    def word_first(self) -> np.ndarray:
        return self.word_lstart

    @cached_property
    def word_last(self) -> np.ndarray:
        return self.word_lstart + self.word_len - 1

    @cached_property
    def verse_nonempty(self) -> np.ndarray:
        return np.nonzero(self.verse_wcount > 0)[0]

    @cached_property
    def verse_first_letter(self) -> np.ndarray:
        """First letter index of every verse (−1 for an empty verse)."""
        out = np.full(len(self.verse_wstart), -1, dtype=np.int64)
        ne = self.verse_nonempty
        out[ne] = self.word_lstart[self.verse_wstart[ne]]
        return out

    @cached_property
    def verse_last_letter(self) -> np.ndarray:
        out = np.full(len(self.verse_wstart), -1, dtype=np.int64)
        ne = self.verse_nonempty
        lw = self.verse_wstart[ne] + self.verse_wcount[ne] - 1
        out[ne] = self.word_lstart[lw] + self.word_len[lw] - 1
        return out

    def word_letters(self, w: int) -> str:
        s = self.word_lstart[w]
        return "".join(H.ALL_LETTERS[c] for c in self.l_code[s:s + self.word_len[w]])

    @cached_property
    def word_consonants(self) -> list[str]:
        letters = H.ALL_LETTERS
        codes = self.l_code.tolist()
        starts = self.word_lstart.tolist()
        lens = self.word_len.tolist()
        return ["".join(letters[c] for c in codes[s:s + n]) for s, n in zip(starts, lens)]

    def word_types(self, exact_finals: bool = False) -> tuple[np.ndarray, dict[str, int]]:
        """An integer id per distinct consonant string (phrase search)."""
        key = "_wt_exact" if exact_finals else "_wt_fold"
        if key not in self.__dict__:
            ids: dict[str, int] = {}
            arr = np.empty(self.n_words, dtype=np.int32)
            for i, w in enumerate(self.word_consonants):
                k = w if exact_finals else H.normalize_finals(w)
                arr[i] = ids.setdefault(k, len(ids))
            self.__dict__[key] = (arr, ids)
        return self.__dict__[key]

    @cached_property
    def word_index_by_consonants(self) -> dict[str, list[int]]:
        """Final-insensitive consonant string -> word indices."""
        idx: dict[str, list[int]] = {}
        for i, w in enumerate(self.word_consonants):
            idx.setdefault(H.normalize_finals(w), []).append(i)
        return idx


class Corpus:
    """All verses plus lazily built layers."""

    def __init__(self, verses: list[Verse], source_info: dict | None = None):
        self.verses = verses
        self.source_info = source_info or {}
        n = len(verses)
        self.verse_osis = [v.osis for v in verses]
        self.verse_index = {o: i for i, o in enumerate(self.verse_osis)}
        self.verse_book = np.array([BOOK_INDEX[v.book] for v in verses], dtype=np.int16)
        self.verse_chapter = np.array([v.chapter for v in verses], dtype=np.int16)
        self.verse_num = np.array([v.verse for v in verses], dtype=np.int16)
        chap_key = self.verse_book.astype(np.int32) * 1000 + self.verse_chapter
        change = np.ones(n, dtype=bool)
        change[1:] = chap_key[1:] != chap_key[:-1]
        self.verse_chapter_id = (np.cumsum(change) - 1).astype(np.int32)
        groups = {g: i for i, g in enumerate(dict.fromkeys(b.group for b in BOOKS))}
        self.verse_group = np.array([groups[BOOKS[b].group] for b in self.verse_book], dtype=np.int16)
        self._parse_atoms()
        self._layers: dict[tuple[str, str], Layer] = {}

    # -- atoms ----------------------------------------------------------------
    def _parse_atoms(self):
        a_verse, a_role, a_kq, a_maq, a_text = [], [], [], [], []
        a_lstart, a_llen = [], []
        l_code, l_combo, l_flags, l_cs, l_ce = [], [], [], [], []
        self.parse_warnings: list[str] = []
        for vi, v in enumerate(self.verses):
            for atom in v.atoms:
                units, warns = split_letters(atom.text)
                if warns:
                    self.parse_warnings.extend(f"{v.osis}: {w}" for w in warns)
                classify_word(units)
                a_verse.append(vi)
                a_role.append(ROLE_CODE[atom.role])
                a_kq.append(atom.kq)
                a_maq.append(atom.maqaf_after)
                a_text.append(atom.text)
                a_lstart.append(len(l_code))
                a_llen.append(len(units))
                pos = 0
                for li, u in enumerate(units):
                    # character span of this letter inside the atom text
                    start = atom.text.index(u.char, pos)
                    end = start + 1 + len(u.marks)
                    pos = end
                    flags = 0
                    for f in u.flags:
                        flags |= FLAG_BITS[f]
                    kind = atom.slh.get(li)
                    if kind:
                        flags |= FLAG_BITS[kind]
                    l_code.append(H.LETTER_CODE[u.char])
                    l_combo.append(u.combo)
                    l_flags.append(flags)
                    l_cs.append(start)
                    l_ce.append(end)
        self.a_verse = np.array(a_verse, dtype=np.int32)
        self.a_role = np.array(a_role, dtype=np.uint8)
        self.a_kq = np.array(a_kq, dtype=np.int32)
        self.a_maqaf = np.array(a_maq, dtype=bool)
        self.a_text = a_text
        self.a_lstart = np.array(a_lstart, dtype=np.int32)
        self.a_llen = np.array(a_llen, dtype=np.int32)
        self.al_code = np.array(l_code, dtype=np.uint8)
        self.al_combo = np.array(l_combo, dtype=np.int16)
        self.al_flags = np.array(l_flags, dtype=np.uint8)
        self.al_cstart = np.array(l_cs, dtype=np.int32)
        self.al_cend = np.array(l_ce, dtype=np.int32)

    # -- layers -----------------------------------------------------------------
    def layer(self, kq: str = "ketiv", maqaf: str = "split") -> Layer:
        if kq not in KQ_MODES or maqaf not in MAQAF_MODES:
            raise ValueError(f"bad layer {kq}/{maqaf}")
        key = (kq, maqaf)
        if key not in self._layers:
            self._layers[key] = self._build_layer(kq, maqaf)
        return self._layers[key]

    def _build_layer(self, kq: str, maqaf: str) -> Layer:
        excluded = ROLE_CODE["q"] if kq == "ketiv" else ROLE_CODE["k"]
        atoms = np.nonzero(self.a_role != excluded)[0]
        n_verses = len(self.verses)
        # group atoms into words
        if maqaf == "split":
            word_of_atom = np.arange(len(atoms))
        else:
            joined = self.a_maqaf[atoms][:-1] & (self.a_verse[atoms][1:] == self.a_verse[atoms][:-1])
            starts = np.ones(len(atoms), dtype=bool)
            starts[1:] = ~joined
            word_of_atom = np.cumsum(starts) - 1
        n_words = int(word_of_atom[-1]) + 1 if len(atoms) else 0
        # word display text and character offsets of each atom inside its word
        word_text: list[str] = [""] * n_words
        atom_offset = np.zeros(len(atoms), dtype=np.int32)
        a_text = self.a_text
        prev_w = -1
        for j, a in enumerate(atoms.tolist()):
            w = int(word_of_atom[j])
            if w == prev_w:
                word_text[w] += H.MAQAF
                atom_offset[j] = len(word_text[w])
                word_text[w] += a_text[a]
            else:
                word_text[w] = a_text[a]
                prev_w = w
        first_atom = np.searchsorted(word_of_atom, np.arange(n_words))
        word_verse = self.a_verse[atoms][first_atom].astype(np.int32)
        word_role = self.a_role[atoms][first_atom]
        last_atom = np.concatenate([first_atom[1:] - 1, [len(atoms) - 1]]) if n_words else first_atom
        word_maqaf = self.a_maqaf[atoms][last_atom]
        # letters: concatenate atom letter ranges in order
        lens = self.a_llen[atoms]
        total = int(lens.sum())
        starts_a = self.a_lstart[atoms]
        letter_idx = np.repeat(starts_a - np.concatenate([[0], np.cumsum(lens)[:-1]]), lens) + np.arange(total)
        atom_of_letter = np.repeat(np.arange(len(atoms)), lens)
        l_word = word_of_atom[atom_of_letter].astype(np.int32)
        l_cstart = self.al_cstart[letter_idx] + atom_offset[atom_of_letter]
        l_cend = self.al_cend[letter_idx] + atom_offset[atom_of_letter]
        word_len = np.bincount(l_word, minlength=n_words).astype(np.int32)
        word_lstart = np.concatenate([[0], np.cumsum(word_len)[:-1]]).astype(np.int32)
        verse_wcount = np.bincount(word_verse, minlength=n_verses).astype(np.int32)
        verse_wstart = np.concatenate([[0], np.cumsum(verse_wcount)[:-1]]).astype(np.int32)
        code = self.al_code[letter_idx]
        return Layer(
            kq=kq, maqaf=maqaf,
            word_verse=word_verse, word_text=word_text, word_role=word_role, word_maqaf=word_maqaf,
            word_lstart=word_lstart, word_len=word_len,
            l_code=code, l_base=H.BASE[code], l_combo=self.al_combo[letter_idx],
            l_flags=self.al_flags[letter_idx], l_word=l_word,
            l_cstart=l_cstart.astype(np.int32), l_cend=l_cend.astype(np.int32),
            verse_wstart=verse_wstart, verse_wcount=verse_wcount,
        )

    # -- convenience ----------------------------------------------------------
    def ref(self, verse_idx: int) -> dict:
        b = BOOKS[int(self.verse_book[verse_idx])]
        return {
            "osis": self.verse_osis[verse_idx],
            "book": b.osis,
            "book_he": b.he,
            "chapter": int(self.verse_chapter[verse_idx]),
            "verse": int(self.verse_num[verse_idx]),
            "ref_he": f"{b.he} {hebrew_numeral(int(self.verse_chapter[verse_idx]))}:{hebrew_numeral(int(self.verse_num[verse_idx]))}",
        }

    def verse_display(self, layer: Layer, vi: int) -> list[dict]:
        s, n = int(layer.verse_wstart[vi]), int(layer.verse_wcount[vi])
        return [{"w": w, "text": layer.word_text[w]} for w in range(s, s + n)]


_UNITS = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]
_TENS = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"]
_HUNDREDS = ["", "ק", "ר", "ש", "ת"]


def hebrew_numeral(n: int) -> str:
    """Chapter/verse numbers in Hebrew letters (טו and טז, not יה and יו)."""
    if n <= 0:
        return str(n)
    out = ""
    while n >= 400:
        out += "ת"
        n -= 400
    out += _HUNDREDS[n // 100]
    n %= 100
    if n == 15:
        return out + "טו"
    if n == 16:
        return out + "טז"
    out += _TENS[n // 10] + _UNITS[n % 10]
    return out
