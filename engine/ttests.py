"""Lane A: independent and paired t-tests with the course fallback rules.

Rules (Meeting 4/5):
* normality (Shapiro-Wilk per group / on differences) p < .05 -> Mann-Whitney U / Wilcoxon
* equal variances (Levene, mean-centred) p < .05 -> Welch
* when both fail, the normality rule takes precedence (Mann-Whitney is primary),
  and the Welch result is still shown in the decision log (docs/DECISIONS.md).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from . import plots
from .assumptions import levene, shapiro
from .common import (Result, band_d, band_r, describe, fmt_df, fmt_num, fmt_p, fmt_unit, level_order,
                     p_eq, to_frame)
from .effect_sizes import cohen_d_ind, cohen_dz


def _tails(opt: dict) -> str:
    t = opt.get("tails", "two")
    return {"two": "two-sided", "greater": "greater", "less": "less"}.get(t, "two-sided")


def _one_sided_p(p_two: float, stat: float, alt: str) -> float:
    if alt == "two-sided":
        return p_two
    right_way = (stat > 0) if alt == "greater" else (stat < 0)
    return p_two / 2 if right_way else 1 - p_two / 2


def _desc(x: float, dg: int) -> str:
    return fmt_num(x, dg)


def _label(levels_lab: dict, lvl) -> str:
    return str(levels_lab.get(str(lvl), lvl))


def _with_mdn(label: str, mdn: float) -> str:
    m = fmt_num(mdn, 2).rstrip("0").rstrip(".") if abs(mdn - round(mdn)) > 1e-9 else str(int(round(mdn)))
    if label.endswith(")"):
        return f"{label[:-1]}; *Mdn* = {m})"
    return f"{label} (*Mdn* = {m})"


# ----------------------------------------------------------------------------------- independent
def ttest_ind(data, roles: dict, options: dict | None = None) -> dict:
    opt = options or {}
    df = to_frame(data)
    dv = roles["dv"]
    grp = (roles.get("factors_between") or [roles.get("group")])[0]
    alpha = float(opt.get("alpha", 0.05))
    alt = _tails(opt)
    dg = int(opt.get("desc_digits", 2))
    labels = opt.get("level_labels", {})  # {"A": "limited-choice (6 items)"}
    short = opt.get("level_short", {})    # {"B": "extensive choice"}
    dv_label = opt.get("dv_label", dv)
    force = opt.get("force")              # "student" | "welch" | "mannwhitney"

    sub = df[[dv, grp]].copy()
    sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
    n_missing = int(sub[dv].isna().sum() + sub[grp].isna().sum())
    sub = sub.dropna()
    levels = opt.get("order") or level_order(sub[grp])
    levels = [l for l in levels if l in set(sub[grp])] if opt.get("order") else levels
    if len(levels) != 2:
        raise ValueError(f"The grouping variable '{grp}' must have exactly 2 levels (found {len(levels)}).")
    A, B = levels
    a = sub.loc[sub[grp] == A, dv].astype(float).values
    b = sub.loc[sub[grp] == B, dv].astype(float).values
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Each group needs at least 2 values.")

    R = Result("ttest_ind", f"Independent samples t-test: {dv_label} by {grp}")
    if n_missing:
        R.warnings.append(f"{n_missing} case(s) with a missing value on {dv} or {grp} were excluded (listwise).")
        R.decide(f"{n_missing} missing value(s) excluded from the analysis of {dv}.", rule="listwise deletion")

    # descriptives
    da, db = describe(a), describe(b)
    rows = []
    for lvl, d in ((A, da), (B, db)):
        rows.append([str(lvl), d["N"], d["Mean"], d["SD"], d["SE"], d["Median"], d["Min"], d["Max"],
                     d["CI low"], d["CI high"]])
    R.table("Descriptives", [grp, "N", "Mean", "SD", "SE", "Median", "Min", "Max", "95% CI low", "95% CI high"],
            rows, section="descriptives")
    R.plots.append(plots.boxplot({str(A): a, str(B): b}, f"{dv_label} by {grp}", dv))

    # assumptions
    swa, swb = shapiro(a), shapiro(b)
    lev = levene(a, b)
    normal_ok = not ((swa[1] < alpha) or (swb[1] < alpha))
    var_ok = not (lev[1] < alpha)
    R.check(f"Normality ({A})", "Shapiro-Wilk", swa[0], swa[1], not swa[1] < alpha)
    R.check(f"Normality ({B})", "Shapiro-Wilk", swb[0], swb[1], not swb[1] < alpha)
    R.check("Equality of variances", "Levene (mean)", lev[0], lev[1], var_ok, df=[lev[2], lev[3]])
    R.table("Test of Normality (Shapiro-Wilk)", ["Group", "W", "p"],
            [[str(A), swa[0], fmt_p(swa[1])], [str(B), swb[0], fmt_p(swb[1])]],
            ["Significant results suggest a deviation from normality."], section="assumptions")
    R.table("Test of Equality of Variances (Levene's)", ["F", "df1", "df2", "p"],
            [[lev[0], lev[2], lev[3], fmt_p(lev[1])]], section="assumptions")
    R.plots.append(plots.qqplot(a, f"Q-Q {A}"))
    R.plots.append(plots.qqplot(b, f"Q-Q {B}"))

    # all three tests
    st_ = stats.ttest_ind(a, b, equal_var=True)
    we = stats.ttest_ind(a, b, equal_var=False)
    st_p = _one_sided_p(st_.pvalue, st_.statistic, alt)
    we_p = _one_sided_p(we.pvalue, we.statistic, alt)
    mw = stats.mannwhitneyu(a, b, alternative=alt, use_continuity=True)
    U = float(mw.statistic)
    rrb = 2 * U / (len(a) * len(b)) - 1  # positive when A tends to be larger than B
    dp = cohen_d_ind(a, b, pooled=True)
    dw = cohen_d_ind(a, b, pooled=False)

    # decide
    if not normal_ok:
        chosen = "mannwhitney"
        which = ", ".join(str(l) for l, s in ((A, swa), (B, swb)) if s[1] < alpha)
        R.decide(f"Shapiro-Wilk p < .05 in group {which} → switched to Mann-Whitney U (course rule, Meeting 4).",
                 switched=True, rule="normality", key="normality")
        if not var_ok:
            R.decide(f"Levene p = {fmt_p(lev[1])} < .05 as well → Welch would be t({fmt_df(we.df)}) = "
                     f"{fmt_num(we.statistic)}, p = {fmt_p(we_p)}. Both assumptions fail, so the normality rule "
                     "takes precedence and Mann-Whitney is the primary test.", switched=True, rule="precedence",
                     key="variance")
    elif not var_ok:
        chosen = "welch"
        R.decide(f"Levene p = {fmt_p(lev[1])} < .05 → switched to Welch's t-test (course rule, Meeting 4).",
                 switched=True, rule="variance", key="variance")
    else:
        chosen = "student"
        R.decide("Both assumptions met (Shapiro-Wilk and Levene p > .05) → Student's t-test.")
    if force and force != chosen:
        R.decide(f"User override: {force} reported instead of {chosen}.", switched=True, rule="override", key="override")
        chosen = force

    R.table("Independent Samples T-Test", ["Test", "Statistic", "df", "p", "Effect size", "Effect size type"], [
        ["Student", st_.statistic, len(a) + len(b) - 2, fmt_p(st_p), dp["d"], "Cohen's d"],
        ["Welch", we.statistic, we.df, fmt_p(we_p), dw["d"], "Cohen's d"],
        ["Mann-Whitney", U, None, fmt_p(mw.pvalue), rrb, "Rank-biserial r"],
    ], [f"Direction: {A} − {B}. Alternative: {alt}.", "Primary test: " +
        {"student": "Student", "welch": "Welch", "mannwhitney": "Mann-Whitney"}[chosen]])

    R.effect("Cohen's d (pooled SD)", dp["d"], band_d(dp["d"]), dp["ci"], note=f"{A} − {B}")
    if chosen == "welch":
        R.effect("Cohen's d (average SD, Welch)", dw["d"], band_d(dw["d"]), dw["ci"])
    R.effect("Rank-biserial r", rrb, band_r(rrb), note=f"positive = {A} tends higher")
    R.effect("Hedges' g", dp["g"], band_d(dp["g"]))

    # APA
    la, lb = _label(labels, A), _label(labels, B)
    dvl = dv_label
    if chosen == "mannwhitney":
        p = mw.pvalue
        hi = A if np.median(a) > np.median(b) or (np.median(a) == np.median(b) and rrb > 0) else B
        sig = p < alpha
        intro = (f"A Mann-Whitney U test was conducted to compare {dvl} between the "
                 f"{_with_mdn(la, np.median(a))} and {_with_mdn(lb, np.median(b))} groups.")
        stat = f"*U* = {fmt_num(U, 1)}, {p_eq(p)}, *r* = {fmt_unit(rrb, 2)}"
        if sig:
            hs = short.get(str(hi), _label(labels, hi))
            body = f" {dvl[0].upper() + dvl[1:]} was significantly higher with {hs}, {stat}."
        else:
            body = f" There was no significant difference between the groups, {stat}."
        R.apa = intro + body
        R.interpretation = (f"{'Significant' if sig else 'No significant'} difference in {dvl}"
                            + (f": the {short.get(str(hi), hi)} group scored higher." if sig else "."))
        primary = {"test": "Mann-Whitney U", "U": U, "p": p, "r": rrb}
    else:
        t = st_ if chosen == "student" else we
        p = st_p if chosen == "student" else we_p
        dfv = len(a) + len(b) - 2 if chosen == "student" else we.df
        d = dp if chosen == "student" else dw
        pre = ""
        if chosen == "welch":
            pre = (f"Since Levene's test for equality of variances was significant, *F*({lev[2]}, {lev[3]}) = "
                   f"{fmt_num(lev[0])}, {p_eq(lev[1])}, Welch's t-test was used. ")
        sig = p < alpha
        R.apa = (f"{pre}An independent samples t-test was conducted to compare {dvl} in the {la} and {lb} groups. "
                 f"There was {'a' if sig else 'no'} significant difference in the scores for the {la} group "
                 f"(*M* = {_desc(a.mean(), dg)}, *SD* = {_desc(a.std(ddof=1), dg)}) and the {lb} group "
                 f"(*M* = {_desc(b.mean(), dg)}, *SD* = {_desc(b.std(ddof=1), dg)}); "
                 f"*t*({fmt_df(dfv)}) = {fmt_num(t.statistic)}, {p_eq(p)}, *d* = {fmt_num(d['d'])}.")
        R.interpretation = (f"{'Significant' if sig else 'No significant'} difference; the effect is "
                            f"{band_d(d['d'])} (d = {fmt_num(d['d'])}).")
        primary = {"test": "Welch t" if chosen == "welch" else "Student t", "t": t.statistic, "df": dfv, "p": p,
                   "d": d["d"]}
    R.extra = {"primary": primary, "chosen": chosen, "groups": [str(A), str(B)], "n": [len(a), len(b)],
               "student": {"t": st_.statistic, "df": len(a) + len(b) - 2, "p": st_p},
               "welch": {"t": we.statistic, "df": we.df, "p": we_p},
               "mannwhitney": {"U": U, "p": mw.pvalue, "r_rb": rrb},
               "shapiro": [swa[1], swb[1]], "levene_p": lev[1], "d": dp["d"],
               "means": [a.mean(), b.mean()], "sds": [a.std(ddof=1), b.std(ddof=1)]}
    R.python_code = f'''import pandas as pd, numpy as np, scipy.stats as st
df = pd.read_csv("data.csv")
a = df.loc[df["{grp}"] == {A!r}, "{dv}"].dropna()
b = df.loc[df["{grp}"] == {B!r}, "{dv}"].dropna()
print("Shapiro A", st.shapiro(a), "Shapiro B", st.shapiro(b))
print("Levene", st.levene(a, b, center="mean"))
print("Student", st.ttest_ind(a, b, alternative="{alt}"))
print("Welch  ", st.ttest_ind(a, b, equal_var=False, alternative="{alt}"))
mw = st.mannwhitneyu(a, b, alternative="{alt}")
print("Mann-Whitney", mw, "rank-biserial r =", 2 * mw.statistic / (len(a) * len(b)) - 1)
sp = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
print("Cohen d =", (a.mean() - b.mean()) / sp)
'''
    return R.to_dict()


# ----------------------------------------------------------------------------------- paired
def ttest_paired(data, roles: dict, options: dict | None = None) -> dict:
    opt = options or {}
    df = to_frame(data)
    c1, c2 = roles["within_cols"][:2]
    alpha = float(opt.get("alpha", 0.05))
    alt = _tails(opt)
    dg = int(opt.get("desc_digits", 2))
    dv_label = opt.get("dv_label", "the scores")
    sub = df[[c1, c2]].apply(pd.to_numeric, errors="coerce")
    n_missing = int(sub.isna().any(axis=1).sum())
    sub = sub.dropna()
    x, y = sub[c1].values.astype(float), sub[c2].values.astype(float)
    diff = x - y
    R = Result("ttest_paired", f"Paired samples t-test: {c1} vs {c2}")
    if n_missing:
        R.warnings.append(f"{n_missing} participant(s) with a missing measurement were excluded.")
    rows = [[c, *[describe(v)[k] for k in ("N", "Mean", "SD", "SE", "Median", "Min", "Max", "CI low", "CI high")]]
            for c, v in ((c1, x), (c2, y))]
    R.table("Descriptives", ["Condition", "N", "Mean", "SD", "SE", "Median", "Min", "Max", "95% CI low",
                             "95% CI high"], rows, section="descriptives")
    R.plots.append(plots.boxplot({c1: x, c2: y}, f"{c1} vs {c2}"))
    sw = shapiro(diff)
    ok = not sw[1] < alpha
    R.check("Normality of differences", "Shapiro-Wilk", sw[0], sw[1], ok)
    R.table("Test of Normality (Shapiro-Wilk)", ["Pair", "W", "p"], [[f"{c1} − {c2}", sw[0], fmt_p(sw[1])]],
            section="assumptions")
    R.plots.append(plots.qqplot(diff, "Q-Q of differences"))
    t = stats.ttest_rel(x, y)
    tp = _one_sided_p(t.pvalue, t.statistic, alt)
    nz = diff[diff != 0]
    ranks = stats.rankdata(np.abs(nz))
    wplus = float(ranks[nz > 0].sum())
    wminus = float(ranks[nz < 0].sum())
    wx = stats.wilcoxon(x, y, alternative=alt) if len(nz) else None
    wp = float(wx.pvalue) if wx is not None else float("nan")
    rrb = (wplus - wminus) / (wplus + wminus) if (wplus + wminus) else float("nan")
    dz = cohen_dz(diff)
    chosen = "student" if ok else "wilcoxon"
    if not ok:
        R.decide(f"Shapiro-Wilk on the differences p = {fmt_p(sw[1])} < .05 → switched to the Wilcoxon signed-rank "
                 "test (course rule, Meeting 5).", switched=True, rule="normality", key="normality")
    else:
        R.decide("Differences are approximately normal → paired t-test.")
    if opt.get("force") and opt["force"] != chosen:
        R.decide(f"User override: {opt['force']} reported.", switched=True, rule="override")
        chosen = opt["force"]
    R.table("Paired Samples T-Test", ["Test", "Statistic", "df", "p", "Effect size", "Type"], [
        ["Student", t.statistic, len(diff) - 1, fmt_p(tp), dz["d"], "Cohen's d_z"],
        ["Wilcoxon", wplus, None, fmt_p(wp), rrb, "Matched rank-biserial"]],
        [f"Direction: {c1} − {c2}."])
    R.effect("Cohen's d_z", dz["d"], band_d(dz["d"]), dz["ci"])
    R.effect("Matched rank-biserial r", rrb, band_r(rrb))
    if chosen == "student":
        sig = tp < alpha
        R.apa = (f"A paired samples t-test was conducted to compare {dv_label} in the {c1} and {c2} conditions. "
                 f"There was {'a' if sig else 'no'} significant difference between {c1} (*M* = {fmt_num(x.mean(), dg)}, "
                 f"*SD* = {fmt_num(x.std(ddof=1), dg)}) and {c2} (*M* = {fmt_num(y.mean(), dg)}, "
                 f"*SD* = {fmt_num(y.std(ddof=1), dg)}); *t*({len(diff) - 1}) = {fmt_num(t.statistic)}, {p_eq(tp)}, "
                 f"*d* = {fmt_num(dz['d'])}.")
    else:
        sig = wp < alpha
        R.apa = (f"Because the differences were not normally distributed (Shapiro-Wilk {p_eq(sw[1])}), a Wilcoxon "
                 f"signed-rank test was conducted to compare {c1} (*Mdn* = {fmt_num(np.median(x), dg)}) and {c2} "
                 f"(*Mdn* = {fmt_num(np.median(y), dg)}). The difference was {'' if sig else 'not '}significant, "
                 f"*W* = {fmt_num(wplus, 1)}, {p_eq(wp)}, *r* = {fmt_unit(rrb, 2)}.")
    R.interpretation = f"{'Significant' if sig else 'No significant'} difference between {c1} and {c2}."
    R.extra = {"chosen": chosen, "t": t.statistic, "p": tp, "dz": dz["d"], "W": wplus, "wilcoxon_p": wp}
    R.python_code = f'''import pandas as pd, scipy.stats as st
df = pd.read_csv("data.csv").dropna(subset=["{c1}", "{c2}"])
d = df["{c1}"] - df["{c2}"]
print("Shapiro on differences", st.shapiro(d))
print(st.ttest_rel(df["{c1}"], df["{c2}"]))
print(st.wilcoxon(df["{c1}"], df["{c2}"]))
print("d_z =", d.mean() / d.std())
'''
    return R.to_dict()
