"""Lane A: one-way and n-way between-subject ANOVA."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.anova import anova_lm

from . import plots
from .assumptions import levene, shapiro
from .common import (Result, band_eta, describe, fmt_df, fmt_num, fmt_p, fmt_unit, level_order, p_eq, to_frame)
from .effect_sizes import omega_sq
from .posthoc import contrast_rows, games_howell, pooled_pairwise

PH_COLS = ["Comparison", "Mean difference", "SE", "t", "df", "p (adj)"]


def _sort_levels(s: pd.Series, order=None):
    return list(order) if order else level_order(s)


# ======================================================================== one-way
def anova_oneway(data, roles: dict, options: dict | None = None) -> dict:
    opt = options or {}
    df = to_frame(data)
    dv = roles["dv"]
    grp = (roles.get("factors_between") or [roles.get("group")])[0]
    alpha = float(opt.get("alpha", 0.05))
    ph_method = opt.get("posthoc", "tukey")
    dv_label = opt.get("dv_label", dv)
    sub = df[[dv, grp]].copy()
    sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
    n_miss = int(sub.isna().any(axis=1).sum())
    sub = sub.dropna()
    levels = _sort_levels(sub[grp], opt.get("order"))
    groups = {l: sub.loc[sub[grp] == l, dv].astype(float).values for l in levels}
    k = len(levels)
    if k < 2:
        raise ValueError("Need at least 2 groups.")
    R = Result("anova_oneway", f"One-way ANOVA: {dv_label} by {grp}")
    if n_miss:
        R.warnings.append(f"{n_miss} case(s) with missing values were excluded.")
    small = [str(l) for l, g in groups.items() if len(g) < 2]
    if small:
        raise ValueError(f"Groups with fewer than 2 values: {', '.join(small)}")

    R.table("Descriptives", [grp, "N", "Mean", "SD", "SE", "Median", "95% CI low", "95% CI high"],
            [[str(l), *[describe(g)[c] for c in ("N", "Mean", "SD", "SE", "Median", "CI low", "CI high")]]
             for l, g in groups.items()], section="descriptives")
    R.plots.append(plots.boxplot({str(l): g for l, g in groups.items()}, f"{dv_label} by {grp}", dv))

    allv = np.concatenate(list(groups.values()))
    N = len(allv)
    gm = allv.mean()
    ssb = sum(len(g) * (g.mean() - gm) ** 2 for g in groups.values())
    ssw = sum(((g - g.mean()) ** 2).sum() for g in groups.values())
    sst = ssb + ssw
    dfb, dfw = k - 1, N - k
    msb, msw = ssb / dfb, ssw / dfw
    F = msb / msw
    p = float(stats.f.sf(F, dfb, dfw))
    eta = ssb / sst
    omega = omega_sq(ssb, dfb, msw, sst)

    # assumptions
    sw = {l: shapiro(g) for l, g in groups.items()}
    lev = levene(*groups.values())
    non_normal = [str(l) for l, s in sw.items() if s[1] < alpha]
    var_ok = not lev[1] < alpha
    for l, s in sw.items():
        R.check(f"Normality ({l})", "Shapiro-Wilk", s[0], s[1], not s[1] < alpha)
    R.check("Homogeneity of variances", "Levene (mean)", lev[0], lev[1], var_ok, df=[lev[2], lev[3]])
    R.table("Test of Equality of Variances (Levene's)", ["F", "df1", "df2", "p"],
            [[lev[0], lev[2], lev[3], fmt_p(lev[1])]], section="assumptions")
    R.table("Test of Normality (Shapiro-Wilk)", [grp, "W", "p"],
            [[str(l), s[0], fmt_p(s[1])] for l, s in sw.items()], section="assumptions")
    resid = np.concatenate([g - g.mean() for g in groups.values()])
    R.plots.append(plots.qqplot(resid, "Q-Q plot of residuals"))

    # Welch / Brown-Forsythe
    w = _welch_anova(groups)
    bf = _brown_forsythe(groups)
    kw = stats.kruskal(*groups.values())

    if non_normal and not opt.get("force"):
        chosen = "kruskal"
        R.decide(f"Shapiro-Wilk p < .05 in {', '.join(non_normal)} → switched to Kruskal-Wallis with Dunn's post hoc "
                 "(course rule, Meeting 6).", switched=True, rule="normality", key="normality")
        if not var_ok:
            R.decide(f"Levene p = {fmt_p(lev[1])} < .05 as well (Welch F({w['df1']}, {fmt_df(w['df2'])}) = "
                     f"{fmt_num(w['F'])}, p = {fmt_p(w['p'])}); normality rule takes precedence.", switched=True,
                     rule="precedence")
    elif not var_ok and not opt.get("force"):
        chosen = "welch"
        R.decide(f"Levene p = {fmt_p(lev[1])} < .05 → switched to Welch ANOVA with Games-Howell post hoc "
                 "(course rule, Meeting 6). Brown-Forsythe shown for reference.", switched=True, rule="variance",
                 key="variance")
    else:
        chosen = opt.get("force") or "classic"
        if opt.get("force"):
            R.decide(f"User override: {chosen} reported.", switched=True, rule="override")
        else:
            R.decide("Normality and equal variances met → classical one-way ANOVA.")

    R.table(f"ANOVA – {dv}", ["Cases", "Sum of Squares", "df", "Mean Square", "F", "p", "η²", "ω²"], [
        [grp, ssb, dfb, msb, F, fmt_p(p), eta, omega], ["Residuals", ssw, dfw, msw, None, None, None, None]])
    R.table("Homogeneity corrections", ["Correction", "F", "df1", "df2", "p"], [
        ["None", F, dfb, dfw, fmt_p(p)], ["Brown-Forsythe", bf["F"], bf["df1"], bf["df2"], fmt_p(bf["p"])],
        ["Welch", w["F"], w["df1"], w["df2"], fmt_p(w["p"])]])
    R.table("Kruskal-Wallis Test", ["Factor", "H", "df", "p"], [[grp, kw.statistic, k - 1, fmt_p(kw.pvalue)]])
    R.effect("η²", eta, band_eta(eta))
    R.effect("ω²", omega, band_eta(max(omega, 0)))

    means = {l: g.mean() for l, g in groups.items()}
    ns = {l: len(g) for l, g in groups.items()}
    # follow-ups
    if chosen == "welch":
        R.table("Post Hoc Comparisons – Games-Howell", PH_COLS, [r[:6] for r in games_howell(groups)],
                section="followups")
    elif chosen == "kruskal":
        import scikit_posthocs as sp
        adj = opt.get("dunn_adjust", "bonferroni")
        long = pd.DataFrame({"v": allv, "g": np.repeat([str(l) for l in levels], [len(g) for g in groups.values()])})
        dm = sp.posthoc_dunn(long, val_col="v", group_col="g", p_adjust=adj)
        rows = [[f"{a} − {b}", fmt_p(dm.loc[str(a), str(b)])] for a, b in itertools.combinations(levels, 2)]
        R.table(f"Dunn's Post Hoc Comparisons ({adj})", ["Comparison", "p (adj)"], rows, section="followups")
    if chosen != "kruskal":
        R.table(f"Post Hoc Comparisons – {ph_method.title()}" + (" (uncorrected)" if ph_method == "lsd" else ""),
                PH_COLS, [r[:6] for r in pooled_pairwise(means, ns, msw, dfw, ph_method)], section="followups")
        ckind = opt.get("contrast", "polynomial")
        if ckind and ckind != "none" and k >= 3:
            R.table(f"Contrasts ({ckind})", ["Contrast", "Estimate", "SE", "df", "t", "p"],
                    [r[:6] for r in contrast_rows(means, ns, msw, dfw, ckind, opt.get("contrast_weights"),
                                                  opt.get("level_values"))], section="followups")
    R.plots.append(plots.means_plot([str(l) for l in levels], list(means.values()),
                                    [g.std(ddof=1) / math.sqrt(len(g)) for g in groups.values()],
                                    f"Mean {dv_label} (±SE)", dv))

    # APA
    if chosen == "welch":
        R.apa = (f"Since Levene's test for equality of variances was significant, *F*({lev[2]}, {lev[3]}) = "
                 f"{fmt_num(lev[0])}, {p_eq(lev[1])}, Welch ANOVA test was used. "
                 f"There was {'a' if w['p'] < alpha else 'no'} significant effect of {grp} on {dv_label}, "
                 f"*F*({w['df1']}, {fmt_df(w['df2'])}) = {fmt_num(w['F'])}, {p_eq(w['p'])}, η² = {fmt_unit(eta)}.")
        sig = w["p"] < alpha
    elif chosen == "kruskal":
        sig = kw.pvalue < alpha
        R.apa = (f"Because the normality assumption was violated, a Kruskal-Wallis test was conducted. {dv_label[0].upper() + dv_label[1:]} "
                 f"{'differed' if sig else 'did not differ'} significantly across {grp} levels, "
                 f"*H*({k - 1}) = {fmt_num(kw.statistic)}, {p_eq(kw.pvalue)}.")
    else:
        sig = p < alpha
        R.apa = (f"A one-way between-subjects ANOVA was conducted to compare the effect of {grp} on {dv_label}. "
                 f"There was {'a' if sig else 'no'} significant effect of {grp}, *F*({dfb}, {dfw}) = {fmt_num(F)}, "
                 f"{p_eq(p)}, η² = {fmt_unit(eta)}." +
                 (f" Post hoc comparisons ({ph_method.title()}) are shown in the follow-up table." if sig else ""))
    R.interpretation = (f"{grp} {'has' if sig else 'has no'} significant effect on {dv_label}; η² = {fmt_unit(eta)} "
                        f"({band_eta(eta)}).")
    R.extra = {"F": F, "p": p, "df": [dfb, dfw], "ss": [ssb, ssw], "eta2": eta, "omega2": omega, "welch": w,
               "chosen": chosen, "kruskal": {"H": kw.statistic, "p": kw.pvalue}}
    R.python_code = f'''import pandas as pd, pingouin as pg, scipy.stats as st
df = pd.read_csv("data.csv").dropna(subset=["{dv}", "{grp}"])
groups = [g["{dv}"].values for _, g in df.groupby("{grp}")]
print(st.levene(*groups, center="mean"))
print(pg.anova(data=df, dv="{dv}", between="{grp}", detailed=True))
print(pg.welch_anova(data=df, dv="{dv}", between="{grp}"))
print(pg.pairwise_tukey(data=df, dv="{dv}", between="{grp}"))
print(st.kruskal(*groups))
'''
    return R.to_dict()


def _welch_anova(groups: dict) -> dict:
    g = [np.asarray(v, float) for v in groups.values()]
    k = len(g)
    n = np.array([len(x) for x in g], float)
    m = np.array([x.mean() for x in g])
    v = np.array([x.var(ddof=1) for x in g])
    w = n / v
    mw = (w * m).sum() / w.sum()
    a = (w * (m - mw) ** 2).sum() / (k - 1)
    lam = ((1 - w / w.sum()) ** 2 / (n - 1)).sum()
    b = 1 + 2 * (k - 2) / (k ** 2 - 1) * lam
    F = a / b
    df2 = (k ** 2 - 1) / (3 * lam)
    return {"F": F, "df1": k - 1, "df2": df2, "p": float(stats.f.sf(F, k - 1, df2))}


def _brown_forsythe(groups: dict) -> dict:
    g = [np.asarray(v, float) for v in groups.values()]
    k = len(g)
    n = np.array([len(x) for x in g], float)
    N = n.sum()
    m = np.array([x.mean() for x in g])
    v = np.array([x.var(ddof=1) for x in g])
    gm = (n * m).sum() / N
    den = ((1 - n / N) * v).sum()
    F = (n * (m - gm) ** 2).sum() / den
    c = (1 - n / N) * v / den
    df2 = 1 / (c ** 2 / (n - 1)).sum()
    return {"F": F, "df1": k - 1, "df2": df2, "p": float(stats.f.sf(F, k - 1, df2))}


# ======================================================================== factorial
def _safe(df: pd.DataFrame, dv: str, factors: list[str]):
    m = {dv: "y"}
    for i, f in enumerate(factors):
        m[f] = f"F{i}"
    d = df[[dv, *factors]].rename(columns=m).copy()
    return d, {v: k for k, v in m.items()}


def factorial_table(df: pd.DataFrame, dv: str, factors: list[str], transform: str | None = None):
    d, back = _safe(df, dv, factors)
    d["y"] = pd.to_numeric(d["y"], errors="coerce")
    d = d.dropna()
    if transform == "log":
        d["y"] = np.log(d["y"])
    elif transform == "sqrt":
        d["y"] = np.sqrt(d["y"])
    for i in range(len(factors)):
        d[f"F{i}"] = d[f"F{i}"].astype(str)
    rhs = " * ".join(f"C(F{i}, Sum)" for i in range(len(factors)))
    model = smf.ols(f"y ~ {rhs}", data=d).fit()
    tab = anova_lm(model, typ=3)
    tab = tab.drop(index="Intercept")
    rows = []
    ss_total = float(((d["y"] - d["y"].mean()) ** 2).sum())
    sse = float(tab.loc["Residual", "sum_sq"])
    dfe = float(tab.loc["Residual", "df"])
    mse = sse / dfe
    for idx, r in tab.iterrows():
        if idx == "Residual":
            continue
        names = [back[f"F{int(c)}"] for c in __import__("re").findall(r"C\(F(\d+), Sum\)", idx)]
        label = " ✻ ".join(names)
        ss, dfx, F, p = float(r["sum_sq"]), float(r["df"]), float(r["F"]), float(r["PR(>F)"])
        rows.append({"effect": label, "factors": names, "ss": ss, "df": dfx, "ms": ss / dfx, "F": F, "p": p,
                     "eta2": ss / ss_total, "peta2": ss / (ss + sse), "omega2": omega_sq(ss, dfx, mse, ss_total)})
    return rows, {"ss": sse, "df": dfe, "ms": mse}, model, d, back


def anova_factorial(data, roles: dict, options: dict | None = None) -> dict:
    opt = options or {}
    df = to_frame(data)
    dv = roles["dv"]
    factors = roles.get("factors_between") or []
    alpha = float(opt.get("alpha", 0.05))
    dv_label = opt.get("dv_label", dv)
    transform = opt.get("transform")
    if len(factors) < 2:
        return anova_oneway(data, roles, options)
    sub = df[[dv, *factors]].copy()
    sub[dv] = pd.to_numeric(sub[dv], errors="coerce")
    n_miss = int(sub.isna().any(axis=1).sum())
    sub = sub.dropna()
    R = Result("anova_factorial", f"{' × '.join(factors)} between-subjects ANOVA: {dv_label}")
    if n_miss:
        R.warnings.append(f"{n_miss} case(s) with missing values were excluded.")
    if len(factors) >= 4:
        R.warnings.append("Four-way and higher interactions are very hard to explain (Meeting 10).")
    # descriptives per cell
    cells = sub.groupby(factors)[dv]
    desc_rows = []
    for key, g in cells:
        key = key if isinstance(key, tuple) else (key,)
        d = describe(g)
        desc_rows.append([*[str(k) for k in key], d["N"], d["Mean"], d["SD"], d["SE"]])
    R.table("Descriptives", [*factors, "N", "Mean", "SD", "SE"], desc_rows, section="descriptives")
    counts = cells.count()
    if counts.nunique() > 1:
        R.warnings.append("Unbalanced cells: Type III sums of squares are used (JASP default).")
    if (counts < 2).any():
        R.warnings.append("Some cells have fewer than 2 observations.")

    rows, err, model, d, back = factorial_table(sub, dv, factors, transform)
    if transform:
        R.decide(f"DV transformed with {transform} before the analysis (user choice).", switched=True, rule="transform")
    # assumptions
    resid = model.resid
    sw = shapiro(resid)
    lev = levene(*[g.values for _, g in cells])
    R.check("Normality of residuals", "Shapiro-Wilk", sw[0], sw[1], not sw[1] < alpha)
    R.check("Homogeneity of variances", "Levene (mean)", lev[0], lev[1], not lev[1] < alpha, df=[lev[2], lev[3]])
    R.table("Test of Equality of Variances (Levene's)", ["F", "df1", "df2", "p"],
            [[lev[0], lev[2], lev[3], fmt_p(lev[1])]], section="assumptions")
    R.plots.append(plots.qqplot(resid, "Q-Q plot of residuals"))
    if sw[1] < alpha or lev[1] < alpha:
        R.decide("An assumption is violated and factorial ANOVA has no nonparametric version in the course. "
                 "Options: (a) log/sqrt transform the DV, (b) split into one-way ANOVAs with a Bonferroni-corrected α, "
                 "(c) proceed and add a caveat sentence. The analysis below proceeds with the caveat; choose another "
                 "option in the settings.", switched=True, rule="factorial-fallback", key="factorial")
    else:
        R.decide("Residuals normal and variances homogeneous → factorial ANOVA (Type III SS).")

    R.table(f"ANOVA – {dv}", ["Cases", "Sum of Squares", "df", "Mean Square", "F", "p", "η²", "η²p", "ω²"],
            [[r["effect"], r["ss"], r["df"], r["ms"], r["F"], fmt_p(r["p"]), r["eta2"], r["peta2"], r["omega2"]]
             for r in rows] + [["Residuals", err["ss"], err["df"], err["ms"], None, None, None, None, None]],
            ["Type III Sum of Squares"])
    for r in rows:
        R.effect(f"η²p {r['effect']}", r["peta2"], band_eta(r["peta2"]))

    # follow-ups
    inter = [r for r in rows if len(r["factors"]) >= 2]
    sig_inter = [r for r in inter if r["p"] < alpha]
    if len(factors) == 2:
        R.plots.append(plots.interaction_plot(sub, dv, factors[1], factors[0]))
    elif len(factors) == 3:
        for lvl, part in sub.groupby(factors[2]):
            R.plots.append(plots.interaction_plot(part, dv, factors[1], factors[0],
                                                  f"{factors[2]} = {lvl}"))
    if sig_inter and len(factors) >= 2:
        R.decide(f"Interaction {sig_inter[0]['effect']} is significant → simple main effects instead of main-effect "
                 "post hoc tests (Meeting 8).", rule="interaction")
        A, B = sig_inter[0]["factors"][:2]
        sme = simple_main_effects(sub, dv, A, B, err) + simple_main_effects(sub, dv, B, A, err)
        R.table("Simple Main Effects", ["Effect", "At level", "Sum of Squares", "df", "Mean Square", "F", "p"],
                [[s[0], s[1], s[2], s[3], s[4], s[5], fmt_p(s[6])] for s in sme], ["Error term: full-model MSE."],
                section="followups")
        R.extra["simple_effects"] = sme
    else:
        for r in rows:
            if len(r["factors"]) == 1:
                f = r["factors"][0]
                lv = level_order(sub[f])
                if len(lv) >= 3:
                    g = sub.groupby(f)[dv]
                    ph = pooled_pairwise(g.mean().to_dict(), g.count().to_dict(), err["ms"], err["df"],
                                         opt.get("posthoc", "tukey"))
                    R.table(f"Post Hoc – {f} ({opt.get('posthoc', 'tukey').title()})", PH_COLS,
                            [x[:6] for x in ph], section="followups")

    # APA
    parts = []
    for r in rows:
        parts.append(f"the {'interaction ' if len(r['factors']) > 1 else 'main effect of '}{r['effect'].replace(' ✻ ', ' × ')}"
                     f" was {'' if r['p'] < alpha else 'not '}significant, *F*({fmt_df(r['df'])}, {fmt_df(err['df'])}) = "
                     f"{fmt_num(r['F'])}, {p_eq(r['p'])}, η²p = {fmt_unit(r['peta2'])}")
    R.apa = (f"A {' × '.join(str(sub[f].nunique()) for f in factors)} between-subjects ANOVA was conducted on "
             f"{dv_label}. " + "; ".join(p[0].upper() + p[1:] if i == 0 else p for i, p in enumerate(parts)) + ".")
    if sig_inter:
        R.apa += " Because the interaction was significant, simple main effects were examined."
    if sw[1] < alpha or lev[1] < alpha:
        R.apa += " Note that the normality and/or equal-variance assumption was violated, so these results should be interpreted with caution."
    R.interpretation = ("Significant interaction: the effect of one factor depends on the level of the other; "
                        "interpret simple effects rather than main effects." if sig_inter else
                        "No significant interaction: main effects can be interpreted directly.")
    R.extra.update({"rows": rows, "error": err})
    flist = ", ".join(f'"{f}"' for f in factors)
    R.python_code = f'''import pandas as pd, statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
df = pd.read_csv("data.csv")
factors = [{flist}]
d = df.rename(columns={{"{dv}": "y", **{{f: f"F{{i}}" for i, f in enumerate(factors)}}}})
model = smf.ols("y ~ " + " * ".join(f"C(F{{i}}, Sum)" for i in range(len(factors))), data=d).fit()
print(anova_lm(model, typ=3))  # Type III, sum-to-zero (JASP default)
'''
    return R.to_dict()


def simple_main_effects(df: pd.DataFrame, dv: str, A: str, B: str, err: dict) -> list:
    """Effect of A at each level of B, tested against the full-model MSE."""
    out = []
    for lvl, part in df.groupby(B):
        g = part.groupby(A)[dv]
        m, n = g.mean(), g.count()
        gm = part[dv].mean()
        ss = float((n * (m - gm) ** 2).sum())
        dfx = len(m) - 1
        ms = ss / dfx if dfx else float("nan")
        F = ms / err["ms"]
        p = float(stats.f.sf(F, dfx, err["df"]))
        out.append([A, f"{B} = {lvl}", ss, dfx, ms, F, p])
    return out
