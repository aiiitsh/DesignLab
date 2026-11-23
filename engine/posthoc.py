"""Post hoc comparisons and planned contrasts using the pooled error term (as JASP)."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from .common import fmt_p

METHODS = ["tukey", "bonferroni", "holm", "sidak", "scheffe", "lsd"]


def pooled_pairwise(means: dict, ns: dict, mse: float, dfe: float, method: str = "tukey") -> list[list]:
    levels = list(means)
    k = len(levels)
    rows, raw = [], []
    for i, j in itertools.combinations(levels, 2):
        diff = means[i] - means[j]
        se = math.sqrt(mse * (1 / ns[i] + 1 / ns[j]))
        t = diff / se
        p_unc = 2 * stats.t.sf(abs(t), dfe)
        raw.append((i, j, diff, se, t, p_unc))
    ps = [r[5] for r in raw]
    if method == "tukey":
        adj = [float(stats.studentized_range.sf(abs(r[4]) * math.sqrt(2), k, dfe)) for r in raw]
    elif method == "scheffe":
        adj = [float(stats.f.sf(r[4] ** 2 / (k - 1), k - 1, dfe)) for r in raw]
    elif method == "lsd":
        adj = ps
    else:
        adj = list(multipletests(ps, method={"bonferroni": "bonferroni", "holm": "holm", "sidak": "sidak"}[method])[1])
    for (i, j, diff, se, t, p_unc), p in zip(raw, adj):
        rows.append([f"{i} − {j}", diff, se, t, dfe, fmt_p(p), p])
    return rows


def games_howell(groups: dict) -> list[list]:
    levels = list(groups)
    k = len(levels)
    rows = []
    for i, j in itertools.combinations(levels, 2):
        a, b = np.asarray(groups[i], float), np.asarray(groups[j], float)
        va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
        diff = a.mean() - b.mean()
        se = math.sqrt(va + vb)
        t = diff / se
        df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
        p = float(stats.studentized_range.sf(abs(t) * math.sqrt(2), k, df))
        rows.append([f"{i} − {j}", diff, se, t, df, fmt_p(p), p])
    return rows


def poly_coefs(k: int, values=None) -> dict:
    """Orthogonal polynomial contrasts (linear, quadratic, cubic, ...) for k levels."""
    x = np.asarray(values if values is not None else np.arange(1, k + 1), float)
    X = np.vander(x - x.mean(), k, increasing=True)
    Q, _ = np.linalg.qr(X)
    names = ["linear", "quadratic", "cubic", "quartic", "quintic"]
    out = {}
    for d in range(1, min(k, 6)):
        c = Q[:, d]
        if c[-1] < 0:
            c = -c
        out[names[d - 1] if d - 1 < len(names) else f"order {d}"] = c
    return out


def contrast_rows(means: dict, ns: dict, mse: float, dfe: float, kind: str = "polynomial",
                  custom=None, values=None) -> list[list]:
    levels = list(means)
    k = len(levels)
    m = np.array([means[l] for l in levels])
    n = np.array([ns[l] for l in levels], float)
    sets = {}
    if kind == "polynomial":
        sets = poly_coefs(k, values)
    elif kind == "treatment":
        for i in range(1, k):
            c = np.zeros(k)
            c[i], c[0] = 1, -1
            sets[f"{levels[i]} − {levels[0]}"] = c
    elif kind == "deviation":
        for i in range(1, k):
            c = -np.ones(k) / k
            c[i] += 1
            sets[f"{levels[i]} − grand mean"] = c
    elif kind == "custom" and custom:
        for idx, w in enumerate(custom):
            sets[f"contrast {idx + 1}"] = np.asarray(w, float)
    rows = []
    for name, c in sets.items():
        est = float(c @ m)
        se = math.sqrt(mse * float((c ** 2 / n).sum()))
        t = est / se
        p = 2 * stats.t.sf(abs(t), dfe)
        rows.append([name, est, se, dfe, t, fmt_p(p), p])
    return rows
