"""User-defined gematria methods (שיטות מותאמות אישית).

A custom method is a letter-value table for the 22 letters, optionally with
separate values for the five final forms. It is registered under the id
``custom:<slug>`` in the category ``custom`` and behaves like any built-in
method in every search.
"""

from __future__ import annotations

import re

from .. import hebrew as H
from .engine import REGISTRY, Method, register


def _table(values: dict[str, int]) -> dict[str, int]:
    out = {}
    for ch in H.ALEPHBET:
        if ch not in values:
            raise ValueError(f"missing value for {ch}")
        out[ch] = int(values[ch])
    for f, r in H.FINAL_TO_REGULAR.items():
        out[f] = int(values.get(f, out[r]))
    return out


def register_custom(slug: str, name_he: str, values: dict[str, int], description: str = "") -> Method:
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,40}", slug):
        raise ValueError("slug must be 1–40 latin letters, digits, _ or -")
    table = _table(values)
    mid = f"custom:{slug}"
    REGISTRY.pop(mid, None)
    return register(Method(
        mid, name_he, slug, "custom",
        description or "טבלת ערכים שהגדיר המשתמש: " + ", ".join(f"{k}={v}" for k, v in table.items()),
        "שיטה מותאמת אישית — אינה שיטה מסורתית.",
        "לפי הטבלה שהוגדרה.", letter_table=lambda p, t=table: t))


def remove_custom(slug: str) -> None:
    REGISTRY.pop(f"custom:{slug}", None)
