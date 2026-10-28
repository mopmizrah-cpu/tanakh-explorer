"""Integrity checks of the corpus against its sources.

Each check returns a status:

* ``pass``    — verified;
* ``fail``    — verified and wrong (the overall report then fails);
* ``warn``    — verified, with cases that need a human look;
* ``info``    — a measurement or comparison, not a pass/fail claim;
* ``not_run`` — could not be performed (e.g. a source file is missing).

A failed or skipped check is never reported as a success.
"""

from __future__ import annotations

import json
import time
import traceback
from collections import Counter
from difflib import SequenceMatcher

import numpy as np

from .. import config
from .. import hebrew as H
from ..corpus.books import BOOK_INDEX, BOOKS, GROUPS_24, MAM_SIMPLE_FILES
from ..corpus.sections import masoretic_sections, weekly_parashot
from ..importers.download import BHS_FILES, verify_manifest
from ..importers.mam_simple import MARKERS, MamSimpleReader, independent_letter_extract

MAM_DIR = config.RAW_DIR / "mam" / "json-vtrad-mam"


def _check(cid, name_he, status, summary_he, details=None):
    return {"id": cid, "name_he": name_he, "status": status, "summary_he": summary_he, "details": details or {}}


def _raw_verses():
    """Raw verse nodes in source order, read independently of the importer."""
    out = []
    for name in MAM_SIMPLE_FILES:
        data = json.loads((MAM_DIR / f"{name}.json").read_text(encoding="utf-8"))

        def walk(items):
            for it in items:
                if it["type"] == "verse":
                    out.append(it)
                elif it["type"] in ("book39", "chapter"):
                    walk(it["contents"])
        walk(data["contents"])
    return out


def _raw_markers():
    c = Counter()
    for name in MAM_SIMPLE_FILES:
        text = (MAM_DIR / f"{name}.json").read_text(encoding="utf-8")
        for t in MARKERS:
            c[t] += text.count(f'"type": "{t}"') + text.count(f'"type":"{t}"')
    return c


def _marks_of(text: str) -> Counter:
    return Counter(ch for ch in text if H.is_combining_mark(ch) and ch != H.CGJ)


def _raw_marks(node, role_filter):
    """Combining marks of the Scripture branches of a raw verse node."""
    out = Counter()

    def rec(n, role):
        t = n.get("type")
        if t in ("good-ending", "sdt-note"):
            return
        if t == "cant-all-three":
            n = [c for c in n["contents"] if c["type"] == "cant-alef"][0]
        if t in ("kq-k", "kq-k-velo-q"):
            role = "k"
        elif t in ("kq-q", "kq-q-velo-k"):
            role = "q"
        if role not in ("both", role_filter):
            return
        if "text" in n and t != "slh-word":
            out.update(_marks_of(n["text"]))
        for c in n.get("contents", []):
            rec(c, role)
    rec(node, "both")
    return out


def run_checks(corpus, include_wlc: bool = True) -> dict:
    t0 = time.time()
    checks = []

    def guarded(fn):
        try:
            res = fn()
            checks.extend(res if isinstance(res, list) else [res])
        except Exception as e:  # a check that crashed is reported, not hidden
            checks.append(_check(fn.__name__, fn.__name__, "not_run", f"הבדיקה לא הושלמה: {e}",
                                 {"traceback": traceback.format_exc()[-2000:]}))

    raw = _raw_verses()
    L_k = corpus.layer("ketiv", "split")
    L_q = corpus.layer("qere", "split")

    def source_hashes():
        r = verify_manifest()
        return _check("source_hashes", "בדיקות SHA-256 לקובצי המקור", "pass" if r["ok"] else "fail",
                      f"נבדקו {r['checked']} קבצים; " + ("כל הגיבובים תואמים" if r["ok"] else f"{len(r['problems'])} בעיות"),
                      r)

    def books():
        found = list(dict.fromkeys(v.book for v in corpus.verses))
        ok = found == [b.osis for b in BOOKS]
        groups = list(dict.fromkeys(BOOKS[BOOK_INDEX[b]].group for b in found))
        ok24 = len(groups) == 24 and groups == GROUPS_24
        return _check("books", "שלמות הספרים", "pass" if ok and ok24 else "fail",
                      f"{len(found)} ספרים (39 לפי חלוקת הדפוס), {len(groups)} ספרים לפי המניין המסורתי (24)",
                      {"books": found, "groups_24": groups})

    def chapters():
        bad = []
        for b in BOOKS:
            chs = sorted({v.chapter for v in corpus.verses if v.book == b.osis})
            if chs != list(range(1, b.chapters + 1)):
                bad.append({"book": b.osis, "found": len(chs), "expected": b.chapters})
        total = len({(v.book, v.chapter) for v in corpus.verses})
        return _check("chapters", "שלמות הפרקים", "pass" if not bad and total == 929 else "fail",
                      f"{total} פרקים (צפוי 929); " + ("כל הפרקים רציפים" if not bad else f"{len(bad)} ספרים חריגים"),
                      {"total": total, "problems": bad})

    def verses():
        problems = []
        by_chapter: dict = {}
        for v in corpus.verses:
            by_chapter.setdefault((v.book, v.chapter), []).append(v.verse)
        for key, nums in by_chapter.items():
            if nums != list(range(1, len(nums) + 1)):
                problems.append({"chapter": f"{key[0]} {key[1]}", "numbers": nums[:200]})
        dup = [o for o, c in Counter(corpus.verse_osis).items() if c > 1]
        n = len(corpus.verses)
        ok = not problems and not dup and n == 23202 and len(raw) == n
        return _check("verses", "שלמות הפסוקים וסדרם", "pass" if ok else "fail",
                      f"{n} פסוקים (MAM מתעד 23,202); בקובצי המקור {len(raw)}; כפולים: {len(dup)}; "
                      f"פרקים עם מספור לא רציף: {len(problems)}",
                      {"count": n, "raw_count": len(raw), "duplicates": dup, "gaps": problems})

    def order():
        raw_ids = [r["osisID"] for r in raw]
        expected = sorted(raw_ids, key=lambda o: (BOOK_INDEX[o.split(".")[0]], int(o.split(".")[1]), int(o.split(".")[2])))
        same_set = sorted(raw_ids) == sorted(corpus.verse_osis)
        ok = expected == corpus.verse_osis and same_set
        within = all(raw_ids[i] != raw_ids[i + 1] for i in range(len(raw_ids) - 1))
        return _check("location_ids", "תקינות מזהי המיקום וסדר הפסוקים", "pass" if ok and within else "fail",
                      "מזהי הפסוקים ייחודיים, זהים למקור ומסודרים לפי ספר־פרק־פסוק" if ok else "נמצאה סטייה בסדר או במזהים")

    def letters():
        out = []
        for name, role, layer in (("ketiv", "k", L_k), ("qere", "q", L_q)):
            bad = []
            total_raw = 0
            for vi, node in enumerate(raw):
                vi2 = corpus.verse_index[node["osisID"]]
                expect = independent_letter_extract(node, role)
                total_raw += len(expect)
                s, n = int(layer.verse_wstart[vi2]), int(layer.verse_wcount[vi2])
                got = "".join(layer.word_consonants[w] for w in range(s, s + n))
                if got != expect:
                    bad.append(node["osisID"])
            out.append(_check(f"letters_{name}", f"שלמות האותיות — {'כתיב' if role == 'k' else 'קרי'}",
                              "pass" if not bad and total_raw == layer.n_letters else "fail",
                              f"מחלץ עצמאי: {total_raw:,} אותיות; במאגר: {layer.n_letters:,}; פסוקים שונים: {len(bad)}",
                              {"raw_letters": total_raw, "corpus_letters": layer.n_letters, "mismatched_verses": bad[:50]}))
        return out

    def marks():
        out = []
        for name, role, keep in (("ketiv", "k", "q"), ("qere", "q", "k")):
            raw_c = Counter()
            for node in raw:
                raw_c.update(_raw_marks(node, role))
            got = Counter()
            excluded = 1 if role == "q" else 2  # role code to drop
            for a in np.nonzero(corpus.a_role != excluded)[0].tolist():
                got.update(_marks_of(corpus.a_text[a]))
            vowels = {k: v for k, v in raw_c.items() if not H.is_accent(k)}
            accents = {k: v for k, v in raw_c.items() if H.is_accent(k)}
            gv = {k: v for k, v in got.items() if not H.is_accent(k)}
            ga = {k: v for k, v in got.items() if H.is_accent(k)}
            out.append(_check(f"niqqud_{name}", f"שלמות סימני הניקוד — {'כתיב' if role == 'k' else 'קרי'}",
                              "pass" if vowels == gv else "fail",
                              f"{sum(vowels.values()):,} סימני ניקוד במקור; {sum(gv.values()):,} במאגר",
                              {"source": {f"U+{ord(k):04X}": v for k, v in sorted(vowels.items())},
                               "corpus": {f"U+{ord(k):04X}": v for k, v in sorted(gv.items())}}))
            out.append(_check(f"accents_{name}", f"שלמות טעמי המקרא — {'כתיב' if role == 'k' else 'קרי'}",
                              "pass" if accents == ga else "fail",
                              f"{sum(accents.values()):,} סימני טעמים במקור; {sum(ga.values()):,} במאגר"))
        return out

    def markers():
        rawc = _raw_markers()
        got = Counter()
        for v in corpus.verses:
            got.update(v.markers_before)
            got.update(v.markers_end)
            got.update(a.marker_before for a in v.atoms if a.marker_before)
        expected = Counter({MARKERS[k]: v for k, v in rawc.items()})
        consistent = []
        for i, v in enumerate(corpus.verses):
            if v.starts_with_sampe and not v.markers_before and not (i and corpus.verses[i - 1].markers_end):
                consistent.append(v.osis)
        # a section marker must never become a letter: no atom may consist of a bare פ or ס
        bare = [(corpus.verses[corpus.a_verse[a]].osis, t) for a, t in enumerate(corpus.a_text)
                if H.letters_only(t) in ("פ", "ס") and not any(ch in H.VOWEL_POINTS for ch in t)]
        ok = got == expected and not consistent and not bare
        return _check("parashah_markers", "סימוני פרשות פתוחות וסתומות", "pass" if ok else "fail",
                      f"במקור {sum(expected.values()):,} סימונים, במאגר {sum(got.values()):,}; "
                      f"סימון פ/ס שהפך לאות: {len(bare)}; אי־התאמות starts-with-sampe: {len(consistent)}. "
                      "הסימונים נשמרים כמבנה ואינם נספרים כאותיות.",
                      {"source": dict(expected), "corpus": dict(got), "bare_pe_samekh_atoms": bare[:20],
                       "inconsistent": consistent[:20],
                       "sections": len(masoretic_sections(corpus))})

    def ketiv_qere():
        groups: dict[int, set] = {}
        pointed_ketiv = []
        for a in range(len(corpus.a_text)):
            g = int(corpus.a_kq[a])
            if g >= 0:
                groups.setdefault(g, set()).add(int(corpus.a_role[a]))
                if corpus.a_role[a] == 1 and any(ch in H.VOWEL_POINTS for ch in corpus.a_text[a]):
                    pointed_ketiv.append(corpus.verses[corpus.a_verse[a]].osis)
        pairs = sum(1 for s in groups.values() if s == {1, 2})
        k_only = sum(1 for s in groups.values() if s == {1})
        q_only = sum(1 for s in groups.values() if s == {2})
        both_in_layer = 0
        for layer, drop in ((L_k, 2), (L_q, 1)):
            both_in_layer += int((layer.word_role == drop).sum())
        ok = pairs == 1047 and k_only == 8 and q_only == 9 and both_in_layer == 0
        return _check("ketiv_qere", "קרי וכתיב", "pass" if ok else "fail",
                      f"{pairs} זוגות קרי/כתיב (MAM: 1,047), {k_only} כתיב ולא קרי, {q_only} קרי ולא כתיב; "
                      f"כתיב מנוקד: {len(pointed_ketiv)}; קרי וכתיב באותה שכבה: {both_in_layer}",
                      {"pairs": pairs, "ketiv_only": k_only, "qere_only": q_only,
                       "pointed_ketiv": pointed_ketiv[:20]})

    def parashot():
        bad = []
        for p in weekly_parashot(corpus):
            w = L_k.word_consonants[L_k.verse_wstart[p.start]]
            if w != p.first_word_expected:
                bad.append({"parasha": p.name, "found": w, "expected": p.first_word_expected})
        n = len(weekly_parashot(corpus))
        return _check("weekly_parashot", "חלוקת פרשות השבוע", "pass" if not bad and n == 54 else "fail",
                      f"{n} פרשות; המילה הראשונה של כל פרשה נבדקה מול הטקסט: {n - len(bad)} תקינות", {"problems": bad})

    def parse_warnings():
        st = corpus.source_info.get("reader_stats", {})
        bad = {k: v for k, v in st.items() if not k.startswith("type:") and k != "marker_at_verse_end"}
        warns = corpus.parse_warnings
        return _check("unicode", "תווים לא צפויים וסימנים יתומים", "pass" if not bad and not warns else "fail",
                      f"תווים לא צפויים / סימנים ללא אות: {len(warns)}; חריגות מבנה: {sum(bad.values()) if bad else 0}",
                      {"warnings": warns[:50], "reader": bad})

    def shuruq():
        review = np.nonzero(corpus.al_flags & 32)[0]
        cases = []
        for li in review.tolist():
            a = int(np.searchsorted(corpus.a_lstart, li, side="right") - 1)
            cases.append({"verse": corpus.verses[corpus.a_verse[a]].osis, "word": corpus.a_text[a]})
        shuruq_n = int((corpus.al_combo == 12).sum())
        cons = []
        for li in np.nonzero(corpus.al_flags & 64)[0].tolist():
            a = int(np.searchsorted(corpus.a_lstart, li, side="right") - 1)
            cons.append({"verse": corpus.verses[corpus.a_verse[a]].osis, "word": corpus.a_text[a]})
        return _check("shuruq", "זיהוי שורוק", "warn" if cases else "pass",
                      f"{shuruq_n:,} שורוקים; {len(cons)} ו׳ עיצוריות דגושות (ו׳ דגושה שאחריה ו׳ הנושאת את התנועה, "
                      f"כגון וַיְצַוּוּ — סווגו לפי כלל מפורש כאות ללא תנועה); "
                      f"{len(cases)} מקרים לא ודאיים סומנו לבדיקה ולא סווגו",
                      {"unclear_cases": cases, "consonantal_vav_cases": cons})

    def wlc():
        from ..importers.wlc import read_wlc
        wdir = config.RAW_DIR / "wlc"
        if not (wdir / "Gen.xml").exists():
            return _check("wlc_comparison", "השוואה לכתב יד לנינגרד (WLC)", "not_run", "קובצי WLC אינם זמינים")
        w = read_wlc(wdir)
        reader = MamSimpleReader()
        mam = {}
        for name in MAM_SIMPLE_FILES:
            d = "json-vtrad-bhs" if name in BHS_FILES else "json-vtrad-mam"
            for v in reader.read_file(config.RAW_DIR / "mam" / d / f"{name}.json"):
                mam[v.osis] = [H.letters_only(a.text) for a in v.atoms if a.role != "q" and H.letters_only(a.text)]
        same, diffs = 0, []
        for o, x in w.items():
            if o not in mam:
                diffs.append({"verse": o, "note": "חסר ב־MAM"})
                continue
            a, b = mam[o], x["ketiv"]
            if "".join(a) == "".join(b):
                same += 1
            else:
                ops = [{"mam": " ".join(a[i1:i2]), "wlc": " ".join(b[j1:j2])}
                       for t, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if t != "equal"]
                diffs.append({"verse": o, "diff": ops[:6]})
        missing = [o for o in mam if o not in w]
        torah = {"Gen", "Exod", "Lev", "Num", "Deut"}
        wlc_torah = sum(len("".join(x["ketiv"])) for o, x in w.items() if o.split(".")[0] in torah)
        return _check("wlc_comparison", "השוואה למקור ביקורת: כתב יד לנינגרד (WLC, OSHB)", "info",
                      f"{same:,} פסוקים זהים באותיותיהם, {len(diffs)} שונים (רובם הבדלי כתיב מלא/חסר בין כתר ארם צובא "
                      f"לכתב יד לנינגרד); {len(missing)} פסוקים של MAM חסרים ב־WLC. "
                      f"אותיות תורה ב־WLC: {wlc_torah:,}. ההשוואה בוצעה בחלוקת הפסוקים של BHS.",
                      {"identical": same, "different": len(diffs), "differences": diffs, "missing_in_wlc": missing,
                       "wlc_torah_letters": wlc_torah})

    def known_totals():
        torah = np.isin(corpus.verse_book[L_k.l_verse], [0, 1, 2, 3, 4])
        letters = int(torah.sum())
        words = int(np.isin(corpus.verse_book[L_k.word_verse], [0, 1, 2, 3, 4]).sum())
        return _check("torah_totals", "סיכומי התורה (כתיב)", "info",
                      f"אותיות בתורה לפי MAM: {letters:,}; מילים: {words:,} (מקף מפריד). "
                      "המספר המסורתי המקובל לספר תורה אשכנזי/ספרדי הוא 304,805 אותיות. ההפרש לא נבדק כאן אות־אות "
                      "ואינו מוצג כשגיאה או כהצלחה; ההבדלים בפועל מול WLC מפורטים בבדיקת ההשוואה.",
                      {"torah_letters": letters, "torah_words": words, "traditional_letters": 304805,
                       "difference": letters - 304805})

    for fn in (source_hashes, books, chapters, verses, order, letters, marks, markers, ketiv_qere, parashot,
               parse_warnings, shuruq, known_totals):
        guarded(fn)
    if include_wlc:
        guarded(wlc)
    status = "fail" if any(c["status"] == "fail" for c in checks) else (
        "incomplete" if any(c["status"] == "not_run" for c in checks) else "pass")
    report = {
        "status": status, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1), "source": corpus.source_info,
        "counts": {"verses": len(corpus.verses), "words_ketiv": L_k.n_words, "letters_ketiv": L_k.n_letters,
                   "words_qere": L_q.n_words, "letters_qere": L_q.n_letters},
        "checks": checks,
    }
    config.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    config.VALIDATION_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report
