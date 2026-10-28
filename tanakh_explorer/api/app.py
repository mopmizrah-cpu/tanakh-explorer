"""FastAPI application: JSON API under ``/api`` and the Hebrew web UI at ``/``."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import __version__, config
from .. import gematria as G
from .. import transformations as X
from ..combined import pipeline
from ..corpus import reader
from ..corpus.books import BOOKS, GROUPS_24, SECTION_HE
from ..corpus.parashot import PARASHOT
from ..corpus.sections import masoretic_sections
from ..corpus.store import load_corpus
from ..niqqud_gematria import DEFAULT_VALUES, NiqqudTable
from ..search import service as S
from ..stats import analysis
from ..validation.checks import run_checks
from .jobs import JobManager
from .userdb import UserDB

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="חוקר התנ״ך", version=__version__)
db = UserDB()
for cm in db.load_custom():
    try:
        G.register_custom(cm["slug"], cm["name_he"], cm["values"], cm["description"])
    except ValueError:
        pass
jobs = JobManager(load_corpus, db, workers=int(os.environ.get("TANAKH_WORKERS", "4")))


@app.exception_handler(ValueError)
async def value_error(_, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(KeyError)
async def key_error(_, exc: KeyError):
    return JSONResponse(status_code=400, content={"error": f"ערך לא מוכר: {exc}"})


def corpus():
    return load_corpus()


def _save(kind: str, title: str, req: dict, res: dict) -> dict:
    if req.get("save", True):
        stored = dict(res)
        if isinstance(stored.get("results"), list):
            stored["results"] = stored["results"][:200]
        res["history_id"] = db.add_history(kind, title, req, res.get("total"), stored)
    return res


# --- metadata -----------------------------------------------------------------------

@app.get("/api/meta")
def meta():
    c = corpus()
    secs = masoretic_sections(c)
    per_book = {}
    for s in secs:
        per_book[s.book] = per_book.get(s.book, 0) + 1
    return {
        "version": __version__,
        "source": c.source_info,
        "books": [{"osis": b.osis, "he": b.he, "group": b.group, "section": b.section, "chapters": b.chapters,
                   "masoretic_sections": per_book.get(b.osis, 0)} for b in BOOKS],
        "groups_24": GROUPS_24, "sections": [{"id": k, "he": v} for k, v in SECTION_HE.items()],
        "parashot": [{"name": p[0], "book": p[1], "chapter": p[2], "verse": p[3]} for p in PARASHOT],
        "gematria_methods": [m.to_dict() for m in G.REGISTRY.values()],
        "transformations": [t.to_dict() for t in X.REGISTRY.values()],
        "articulation_groups": X.articulation_groups(),
        "niqqud_table": NiqqudTable().describe(), "niqqud_defaults": DEFAULT_VALUES,
        "tagin_note": reader.TAGIN_NOTE,
    }


@app.get("/api/sections/{book}")
def sections(book: str):
    c = corpus()
    return [s.to_dict(c) for s in masoretic_sections(c) if s.book == book]


# --- searches -------------------------------------------------------------------------

@app.post("/api/search/letters")
def search_letters(req: dict = Body(...)):
    res = S.letter_search(corpus(), req)
    unit_he = {"words": "מילים", "verses": "פסוקים", "letters": "אותיות"}[req.get("unit", "words")]
    return _save("letters", f"{req.get('query')} · {unit_he}", req, res)


@app.post("/api/search/phrase")
def search_phrase(req: dict = Body(...)):
    return _save("phrase", f"ביטוי: {req.get('query')}", req, S.phrase_search(corpus(), req))


@app.post("/api/search/niqqud")
def search_niqqud(req: dict = Body(...)):
    return _save("niqqud", f"ניקוד: {req.get('query')}", req, S.niqqud_search(corpus(), req))


@app.post("/api/search/niqqud-sum")
def search_niqqud_sum(req: dict = Body(...)):
    return _save("niqqud_sum", f"סכום ניקוד: {req.get('query') or req.get('target')}", req,
                 S.niqqud_sum_search(corpus(), req))


@app.post("/api/search/gematria")
def search_gematria(req: dict = Body(...)):
    return _save("gematria", f"גימטריה ({req.get('method', 'standard')}): {req.get('query') or req.get('target')}",
                 req, S.gematria_search(corpus(), req))


@app.post("/api/search/gematria-all")
def search_gematria_all(req: dict = Body(...)):
    res = S.gematria_all(corpus(), req)
    res["total"] = sum(r["total"] for r in res["rows"])
    return _save("gematria_all", f"כל הגימטריות: {req.get('query')}", req, res)


@app.post("/api/search/transform")
def search_transform(req: dict = Body(...)):
    return _save("transform", f"{req.get('transformation')}: {req.get('query')}", req, S.transform_search(corpus(), req))


@app.post("/api/search/transform-all")
def search_transform_all(req: dict = Body(...)):
    res = S.transform_all(corpus(), req)
    res["total"] = sum(r["count"] for r in res["rows"])
    return _save("transform_all", f"כל החילופים: {req.get('query')}", req, res)


@app.post("/api/search/all-combined")
def search_all_combined(req: dict = Body(...)):
    """Every transformation × every selected gematria method: the value of the
    transformed query and the number of matching words."""
    import numpy as np
    c = corpus()
    layer, scope, ntable, exact, _, _ = S._ctx(c, req)
    methods = req.get("methods") or ["standard", "gadol", "katan", "ordinal", "kidmi", "milui"]
    variants = [("none", "ללא חילוף", {})] + [(tid, t.name_he, {}) for tid, t in X.REGISTRY.items() if tid != "shift"]
    wrid = scope.range_id[layer.word_verse]
    rows = []
    cache = {}
    for mid in methods:
        m = G.get(mid)
        p = m.resolve(None)
        vals = m.word_values(layer, p, ntable)
        cache[mid] = (m, p, vals)
    for tid, name, params in variants:
        text = req.get("query", "") if tid == "none" else X.get(tid).apply(req.get("query", ""), params)
        for mid in methods:
            m, p, vals = cache[mid]
            v = m.compute(text, p, ntable)["value"]
            count = int((np.asarray(vals == v, dtype=bool) & (wrid >= 0)).sum())
            rows.append({"transformation": tid, "transformation_he": name, "text": text, "method": mid,
                         "method_he": m.name_he, "value": v, "count": count})
    res = {"rows": rows, "complete": True, "combinations": len(rows),
           "scope_note": f"{len(variants)} חילופים × {len(methods)} שיטות = {len(rows)} צירופים; ספירת מילים בודדות בתחום"}
    res["total"] = sum(r["count"] for r in rows)
    return _save("all_combined", f"כל הגימטריות והחילופים: {req.get('query')}", req, res)


@app.post("/api/search/pipeline")
def search_pipeline(req: dict = Body(...)):
    res = pipeline.run(corpus(), req)
    if res.get("ok") and res.get("result"):
        res["total"] = res["result"]["total"]
    return _save("pipeline", f"חיפוש משולב: {req.get('query')}", req, res)


@app.post("/api/pipeline/validate")
def validate_pipeline(req: dict = Body(...)):
    return {"errors": pipeline.validate(req.get("steps") or []), "step_types": pipeline.STEP_TYPES}


# --- scans and jobs --------------------------------------------------------------------

@app.post("/api/scan/estimate")
def scan_estimate(req: dict = Body(...)):
    return S.estimate_scan(corpus(), req)


@app.post("/api/scan/start")
def scan_start(req: dict = Body(...)):
    kind = "variable_scan" if req.get("variable") else "constant_scan"
    return {"job_id": jobs.start(kind, req)}


@app.get("/api/jobs")
def jobs_list():
    return jobs.list()


@app.get("/api/jobs/{jid}")
def job_get(jid: str):
    if jid not in jobs.jobs:
        raise HTTPException(404, "לא נמצא")
    return jobs.get(jid)


@app.post("/api/jobs/{jid}/cancel")
def job_cancel(jid: str):
    jobs.cancel(jid)
    return {"ok": True}


@app.post("/api/jobs/{jid}/resume")
def job_resume(jid: str):
    jobs.resume(jid)
    return {"ok": True}


# --- calculators ----------------------------------------------------------------------

@app.post("/api/calc/gematria")
def calc_gematria(req: dict = Body(...)):
    nt = NiqqudTable.from_overrides(req.get("niqqud_values"))
    mids = req.get("methods") or [req.get("method", "standard")]
    return [S.gematria_value(req.get("query", ""), mid, (req.get("params") or {}).get(mid), nt) for mid in mids]


@app.post("/api/calc/transform")
def calc_transform(req: dict = Body(...)):
    return S.transform_text(req.get("query", ""), req.get("transformation", "atbash"), req.get("params"))


@app.post("/api/calc/shifts")
def calc_shifts(req: dict = Body(...)):
    return S.all_shifts(req.get("query", ""), req.get("finals", "keep"))


@app.post("/api/calc/letters")
def calc_letters(req: dict = Body(...)):
    return {"words": reader.analyze_letters(req.get("query", ""), NiqqudTable.from_overrides(req.get("niqqud_values"))),
            "tagin_note": reader.TAGIN_NOTE}


@app.post("/api/custom-methods")
def custom_add(req: dict = Body(...)):
    m = G.register_custom(req["slug"], req["name_he"], req["values"], req.get("description", ""))
    db.save_custom(req["slug"], req["name_he"], req["values"], req.get("description", ""))
    return m.to_dict()


@app.delete("/api/custom-methods/{slug}")
def custom_delete(slug: str):
    G.remove_custom(slug)
    db.delete_custom(slug)
    return {"ok": True}


# --- statistics ----------------------------------------------------------------------

@app.post("/api/stats/table")
def stats_table(req: dict = Body(...)):
    return analysis.letter_table(corpus(), req)


@app.post("/api/stats/cell")
def stats_cell(req: dict = Body(...)):
    return analysis.cell_occurrences(corpus(), req)


@app.post("/api/stats/distribution")
def stats_distribution(req: dict = Body(...)):
    return analysis.distribution(corpus(), req)


@app.post("/api/stats/compare")
def stats_compare(req: dict = Body(...)):
    return analysis.compare(corpus(), req)


@app.post("/api/stats/summary")
def stats_summary(req: dict = Body(...)):
    return analysis.summary(corpus(), req)


# --- reader and validation ------------------------------------------------------------

@app.get("/api/reader/{book}/{chap}")
def read_chapter(book: str, chap: int):
    return reader.chapter(corpus(), book, chap)


@app.get("/api/validation")
def validation_report():
    if config.VALIDATION_REPORT.exists():
        return json.loads(config.VALIDATION_REPORT.read_text(encoding="utf-8"))
    return {"status": "not_run", "checks": []}


@app.post("/api/validation/run")
def validation_run():
    return run_checks(corpus())


# --- history and export ---------------------------------------------------------------

@app.get("/api/history")
def history_list():
    return db.list_history()


@app.get("/api/history/{hid}")
def history_get(hid: int):
    h = db.get_history(hid)
    if not h:
        raise HTTPException(404, "לא נמצא")
    return h


@app.delete("/api/history/{hid}")
def history_delete(hid: int):
    db.delete_history(hid)
    return {"ok": True}


def _rows_for_export(res: dict) -> list[dict]:
    rows = []
    if isinstance(res.get("results"), list):
        for i, r in enumerate(res["results"], 1):
            rows.append({
                "#": i,
                "from": (r.get("from") or {}).get("ref_he", ""), "to": (r.get("to") or {}).get("ref_he", ""),
                "found": r.get("found", ""), "value": r.get("value", ""),
                "words": " | ".join(" ".join(w["text"] for w in b.get("words", [])) for b in r.get("display", [])
                                    if "words" in b),
                "calculation": " ; ".join(r.get("steps", [])),
            })
    elif isinstance(res.get("rows"), list):
        for r in res["rows"]:
            rows.append({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                         for k, v in r.items() if k != "results"})
    return rows


@app.get("/api/history/{hid}/export")
def history_export(hid: int, format: str = "csv"):
    h = db.get_history(hid)
    if not h:
        raise HTTPException(404, "לא נמצא")
    if format == "json":
        data = json.dumps(h, ensure_ascii=False, indent=1).encode("utf-8")
        return Response(data, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="search-{hid}.json"'})
    rows = _rows_for_export(h["result"])
    buf = io.StringIO()
    buf.write(f"# {h['title']} | {h['ts']} | settings: {json.dumps(h['request'], ensure_ascii=False)}\n")
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    data = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so spreadsheet programs read Hebrew correctly
    return Response(data, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="search-{hid}.csv"'})


# --- static frontend ------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
