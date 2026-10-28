"""Hebrew Unicode primitives.

Every component of the system that has to decide "is this a letter?",
"which letter is it?" or "is this a final form?" goes through this module, so
that the definition of a letter is made in exactly one place.

Letter codes
------------
Letters are represented internally by small integers:

* ``0..21``  — the 22 letters in alphabet order (א=0 … ת=21)
* ``22..26`` — the five final forms ך ם ן ף ץ

``BASE[code]`` maps a code to its base letter (0..21), so final forms collapse
onto their regular letter only when a caller asks for it explicitly.
"""

from __future__ import annotations

import numpy as np

ALEPHBET = "אבגדהוזחטיכלמנסעפצקרשת"  # 22 letters, alphabet order
FINALS = "ךםןףץ"  # final forms in alphabet order of their regular letters: כ מ נ פ צ
FINAL_TO_REGULAR = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
REGULAR_TO_FINAL = {v: k for k, v in FINAL_TO_REGULAR.items()}

ALL_LETTERS = ALEPHBET + FINALS  # index == letter code
LETTER_CODE = {ch: i for i, ch in enumerate(ALL_LETTERS)}
N_CODES = len(ALL_LETTERS)  # 27

BASE = np.array(
    [i for i in range(22)] + [ALEPHBET.index(FINAL_TO_REGULAR[f]) for f in FINALS],
    dtype=np.uint8,
)
IS_FINAL = np.array([False] * 22 + [True] * 5)

# --- code points ------------------------------------------------------------
MAQAF = "־"
PASEQ = "׀"
SOF_PASUQ = "׃"
NUN_HAFUKHA = "׆"
CGJ = "͏"
GERESH = "׳"
GERSHAYIM = "״"

SHEVA = "ְ"
HATAF_SEGOL = "ֱ"
HATAF_PATAH = "ֲ"
HATAF_QAMATS = "ֳ"
HIRIQ = "ִ"
TSERE = "ֵ"
SEGOL = "ֶ"
PATAH = "ַ"
QAMATS = "ָ"
HOLAM = "ֹ"
HOLAM_HASER_FOR_VAV = "ֺ"
QUBUTS = "ֻ"
DAGESH = "ּ"  # also mapiq and the shuruq dot
METEG = "ֽ"
RAFE = "ֿ"
SHIN_DOT = "ׁ"
SIN_DOT = "ׂ"
UPPER_DOT = "ׄ"  # puncta extraordinaria
LOWER_DOT = "ׅ"
QAMATS_QATAN = "ׇ"

VOWEL_POINTS = {
    SHEVA, HATAF_SEGOL, HATAF_PATAH, HATAF_QAMATS, HIRIQ, TSERE, SEGOL,
    PATAH, QAMATS, HOLAM, HOLAM_HASER_FOR_VAV, QUBUTS, QAMATS_QATAN,
}


def is_letter(ch: str) -> bool:
    return ch in LETTER_CODE


def is_accent(ch: str) -> bool:
    """Cantillation marks (טעמי המקרא), U+0591..U+05AF."""
    return "֑" <= ch <= "֯"


def is_point(ch: str) -> bool:
    """Niqqud-range points other than the cantillation accents."""
    return ch in VOWEL_POINTS or ch in (DAGESH, METEG, RAFE, SHIN_DOT, SIN_DOT)


def is_combining_mark(ch: str) -> bool:
    """Any mark that attaches to the preceding letter."""
    return (
        is_accent(ch)
        or is_point(ch)
        or ch in (UPPER_DOT, LOWER_DOT, CGJ)
    )


def letters_only(text: str) -> str:
    """The consonantal skeleton of ``text``: Hebrew letters only, in order."""
    return "".join(ch for ch in text if ch in LETTER_CODE)


def strip_marks(text: str) -> str:
    """Remove niqqud and cantillation, keeping letters, spaces and maqaf."""
    return "".join(ch for ch in text if not is_combining_mark(ch))


def normalize_finals(text: str) -> str:
    """Replace final forms by regular letters (ך→כ …). Non-letters are kept."""
    return "".join(FINAL_TO_REGULAR.get(ch, ch) for ch in text)


def apply_final_forms(word: str) -> str:
    """Write the last letter of a word in final form when it has one,
    and every non-final position in regular form."""
    letters = [FINAL_TO_REGULAR.get(ch, ch) for ch in word]
    # find the index of the last Hebrew letter
    for i in range(len(letters) - 1, -1, -1):
        if letters[i] in LETTER_CODE:
            letters[i] = REGULAR_TO_FINAL.get(letters[i], letters[i])
            break
    return "".join(letters)


def codes(text: str) -> list[int]:
    """Letter codes (0..26) of the letters in ``text``, ignoring everything else."""
    return [LETTER_CODE[ch] for ch in text if ch in LETTER_CODE]


def code_to_char(code: int) -> str:
    return ALL_LETTERS[code]


def base_index(ch: str) -> int:
    """Alphabet index 0..21 of a letter; final forms map to their regular letter."""
    return int(BASE[LETTER_CODE[ch]])


def letter_lut(letters: str, exact_finals: bool = False) -> np.ndarray:
    """A boolean lookup table over the 27 letter codes that accepts ``letters``.

    With ``exact_finals=False`` (the default for ordinary search) a regular
    letter and its final form are interchangeable; with ``True`` they are
    distinct, so ``מ`` does not match ``ם``.
    """
    lut = np.zeros(N_CODES, dtype=bool)
    for ch in letters:
        if ch not in LETTER_CODE:
            raise ValueError(f"not a Hebrew letter: {ch!r}")
        c = LETTER_CODE[ch]
        if exact_finals:
            lut[c] = True
        else:
            lut[BASE == BASE[c]] = True
    return lut
