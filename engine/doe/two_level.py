"""Lane D: two-level factorial designs 2^k (Meeting 10, Montgomery Ch. 6)."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats

LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # Montgomery skips I


def letters(k: int) -> list[str]:
    return list(LETTERS[:k])


def run_label(signs, names) -> str:
    lab = "".join(n.lower() for n, s in zip(names, signs) if s > 0)
    return lab or "(1)"


def standard_order(k: int) -> np.ndarray:
    """2^k x k matrix of ±1 in Yates standard order: (1), a, b, ab, c, ..."""
    return np.array([[1 if (i >> j) & 1 else -1 for j in range(k)] for i in range(2 ** k)])


def all_effects(names: list[str], max_order: int | None = None) -> list[str]:
    out = []
    k = len(names)
    for r in range(1, (max_order or k) + 1):
        for c in itertools.combinations(names, r):
            out.append("".join(c))
    return out


def col(X: pd.DataFrame, effect: str) -> np.ndarray:
    v = np.ones(len(X))
    for ch in effect:
        v = v * X[ch].values
    return v


def generate(k: int, names=None, low=None, high=None, replicates: int = 1, center: int = 0, seed: int = 640,
             randomize: bool = True) -> dict:
    names = names or letters(k)
    base = standard_order(k)
    rows = []
    std = 0
    for rep in range(replicates):
        for r in base:
            std += 1
            row = {"Std order": std, "Replicate": rep + 1, "Run label": run_label(r, letters(k))}
            for n, L, s in zip(names, letters(k), r):
                row[L] = int(s)
                if low and high:
                    row[n + " (real)"] = (low[names.index(n)] if s < 0 else high[names.index(n)])
            rows.append(row)
    for c in range(center):
        std += 1
        row = {"Std order": std, "Replicate": None, "Run label": "center"}
        for i, (n, L) in enumerate(zip(names, letters(k))):
            row[L] = 0
            if low and high:
                row[n + " (real)"] = (low[i] + high[i]) / 2
        rows.append(row)
    df = pd.DataFrame(rows)
    rng = np.random.default_rng(seed)
    df["Run order"] = rng.permutation(len(df)) + 1 if randomize else np.arange(1, len(df) + 1)
    return {"runs": df.to_dict(orient="records"), "columns": list(df.columns), "n_runs": len(df), "seed": seed,
            "factor_letters": letters(k), "names": names}


def lenth(effects: np.ndarray, alpha: float = 0.05) -> dict:
    a = np.abs(np.asarray(effects, float))
    s0 = 1.5 * np.median(a)
    pse = 1.5 * np.median(a[a < 2.5 * s0]) if (a < 2.5 * s0).any() else s0
    d = len(a) / 3
    me = stats.t.ppf(1 - alpha / 2, d) * pse
    gamma = (1 + (1 - alpha) ** (1 / len(a))) / 2
    sme = stats.t.ppf(gamma, d) * pse
    return {"PSE": pse, "ME": me, "SME": sme}


def analyze(k: int, data: list[dict] | pd.DataFrame, response: str = "y", names=None, model_terms=None,
            alpha: float = 0.05) -> dict:
    """data rows need factor columns (letters, coded ±1, 0 for centre) and the response."""
    L = letters(k)
    df = pd.DataFrame(data).copy()
    df[response] = pd.to_numeric(df[response], errors="coerce")
    df = df.dropna(subset=[response])
    for c in L:
        df[c] = pd.to_numeric(df[c])
    center = df[(df[L] == 0).all(axis=1)]
    fact = df[~(df[L] == 0).all(axis=1)]
    y = fact[response].values.astype(float)
    N = len(fact)
    n_rep = N / 2 ** k
    effects = all_effects(L)
    rows = []
    for e in effects:
        c = col(fact, e)
        contrast = float((c * y).sum())
        eff = contrast / (N / 2)
        ss = contrast ** 2 / N
        rows.append({"term": e, "contrast": contrast, "effect": eff, "coef": eff / 2, "ss": ss})
    ss_tot = float(((y - y.mean()) ** 2).sum())
    for r in rows:
        r["pct"] = 100 * r["ss"] / ss_tot if ss_tot else 0
    effs = np.array([r["effect"] for r in rows])
    out = {"effects": rows, "mean": float(y.mean()), "N": N, "replicates": n_rep, "ss_total": ss_tot}
    # normal & half-normal plot data
    order = np.argsort(effs)
    m = len(effs)
    pn = (np.arange(1, m + 1) - 0.5) / m
    out["normal_plot"] = [{"term": rows[i]["term"], "effect": float(effs[i]), "z": float(stats.norm.ppf(pn[j]))}
                          for j, i in enumerate(order)]
    ordh = np.argsort(np.abs(effs))
    ph = 0.5 + 0.5 * (np.arange(1, m + 1) - 0.5) / m
    out["half_normal_plot"] = [{"term": rows[i]["term"], "abs_effect": float(abs(effs[i])),
                                "z": float(stats.norm.ppf(ph[j]))} for j, i in enumerate(ordh)]
    out["lenth"] = lenth(effs, alpha)
    out["lenth_active"] = [r["term"] for r in rows if abs(r["effect"]) > out["lenth"]["ME"]]
    # ANOVA
    if model_terms is None:
        model_terms = effects if n_rep >= 2 else out["lenth_active"]
    out["model_terms"] = list(model_terms)
    an = []
    ss_model = 0.0
    for r in rows:
        if r["term"] in model_terms:
            an.append([r["term"], r["ss"], 1])
            ss_model += r["ss"]
    df_err = N - 1 - len(model_terms)
    ss_err = ss_tot - ss_model
    tab = []
    if df_err > 0:
        mse = ss_err / df_err
        for t, ss, d in an:
            F = ss / mse
            tab.append({"term": t, "ss": ss, "df": d, "ms": ss, "F": F, "p": float(stats.f.sf(F, 1, df_err))})
        tab.append({"term": "Error", "ss": ss_err, "df": df_err, "ms": mse, "F": None, "p": None})
        # pure error when replicated
        if n_rep >= 2 and len(model_terms) < len(effects):
            g = fact.groupby(L)[response]
            ss_pe = float(((fact[response] - g.transform("mean")) ** 2).sum())
            df_pe = N - 2 ** k
            tab.append({"term": "  Pure error", "ss": ss_pe, "df": df_pe, "ms": ss_pe / df_pe if df_pe else None,
                        "F": None, "p": None})
        out["mse"] = mse
    tab.append({"term": "Total", "ss": ss_tot, "df": N - 1, "ms": None, "F": None, "p": None})
    out["anova"] = tab
    out["df_error"] = df_err
    # curvature (centre points)
    if len(center) >= 2:
        nf, nc = N, len(center)
        yf, yc = y.mean(), center[response].mean()
        ss_c = nf * nc * (yf - yc) ** 2 / (nf + nc)
        ms_pe = center[response].var(ddof=1)
        Fc = ss_c / ms_pe
        out["curvature"] = {"ss": ss_c, "F": Fc, "df": [1, nc - 1], "p": float(stats.f.sf(Fc, 1, nc - 1)),
                            "y_factorial": yf, "y_center": yc}
    # regression equation (coded)
    coefs = {t: r["coef"] for r in rows for t in [r["term"]] if t in model_terms}
    eq = f"ŷ = {y.mean():.4f}" + "".join(f" {'+' if b >= 0 else '−'} {abs(b):.4f}·{' '.join('x' + str(L.index(c) + 1) for c in t)}"
                                         for t, b in coefs.items())
    out["equation_coded"] = eq
    if names:
        out["names"] = dict(zip(L, names))
    return out


def collapse_drop(k: int, data, drop: str, response: str = "y") -> dict:
    """Drop an inactive factor: the 2^k becomes a 2^(k-1) with 2 replicates (filtration example)."""
    L = letters(k)
    keep = [c for c in L if c != drop]
    df = pd.DataFrame(data).copy()
    sub = df[[*keep, response]].rename(columns={c: n for c, n in zip(keep, letters(k - 1))})
    full = all_effects(letters(k - 1))
    res = analyze(k - 1, sub, response, model_terms=full)
    res["mapping"] = dict(zip(letters(k - 1), keep))
    for r in res["effects"]:
        r["term_original"] = "".join(res["mapping"][c] for c in r["term"])
    for r in res["anova"]:
        if r["term"] not in ("Error", "Total", "  Pure error"):
            r["term"] = "".join(res["mapping"][c] for c in r["term"])
    return res


def from_labels(k: int, labelled: dict, response: str = "y") -> list[dict]:
    """{'(1)': 45, 'a': 71, ...} -> coded rows."""
    L = letters(k)
    rows = []
    for lab, val in labelled.items():
        vals = val if isinstance(val, (list, tuple)) else [val]
        for v in vals:
            row = {c: (1 if c.lower() in lab and lab != "(1)" else -1) for c in L}
            row[response] = v
            row["Run label"] = lab
            rows.append(row)
    return rows
