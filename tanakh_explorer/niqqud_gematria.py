"""Niqqud gematria (גימטריית ניקוד) — the researcher's own value table.

This is a table defined by the user of this system for research purposes;
it is *not* presented as a traditional gematria method.

| vowel        | value |
|--------------|------:|
| patah        |     6 |
| qamats       |    16 |
| tsere        |    20 |
| segol        |    30 |
| sheva        |    20 |
| holam        |    10 |
| hiriq        |    10 |
| qubuts       |    30 |
| shuruq       |    10 |
| hataf patah  |    26 (20 + 6)  |
| hataf qamats |    36 (20 + 16) |
| hataf segol  |    50 (20 + 30) |

Rules: each vowel unit counts once; dagesh, meteg, accents and shin/sin dots
add nothing; a letter with no vowel is the separate state "none" with value 0;
qamats qatan defaults to the qamats value (16) and can be set separately.
A vav whose U+05BC could not be classified reliably (see
:func:`tanakh_explorer.niqqud.classify_word`) gets the configurable value of
``vav_dagesh_unclear``, 0 by default, and is reported by validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .niqqud import COMBO_BASE, MAX_COMBO, VOWEL_HEBREW, VOWEL_INDEX, decode_combo

DEFAULT_VALUES: dict[str, int] = {
    "patah": 6,
    "qamats": 16,
    "tsere": 20,
    "segol": 30,
    "sheva": 20,
    "holam": 10,
    "hiriq": 10,
    "qubuts": 30,
    "shuruq": 10,
    "hataf_patah": 26,
    "hataf_qamats": 36,
    "hataf_segol": 50,
    "qamats_qatan": 16,
    "vav_dagesh_unclear": 0,
}


@dataclass(frozen=True)
class NiqqudTable:
    values: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_VALUES))

    @classmethod
    def from_overrides(cls, overrides: dict[str, int] | None) -> "NiqqudTable":
        vals = dict(DEFAULT_VALUES)
        for k, v in (overrides or {}).items():
            if k not in vals:
                raise ValueError(f"unknown vowel class: {k}")
            vals[k] = int(v)
        return cls(vals)

    def vowel_value(self, vowel: str) -> int:
        return self.values[vowel]

    def combo_value(self, combo: int) -> int:
        return sum(self.values[v] for v in decode_combo(combo))

    def combo_lut(self) -> np.ndarray:
        """Value of every combination id, for vectorised corpus computation."""
        lut = np.zeros(MAX_COMBO, dtype=np.int32)
        single = {VOWEL_INDEX[k]: v for k, v in self.values.items()}
        for code in range(1, MAX_COMBO):
            c, total = code, 0
            ok = True
            while c:
                d = c % COMBO_BASE
                if d == 0 or d not in single:
                    ok = False
                    break
                total += single[d]
                c //= COMBO_BASE
            if ok:
                lut[code] = total
        return lut

    def describe(self) -> list[dict]:
        return [{"vowel": k, "name": VOWEL_HEBREW[k], "value": v} for k, v in self.values.items()]


DEFAULT_TABLE = NiqqudTable()


def word_breakdown(units, table: NiqqudTable = DEFAULT_TABLE) -> dict:
    """Per-letter niqqud values of a parsed word plus their total."""
    rows = []
    total = 0
    for u in units:
        val = sum(table.values[v] for v in u.vowels)
        total += val
        rows.append({
            "letter": u.char,
            "vowels": [VOWEL_HEBREW[v] for v in u.vowels] or [VOWEL_HEBREW["none"]],
            "value": val,
        })
    return {"letters": rows, "total": total}
