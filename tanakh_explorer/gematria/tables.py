"""Letter-value tables used by the gematria methods."""

from __future__ import annotations

from .. import hebrew as H

STANDARD = {  # מספר הכרחי; final forms take the value of the regular letter
    "א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9,
    "י": 10, "כ": 20, "ל": 30, "מ": 40, "נ": 50, "ס": 60, "ע": 70, "פ": 80, "צ": 90,
    "ק": 100, "ר": 200, "ש": 300, "ת": 400,
}
for _f, _r in H.FINAL_TO_REGULAR.items():
    STANDARD[_f] = STANDARD[_r]

GADOL_FINALS = {"ך": 500, "ם": 600, "ן": 700, "ף": 800, "ץ": 900}  # מנצפ״ך רבתי

# --- letter names (מילוי) -------------------------------------------------------
# Each letter lists its documented spellings; the first is the default of the
# "common" preset. Final forms are filled like their regular letters.
LETTER_NAMES: dict[str, list[str]] = {
    "א": ["אלף"],
    "ב": ["בית"],
    "ג": ["גימל", "גמל"],
    "ד": ["דלת", "דלית"],
    "ה": ["הא", "הה", "הי"],
    "ו": ["וו", "ואו", "ויו"],
    "ז": ["זין", "זיין"],
    "ח": ["חית", "חת"],
    "ט": ["טית", "טת"],
    "י": ["יוד", "יד"],
    "כ": ["כף"],
    "ל": ["למד"],
    "מ": ["מם"],
    "נ": ["נון"],
    "ס": ["סמך"],
    "ע": ["עין"],
    "פ": ["פא", "פה", "פי"],
    "צ": ["צדי", "צדיק"],
    "ק": ["קוף"],
    "ר": ["ריש"],
    "ש": ["שין"],
    "ת": ["תו", "תיו", "תאו"],
}

# Presets. The four Kabbalistic fillings differ in ה and ו; they are the
# fillings behind the names ע״ב (72), ס״ג (63), מ״ה (45) and ב״ן (52) of יהוה.
MILUI_PRESETS: dict[str, dict] = {
    "common": {"name_he": "מילוי רגיל", "override": {}},
    "yudin": {"name_he": "מילוי דיודין (ע״ב): ה=הי, ו=ויו", "override": {"ה": "הי", "ו": "ויו"}},
    "sag": {"name_he": "מילוי ס״ג: ה=הי, ו=ואו", "override": {"ה": "הי", "ו": "ואו"}},
    "alfin": {"name_he": "מילוי דאלפין (מ״ה): ה=הא, ו=ואו", "override": {"ה": "הא", "ו": "ואו"}},
    "hehin": {"name_he": "מילוי דההין (ב״ן): ה=הה, ו=וו", "override": {"ה": "הה", "ו": "וו"}},
}


def letter_name_table(preset: str = "common", custom: dict[str, str] | None = None) -> dict[str, str]:
    if preset not in MILUI_PRESETS:
        raise ValueError(f"unknown milui preset: {preset}")
    names = {k: v[0] for k, v in LETTER_NAMES.items()}
    names.update(MILUI_PRESETS[preset]["override"])
    for k, v in (custom or {}).items():
        k = H.FINAL_TO_REGULAR.get(k, k)
        if k not in names or not v or any(ch not in H.LETTER_CODE for ch in v):
            raise ValueError(f"bad custom filling {k!r}: {v!r}")
        names[k] = v
    for f, r in H.FINAL_TO_REGULAR.items():
        names[f] = names[r]
    return names


# --- number names (מספר מספרי) ---------------------------------------------------
# The spelled-out names of the letter values. Defective spelling follows the
# usual biblical spelling (שלשה, שמנה); plene adds the vav (שלושה, שמונה).
NUMBER_NAMES = {
    "masc": {
        1: "אחד", 2: "שנים", 3: "שלשה", 4: "ארבעה", 5: "חמשה", 6: "ששה", 7: "שבעה", 8: "שמנה", 9: "תשעה",
        10: "עשרה",
    },
    "fem": {
        1: "אחת", 2: "שתים", 3: "שלש", 4: "ארבע", 5: "חמש", 6: "שש", 7: "שבע", 8: "שמנה", 9: "תשע",
        10: "עשר",
    },
    "common": {
        20: "עשרים", 30: "שלשים", 40: "ארבעים", 50: "חמשים", 60: "ששים", 70: "שבעים", 80: "שמנים", 90: "תשעים",
        100: "מאה", 200: "מאתים", 300: "שלש מאות", 400: "ארבע מאות",
        500: "חמש מאות", 600: "שש מאות", 700: "שבע מאות", 800: "שמנה מאות", 900: "תשע מאות",
    },
}
_PLENE = {"שלשה": "שלושה", "שמנה": "שמונה", "שלש": "שלוש", "שלשים": "שלושים", "שמנים": "שמונים",
          "שלש מאות": "שלוש מאות", "שמנה מאות": "שמונה מאות"}


def number_name(value: int, gender: str = "masc", spelling: str = "defective") -> str:
    table = {**NUMBER_NAMES["common"], **NUMBER_NAMES[gender]}
    name = table[value]
    if spelling == "plene":
        name = _PLENE.get(name, name)
    return name
