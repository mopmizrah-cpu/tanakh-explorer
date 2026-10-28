"""Generate the reference documents in ``docs/`` from the code and from the
latest validation and benchmark runs, so the documentation cannot drift from
the implementation. Run: ``python -m tanakh_explorer.docsgen``."""

from __future__ import annotations

import json

from . import config
from . import gematria as G
from . import transformations as X
from .niqqud_gematria import DEFAULT_VALUES
from .niqqud import VOWEL_HEBREW

DOCS = config.PROJECT_ROOT / "docs"
CAT_HE = {"traditional": "מסורתית מתועדת", "mathematical": "מתמטית", "niqqud": "ניקוד (טבלת החוקר)",
          "custom": "מותאמת אישית", "user_defined": "הגדרת המשתמש"}


def gematria_doc() -> str:
    out = ["# שיטות הגימטריה\n", "המסמך נוצר אוטומטית מקוד המערכת (`tanakh_explorer/gematria/methods.py`).\n",
           "כל שיטה מוגדרת כיחידה עצמאית עם מזהה ייחודי. הוספת שיטה אינה דורשת שינוי במנוע החיפוש.\n",
           "סדר הפעולות בכל שיטה: (1) ערכי אותיות → (2) שקלול מיקום (אם יש) → (3) עיבוד הסכום (אם יש).\n"]
    for m in G.REGISTRY.values():
        if m.category == "custom":
            continue
        out.append(f"\n## {m.name_he}\n")
        out.append(f"- **מזהה:** `{m.id}` · **שם לועזי:** {m.name_en} · **קטגוריה:** {CAT_HE[m.category]}\n")
        out.append(f"- **נוסחה:** {m.formula_he}\n- **מקור:** {m.source_he}\n- **אותיות סופיות:** {m.finals_he}\n")
        if m.params:
            out.append("- **הגדרות:** " + "; ".join(
                f"`{p.name}` — {p.label_he} (ברירת מחדל: {p.default})" for p in m.params) + "\n")
        out.append(f"- **דוגמה:** שלום = {m.compute('שָׁלוֹם')['value']}\n")
    return "".join(out)


def transformations_doc() -> str:
    out = ["# שיטות חילופי האותיות\n", "המסמך נוצר אוטומטית מקוד המערכת (`tanakh_explorer/transformations/methods.py`).\n",
           "חילוף הוא פעולת טקסט → טקסט. הניקוד נשאר במקומו (על אותו מיקום), נקודות שין/שׂין מושמטות כשהאות אינה ש.\n"]
    for t in X.REGISTRY.values():
        d = t.to_dict()
        out.append(f"\n## {t.name_he}\n")
        out.append(f"- **מזהה:** `{t.id}` · **שם לועזי:** {t.name_en} · **קטגוריה:** {CAT_HE[t.category]}\n")
        out.append(f"- **תיאור:** {t.description_he}\n- **מקור:** {t.source_he}\n")
        out.append(f"- **מדיניות אותיות סופיות (ברירת מחדל):** {t.finals_default} · "
                   f"**החלפה הדדית:** {'כן' if d['involution'] else 'לא'}\n")
        if t.params:
            out.append("- **הגדרות:** " + "; ".join(f"`{p.name}` — {p.label_he}" for p in t.params) + "\n")
        table = t.table()
        out.append("\n| " + " | ".join(r["from"] for r in table) + " |\n|" + "---|" * len(table) + "\n| "
                   + " | ".join(r["to"] for r in table) + " |\n")
    out.append("\n## חילופי מוצאות הפה\n\nלפי ספר יצירה (ב, ג): " + "; ".join(
        f"{g['name_he']} — {g['letters']}" for g in X.articulation_groups())
        + ". אין מיפוי אחד־לאחד מתועד בתוך קבוצה, ולכן המערכת מממשת זאת כהתאמה: אות בשאילתה מתאימה לכל אות מקבוצתה "
          "(״קבוצות אותיות״ בחיפוש). מיפוי אחר אפשר להגדיר ב״מיפוי אותיות מותאם״ בחיפוש המשולב.\n")
    return "".join(out)


def niqqud_doc() -> str:
    rows = "\n".join(f"| {VOWEL_HEBREW[k]} | `{k}` | {v} |" for k, v in DEFAULT_VALUES.items())
    return f"""# מערכת הניקוד

## ניתוח
* כל אות היא *יחידת אות*: האות ואחריה כל הסימנים המשולבים עד האות הבאה, בסדר המקור. סימנים אינם עוברים בין אותיות.
* תנועות: שווא, חטפים, חיריק, צירי, סגול, פתח, קמץ, קמץ קטן (U+05C7), חולם (כולל חולם חסר לוו U+05BA), קובוץ, שורוק.
* דגש/מפיק, מתג, רפה, נקודות שין/שׂין, טעמי המקרא והנקודות שעל האותיות אינם תנועות ואין להם ערך.
* שווא עם פתח/קמץ/סגול על אותה אות = חטף אחד (נספר פעם אחת).
* אות יכולה לשאת יותר מתנועה אחת (למשל ירושלַ͏ִם): כל תנועה נספרת פעם אחת.
* **שורוק:** ו עם U+05BC וללא תנועה, כשהיא ראשונה במילה או כשהאות שלפניה אינה נושאת תנועה.
  **ו עיצורית דגושה:** ו דגושה ללא תנועה אחרי אות מנוקדת, שאחריה ו הנושאת את התנועה (וַיְצַוּוּ, הַוּוֹת) — אות ללא תנועה, לפי כלל מפורש.
  כל מקרה אחר מסומן ״לא ודאי״ ואינו מסווג. בתנ״ך המלא: 37,088 שורוקים, 22 ו׳ עיצוריות, 0 מקרים לא ודאיים.

## טבלת הערכים (ברירת מחדל; כל ערך ניתן לשינוי בבקשה דרך `niqqud_values`)

| תנועה | מזהה | ערך |
|---|---|---:|
{rows}

טבלה זו הוגדרה על ידי החוקר לצורכי המחקר ואינה מוצגת כשיטת גימטריה מסורתית. ״ללא תנועה״ הוא מצב נפרד שערכו 0.

## חתימת ניקוד
לכל אות נשמר מזהה צירוף התנועות (`combo`, מספר שלם: אינדקס התנועה הראשונה + 16 × השנייה …). החיפוש משווה:
* **ניקוד מדויק** — אותו צירוף תנועות לכל אות (סגול ≠ קובוץ). ברירת מחדל: קמץ קטן = קמץ (ניתן לביטול).
* **ערכים לפי הסדר** — אותו ערך מספרי לכל אות.
* **אותיות + ניקוד** — גם האות וגם הניקוד.
* **סכום** — סכום הערכים בלבד.
"""


def validation_doc() -> str:
    if not config.VALIDATION_REPORT.exists():
        return "# דוח תקינות\n\nהאימות טרם הורץ. הריצו `python -m tanakh_explorer validate`.\n"
    r = json.loads(config.VALIDATION_REPORT.read_text(encoding="utf-8"))
    st = {"pass": "✅ עבר", "fail": "❌ נכשל", "warn": "⚠️ לבדיקה", "info": "ℹ️ מידע", "not_run": "⏸ לא בוצע"}
    lines = [f"# דוח תקינות\n\nנוצר: {r['created']} · סטטוס כולל: **{r['status']}**\n",
             f"\nמקור: {r['source']['source']} · `{r['source']['repo']}@{r['source']['commit']}` · {r['source']['license']}\n",
             "\n| בדיקה | סטטוס | תוצאה |\n|---|---|---|\n"]
    for c in r["checks"]:
        lines.append(f"| {c['name_he']} | {st.get(c['status'], c['status'])} | {c['summary_he']} |\n")
    w = next((c for c in r["checks"] if c["id"] == "wlc_comparison"), None)
    if w and w["details"].get("differences"):
        lines.append("\n## דוגמאות להבדלים בין MAM ל־WLC (20 הראשונים)\n\n| פסוק | MAM | WLC |\n|---|---|---|\n")
        for d in w["details"]["differences"][:20]:
            for op in d.get("diff", [])[:2]:
                lines.append(f"| {d['verse']} | {op['mam']} | {op['wlc']} |\n")
    return "".join(lines)


def bench_doc() -> str:
    p = config.BUILD_DIR / "bench.json"
    if not p.exists():
        return "# ביצועים\n\nהריצו `python -m tanakh_explorer bench`.\n"
    b = json.loads(p.read_text(encoding="utf-8"))
    rows = "".join(f"| {c['case']} | {c['median_ms']} | {c['total'] if c['total'] is not None else '—'} |\n" for c in b["cases"])
    return (f"# ביצועים על התנ״ך המלא\n\nמכונה: {b['machine']} · Python {b['python']} · טעינת המאגר: {b['corpus_load_s']} שניות"
            f" · נמדד: {b['created']}\n\nזמן חציוני מתוך 3 הרצות.\n\n| בדיקה | מ״ש | תוצאות |\n|---|---:|---:|\n{rows}")


def main():
    DOCS.mkdir(exist_ok=True)
    for name, fn in (("GEMATRIA.md", gematria_doc), ("TRANSFORMATIONS.md", transformations_doc),
                     ("NIQQUD.md", niqqud_doc), ("VALIDATION.md", validation_doc), ("BENCHMARKS.md", bench_doc)):
        (DOCS / name).write_text(fn(), encoding="utf-8")
        print("wrote", DOCS / name)


if __name__ == "__main__":
    main()
