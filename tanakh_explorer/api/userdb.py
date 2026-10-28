"""User database: search history with saved results, background-job
checkpoints and custom gematria methods (SQLite, ``data/user.sqlite``)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .. import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, title TEXT,
    request TEXT, total INTEGER, result TEXT);
CREATE TABLE IF NOT EXISTS jobs(
    id TEXT PRIMARY KEY, ts TEXT, kind TEXT, request TEXT, status TEXT,
    progress REAL, checkpoint TEXT, result TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS custom_methods(
    slug TEXT PRIMARY KEY, name_he TEXT, values_json TEXT, description TEXT);
"""


class UserDB:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or config.USER_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as db:
            db.executescript(SCHEMA)

    def _conn(self):
        return sqlite3.connect(self.path, timeout=30)

    # -- history ----------------------------------------------------------------
    def add_history(self, kind: str, title: str, request: dict, total, result: dict) -> int:
        with _lock, self._conn() as db:
            cur = db.execute("INSERT INTO history(ts,kind,title,request,total,result) VALUES(?,?,?,?,?,?)",
                             (time.strftime("%Y-%m-%d %H:%M:%S"), kind, title,
                              json.dumps(request, ensure_ascii=False), total,
                              json.dumps(result, ensure_ascii=False, default=str)))
            return int(cur.lastrowid)

    def list_history(self, limit: int = 200) -> list[dict]:
        with self._conn() as db:
            rows = db.execute("SELECT id,ts,kind,title,total FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"id": r[0], "ts": r[1], "kind": r[2], "title": r[3], "total": r[4]} for r in rows]

    def get_history(self, hid: int) -> dict | None:
        with self._conn() as db:
            r = db.execute("SELECT id,ts,kind,title,request,total,result FROM history WHERE id=?", (hid,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "ts": r[1], "kind": r[2], "title": r[3], "request": json.loads(r[4]),
                "total": r[5], "result": json.loads(r[6])}

    def delete_history(self, hid: int | None = None) -> None:
        with _lock, self._conn() as db:
            if hid is None:
                db.execute("DELETE FROM history")
            else:
                db.execute("DELETE FROM history WHERE id=?", (hid,))

    # -- jobs -------------------------------------------------------------------
    def save_job(self, job: dict) -> None:
        with _lock, self._conn() as db:
            db.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                       (job["id"], job["ts"], job["kind"], json.dumps(job["request"], ensure_ascii=False),
                        job["status"], job.get("progress", 0.0),
                        json.dumps(job.get("checkpoint"), ensure_ascii=False, default=str),
                        json.dumps(job.get("result"), ensure_ascii=False, default=str), job.get("error")))

    def load_jobs(self) -> list[dict]:
        with self._conn() as db:
            rows = db.execute("SELECT id,ts,kind,request,status,progress,checkpoint,result,error FROM jobs "
                              "ORDER BY ts DESC").fetchall()
        return [{"id": r[0], "ts": r[1], "kind": r[2], "request": json.loads(r[3]), "status": r[4],
                 "progress": r[5], "checkpoint": json.loads(r[6]) if r[6] else None,
                 "result": json.loads(r[7]) if r[7] else None, "error": r[8]} for r in rows]

    # -- custom methods --------------------------------------------------------------
    def save_custom(self, slug, name_he, values, description=""):
        with _lock, self._conn() as db:
            db.execute("INSERT OR REPLACE INTO custom_methods VALUES(?,?,?,?)",
                       (slug, name_he, json.dumps(values, ensure_ascii=False), description))

    def delete_custom(self, slug):
        with _lock, self._conn() as db:
            db.execute("DELETE FROM custom_methods WHERE slug=?", (slug,))

    def load_custom(self) -> list[dict]:
        with self._conn() as db:
            rows = db.execute("SELECT slug,name_he,values_json,description FROM custom_methods").fetchall()
        return [{"slug": r[0], "name_he": r[1], "values": json.loads(r[2]), "description": r[3]} for r in rows]
