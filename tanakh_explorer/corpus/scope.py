"""Search scopes (תחום חיפוש).

A scope is a union of verse ranges. Each contiguous range gets its own id;
a match must lie entirely inside one range, so a search over "Genesis and
Psalms" never builds a match from the end of Genesis and the start of Psalms.

Spec format (JSON)::

    {"items": [
        {"type": "all"},
        {"type": "section", "value": "torah"},          # torah / neviim / ketuvim
        {"type": "books", "value": ["Gen", "Exod"]},
        {"type": "group", "value": "תרי עשר"},          # one of the 24 books
        {"type": "parasha", "value": "נח"},              # weekly portion
        {"type": "masoretic", "book": "Gen", "number": 3},  # open/closed section
        {"type": "chapters", "book": "Gen", "from": 1, "to": 3},
        {"type": "verses", "from": "Gen.1.1", "to": "Gen.2.3"}
    ]}

An empty or missing spec means the whole Tanakh.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .books import BOOK_BY_OSIS, BOOK_INDEX, BOOKS, SECTION_HE
from .sections import masoretic_sections, weekly_parashot


@dataclass
class Scope:
    mask: np.ndarray  # bool per verse
    range_id: np.ndarray  # int32 per verse, -1 outside the scope
    description: str
    spec: dict

    @property
    def n_verses(self) -> int:
        return int(self.mask.sum())


def _describe(item: dict) -> str:
    t = item.get("type")
    if t == "all":
        return "כל התנ״ך"
    if t == "section":
        return SECTION_HE[item["value"]]
    if t == "books":
        return ", ".join(BOOK_BY_OSIS[b].he for b in item["value"])
    if t == "group":
        return item["value"]
    if t == "parasha":
        return f"פרשת {item['value']}"
    if t == "masoretic":
        return f"{BOOK_BY_OSIS[item['book']].he}, פרשה מסורתית מס׳ {item['number']}"
    if t == "chapters":
        return f"{BOOK_BY_OSIS[item['book']].he} פרקים {item['from']}–{item.get('to', item['from'])}"
    if t == "verses":
        return f"{item['from']} – {item.get('to', item['from'])}"
    return str(item)


def resolve_scope(corpus, spec: dict | None) -> Scope:
    n = len(corpus.verses)
    items = (spec or {}).get("items") or [{"type": "all"}]
    mask = np.zeros(n, dtype=bool)
    for item in items:
        t = item.get("type")
        if t == "all":
            mask[:] = True
        elif t == "section":
            books = [BOOK_INDEX[b.osis] for b in BOOKS if b.section == item["value"]]
            mask |= np.isin(corpus.verse_book, books)
        elif t == "books":
            mask |= np.isin(corpus.verse_book, [BOOK_INDEX[b] for b in item["value"]])
        elif t == "group":
            books = [BOOK_INDEX[b.osis] for b in BOOKS if b.group == item["value"]]
            if not books:
                raise ValueError(f"unknown book group: {item['value']}")
            mask |= np.isin(corpus.verse_book, books)
        elif t == "parasha":
            for p in weekly_parashot(corpus):
                if p.name == item["value"]:
                    mask[p.start:p.end + 1] = True
                    break
            else:
                raise ValueError(f"unknown parasha: {item['value']}")
        elif t == "masoretic":
            for s in masoretic_sections(corpus):
                if s.book == item["book"] and s.number == int(item["number"]):
                    mask[s.start:s.end + 1] = True
                    break
            else:
                raise ValueError("unknown Masoretic section")
        elif t == "chapters":
            b = BOOK_INDEX[item["book"]]
            lo, hi = int(item["from"]), int(item.get("to", item["from"]))
            mask |= (corpus.verse_book == b) & (corpus.verse_chapter >= lo) & (corpus.verse_chapter <= hi)
        elif t == "verses":
            lo = corpus.verse_index[item["from"]]
            hi = corpus.verse_index[item.get("to", item["from"])]
            if hi < lo:
                lo, hi = hi, lo
            mask[lo:hi + 1] = True
        else:
            raise ValueError(f"unknown scope item type: {t}")
    starts = mask & ~np.concatenate([[False], mask[:-1]])
    range_id = np.where(mask, np.cumsum(starts) - 1, -1).astype(np.int32)
    desc = " + ".join(_describe(i) for i in items)
    return Scope(mask=mask, range_id=range_id, description=desc, spec={"items": items})
