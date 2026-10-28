"""Data for the Tanakh reader and the per-letter analysis panel."""

from __future__ import annotations

from .. import hebrew as H
from ..gematria.tables import STANDARD
from ..niqqud import VOWEL_HEBREW, classify_word, split_letters
from ..niqqud_gematria import NiqqudTable
from .books import BOOK_BY_OSIS
from .sections import KIND_HE, MARKER_KIND

# Tagin (תגין) by the general rule only. Menachot 29b and Shulchan Aruch,
# Orach Chaim 36:3: the seven letters שעטנ״ז ג״ץ take three tagin. A custom
# recorded by the later authorities gives בד״ק חי״ה one tag. Special tagin
# on particular words (Sefer Tagin) are NOT included: no verified digital
# source for them was found, and none is invented.
TAGIN_THREE = set("שעטנזגצןץ")
TAGIN_ONE = set("בדקחיה")
TAGIN_NOTE = ("תגין לפי הכלל בלבד: שעטנ״ז ג״ץ — שלושה תגין (מנחות כט ע״ב; שו״ע או״ח לו, ג); "
              "בד״ק חי״ה — תג אחד לפי מנהג המובא בפוסקים. תגין מיוחדים לפי ספר התגין אינם כלולים, "
              "משום שלא נמצא להם מקור דיגיטלי מאומת.")


def tagin_of(ch: str) -> int:
    if ch in TAGIN_THREE:
        return 3
    if ch in TAGIN_ONE:
        return 1
    return 0


def chapter(corpus, book: str, chap: int) -> dict:
    if book not in BOOK_BY_OSIS:
        raise ValueError(f"unknown book {book}")
    out = []
    for vi, v in enumerate(corpus.verses):
        if v.book != book or v.chapter != chap:
            continue
        atoms = []
        for a in v.atoms:
            atoms.append({"text": a.text, "role": a.role, "kq": a.kq, "maqaf": a.maqaf_after,
                          "implicit_maqaf": a.implicit_maqaf, "after": a.after, "marker": a.marker_before,
                          "slh": {str(k): x for k, x in a.slh.items()}, "qere_first": a.kq_qere_first})
        out.append({
            "index": vi, "ref": corpus.ref(vi), "atoms": atoms,
            "markers_before": [{"marker": m, "kind_he": KIND_HE[MARKER_KIND[m]]} for m in v.markers_before],
            "markers_end": [{"marker": m, "kind_he": KIND_HE[MARKER_KIND[m]]} for m in v.markers_end],
            "notes": v.notes, "good_ending": v.good_ending,
        })
    if not out:
        raise ValueError("פרק לא קיים")
    b = BOOK_BY_OSIS[book]
    return {"book": book, "book_he": b.he, "chapter": chap, "chapters": b.chapters, "verses": out}


def analyze_letters(text: str, ntable: NiqqudTable | None = None) -> list[dict]:
    """Per-letter breakdown of a (pointed) word or phrase."""
    nt = ntable or NiqqudTable()
    words = []
    for raw in text.replace(H.MAQAF, " ").split():
        units, warns = split_letters(raw)
        classify_word(units)
        letters = []
        for u in units:
            letters.append({
                "letter": u.char, "pointed": u.char + u.marks,
                "marks": [{"cp": f"U+{ord(m):04X}", "kind": _mark_kind(m)} for m in u.marks],
                "vowels_he": [VOWEL_HEBREW[x] for x in u.vowels] or [VOWEL_HEBREW["none"]],
                "niqqud_value": sum(nt.values[x] for x in u.vowels), "gematria": STANDARD[u.char],
                "flags": sorted(u.flags), "tagin": tagin_of(u.char),
            })
        if letters:
            words.append({"word": raw, "letters": letters, "warnings": warns,
                          "niqqud_sum": sum(x["niqqud_value"] for x in letters),
                          "gematria_sum": sum(x["gematria"] for x in letters)})
    return words


def _mark_kind(m: str) -> str:
    if H.is_accent(m):
        return "טעם"
    if m in H.VOWEL_POINTS:
        return "תנועה"
    return {H.DAGESH: "דגש / מפיק / נקודת שורוק", H.METEG: "מתג (געיה)", H.RAFE: "רפה",
            H.SHIN_DOT: "נקודת שין", H.SIN_DOT: "נקודת שין שמאלית", H.UPPER_DOT: "נקודה מעל האות (נקודות על אותיות)",
            H.LOWER_DOT: "נקודה מתחת לאות", H.CGJ: "מחבר גרפמות (CGJ)"}.get(m, "סימן")
