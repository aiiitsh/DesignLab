"""Effect sizes and their confidence intervals."""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats


def _nct_ci(t: float, df: float, conf: float = 0.95) -> tuple[float, float]:
    """CI for the noncentrality parameter of a t statistic (exact, as JASP/MBESS)."""
    a = (1 - conf) / 2

    def f(ncp, target):
        return stats.nct.cdf(t, df, ncp) - target

    lo_b, hi_b = t - 50, t + 50
    try:
        lo = optimize.brentq(f, lo_b, hi_b, args=(1 - a,))
        hi = optimize.brentq(f, lo_b, hi_b, args=(a,))
    except ValueError:
        return float("nan"), float("nan")
    return lo, hi


def cohen_d_ind(a, b, pooled: bool = True) -> dict:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    n1, n2 = len(a), len(b)
    v1, v2 = a.var(ddof=1), b.var(ddof=1)
    if pooled:
        sd = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    else:
        sd = math.sqrt((v1 + v2) / 2)
    d = (a.mean() - b.mean()) / sd
    t = d / math.sqrt(1 / n1 + 1 / n2)
    lo, hi = _nct_ci(t, n1 + n2 - 2)
    k = math.sqrt(1 / n1 + 1 / n2)
    J = 1 - 3 / (4 * (n1 + n2) - 9)
    return {"d": d, "ci": (lo * k, hi * k), "g": d * J, "sd": sd}


def cohen_dz(diff) -> dict:
    diff = np.asarray(diff, float)
    n = len(diff)
    dz = diff.mean() / diff.std(ddof=1)
    t = dz * math.sqrt(n)
    lo, hi = _nct_ci(t, n - 1)
    return {"d": dz, "ci": (lo / math.sqrt(n), hi / math.sqrt(n))}


def eta_from_ss(ss_effect: float, ss_total: float) -> float:
    return ss_effect / ss_total if ss_total else float("nan")


def partial_eta(ss_effect: float, ss_error: float) -> float:
    return ss_effect / (ss_effect + ss_error) if (ss_effect + ss_error) else float("nan")


def omega_sq(ss_effect: float, df_effect: float, ms_error: float, ss_total: float) -> float:
    return (ss_effect - df_effect * ms_error) / (ss_total + ms_error)


def f_from_eta(eta2p: float) -> float:
    return math.sqrt(eta2p / (1 - eta2p))


def eta_from_f(f: float) -> float:
    return f * f / (1 + f * f)
