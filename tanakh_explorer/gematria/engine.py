"""Gematria Engine.

Every method is a self-contained :class:`Method` registered in ``REGISTRY``;
adding a method does not touch the search engine. A method is defined by
three parts, applied in this order:

1. **letter values** — a value for each letter (or, for niqqud methods, for
   the vowels of each letter);
2. **weighting** — ``none``, ``achor`` (value × position) or ``boneh``
   (cumulative prefixes, i.e. value × number of prefixes containing the
   letter); positions restart in every word or run through the phrase;
3. **post-processing** of the total ``S`` with the number of letters ``nl``
   and words ``nw`` — e.g. ``S+1`` (הכולל), ``S²``, digit root.

The same definition drives the scalar calculator (with a step-by-step
explanation) and the vectorised corpus computation, and tests check that
the two agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .. import hebrew as H
from ..niqqud import LetterUnit, parse_text
from ..niqqud_gematria import NiqqudTable


@dataclass
class ParamSpec:
    name: str
    kind: str  # choice | int | bool | json
    default: object
    label_he: str
    choices: list[tuple[str, str]] | None = None
    min: int | None = None
    max: int | None = None

    def to_dict(self):
        d = {"name": self.name, "kind": self.kind, "default": self.default, "label_he": self.label_he}
        if self.choices:
            d["choices"] = [{"value": v, "label": label} for v, label in self.choices]
        if self.min is not None:
            d["min"] = self.min
        if self.max is not None:
            d["max"] = self.max
        return d


@dataclass
class Method:
    id: str
    name_he: str
    name_en: str
    category: str  # traditional | mathematical | niqqud | custom
    formula_he: str
    source_he: str
    finals_he: str
    letter_table: Callable[[dict], dict[str, int]] | None = None  # letter -> value
    uses_niqqud: bool = False
    weighting: Callable[[dict], str] = lambda p: "none"
    reset: Callable[[dict], str] = lambda p: "word"
    post: Callable[[object, object, object, dict], object] | None = None
    post_he: Callable[[dict], str] | None = None
    params: list[ParamSpec] = field(default_factory=list)
    big_values: Callable[[dict], bool] = lambda p: False

    # -- parameters -------------------------------------------------------------
    def resolve(self, params: dict | None) -> dict:
        p = {s.name: s.default for s in self.params}
        for k, v in (params or {}).items():
            if k in p:
                spec = next(s for s in self.params if s.name == k)
                if spec.kind == "int":
                    v = int(v)
                    if spec.min is not None and v < spec.min or spec.max is not None and v > spec.max:
                        raise ValueError(f"{k} out of range")
                elif spec.kind == "bool":
                    v = bool(v)
                elif spec.kind == "choice" and v not in [c[0] for c in spec.choices]:
                    raise ValueError(f"bad value for {k}: {v}")
                p[k] = v
        return p

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name_he": self.name_he, "name_en": self.name_en, "category": self.category,
            "formula_he": self.formula_he, "source_he": self.source_he, "finals_he": self.finals_he,
            "uses_niqqud": self.uses_niqqud, "params": [s.to_dict() for s in self.params],
        }

    # -- scalar path --------------------------------------------------------------
    def unit_values(self, units: list[LetterUnit], p: dict, ntable: NiqqudTable | None = None) -> list[int]:
        if self.uses_niqqud:
            nt = ntable or NiqqudTable()
            vals = [sum(nt.values[v] for v in u.vowels) for u in units]
            if self.letter_table:
                lt = self.letter_table(p)
                vals = [lt[u.char] + v for u, v in zip(units, vals)]
            return vals
        lt = self.letter_table(p)
        return [lt[u.char] for u in units]

    def compute(self, words: list[list[LetterUnit]] | str, params: dict | None = None,
                ntable: NiqqudTable | None = None) -> dict:
        """Value of a word or phrase, with every step of the calculation."""
        if isinstance(words, str):
            words = parse_text(words)
        p = self.resolve(params)
        weighting, reset = self.weighting(p), self.reset(p)
        steps: list[str] = []
        total = 0
        nl = sum(len(w) for w in words)
        nw = len(words)
        flat_pos = 0
        for w in words:
            vals = self.unit_values(w, p, ntable)
            parts = []
            for i, (u, v) in enumerate(zip(w, vals)):
                if reset == "word":
                    pos, n = i + 1, len(w)
                else:
                    pos, n = flat_pos + i + 1, nl
                if weighting == "achor":
                    wt = pos
                elif weighting == "boneh":
                    wt = n - pos + 1
                else:
                    wt = 1
                total += v * wt
                parts.append(f"{u.char}={v}" + (f"×{wt}" if wt != 1 else ""))
            flat_pos += len(w)
            steps.append(" + ".join(parts) if parts else "(אין אותיות)")
        steps.append(f"סכום = {total}")
        value = total
        if self.post:
            value = int(self.post(total, nl, nw, p))
            steps.append(f"{self.post_he(p)} → {value}")
        return {"method": self.id, "value": int(value), "base_sum": int(total), "letters": nl, "words": nw,
                "params": p, "steps": steps}

    # -- vectorised path ----------------------------------------------------------
    def letter_array(self, layer, p: dict, ntable: NiqqudTable | None = None) -> np.ndarray:
        dtype = object if self.big_values(p) else np.int64
        out = np.zeros(layer.n_letters, dtype=np.int64)
        if self.letter_table:
            lt = self.letter_table(p)
            lut = np.array([lt[ch] for ch in H.ALL_LETTERS], dtype=np.int64)
            out = out + lut[layer.l_code]
        if self.uses_niqqud:
            nt = ntable or NiqqudTable()
            out = out + nt.combo_lut()[layer.l_combo]
        return out.astype(dtype) if dtype is object else out

    def window_values(self, layer, n: int, p: dict, ntable: NiqqudTable | None = None,
                      starts: np.ndarray | None = None) -> np.ndarray:
        """Value of every run of ``n`` consecutive words starting at ``starts``
        (default: every word index for which the run fits in the layer)."""
        if starts is None:
            starts = np.arange(max(layer.n_words - n + 1, 0))
        return self.span_values(layer, starts, starts + n, p, ntable)

    def span_values(self, layer, starts: np.ndarray, ends: np.ndarray, p: dict,
                    ntable: NiqqudTable | None = None, letter_values: np.ndarray | None = None) -> np.ndarray:
        """Value of the word spans ``[starts[i], ends[i])`` (exclusive end)."""
        v = self.letter_array(layer, p, ntable) if letter_values is None else letter_values
        weighting, reset = self.weighting(p), self.reset(p)
        starts = np.asarray(starts, dtype=np.int64)
        ends = np.asarray(ends, dtype=np.int64)
        n = ends - starts
        lstart = layer.word_lstart
        lend_word = lstart + layer.word_len
        l0 = lstart[starts]
        l1 = lend_word[ends - 1]  # exclusive letter index
        nl = (l1 - l0)
        if weighting == "none" or reset == "word":
            if weighting == "achor":
                v = v * (layer.l_pos + 1)
            elif weighting == "boneh":
                v = v * (layer.word_len[layer.l_word] - layer.l_pos)
            cs = np.concatenate([[0], np.cumsum(v)])
            s = cs[l1] - cs[l0]
        else:
            g = np.arange(layer.n_letters, dtype=np.int64)
            cs = np.concatenate([[0], np.cumsum(v)])
            csg = np.concatenate([[0], np.cumsum(v * g)])
            sum_v = cs[l1] - cs[l0]
            sum_vg = csg[l1] - csg[l0]
            if weighting == "achor":  # position = g - l0 + 1
                s = sum_vg - (l0 - 1) * sum_v
            else:  # boneh: weight = l1 - g
                s = l1 * sum_v - sum_vg
        if self.post:
            s = self.post(s, nl, n, p)
        return s

    def word_values(self, layer, p: dict, ntable: NiqqudTable | None = None) -> np.ndarray:
        return self.window_values(layer, 1, p, ntable)


REGISTRY: dict[str, Method] = {}


def register(m: Method) -> Method:
    if m.id in REGISTRY:
        raise ValueError(f"duplicate gematria method id: {m.id}")
    REGISTRY[m.id] = m
    return m


def get(method_id: str) -> Method:
    try:
        return REGISTRY[method_id]
    except KeyError:
        raise ValueError(f"unknown gematria method: {method_id}") from None
