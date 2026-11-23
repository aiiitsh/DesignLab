"""Lane B: linear regression (enter, hierarchical blocks, forward, backward, stepwise)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from . import plots
from .assumptions import shapiro
from .common import Result, band_f2, fmt_df, fmt_num, fmt_p, fmt_unit, p_eq, to_frame


def _design(df: pd.DataFrame, covs: list[str], factors: list[str], refs: dict) -> tuple[pd.DataFrame, dict]:
    X = pd.DataFrame(index=df.index)
    groups = {}
    for c in covs:
        X[c] = pd.to_numeric(df[c], errors="coerce")
        groups[c] = [c]
    for f in factors:
        lv = sorted(df[f].dropna().astype(str).unique())
        ref = str(refs.get(f, lv[0]))
        cols = []
        for l in lv:
            if l == ref:
                continue
            name = f"{f} ({l})"
            X[name] = (df[f].astype(str) == l).astype(float)
            cols.append(name)
        groups[f] = cols
    return X, groups


def _fit(y, X, cols):
    Xc = sm.add_constant(X[cols], has_constant="add") if cols else pd.DataFrame({"const": np.ones(len(y))}, index=y.index)
    return sm.OLS(y, Xc).fit()


def _p_enter(y, X, cur_cols, add_cols):
    m0, m1 = _fit(y, X, cur_cols), _fit(y, X, cur_cols + add_cols)
    df1 = len(add_cols)
    F = ((m0.ssr - m1.ssr) / df1) / (m1.ssr / m1.df_resid)
    return float(stats.f.sf(F, df1, m1.df_resid))


def _select(y, X, groups, method, p_in=0.05, p_out=0.10):
    names = list(groups)
    steps = []
    if method == "backward":
        cur = names[:]
        while cur:
            ps = {n: _p_enter(y, X, sum((groups[c] for c in cur if c != n), []), groups[n]) for n in cur}
            worst = max(ps, key=ps.get)
            if ps[worst] > p_out:
                cur.remove(worst)
                steps.append(f"removed {worst} (p = {fmt_p(ps[worst])} > {p_out})")
            else:
                break
        return cur, steps
    cur = []
    while True:
        rest = [n for n in names if n not in cur]
        if not rest:
            break
        cols = sum((groups[c] for c in cur), [])
        ps = {n: _p_enter(y, X, cols, groups[n]) for n in rest}
        best = min(ps, key=ps.get)
        if ps[best] >= p_in:
            break
        cur.append(best)
        steps.append(f"entered {best} (p = {fmt_p(ps[best])})")
        if method == "stepwise":
            changed = True
            while changed and len(cur) > 1:
                changed = False
                pr = {n: _p_enter(y, X, sum((groups[c] for c in cur if c != n), []), groups[n]) for n in cur}
                worst = max(pr, key=pr.get)
                if pr[worst] > p_out:
                    cur.remove(worst)
                    steps.append(f"removed {worst} (p = {fmt_p(pr[worst])})")
                    changed = True
    return cur, steps


def regression(data, roles: dict, options: dict | None = None) -> dict:
    opt = options or {}
    df = to_frame(data)
    dv = roles["dv"]
    covs = roles.get("covariates") or []
    factors = roles.get("factors_between") or roles.get("factors") or []
    method = opt.get("method", "enter")
    blocks = opt.get("blocks")  # list of lists of predictor names
    alpha = float(opt.get("alpha", 0.05))
    use = [dv, *covs, *factors]
    sub = df[use].copy()
    sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
    n_miss = int(sub.isna().any(axis=1).sum())
    sub = sub.dropna().reset_index(drop=True)
    y = sub[dv].astype(float)
    X, groups = _design(sub, covs, factors, opt.get("reference", {}))
    R = Result("regression", f"Linear regression: {dv}")
    if n_miss:
        R.warnings.append(f"{n_miss} case(s) with missing values were excluded (listwise).")

    # which predictors, in which models
    if method == "hierarchical" and blocks:
        model_sets, acc = [], []
        for b in blocks:
            acc = acc + [p for p in b if p in groups]
            model_sets.append(acc[:])
    elif method in ("forward", "backward", "stepwise"):
        chosen, steps = _select(y, X, groups, method, opt.get("p_enter", 0.05), opt.get("p_remove", 0.10))
        for s in steps:
            R.decide(f"{method.title()}: {s}", rule="entry")
        if not chosen:
            R.warnings.append("No predictor met the entry criterion; only the intercept model is reported.")
        model_sets = [chosen]
    else:
        model_sets = [list(groups)]
    model_sets = [[]] + model_sets  # H0 (intercept only), as JASP

    fits = [_fit(y, X, sum((groups[c] for c in ms), [])) for ms in model_sets]
    summ = []
    for i, (ms, m) in enumerate(zip(model_sets, fits)):
        r2 = m.rsquared if ms else 0.0
        row = [f"M{i}", ", ".join(ms) or "(intercept)", math.sqrt(max(r2, 0)), r2, m.rsquared_adj if ms else 0.0,
               math.sqrt(m.mse_resid)]
        if i > 0:
            prev = fits[i - 1]
            r2p = prev.rsquared if model_sets[i - 1] else 0.0
            df1 = int(m.df_model - (prev.df_model if model_sets[i - 1] else 0))
            df2 = int(m.df_resid)
            if df1 > 0:
                Fc = ((r2 - r2p) / df1) / ((1 - r2) / df2)
                row += [r2 - r2p, Fc, df1, df2, fmt_p(float(stats.f.sf(Fc, df1, df2)))]
            else:
                row += [0.0, None, 0, df2, None]
        else:
            row += [None, None, None, None, None]
        summ.append(row)
    R.table("Model Summary", ["Model", "Predictors", "R", "R²", "Adjusted R²", "RMSE", "R² Change", "F Change", "df1",
                              "df2", "p"], summ)
    final_set = model_sets[-1]
    m = fits[-1]
    anova_rows = []
    for i, (ms, mf) in enumerate(zip(model_sets, fits)):
        if not ms:
            continue
        anova_rows += [[f"M{i}", "Regression", mf.ess, mf.df_model, mf.ess / mf.df_model, mf.fvalue, fmt_p(mf.f_pvalue)],
                       ["", "Residual", mf.ssr, mf.df_resid, mf.mse_resid, None, None],
                       ["", "Total", mf.ess + mf.ssr, mf.df_model + mf.df_resid, None, None, None]]
    R.table("ANOVA", ["Model", "", "Sum of Squares", "df", "Mean Square", "F", "p"], anova_rows)

    cols = sum((groups[c] for c in final_set), [])
    coef_rows = []
    ci = m.conf_int()
    sdy = y.std(ddof=1)
    vif = {}
    if len(cols) > 1:
        for c in cols:
            others = [o for o in cols if o != c]
            r2c = sm.OLS(X[c], sm.add_constant(X[others])).fit().rsquared
            vif[c] = 1 / (1 - r2c) if r2c < 1 else float("inf")
    for name in m.params.index:
        b = m.params[name]
        if name == "const":
            coef_rows.append(["(Intercept)", b, m.bse[name], None, m.tvalues[name], fmt_p(m.pvalues[name]),
                              ci.loc[name, 0], ci.loc[name, 1], None, None])
        else:
            beta = b * X[name].std(ddof=1) / sdy
            v = vif.get(name, 1.0)
            coef_rows.append([name, b, m.bse[name], beta, m.tvalues[name], fmt_p(m.pvalues[name]), ci.loc[name, 0],
                              ci.loc[name, 1], 1 / v, v])
    R.table(f"Coefficients (M{len(model_sets) - 1})", ["", "Unstandardized B", "SE", "Standardized β", "t", "p",
                                                         "95% CI low", "95% CI high", "Tolerance", "VIF"], coef_rows)
    if any(v >= 10 for v in vif.values()):
        R.decide("VIF ≥ 10 for " + ", ".join(k for k, v in vif.items() if v >= 10) +
                 " → multicollinearity; consider dropping or combining predictors.", switched=True, rule="vif")
    # collinearity diagnostics
    if cols:
        Xd = sm.add_constant(X[cols]).values
        Xs = Xd / np.sqrt((Xd ** 2).sum(axis=0))
        ev, V = np.linalg.eigh(Xs.T @ Xs)
        order = np.argsort(ev)[::-1]
        ev, V = ev[order], V[:, order]
        phi = (V ** 2) / ev
        props = phi / phi.sum(axis=1, keepdims=True)
        crow = []
        for j in range(len(ev)):
            crow.append([j + 1, ev[j], math.sqrt(ev[0] / ev[j]), *props[:, j].tolist()])
        R.table("Collinearity Diagnostics", ["Dimension", "Eigenvalue", "Condition Index", "(Intercept)", *cols], crow,
                section="assumptions")

    # residual diagnostics
    infl = m.get_influence()
    std_res = infl.resid_studentized_internal
    cooks = infl.cooks_distance[0]
    sw = shapiro(m.resid)
    R.check("Normality of residuals", "Shapiro-Wilk", sw[0], sw[1], not sw[1] < alpha)
    pct = float((np.abs(std_res) > 2).mean() * 100)
    R.check("Standardized residuals beyond ±2", "count", pct, None, pct <= 5.0 + 1e-9,
            detail=f"{pct:.1f}% of cases (about 5% expected)")
    R.check("Influential cases (Cook's D > 1)", "Cook's D", float(cooks.max()), None, bool(cooks.max() <= 1))
    case_rows = [[i + 1, std_res[i], y.iloc[i], m.fittedvalues.iloc[i], m.resid.iloc[i], cooks[i]]
                 for i in range(len(y)) if abs(std_res[i]) > 2 or cooks[i] > 1]
    R.table("Casewise Diagnostics", ["Case", "Std. Residual", dv, "Predicted", "Residual", "Cook's Distance"], case_rows,
            ["Cases with |standardized residual| > 2 or Cook's D > 1."], section="assumptions")
    R.plots.append(plots.resid_fitted(m.fittedvalues.tolist(), m.resid.tolist()))
    R.plots.append(plots.qqplot(m.resid, "Q-Q plot of residuals"))
    if len(cols) == 1:
        xs = np.linspace(X[cols[0]].min(), X[cols[0]].max(), 50)
        pr = m.get_prediction(sm.add_constant(pd.DataFrame({cols[0]: xs}), has_constant="add")).summary_frame()
        R.plots.insert(0, plots.scatter_fit(X[cols[0]].tolist(), y.tolist(), cols[0], dv, xs.tolist(),
                                            pr["mean"].tolist(), pr["mean_ci_lower"].tolist(),
                                            pr["mean_ci_upper"].tolist()))
    if sw[1] < alpha:
        R.decide("Residuals are not normal. Suggestions (no automatic switch): transform the DV, add polynomial terms, "
                 "or use a GLM.", switched=True, rule="regression-normality")

    r2 = m.rsquared if final_set else 0
    f2 = r2 / (1 - r2) if r2 < 1 else float("inf")
    R.effect("f²", f2, band_f2(f2))
    R.effect("R²", r2, "")
    eq = f"{dv} = {fmt_num(m.params['const'])}"
    for name in m.params.index[1:]:
        b = m.params[name]
        eq += f" {'−' if b < 0 else '+'} {fmt_num(abs(b))} × {name}"
    R.extra = {"equation": eq, "r2": r2, "F": m.fvalue if final_set else None, "df": [m.df_model, m.df_resid],
               "p": m.f_pvalue if final_set else None, "params": m.params.to_dict(), "models": summ, "vif": vif}
    if final_set:
        sig = m.f_pvalue < alpha
        kind = "simple" if len(cols) == 1 else "multiple"
        R.apa = (f"A {kind} linear regression was conducted to predict {dv} from {', '.join(final_set)}. "
                 f"The model was {'' if sig else 'not '}significant, *F*({fmt_df(m.df_model)}, {fmt_df(m.df_resid)}) = "
                 f"{fmt_num(m.fvalue)}, {p_eq(m.f_pvalue)}, *R*² = {fmt_unit(r2)}. {eq}.")
        if method == "hierarchical" and len(model_sets) > 2:
            last = summ[-1]
            R.apa += (f" Adding the final block increased *R*² by {fmt_unit(last[6])}, *F* change({last[8]}, {last[9]}) = "
                      f"{fmt_num(last[7])}, *p* {last[10] if str(last[10]).startswith('<') else '= ' + str(last[10])}.")
        R.interpretation = (f"The predictors explain {r2 * 100:.1f}% of the variance in {dv} (f² = {fmt_num(f2)}, "
                            f"{band_f2(f2)}). B is in the DV's original units; β compares predictors.")
    plist = ", ".join(f'"{c}"' for c in cols)
    R.python_code = f'''import pandas as pd, statsmodels.api as sm
df = pd.read_csv("data.csv")
# factor predictors need k-1 dummy columns, e.g. pd.get_dummies(df["factor"], drop_first=True)
X = sm.add_constant(df[[{plist}]])
model = sm.OLS(df["{dv}"], X, missing="drop").fit()
print(model.summary())
'''
    return R.to_dict()
