"""Niqqud analysis: split pointed Hebrew into letters with their own marks,
and classify the vowel (תנועה) attached to each letter.

Principles
----------
* A *letter unit* is one Hebrew letter followed by every combining mark that
  comes after it and before the next letter. Marks are never moved from one
  letter to another.
* Vowel classification looks only at vowel points. Dagesh, meteg, rafe,
  shin/sin dots, cantillation accents and the puncta extraordinaria carry no
  vowel. The one exception is the shuruq (וּ), whose dot is the same code
  point as dagesh (U+05BC) — see :func:`classify_word`.
* A letter may carry more than one vowel (e.g. ירושָׁלַ͏ִם, where the lamed has
  both patah and hiriq). Each vowel is counted once.

Vowel combinations are encoded as integers so they can live in NumPy arrays:
each vowel class has an index 1..15 and a combination of up to three vowels is
``v1 + 16*v2 + 256*v3`` in order of appearance. ``0`` means "no vowel".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import hebrew as H

# --- vowel classes -------------------------------------------------------------
# (id, index, Hebrew name)
VOWEL_CLASSES: list[tuple[str, int, str]] = [
    ("sheva", 1, "שווא"),
    ("hataf_segol", 2, "חטף סגול"),
    ("hataf_patah", 3, "חטף פתח"),
    ("hataf_qamats", 4, "חטף קמץ"),
    ("hiriq", 5, "חיריק"),
    ("tsere", 6, "צירי"),
    ("segol", 7, "סגול"),
    ("patah", 8, "פתח"),
    ("qamats", 9, "קמץ"),
    ("holam", 10, "חולם"),
    ("qubuts", 11, "קובוץ"),
    ("shuruq", 12, "שורוק"),
    ("qamats_qatan", 13, "קמץ קטן"),
    ("vav_dagesh_unclear", 14, "ו׳ דגושה — סיווג לא ודאי"),
]
VOWEL_INDEX = {name: idx for name, idx, _ in VOWEL_CLASSES}
VOWEL_NAME = {idx: name for name, idx, _ in VOWEL_CLASSES}
VOWEL_HEBREW = {name: he for name, _, he in VOWEL_CLASSES}
VOWEL_HEBREW["none"] = "ללא תנועה"

POINT_TO_VOWEL = {
    H.SHEVA: "sheva",
    H.HATAF_SEGOL: "hataf_segol",
    H.HATAF_PATAH: "hataf_patah",
    H.HATAF_QAMATS: "hataf_qamats",
    H.HIRIQ: "hiriq",
    H.TSERE: "tsere",
    H.SEGOL: "segol",
    H.PATAH: "patah",
    H.QAMATS: "qamats",
    H.HOLAM: "holam",
    # Holam haser for vav is a holam written on a consonantal vav (מִצְוֺת).
    # It is the same vowel; the distinction is kept only in the raw marks.
    H.HOLAM_HASER_FOR_VAV: "holam",
    H.QUBUTS: "qubuts",
    H.QAMATS_QATAN: "qamats_qatan",
}

# Sheva written together with a short vowel on one letter is a hataf vowel
# spelled with two points. It is counted once, as the hataf (rule 2 of the spec).
_SPLIT_HATAF = {"patah": "hataf_patah", "qamats": "hataf_qamats", "segol": "hataf_segol"}

COMBO_BASE = 16
MAX_COMBO = COMBO_BASE ** 3  # size of lookup tables over combination ids


def encode_combo(vowels: tuple[str, ...]) -> int:
    code = 0
    for i, v in enumerate(vowels[:3]):
        code += VOWEL_INDEX[v] * (COMBO_BASE ** i)
    return code


def decode_combo(code: int) -> tuple[str, ...]:
    out = []
    while code:
        out.append(VOWEL_NAME[code % COMBO_BASE])
        code //= COMBO_BASE
    return tuple(out)


def combo_hebrew(code: int) -> str:
    vs = decode_combo(code)
    return " + ".join(VOWEL_HEBREW[v] for v in vs) if vs else VOWEL_HEBREW["none"]


@dataclass
class LetterUnit:
    char: str  # the letter exactly as written (final forms preserved)
    marks: str = ""  # all combining marks after it, in source order
    vowels: tuple[str, ...] = ()  # classified vowels, filled by classify_word
    flags: set[str] = field(default_factory=set)  # e.g. {"large"}, {"dot_above"}

    @property
    def code(self) -> int:
        return H.LETTER_CODE[self.char]

    @property
    def combo(self) -> int:
        return encode_combo(self.vowels)

    @property
    def text(self) -> str:
        return self.char + self.marks

    def has(self, mark: str) -> bool:
        return mark in self.marks


def _raw_vowels(marks: str) -> list[str]:
    vs = [POINT_TO_VOWEL[m] for m in marks if m in POINT_TO_VOWEL]
    if "sheva" in vs:
        for short, hataf in _SPLIT_HATAF.items():
            if short in vs:
                vs.remove("sheva")
                vs[vs.index(short)] = hataf
                break
    return vs


def classify_word(units: list[LetterUnit]) -> list[LetterUnit]:
    """Fill ``vowels`` for each letter of one word (atom), in place.

    Shuruq: a vav carrying U+05BC and no vowel point is a shuruq when it is
    the first letter of the word, or when the letter before it carries no
    vowel of its own (as in הוּא, וּבְ…). When the previous letter does carry a
    vowel, U+05BC may be a dagesh ḥazak in a consonantal vav. One case is
    decided by rule: if the next letter is a vav that carries the vowel (a
    shuruq or holam male, as in וַיְצַוּוּ, הַוּוֹת), the dotted vav is a doubled
    consonant with no vowel of its own (two vowels cannot stand without a
    consonant between them). Such letters get no vowel and the flag
    ``consonantal_vav``. Any other case is classified ``vav_dagesh_unclear``
    and flagged ``needs_review`` instead of guessing.
    """
    raw = [_raw_vowels(u.marks) for u in units]
    for i, u in enumerate(units):
        vs = raw[i]
        if u.char == "ו" and H.DAGESH in u.marks and not vs:
            nxt = units[i + 1] if i + 1 < len(units) else None
            if i == 0 or not raw[i - 1]:
                vs = ["shuruq"]
            elif nxt is not None and nxt.char == "ו" and (
                    H.HOLAM in nxt.marks or (H.DAGESH in nxt.marks and not raw[i + 1])):
                vs = []
                u.flags.add("consonantal_vav")
            else:
                vs = ["vav_dagesh_unclear"]
                u.flags.add("needs_review")
        u.vowels = tuple(vs)
        if H.UPPER_DOT in u.marks:
            u.flags.add("dot_above")
        if H.LOWER_DOT in u.marks:
            u.flags.add("dot_below")
    return units


def split_letters(text: str) -> tuple[list[LetterUnit], list[str]]:
    """Split a single atom (no spaces, no maqaf) into letter units.

    Returns the units and a list of warnings (marks with no preceding letter,
    unknown characters).
    """
    units: list[LetterUnit] = []
    warnings: list[str] = []
    for ch in text:
        if ch in H.LETTER_CODE:
            units.append(LetterUnit(ch))
        elif H.is_combining_mark(ch):
            if not units:
                warnings.append(f"orphan mark U+{ord(ch):04X}")
                continue
            units[-1].marks += ch
        else:
            warnings.append(f"unexpected character U+{ord(ch):04X}")
    return units, warnings


def parse_word(text: str) -> list[LetterUnit]:
    """Parse and classify a single pointed word typed by a user."""
    units, _ = split_letters(text)
    return classify_word(units)


_SPACES = {" ", "\t", "\n", "\r", H.SOF_PASUQ, H.PASEQ, "|", ",", "."}
_MAQAFS = {H.MAQAF, "-"}


def parse_text(text: str, join_maqaf: bool = False) -> list[list[LetterUnit]]:
    """Parse user input into words.

    Spaces always separate words. A maqaf separates words too, unless
    ``join_maqaf`` is set, in which case a maqaf compound is one word. Each
    atom (the text between spaces/maqaf) is classified on its own either way,
    exactly as the corpus is, so the shuruq rule never looks across a maqaf.
    """
    words: list[list[LetterUnit]] = []
    cur_word: list[LetterUnit] = []
    atom: list[str] = []

    def end_atom():
        if atom:
            cur_word.extend(parse_word("".join(atom)))
            atom.clear()

    def end_word():
        end_atom()
        if cur_word:
            words.append(list(cur_word))
            cur_word.clear()

    for ch in text:
        if ch in _SPACES:
            end_word()
        elif ch in _MAQAFS:
            if join_maqaf:
                end_atom()
            else:
                end_word()
        else:
            atom.append(ch)
    end_word()
    return words


def signature(units: list[LetterUnit]) -> list[dict]:
    """A transparent description of a word's pointing, one entry per letter."""
    return [
        {
            "letter": u.char,
            "marks": [f"U+{ord(m):04X}" for m in u.marks],
            "vowels": list(u.vowels),
            "vowels_he": [VOWEL_HEBREW[v] for v in u.vowels] or [VOWEL_HEBREW["none"]],
            "combo": u.combo,
            "flags": sorted(u.flags),
        }
        for u in units
    ]
