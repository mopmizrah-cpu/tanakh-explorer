"""The parsed, layout-aware structure of the text: verses made of atoms.

An *atom* is one written form between spaces or maqaf marks (MAM's term).
Atoms carry a ``role``:

* ``both`` — ordinary text, read as written;
* ``k``    — ketiv (written form) of a ketiv/qere pair, or a ketiv not read;
* ``q``    — qere (read form) of a pair, or a qere not written.

Atoms of one ketiv/qere pair share a ``kq`` id. The ketiv layer of the text
consists of the ``both`` and ``k`` atoms; the qere layer of ``both`` and
``q`` atoms. Ketiv and qere are never concatenated as consecutive words.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Atom:
    text: str  # pointed text with cantillation, no maqaf, no punctuation
    role: str = "both"  # both | k | q
    kq: int = -1  # ketiv/qere group id, -1 if none
    maqaf_after: bool = False  # joined to the next atom by a maqaf
    implicit_maqaf: bool = False  # MAM's gray (implicit) maqaf
    after: list[str] = field(default_factory=list)  # legarmeih, paseq, sof_pasuq, shirah, invnun
    marker_before: str | None = None  # a parashah marker standing inside the verse
    slh: dict[int, str] = field(default_factory=dict)  # letter index -> large/small/hung
    kq_trivial: bool = False
    kq_qere_first: bool = False  # MAM displays the qere first in this pair


@dataclass
class Verse:
    osis: str  # e.g. "Gen.1.1"
    book: str
    chapter: int
    verse: int
    atoms: list[Atom] = field(default_factory=list)
    markers_before: list[str] = field(default_factory=list)  # markers between previous verse and this one
    markers_end: list[str] = field(default_factory=list)  # markers standing at the end of the verse's own contents
    starts_with_sampe: str | None = None
    ends_with_sampe: str | None = None
    notes: list[str] = field(default_factory=list)  # scroll-difference notes, documentation only
    good_ending: str | None = None  # repeated favourable ending (not running text)
