"""Assumption checks: Shapiro-Wilk, Levene (mean-centered, as JASP), Mauchly + GG/HF epsilon."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats


def shapiro(x) -> tuple[float, float]:
    x = pd.Series(x).dropna().astype(float)
    if len(x) < 3 or x.nunique() < 2:
        return float("nan"), float("nan")
    r = stats.shapiro(x)
    return float(r.statistic), float(r.pvalue)


def levene(*groups) -> tuple[float, float, int, int]:
    """Levene's test centered on the mean (JASP default)."""
    gs = [pd.Series(g).dropna().astype(float).values for g in groups]
    gs = [g for g in gs if len(g) > 0]
    if len(gs) < 2:
        return float("nan"), float("nan"), 0, 0
    r = stats.levene(*gs, center="mean")
    n = sum(len(g) for g in gs)
    return float(r.statistic), float(r.pvalue), len(gs) - 1, n - len(gs)


def _orth_contrasts(k: int) -> np.ndarray:
    """Normalised orthogonal (Helmert) contrasts, k x (k-1)."""
    C = np.zeros((k, k - 1))
    for j in range(1, k):
        C[:j, j - 1] = 1.0
        C[j, j - 1] = -j
        C[:, j - 1] /= np.linalg.norm(C[:, j - 1])
    return C


def sphericity(wide: np.ndarray, groups: np.ndarray | None = None) -> dict:
    """Mauchly's test and GG / HF epsilons for an n x k matrix of repeated measures.

    With between-subject groups the pooled within-group covariance is used
    (as JASP/SPSS do for mixed designs). HF uses the Lecoutre (1991) correction,
    which JASP reports.
    """
    Y = np.asarray(wide, dtype=float)
    n, k = Y.shape
    p = k - 1
    if groups is None:
        groups = np.zeros(n)
    g_levels = pd.unique(groups)
    g = len(g_levels)
    C = _orth_contrasts(k)
    Z = Y @ C
    # pooled within-group SSCP
    S = np.zeros((p, p))
    for lvl in g_levels:
        Zg = Z[groups == lvl]
        Zc = Zg - Zg.mean(axis=0)
        S += Zc.T @ Zc
    dfe = n - g
    S /= dfe
    eig = np.linalg.eigvalsh(S)
    gg = float((eig.sum() ** 2) / (p * (eig ** 2).sum())) if p > 0 else 1.0
    hf_raw = ((dfe + 1) * p * gg - 2) / (p * (dfe - p * gg)) if p > 0 else 1.0
    hf = float(min(1.0, hf_raw))
    lower = 1.0 / p if p > 0 else 1.0
    if p < 2:
        return {"W": 1.0, "chi2": float("nan"), "df": 0, "p": float("nan"), "gg": 1.0, "hf": 1.0,
                "lower": 1.0, "testable": False}
    W = float(np.linalg.det(S) / (np.trace(S) / p) ** p)
    f = 1 - (2 * p * p + p + 2) / (6 * p * dfe)
    chi2 = float(-dfe * f * math.log(W)) if W > 0 else float("inf")
    df = p * (p + 1) // 2 - 1
    # second-order correction as in R's mauchly.test (used by JASP through car::Anova)
    w2 = ((p + 2) * (p - 1) * (p - 2) * (2 * p ** 3 + 6 * p ** 2 + 3 * p + 2)) / (288 * (dfe * p * f) ** 2)
    pr1 = stats.chi2.sf(chi2, df)
    pr2 = stats.chi2.sf(chi2, df + 4)
    pval = float(pr1 + w2 * (pr2 - pr1))
    return {"W": W, "chi2": chi2, "df": df, "p": pval, "gg": gg, "hf": hf, "lower": lower, "testable": True}


def choose_correction(sph: dict, alpha: float = 0.05) -> tuple[str, float, str]:
    """Course rule (Meetings 7/9): if Mauchly p < .05 -> epsilon < .60 ? GG : HF."""
    from .common import fmt_p
    pp = fmt_p(sph.get("p"))
    peq = f"p {pp}" if pp.startswith("<") else f"p = {pp}"
    if not sph.get("testable"):
        return "none", 1.0, "Sphericity is automatically met with only 2 levels."
    if sph["p"] >= alpha:
        return "none", 1.0, f"Mauchly's test was not significant ({peq}), so sphericity is assumed."
    if sph["gg"] < 0.60:
        return "Greenhouse-Geisser", sph["gg"], (
            f"Mauchly {peq} < .05 and GG ε = {sph['gg']:.3f} < 0.60 → Greenhouse-Geisser (course rule, Meeting 7).")
    return "Huynh-Feldt", sph["hf"], (
        f"Mauchly {peq} < .05 and GG ε = {sph['gg']:.3f} ≥ 0.60 → Huynh-Feldt (course rule, Meeting 7).")


def sphericity_scores(Z: np.ndarray, groups: np.ndarray | None = None) -> dict:
    """Mauchly / GG / HF from orthonormal contrast scores Z (n x p)."""
    Z = np.asarray(Z, float)
    n, p = Z.shape
    k_equiv = p + 1
    # build a fake wide matrix whose Helmert scores equal Z: Y = Z @ C.T works because C is orthonormal
    C = _orth_contrasts(k_equiv)
    return sphericity(Z @ C.T, groups)
