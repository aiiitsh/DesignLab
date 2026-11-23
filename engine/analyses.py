"""Registry of analyses + helpers used by the API (descriptives, multiple-DV batches)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from . import plots
from .anova import anova_factorial, anova_oneway
from .chisquare import chisquare
from .common import Result, describe, familywise, fmt_p, to_frame
from .logistic import logistic
from .regression import regression
from .rm_anova import anova_rm
from .ttests import ttest_ind, ttest_paired


def descriptives(data, roles: dict, options: dict | None = None) -> dict:
    df = to_frame(data)
    dvs = roles.get("dvs") or [roles["dv"]]
    split = (roles.get("factors_between") or [None])[0]
    R = Result("descriptives", "Descriptive statistics")
    rows = []
    for dv in dvs:
        x = pd.to_numeric(df[dv], errors="coerce")
        if split:
            for lvl, g in x.groupby(df[split]):
                d = describe(g)
                rows.append([dv, str(lvl), d["N"], int(g.isna().sum()), d["Mean"], d["SD"], d["SE"], d["Median"],
                             d["Q1"], d["Q3"], d["Min"], d["Max"], d["CI low"], d["CI high"]])
            R.plots.append(plots.boxplot({str(l): g.dropna() for l, g in x.groupby(df[split])}, dv, dv))
        else:
            d = describe(x)
            rows.append([dv, "", d["N"], int(x.isna().sum()), d["Mean"], d["SD"], d["SE"], d["Median"], d["Q1"],
                         d["Q3"], d["Min"], d["Max"], d["CI low"], d["CI high"]])
    R.table("Descriptive Statistics", ["Variable", split or "", "Valid", "Missing", "Mean", "SD", "SE", "Median", "Q1",
                                       "Q3", "Min", "Max", "95% CI low", "95% CI high"], rows, section="descriptives")
    if not split:
        R.plots.append(plots.boxplot({dv: pd.to_numeric(df[dv], errors="coerce").dropna() for dv in dvs},
                                     "Box plots"))
    return R.to_dict()


ANALYSES = {
    "descriptives": descriptives,
    "ttest_ind": ttest_ind,
    "ttest_paired": ttest_paired,
    "anova_oneway": anova_oneway,
    "anova_factorial": anova_factorial,
    "anova_rm1": anova_rm,
    "anova_rm": anova_rm,
    "anova_mixed": anova_rm,
    "regression": regression,
    "logistic": logistic,
    "chisquare": chisquare,
}

ANALYSIS_INFO = {
    "descriptives": {"name": "Descriptives", "lane": "A", "roles": ["dvs", "factors_between?"]},
    "ttest_ind": {"name": "Independent samples t-test", "lane": "A", "roles": ["dv", "factors_between:1"]},
    "ttest_paired": {"name": "Paired samples t-test", "lane": "A", "roles": ["within_cols:2"]},
    "anova_oneway": {"name": "One-way ANOVA", "lane": "A", "roles": ["dv", "factors_between:1"]},
    "anova_factorial": {"name": "Factorial ANOVA", "lane": "A", "roles": ["dv", "factors_between:2+"]},
    "anova_rm1": {"name": "One-way repeated measures ANOVA", "lane": "A", "roles": ["within_cols:3+"]},
    "anova_rm": {"name": "N-way repeated measures ANOVA", "lane": "A", "roles": ["within_cols", "within_factors"]},
    "anova_mixed": {"name": "Mixed ANOVA", "lane": "A", "roles": ["within_cols", "within_factors", "factors_between"]},
    "regression": {"name": "Linear regression", "lane": "B", "roles": ["dv", "covariates", "factors_between?"]},
    "logistic": {"name": "Binary logistic regression", "lane": "C", "roles": ["dv", "covariates", "factors_between?"]},
    "chisquare": {"name": "χ² test of independence", "lane": "C", "roles": ["row", "col", "counts?"]},
}


def run(analysis_id: str, data, roles: dict, options: dict | None = None) -> dict:
    if analysis_id not in ANALYSES:
        raise ValueError(f"Unknown analysis '{analysis_id}'.")
    return ANALYSES[analysis_id](data, roles, options or {})


def batch(analysis_id: str, data, roles: dict, dvs: list[str], options: dict | None = None,
          correction: str = "bonferroni") -> dict:
    """Run the same test on several DVs and apply the familywise correction (Meeting 6)."""
    opt = options or {}
    alpha = float(opt.get("alpha", 0.05))
    results, ps = [], []
    for dv in dvs:
        r = run(analysis_id, data, {**roles, "dv": dv}, {**opt, "dv_label": opt.get("dv_labels", {}).get(dv, dv)})
        results.append(r)
        prim = r.get("extra", {}).get("primary") or {}
        ps.append(prim.get("p", r.get("extra", {}).get("p")))
    m = len(dvs)
    fw = familywise(m, alpha)
    valid = [p for p in ps if p is not None]
    holm = list(multipletests(valid, method="holm")[1]) if valid else []
    rows = []
    hi = iter(holm)
    for dv, r, p in zip(dvs, results, ps):
        prim = r.get("extra", {}).get("primary") or {}
        h = next(hi) if p is not None else None
        rows.append({"dv": dv, "test": prim.get("test"), "p": p, "p_fmt": fmt_p(p),
                     "sig_uncorrected": p is not None and p < alpha,
                     "sig_bonferroni": p is not None and p < alpha / m,
                     "p_holm": h, "sig_holm": h is not None and h < alpha})
    return {"results": results, "summary": rows, "m": m, "familywise_alpha": fw, "bonferroni_alpha": alpha / m,
            "warning": (f"{m} tests on the same participants: the chance of at least one false alarm is "
                        f"1 − .95^{m} = {fw:.2f}. Use Bonferroni (α = .05/{m} = {alpha / m:.4f}) or Holm."),
            "correction": correction}
