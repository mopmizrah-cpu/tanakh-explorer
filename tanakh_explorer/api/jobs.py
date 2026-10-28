"""Background jobs for long scans: progress, cancellation, checkpoints and
resumption.

Constant-skip scans are split into skip sub-ranges processed in parallel by
a thread pool (NumPy releases the GIL in its array kernels). A checkpoint
after every finished sub-range records which skips are done; a cancelled or
interrupted job resumes from its checkpoint and never re-reports a skip.
A job is reported ``done`` only after every sub-range has finished.
Variable-skip scans checkpoint after every chunk of start positions and
resume from the next unfinished chunk.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from ..search import service as S
from .userdb import UserDB


class JobManager:
    def __init__(self, corpus_getter, db: UserDB, workers: int = 4):
        self.corpus_getter = corpus_getter
        self.db = db
        self.workers = max(1, workers)
        self.pool = ThreadPoolExecutor(max_workers=self.workers)
        self.jobs: dict[str, dict] = {}
        self.cancel_flags: dict[str, threading.Event] = {}
        self.lock = threading.Lock()
        for j in db.load_jobs():
            if j["status"] in ("running", "queued"):
                j["status"] = "interrupted"  # the server stopped while it ran; it can be resumed
            self.jobs[j["id"]] = j

    def list(self) -> list[dict]:
        return [self._public(j) for j in sorted(self.jobs.values(), key=lambda j: j["ts"], reverse=True)]

    def get(self, jid: str) -> dict:
        return self._public(self.jobs[jid], full=True)

    @staticmethod
    def _public(j: dict, full: bool = False) -> dict:
        out = {k: j.get(k) for k in ("id", "ts", "kind", "status", "progress", "error")}
        out["request"] = j["request"]
        cp = j.get("checkpoint") or {}
        out["done_skips"] = len(cp.get("done", []))
        if full:
            out["result"] = j.get("result")
            out["checkpoint"] = cp
        return out

    def start(self, kind: str, request: dict) -> str:
        if kind not in ("constant_scan", "variable_scan"):
            raise ValueError(kind)
        jid = uuid.uuid4().hex[:12]
        job = {"id": jid, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "request": request,
               "status": "queued", "progress": 0.0, "checkpoint": {"done": [], "rows": [], "total": 0}}
        with self.lock:
            self.jobs[jid] = job
        self.db.save_job(job)
        self._launch(jid)
        return jid

    def resume(self, jid: str) -> None:
        job = self.jobs[jid]
        if job["status"] not in ("cancelled", "interrupted", "error"):
            raise ValueError("רק סריקה שבוטלה או נקטעה ניתנת לחידוש")
        job["status"] = "queued"
        job["error"] = None
        self._launch(jid)

    def cancel(self, jid: str) -> None:
        ev = self.cancel_flags.get(jid)
        if ev:
            ev.set()

    def _launch(self, jid: str):
        ev = threading.Event()
        self.cancel_flags[jid] = ev
        threading.Thread(target=self._run, args=(jid, ev), daemon=True).start()

    def _run(self, jid: str, ev: threading.Event):
        job = self.jobs[jid]
        job["status"] = "running"
        self.db.save_job(job)
        try:
            corpus = self.corpus_getter()
            if job["kind"] == "constant_scan":
                self._constant(job, corpus, ev)
            else:
                self._variable(job, corpus, ev)
        except Exception as e:  # reported on the job, never swallowed
            job["status"] = "error"
            job["error"] = str(e)
        self.db.save_job(job)

    def _constant(self, job, corpus, ev):
        req = job["request"]
        lo, hi = int(req.get("skip_min", 1)), int(req.get("skip_max", 50))
        cp = job["checkpoint"]
        done = set(cp.get("done", []))
        todo = [d for d in range(lo, hi + 1) if d not in done]
        n_total = hi - lo + 1
        # sub-ranges of consecutive skips for the worker pool
        size = max(1, len(todo) // (self.workers * 4) or 1)
        chunks = [todo[i:i + size] for i in range(0, len(todo), size)]

        def work(chunk):
            if ev.is_set():
                return None
            sub = dict(req)
            sub["skip_min"], sub["skip_max"] = chunk[0], chunk[-1]
            return chunk, S.constant_skip_scan(corpus, sub, cancel=ev.is_set)

        futures = [self.pool.submit(work, c) for c in chunks]
        for f in futures:
            out = f.result()
            if out is None:
                continue
            chunk, res = out
            if res.get("status") == "cancelled":
                finished = [d for d in chunk if d < res["next_skip"]]
            else:
                finished = chunk
            with self.lock:
                cp["rows"].extend(r for r in res["rows"] if r["skip"] in finished)
                cp["total"] = sum(r["count"] for r in cp["rows"])
                cp["done"] = sorted(set(cp["done"]) | set(finished))
                job["progress"] = len(cp["done"]) / n_total
            self.db.save_job(job)
        complete = len(cp["done"]) == n_total
        cp["rows"].sort(key=lambda r: (r["skip"], r["direction"]))
        job["status"] = "done" if complete else "cancelled"
        job["result"] = {"total": cp["total"], "rows": cp["rows"], "complete": complete,
                         "skips_checked": len(cp["done"]), "skips_requested": n_total}

    def _variable(self, job, corpus, ev):
        req = job["request"]

        cp = job["checkpoint"]
        state = cp.setdefault("variable_state", {})

        def prog(frac, ci):
            job["progress"] = frac
            if ci % 20 == 0:
                self.db.save_job(job)
        res = S.variable_skip_scan(corpus, req, progress=prog, cancel=ev.is_set, state=state)
        if res.get("status") == "cancelled":
            job["status"] = "cancelled"
            job["result"] = {"complete": False, "total_so_far": res.get("total_so_far")}
        else:
            job["status"] = "done"
            job["progress"] = 1.0
            job["result"] = res
