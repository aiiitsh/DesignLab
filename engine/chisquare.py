"""Lane C: χ² test of independence (Fisher's exact for small 2×2 tables)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from . import plots
from .common import Result, band_w, fmt_num, fmt_p, fmt_unit, normalize_labels, p_eq, to_frame


def chisquare(data, roles: dict, options: dict | None = None) -> dict:
    opt = options or {}
    df = to_frame(data)
    r_var = roles.get("row") or (roles.get("factors_between") or [None])[0]
    c_var = roles.get("col") or roles.get("dv")
    w_var = roles.get("counts")
    alpha = float(opt.get("alpha", 0.05))
    sub = df[[r_var, c_var] + ([w_var] if w_var else [])].copy()
    sub[r_var] = normalize_labels(sub[r_var])
    sub[c_var] = normalize_labels(sub[c_var])
    sub = sub.dropna()
    if w_var:
        obs = sub.pivot_table(index=r_var, columns=c_var, values=w_var, aggfunc="sum", fill_value=0)
    else:
        obs = pd.crosstab(sub[r_var], sub[c_var])
    R = Result("chisquare", f"χ² test of independence: {r_var} × {c_var}")
    for var, ax in ((r_var, obs.index), (c_var, obs.columns)):
        if len(ax) < 2:
            only = ax[0] if len(ax) else "–"
            raise ValueError(f"'{var}' has no variation (every case is '{only}'), so the χ² test cannot be run. "
                             "Choose a variable with at least two observed categories.")
    O = obs.values.astype(float)
    n = O.sum()
    chi2, p, dof, E = stats.chi2_contingency(O, correction=False)
    g2, gp, _, _ = stats.chi2_contingency(O, correction=False, lambda_="log-likelihood")
    rows = [["Pearson χ²", chi2, dof, fmt_p(p)], ["Likelihood ratio", g2, dof, fmt_p(gp)]]
    k = min(O.shape)
    V = math.sqrt(chi2 / (n * (k - 1)))
    small = (E < 5).sum()
    is22 = O.shape == (2, 2)
    fisher = None
    if is22:
        cc, cp, _, _ = stats.chi2_contingency(O, correction=True)
        rows.insert(1, ["χ² continuity correction", cc, dof, fmt_p(cp)])
        orr, fp = stats.fisher_exact(O)
        fisher = (orr, fp)
        rows.append(["Fisher's exact test", None, None, fmt_p(fp)])
    R.table("Contingency Tables – observed", [f"{r_var} \\ {c_var}", *map(str, obs.columns), "Total"],
            [[str(i), *O[j].tolist(), O[j].sum()] for j, i in enumerate(obs.index)] +
            [["Total", *O.sum(axis=0).tolist(), n]], section="descriptives")
    R.table("Expected counts", [f"{r_var} \\ {c_var}", *map(str, obs.columns)],
            [[str(i), *E[j].tolist()] for j, i in enumerate(obs.index)], section="descriptives")
    R.table("Chi-Squared Tests", ["", "Value", "df", "p"], rows, [f"N = {int(n)}"])
    rs = O.sum(axis=1, keepdims=True) / n
    cs = O.sum(axis=0, keepdims=True) / n
    adj = (O - E) / np.sqrt(E * (1 - rs) * (1 - cs))
    R.table("Standardized (adjusted) residuals", [f"{r_var} \\ {c_var}", *map(str, obs.columns)],
            [[str(i), *adj[j].tolist()] for j, i in enumerate(obs.index)], ["|residual| > 1.96 → cell differs from "
                                                                              "independence."], section="followups")
    R.plots.append({"data": [{"type": "heatmap", "z": adj.tolist(), "x": list(map(str, obs.columns)),
                              "y": list(map(str, obs.index)), "colorscale": "RdBu", "reversescale": True, "zmid": 0}],
                    "layout": {"title": {"text": "Standardized residuals"}, "height": 300}})
    R.check("Expected counts ≥ 5", "Expected count", float(E.min()), None, small == 0,
            detail=f"{int(small)} cell(s) below 5")
    chosen = "pearson"
    if small and is22:
        chosen = "fisher"
        R.decide(f"{int(small)} expected count(s) < 5 in a 2×2 table → Fisher's exact test (course rule).",
                 switched=True, rule="expected", key="expected")
    elif small:
        R.decide(f"{int(small)} expected count(s) < 5. Fisher's exact test is only offered for 2×2 tables here; "
                 "interpret χ² with caution or merge categories.", switched=True, rule="expected")
    R.effect("Cramér's V", V, band_w(V))
    if is22:
        R.effect("Odds ratio", fisher[0], "")
    if chosen == "fisher":
        R.apa = (f"Because an expected count was below 5, Fisher's exact test was used to examine the association between "
                 f"{r_var} and {c_var}; it was {'' if fisher[1] < alpha else 'not '}significant, {p_eq(fisher[1])}, "
                 f"OR = {fmt_num(fisher[0], 2)}.")
    else:
        R.apa = (f"A chi-square test of independence was performed to examine the relation between {r_var} and {c_var}. "
                 f"The relation between these variables was {'' if p < alpha else 'not '}significant, "
                 f"χ²({dof}, *N* = {int(n)}) = {fmt_num(chi2)}, {p_eq(p)}, Cramér's *V* = {fmt_unit(V)}.")
    R.interpretation = "Look at the standardized residuals to see which cells drive the association."
    R.extra = {"chi2": chi2, "p": p, "df": dof, "V": V, "fisher": fisher}
    R.python_code = f'''import pandas as pd, scipy.stats as st
df = pd.read_csv("data.csv")
obs = pd.crosstab(df["{r_var}"], df["{c_var}"])
print(obs); print(st.chi2_contingency(obs, correction=False))
'''
    return R.to_dict()
