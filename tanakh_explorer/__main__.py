"""Command line: ``python -m tanakh_explorer <command>``

  setup     download sources, build the corpus and run validation (first run)
  download  download the source texts at the pinned revisions
  build     build the corpus database and cache from the raw sources
  validate  run the integrity checks and write the report
  serve     start the web interface (default http://127.0.0.1:8000)
  bench     run performance benchmarks on the full Tanakh
"""

from __future__ import annotations

import argparse
import sys


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="tanakh_explorer", description="חוקר התנ״ך")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    d = sub.add_parser("download")
    d.add_argument("--force", action="store_true")
    sub.add_parser("build")
    sub.add_parser("validate")
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    sub.add_parser("bench")
    args = ap.parse_args(argv)

    if args.cmd in ("setup", "download"):
        from .importers.download import download_all
        download_all(force=getattr(args, "force", False))
        print("sources downloaded and hashed")
    if args.cmd in ("setup", "build"):
        from .corpus.store import build
        build()
    if args.cmd in ("setup", "validate"):
        from .corpus.store import load_corpus
        from .validation.checks import run_checks
        rep = run_checks(load_corpus())
        for c in rep["checks"]:
            print(f"[{c['status']:>7}] {c['name_he']}: {c['summary_he']}")
        print(f"overall: {rep['status']}")
        if rep["status"] == "fail":
            return 1
    if args.cmd == "serve":
        import uvicorn
        from .corpus.store import load_corpus
        load_corpus()
        uvicorn.run("tanakh_explorer.api.app:app", host=args.host, port=args.port)
    if args.cmd == "bench":
        from .bench import run_bench
        run_bench()
    return 0


if __name__ == "__main__":
    sys.exit(main())
