"""Advanced Search Builder: typed, reproducible multi-step searches.

A pipeline is a list of steps. Each step declares the type it consumes and
the type it produces:

==================  ==========  ==========  ======================================
op                  input       output      meaning
==================  ==========  ==========  ======================================
``transform``       text        text        letter transformation (א״ת ב״ש, …)
``custom_map``      text        text        user-defined letter map
``heads``           text        text        first letter of every word (ראשי תיבות)
``tails``           text        text        last letter of every word (סופי תיבות)
``gematria``        text        number      value in a gematria method
``add_niqqud``      text        number      niqqud gematria of the text (with the
                                            number it is added to, see below)
``arith``           number      number      + / × a constant (explicit arithmetic)
``search_text``     text        matches     word / sequence / acrostic / skip search
``search_niqqud``   text        matches     niqqud-pattern search
``search_value``    number      matches     gematria-value search in the corpus
==================  ==========  ==========  ======================================

The pipeline starts with the user's (pointed) text. A step whose input type
does not match the current value is rejected with an explanation — no
implicit conversion. ``gematria`` with ``"include_niqqud": true`` adds the
niqqud gematria of the same text; transformations keep each vowel on its
position, so the niqqud value is unchanged by them. Every step's output is
recorded in the trace, so the result can be reproduced.
"""

from __future__ import annotations

from .. import hebrew as H
from ..gematria import get as get_method
from ..niqqud import parse_text
from ..niqqud_gematria import NiqqudTable
from ..search import service as S
from ..transformations import get as get_transform

STEP_TYPES = {
    "transform": ("text", "text"),
    "custom_map": ("text", "text"),
    "heads": ("text", "text"),
    "tails": ("text", "text"),
    "gematria": ("text", "number"),
    "add_niqqud": ("text", "number"),
    "arith": ("number", "number"),
    "search_text": ("text", "matches"),
    "search_niqqud": ("text", "matches"),
    "search_value": ("number", "matches"),
}
TYPE_HE = {"text": "טקסט", "number": "מספר", "matches": "רשימת התאמות"}
OP_HE = {
    "transform": "חילוף אותיות", "custom_map": "מיפוי אותיות מותאם", "heads": "חילוץ ראשי תיבות",
    "tails": "חילוץ סופי תיבות", "gematria": "חישוב גימטריה", "add_niqqud": "גימטריית ניקוד",
    "arith": "פעולה חשבונית", "search_text": "חיפוש טקסט בתנ״ך", "search_niqqud": "חיפוש ניקוד בתנ״ך",
    "search_value": "חיפוש ערך גימטרי בתנ״ך",
}


def validate(steps: list[dict]) -> list[str]:
    """Type-check a pipeline. Returns a list of Hebrew error messages."""
    errors = []
    cur = "text"
    for i, st in enumerate(steps):
        op = st.get("op")
        if op not in STEP_TYPES:
            errors.append(f"שלב {i + 1}: פעולה לא מוכרת «{op}»")
            continue
        need, give = STEP_TYPES[op]
        if cur == "matches":
            errors.append(f"שלב {i + 1}: אין שלבים אחרי חיפוש בתנ״ך")
        elif need != cur:
            errors.append(f"שלב {i + 1} ({OP_HE[op]}) מצפה ל{TYPE_HE[need]}, אך השלב הקודם מפיק {TYPE_HE[cur]}. "
                          + ("כדי לעבור מטקסט למספר הוסף שלב ״חישוב גימטריה״." if need == "number" else
                             "לא ניתן להמיר מספר בחזרה לטקסט; סדר מחדש את השלבים."))
        cur = give
    return errors


def run(corpus, req: dict) -> dict:
    steps = req.get("steps") or []
    errors = validate(steps)
    if errors:
        return {"ok": False, "errors": errors}
    ntable = NiqqudTable.from_overrides(req.get("niqqud_values"))
    text = req.get("query", "")
    join = (req.get("layer") or {}).get("maqaf") == "join"
    value = None
    trace = [{"step": 0, "op": "input", "op_he": "קלט", "type": "text", "output": text}]
    result = None
    for i, st in enumerate(steps, start=1):
        op = st["op"]
        entry = {"step": i, "op": op, "op_he": OP_HE[op], "params": st}
        if op == "transform":
            t = get_transform(st["transformation"])
            text = t.apply(text, st.get("params"))
            entry.update(type="text", output=text, detail=t.name_he)
        elif op == "custom_map":
            m = {H.FINAL_TO_REGULAR.get(k, k): v for k, v in (st.get("map") or {}).items()}
            text = "".join(m.get(H.FINAL_TO_REGULAR.get(ch, ch), ch) if ch in H.LETTER_CODE else ch for ch in text)
            entry.update(type="text", output=text)
        elif op in ("heads", "tails"):
            words = parse_text(text, join)
            pick = [(w[0] if op == "heads" else w[-1]) for w in words if w]
            text = "".join(u.char + u.marks for u in pick)
            entry.update(type="text", output=text)
        elif op == "gematria":
            m = get_method(st.get("method", "standard"))
            calc = m.compute(parse_text(text, join), st.get("params"), ntable)
            value = calc["value"]
            steps_he = list(calc["steps"])
            if st.get("include_niqqud"):
                nq = get_method("niqqud").compute(parse_text(text, join), None, ntable)
                value += nq["value"]
                steps_he.append(f"+ גימטריית ניקוד {nq['value']} = {value}")
            entry.update(type="number", output=value, detail=m.name_he, calc=steps_he)
        elif op == "add_niqqud":
            nq = get_method("niqqud").compute(parse_text(text, join), None, ntable)
            value = nq["value"]
            entry.update(type="number", output=value, calc=nq["steps"])
        elif op == "arith":
            a = int(st.get("value", 0))
            value = value + a if st.get("operator", "+") == "+" else value * a
            entry.update(type="number", output=value, detail=f"{st.get('operator', '+')} {a}")
        elif op == "search_text":
            sub = {**req, **st, "query": H.letters_only(text)}
            if "search_mode" in st:
                result = S.search_by_mode(corpus, sub, H.letters_only(text))
            else:
                result = S.letter_search(corpus, sub)
            entry.update(type="matches", output=f"{result['total']} התאמות")
        elif op == "search_niqqud":
            result = S.niqqud_search(corpus, {**req, **st, "query": text})
            entry.update(type="matches", output=f"{result['total']} התאמות")
        elif op == "search_value":
            result = S.gematria_search(corpus, {**req, **st, "target": value})
            entry.update(type="matches", output=f"{result['total']} התאמות")
        trace.append(entry)
    return {"ok": True, "trace": trace, "final_type": trace[-1]["type"], "value": value, "text": text,
            "result": result, "steps": steps}
