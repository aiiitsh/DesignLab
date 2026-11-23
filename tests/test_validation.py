"""Validation suite: spec §12 cases 1–20 (tolerance 0.001 unless stated)."""
import math
import os

import numpy as np
import pandas as pd
import pytest
from conftest import FIX
from jasp_extract import read_jasp

from engine.analyses import run
from engine.anova import anova_factorial, anova_oneway
from engine.decision_tree import all_paths, load_tree, next_node
from engine.design_utils import check_latin, counterbalance, williams
from engine.doe import fractional as fr
from engine.doe import two_level as tl
from engine.logistic import logistic
from engine.power.gpower import calculate, familywise
from engine.regression import regression
from engine.report import apa
from engine.rm_anova import anova_rm
from engine.ttests import ttest_ind

A = lambda x, y, tol=1e-3: abs(x - y) <= tol  # noqa: E731
LIB = os.path.join(FIX, "jasp_library")
JASP = os.path.join(FIX, "jasp")


# ---------------------------------------------------------------- case 1
def test_case1_hand_t():
    df = pd.DataFrame({"g": ["A"] * 5 + ["B"] * 5, "y": [6, 7, 8, 9, 10, 8, 9, 10, 11, 12]})
    r = ttest_ind(df, {"dv": "y", "factors_between": ["g"]})["extra"]
    assert r["student"]["df"] == 8
    assert A(r["student"]["t"], -2.000)
    assert round(r["student"]["p"], 3) == 0.081
    assert A(abs(r["d"]), 1.265)


# ---------------------------------------------------------------- case 2
def test_case2_drp():
    df = pd.read_csv(os.path.join(LIB, "Directed Reading Activities.csv"))
    r = ttest_ind(df, {"dv": "drp", "factors_between": ["group"]},
                  {"order": ["Treat", "Control"], "desc_digits": 1,
                   "level_labels": {"Treat": "experiment", "Control": "control"}, "dv_label": "DRP scores"})
    e = r["extra"]
    assert e["chosen"] == "student"
    assert A(e["student"]["t"], 2.267) and e["student"]["df"] == 42
    assert round(e["student"]["p"], 3) == 0.029
    assert A(e["d"], 0.684)
    assert round(e["means"][0], 2) == 51.48 and round(e["means"][1], 2) == 41.52
    assert ("There was a significant difference in the scores for the experiment group (*M* = 51.5, *SD* = 11.0) and "
            "the control group (*M* = 41.5, *SD* = 17.1); *t*(42) = 2.267, *p* = .029, *d* = 0.684.") in r["apa"]


# ---------------------------------------------------------------- case 3
def test_case3_battery_factorial():
    df, _ = read_jasp(os.path.join(JASP, "Montgomery Example 5.1 - data.jasp"))
    r = anova_factorial(df, {"dv": "Battery life in hours", "factors_between": ["Material type", "Temperature in F"]})
    rows = {x["effect"]: x for x in r["extra"]["rows"]}
    mat, tmp = rows["Material type"], rows["Temperature in F"]
    inter = rows["Material type ✻ Temperature in F"]
    assert A(mat["ss"], 10683.72, 0.01) and A(mat["F"], 7.91, 0.005) and A(mat["p"], 0.0020, 0.0001)
    assert A(tmp["ss"], 39118.72, 0.01) and A(tmp["F"], 28.97, 0.005)
    assert A(inter["ss"], 9613.78, 0.01) and A(inter["F"], 3.56, 0.005) and A(inter["p"], 0.0186, 0.0001)
    assert A(r["extra"]["error"]["ss"], 18230.75, 0.01) and r["extra"]["error"]["df"] == 27
    assert "simple_effects" in r["extra"]  # interaction significant -> simple main effects


# ---------------------------------------------------------------- case 4
FILTRATION = {"(1)": 45, "a": 71, "b": 48, "ab": 65, "c": 68, "ac": 60, "bc": 80, "abc": 65, "d": 43, "ad": 100,
              "bd": 45, "abd": 104, "cd": 75, "acd": 86, "bcd": 70, "abcd": 96}


def test_case4_filtration_2k():
    rows = tl.from_labels(4, FILTRATION)
    r = tl.analyze(4, rows)
    eff = {e["term"]: e for e in r["effects"]}
    for t, v in {"A": 21.625, "B": 3.125, "C": 9.875, "D": 14.625, "AC": -18.125, "AD": 16.625, "AB": 0.125}.items():
        assert A(eff[t]["effect"], v)
    assert A(eff["A"]["ss"], 1870.56, 0.01)
    assert round(eff["A"]["pct"], 1) == 32.6
    c = tl.collapse_drop(4, rows, "B")
    an = {a["term"]: a for a in c["anova"]}
    assert an["Error"]["df"] == 8
    # Montgomery prints 83.36 / 58.56 / 49.27 (rounded MS); exact values are 83.37 / 58.57 / 49.27
    assert A(an["A"]["F"], 83.36, 0.02) and A(an["AC"]["F"], 58.56, 0.02) and A(an["AD"]["F"], 49.27, 0.02)


def test_case4_from_jasp_file_matches():
    df, _ = read_jasp(os.path.join(JASP, "Example 6.2.jasp"))
    for c in "ABCD":
        df[c] = df[c].map({"+": 1, "-": -1})
    r = tl.analyze(4, df, "Filtration Rate (gal/h)")
    assert A({e["term"]: e["effect"] for e in r["effects"]}["AC"], -18.125)


# ---------------------------------------------------------------- cases 5–6
def test_case5_half_fraction():
    h = fr.runs_from_labels(4, {"(1)": 45, "ad": 100, "bd": 45, "ab": 65, "cd": 75, "ac": 60, "bc": 80, "abcd": 96})
    r = fr.analyze(4, "I=ABCD", h)
    est = {e["effect"]: e for e in r["estimates"]}
    for t, v in {"A": 19.0, "B": 1.5, "C": 14.0, "D": 16.5, "AB": -1.0, "AC": -18.5, "AD": 19.0}.items():
        assert A(est[t]["estimate"], v)
    assert est["A"]["aliases"] == ["BCD"] and est["AB"]["aliases"] == ["CD"]
    assert est["AC"]["aliases"] == ["BD"] and est["AD"]["aliases"] == ["BC"]


def test_case6_other_half_and_combined():
    o = fr.runs_from_labels(4, {"d": 43, "a": 71, "b": 48, "abd": 104, "c": 68, "acd": 86, "bcd": 70, "abc": 65})
    r = fr.analyze(4, "I=-ABCD", o)
    est = {e["effect"]: e["estimate"] for e in r["estimates"]}
    for t, v in {"A": 24.25, "B": 4.75, "C": 5.75, "D": 12.75, "AB": 1.25, "AC": -17.75}.items():
        assert A(est[t], v)
    h = fr.runs_from_labels(4, {"(1)": 45, "ad": 100, "bd": 45, "ab": 65, "cd": 75, "ac": 60, "bc": 80, "abcd": 96})
    full = tl.analyze(4, h + o)
    assert A({e["term"]: e["effect"] for e in full["effects"]}["A"], 21.625)


# ---------------------------------------------------------------- cases 7–8
def test_case7_alias_calculator():
    rel = fr.defining_relation(fr.parse_defining("I=-ABCDE"), "ABCDE")
    assert fr.alias_of("C", rel, "ABCDE") == [(-1, "ABDE")]
    assert fr.alias_of("BCE", rel, "ABCDE") == [(-1, "AD")]
    assert fr.missing_level("I=-ABCDE", {"A": 1, "B": -1, "C": 1, "D": 1}, "E") == 1
    assert fr.missing_level("I=-ABCDE", {"A": 1, "C": 1, "D": -1, "E": -1}, "B") == -1


def test_case8_run_counts():
    assert [fr.n_runs(4), fr.n_runs(6, 2), fr.n_runs(5, 1), fr.n_runs(7, 3)] == [16, 16, 16, 16]
    assert fr.design(6, 2)["n_runs"] == 16 and fr.design(7, 3)["resolution"] == 4


# ---------------------------------------------------------------- case 9
def field_df():
    rows = [("No", "Yes")] * 24 + [("No", "No")] * 32 + [("Yes", "Yes")] * 41 + [("Yes", "No")] * 16
    return pd.DataFrame(rows, columns=["Intervention", "Cured"])


def test_case9_logistic_field():
    r = logistic(field_df(), {"dv": "Cured", "factors_between": ["Intervention"]}, {"event": "Yes"})
    e = r["extra"]
    assert A(e["b"]["const"], -0.288) and A(e["b"]["Intervention (Yes)"], 1.229)
    assert A(e["se"]["Intervention (Yes)"], 0.400)
    assert A(math.exp(e["b"]["Intervention (Yes)"]), 3.417)
    assert A(e["wald"]["Intervention (Yes)"], 9.447)
    assert round(e["p_coef"]["Intervention (Yes)"], 3) == 0.002
    assert round(e["dev0"], 1) == 154.1 and round(e["dev1"], 1) == 144.2
    assert A(e["chi2"], 9.926) and A(e["cox_snell"], 0.084)
    assert A(e["b0_null"], 0.303)
    assert "(χ²(111) = 9.926, *p* = .002)" in r["apa"] and "3.42 times higher" in r["apa"]


# ---------------------------------------------------------------- case 10
def test_case10_titanic():
    df = pd.read_csv(os.path.join(LIB, "Titanic.csv"))
    e = logistic(df, {"dv": "Survived", "covariates": ["Age"], "factors_between": ["PClass"]})["extra"]
    b = e["b"]
    assert A(b["const"], 2.034) and A(b["Age"], -0.039) and A(b["PClass (2nd)"], -1.146) and A(b["PClass (3rd)"], -2.232)
    assert A(e["chi2"], 115.656) and A(e["cox_snell"], 0.142)


# ---------------------------------------------------------------- case 11
def test_case11_album_sales():
    df = pd.read_csv(os.path.join(LIB, "Album Sales.csv"))
    r = regression(df, {"dv": "sales", "covariates": ["adverts"]})
    assert r["extra"]["equation"] == "sales = 134.140 + 0.096 × adverts"
    assert A(r["extra"]["F"], 99.587)
    h = regression(df, {"dv": "sales", "covariates": ["adverts", "airplay", "attract"]},
                   {"method": "hierarchical", "blocks": [["adverts"], ["airplay", "attract"]]})
    m1, m2 = h["extra"]["models"][1], h["extra"]["models"][2]
    assert A(m1[3], 0.335) and A(m2[3], 0.665) and A(m2[6], 0.330)
    # The spec's "F change(3, 196) ≈ 129.5" was flagged "check df": two predictors are added, so df1 = 2 (JASP: 96.447)
    assert m2[8] == 2 and m2[9] == 196 and A(m2[7], 96.447)


# ---------------------------------------------------------------- cases 12–18
@pytest.mark.parametrize("family,params,N", [
    ("ttest_ind", {"es": 0.5}, 128),
    ("ttest_paired", {"es": 0.5}, 34),
    ("anova_oneway", {"es": 0.25, "k": 3}, 159),
    ("reg_r2", {"es": 0.15, "predictors": 3}, 77),
    ("chisq", {"es": 0.3, "df": 1}, 88),
    ("rm_within", {"es": 0.25, "groups": 1, "m": 3, "rho": 0.5, "eps": 1}, 28),
])
def test_cases12_17_power(family, params, N):
    assert calculate(family, "apriori", params)["N"] == N


def test_case12_per_group():
    r = calculate("ttest_ind", "apriori", {"es": 0.5})
    assert r["n1"] == 64 and r["n2"] == 64


def test_case18_familywise():
    assert A(familywise(10), 0.401)


# ---------------------------------------------------------------- case 19
def test_case19_latin_square():
    rows = williams(4)
    chk = check_latin(rows, 4)
    assert chk["each_once_per_row"] and chk["each_once_per_column"] and chk["carryover_balanced"]
    odd = williams(3)
    assert len(odd) == 6 and check_latin(odd, 3)["carryover_balanced"]
    cb = counterbalance(["A", "B", "C", "D"], "latin", participants=8)
    assert cb["assignment"][4]["order"] == cb["assignment"][0]["order"]


# ---------------------------------------------------------------- case 20
HW3_OUTCOMES = {  # path through the HW3 chart -> outcome
    ("A", "1", "2", "between"): "ttest_ind", ("A", "1", "2", "within"): "ttest_paired",
    ("A", "1", "3+", "between"): "anova_oneway", ("A", "1", "3+", "within"): "anova_rm1",
    ("A", "2+", "between"): "anova_factorial", ("A", "2+", "within"): "anova_rm", ("A", "2+", "mixed"): "anova_mixed",
    ("B", "1"): "regression_simple", ("B", "2+", "theory"): "regression_hier", ("B", "2+", "data"): "regression_step",
    ("C", "binary"): "logistic", ("C", "table"): "chisquare", ("C", "multi"): "not_covered",
    ("D", "screen", "replicated"): "doe_2k_rep", ("D", "screen", "single"): "doe_2k_single",
    ("D", "screen", "fraction"): "doe_frac", ("D", "optimize"): "doe_rsm", ("D", "robust"): "doe_robust",
}


def test_case20_every_path_reaches_an_outcome():
    tree = load_tree()
    paths = all_paths()
    assert paths and all(o in tree["outcomes"] for _, o in paths)
    reached = {o for _, o in paths}
    assert reached == set(HW3_OUTCOMES.values())
    for answers, outcome in paths:
        res = next_node(answers)
        assert res["done"] and res["outcome"] == outcome


def test_case20_specific_routes():
    base = {"plan_rq": "x", "plan_hyp": "two", "plan_vars": {}, "plan_manip": "true", "plan_controls": []}
    keys = {"A": ["A_niv", "A_levels", "A_within2"], "B": ["B_npred", "B_theory"], "C": ["C_type"], "D": ["D_goal", "D_budget"]}
    for route, outcome in HW3_OUTCOMES.items():
        lane = route[0]
        ans = {**base, "lane": lane}
        if lane == "A" and route[1] == "1":
            ans.update({"A_niv": "1", "A_levels": route[2], "A_within2" if route[2] == "2" else "A_within3": route[3]})
        elif lane == "A":
            ans.update({"A_niv": "2+", "A_nfactors": 2, "A_mix": route[2]})
        else:
            for k, v in zip(keys[lane], route[1:]):
                ans[k] = v
        assert next_node(ans)["outcome"] == outcome, route


# ---------------------------------------------------------------- golden APA strings (§9.1)
def test_golden_apa_strings():
    s = apa.strip_md(apa.rm_gg(11.406, 5, 0.047, 0.533, 3.794, 1.599, 11.190, 0.063, 0.351))
    assert ("Since Mauchly's test indicated that the assumption of sphericity was violated, χ²(5) = 11.406, p = .047, "
            "and the Greenhouse-Geisser ε = 0.533, Greenhouse-Geisser correction was used.") in s
    assert "F(1.599, 11.190) = 3.794, p = .063, η² = .351." in s
    s = apa.strip_md(apa.welch_anova(2.607, 4, 129, 0.039, 5.445, 4, 61.144, 0.0004, 0.114))
    assert ("Since Levene's test for equality of variances was significant, F(4, 129) = 2.607, p = .039, Welch ANOVA "
            "test was used.") in s and "F(4, 61.144) = 5.445, p < .001, η² = .114." in s
    s = apa.strip_md(apa.regression(17.096, 1, 98, 0.00007, 0.149, "BMI = 29.578 − 0.655 × PA"))
    assert "F(1, 98) = 17.096, p < .001, R² = .149. BMI = 29.578 − 0.655 × PA" in s
    s = apa.strip_md(apa.logistic("Intervention", 9.447, 0.0021, 9.926, 111, 0.0016, 0.084, 3.4167, "being cured"))
    assert "only the Intervention predictor had a significant effect (W(1) = 9.447, p = .002)" in s
    assert "(χ²(111) = 9.926, p = .002), with R² = .084 (Cox & Snell)" in s and "3.42 times higher" in s
    s = apa.strip_md(apa.t_ind("DRP scores", "experiment", "control", 51.48, 11.01, 41.52, 17.15, 2.267, 42, 0.029, 0.684))
    assert ("There was a significant difference in the scores for the experiment group (M = 51.5, SD = 11.0) and the "
            "control group (M = 41.5, SD = 17.1); t(42) = 2.267, p = .029, d = 0.684.") in s


def test_p_formatting_rules():
    from engine.common import fmt_p, fmt_unit
    assert fmt_p(0.0004) == "< .001" and fmt_p(0.029) == ".029" and fmt_p(0.0005) == "< .001"
    assert fmt_unit(0.351) == ".351" and fmt_unit(-0.52, 2) == "−.52"


# ---------------------------------------------------------------- extra course examples
def test_montgomery_3_1_oneway():
    df, _ = read_jasp(os.path.join(JASP, "Montgomery Example 3.1 oneway ANOVA (independent sample) - data.jasp"))
    r = anova_oneway(df, {"dv": "Observed Etch rate", "factors_between": ["RF Power"]})
    assert A(r["extra"]["F"], 66.797) and A(r["extra"]["ss"][0], 66870.55, 0.01)


def test_montgomery_4_1_rcbd_as_rm():
    df, _ = read_jasp(os.path.join(JASP, "Montgomery Example 4.1 - data.jasp"))
    r = anova_rm(df, {"within_cols": ["PSI 8500", "PSI 8700", "PSI 8900", "PSI 9100"], "within_name": "Pressure"})
    e = r["extra"]["effects"][0]
    assert A(e["ss"], 178.171) and A(e["F"], 8.107) and e["err_df"] == 15


def test_rm_and_mixed_match_pingouin():
    pg = pytest.importorskip("pingouin")
    rng = np.random.default_rng(3)
    d = pd.DataFrame({"g": ["x"] * 5 + ["y"] * 7, "a": rng.normal(size=12), "b": rng.normal(size=12) + .5,
                      "c": rng.normal(size=12) + np.r_[np.zeros(5), np.ones(7)]})
    r = anova_rm(d, {"within_cols": ["a", "b", "c"], "within_name": "T", "factors_between": ["g"]})
    eff = {e["effect"]: e for e in r["extra"]["effects"]}
    long = d.reset_index().melt(id_vars=["index", "g"], value_vars=["a", "b", "c"])
    ref = pg.mixed_anova(long, dv="value", within="variable", between="g", subject="index", correction=True)
    assert A(eff["g"]["F"], ref.loc[0, "F"]) and A(eff["T"]["F"], ref.loc[1, "F"]) and A(eff["T ✻ g"]["F"], ref.loc[2, "F"])
    sph = r["extra"]["sphericity"]["T"]
    assert A(sph["gg"], ref.loc[1, "eps"]) and A(sph["W"], ref.loc[1, "W_spher"])


def test_two_way_rm_matches_pingouin():
    pg = pytest.importorskip("pingouin")
    rng = np.random.default_rng(5)
    cols = ["a1b1", "a1b2", "a1b3", "a2b1", "a2b2", "a2b3"]
    d = pd.DataFrame(rng.normal(size=(10, 6)) + np.array([0, 1, 2, 0, 0.5, 3]), columns=cols)
    r = anova_rm(d, {"within_cols": cols, "within_factors": [{"name": "A", "levels": ["a1", "a2"]},
                                                              {"name": "B", "levels": ["b1", "b2", "b3"]}]})
    eff = {e["effect"]: e for e in r["extra"]["effects"]}
    long = d.reset_index().melt(id_vars="index")
    long["A"], long["B"] = long.variable.str[:2], long.variable.str[2:]
    ref = pg.rm_anova(long, dv="value", within=["A", "B"], subject="index").set_index("Source")
    for k, src in (("A", "A"), ("B", "B"), ("A ✻ B", "A * B")):
        assert A(eff[k]["F"], ref.loc[src, "F"])
