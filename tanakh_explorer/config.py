"""Filesystem locations. ``TANAKH_DATA`` overrides the data directory."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TANAKH_DATA", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"  # source files exactly as downloaded, never modified
BUILD_DIR = DATA_DIR / "build"  # derived corpus database and caches
USER_DB = DATA_DIR / "user.sqlite"  # search history, saved results, job checkpoints
CORPUS_DB = BUILD_DIR / "corpus.sqlite"
MANIFEST = RAW_DIR / "manifest.json"
VALIDATION_REPORT = BUILD_DIR / "validation_report.json"

# Pinned upstream revisions, so every build is reproducible.
MAM_REPO = "bdenckla/MAM-basics"
MAM_COMMIT = "5c28eba09f95fd491afef38454149bde628ee2a7"
WLC_REPO = "openscriptures/morphhb"
WLC_COMMIT = "3d15126fb1ef74867fc1434be1942e837932691f"
