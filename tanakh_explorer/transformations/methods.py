"""Definitions of the letter transformations (חילופי אותיות ותמורות).

Mappings are written over alphabet indices 0..21 (א=0 … ת=21).
"""

from __future__ import annotations

from .. import hebrew as H
from ..gematria.engine import ParamSpec
from .engine import AB, Transformation, register

FINALS_PARAM = ParamSpec("finals", "choice", "normalize", "אותיות סופיות בקלט",
                         [("normalize", "כאות הרגילה"), ("keep", "נשארות ללא שינוי")])
FINALS_PARAM_OWN = ParamSpec("finals", "choice", "own", "אותיות סופיות בקלט",
                             [("own", "לפי המיפוי של השיטה (מאות 500–900)"), ("normalize", "כאות הרגילה"),
                              ("keep", "נשארות ללא שינוי")])
OUTPUT_PARAM = ParamSpec("output_finals", "choice", "word_end", "צורת אותיות בפלט",
                         [("word_end", "אות סופית בסוף מילה"), ("as_mapped", "כפי שמופה")])


def _pairs(pairs: list[tuple[int, int]]) -> dict[str, str]:
    m = {ch: ch for ch in AB}
    for a, b in pairs:
        m[AB[a]], m[AB[b]] = AB[b], AB[a]
    return m


def _reverse_block(lo: int, hi: int) -> list[tuple[int, int]]:
    return [(lo + i, hi - i) for i in range((hi - lo + 1) // 2)]


register(Transformation(
    "atbash", "א״ת ב״ש", "Atbash", "traditional",
    "כל אות מתחלפת באות המקבילה לה מסוף האלף־בית: א↔ת, ב↔ש, ג↔ר, ד↔ק …",
    "מתועד במקרא עצמו לפי חז״ל (״ששך״ = בבל, ירמיהו כה, כו; רש״י שם) ובברייתא דל״ב מידות.",
    lambda p: _pairs(_reverse_block(0, 21)), involution=lambda p: True,
    params=[FINALS_PARAM, OUTPUT_PARAM], examples=[("ששך", "בבל")]))

register(Transformation(
    "albam", "אלב״ם", "Albam", "traditional",
    "חלוקת האלף־בית לשני חצאים של 11 אותיות והחלפת אותיות באותו מיקום: א↔ל, ב↔מ, ג↔נ, ד↔ס …",
    "מתועד בברייתא דל״ב מידות ובספרות הקבלה (פרדס רימונים, שער הצירופים).",
    lambda p: _pairs([(i, i + 11) for i in range(11)]), involution=lambda p: True,
    params=[FINALS_PARAM, OUTPUT_PARAM]))

register(Transformation(
    "achbi", "אכ״ב י״ (Achbi)", "Achbi", "traditional",
    "היפוך פנימי בכל חצי של האלף־בית: א↔כ, ב↔י, ג↔ט, ד↔ח, ה↔ז; ל↔ת, מ↔ש, נ↔ר, ס↔ק, ע↔צ. "
    "ו ו־פ הן אמצע כל חצי ונשארות במקומן.",
    "מנוי בין צירופי האותיות בספרות הקבלה.",
    lambda p: _pairs(_reverse_block(0, 10) + _reverse_block(11, 21)), involution=lambda p: True,
    params=[FINALS_PARAM, OUTPUT_PARAM]))

register(Transformation(
    "split_alef_yod", "חלוקה א–י / כ–ת (״א״ח ב״ע״ — הגדרת המשתמש)", "Split alef–yod / kaf–tav", "user_defined",
    "חלוקה לשני חלקים שאינם שווים: א–י (10 אותיות) ו־כ–ת (12 אותיות), והיפוך כל חלק בנפרד: "
    "א↔י, ב↔ט, ג↔ח, ד↔ז, ה↔ו; כ↔ת, ל↔ש, מ↔ר, נ↔ק, ס↔צ, ע↔פ.",
    "השיטה מוגדרת כאן לפי בקשת המשתמש. לא נמצאה עבורה מקבילה מתועדת בשם זה; אין להציגה כשיטה מסורתית.",
    lambda p: _pairs(_reverse_block(0, 9) + _reverse_block(10, 21)), involution=lambda p: True,
    params=[FINALS_PARAM, OUTPUT_PARAM]))


def _atbach(p):
    pairs = [(0, 8), (1, 7), (2, 6), (3, 5),  # א↔ט ב↔ח ג↔ז ד↔ו (sum 10)
             (9, 17), (10, 16), (11, 15), (12, 14),  # י↔צ כ↔פ ל↔ע מ↔ס (sum 100)
             (18, 21), (19, 20)]  # ק↔ת ר↔ש (sum 500)
    if p.get("he_nun") == "pair":
        pairs.append((4, 13))  # ה↔נ
    return _pairs(pairs)


register(Transformation(
    "atbach", "אטב״ח", "Atbach", "traditional",
    "זיווג אותיות שסכומן 10 ביחידות (א↔ט, ב↔ח, ג↔ז, ד↔ו), 100 בעשרות (י↔צ, כ↔פ, ל↔ע, מ↔ס) "
    "ו־500 במאות (ק↔ת, ר↔ש). ה ו־נ שנותרו: לפי גרסה אחת מתחלפות זו בזו (ה״ן), לפי אחרת נשארות.",
    "בבלי סוכה נב ע״ב ורש״י שם (״באטב״ח״); קיימות גרסאות לגבי ה ו־נ.",
    _atbach, involution=lambda p: True,
    params=[ParamSpec("he_nun", "choice", "pair", "האותיות ה ו־נ",
                      [("pair", "מתחלפות זו בזו (ה↔נ)"), ("fixed", "נשארות במקומן")]),
            FINALS_PARAM, OUTPUT_PARAM]))


def _atbach_gadol(p):
    m = _atbach({"he_nun": p.get("he_nun", "pair")})
    # hundreds with final forms as 500–900: pairs summing to 1000
    for a, b in (("ק", "ץ"), ("ר", "ף"), ("ש", "ן"), ("ת", "ם")):
        m[a], m[b] = b, a
    m["ך"] = "ך"
    return m


register(Transformation(
    "atbach_gadol", "אטב״ח עם מנצפ״ך (סכום 1000 במאות)", "Atbach with final forms", "traditional",
    "כמו אטב״ח ביחידות ובעשרות, ובמאות האותיות הסופיות כמאות 500–900: ק↔ץ, ר↔ף, ש↔ן, ת↔ם; ך (500) נשארת.",
    "גרסה המופיעה בספרות הקבלה לצד הגרסה הבסיסית; מוצגת כגרסה נפרדת.",
    _atbach_gadol, finals_default="own", involution=lambda p: True,
    params=[ParamSpec("he_nun", "choice", "pair", "האותיות ה ו־נ",
                      [("pair", "מתחלפות זו בזו (ה↔נ)"), ("fixed", "נשארות במקומן")]),
            FINALS_PARAM_OWN, ParamSpec("output_finals", "choice", "as_mapped", "צורת אותיות בפלט",
                                        [("as_mapped", "כפי שמופה"), ("word_end", "אות סופית בסוף מילה")])]))


def _cycles(groups: list[list[str]], direction: str) -> dict[str, str]:
    m = {ch: ch for ch in H.ALL_LETTERS}
    for g in groups:
        k = len(g)
        for i, ch in enumerate(g):
            m[ch] = g[(i + 1) % k] if direction == "forward" else g[(i - 1) % k]
    return m


DIRECTION = ParamSpec("direction", "choice", "forward", "כיוון המחזור",
                      [("forward", "קדימה (א→ח→ס→א)"), ("backward", "אחורה (א→ס→ח→א)")])


def _achas(p):
    groups = [[AB[k], AB[k + 7], AB[k + 14]] for k in range(7)]
    return _cycles(groups, p["direction"])


register(Transformation(
    "achas_betah", "אח״ס בט״ע", "Achas Betah", "traditional",
    "שבע קבוצות של שלוש אותיות במרווח 7: אח״ס, בט״ע, גי״פ, דכ״צ, הל״ק, ומ״ר, זנ״ש. "
    "כל אות עוברת לאות הבאה בקבוצתה (מחזורית). ת אינה בשום קבוצה ונשארת במקומה.",
    "מנוי בספרות הקבלה בין צירופי האותיות (פרדס רימונים, שער הצירופים).",
    _achas, params=[DIRECTION, FINALS_PARAM, OUTPUT_PARAM]))


def _ayak(p):
    if p["finals_mode"] == "with_finals":
        groups = [[AB[k], AB[k + 9], AB[k + 18]] for k in range(4)]
        groups += [[AB[k], AB[k + 9], f] for k, f in zip(range(4, 9), "ךםןףץ")]
    else:
        groups = [[AB[k], AB[k + 9], AB[k + 18]] for k in range(4)]
        groups += [[AB[k], AB[k + 9]] for k in range(4, 9)]
    m = _cycles(groups, p["direction"])
    if p["finals_mode"] != "with_finals":
        for f, r in H.FINAL_TO_REGULAR.items():
            m[f] = m[r]
    return m


register(Transformation(
    "ayak_bachar", "אי״ק בכ״ר", "Ayak Bachar", "traditional",
    "קבוצות של אותיות בעלות אותו ערך ביחידות, עשרות ומאות: אי״ק, בכ״ר, גל״ש, דמ״ת, הנ״ך, וס״ם, זע״ן, חפ״ף, טצ״ץ "
    "(הסופיות כמאות 500–900). כל אות עוברת לאות הבאה בקבוצתה.",
    "מנוי בספרות הקבלה (פרדס רימונים); זהו גם יסוד ״חשבון תשע״ / מספר קטן.",
    _ayak, finals_default="own",
    params=[DIRECTION,
            ParamSpec("finals_mode", "choice", "with_finals", "קבוצות",
                      [("with_finals", "עם מנצפ״ך כמאות (9 שלשות)"), ("no_finals", "בלי סופיות (5 זוגות אחרונים)")]),
            FINALS_PARAM_OWN, ParamSpec("output_finals", "choice", "as_mapped", "צורת אותיות בפלט",
                                        [("as_mapped", "כפי שמופה"), ("word_end", "אות סופית בסוף מילה")])]))


def _shift(p):
    n = int(p["n"]) % 22 if p["cyclic"] else int(p["n"])
    step = n if p["direction"] == "forward" else -n
    m = {}
    for i, ch in enumerate(AB):
        j = i + step
        if p["cyclic"]:
            m[ch] = AB[j % 22]
        elif 0 <= j < 22:
            m[ch] = AB[j]
        else:
            m[ch] = ch if p["edge"] == "stay" else AB[min(max(j, 0), 21)]
    return m


SHIFT_PARAMS = [
    ParamSpec("n", "int", 1, "מספר מקומות", min=0, max=21),
    ParamSpec("direction", "choice", "forward", "כיוון", [("forward", "קדימה (א→ב)"), ("backward", "אחורה (ב→א)")]),
    ParamSpec("cyclic", "bool", True, "מחזורי (ת→א / א→ת)"),
    ParamSpec("edge", "choice", "stay", "בהזזה לא מחזורית, אות שעוברת את הקצה",
              [("stay", "נשארת במקומה"), ("clamp", "נעצרת בקצה (א או ת)")]),
    ParamSpec("finals", "choice", "keep", "אותיות סופיות",
              [("keep", "נשארות בדיוק כפי שהן"), ("normalize", "מנורמלות לאות רגילה לפני ההזזה")]),
    OUTPUT_PARAM,
]

register(Transformation(
    "shift", "הזזת אותיות (כל מספר מקומות)", "Letter shift", "traditional",
    "כל אות עוברת n מקומות קדימה או אחורה באלף־בית. הזזה קדימה באחת היא אבג״ד (א→ב, ב→ג …).",
    "״אבג״ד״ מנוי בין צירופי האותיות; ההזזה הכללית היא הכללה מתמטית שלו.",
    _shift, finals_default="keep", params=SHIFT_PARAMS))

register(Transformation(
    "avgad", "אבג״ד — הזזה קדימה באחת", "Avgad", "traditional",
    "כל אות מוחלפת באות שאחריה: א→ב, ב→ג … ; ברירת מחדל: ת→ת (לא מחזורי) והסופיות ללא שינוי.",
    "מנוי בספרות הקבלה בין צירופי האותיות.",
    lambda p: _shift({**p, "n": 1, "direction": "forward"}), finals_default="keep",
    params=[ParamSpec("cyclic", "bool", False, "מחזורי (ת→א)"),
            ParamSpec("edge", "choice", "stay", "ת", [("stay", "נשארת ת")]),
            SHIFT_PARAMS[4], OUTPUT_PARAM]))

register(Transformation(
    "shift_back", "הזזה אחורה באחת", "Shift back", "traditional",
    "כל אות מוחלפת באות שלפניה: ב→א, ג→ב … ; ברירת מחדל: א נשארת א והסופיות ללא שינוי. "
    "מצב מחזורי נפרד: א→ת.",
    "ההפך של אבג״ד.",
    lambda p: _shift({**p, "n": 1, "direction": "backward"}), finals_default="keep",
    params=[ParamSpec("cyclic", "bool", False, "מחזורי (א→ת)"),
            ParamSpec("edge", "choice", "stay", "א", [("stay", "נשארת א")]),
            SHIFT_PARAMS[4], OUTPUT_PARAM]))
