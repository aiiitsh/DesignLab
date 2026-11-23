"""Lane C: binary logistic regression (Enter / stepwise)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from .common import Result, fmt_df, fmt_num, fmt_p, fmt_unit, normalize_labels, p_eq, to_frame


def logistic(data, roles: dict, options: dict | None = None) -> dict:
    opt = options or {}
    df = to_frame(data)
    dv = roles["dv"]
    covs = roles.get("covariates") or []
    factors = roles.get("factors_between") or roles.get("factors") or []
    alpha = float(opt.get("alpha", 0.05))
    sub = df[[dv, *covs, *factors]].copy()
    sub[dv] = normalize_labels(sub[dv])
    n_miss = int(sub.isna().any(axis=1).sum())
    sub = sub.dropna().reset_index(drop=True)
    levels = sorted(sub[dv].astype(str).unique())
    R = Result("logistic", f"Binary logistic regression: {dv}")
    if len(levels) < 2:
        raise ValueError(f"The outcome '{dv}' has no variation (every case is '{levels[0] if levels else '–'}'), so a "
                         "logistic regression cannot be run.")
    if len(levels) > 2:
        raise ValueError(f"'{dv}' has {len(levels)} categories. Multinomial regression is not covered in SYDE 640.")
    event = str(opt.get("event", levels[1]))
    y = (sub[dv].astype(str) == event).astype(float)
    if n_miss:
        R.warnings.append(f"{n_miss} case(s) with missing values were excluded.")
    X = pd.DataFrame(index=sub.index)
    for c in covs:
        X[c] = pd.to_numeric(sub[c], errors="coerce")
    for f in factors:
        sub[f] = normalize_labels(sub[f])
        lv = sorted(sub[f].astype(str).unique())
        ref = str(opt.get("reference", {}).get(f, lv[0]))
        for l in lv:
            if l != ref:
                X[f"{f} ({l})"] = (sub[f].astype(str) == l).astype(float)
    Xc = sm.add_constant(X, has_constant="add")
    m1 = sm.Logit(y, Xc).fit(disp=0)
    m0 = sm.Logit(y, np.ones((len(y), 1))).fit(disp=0)
    n = len(y)
    dev0, dev1 = -2 * m0.llf, -2 * m1.llf
    chi = dev0 - dev1
    dfm = int(m1.df_model)
    pchi = float(stats.chi2.sf(chi, dfm))
    mcf = 1 - m1.llf / m0.llf
    cs = 1 - math.exp((2 / n) * (m0.llf - m1.llf))
    nag = cs / (1 - math.exp((2 / n) * m0.llf))
    ph = m1.predict(Xc)
    tjur = float(ph[y == 1].mean() - ph[y == 0].mean())
    R.table("Model Summary", ["Model", "Deviance", "AIC", "BIC", "df", "Δχ²", "p", "McFadden R²", "Nagelkerke R²",
                              "Tjur R²", "Cox & Snell R²"], [
        ["M₀", dev0, m0.aic, m0.bic, int(m0.df_resid), None, None, None, None, None, None],
        ["M₁", dev1, m1.aic, m1.bic, int(m1.df_resid), chi, fmt_p(pchi), mcf, nag, tjur, cs]])
    ci = m1.conf_int()
    rows = []
    for name in m1.params.index:
        b, se, z = m1.params[name], m1.bse[name], m1.tvalues[name]
        rows.append(["(Intercept)" if name == "const" else name, b, se, math.exp(b), math.exp(ci.loc[name, 0]),
                     math.exp(ci.loc[name, 1]), z, z * z, 1, fmt_p(m1.pvalues[name])])
    R.table("Coefficients", ["", "Estimate", "SE", "Odds Ratio", "OR 95% CI low", "OR 95% CI high", "z", "Wald", "df",
                             "p"], rows, [f"'{event}' is the modelled event (Y = 1)."])
    R.table("M₀ coefficients", ["", "Estimate", "SE", "z", "p"],
            [["(Intercept)", m0.params.iloc[0], m0.bse.iloc[0], m0.tvalues.iloc[0], fmt_p(m0.pvalues.iloc[0])]])
    pred = (ph >= 0.5).astype(int)
    cm = pd.crosstab(y.astype(int), pred).reindex(index=[0, 1], columns=[0, 1], fill_value=0)
    acc = float((pred == y).mean())
    R.table("Confusion matrix (cutoff 0.5)", ["Observed", f"Predicted not {event}", f"Predicted {event}", "% correct"], [
        [f"not {event}", int(cm.loc[0, 0]), int(cm.loc[0, 1]), 100 * cm.loc[0, 0] / max(cm.loc[0].sum(), 1)],
        [event, int(cm.loc[1, 0]), int(cm.loc[1, 1]), 100 * cm.loc[1, 1] / max(cm.loc[1].sum(), 1)],
        ["Overall", None, None, 100 * acc]], section="followups")
    if len(X.columns) == 1 and X.columns[0] in covs:
        c = X.columns[0]
        xs = np.linspace(X[c].min(), X[c].max(), 60)
        ps = m1.predict(sm.add_constant(pd.DataFrame({c: xs}), has_constant="add"))
        R.plots.append({"data": [{"type": "scatter", "mode": "lines", "x": xs.tolist(), "y": list(ps), "name": "P(Y=1)",
                                  "line": {"color": "#0d8a87"}},
                                 {"type": "scatter", "mode": "markers", "x": X[c].tolist(), "y": y.tolist(),
                                  "name": "data", "marker": {"opacity": .5}}],
                        "layout": {"title": {"text": "Predicted probability"}, "height": 320,
                                   "xaxis": {"title": {"text": c}}, "yaxis": {"title": {"text": f"P({event})"}}}})
    R.effect("Cox & Snell R²", cs)
    R.effect("Nagelkerke R²", nag)
    sig_preds = [r for r, name in zip(rows, m1.params.index) if name != "const" and m1.pvalues[name] < alpha]
    pred_txt = ""
    if sig_preds:
        r0 = sig_preds[0]
        names = [r[0] for r in sig_preds]
        pred_txt = (f"{'Only the' if len(sig_preds) == 1 and len(rows) > 2 else 'The'} {', '.join(names)} predictor"
                    f"{'s' if len(names) > 1 else ''} had a significant effect (*W*(1) = {fmt_num(r0[7])}, "
                    f"*p* {r0[9] if r0[9].startswith('<') else '= ' + r0[9]}). ")
    R.apa = (f"A binary logistic regression was conducted to predict {dv} ({event}) from "
             f"{', '.join(list(X.columns))}. {pred_txt}Overall, the regression model was "
             f"{'' if pchi < alpha else 'not '}significant (χ²({int(m1.df_resid)}) = {fmt_num(chi)}, {p_eq(pchi)}), with "
             f"*R*² = {fmt_unit(cs)} (Cox & Snell).")
    if sig_preds:
        r0 = sig_preds[0]
        R.apa += f" The odds of {event} for {r0[0]} are {r0[3]:.2f} times {'higher' if r0[3] > 1 else 'lower'}."
    R.interpretation = ("The odds ratio multiplies the odds, not the probability: OR = 3 does not mean the outcome is "
                        "three times as likely.")
    R.extra = {"b": m1.params.to_dict(), "se": m1.bse.to_dict(), "dev0": dev0, "dev1": dev1, "chi2": chi, "p": pchi,
               "cox_snell": cs, "nagelkerke": nag, "mcfadden": mcf, "b0_null": float(m0.params.iloc[0]),
               "wald": {k: float(v ** 2) for k, v in m1.tvalues.items()}, "p_coef": m1.pvalues.to_dict()}
    R.python_code = f'''import pandas as pd, statsmodels.api as sm
df = pd.read_csv("data.csv").dropna()
y = (df["{dv}"].astype(str).str.strip().str.title() == "{event}").astype(int)
X = sm.add_constant(pd.get_dummies(df[{list(covs + factors)!r}], drop_first=True, dtype=float))
m = sm.Logit(y, X).fit()
print(m.summary()); import numpy as np; print("odds ratios", np.exp(m.params))
'''
    return R.to_dict()
