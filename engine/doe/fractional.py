"""Lane D: fractional factorial 2^(k-p) designs (Meeting 11, Montgomery Ch. 8)."""
from __future__ import annotations

import itertools
import re

import numpy as np
import pandas as pd

from .two_level import letters, run_label, standard_order

# Montgomery Appendix Table XII (minimum aberration / max resolution), letters skip I.
STANDARD = {
    (3, 1): ["C=AB"], (4, 1): ["D=ABC"], (5, 1): ["E=ABCD"], (5, 2): ["D=AB", "E=AC"],
    (6, 1): ["F=ABCDE"], (6, 2): ["E=ABC", "F=BCD"], (6, 3): ["D=AB", "E=AC", "F=BC"],
    (7, 1): ["G=ABCDEF"], (7, 2): ["F=ABCD", "G=ABDE"], (7, 3): ["E=ABC", "F=BCD", "G=ACD"],
    (7, 4): ["D=AB", "E=AC", "F=BC", "G=ABC"],
    (8, 2): ["G=ABCD", "H=ABEF"], (8, 3): ["F=ABC", "G=ABD", "H=BCDE"], (8, 4): ["E=BCD", "F=ACD", "G=ABC", "H=ABD"],
    (9, 2): ["H=ACDFG", "J=BCEFG"], (9, 3): ["G=ABCD", "H=ACEF", "J=CDEF"],
    (9, 4): ["F=BCDE", "G=ACDE", "H=ABDE", "J=ABCE"], (9, 5): ["E=ABC", "F=BCD", "G=ACD", "H=ABD", "J=ABCD"],
    (10, 3): ["H=ABCG", "J=ACDE", "K=ACDF"], (10, 4): ["G=BCDF", "H=ACDF", "J=ABDE", "K=ABCE"],
    (10, 5): ["F=ABCD", "G=ABCE", "H=ABDE", "J=ACDE", "K=BCDE"],
    (10, 6): ["E=ABC", "F=BCD", "G=ACD", "H=ABD", "J=ABCD", "K=AB"],
    (11, 4): ["H=ABCG", "J=BCDE", "K=ACDF", "L=ABCDEFG"], (11, 5): ["G=CDE", "H=ABCD", "J=ABF", "K=BDEF", "L=ADEF"],
    (11, 6): ["F=ABC", "G=BCD", "H=CDE", "J=ACD", "K=ADE", "L=BDE"],
    (11, 7): ["E=ABC", "F=BCD", "G=ACD", "H=ABD", "J=ABCD", "K=AB", "L=AC"],
}

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI"}


def _norm(word: str, order: str) -> str:
    return "".join(sorted(word, key=order.index))


def multiply(w1: str, w2: str, order: str) -> str:
    """Product of two effect words (squares cancel): AB * BC = AC."""
    s = set(w1) ^ set(w2)
    return _norm("".join(s), order)


def parse_generator(g: str) -> tuple[str, int, str]:
    """'E = -ABCD' -> ('E', -1, 'ABCD')."""
    g = g.replace(" ", "").replace("−", "-").upper()
    m = re.fullmatch(r"([A-Z])=([+-]?)([A-Z]+)", g)
    if not m:
        raise ValueError(f"Cannot read generator '{g}'. Use the form D=ABC or E=-ABCD.")
    return m.group(1), -1 if m.group(2) == "-" else 1, m.group(3)


def parse_defining(rel: str) -> list[tuple[int, str]]:
    """'I = -ABCDE' or 'I=ABCD=BCEF' -> [(sign, word), ...] (generating words only)."""
    rel = rel.replace(" ", "").replace("−", "-").upper()
    parts = rel.split("=")
    if parts[0] != "I":
        raise ValueError("A defining relation starts with I, e.g. I = ABCD.")
    out = []
    for p in parts[1:]:
        s = -1 if p.startswith("-") else 1
        out.append((s, p.lstrip("+-")))
    return out


def defining_relation(words: list[tuple[int, str]], order: str) -> list[tuple[int, str]]:
    """All 2^p - 1 words of the defining relation, with signs."""
    full = []
    for r in range(1, len(words) + 1):
        for combo in itertools.combinations(words, r):
            sign, w = 1, ""
            for s, word in combo:
                sign *= s
                w = multiply(w, word, order)
            full.append((sign, w))
    return sorted(full, key=lambda x: (len(x[1]), x[1]))


def resolution(rel: list[tuple[int, str]]) -> int:
    return min(len(w) for _, w in rel)


def alias_of(effect: str, rel: list[tuple[int, str]], order: str) -> list[tuple[int, str]]:
    effect = _norm(effect.upper(), order)
    out = [(s, multiply(effect, w, order)) for s, w in rel]
    return sorted(out, key=lambda x: (len(x[1]), order.index(x[1][0]) if x[1] else 0, x[1]))


def fmt_signed(s: int, w: str) -> str:
    return f"{'−' if s < 0 else ''}{w or 'I'}"


def design(k: int, p: int, generators: list[str] | None = None, names=None, seed: int = 640,
           randomize: bool = True) -> dict:
    L = letters(k)
    order = "".join(L)
    gens = generators or STANDARD.get((k, p))
    if not gens:
        raise ValueError(f"No standard generators stored for 2^({k}-{p}); enter them yourself (e.g. D=ABC).")
    if len(gens) != p:
        raise ValueError(f"A 2^({k}-{p}) design needs {p} generator(s).")
    parsed = [parse_generator(g) for g in gens]
    base = [c for c in L if c not in [g[0] for g in parsed]]
    X = standard_order(len(base))
    df = pd.DataFrame(X, columns=base)
    for new, sign, word in parsed:
        v = np.ones(len(df), int)
        for ch in word:
            v = v * df[ch].values
        df[new] = sign * v
    df = df[L]
    df.insert(0, "Run label", [run_label(r, L) for r in df[L].values])
    df.insert(0, "Std order", np.arange(1, len(df) + 1))
    rng = np.random.default_rng(seed)
    df["Run order"] = rng.permutation(len(df)) + 1 if randomize else np.arange(1, len(df) + 1)
    words = [(s, _norm(new + w, order)) for new, s, w in parsed]
    rel = defining_relation(words, order)
    res = resolution(rel)
    return {"runs": df.to_dict(orient="records"), "n_runs": len(df), "generators": gens,
            "defining_relation": "I = " + " = ".join(fmt_signed(s, w) for s, w in rel),
            "words": rel, "resolution": res, "resolution_roman": ROMAN.get(res, str(res)),
            "aliases": alias_table(k, rel), "factor_letters": L, "names": names or L, "seed": seed}


def alias_table(k: int, rel, max_order: int = 3) -> list[dict]:
    L = letters(k)
    order = "".join(L)
    seen, out = set(), []
    for r in range(1, max_order + 1):
        for c in itertools.combinations(L, r):
            e = "".join(c)
            if e in seen:
                continue
            chain = alias_of(e, rel, order)
            seen.add(e)
            for _, w in chain:
                seen.add(w)
            out.append({"effect": e, "aliases": [fmt_signed(s, w) for s, w in chain],
                        "chain": f"[{e}] → {e} " + " ".join(f"{'−' if s < 0 else '+'} {w}" for s, w in chain)})
    return out


def analyze(k: int, rel_or_gens, data, response: str = "y") -> dict:
    """Effect estimates [X] for each alias chain (contrast / (N/2))."""
    L = letters(k)
    order = "".join(L)
    if isinstance(rel_or_gens, str):
        words = parse_defining(rel_or_gens)
    else:
        words = [(s, _norm(n + w, order)) for n, s, w in (parse_generator(g) for g in rel_or_gens)]
    rel = defining_relation(words, order)
    df = pd.DataFrame(data).copy()
    df[response] = pd.to_numeric(df[response])
    N = len(df)
    y = df[response].values.astype(float)
    rows, seen = [], set()
    for r in range(1, k + 1):
        for c in itertools.combinations(L, r):
            e = "".join(c)
            if e in seen:
                continue
            chain = alias_of(e, rel, order)
            seen.add(e)
            for _, w in chain:
                seen.add(w)
            v = np.ones(N)
            for ch in e:
                v = v * df[ch].values
            est = float((v * y).sum() / (N / 2))
            rows.append({"effect": e, "estimate": est,
                         "chain": f"[{e}] → {e} " + " ".join(f"{'−' if s < 0 else '+'} {w}" for s, w in chain),
                         "aliases": [fmt_signed(s, w) for s, w in chain]})
            if len(seen) >= 2 ** k - 1:
                break
    rows = [r for r in rows][: N - 1]
    return {"estimates": rows, "defining_relation": "I = " + " = ".join(fmt_signed(s, w) for s, w in rel),
            "resolution": resolution(rel)}


def runs_from_labels(k: int, labelled: dict, response: str = "y") -> list[dict]:
    L = letters(k)
    out = []
    for lab, v in labelled.items():
        row = {c: (1 if lab != "(1)" and c.lower() in lab else -1) for c in L}
        row[response] = v
        row["Run label"] = lab
        out.append(row)
    return out


def foldover(k: int, generators: list[str], full: bool = False) -> list[str]:
    """Other half (switch generator signs). full=True -> reverse all signs (same generators, flipped runs)."""
    out = []
    for g in generators:
        n, s, w = parse_generator(g)
        out.append(f"{n}={'' if s < 0 else '-'}{w}")
    return out


def n_runs(k: int, p: int = 0) -> int:
    return 2 ** (k - p)


def missing_level(rel: str, known: dict, target: str) -> int:
    """Level of `target` in a run, given the defining relation and the other factor levels.

    rel: 'I = -ABCDE'; known: {'A': 1, 'B': -1, 'C': 1, 'D': 1}; target 'E' -> +1
    """
    words = parse_defining(rel)
    s, w = words[0]
    if target not in w:
        raise ValueError(f"{target} is not in the word {w}.")
    prod = s
    for ch in w:
        if ch == target:
            continue
        prod *= known[ch]
    return int(prod)  # since I = s*W  ->  target = s * product(others)
