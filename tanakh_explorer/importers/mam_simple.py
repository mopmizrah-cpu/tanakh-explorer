"""Import MAM-simple JSON into :class:`~tanakh_explorer.corpus.structure.Verse`
objects.

The reader follows MAM-simple's documented contract: a closed dispatch over
element types that raises on an unknown type, recursion into every container,
one branch chosen where the element holds alternatives (kq, cant-all-three,
scrdfftar, good-ending), and fragments reassembled before atoms are cut.

Parashah markers (spi-pe2, spi-samekh2, …) are structural elements without
text. They are recorded as markers and *never* become letters, so a פ or ס
that is a section marker cannot enter any count, while a פ or ס inside a word
is an ordinary letter.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .. import hebrew as H
from ..corpus.books import BOOK_INDEX, MAM_SIMPLE_FILES
from ..corpus.structure import Atom, Verse

MARKERS = {"spi-pe2": "pe2", "spi-pe3": "pe3", "spi-samekh2": "samekh2", "spi-samekh3": "samekh3"}


class _Segmenter:
    """Turns a stream of characters and separator events into atoms."""

    def __init__(self, verse: Verse, stats: Counter):
        self.verse = verse
        self.stats = stats
        self.buf: list[str] = []
        self.role = "both"
        self.kq = -1
        self.slh: dict[int, str] = {}
        self.letter_count = 0
        self.pending_marker: str | None = None
        self.kq_trivial = False
        self.kq_qere_first = False

    # -- events -------------------------------------------------------------
    def char(self, ch: str, role: str, kq: int, attr: str | None = None, trivial=False, qfirst=False):
        if self.buf and (role != self.role or kq != self.kq):
            self.stats["role_change_without_separator"] += 1
            self.flush()
        if ch == " ":
            self.flush()
            return
        if ch == H.MAQAF:
            self.flush(maqaf=True)
            return
        if ch == H.SOF_PASUQ:
            self.flush()
            self._last_add("sof_pasuq")
            return
        if ch in H.LETTER_CODE:
            if attr:
                self.slh[self.letter_count] = attr
            self.letter_count += 1
        elif not H.is_combining_mark(ch):
            self.stats[f"unexpected_char_U+{ord(ch):04X}"] += 1
            return
        if not self.buf:
            self.role, self.kq, self.kq_trivial, self.kq_qere_first = role, kq, trivial, qfirst
        self.buf.append(ch)

    def sep(self, kind: str):
        self.flush()
        if kind == "implicit_maqaf":
            self._apply_maqaf(implicit=True)
        elif kind == "maqaf":
            self._apply_maqaf()
        else:
            self._last_add(kind)

    def marker(self, kind: str):
        self.flush()
        self.pending_marker = kind

    # -- internals ----------------------------------------------------------
    def _last_add(self, flag: str):
        if self.verse.atoms:
            self.verse.atoms[-1].after.append(flag)

    def _apply_maqaf(self, implicit: bool = False):
        """Mark the last atom (and, inside a kq pair, the last atom of the
        other branch) as joined to the next atom by maqaf."""
        atoms = self.verse.atoms
        if not atoms:
            self.stats["maqaf_without_atom"] += 1
            return
        last = atoms[-1]
        targets = [last]
        if last.kq >= 0:
            for a in reversed(atoms[:-1]):
                if a.kq != last.kq:
                    break
                if a.role != last.role:
                    targets.append(a)
                    break
        for a in targets:
            a.maqaf_after = True
            a.implicit_maqaf = a.implicit_maqaf or implicit

    def flush(self, maqaf: bool = False):
        if not self.buf:
            if maqaf:
                self._apply_maqaf()
            return
        text = "".join(self.buf)
        if not H.letters_only(text):
            self.stats["atom_without_letters"] += 1
        atom = Atom(text=text, role=self.role, kq=self.kq, maqaf_after=maqaf,
                    slh=self.slh, kq_trivial=self.kq_trivial, kq_qere_first=self.kq_qere_first)
        if self.pending_marker:
            atom.marker_before = self.pending_marker
            self.pending_marker = None
        self.verse.atoms.append(atom)
        self.buf = []
        self.slh = {}
        self.letter_count = 0


class MamSimpleReader:
    def __init__(self, cant_strand: str = "cant-alef"):
        if cant_strand not in ("cant-alef", "cant-bet", "cant-combined"):
            raise ValueError(cant_strand)
        self.cant_strand = cant_strand
        self.stats: Counter = Counter()
        self._kq_counter = 0

    # -- dispatch over element types ---------------------------------------
    def _emit(self, node: dict, seg: _Segmenter, role: str, kq: int, attr=None, trivial=False, qfirst=False):
        t = node["type"]
        self.stats[f"type:{t}"] += 1

        def text_or_children(r=role, k=kq, a=attr, tr=trivial, qf=qfirst):
            if "text" in node:
                for ch in node["text"]:
                    seg.char(ch, r, k, a, tr, qf)
            elif "contents" in node:
                for c in node["contents"]:
                    self._emit(c, seg, r, k, a, tr, qf)
            else:
                self.stats[f"empty:{t}"] += 1

        if t in ("text", "silluq-before-meteg"):
            text_or_children()
        elif t == "lp-legarmeih":
            seg.sep("legarmeih")
        elif t == "lp-paseq":
            seg.sep("paseq")
        elif t == "implicit-maqaf":
            seg.sep("implicit_maqaf")
        elif t == "kq-k-velo-q-maq":
            seg.sep("maqaf")
        elif t == "shirah-space":
            seg.sep("shirah")
        elif t == "spi-invnun":
            seg.sep("invnun")
        elif t in MARKERS:
            seg.marker(MARKERS[t])
        elif t == "slh-word":
            for c in node["contents"]:
                self._emit(c, seg, role, kq, attr, trivial, qfirst)
        elif t in ("letter-small", "letter-large", "letter-hung"):
            kind = t.split("-")[1]
            text_or_children(a=kind)
        elif t == "kq":
            seg.flush()
            self._kq_counter += 1
            gid = self._kq_counter
            kids = node["contents"]
            ktypes = [c["type"] for c in kids]
            if sorted(ktypes) != ["kq-k", "kq-q"]:
                raise ValueError(f"malformed kq: {ktypes}")
            qfirst_pair = ktypes[0] == "kq-q"
            for c in kids:
                r = "k" if c["type"] == "kq-k" else "q"
                self._emit(c, seg, r, gid, attr, False, qfirst_pair)
                seg.flush()
        elif t in ("kq-k", "kq-q"):
            text_or_children()
        elif t == "kq-trivial":
            text_or_children(tr=True)
        elif t == "kq-k-velo-q":
            seg.flush()
            self._kq_counter += 1
            text_or_children(r="k", k=self._kq_counter)
            seg.flush()
        elif t == "kq-q-velo-k":
            seg.flush()
            self._kq_counter += 1
            text_or_children(r="q", k=self._kq_counter)
            seg.flush()
        elif t == "cant-all-three":
            chosen = [c for c in node["contents"] if c["type"] == self.cant_strand]
            if len(chosen) != 1:
                raise ValueError("cant-all-three without the chosen strand")
            self._emit(chosen[0], seg, role, kq, attr, trivial, qfirst)
        elif t in ("cant-combined", "cant-alef", "cant-bet"):
            text_or_children()
        elif t == "scrdfftar":
            for c in node["contents"]:
                if c["type"] == "sdt-target":
                    self._emit(c, seg, role, kq, attr, trivial, qfirst)
                elif c["type"] == "sdt-note":
                    seg.verse.notes.append(_plain(c))
                else:
                    raise ValueError(f"unexpected scrdfftar child {c['type']}")
        elif t == "sdt-target":
            text_or_children()
        elif t == "good-ending":
            seg.flush()
            seg.verse.good_ending = node.get("text")
        else:
            raise ValueError(f"unknown MAM-simple element type: {t}")

    def read_verse(self, node: dict, markers_before: list[str]) -> Verse:
        osis = node["osisID"]
        book, ch, vs = osis.split(".")
        verse = Verse(osis=osis, book=book, chapter=int(ch), verse=int(vs),
                      markers_before=list(markers_before),
                      starts_with_sampe=node.get("starts-with-sampe"),
                      ends_with_sampe=node.get("ends-with-sampe"))
        seg = _Segmenter(verse, self.stats)
        if "text" in node:
            for c in node["text"]:
                seg.char(c, "both", -1)
        else:
            for c in node.get("contents", []):
                self._emit(c, seg, "both", -1)
        seg.flush()
        if seg.pending_marker:
            # a marker standing at the very end of the verse's own contents
            self.stats["marker_at_verse_end"] += 1
            verse.markers_end.append(seg.pending_marker)
        return verse

    def read_file(self, path: Path) -> list[Verse]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        verses: list[Verse] = []
        pending: list[str] = []

        def walk(items):
            nonlocal pending
            for it in items:
                t = it["type"]
                if t in MARKERS:
                    pending.append(MARKERS[t])
                elif t in ("book39", "chapter"):
                    walk(it["contents"])
                elif t == "verse":
                    verses.append(self.read_verse(it, pending))
                    pending = []
                else:
                    raise ValueError(f"unexpected container child {t}")

        walk(data["contents"])
        if pending:
            self.stats["trailing_markers"] += len(pending)
            if verses:
                verses[-1].notes.append("trailing markers: " + ",".join(pending))
        return verses

    def read_all(self, directory: Path) -> list[Verse]:
        verses: list[Verse] = []
        for name in MAM_SIMPLE_FILES:
            verses.extend(self.read_file(Path(directory) / f"{name}.json"))
        verses.sort(key=lambda v: (BOOK_INDEX[v.book], v.chapter, v.verse))
        return verses


def _plain(node: dict) -> str:
    if "text" in node:
        return node["text"]
    if node.get("type") == "slh-word":
        return node.get("slhw-desc-0", "")
    return "".join(_plain(c) for c in node.get("contents", []))


def independent_letter_extract(node, role_filter: str) -> str:
    """A deliberately simple, independent extractor used only by validation:
    collects Hebrew letters from the Scripture branches of a verse node.

    ``role_filter`` is "k" (ketiv text) or "q" (qere text). It shares no code
    with the segmenter above, so agreement between the two is meaningful.
    """
    out: list[str] = []

    def rec(n, role):
        t = n.get("type")
        if t in ("good-ending", "sdt-note"):
            return
        if t == "cant-all-three":
            n = [c for c in n["contents"] if c["type"] == "cant-alef"][0]
            t = n["type"]
        if t in ("kq-k", "kq-k-velo-q"):
            role = "k"
        elif t in ("kq-q", "kq-q-velo-k"):
            role = "q"
        if role not in ("both", role_filter):
            return
        if "text" in n:
            out.append("".join(c for c in n["text"] if "א" <= c <= "ת"))
        for c in n.get("contents", []):
            rec(c, role)

    rec(node, "both")
    return "".join(out)
