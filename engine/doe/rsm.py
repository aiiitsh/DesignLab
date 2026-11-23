"""Lane D: response surface methodology (Montgomery Ch. 11)."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from .two_level import letters, standard_order


def curvature(y_factorial, y_center) -> dict:
    yf = np.asarray(y_factorial, float)
    yc = np.asarray(y_center, float)
    nf, nc = len(yf), len(yc)
    ss = nf * nc * (yf.mean() - yc.mean()) ** 2 / (nf + nc)
    mspe = yc.var(ddof=1)
    F = ss / mspe
    return {"ss_curvature": ss, "ms_pure_error": mspe, "F": F, "df": [1, nc - 1], "p": float(stats.f.sf(F, 1, nc - 1)),
            "y_factorial": yf.mean(), "y_center": yc.mean()}


def steepest(coefs: dict, base: str | None = None, step: float = 1.0, n_steps: int = 10, centers=None, halfs=None,
             descent: bool = False) -> dict:
    """Path of steepest ascent from a first-order model in coded units (and real units if given)."""
    names = list(coefs)
    b = np.array([coefs[n] for n in names], float) * (-1 if descent else 1)
    base = base or names[int(np.argmax(np.abs(b)))]
    j = names.index(base)
    delta = b / abs(b[j]) * step
    rows = []
    for s in range(n_steps + 1):
        x = delta * s
        row = {"Step": "Origin" if s == 0 else f"Origin + {s}Δ"}
        for i, n in enumerate(names):
            row[f"x{i + 1} ({n}) coded"] = x[i]
            if centers and halfs:
                row[f"{n} real"] = centers[i] + x[i] * halfs[i]
        rows.append(row)
    return {"base": base, "delta_coded": dict(zip(names, delta.tolist())), "path": rows}


def ccd(k: int, alpha: str | float = "rotatable", center: int = 4, fraction_p: int = 0) -> dict:
    F = standard_order(k)
    nf = len(F)
    if alpha == "rotatable":
        a = nf ** 0.25
    elif alpha == "face":
        a = 1.0
    elif alpha == "orthogonal":
        # Montgomery: alpha = (Q F / 4)^(1/4), Q = (sqrt(F + T) - sqrt(F))^2, T = 2k + n_c
        a = ((nf * (math.sqrt(nf + 2 * k + center) - math.sqrt(nf)) ** 2) / 4) ** 0.25
    else:
        a = float(alpha)
    rows = [list(r) for r in F]
    for i in range(k):
        for s in (-a, a):
            v = [0.0] * k
            v[i] = s
            rows.append(v)
    rows += [[0.0] * k for _ in range(center)]
    L = letters(k)
    df = pd.DataFrame(rows, columns=[f"x{i + 1}" for i in range(k)])
    df.insert(0, "Type", ["factorial"] * nf + ["axial"] * (2 * k) + ["center"] * center)
    return {"runs": df.to_dict(orient="records"), "alpha": a, "n_runs": len(df), "letters": L}


def box_behnken(k: int, center: int = 3) -> dict:
    if k < 3:
        raise ValueError("Box-Behnken needs at least 3 factors.")
    rows = []
    for i, j in itertools.combinations(range(k), 2):
        for a, b in itertools.product((-1, 1), repeat=2):
            v = [0] * k
            v[i], v[j] = a, b
            rows.append(v)
    rows += [[0] * k for _ in range(center)]
    df = pd.DataFrame(rows, columns=[f"x{i + 1}" for i in range(k)])
    return {"runs": df.to_dict(orient="records"), "n_runs": len(df)}


def _quad_X(X: np.ndarray):
    n, k = X.shape
    cols, names = [np.ones(n)], ["Intercept"]
    for i in range(k):
        cols.append(X[:, i]); names.append(f"x{i + 1}")
    for i in range(k):
        cols.append(X[:, i] ** 2); names.append(f"x{i + 1}²")
    for i, j in itertools.combinations(range(k), 2):
        cols.append(X[:, i] * X[:, j]); names.append(f"x{i + 1}x{j + 1}")
    return np.column_stack(cols), names


def fit_quadratic(data, xcols: list[str], response: str) -> dict:
    df = pd.DataFrame(data).copy()
    df = df.dropna(subset=[response])
    X = df[xcols].astype(float).values
    y = df[response].astype(float).values
    k = len(xcols)
    Q, names = _quad_X(X)
    m = sm.OLS(y, Q).fit()
    b = m.params[1:k + 1]
    B = np.zeros((k, k))
    for i in range(k):
        B[i, i] = m.params[1 + k + i]
    idx = 1 + 2 * k
    for i, j in itertools.combinations(range(k), 2):
        B[i, j] = B[j, i] = m.params[idx] / 2
        idx += 1
    # sequential ANOVA: linear, quadratic (pure + interaction), residual, lack of fit, pure error
    def ssr(cols):
        mm = sm.OLS(y, Q[:, cols]).fit()
        return mm.ssr
    ss0 = ssr([0])
    lin = list(range(0, k + 1))
    ss_lin = ss0 - ssr(lin)
    inter_cols = list(range(1 + 2 * k, Q.shape[1]))
    ss_int = ssr(lin) - ssr(lin + inter_cols)
    ss_sq = ssr(lin + inter_cols) - m.ssr
    dfe = int(m.df_resid)
    mse = m.ssr / dfe if dfe else float("nan")
    tab = [["Linear", ss_lin, k], ["Interaction (2FI)", ss_int, len(inter_cols)], ["Square", ss_sq, k]]
    out_tab = []
    for name, ss, d in tab:
        F = (ss / d) / mse if d and dfe else None
        out_tab.append([name, ss, d, ss / d if d else None, F, float(stats.f.sf(F, d, dfe)) if F else None])
    # lack of fit vs pure error (replicated points)
    key = pd.Series([tuple(r) for r in X.round(6)])
    grp = pd.DataFrame({"k": key, "y": y}).groupby("k")["y"]
    ss_pe = float(((y - grp.transform("mean").values) ** 2).sum())
    df_pe = int(len(y) - grp.ngroups)
    ss_lof, df_lof = m.ssr - ss_pe, dfe - df_pe
    out_tab.append(["Residual", m.ssr, dfe, mse, None, None])
    if df_pe > 0 and df_lof > 0:
        Fl = (ss_lof / df_lof) / (ss_pe / df_pe)
        out_tab.append(["  Lack of fit", ss_lof, df_lof, ss_lof / df_lof, Fl, float(stats.f.sf(Fl, df_lof, df_pe))])
        out_tab.append(["  Pure error", ss_pe, df_pe, ss_pe / df_pe, None, None])
    # stationary point & canonical analysis
    try:
        xs = -0.5 * np.linalg.solve(B, b)
        ys = float(m.params[0] + 0.5 * xs @ b)
        ev = np.linalg.eigvalsh(B)
        nature = "maximum" if (ev < 0).all() else "minimum" if (ev > 0).all() else "saddle point"
    except np.linalg.LinAlgError:
        xs, ys, ev, nature = None, None, None, "undetermined (singular B)"
    coef = [[n, m.params[i], m.bse[i], m.tvalues[i], float(m.pvalues[i])] for i, n in enumerate(names)]
    return {"coefficients": coef, "anova": out_tab, "r2": m.rsquared, "r2_adj": m.rsquared_adj,
            "stationary_point": None if xs is None else xs.tolist(), "y_stationary": ys,
            "eigenvalues": None if ev is None else ev.tolist(), "nature": nature, "b": b.tolist(), "B": B.tolist(),
            "b0": float(m.params[0]), "xcols": xcols}


def surface_grid(fit: dict, i: int = 0, j: int = 1, hold=None, lo: float = -2, hi: float = 2, n: int = 41) -> dict:
    k = len(fit["b"])
    hold = hold or [0.0] * k
    g = np.linspace(lo, hi, n)
    b0, b, B = fit["b0"], np.array(fit["b"]), np.array(fit["B"])
    Z = np.zeros((n, n))
    for a, xi in enumerate(g):
        for c, xj in enumerate(g):
            x = np.array(hold, float)
            x[i], x[j] = xi, xj
            Z[c, a] = b0 + x @ b + x @ B @ x
    return {"x": g.tolist(), "y": g.tolist(), "z": Z.tolist()}


def desirability(value: float, goal: str, low: float, high: float, target: float | None = None, s: float = 1.0) -> float:
    if goal == "max":
        return float(np.clip((value - low) / (high - low), 0, 1) ** s)
    if goal == "min":
        return float(np.clip((high - value) / (high - low), 0, 1) ** s)
    t = target if target is not None else (low + high) / 2
    if value < low or value > high:
        return 0.0
    return float(((value - low) / (t - low)) ** s if value <= t else ((high - value) / (high - t)) ** s)


def overall_desirability(fits: list[dict], goals: list[dict], lo=-1.5, hi=1.5, n=31, i=0, j=1) -> dict:
    g = np.linspace(lo, hi, n)
    best = (-1, None)
    D = np.zeros((n, n))
    k = len(fits[0]["b"])
    for a, xi in enumerate(g):
        for c, xj in enumerate(g):
            x = np.zeros(k)
            x[i], x[j] = xi, xj
            ds = []
            for f, gl in zip(fits, goals):
                v = f["b0"] + x @ np.array(f["b"]) + x @ np.array(f["B"]) @ x
                ds.append(desirability(v, gl["goal"], gl["low"], gl["high"], gl.get("target")))
            Dv = float(np.prod(ds) ** (1 / len(ds)))
            D[c, a] = Dv
            if Dv > best[0]:
                best = (Dv, x.tolist())
    return {"x": g.tolist(), "y": g.tolist(), "z": D.tolist(), "best_D": best[0], "best_x": best[1]}
