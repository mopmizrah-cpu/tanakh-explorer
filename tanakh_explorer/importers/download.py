"""Download the source texts at pinned revisions and record SHA-256 checksums.

Primary source: Miqra according to the Masorah (MAM), MAM-simple JSON,
CC BY-SA 4.0, prepared by Seth (Avi) Kadish on Hebrew Wikisource.
Control source: Westminster Leningrad Codex as distributed by the Open
Scriptures Hebrew Bible (openscriptures/morphhb), CC BY 4.0.

Downloaded files are stored byte-for-byte under ``data/raw`` and are never
modified. ``manifest.json`` records each file's URL, revision, size and
SHA-256; :func:`verify_manifest` recomputes the hashes.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

from .. import config
from ..corpus.books import BOOKS, MAM_SIMPLE_FILES

BHS_FILES = ["Exod", "Num", "Deut", "Josh", "1Sam-2Sam", "Jer"]


def _raw_url(repo: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.request.quote(path)}"


def planned_files() -> list[dict]:
    files = []
    for name in MAM_SIMPLE_FILES:
        files.append({"source": "mam", "repo": config.MAM_REPO, "commit": config.MAM_COMMIT,
                      "path": f"MAM-simple/json-vtrad-mam/{name}.json",
                      "local": f"mam/json-vtrad-mam/{name}.json"})
    for name in BHS_FILES:
        files.append({"source": "mam", "repo": config.MAM_REPO, "commit": config.MAM_COMMIT,
                      "path": f"MAM-simple/json-vtrad-bhs/{name}.json",
                      "local": f"mam/json-vtrad-bhs/{name}.json"})
    files.append({"source": "mam", "repo": config.MAM_REPO, "commit": config.MAM_COMMIT,
                  "path": "MAM-simple/LICENSE.md", "local": "mam/LICENSE.md"})
    for b in BOOKS:
        files.append({"source": "wlc", "repo": config.WLC_REPO, "commit": config.WLC_COMMIT,
                      "path": f"wlc/{b.osis}.xml", "local": f"wlc/{b.osis}.xml"})
    files.append({"source": "wlc", "repo": config.WLC_REPO, "commit": config.WLC_COMMIT,
                  "path": "LICENSE.md", "local": "wlc/LICENSE.md"})
    return files


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_all(force: bool = False, log=print) -> dict:
    raw = config.RAW_DIR
    raw.mkdir(parents=True, exist_ok=True)
    entries = []
    for spec in planned_files():
        dest = raw / spec["local"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = _raw_url(spec["repo"], spec["commit"], spec["path"])
        if force or not dest.exists():
            log(f"downloading {spec['path']}")
            tmp = dest.with_suffix(dest.suffix + ".part")
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                        f.write(r.read())
                    break
                except OSError:
                    if attempt == 2:
                        raise
                    time.sleep(2)
            tmp.replace(dest)
        entries.append({**spec, "url": url, "size": dest.stat().st_size, "sha256": sha256_file(dest)})
    manifest = {"created": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": entries}
    config.MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def verify_manifest() -> dict:
    """Recompute every hash. Returns {"ok": bool, "checked": n, "problems": [...]}."""
    if not config.MANIFEST.exists():
        return {"ok": False, "checked": 0, "problems": ["manifest.json is missing"]}
    manifest = json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    problems = []
    for e in manifest["files"]:
        p = config.RAW_DIR / e["local"]
        if not p.exists():
            problems.append(f"missing: {e['local']}")
        elif sha256_file(p) != e["sha256"]:
            problems.append(f"hash mismatch: {e['local']}")
    return {"ok": not problems, "checked": len(manifest["files"]), "problems": problems,
            "files": [{"file": e["local"], "sha256": e["sha256"], "size": e["size"]} for e in manifest["files"]]}
