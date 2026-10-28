import random

import pytest

from tanakh_explorer import config
from tanakh_explorer.corpus.model import Corpus
from tanakh_explorer.corpus.structure import Atom, Verse

VOWELS = ["ְ", "ֱ", "ֲ", "ֳ", "ִ", "ֵ", "ֶ", "ַ", "ָ", "ֹ",
          "ֻ", "ׇ", ""]
LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"
FINAL = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}


def random_word(rng: random.Random, pointed: bool = True) -> str:
    n = rng.randint(1, 6)
    out = []
    for i in range(n):
        ch = rng.choice(LETTERS)
        if i == n - 1 and ch in FINAL and rng.random() < 0.7:
            ch = FINAL[ch]
        mark = ""
        if pointed:
            if ch == "ו" and rng.random() < 0.2:
                mark = "ּ"  # shuruq / dagesh
            else:
                mark = rng.choice(VOWELS)
            if rng.random() < 0.2:
                mark += "֑"  # an accent, which must never change any value
        out.append(ch + mark)
    return "".join(out)


def synthetic_verses(seed: int = 7, n_verses: int = 120) -> list[Verse]:
    rng = random.Random(seed)
    verses = []
    kq = 0
    books = [("Gen", 3), ("Exod", 2), ("Ps", 2)]
    vi = 0
    for book, chapters in books:
        for ch in range(1, chapters + 1):
            for vs in range(1, n_verses // 7 + 1):
                atoms = []
                for _ in range(rng.randint(0, 9)):
                    if rng.random() < 0.05:
                        kq += 1
                        atoms.append(Atom(random_word(rng, False), role="k", kq=kq))
                        atoms.append(Atom(random_word(rng), role="q", kq=kq))
                    else:
                        atoms.append(Atom(random_word(rng), maqaf_after=rng.random() < 0.15))
                verses.append(Verse(f"{book}.{ch}.{vs}", book, ch, vs, atoms))
                vi += 1
    return verses


@pytest.fixture(scope="session")
def synth():
    return Corpus(synthetic_verses())


@pytest.fixture(scope="session")
def corpus():
    if not config.MANIFEST.exists():
        pytest.skip("full Tanakh data not downloaded (run: python -m tanakh_explorer setup)")
    from tanakh_explorer.corpus.store import load_corpus
    return load_corpus(log=lambda s: None)
