"""API smoke tests and the Python-export round trip (spec §9.3)."""
import os
import re
import subprocess
import sys
import tempfile

import pandas as pd
import pytest
from conftest import FIX, ROOT

from fastapi.testclient import TestClient

from api.main import app
from engine.analyses import run

client = TestClient(app)
CANDY = pd.read_csv(os.path.join(FIX, "candy", "candy_clean.csv"))


def test_api_examples_and_analyze():
    ex = client.get("/api/examples").json()
    assert ex[0]["id"] == "candy"
    e = client.get("/api/examples/candy").json()
    r = client.post("/api/analyze/ttest_ind", json={"data": e["rows"], "roles": e["roles"], "options": e["options"]}).json()
    assert r["extra"]["chosen"] == "mannwhitney"


def test_api_error_is_friendly():
    rows = CANDY.astype(object).where(pd.notna(CANDY), None).to_dict(orient="records")
    r = client.post("/api/analyze/chisquare", json={"data": rows, "roles": {"row": "group", "col": "made"}})
    assert r.status_code == 400 and "no variation" in r.json()["detail"]


def test_api_power_tree_doe():
    assert client.post("/api/power/ttest_ind", json={"mode": "apriori", "params": {"es": 0.5}}).json()["N"] == 128
    assert client.post("/api/tree/next", json={"answers": {}}).json()["node"]["id"] == "plan_rq"
    d = client.post("/api/doe/design", json={"type": "fraction", "k": 5, "p": 1}).json()
    assert d["n_runs"] == 16 and d["resolution"] == 5


def test_project_roundtrip():
    body = {"name": "t", "answers": {"a": 1}, "datasets": {"main": {"columns": ["x"], "types": {"x": "scale"}, "rows": [{"x": 1}, {"x": 2}]}}}
    z = client.post("/api/project/save", json=body).content
    with tempfile.NamedTemporaryFile(suffix=".dlab", delete=False) as f:
        f.write(z)
    with open(f.name, "rb") as fh:
        p = client.post("/api/project/open", files={"file": ("p.dlab", fh, "application/zip")}).json()
    assert p["answers"] == {"a": 1} and p["datasets"]["main"]["rows"][1]["x"] == 2


@pytest.mark.parametrize("aid,roles", [
    ("ttest_ind", {"dv": "Q1", "factors_between": ["group"]}),
])
def test_generated_python_reproduces_numbers(aid, roles, tmp_path):
    r = run(aid, CANDY, roles)
    CANDY.to_csv(tmp_path / "data.csv", index=False)
    (tmp_path / "script.py").write_text(r["python_code"])
    out = subprocess.run([sys.executable, "script.py"], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    m = re.search(r"statistic=np\.float64\(([\d.]+)\)", out.stdout.split("Mann-Whitney")[1])
    assert abs(float(m.group(1)) - r["extra"]["mannwhitney"]["U"]) < 1e-9
    d = float(out.stdout.strip().split("Cohen d =")[1])
    assert abs(d - r["extra"]["d"]) < 1e-9


def test_generated_python_oneway(tmp_path):
    pytest.importorskip("pingouin")
    import sys as _s
    _s.path.insert(0, os.path.join(ROOT, "tests", "tools"))
    from jasp_extract import read_jasp
    df, _ = read_jasp(os.path.join(FIX, "jasp", "Montgomery Example 3.1 oneway ANOVA (independent sample) - data.jasp"))
    r = run("anova_oneway", df, {"dv": "Observed Etch rate", "factors_between": ["RF Power"]})
    df.to_csv(tmp_path / "data.csv", index=False)
    (tmp_path / "s.py").write_text(r["python_code"])
    out = subprocess.run([sys.executable, "s.py"], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert "66.797" in out.stdout or "66.79" in out.stdout
