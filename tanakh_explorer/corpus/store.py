"""Build and load the corpus.

``build()`` reads the raw MAM files, writes a normalised SQLite database
(``data/build/corpus.sqlite``: books, verses, atoms, letters, sections,
weekly portions) and a fast-load cache of the in-memory :class:`Corpus`.
``load_corpus()`` returns the cached corpus, rebuilding it when the source
manifest changed.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sqlite3
import threading
import time

from .. import config
from ..hebrew import ALL_LETTERS
from ..importers.mam_simple import MamSimpleReader
from ..niqqud import combo_hebrew
from .books import BOOKS
from .model import Corpus
from .sections import masoretic_sections, weekly_parashot

CACHE = config.BUILD_DIR / "corpus.pkl"
CACHE_VERSION = 5
_lock = threading.Lock()
_corpus: Corpus | None = None


def _manifest_hash() -> str:
    if not config.MANIFEST.exists():
        raise FileNotFoundError("source manifest missing — run: python -m tanakh_explorer download")
    return hashlib.sha256(config.MANIFEST.read_bytes()).hexdigest()


def build(log=print) -> Corpus:
    t0 = time.time()
    reader = MamSimpleReader()
    verses = reader.read_all(config.RAW_DIR / "mam" / "json-vtrad-mam")
    log(f"read {len(verses)} verses in {time.time() - t0:.1f}s")
    corpus = Corpus(verses, source_info={
        "source": "Miqra according to the Masorah (MAM-simple JSON, vtmam)",
        "repo": config.MAM_REPO, "commit": config.MAM_COMMIT,
        "license": "CC BY-SA 4.0", "manifest_sha256": _manifest_hash(),
        "reader_stats": {k: v for k, v in reader.stats.items()},
        "cant_strand": reader.cant_strand,
        "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cache_version": CACHE_VERSION,
    })
    config.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    write_sqlite(corpus)
    log(f"wrote {config.CORPUS_DB}")
    with open(CACHE, "wb") as f:
        pickle.dump(corpus, f, protocol=pickle.HIGHEST_PROTOCOL)
    log(f"built corpus in {time.time() - t0:.1f}s")
    return corpus


def write_sqlite(corpus: Corpus) -> None:
    path = config.CORPUS_DB
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript("""
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE books(id INTEGER PRIMARY KEY, osis TEXT, he TEXT, en TEXT, grp TEXT, section TEXT, chapters INTEGER);
    CREATE TABLE verses(id INTEGER PRIMARY KEY, osis TEXT UNIQUE, book_id INTEGER, chapter INTEGER, verse INTEGER,
        markers_before TEXT, markers_end TEXT, starts_with_sampe TEXT, ends_with_sampe TEXT, notes TEXT, good_ending TEXT);
    CREATE TABLE atoms(id INTEGER PRIMARY KEY, verse_id INTEGER, idx INTEGER, text TEXT, role TEXT, kq INTEGER,
        maqaf_after INTEGER, implicit_maqaf INTEGER, after TEXT, marker_before TEXT, kq_trivial INTEGER, kq_qere_first INTEGER);
    CREATE TABLE letters(id INTEGER PRIMARY KEY, atom_id INTEGER, pos INTEGER, letter TEXT, code INTEGER,
        combo INTEGER, vowels_he TEXT, flags INTEGER);
    CREATE TABLE sections(id INTEGER PRIMARY KEY, book TEXT, number INTEGER, kind TEXT, marker TEXT,
        start_verse INTEGER, end_verse INTEGER, start_partial INTEGER, end_partial INTEGER);
    CREATE TABLE parashot(id INTEGER PRIMARY KEY, name TEXT, book TEXT, start_verse INTEGER, end_verse INTEGER);
    """)
    db.executemany("INSERT INTO meta VALUES(?,?)", [(k, json.dumps(v, ensure_ascii=False)) for k, v in corpus.source_info.items()])
    db.executemany("INSERT INTO books VALUES(?,?,?,?,?,?,?)",
                   [(i, b.osis, b.he, b.en, b.group, b.section, b.chapters) for i, b in enumerate(BOOKS)])
    db.executemany("INSERT INTO verses VALUES(?,?,?,?,?,?,?,?,?,?,?)", [
        (i, v.osis, int(corpus.verse_book[i]), v.chapter, v.verse, ",".join(v.markers_before), ",".join(v.markers_end),
         v.starts_with_sampe, v.ends_with_sampe, json.dumps(v.notes, ensure_ascii=False), v.good_ending)
        for i, v in enumerate(corpus.verses)])
    rows = []
    aid = 0
    for i, v in enumerate(corpus.verses):
        for k, a in enumerate(v.atoms):
            rows.append((aid, i, k, a.text, a.role, a.kq, int(a.maqaf_after), int(a.implicit_maqaf),
                         ",".join(a.after), a.marker_before, int(a.kq_trivial), int(a.kq_qere_first)))
            aid += 1
    db.executemany("INSERT INTO atoms VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    combo_names = {}
    lrows = []
    codes, combos, flags = corpus.al_code.tolist(), corpus.al_combo.tolist(), corpus.al_flags.tolist()
    for a in range(len(corpus.a_text)):
        s, n = int(corpus.a_lstart[a]), int(corpus.a_llen[a])
        for p in range(n):
            li = s + p
            c = combos[li]
            if c not in combo_names:
                combo_names[c] = combo_hebrew(c)
            lrows.append((li, a, p, ALL_LETTERS[codes[li]], codes[li], c, combo_names[c], flags[li]))
    db.executemany("INSERT INTO letters VALUES(?,?,?,?,?,?,?,?)", lrows)
    db.executemany("INSERT INTO sections(book,number,kind,marker,start_verse,end_verse,start_partial,end_partial) VALUES(?,?,?,?,?,?,?,?)",
                   [(s.book, s.number, s.kind, s.marker, s.start, s.end, int(s.start_partial), int(s.end_partial))
                    for s in masoretic_sections(corpus)])
    db.executemany("INSERT INTO parashot(name,book,start_verse,end_verse) VALUES(?,?,?,?)",
                   [(p.name, p.book, p.start, p.end) for p in weekly_parashot(corpus)])
    db.executescript("""
    CREATE INDEX ix_atoms_verse ON atoms(verse_id);
    CREATE INDEX ix_letters_atom ON letters(atom_id);
    CREATE INDEX ix_letters_letter_combo ON letters(code, combo);
    """)
    db.commit()
    db.close()


def load_corpus(rebuild: bool = False, log=print) -> Corpus:
    global _corpus
    with _lock:
        if _corpus is not None and not rebuild:
            return _corpus
        corpus = None
        if CACHE.exists() and not rebuild:
            try:
                with open(CACHE, "rb") as f:
                    corpus = pickle.load(f)
                info = corpus.source_info
                if info.get("manifest_sha256") != _manifest_hash() or info.get("cache_version") != CACHE_VERSION:
                    corpus = None
            except Exception:  # stale or incompatible cache: rebuild
                corpus = None
        if corpus is None:
            corpus = build(log=log)
        _corpus = corpus
        return corpus
