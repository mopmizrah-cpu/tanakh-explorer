"""Definitions of the gematria methods.

Categories:

* ``traditional`` — methods with a documented definition in the Jewish
  literature (the source field says where);
* ``mathematical`` — well-defined mathematical variants that are not
  presented as traditional (e.g. arbitrary powers);
* ``niqqud`` — the researcher's own niqqud table (not traditional);
* ``custom`` — "שיטות מותאמות אישית", user-defined letter tables.

Where one Hebrew name is used in the literature for two different formulas
(מספר משולש), each formula has its own id.
"""

from __future__ import annotations

import numpy as np

from .. import hebrew as H
from . import tables as T
from .engine import Method, ParamSpec, register

# --- letter tables -------------------------------------------------------------


def standard(p=None):
    return dict(T.STANDARD)


def gadol(p=None):
    t = dict(T.STANDARD)
    t.update(T.GADOL_FINALS)
    return t


def _strip_zeros(v: int) -> int:
    while v and v % 10 == 0:
        v //= 10
    return v


def katan(p):
    base = gadol() if p.get("finals") == "gadol" else standard()
    return {k: _strip_zeros(v) for k, v in base.items()}


def ordinal(p):
    t = {ch: i + 1 for i, ch in enumerate(H.ALEPHBET)}
    for i, f in enumerate(H.FINALS):
        t[f] = 23 + i if p.get("finals") == "extended" else t[H.FINAL_TO_REGULAR[f]]
    return t


def kidmi(p=None):
    t, acc = {}, 0
    for ch in H.ALEPHBET:
        acc += T.STANDARD[ch]
        t[ch] = acc
    for f, r in H.FINAL_TO_REGULAR.items():
        t[f] = t[r]
    return t


def _names(p):
    custom = p.get("custom") or {}
    return T.letter_name_table(p.get("preset", "common"), custom)


def milui(p):
    names = _names(p)
    depth = int(p.get("depth", 1))
    std = T.STANDARD

    def expand(s: str, d: int) -> str:
        for _ in range(d):
            s = "".join(names[ch] for ch in s)
        return s

    return {ch: sum(std[c] for c in expand(ch, depth)) for ch in H.ALL_LETTERS}


def neelam(p):
    names = _names(p)
    return {ch: sum(T.STANDARD[c] for c in names[ch][1:]) for ch in H.ALL_LETTERS}


def mispari(p):
    base = gadol() if p.get("finals") == "gadol" else standard()
    out = {}
    for ch, v in base.items():
        name = T.number_name(v, p.get("gender", "masc"), p.get("spelling", "defective"))
        out[ch] = sum(T.STANDARD[c] for c in name if c in H.LETTER_CODE)
    return out


def squares(p=None):
    return {k: v * v for k, v in T.STANDARD.items()}


def cubes(p=None):
    return {k: v ** 3 for k, v in T.STANDARD.items()}


def power_letters(p):
    k = int(p["power"])
    return {ch: v ** k for ch, v in T.STANDARD.items()}


BASES = {
    "standard": ("רגילה", standard),
    "gadol": ("מנצפ״ך רבתי", gadol),
    "katan": ("קטנה", lambda p: katan({"finals": "regular"})),
    "ordinal": ("סידורית", lambda p: ordinal({"finals": "regular"})),
    "kidmi": ("קדמית", kidmi),
}
BASE_PARAM = ParamSpec("base", "choice", "standard", "ערכי האותיות הבסיסיים",
                       [(k, v[0]) for k, v in BASES.items()])


def based(p):
    return BASES[p.get("base", "standard")][1](p)


def digit_root(s):
    s = np.asarray(s) if not np.isscalar(s) else s
    if np.isscalar(s):
        return 0 if s == 0 else 1 + (s - 1) % 9
    return np.where(s == 0, 0, 1 + (s - 1) % 9)


def _pow(s, k):
    if np.isscalar(s):
        return int(s) ** k
    return np.asarray(s, dtype=object) ** k


FINALS_REGULAR = "אותיות סופיות מקבלות את ערך האות הרגילה (ך=20, ם=40, ן=50, ף=80, ץ=90)."

# --- registration --------------------------------------------------------------

register(Method(
    "standard", "גימטריה רגילה (מספר הכרחי)", "Mispar Hechrachi", "traditional",
    "כל אות לפי ערכה: א=1 … ט=9, י=10 … צ=90, ק=100 … ת=400; סכום הערכים.",
    "השיטה הבסיסית, מתועדת כבר במשנה (אבות ג, יח: ״גימטריאות — פרפראות לחכמה״) ובברייתא דל״ב מידות.",
    FINALS_REGULAR, letter_table=standard))

register(Method(
    "gadol", "מנצפ״ך רבתי (מספר גדול)", "Mispar Gadol", "traditional",
    "כמו הגימטריה הרגילה, אך האותיות הסופיות: ך=500, ם=600, ן=700, ף=800, ץ=900.",
    "שיטה מתועדת בספרות הקבלה והפרשנות (למשל בפירוש בעל הטורים).",
    "לאותיות הסופיות ערכים 500–900.", letter_table=gadol))

register(Method(
    "katan", "גימטריה קטנה (מספר קטן)", "Mispar Katan", "traditional",
    "ערך כל אות ללא אפסים: י=1, כ=2, ק=1, ר=2, ש=3, ת=4; סכום הערכים (התוצאה אינה מצומצמת).",
    "מתועדת בספרות הקבלה (פרדס רימונים ועוד) בשם ״מספר קטן״.",
    "ברירת מחדל: הסופיות כאות הרגילה (ך=2); אפשר לבחור סופיות לפי מנצפ״ך רבתי (ך=5 … ץ=9).",
    letter_table=katan,
    params=[ParamSpec("finals", "choice", "regular", "אותיות סופיות",
                      [("regular", "כאות הרגילה"), ("gadol", "לפי מנצפ״ך רבתי")])]))

register(Method(
    "katan_reduced", "גימטריה קטנה מצומצמת (סכום ספרות חוזר)", "Mispar Katan Mispari", "traditional",
    "מחשבים מספר קטן ואז מצמצמים את התוצאה לספרה אחת בסכימת ספרות חוזרת (1–9; 0 נשאר 0).",
    "נקרא גם ״מספר קטן מספרי״; שיטה נפרדת מן הגימטריה הקטנה שאינה מצמצמת את הסכום.",
    "כמו בגימטריה הקטנה.", letter_table=katan,
    post=lambda s, nl, nw, p: digit_root(s), post_he=lambda p: "צמצום לספרה אחת",
    params=[ParamSpec("finals", "choice", "regular", "אותיות סופיות",
                      [("regular", "כאות הרגילה"), ("gadol", "לפי מנצפ״ך רבתי")])]))

register(Method(
    "kolel", "גימטריה עם הכולל", "Im HaKolel", "traditional",
    "גימטריה + 1 על הביטוי כולו, או + 1 לכל מילה.",
    "״עם הכולל״ — מקובל בספרות הקבלה ובפרשנות (לדוגמה אצל בעל הטורים).",
    FINALS_REGULAR, letter_table=based,
    post=lambda s, nl, nw, p: s + (nw if p["scope"] == "word" else 1),
    post_he=lambda p: "+1 לכל מילה" if p["scope"] == "word" else "+1 (הכולל)",
    params=[ParamSpec("scope", "choice", "phrase", "החלת הכולל",
                      [("phrase", "פעם אחת לביטוי"), ("word", "לכל מילה")]), BASE_PARAM]))

register(Method(
    "ordinal", "גימטריה סידורית (מספר סידורי)", "Mispar Siduri", "traditional",
    "ערך כל אות לפי מיקומה באלף־בית: א=1 … ת=22.",
    "מתועדת בספרות הקבלה בשם ״מספר סידורי״.",
    "ברירת מחדל: סופיות כאות הרגילה; אפשרות לסדר מורחב ך=23, ם=24, ן=25, ף=26, ץ=27.",
    letter_table=ordinal,
    params=[ParamSpec("finals", "choice", "regular", "אותיות סופיות",
                      [("regular", "כאות הרגילה"), ("extended", "סדר מורחב 23–27")])]))

MILUI_PARAMS = [
    ParamSpec("preset", "choice", "common", "נוסח המילוי",
              [(k, v["name_he"]) for k, v in T.MILUI_PRESETS.items()]),
    ParamSpec("custom", "json", {}, "מילוי מותאם אישית לאותיות מסוימות (למשל {\"ה\": \"הי\"})"),
]

register(Method(
    "milui", "גימטריית מילוי (מספר שמי)", "Mispar Shemi / Milui", "traditional",
    "כל אות מחושבת לפי האיות המלא של שמה (א=אלף=111, ב=בית=412 …).",
    "מילוי האותיות מתועד בספרות הקבלה (פרדס רימונים, כתבי האר״י); נוסחי המילוי של ה ו־ו משתנים.",
    "אות סופית ממולאת כמו האות הרגילה (ם=מם).", letter_table=lambda p: milui({**p, "depth": 1}),
    params=MILUI_PARAMS))

register(Method(
    "milui_demilui", "מילוי דמילוי", "Milui deMilui", "traditional",
    "ממלאים את האותיות, ואז ממלאים שוב את אותיות המילוי — בעומק שהמשתמש בוחר (2 = מילוי דמילוי).",
    "מתועד בכתבי האר״י ובספרות הקבלה.",
    "אות סופית ממולאת כמו האות הרגילה.", letter_table=milui,
    params=[ParamSpec("depth", "int", 2, "עומק המילוי", min=1, max=4)] + MILUI_PARAMS))

register(Method(
    "neelam", "מספר נעלם", "Mispar Ne'elam", "traditional",
    "ערך האותיות הנוספות שבמילוי כל אות, בלי האות עצמה (א: אלף → לף = 110).",
    "מתועד בספרות הקבלה; תלוי בנוסח המילוי שנבחר.",
    "אות סופית כאות הרגילה.", letter_table=neelam, params=MILUI_PARAMS))

register(Method(
    "kidmi", "מספר קדמי", "Mispar Kidmi", "traditional",
    "ערך כל אות = סכום ערכי כל האותיות מתחילת האלף־בית עד אליה: א=1, ב=3, ג=6, ד=10 … ת=1495.",
    "מתועד בספרות הקבלה (נקרא גם ״מספר משולש״ במקורות אחדים).",
    "אות סופית כאות הרגילה.", letter_table=kidmi))

register(Method(
    "meshulash_kidmi", "מספר משולש — קדמי מצטבר", "Mispar Meshulash (triangular)", "traditional",
    "השימוש בשם ״משולש״ במובן הקדמי המצטבר: א=1, ב=1+2=3, ג=6 … (אותה נוסחה כמו המספר הקדמי).",
    "יש מקורות שבהם ״מספר משולש״ פירושו המספר הקדמי; מוצג כמזהה נפרד כדי לא לבלבל עם החזקה השלישית.",
    "אות סופית כאות הרגילה.", letter_table=kidmi))

register(Method(
    "meshulash_cube", "מספר משולש — חזקה שלישית", "Mispar Meshulash (cube)", "traditional",
    "ערך כל אות בחזקה שלישית: ב=2³=8, ג=3³=27 … ; סכום הערכים.",
    "יש מקורות שבהם ״מספר משולש״ פירושו העלאה בחזקת 3; מזהה נפרד מן הקדמי.",
    "אות סופית כאות הרגילה.", letter_table=cubes))

register(Method(
    "prati", "מספר הפרטי (ריבוע האותיות)", "Mispar Prati / Meruba Prati", "traditional",
    "ערך כל אות בריבוע: ב=4, ג=9 … ת=160000; סכום הריבועים.",
    "מתועד בספרות הקבלה בשם ״מספר המרובע הפרטי״.",
    "אות סופית כאות הרגילה.", letter_table=squares))

register(Method(
    "merubah_klali", "מספר המרובע הכללי", "Mispar Meruba Klali", "traditional",
    "סכום הגימטריה של כל הביטוי, ואז העלאת הסכום בריבוע (שונה מסכום ריבועי האותיות).",
    "מתועד בספרות הקבלה בשם ״מרובע הכללי״.",
    FINALS_REGULAR, letter_table=based,
    post=lambda s, nl, nw, p: _pow(s, 2), post_he=lambda p: "העלאת הסכום בריבוע", params=[BASE_PARAM]))

register(Method(
    "boneh", "מספר בונה (ריבוע / בניין)", "Mispar Boneh", "traditional",
    "סכום כל הרישות המצטברות: אבג → א + אב + אבג = 1 + 3 + 6 = 10.",
    "בקבלה נקרא גם ״ריבוע״ של השם (י, יה, יהו, יהוה = 72).",
    FINALS_REGULAR, letter_table=based, weighting=lambda p: "boneh", reset=lambda p: p["reset"],
    params=[ParamSpec("reset", "choice", "word", "בביטוי של כמה מילים",
                      [("word", "מתחילים מחדש בכל מילה"), ("phrase", "רצף אחד לאורך הביטוי")]), BASE_PARAM]))

register(Method(
    "achor", "מספר האחור (ערך × מיקום)", "Mispar HaAchor", "traditional",
    "כל אות כפול מיקומה ברצף: ראשונה ×1, שנייה ×2 …",
    "בהגדרה שנמסרה בבקשה. שים לב: במקורות הקבלה ״אחוריים״ מציין לעיתים את המספר הבונה.",
    FINALS_REGULAR, letter_table=based, weighting=lambda p: "achor", reset=lambda p: p["reset"],
    params=[ParamSpec("reset", "choice", "word", "מיקום האות",
                      [("word", "מתאפס בכל מילה"), ("phrase", "ממשיך לאורך הביטוי")]), BASE_PARAM]))

register(Method(
    "mosafi", "מספר מוספי (עם האותיות)", "Mispar Musafi", "traditional",
    "גימטריה + מספר האותיות בביטוי.",
    "״עם האותיות״ — מקובל בפרשנות ובקבלה.",
    FINALS_REGULAR, letter_table=based, post=lambda s, nl, nw, p: s + nl,
    post_he=lambda p: "+ מספר האותיות", params=[BASE_PARAM]))

register(Method(
    "with_words", "גימטריה עם מספר המילים", "With word count", "traditional",
    "גימטריה + מספר המילים בביטוי (שונה מתוספת מספר האותיות).",
    "״עם התיבות״ — מקובל בפרשנות.",
    FINALS_REGULAR, letter_table=based, post=lambda s, nl, nw, p: s + nw,
    post_he=lambda p: "+ מספר המילים", params=[BASE_PARAM]))

register(Method(
    "mispari", "מספר מספרי", "Mispar Mispari", "traditional",
    "ערך כל אות = הגימטריה של שם המספר שהיא מייצגת: א=1=אחד=13, ב=2=שנים=400 …",
    "מתועד בספרות הקבלה; כתיב שמות המספרים לפי הכתיב המקראי (שלשה, שמנה) או מלא, בלשון זכר או נקבה.",
    "ברירת מחדל: סופיות כאות הרגילה; אפשר לפי מנצפ״ך רבתי (ך=500=חמש מאות).",
    letter_table=mispari,
    params=[ParamSpec("gender", "choice", "masc", "לשון", [("masc", "זכר (אחד, שנים…)"), ("fem", "נקבה (אחת, שתים…)")]),
            ParamSpec("spelling", "choice", "defective", "כתיב", [("defective", "חסר (שלשה)"), ("plene", "מלא (שלושה)")]),
            ParamSpec("finals", "choice", "regular", "אותיות סופיות",
                      [("regular", "כאות הרגילה"), ("gadol", "לפי מנצפ״ך רבתי")])]))

register(Method(
    "power_letters", "חזקה לכל אות", "Letter power", "mathematical",
    "ערך כל אות בחזקה שהמשתמש בוחר, וסכום התוצאות.",
    "שיטה מתמטית כללית (חזקה 2 = מספר הפרטי, חזקה 3 = משולש בחזקה).",
    FINALS_REGULAR, letter_table=power_letters,
    params=[ParamSpec("power", "int", 2, "חזקה", min=1, max=8)]))

register(Method(
    "power_total", "חזקה לסכום הכולל", "Total power", "mathematical",
    "סכום הגימטריה של הביטוי, ואז העלאה בחזקה שהמשתמש בוחר.",
    "שיטה מתמטית כללית (חזקה 2 = המרובע הכללי).",
    FINALS_REGULAR, letter_table=based,
    post=lambda s, nl, nw, p: _pow(s, int(p["power"])), post_he=lambda p: f"העלאה בחזקת {p['power']}",
    params=[ParamSpec("power", "int", 2, "חזקה", min=1, max=8), BASE_PARAM]))

register(Method(
    "ordinal_katan", "סידורי מצומצם (סכום ספרות)", "Reduced ordinal", "mathematical",
    "ערך סידורי (1–22) של כל אות, ואז צמצום הסכום לספרה אחת.",
    "אין לשיטה הגדרה מסורתית אחידה; מוצגת כשיטה מתמטית.",
    "אות סופית כאות הרגילה.", letter_table=lambda p: ordinal({"finals": "regular"}),
    post=lambda s, nl, nw, p: digit_root(s), post_he=lambda p: "צמצום לספרה אחת"))

register(Method(
    "niqqud", "גימטריית ניקוד (טבלת החוקר)", "Niqqud gematria", "niqqud",
    "סכום ערכי התנועות לפי הטבלה: פתח 6, קמץ 16, צירי 20, סגול 30, שווא 20, חולם 10, חיריק 10, קובוץ 30, "
    "שורוק 10, חטף פתח 26, חטף קמץ 36, חטף סגול 50; אות ללא תנועה = 0.",
    "טבלה ייעודית שהגדיר החוקר — אינה מוצגת כשיטה מסורתית.",
    "האותיות עצמן אינן נספרות.", uses_niqqud=True))

register(Method(
    "letters_plus_niqqud", "גימטריה רגילה + גימטריית ניקוד", "Letters + niqqud", "niqqud",
    "לכל אות: ערך האות + ערך התנועה שלה; סכום הכול.",
    "שילוב של הגימטריה הרגילה עם טבלת הניקוד של החוקר.",
    FINALS_REGULAR, letter_table=based, uses_niqqud=True, params=[BASE_PARAM]))
