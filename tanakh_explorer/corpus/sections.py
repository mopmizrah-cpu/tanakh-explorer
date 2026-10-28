"""Masoretic sections (פרשות פתוחות וסתומות) and weekly portions as verse
ranges.

A Masoretic section begins at a parashah marker. Most markers stand between
verses; about 170 stand inside a verse (פיסקא באמצע פסוק). Scopes work at
verse granularity, so a section opened by a mid-verse marker starts with the
verse that contains the marker, and the section it closes ends with that same
verse; that verse belongs to both sections and is flagged ``partial``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .books import BOOKS
from .parashot import PARASHOT

MARKER_KIND = {"pe2": "petuha", "pe3": "petuha", "samekh2": "setuma", "samekh3": "setuma"}
KIND_HE = {"petuha": "פתוחה", "setuma": "סתומה", "book_start": "תחילת ספר"}


@dataclass
class Section:
    book: str
    number: int  # 1-based within its book
    kind: str  # petuha / setuma / book_start
    marker: str | None  # raw MAM marker name
    start: int  # first verse index (inclusive)
    end: int  # last verse index (inclusive)
    start_partial: bool
    end_partial: bool

    def to_dict(self, corpus) -> dict:
        return {
            "book": self.book, "number": self.number, "kind": self.kind,
            "kind_he": KIND_HE[self.kind], "marker": self.marker,
            "start": corpus.ref(self.start), "end": corpus.ref(self.end),
            "start_partial": self.start_partial, "end_partial": self.end_partial,
            "verses": self.end - self.start + 1,
        }


def masoretic_sections(corpus) -> list[Section]:
    verses = corpus.verses
    sections: list[Section] = []
    # boundaries: (verse index where the new section starts, marker, partial)
    starts: list[tuple[int, str | None, bool]] = []
    prev_book = None
    pending_end: str | None = None
    for i, v in enumerate(verses):
        if v.book != prev_book:
            starts.append((i, None, False))
            prev_book = v.book
            pending_end = None
        elif v.markers_before:
            starts.append((i, v.markers_before[-1], False))
        elif pending_end:
            starts.append((i, pending_end, False))
        pending_end = None
        for k, a in enumerate(v.atoms):
            if a.marker_before and k > 0:
                starts.append((i, a.marker_before, True))
            elif a.marker_before and k == 0 and not v.markers_before:
                starts.append((i, a.marker_before, False))
        if v.markers_end:
            pending_end = v.markers_end[-1]
    # turn the boundary list into sections
    numbers: dict[str, int] = {}
    for j, (s, marker, partial) in enumerate(starts):
        book = verses[s].book
        if j + 1 < len(starts) and verses[starts[j + 1][0]].book == book:
            nxt, _, nxt_partial = starts[j + 1]
            end = nxt if nxt_partial else nxt - 1
            end_partial = nxt_partial
        else:
            end = s
            while end + 1 < len(verses) and verses[end + 1].book == book:
                end += 1
            end_partial = False
        if j > 0 and starts[j - 1][0] == s and not partial and not starts[j - 1][2]:
            continue  # duplicate boundary at the same verse
        numbers[book] = numbers.get(book, 0) + 1
        kind = MARKER_KIND[marker] if marker else "book_start"
        sections.append(Section(book, numbers[book], kind, marker, s, max(end, s), partial, end_partial))
    return sections


@dataclass
class Parasha:
    name: str
    book: str
    start: int
    end: int
    first_word_expected: str


def weekly_parashot(corpus) -> list[Parasha]:
    out: list[Parasha] = []
    idx = corpus.verse_index
    torah_end = max(i for i, v in enumerate(corpus.verses) if v.book == "Deut")
    for j, (name, book, ch, vs, first) in enumerate(PARASHOT):
        start = idx[f"{book}.{ch}.{vs}"]
        if j + 1 < len(PARASHOT):
            _, b2, c2, v2, _ = PARASHOT[j + 1]
            end = idx[f"{b2}.{c2}.{v2}"] - 1
        else:
            end = torah_end
        out.append(Parasha(name, book, start, end, first))
    return out


def book_names() -> list[dict]:
    return [{"osis": b.osis, "he": b.he, "group": b.group, "section": b.section, "chapters": b.chapters} for b in BOOKS]
