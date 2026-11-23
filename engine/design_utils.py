"""Stage 1 utilities: counterbalancing (full permutations / Latin squares) and randomization."""
from __future__ import annotations

import itertools

import numpy as np


def williams(n: int) -> list[list[int]]:
    """Balanced Latin square (Williams design). Even n: n rows; odd n: 2n rows (two squares)."""
    first = []
    lo, hi = 0, n - 1
    for i in range(n):
        if i % 2 == 0:
            first.append(lo)
            lo += 1
        else:
            first.append(hi)
            hi -= 1
    rows = [[(x + r) % n for x in first] for r in range(n)]
    if n % 2 == 1:
        rows += [list(reversed(r)) for r in rows]
    return rows


def check_latin(rows: list[list[int]], n: int) -> dict:
    sq = rows[:n]
    rows_ok = all(sorted(r) == list(range(n)) for r in sq)
    cols_ok = all(sorted(r[c] for r in sq) == list(range(n)) for c in range(n))
    pairs = {}
    for r in rows:
        for a, b in zip(r, r[1:]):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1
    balanced = len(set(pairs.values())) == 1 and len(pairs) == n * (n - 1)
    return {"each_once_per_row": rows_ok, "each_once_per_column": cols_ok, "carryover_balanced": balanced}


def counterbalance(conditions: list[str], method: str = "latin", participants: int | None = None) -> dict:
    n = len(conditions)
    if method == "full":
        orders = [list(p) for p in itertools.permutations(range(n))]
    else:
        orders = williams(n)
    named = [[conditions[i] for i in o] for o in orders]
    out = {"method": "Full permutations (n!)" if method == "full" else "Balanced Latin square (Williams)",
           "orders": named, "n_orders": len(named), "check": check_latin(orders, n) if method != "full" else None}
    if participants:
        out["assignment"] = [{"participant": p + 1, "order_no": p % len(named) + 1, "order": named[p % len(named)]}
                             for p in range(participants)]
        if participants % len(named):
            out["note"] = (f"{participants} participants is not a multiple of {len(named)} orders, so the "
                           "counterbalancing is incomplete.")
    return out


def randomize(participants: int, groups: list[str], seed: int = 640, blocks: list | None = None) -> dict:
    """Balanced random assignment (optionally within blocks / strata), seeded."""
    rng = np.random.default_rng(seed)
    rows = []
    if blocks:
        by = {}
        for i, b in enumerate(blocks):
            by.setdefault(b, []).append(i)
        assign = [None] * participants
        for b, idx in by.items():
            labs = [groups[i % len(groups)] for i in range(len(idx))]
            rng.shuffle(labs)
            for i, l in zip(idx, labs):
                assign[i] = l
    else:
        assign = [groups[i % len(groups)] for i in range(participants)]
        rng.shuffle(assign)
    run = rng.permutation(participants) + 1
    for i in range(participants):
        rows.append({"participant": i + 1, "condition": assign[i], "run_order": int(run[i]),
                     **({"block": blocks[i]} if blocks else {})})
    return {"seed": seed, "rows": rows}
