"""Flagship end-to-end case: the group's candy choice-overload replication (spec §12.1)."""
import os

import pandas as pd
import pytest
from conftest import FIX

from engine.analyses import batch
from engine.chisquare import chisquare
from engine.decision_tree import next_node
from engine.power.gpower import calculate
from engine.ttests import ttest_ind

CSV = os.path.join(FIX, "candy", "candy_clean.csv")
XLSX = os.path.join(FIX, "candy", "SYDE640_Real_Candy_Tasting_Questionnaire.xlsx")
A = lambda x, y, tol=1e-3: abs(x - y) <= tol + 1e-12  # noqa: E731

# DV: (MA, SDA, MB, SDB, SW_A, SW_B, Levene, t, df, p_t, welch_df, U, p_U, d)
EXPECTED = {
    "Q1": (1.923, 1.320, 3.385, 1.710, .002, .269, .245, -2.439, 24, .022, 22.56, 40.5, .022, -0.957),
    "Q2": (6.462, 0.877, 5.923, 1.038, None, .001, .799, 1.429, 24, .166, None, 117.0, .071, 0.560),
    "Q3": (5.769, 1.235, 6.077, 1.115, .037, .005, .772, -0.667, 24, .511, None, 71.0, .482, -0.261),
    "Q4": (5.846, 1.573, 6.385, 0.961, .003, .001, .084, -1.053, 24, .303, 19.86, 71.5, .474, -0.413),
    "Q5": (2.077, 1.441, 1.769, 1.363, .002, None, .919, 0.559, 24, .581, None, 100.0, .390, 0.219),
    "Q6": (4.308, 1.494, 2.308, 0.947, .001, .025, .571, 4.077, 24, None, 20.31, 148.0, .001, 1.599),
    "time": (7.236, 3.930, 18.501, 10.485, .005, .053, .001, -3.497, 23, .002, 15.54, 14.0, .001, -1.400),
}


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(CSV)


def test_import_xlsx_normalizes_labels():
    raw = pd.read_excel(XLSX, sheet_name="DATA ENTRY")
    assert len(raw) == 26
    from engine.common import normalize_labels
    made = normalize_labels(raw.iloc[:, 3])
    assert set(made.dropna()) == {"Yes"}


@pytest.mark.parametrize("dv", list(EXPECTED))
def test_each_dv(df, dv):
    ma, sda, mb, sdb, swa, swb, lev, t, dft, pt, wdf, U, pU, d = EXPECTED[dv]
    r = ttest_ind(df, {"dv": dv, "factors_between": ["group"]})
    e = r["extra"]
    assert A(e["means"][0], ma) and A(e["means"][1], mb) and A(e["sds"][0], sda) and A(e["sds"][1], sdb)
    if swa is not None:
        assert round(e["shapiro"][0], 3) == swa
    else:
        assert e["shapiro"][0] < .001
    if swb is not None:
        assert round(e["shapiro"][1], 3) == swb
    else:
        assert e["shapiro"][1] < .001
    assert round(e["levene_p"], 3) == lev
    assert A(e["student"]["t"], t) and e["student"]["df"] == dft
    if pt is not None:
        assert round(e["student"]["p"], 3) == pt
    if wdf is not None:
        assert round(e["welch"]["df"], 2) == wdf
    assert A(e["mannwhitney"]["U"], U, 0.05) and round(e["mannwhitney"]["p"], 3) == pU
    assert A(e["d"], d)
    assert e["chosen"] == "mannwhitney"  # every DV has a non-normal group -> course fallback


def test_rank_biserial_signs(df):
    for dv, r_exp in (("Q1", -.521), ("Q6", .751), ("time", -.821)):
        e = ttest_ind(df, {"dv": dv, "factors_between": ["group"]})["extra"]
        assert A(e["mannwhitney"]["r_rb"], r_exp)


def test_time_precedence_and_missing(df):
    r = ttest_ind(df, {"dv": "time", "factors_between": ["group"]})
    assert r["extra"]["n"] == [12, 13]
    rules = [d["rule"] for d in r["decisions"]]
    assert "normality" in rules and "precedence" in rules
    assert any("Welch would be t(15.537) = −3.609, p = .002" in d["text"] for d in r["decisions"])
    assert any("missing" in w for w in r["warnings"])


def test_zero_variance_chi_square(df):
    with pytest.raises(ValueError, match="no variation"):
        chisquare(df, {"row": "group", "col": "made"})


def test_many_dvs_familywise(df):
    b = batch("ttest_ind", df, {"factors_between": ["group"]}, list(EXPECTED))
    assert A(b["familywise_alpha"], 0.302) and A(b["bonferroni_alpha"], 0.0071, 0.0001)
    s = {r["dv"]: r for r in b["summary"]}
    assert s["Q1"]["sig_uncorrected"] and not s["Q1"]["sig_bonferroni"]
    assert s["Q6"]["sig_bonferroni"] and s["time"]["sig_bonferroni"]


def test_power_for_the_replication():
    assert round(calculate("ttest_ind", "posthoc", {"es": 0.957, "n1": 13, "n2": 13})["power"], 3) == 0.649
    assert calculate("ttest_ind", "apriori", {"es": 0.957})["n1"] == 19
    assert round(calculate("ttest_ind", "sensitivity", {"n1": 13, "n2": 13})["es"], 3) == 1.145
    assert round(calculate("ttest_ind", "posthoc", {"es": 1.4, "n1": 12, "n2": 13})["power"], 3) == 0.917


def test_apa_q1(df):
    r = ttest_ind(df, {"dv": "Q1", "factors_between": ["group"]},
                  {"level_labels": {"A": "limited-choice (6 items)", "B": "extensive-choice (30 items)"},
                   "level_short": {"B": "extensive choice"}, "dv_label": "decision difficulty"})
    plain = r["apa"].replace("*", "")
    assert plain.startswith("A Mann-Whitney U test was conducted to compare decision difficulty between the "
                            "limited-choice (6 items; Mdn = 1) and extensive-choice (30 items; Mdn = 3) groups.")
    assert "significantly higher with extensive choice, U = 40.5, p = .022, r = −.52." in plain


def test_wizard_path():
    ans = {"plan_rq": "x", "plan_hyp": "two", "plan_vars": {}, "plan_manip": "quasi", "plan_controls": [],
           "lane": "A", "A_niv": "1", "A_levels": "2", "A_within2": "between"}
    r = next_node(ans)
    assert r["outcome"] == "ttest_ind" and any("Quasi" in f for f in r["flags"])
    assert "Mann-Whitney" in r["fallbacks"]
