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
    s.add_argument("--open", action="store_true", help="open the browser once the server answers")
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
        url = f"http://{args.host}:{args.port}/"
        if _answers(url + "api/meta"):
            # already running (e.g. the desktop icon was clicked twice): just show it
            print(f"server already running at {url}")
            if args.open:
                import webbrowser
                webbrowser.open(url)
            return 0
        load_corpus()
        if args.open:
            _open_when_ready(url)
        uvicorn.run("tanakh_explorer.api.app:app", host=args.host, port=args.port)
    if args.cmd == "bench":
        from .bench import run_bench
        run_bench()
    return 0


def _answers(url: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def _open_when_ready(url: str) -> None:
    import threading
    import time
    import webbrowser

    def wait():
        for _ in range(120):
            if _answers(url + "api/meta"):
                webbrowser.open(url)
                return
            time.sleep(0.5)
    threading.Thread(target=wait, daemon=True).start()


if __name__ == "__main__":
    sys.exit(main())
