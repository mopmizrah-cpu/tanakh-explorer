"""Book metadata: the 39 books in the order of printed Tanakh editions, their
grouping into the traditional 24 books, the three sections, and the expected
number of chapters (used by validation)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Book:
    osis: str
    he: str
    en: str
    group: str  # one of the 24 traditional books (Hebrew name)
    section: str  # torah / neviim / ketuvim
    chapters: int  # expected chapter count (Hebrew versification)


BOOKS: list[Book] = [
    Book("Gen", "בראשית", "Genesis", "בראשית", "torah", 50),
    Book("Exod", "שמות", "Exodus", "שמות", "torah", 40),
    Book("Lev", "ויקרא", "Leviticus", "ויקרא", "torah", 27),
    Book("Num", "במדבר", "Numbers", "במדבר", "torah", 36),
    Book("Deut", "דברים", "Deuteronomy", "דברים", "torah", 34),
    Book("Josh", "יהושע", "Joshua", "יהושע", "neviim", 24),
    Book("Judg", "שופטים", "Judges", "שופטים", "neviim", 21),
    Book("1Sam", "שמואל א", "1 Samuel", "שמואל", "neviim", 31),
    Book("2Sam", "שמואל ב", "2 Samuel", "שמואל", "neviim", 24),
    Book("1Kgs", "מלכים א", "1 Kings", "מלכים", "neviim", 22),
    Book("2Kgs", "מלכים ב", "2 Kings", "מלכים", "neviim", 25),
    Book("Isa", "ישעיהו", "Isaiah", "ישעיהו", "neviim", 66),
    Book("Jer", "ירמיהו", "Jeremiah", "ירמיהו", "neviim", 52),
    Book("Ezek", "יחזקאל", "Ezekiel", "יחזקאל", "neviim", 48),
    Book("Hos", "הושע", "Hosea", "תרי עשר", "neviim", 14),
    Book("Joel", "יואל", "Joel", "תרי עשר", "neviim", 4),
    Book("Amos", "עמוס", "Amos", "תרי עשר", "neviim", 9),
    Book("Obad", "עובדיה", "Obadiah", "תרי עשר", "neviim", 1),
    Book("Jonah", "יונה", "Jonah", "תרי עשר", "neviim", 4),
    Book("Mic", "מיכה", "Micah", "תרי עשר", "neviim", 7),
    Book("Nah", "נחום", "Nahum", "תרי עשר", "neviim", 3),
    Book("Hab", "חבקוק", "Habakkuk", "תרי עשר", "neviim", 3),
    Book("Zeph", "צפניה", "Zephaniah", "תרי עשר", "neviim", 3),
    Book("Hag", "חגי", "Haggai", "תרי עשר", "neviim", 2),
    Book("Zech", "זכריה", "Zechariah", "תרי עשר", "neviim", 14),
    Book("Mal", "מלאכי", "Malachi", "תרי עשר", "neviim", 3),
    Book("Ps", "תהלים", "Psalms", "תהלים", "ketuvim", 150),
    Book("Prov", "משלי", "Proverbs", "משלי", "ketuvim", 31),
    Book("Job", "איוב", "Job", "איוב", "ketuvim", 42),
    Book("Song", "שיר השירים", "Song of Songs", "שיר השירים", "ketuvim", 8),
    Book("Ruth", "רות", "Ruth", "רות", "ketuvim", 4),
    Book("Lam", "איכה", "Lamentations", "איכה", "ketuvim", 5),
    Book("Eccl", "קהלת", "Ecclesiastes", "קהלת", "ketuvim", 12),
    Book("Esth", "אסתר", "Esther", "אסתר", "ketuvim", 10),
    Book("Dan", "דניאל", "Daniel", "דניאל", "ketuvim", 12),
    Book("Ezra", "עזרא", "Ezra", "עזרא-נחמיה", "ketuvim", 10),
    Book("Neh", "נחמיה", "Nehemiah", "עזרא-נחמיה", "ketuvim", 13),
    Book("1Chr", "דברי הימים א", "1 Chronicles", "דברי הימים", "ketuvim", 29),
    Book("2Chr", "דברי הימים ב", "2 Chronicles", "דברי הימים", "ketuvim", 36),
]

BOOK_BY_OSIS = {b.osis: b for b in BOOKS}
BOOK_INDEX = {b.osis: i for i, b in enumerate(BOOKS)}
GROUPS_24 = list(dict.fromkeys(b.group for b in BOOKS))
SECTION_HE = {"torah": "תורה", "neviim": "נביאים", "ketuvim": "כתובים"}

# MAM-simple book-group file names, in the same order as GROUPS_24.
MAM_SIMPLE_FILES = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "1Sam-2Sam", "1Kgs-2Kgs",
    "Isa", "Jer", "Ezek", "Hos-Mal", "Ps", "Prov", "Job", "Song", "Ruth", "Lam",
    "Eccl", "Esth", "Dan", "Ezra-Neh", "1Chr-2Chr",
]
