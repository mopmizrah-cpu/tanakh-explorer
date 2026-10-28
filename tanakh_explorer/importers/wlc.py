"""Read the Westminster Leningrad Codex (OSHB / morphhb OSIS XML) as an
independent control text for validation.

Only ``<w>`` elements that belong to the running text are read; qere
readings inside ``<note>`` are kept apart, and ``<seg>`` elements (maqaf,
sof pasuq, paseq, and the פ/ס section markers) contribute no letters.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .. import hebrew as H
from ..corpus.books import BOOKS

NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"


def read_wlc(directory: Path) -> dict[str, dict]:
    """osis verse id -> {"ketiv": [words], "qere": [words]} (consonants only)."""
    out: dict[str, dict] = {}
    for b in BOOKS:
        tree = ET.parse(Path(directory) / f"{b.osis}.xml")
        for verse in tree.iter(f"{NS}verse"):
            ketiv, qere = [], []
            for child in verse:
                tag = child.tag.replace(NS, "")
                if tag == "w":
                    word = H.letters_only("".join(child.itertext()))
                    if word:
                        ketiv.append(word)
                        if child.get("type") != "x-ketiv":
                            qere.append(word)
                elif tag == "note" and child.get("type") == "variant":
                    for rdg in child.iter(f"{NS}rdg"):
                        if rdg.get("type") == "x-qere":
                            for w in rdg.iter(f"{NS}w"):
                                word = H.letters_only("".join(w.itertext()))
                                if word:
                                    qere.append(word)
            out[verse.get("osisID")] = {"ketiv": ketiv, "qere": qere}
    return out
