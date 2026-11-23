"""Lane D: robust parameter design (Taguchi crossed arrays and the response-model approach; Montgomery Ch. 12)."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .two_level import standard_order


# ---------------------------------------------------------------- orthogonal arrays
def _gf3_array(n_base: int) -> np.ndarray:
    """3-level OA from GF(3): L9 (n_base=2, 4 cols) and L27 (n_base=3, 13 cols). Levels 1..3."""
    base = np.array(list(itertools.product(range(3), repeat=n_base)))
    cols = []
    for coefs in itertools.product(range(3), repeat=n_base):
        if not any(coefs):
            continue
        first = next(c for c in coefs if c)
        if first != 1:
            continue
        cols.append((base @ np.array(coefs)) % 3)
    return np.column_stack(cols) + 1


def _pb12() -> np.ndarray:
    gen = [1, 1, -1, 1, 1, 1, -1, -1, -1, 1, -1]
    rows = [np.roll(gen, i) for i in range(11)] + [np.full(11, -1)]
    return np.array(rows)


def orthogonal_array(name: str) -> np.ndarray:
    name = name.upper()
    if name in ("L4", "L8", "L16"):
        n = {"L4": 2, "L8": 3, "L16": 4}[name]
        F = standard_order(n)
        cols = []
        for r in range(1, n + 1):
            for c in itertools.combinations(range(n), r):
                cols.append(np.prod(F[:, list(c)], axis=1))
        A = np.column_stack(cols)
        return np.where(A > 0, 2, 1)
    if name == "L9":
        return _gf3_array(2)
    if name == "L27":
        return _gf3_array(3)
    if name == "L12":
        return np.where(_pb12() > 0, 2, 1)
    raise ValueError(f"Orthogonal array {name} is not available (L4, L8, L9, L12, L16, L27).")


# ---------------------------------------------------------------- SN ratios
def sn_ratio(y, kind: str) -> float:
    y = np.asarray(y, float)
    if kind == "smaller":
        return float(-10 * math.log10((y ** 2).mean()))
    if kind == "larger":
        return float(-10 * math.log10((1 / y ** 2).mean()))
    s2 = y.var(ddof=1)
    return float(10 * math.log10(y.mean() ** 2 / s2)) if s2 > 0 else float("inf")


def crossed(inner: list[list], outer_responses: list[list], control_names: list[str], kind: str = "nominal") -> dict:
    """inner: runs x control-factor levels; outer_responses: for each inner run, the y values over the outer array."""
    Xi = pd.DataFrame(inner, columns=control_names)
    stats_rows = []
    for i, ys in enumerate(outer_responses):
        y = np.asarray(ys, float)
        s = y.std(ddof=1)
        stats_rows.append({"run": i + 1, "ybar": y.mean(), "s": s, "ln_s2": math.log(s * s) if s > 0 else None,
                           "SN": sn_ratio(y, kind)})
    S = pd.DataFrame(stats_rows)
    effects = {}
    for c in control_names:
        g = pd.concat([Xi[c], S[["ybar", "SN"]]], axis=1).groupby(c)
        effects[c] = {"levels": [str(l) for l in g.groups], "SN": g["SN"].mean().tolist(),
                      "mean": g["ybar"].mean().tolist(),
                      "SN_range": float(g["SN"].mean().max() - g["SN"].mean().min()),
                      "mean_range": float(g["ybar"].mean().max() - g["ybar"].mean().min())}
    best = {c: effects[c]["levels"][int(np.argmax(effects[c]["SN"]))] for c in control_names}
    snr = np.array([effects[c]["SN_range"] for c in control_names])
    mr = np.array([effects[c]["mean_range"] for c in control_names])
    adj = [c for c, a, b in zip(control_names, snr, mr) if a <= np.median(snr) and b >= np.median(mr)]
    # separate models for ybar and ln s² (Montgomery's recommendation)
    models = {}
    for resp in ("ybar", "ln_s2"):
        d = pd.concat([Xi.astype(float), S[resp]], axis=1).dropna()
        if len(d) > len(control_names) + 1:
            m = sm.OLS(d[resp], sm.add_constant(d[control_names])).fit()
            models[resp] = {"params": m.params.to_dict(), "p": m.pvalues.to_dict(), "r2": m.rsquared}
    return {"run_stats": stats_rows, "effects": effects, "best_SN_settings": best, "adjustment_candidates": adj,
            "models": models, "kind": kind,
            "caveat": ("Montgomery's caveat: SN ratios confound location and dispersion and the crossed array ignores "
                       "control × control interactions; check the separate models for ȳ and ln s² as well.")}


# ---------------------------------------------------------------- combined array (response model)
def combined(data, x_names: list[str], z_names: list[str], response: str, sigma_z2: float = 1.0,
             target: float | None = None, tol: float = 0.0, quadratic: bool = False, grid_n: int = 21) -> dict:
    df = pd.DataFrame(data).dropna(subset=[response]).copy()
    cols, terms = {}, []
    for x in x_names:
        cols[x] = df[x].astype(float)
    for z in z_names:
        cols[z] = df[z].astype(float)
    for a, b in itertools.combinations(x_names, 2):
        cols[f"{a}*{b}"] = df[a].astype(float) * df[b].astype(float)
    if quadratic:
        for x in x_names:
            cols[f"{x}^2"] = df[x].astype(float) ** 2
    for x in x_names:
        for z in z_names:
            cols[f"{x}*{z}"] = df[x].astype(float) * df[z].astype(float)
    X = sm.add_constant(pd.DataFrame(cols))
    m = sm.OLS(df[response].astype(float), X).fit()
    P = m.params
    mse = m.mse_resid
    kx = len(x_names)
    beta = np.array([P[x] for x in x_names])
    gamma = np.array([P[z] for z in z_names])
    Bm = np.zeros((kx, kx))
    for i, j in itertools.combinations(range(kx), 2):
        Bm[i, j] = Bm[j, i] = P[f"{x_names[i]}*{x_names[j]}"] / 2
    if quadratic:
        for i, x in enumerate(x_names):
            Bm[i, i] = P[f"{x}^2"]
    Delta = np.array([[P[f"{x}*{z}"] for z in z_names] for x in x_names])

    def mean_f(x):
        return float(P["const"] + x @ beta + x @ Bm @ x)

    def var_f(x):
        v = gamma + Delta.T @ x
        return float(sigma_z2 * v @ v + mse)

    sig = [{"term": t, "estimate": float(P[t]), "p": float(m.pvalues[t])} for t in P.index if "*" in t and
           any(z in t.split("*") for z in z_names)]
    g = np.linspace(-1, 1, grid_n)
    out = {"params": P.to_dict(), "p": m.pvalues.to_dict(), "mse": mse, "r2": m.rsquared,
           "mean_model": f"E_z[y] = {P['const']:.3f}" + "".join(f" {'+' if b >= 0 else '−'} {abs(b):.3f}{x}"
                                                               for x, b in zip(x_names, beta)),
           "variance_model": "Var_z[y] = σ_z²(γ + Δ′x)′(γ + Δ′x) + σ²", "control_noise_interactions": sig}
    if kx >= 1:
        best = None
        mean_grid, sd_grid = [], []
        pts = list(itertools.product(g, repeat=kx)) if kx <= 3 else [tuple(np.zeros(kx))]
        for pt in pts:
            x = np.array(pt)
            mu, v = mean_f(x), var_f(x)
            ok = target is None or abs(mu - target) <= tol
            if ok and (best is None or v < best[1]):
                best = (x.tolist(), v, mu)
        out["optimum"] = None if best is None else {"x": best[0], "var": best[1], "sd": math.sqrt(best[1]),
                                                   "mean": best[2]}
        if kx >= 2:
            for yj in g:
                mean_grid.append([mean_f(np.array([xi, yj] + [0] * (kx - 2))) for xi in g])
                sd_grid.append([math.sqrt(var_f(np.array([xi, yj] + [0] * (kx - 2)))) for xi in g])
            out["contours"] = {"x": g.tolist(), "y": g.tolist(), "mean": mean_grid, "sd": sd_grid}
    return out
