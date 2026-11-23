"""Lane A: repeated-measures (one-way and n-way) and mixed ANOVA.

One general engine handles every design with within factors: sums of squares are
computed from cell totals (error strata, split-plot logic), each within effect is
tested against its own effect × subject(groups) error term, and sphericity
(Mauchly, GG, HF with the Lecoutre correction) is computed per within effect from
orthonormal contrast scores. The course rule picks the correction.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from . import plots
from .assumptions import _orth_contrasts, choose_correction, levene, shapiro, sphericity_scores
from .common import Result, band_eta, describe, fmt_df, fmt_num, fmt_p, fmt_unit, level_order, p_eq, to_frame
from .posthoc import pooled_pairwise

SUBJ = "__subject__"


# ------------------------------------------------------------------ reshaping
def wide_to_long(df: pd.DataFrame, roles: dict) -> tuple[pd.DataFrame, list[str], list[str], dict]:
    cols = roles["within_cols"]
    wf = roles.get("within_factors")
    between = roles.get("factors_between") or []
    if not wf:
        wf = [{"name": roles.get("within_name", "Condition"), "levels": list(cols)}]
    names = [f["name"] for f in wf]
    cell_map = roles.get("cell_map")
    if not cell_map:
        combos = list(itertools.product(*[f["levels"] for f in wf]))
        if len(combos) != len(cols):
            raise ValueError(f"{len(cols)} columns do not match the {len(combos)} within-subject cells.")
        cell_map = {c: list(k) for c, k in zip(cols, combos)}
    d = df.copy()
    d[cols] = d[cols].apply(pd.to_numeric, errors="coerce")
    keep = d[cols].notna().all(axis=1) & d[between].notna().all(axis=1) if between else d[cols].notna().all(axis=1)
    dropped = int((~keep).sum())
    d = d[keep].reset_index(drop=True)
    d[SUBJ] = np.arange(len(d))
    long = d.melt(id_vars=[SUBJ, *between], value_vars=cols, var_name="__cell__", value_name="y")
    for i, n in enumerate(names):
        long[n] = long["__cell__"].map(lambda c: cell_map[c][i])
    info = {"dropped": dropped, "levels": {f["name"]: list(f["levels"]) for f in wf}, "cols": cols,
            "cell_map": cell_map}
    return long, names, between, info


# ------------------------------------------------------------------ core engine
def _M(long: pd.DataFrame, by: list[str]) -> float:
    if not by:
        return float(long["y"].sum() ** 2 / len(long))
    g = long.groupby(by, observed=True)["y"]
    s, c = g.sum(), g.count()
    return float((s ** 2 / c).sum())


def _subsets(seq):
    for r in range(len(seq) + 1):
        yield from itertools.combinations(seq, r)


def strata_anova(long: pd.DataFrame, W: list[str], B: list[str]) -> dict:
    cache: dict = {}

    def M(by):
        key = tuple(sorted(by))
        if key not in cache:
            cache[key] = _M(long, list(key))
        return cache[key]

    lv = {f: long[f].nunique() for f in W + B}
    n_subj = long[SUBJ].nunique()
    n_bcells = long.groupby(B, observed=True)[SUBJ].nunique().shape[0] if B else 1
    effects = []
    for r in range(1, len(W) + len(B) + 1):
        for T in itertools.combinations(W + B, r):
            ss = sum((-1) ** (len(T) - len(U)) * M(list(U)) for U in _subsets(T))
            dfx = int(np.prod([lv[f] - 1 for f in T]))
            Ew = [f for f in T if f in W]
            effects.append({"effect": " ✻ ".join(T), "factors": list(T), "within": Ew, "ss": ss, "df": dfx})
    errors = {}
    for r in range(0, len(W) + 1):
        for Ew in itertools.combinations(W, r):
            ss = sum((-1) ** (len(Ew) - len(U)) * (M(list(U) + [SUBJ]) - M(list(U) + B)) for U in _subsets(Ew))
            dfe = int(np.prod([lv[f] - 1 for f in Ew])) * (n_subj - n_bcells)
            errors[tuple(Ew)] = {"ss": ss, "df": dfe}
    total = float(((long["y"] - long["y"].mean()) ** 2).sum())
    all_err = sum(e["ss"] for e in errors.values())
    for e in effects:
        err = errors[tuple(e["within"])]
        e["err_ss"], e["err_df"] = err["ss"], err["df"]
        e["ms"] = e["ss"] / e["df"]
        e["err_ms"] = err["ss"] / err["df"] if err["df"] else float("nan")
        e["F"] = e["ms"] / e["err_ms"]
        e["p"] = float(stats.f.sf(e["F"], e["df"], err["df"]))
        e["peta2"] = e["ss"] / (e["ss"] + err["ss"])
        e["eta2"] = e["ss"] / total
        e["ges"] = e["ss"] / (e["ss"] + all_err)
    return {"effects": effects, "errors": errors, "total": total, "n_subj": n_subj}


def _sph_for(long: pd.DataFrame, W: list[str], B: list[str], Ew: list[str], levels: dict) -> dict | None:
    if not Ew or all(long[f].nunique() <= 2 for f in Ew):
        return None
    lvls = [levels.get(f) or level_order(long[f]) for f in W]
    piv = long.pivot_table(index=SUBJ, columns=W, values="y", aggfunc="mean")
    piv = piv.reindex(columns=pd.MultiIndex.from_product(lvls) if len(W) > 1 else lvls[0])
    Y = piv.values
    K = np.ones((1, 1))
    for f, l in zip(W, lvls):
        k = len(l)
        part = _orth_contrasts(k) if f in Ew else np.ones((k, 1)) / math.sqrt(k)
        K = np.kron(K, part)
    Z = Y @ K
    groups = None
    if B:
        g = long.drop_duplicates(SUBJ).set_index(SUBJ).loc[piv.index, B].astype(str).agg("|".join, axis=1).values
        groups = g
    return sphericity_scores(Z, groups)


# ------------------------------------------------------------------ public analysis
def anova_rm(data, roles: dict, options: dict | None = None) -> dict:
    """One-way RM, n-way RM and mixed ANOVA (between factors in roles.factors_between)."""
    opt = options or {}
    alpha = float(opt.get("alpha", 0.05))
    df = to_frame(data)
    long, W, B, info = wide_to_long(df, roles)
    dv_label = opt.get("dv_label", "the DV")
    mixed = bool(B)
    aid = "anova_mixed" if mixed else ("anova_rm1" if len(W) == 1 else "anova_rm")
    title = ("Mixed ANOVA" if mixed else "Repeated measures ANOVA") + f": {' × '.join(W + B)}"
    R = Result(aid, title)
    if info["dropped"]:
        R.warnings.append(f"{info['dropped']} participant(s) with a missing measurement were excluded (listwise).")
    if len(W) + len(B) >= 4:
        R.warnings.append("Four-way and higher interactions are very hard to explain (Meeting 10).")

    # descriptives
    rows = []
    for key, g in long.groupby(W + B, observed=True)["y"]:
        key = key if isinstance(key, tuple) else (key,)
        d = describe(g)
        rows.append([*[str(k) for k in key], d["N"], d["Mean"], d["SD"], d["SE"], d["CI low"], d["CI high"]])
    R.table("Descriptives", [*W, *B, "N", "Mean", "SD", "SE", "95% CI low", "95% CI high"], rows,
            section="descriptives")
    if len(W) == 1 and not B:
        R.plots.append(plots.boxplot({str(c): long.loc[long[W[0]] == c, "y"] for c in info["levels"][W[0]]},
                                     f"{dv_label} by {W[0]}"))

    res = strata_anova(long, W, B)
    # sphericity per within effect
    sph_rows, corr_for = [], {}
    for r in range(1, len(W) + 1):
        for Ew in itertools.combinations(W, r):
            s = _sph_for(long, W, B, list(Ew), info["levels"])
            name = " ✻ ".join(Ew)
            if s is None:
                corr_for[Ew] = ("none", 1.0, None)
                continue
            corr, eps, why = choose_correction(s, alpha)
            if opt.get("correction") in ("none", "Greenhouse-Geisser", "Huynh-Feldt"):
                forced = opt["correction"]
                eps = {"none": 1.0, "Greenhouse-Geisser": s["gg"], "Huynh-Feldt": s["hf"]}[forced]
                R.decide(f"User override for {name}: {forced} instead of {corr}.", switched=True, rule="override")
                corr = forced
            corr_for[Ew] = (corr, eps, s)
            sph_rows.append([name, s["W"], s["chi2"], s["df"], fmt_p(s["p"]), s["gg"], s["hf"], s["lower"]])
            R.check(f"Sphericity ({name})", "Mauchly", s["W"], s["p"], not s["p"] < alpha, detail=why, df=s["df"])
            R.decide(f"{name}: {why}", switched=corr != "none", rule="sphericity", key=f"sph:{name}")
    if sph_rows:
        R.table("Test of Sphericity", ["Effect", "Mauchly's W", "Approx. χ²", "df", "p", "Greenhouse-Geisser ε",
                                       "Huynh-Feldt ε", "Lower bound ε"], sph_rows, section="assumptions")
    else:
        R.decide("Every within factor has 2 levels, so sphericity is automatically met.")

    # normality per cell; Levene per within cell across between groups
    normal_fail = []
    norm_rows = []
    for key, g in long.groupby(W + B, observed=True)["y"]:
        s = shapiro(g)
        norm_rows.append([" / ".join(map(str, key if isinstance(key, tuple) else (key,))), s[0], fmt_p(s[1])])
        if s[1] < alpha:
            normal_fail.append(norm_rows[-1][0])
    R.table("Test of Normality (Shapiro-Wilk) per cell", ["Cell", "W", "p"], norm_rows, section="assumptions")
    R.check("Normality (all cells)", "Shapiro-Wilk", None, None, not normal_fail,
            detail=("Non-normal: " + ", ".join(normal_fail)) if normal_fail else "All cells p > .05")
    if B:
        lev_rows = []
        for key, part in long.groupby(W, observed=True):
            gs = [g.values for _, g in part.groupby(B, observed=True)["y"]]
            L = levene(*gs)
            lev_rows.append([" / ".join(map(str, key if isinstance(key, tuple) else (key,))), L[0], L[2], L[3],
                             fmt_p(L[1])])
            R.check(f"Equal variances ({lev_rows[-1][0]})", "Levene (mean)", L[0], L[1], not L[1] < alpha)
        R.table("Test of Equality of Variances (Levene's)", ["Cell", "F", "df1", "df2", "p"], lev_rows,
                section="assumptions")
        if any(not c["ok"] for c in R.checks if c["test"].startswith("Levene")):
            R.decide("Levene p < .05 for the between factor. Mixed ANOVA has no Welch version in the course: "
                     "consider (a) a transform, (b) separate analyses with Bonferroni α, or (c) proceed with a caveat.",
                     switched=True, rule="mixed-variance")

    # main tables
    win_rows, btw_rows = [], []
    strata = {}
    for e in res["effects"]:
        strata.setdefault(tuple(e["within"]), []).append(e)
    for Ew, effs in strata.items():
        if not Ew:
            for e in effs:
                e["correction"], e["eps"], e["df_c"], e["err_df_c"], e["p_c"] = "none", 1.0, e["df"], e["err_df"], e["p"]
                btw_rows.append([e["effect"], e["ss"], e["df"], e["ms"], e["F"], fmt_p(e["p"]), e["eta2"], e["peta2"],
                                 e["ges"]])
            continue
        corr, eps, s = corr_for.get(Ew, ("none", 1.0, None))
        variants = [("None", 1.0)]
        if s is not None:
            variants += [("Greenhouse-Geisser", s["gg"]), ("Huynh-Feldt", s["hf"])]
        for e in effs:
            e["correction"], e["eps"] = corr, eps
            e["df_c"], e["err_df_c"] = e["df"] * eps, e["err_df"] * eps
            e["p_c"] = float(stats.f.sf(e["F"], e["df_c"], e["err_df_c"]))
            for vname, ve in variants:
                used = vname == corr or (vname == "None" and corr == "none")
                win_rows.append([e["effect"], vname, e["ss"], e["df"] * ve, e["ss"] / (e["df"] * ve), e["F"],
                                 fmt_p(float(stats.f.sf(e["F"], e["df"] * ve, e["err_df"] * ve))), e["eta2"],
                                 e["peta2"], e["ges"], "✓" if used else ""])
        e = effs[0]
        for vname, ve in variants:
            win_rows.append([f"Residuals ({' ✻ '.join(Ew)})", vname, e["err_ss"], e["err_df"] * ve,
                             e["err_ss"] / (e["err_df"] * ve), None, None, None, None, None, ""])
    R.table("Within Subjects Effects", ["Cases", "Sphericity correction", "Sum of Squares", "df", "Mean Square", "F",
                                        "p", "η²", "η²p", "η²G", "Used"], win_rows,
            ["Type III Sum of Squares; the ✓ row is the one the course rule selects."])
    err0 = res["errors"][()]
    if B:
        btw_rows.append(["Residuals", err0["ss"], err0["df"], err0["ss"] / err0["df"], None, None, None, None, None])
        R.table("Between Subjects Effects", ["Cases", "Sum of Squares", "df", "Mean Square", "F", "p", "η²", "η²p",
                                             "η²G"], btw_rows)
    for e in res["effects"]:
        R.effect(f"η²p {e['effect']}", e["peta2"], band_eta(e["peta2"]))
        if len(W) == 1 and not B:
            R.effect(f"η² {e['effect']}", e["eta2"], band_eta(e["eta2"]))
            R.effect(f"η²G {e['effect']}", e["ges"], band_eta(e["ges"]))

    # nonparametric fallback (single within factor, no between)
    chosen = "rm"
    if len(W) == 1 and not B:
        wide = long.pivot_table(index=SUBJ, columns=W[0], values="y").reindex(columns=info["levels"][W[0]])
        fr = stats.friedmanchisquare(*[wide[c].values for c in wide.columns]) if wide.shape[1] >= 3 else None
        if fr is not None:
            n, k = wide.shape
            kendall = fr.statistic / (n * (k - 1))
            R.table("Friedman Test", ["Factor", "χ²", "df", "p", "Kendall's W"],
                    [[W[0], fr.statistic, k - 1, fmt_p(fr.pvalue), kendall]])
            if normal_fail and not opt.get("force"):
                chosen = "friedman"
                R.decide(f"Shapiro-Wilk p < .05 in {', '.join(normal_fail)} → Friedman test with Conover post hoc "
                         "(course rule, Meeting 7).", switched=True, rule="normality", key="normality")
                import scikit_posthocs as sp
                cm = sp.posthoc_conover_friedman(wide.values, p_adjust=opt.get("conover_adjust", "bonferroni"))
                labs = list(wide.columns)
                R.table("Conover's Post Hoc Comparisons", ["Comparison", "p (adj)"],
                        [[f"{labs[i]} − {labs[j]}", fmt_p(cm.iloc[i, j])]
                         for i, j in itertools.combinations(range(k), 2)], section="followups")
                R.extra["friedman"] = {"chi2": fr.statistic, "p": fr.pvalue, "W": kendall}

    # follow-ups
    sig_inter = [e for e in res["effects"] if len(e["factors"]) >= 2 and e["p_c"] < alpha]
    if len(W + B) == 2:
        f1, f2 = (W + B)
        R.plots.append(plots.interaction_plot(long, "y", f1, f2, f"{dv_label}: {f1} × {f2}"))
    elif len(W + B) == 1:
        g = long.groupby(W[0])["y"]
        lv = info["levels"][W[0]]
        R.plots.append(plots.means_plot(lv, g.mean().reindex(lv).tolist(),
                                        (g.std() / np.sqrt(g.count())).reindex(lv).tolist(),
                                        f"Mean {dv_label} (±SE)"))
    if sig_inter:
        e0 = sig_inter[0]
        A, Bf = e0["factors"][:2]
        R.decide(f"Interaction {e0['effect']} is significant → simple main effects (Meeting 9).", rule="interaction")
        sme = []
        for fa, fb in ((A, Bf), (Bf, A)):
            for lvl in level_order(long[fb]):
                part = long[long[fb] == lvl]
                W2 = [w for w in W if w != fb]
                B2 = [b for b in B if b != fb]
                if fa not in W2 + B2:
                    continue
                r2 = strata_anova(part, W2, B2)
                row = next(x for x in r2["effects"] if x["factors"] == [fa])
                eps = 1.0
                if fa in W2 and part[fa].nunique() > 2:
                    s = _sph_for(part, W2, B2, [fa], info["levels"])
                    _, eps, _ = choose_correction(s, alpha)
                p = float(stats.f.sf(row["F"], row["df"] * eps, row["err_df"] * eps))
                sme.append([fa, f"{fb} = {lvl}", row["ss"], row["df"] * eps, row["ms"], row["F"], fmt_p(p),
                            row["peta2"]])
        R.table("Simple Main Effects", ["Effect", "At level", "Sum of Squares", "df", "Mean Square", "F", "p", "η²p"],
                sme, ["Each simple effect uses its own error term (separate analysis at each level), as JASP."],
                section="followups")
    else:
        adj = opt.get("posthoc", "bonferroni")
        for f in W:
            lv = info["levels"][f]
            if len(lv) < 3:
                continue
            sm = long.groupby([SUBJ, f])["y"].mean().unstack(f)[lv]
            raw = []
            for a, b in itertools.combinations(lv, 2):
                t = stats.ttest_rel(sm[a], sm[b])
                raw.append([f"{a} − {b}", float((sm[a] - sm[b]).mean()), float(t.statistic), len(sm) - 1, t.pvalue])
            ps = multipletests([r[4] for r in raw], method="holm" if adj == "holm" else "bonferroni")[1]
            R.table(f"Post Hoc – {f} (paired t, {'Holm' if adj == 'holm' else 'Bonferroni'})",
                    ["Comparison", "Mean difference", "t", "df", "p (adj)"],
                    [[r[0], r[1], r[2], r[3], fmt_p(p)] for r, p in zip(raw, ps)], section="followups")
        for f in B:
            if long[f].nunique() < 3:
                continue
            subj = long.groupby([SUBJ, f])["y"].mean().reset_index()
            g = subj.groupby(f)["y"]
            c = len(long) / res["n_subj"]
            ph = pooled_pairwise(g.mean().to_dict(), g.count().to_dict(), err0["ss"] / err0["df"] / c, err0["df"],
                                 "tukey")
            R.table(f"Post Hoc – {f} (Tukey)", ["Comparison", "Mean difference", "SE", "t", "df", "p (adj)"],
                    [x[:6] for x in ph], section="followups")

    # APA
    parts = []
    lead = ""
    for e in res["effects"]:
        corr = e["correction"]
        if corr != "none":
            s = corr_for[tuple(e["within"])][2]
            lead += (f"Since Mauchly's test indicated that the assumption of sphericity was violated for "
                     f"{e['effect'].replace(' ✻ ', ' × ')}, χ²({s['df']}) = {fmt_num(s['chi2'])}, {p_eq(s['p'])}, "
                     f"and the Greenhouse-Geisser ε = {fmt_num(s['gg'])}, {corr} correction was used. ")
        es_name, es_val = ("η²", e["eta2"]) if (len(W) == 1 and not B) else ("η²p", e["peta2"])
        kind = "interaction " if len(e["factors"]) > 1 else "main effect of "
        parts.append(f"the {kind}{e['effect'].replace(' ✻ ', ' × ')} was {'' if e['p_c'] < alpha else 'not '}"
                     f"significant, *F*({fmt_df(e['df_c'])}, {fmt_df(e['err_df_c'])}) = {fmt_num(e['F'])}, "
                     f"{p_eq(e['p_c'])}, {es_name} = {fmt_unit(es_val)}")
    design = "mixed" if B else "repeated measures"
    body = "; ".join(parts)
    R.apa = (lead + f"A {design} ANOVA was conducted on {dv_label}. " + body[0].upper() + body[1:] + ".")
    if chosen == "friedman":
        fr = R.extra["friedman"]
        R.apa = (f"Because the normality assumption was violated, a Friedman test was conducted. {dv_label[0].upper() + dv_label[1:]} "
                 f"{'differed' if fr['p'] < alpha else 'did not differ'} significantly across {W[0]}, "
                 f"χ²({len(info['levels'][W[0]]) - 1}) = {fmt_num(fr['chi2'])}, {p_eq(fr['p'])}, Kendall's *W* = "
                 f"{fmt_unit(fr['W'])}.")
    R.interpretation = ("Significant interaction: interpret the simple main effects." if sig_inter else
                        "No significant interaction (or a single factor): interpret main effects and post hoc tests.")
    R.extra.update({"effects": res["effects"], "errors": {"|".join(k) or "subjects": v for k, v in res["errors"].items()},
                    "chosen": chosen, "sphericity": {" ✻ ".join(k): v[2] for k, v in corr_for.items() if v[2]}})
    wcols = ", ".join(f'"{c}"' for c in info["cols"])
    if len(W) == 1 and not B:
        R.python_code = f'''import pandas as pd, pingouin as pg
df = pd.read_csv("data.csv")
cols = [{wcols}]
long = df.reset_index().melt(id_vars="index", value_vars=cols, var_name="cond", value_name="y")
print(pg.rm_anova(data=long, dv="y", within="cond", subject="index", correction=True, detailed=True))
print(pg.sphericity(df[cols]), "GG", pg.epsilon(df[cols]), "HF", pg.epsilon(df[cols], correction="hf"))
print(pg.friedman(data=long, dv="y", within="cond", subject="index"))
'''
    elif len(W) == 1 and len(B) == 1:
        R.python_code = f'''import pandas as pd, pingouin as pg
df = pd.read_csv("data.csv")
cols = [{wcols}]
long = df.reset_index().melt(id_vars=["index", "{B[0]}"], value_vars=cols, var_name="{W[0]}", value_name="y")
print(pg.mixed_anova(data=long, dv="y", within="{W[0]}", between="{B[0]}", subject="index", correction=True))
'''
    else:
        R.python_code = f'''import pandas as pd
from statsmodels.stats.anova import AnovaRM
df = pd.read_csv("data.csv")
# reshape the within columns [{wcols}] to long format with one column per within factor, then:
# print(AnovaRM(long, depvar="y", subject="id", within={W!r}).fit())
'''
    return R.to_dict()
