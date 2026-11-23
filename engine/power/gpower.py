"""G*Power 3.1 equivalent power calculations from noncentral distributions.

Every family exposes power(es, n, alpha, **kw). The generic solvers below give
the four G*Power modes: a priori (N), post hoc (power), sensitivity (effect),
criterion (alpha).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats

# -------------------------------------------------------------- families
# each entry: power(es, N, alpha, p) where N is the TOTAL sample size and p a dict of extra params


def _t_power(delta, df, alpha, tails):
    if tails == 2:
        tc = stats.t.ppf(1 - alpha / 2, df)
        return float(stats.nct.sf(tc, df, delta) + stats.nct.cdf(-tc, df, delta))
    tc = stats.t.ppf(1 - alpha, df)
    return float(stats.nct.sf(tc, df, delta))


def _split(N, ratio):
    n1 = N / (1 + ratio)
    return n1, N - n1


def p_ttest_ind(d, N, alpha, p):
    ratio = p.get("ratio", 1.0)
    n1, n2 = p.get("n1"), p.get("n2")
    if n1 is None or n2 is None:
        n1, n2 = _split(N, ratio)
    return _t_power(d * math.sqrt(n1 * n2 / (n1 + n2)), n1 + n2 - 2, alpha, p.get("tails", 2))


def p_ttest_paired(dz, N, alpha, p):
    return _t_power(dz * math.sqrt(N), N - 1, alpha, p.get("tails", 2))


def _f_power(lam, df1, df2, alpha):
    if df2 <= 0 or df1 <= 0:
        return float("nan")
    fc = stats.f.ppf(1 - alpha, df1, df2)
    return float(stats.ncf.sf(fc, df1, df2, lam))


def p_anova_oneway(f, N, alpha, p):
    k = p.get("k", 3)
    return _f_power(f * f * N, k - 1, N - k, alpha)


def p_anova_special(f, N, alpha, p):
    return _f_power(f * f * N, p.get("df1", 1), N - p.get("cells", 4), alpha)


def p_rm_within(f, N, alpha, p):
    k, m, rho, eps = p.get("groups", 1), p.get("m", 3), p.get("rho", 0.5), p.get("eps", 1.0)
    lam = f * f * N * m * eps / (1 - rho)
    return _f_power(lam, (m - 1) * eps, (N - k) * (m - 1) * eps, alpha)


def p_rm_between(f, N, alpha, p):
    k, m, rho = p.get("groups", 2), p.get("m", 3), p.get("rho", 0.5)
    lam = f * f * N * m / (1 + (m - 1) * rho)
    return _f_power(lam, k - 1, N - k, alpha)


def p_rm_interaction(f, N, alpha, p):
    k, m, rho, eps = p.get("groups", 2), p.get("m", 3), p.get("rho", 0.5), p.get("eps", 1.0)
    lam = f * f * N * m * eps / (1 - rho)
    return _f_power(lam, (k - 1) * (m - 1) * eps, (N - k) * (m - 1) * eps, alpha)


def p_reg_r2(f2, N, alpha, p):
    q = p.get("predictors", 3)
    return _f_power(f2 * N, q, N - q - 1, alpha)


def p_reg_r2_increase(f2, N, alpha, p):
    q, tot = p.get("tested", 1), p.get("predictors", 3)
    return _f_power(f2 * N, q, N - tot - 1, alpha)


def p_chisq(w, N, alpha, p):
    df = p.get("df", 1)
    cc = stats.chi2.ppf(1 - alpha, df)
    return float(stats.ncx2.sf(cc, df, w * w * N))


def p_logistic(or_, N, alpha, p):
    """Hsieh, Bloch & Larsen (1998) for one binary/normal covariate — approximate."""
    p0 = p.get("p0", 0.5)
    tails = p.get("tails", 2)
    za = stats.norm.ppf(1 - alpha / tails)
    if p.get("x_dist", "normal") == "binomial":
        B = p.get("x_p", 0.5)
        p1 = or_ * p0 / (1 - p0 + or_ * p0)
        pbar = (1 - B) * p0 + B * p1
        # Hsieh eq. for binary X: N = (za*sqrt(pbar(1-pbar)/B) + zb*sqrt(p0(1-p0)+p1(1-p1)(1-B)/B))^2 / ((p0-p1)^2 (1-B))
        a = za * math.sqrt(pbar * (1 - pbar) / B)
        c = math.sqrt(p0 * (1 - p0) + p1 * (1 - p1) * (1 - B) / B)
        zb = (math.sqrt(N * (p0 - p1) ** 2 * (1 - B)) - a) / c
        return float(stats.norm.cdf(zb))
    beta = math.log(or_)
    zb = math.sqrt(N * p0 * (1 - p0) * beta ** 2) - za
    return float(stats.norm.cdf(zb))


FAMILIES = {
    "ttest_ind": {"fn": p_ttest_ind, "es": "d", "default": 0.5, "label": "t tests – Means: difference between two independent means (two groups)", "min_n": 4},
    "ttest_paired": {"fn": p_ttest_paired, "es": "dz", "default": 0.5, "label": "t tests – Means: difference between two dependent means (matched pairs)", "min_n": 3},
    "anova_oneway": {"fn": p_anova_oneway, "es": "f", "default": 0.25, "label": "F tests – ANOVA: fixed effects, omnibus, one-way", "min_n": None},
    "anova_special": {"fn": p_anova_special, "es": "f", "default": 0.25, "label": "F tests – ANOVA: fixed effects, special, main effects and interactions", "min_n": None},
    "rm_within": {"fn": p_rm_within, "es": "f", "default": 0.25, "label": "F tests – ANOVA: repeated measures, within factors", "min_n": None},
    "rm_between": {"fn": p_rm_between, "es": "f", "default": 0.25, "label": "F tests – ANOVA: repeated measures, between factors", "min_n": None},
    "rm_interaction": {"fn": p_rm_interaction, "es": "f", "default": 0.25, "label": "F tests – ANOVA: repeated measures, within-between interaction", "min_n": None},
    "reg_r2": {"fn": p_reg_r2, "es": "f2", "default": 0.15, "label": "F tests – Linear multiple regression: fixed model, R² deviation from zero", "min_n": None},
    "reg_r2_increase": {"fn": p_reg_r2_increase, "es": "f2", "default": 0.15, "label": "F tests – Linear multiple regression: fixed model, R² increase", "min_n": None},
    "chisq": {"fn": p_chisq, "es": "w", "default": 0.3, "label": "χ² tests – Goodness-of-fit tests: contingency tables", "min_n": 2},
    "logistic": {"fn": p_logistic, "es": "OR", "default": 1.5, "label": "z tests – Logistic regression (approximate, Hsieh et al. 1998)", "min_n": 10},
}


def _min_n(family: str, p: dict) -> int:
    f = FAMILIES[family]
    if f["min_n"]:
        return f["min_n"]
    if family in ("anova_oneway",):
        return p.get("k", 3) + 1
    if family == "anova_special":
        return p.get("cells", 4) + 1
    if family.startswith("rm_"):
        return p.get("groups", 1) + 1
    if family == "reg_r2":
        return p.get("predictors", 3) + 2
    if family == "reg_r2_increase":
        return p.get("predictors", 3) + 2
    return 3


def power(family: str, es: float, N: float, alpha: float, p: dict) -> float:
    v = FAMILIES[family]["fn"](es, N, alpha, p)
    if v != v:  # NaN from an extreme noncentrality -> power is effectively 1
        return 1.0 if es > 0 else float("nan")
    return min(max(v, 0.0), 1.0)


def _apriori(family, es, alpha, target, p):
    """Smallest N reaching the target power (two-group t: per-group sizes as in G*Power)."""
    if family == "ttest_ind":
        ratio = p.get("ratio", 1.0)
        n1 = 2
        while n1 < 10 ** 6:
            n2 = math.ceil(n1 * ratio)
            pw = p_ttest_ind(es, n1 + n2, alpha, {**p, "n1": n1, "n2": n2})
            if pw >= target:
                return {"N": n1 + n2, "n1": n1, "n2": n2, "power": pw}
            n1 += 1
        raise ValueError("No N found below 1,000,000.")
    N = _min_n(family, p)
    step = 1
    groups = None
    if family == "anova_oneway":  # G*Power keeps the groups equal: N steps in multiples of k
        step = p.get("k", 3)
        N = math.ceil(N / step) * step
    while N < 10 ** 6:
        pw = power(family, es, N, alpha, p)
        if pw >= target:
            out = {"N": N, "power": pw}
            if groups and N % groups:
                out["note"] = f"N = {N} is not a multiple of {groups}; use {math.ceil(N / groups) * groups} for equal groups."
            return out
        N += step
    raise ValueError("No N found below 1,000,000.")


def calculate(family: str, mode: str, params: dict) -> dict:
    fam = FAMILIES[family]
    p = dict(params)
    alpha = float(p.pop("alpha", 0.05))
    es = p.pop("es", fam["default"])
    target = float(p.pop("power", 0.80))
    N = p.pop("N", None)
    out = {"family": family, "label": fam["label"], "mode": mode, "es_name": fam["es"]}
    if mode == "apriori":
        r = _apriori(family, float(es), alpha, target, p)
        out.update({"es": es, "alpha": alpha, "target_power": target, **r})
    elif mode == "posthoc":
        if family == "ttest_ind" and "n1" in p and "n2" in p:
            N = p["n1"] + p["n2"]
        pw = power(family, float(es), float(N), alpha, p)
        out.update({"es": es, "alpha": alpha, "N": N, "power": pw})
    elif mode == "sensitivity":
        if family == "ttest_ind" and "n1" in p and "n2" in p:
            N = p["n1"] + p["n2"]
        f = lambda e: power(family, e, float(N), alpha, p) - target
        lo, hi = (1.0001, 50.0) if family == "logistic" else (1e-6, 10.0)
        es = optimize.brentq(f, lo, hi)
        out.update({"es": es, "alpha": alpha, "N": N, "power": target})
    elif mode == "criterion":
        if family == "ttest_ind" and "n1" in p and "n2" in p:
            N = p["n1"] + p["n2"]
        f = lambda a: power(family, float(es), float(N), a, p) - target
        a = optimize.brentq(f, 1e-10, 0.999)
        out.update({"es": es, "alpha": a, "N": N, "power": target})
    else:
        raise ValueError(f"Unknown mode {mode}")
    # curve
    Nmax = max(int((out.get("N") or 50) * 2), 20)
    Ns = sorted(set(int(x) for x in np.linspace(_min_n(family, p), Nmax, 60)))
    out["curve"] = [{"N": n, "power": power(family, float(out["es"]), n, float(out["alpha"]),
                                            {k: v for k, v in p.items() if k not in ("n1", "n2")})} for n in Ns]
    out["report"] = report_sentence(out, p)
    return out


def report_sentence(o: dict, p: dict) -> str:
    es = f"{o['es_name']} = {o['es']:.3f}".replace("0.", ".", 1) if o["es_name"] in ("f", "f2", "w") else \
        f"{o['es_name']} = {o['es']:.3f}"
    tool = "an a priori power analysis (G*Power-equivalent, DesignLab)"
    if o["mode"] == "apriori":
        per = f" ({o['n1']} and {o['n2']} per group)" if "n1" in o else ""
        return (f"Based on {tool} for the {o['label'].split('–', 1)[-1].strip()}, with {es}, α = {o['alpha']:.2f} and "
                f"power = {o['target_power']:.2f}, the required total sample size is N = {o['N']}{per}; "
                f"the achieved power is {o['power']:.3f}.")
    if o["mode"] == "posthoc":
        return (f"A post hoc power analysis with {es}, α = {o['alpha']:.2f} and N = {o['N']} gives a power of "
                f"{o['power']:.3f}.")
    if o["mode"] == "sensitivity":
        return (f"A sensitivity analysis showed that with N = {o['N']}, α = {o['alpha']:.2f} and power = "
                f"{o['power']:.2f}, the smallest detectable effect is {o['es_name']} = {o['es']:.3f}.")
    return f"With {es}, N = {o['N']} and power = {o['power']:.2f}, the implied α is {o['alpha']:.4f}."


# -------------------------------------------------------------- effect-size helpers
def d_from_means(m1, m2, sd1, sd2, n1=None, n2=None):
    if n1 and n2:
        sp = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2))
    else:
        sp = math.sqrt((sd1 ** 2 + sd2 ** 2) / 2)
    return abs(m1 - m2) / sp


def f_from_means(means, sd, ns=None):
    means = np.asarray(means, float)
    w = np.ones_like(means) if ns is None else np.asarray(ns, float)
    mu = (w * means).sum() / w.sum()
    sigma_m = math.sqrt((w * (means - mu) ** 2).sum() / w.sum())
    return sigma_m / sd


def f2_from_r2(r2):
    return r2 / (1 - r2)


def f_from_peta2(e):
    return math.sqrt(e / (1 - e))


def peta2_from_f(f):
    return f * f / (1 + f * f)


def w_from_table(p0, p1):
    p0, p1 = np.asarray(p0, float).ravel(), np.asarray(p1, float).ravel()
    return float(math.sqrt(((p1 - p0) ** 2 / p0).sum()))


def familywise(m: int, alpha: float = 0.05) -> float:
    return 1 - (1 - alpha) ** m
