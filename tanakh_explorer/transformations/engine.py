"""Hebrew Letter Transformations Engine.

A transformation maps each of the 27 letter forms to a letter form. It is a
text → text operation: niqqud and cantillation stay on the same position
(they belong to the position, not to the letter), and only the letters are
replaced.

Final-form policy (``finals``), chosen per method and overridable:

* ``normalize`` — a final letter is first treated as its regular letter;
* ``keep``      — final letters are left exactly as they are;
* ``own``       — the method maps final forms explicitly (e.g. אי״ק בכ״ר,
  where ך ם ן ף ץ are the hundreds 500–900).

Output policy (``output_finals``): ``word_end`` writes final forms at the
end of each word and regular forms elsewhere; ``as_mapped`` leaves the mapped
forms untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .. import hebrew as H
from ..gematria.engine import ParamSpec

AB = H.ALEPHBET


@dataclass
class Transformation:
    id: str
    name_he: str
    name_en: str
    category: str  # traditional | user_defined | mathematical | custom
    description_he: str
    source_he: str
    build: Callable[[dict], dict[str, str]]  # params -> map over the 27 forms
    finals_default: str = "normalize"
    involution: Callable[[dict], bool] = lambda p: False
    params: list[ParamSpec] = field(default_factory=list)
    examples: list[tuple[str, str]] = field(default_factory=list)

    def resolve(self, params: dict | None) -> dict:
        p = {s.name: s.default for s in self.params}
        p.setdefault("finals", self.finals_default)
        p.setdefault("output_finals", "word_end")
        for k, v in (params or {}).items():
            if k in p:
                p[k] = int(v) if isinstance(p[k], int) and not isinstance(p[k], bool) else v
        return p

    def mapping(self, params: dict | None = None) -> dict[str, str]:
        p = self.resolve(params)
        m = self.build(p)
        out = {}
        for ch in H.ALL_LETTERS:
            if ch in H.FINALS:
                if p["finals"] == "keep":
                    out[ch] = ch
                elif p["finals"] == "own" and ch in m:
                    out[ch] = m[ch]
                else:
                    out[ch] = m[H.FINAL_TO_REGULAR[ch]]
            else:
                out[ch] = m[ch]
        return out

    def apply(self, text: str, params: dict | None = None) -> str:
        p = self.resolve(params)
        m = self.mapping(p)
        chars = []
        letter = None
        for ch in text:
            if ch in H.LETTER_CODE:
                letter = m[ch]
                chars.append(letter)
            elif ch in (H.SHIN_DOT, H.SIN_DOT) and letter != "ש":
                continue  # shin/sin dots identify the letter ש; they do not travel with the position
            else:
                if not H.is_combining_mark(ch):
                    letter = None
                chars.append(ch)
        out = "".join(chars)
        if p["output_finals"] == "word_end" and p["finals"] != "keep":
            out = _word_end_finals(out)
        return out

    def table(self, params: dict | None = None) -> list[dict]:
        m = self.mapping(params)
        return [{"from": k, "to": v} for k, v in m.items()]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name_he": self.name_he, "name_en": self.name_en, "category": self.category,
            "description_he": self.description_he, "source_he": self.source_he,
            "finals_default": self.finals_default, "params": [s.to_dict() for s in self.params],
            "involution": self.involution(self.resolve(None)),
            "examples": [{"in": a, "out": b} for a, b in self.examples],
        }


def _word_end_finals(text: str) -> str:
    """Final forms at the end of each word of two or more letters (a word ends
    at a character that is neither a letter nor a mark); regular forms
    elsewhere. A single-letter word keeps the regular form."""
    out = list(text)
    n = len(out)
    letters_in_word = 0
    for i, ch in enumerate(out):
        if ch not in H.LETTER_CODE:
            if not H.is_combining_mark(ch):
                letters_in_word = 0
            continue
        letters_in_word += 1
        j = i + 1
        while j < n and H.is_combining_mark(out[j]):
            j += 1
        at_end = j >= n or out[j] not in H.LETTER_CODE
        reg = H.FINAL_TO_REGULAR.get(ch, ch)
        out[i] = H.REGULAR_TO_FINAL.get(reg, reg) if at_end and letters_in_word > 1 else reg
    return "".join(out)


REGISTRY: dict[str, Transformation] = {}


def register(t: Transformation) -> Transformation:
    if t.id in REGISTRY:
        raise ValueError(f"duplicate transformation id: {t.id}")
    REGISTRY[t.id] = t
    return t


def get(tid: str) -> Transformation:
    try:
        return REGISTRY[tid]
    except KeyError:
        raise ValueError(f"unknown transformation: {tid}") from None


# --- articulation groups (מוצאות הפה) ------------------------------------------
# Sefer Yetzirah 2:3 (נוסח הגר״א): five groups by place of articulation.
ARTICULATION = {
    "gutturals": ("אותיות הגרון", "אחהע"),
    "labials": ("אותיות השפתיים", "בומפ"),
    "palatals": ("אותיות החיך", "גיכק"),
    "linguals": ("אותיות הלשון", "דטלנת"),
    "dentals": ("אותיות השיניים", "זסשרצ"),
}


def articulation_groups() -> list[dict]:
    return [{"id": k, "name_he": v[0], "letters": v[1]} for k, v in ARTICULATION.items()]


def articulation_group_of(ch: str) -> str:
    r = H.FINAL_TO_REGULAR.get(ch, ch)
    for _, letters in ARTICULATION.values():
        if r in letters:
            return letters
    raise ValueError(ch)
