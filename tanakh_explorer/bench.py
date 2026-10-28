"""Performance benchmarks on the full Tanakh (wall-clock, median of runs)."""

from __future__ import annotations

import json
import platform
import statistics
import time

from . import config
from .corpus.store import load_corpus
from .search import service as S

CASES = [
    ("ראשי תיבות — שלום", S.letter_search, {"query": "שלום", "unit": "words", "limit": 20}),
    ("סופי פסוקים — שלום", S.letter_search, {"query": "שלום", "unit": "verses", "selector": "last"}),
    ("דילוג משתנה 5,10,5 — שלום", S.letter_search, {"query": "שלום", "unit": "words", "skips": [5, 10, 5]}),
    ("דילוג אותיות 50 — תורה", S.letter_search, {"query": "תורה", "unit": "letters", "skips": [50]}),
    ("מילה שלמה — שלום", S.letter_search, {"query": "שלום", "unit": "letters", "whole_word": True}),
    ("ניקוד בראשי מילים — שָׁלוֹם", S.niqqud_search, {"query": "שָׁלוֹם", "unit": "words", "match": "niqqud"}),
    ("סכום ניקוד של מילים", S.niqqud_sum_search, {"query": "שָׁלוֹם", "kind": "word", "limit": 20}),
    ("סכום ניקוד ברצף מילים בתוך פסוק", S.niqqud_sum_search, {"query": "שָׁלוֹם", "kind": "in_verse", "sub": "run", "limit": 20}),
    ("גימטריה 376, 1–3 מילים", S.gematria_search, {"target": 376, "n_min": 1, "n_max": 3, "limit": 20}),
    ("מילוי, מילה אחת", S.gematria_search, {"query": "שלום", "method": "milui", "limit": 20}),
    ("כל הגימטריות — שלום", S.gematria_all, {"query": "שָׁלוֹם"}),
    ("כל החילופים — בבל", S.transform_all, {"query": "בבל", "search_mode": "word"}),
    ("סריקת דילוג קבוע 1–200 — תורה (אותיות)", S.constant_skip_scan,
     {"query": "תורה", "unit": "letters", "skip_min": 1, "skip_max": 200, "results_per_skip": 1}),
    ("סריקת דילוגים משתנים 1–20 — שלום (מילים)", S.variable_skip_scan,
     {"query": "שלום", "unit": "words", "skip_min": 1, "skip_max": 20, "limit": 20}),
]


def run_bench(repeats: int = 3) -> list[dict]:
    t = time.time()
    corpus = load_corpus()
    load_s = time.time() - t
    corpus.layer("ketiv", "split")
    rows = []
    for name, fn, req in CASES:
        times = []
        total = None
        for _ in range(repeats):
            t = time.perf_counter()
            res = fn(corpus, dict(req))
            times.append(time.perf_counter() - t)
            total = res.get("total")
        rows.append({"case": name, "median_ms": round(statistics.median(times) * 1000, 1),
                     "first_ms": round(times[0] * 1000, 1), "total": total})
        print(f"{rows[-1]['median_ms']:>9.1f} ms  (first {rows[-1]['first_ms']:.1f})  {name}  → {total}")
    out = {"machine": platform.platform(), "python": platform.python_version(), "corpus_load_s": round(load_s, 2),
           "cases": rows, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    config.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    (config.BUILD_DIR / "bench.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows
