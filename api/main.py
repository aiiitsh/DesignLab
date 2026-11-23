"""DesignLab API (FastAPI). Serves the engine and the built frontend on one port."""
from __future__ import annotations

import io
import json
import os
import traceback
import warnings
import zipfile
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine import analyses, decision_tree, design_utils
from engine.common import clean, normalize_labels
from engine.doe import fractional, robust, rsm, two_level
from engine.power import gpower

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(ROOT, "data", "examples")
DIST = os.path.join(ROOT, "web", "dist")

app = FastAPI(title="DesignLab API", version="1.0", description="SYDE 640 experiment design and analysis engine")


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def any_error(_: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


def ok(x: Any) -> JSONResponse:
    return JSONResponse(content=clean(x))


# ------------------------------------------------------------------ models
class AnalyzeReq(BaseModel):
    data: list[dict]
    roles: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)


class BatchReq(AnalyzeReq):
    dvs: list[str]
    correction: str = "bonferroni"


class TreeReq(BaseModel):
    answers: dict = Field(default_factory=dict)


class PowerReq(BaseModel):
    mode: str = "apriori"
    params: dict = Field(default_factory=dict)


# ------------------------------------------------------------------ meta
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/analyses")
def list_analyses():
    return analyses.ANALYSIS_INFO


# ------------------------------------------------------------------ wizard
@app.get("/api/tree")
def tree():
    return decision_tree.load_tree()


@app.post("/api/tree/next")
def tree_next(req: TreeReq):
    return ok(decision_tree.next_node(req.answers))


@app.post("/api/tree/helper")
def tree_helper(body: dict):
    return decision_tree.suggest_within(**{k: bool(v) for k, v in body.items()})


# ------------------------------------------------------------------ analyses
@app.post("/api/analyze/{analysis_id}")
def analyze(analysis_id: str, req: AnalyzeReq):
    return ok(analyses.run(analysis_id, req.data, req.roles, req.options))


@app.post("/api/analyze_batch/{analysis_id}")
def analyze_batch(analysis_id: str, req: BatchReq):
    return ok(analyses.batch(analysis_id, req.data, req.roles, req.dvs, req.options, req.correction))


# ------------------------------------------------------------------ power
@app.get("/api/power/families")
def power_families():
    return {k: {"label": v["label"], "es": v["es"], "default": v["default"]} for k, v in gpower.FAMILIES.items()}


@app.post("/api/power/{family}")
def power(family: str, req: PowerReq):
    if family not in gpower.FAMILIES:
        raise ValueError(f"Unknown power family {family}")
    return ok(gpower.calculate(family, req.mode, req.params))


@app.post("/api/power_helper/{kind}")
def power_helper(kind: str, body: dict):
    fns = {"d": gpower.d_from_means, "f": gpower.f_from_means, "f2": gpower.f2_from_r2,
           "f_from_peta2": gpower.f_from_peta2, "peta2_from_f": gpower.peta2_from_f, "w": gpower.w_from_table,
           "familywise": gpower.familywise}
    return ok({"value": fns[kind](**body)})


# ------------------------------------------------------------------ design utilities
@app.post("/api/design/counterbalance")
def counterbalance(body: dict):
    return ok(design_utils.counterbalance(body["conditions"], body.get("method", "latin"), body.get("participants")))


@app.post("/api/design/randomize")
def randomize(body: dict):
    return ok(design_utils.randomize(int(body["participants"]), body["groups"], int(body.get("seed", 640)),
                                     body.get("blocks")))


# ------------------------------------------------------------------ DOE
@app.post("/api/doe/design")
def doe_design(body: dict):
    t = body.get("type", "2k")
    if t == "2k":
        return ok(two_level.generate(int(body["k"]), body.get("names"), body.get("low"), body.get("high"),
                                     int(body.get("replicates", 1)), int(body.get("center", 0)),
                                     int(body.get("seed", 640))))
    if t == "fraction":
        return ok(fractional.design(int(body["k"]), int(body["p"]), body.get("generators") or None, body.get("names"),
                                    int(body.get("seed", 640))))
    if t == "ccd":
        return ok(rsm.ccd(int(body["k"]), body.get("alpha", "rotatable"), int(body.get("center", 4))))
    if t == "bbd":
        return ok(rsm.box_behnken(int(body["k"]), int(body.get("center", 3))))
    if t == "oa":
        A = robust.orthogonal_array(body["name"])
        return ok({"array": A.tolist(), "runs": A.shape[0], "columns": A.shape[1]})
    raise ValueError(f"Unknown design type {t}")


@app.post("/api/doe/analyze")
def doe_analyze(body: dict):
    t = body.get("type", "2k")
    resp = body.get("response", "y")
    if t == "2k":
        k = int(body["k"])
        data = body["data"]
        out = two_level.analyze(k, data, resp, body.get("names"), body.get("model_terms"))
        if body.get("drop"):
            out["collapsed"] = two_level.collapse_drop(k, data, body["drop"], resp)
        return ok(out)
    if t == "fraction":
        return ok(fractional.analyze(int(body["k"]), body.get("relation") or body.get("generators"), body["data"], resp))
    raise ValueError(f"Unknown DOE analysis {t}")


@app.post("/api/doe/alias")
def doe_alias(body: dict):
    rel = body["relation"]
    k = int(body.get("k", 0)) or len(set("".join(w for _, w in fractional.parse_defining(rel))))
    order = "".join(two_level.letters(k))
    words = fractional.defining_relation(fractional.parse_defining(rel), order)
    out = {"defining_relation": "I = " + " = ".join(fractional.fmt_signed(s, w) for s, w in words),
           "resolution": fractional.resolution(words),
           "runs": 2 ** (k - len(fractional.parse_defining(rel)))}
    if body.get("effect"):
        out["aliases"] = [fractional.fmt_signed(s, w) for s, w in fractional.alias_of(body["effect"], words, order)]
    if body.get("known") and body.get("target"):
        out["level"] = fractional.missing_level(rel, body["known"], body["target"])
    out["table"] = fractional.alias_table(k, words)
    return ok(out)


@app.post("/api/doe/rsm")
def doe_rsm(body: dict):
    action = body.get("action", "fit")
    if action == "curvature":
        return ok(rsm.curvature(body["y_factorial"], body["y_center"]))
    if action == "steepest":
        return ok(rsm.steepest(body["coefs"], body.get("base"), float(body.get("step", 1)), int(body.get("n_steps", 10)),
                               body.get("centers"), body.get("halfs"), bool(body.get("descent"))))
    fit = rsm.fit_quadratic(body["data"], body["xcols"], body["response"])
    if len(body["xcols"]) >= 2:
        fit["surface"] = rsm.surface_grid(fit, 0, 1)
    return ok(fit)


@app.post("/api/doe/robust")
def doe_robust(body: dict):
    if body.get("mode", "crossed") == "crossed":
        return ok(robust.crossed(body["inner"], body["outer_responses"], body["control_names"], body.get("kind", "nominal")))
    return ok(robust.combined(body["data"], body["x_names"], body["z_names"], body["response"],
                              float(body.get("sigma_z2", 1)), body.get("target"), float(body.get("tol", 0)),
                              bool(body.get("quadratic"))))


# ------------------------------------------------------------------ data import / examples / projects
@app.post("/api/import")
async def import_file(file: UploadFile = File(...), sheet: str | None = None):
    raw = await file.read()
    name = (file.filename or "").lower()
    sheets = None
    if name.endswith((".xlsx", ".xls")):
        xl = pd.ExcelFile(io.BytesIO(raw))
        sheets = xl.sheet_names
        df = xl.parse(sheet or sheets[0])
    else:
        text = raw.decode("utf-8-sig", errors="replace")
        sep = "\t" if text.count("\t") > text.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    return ok({"columns": list(df.columns), "rows": df.replace({np.nan: None}).to_dict(orient="records"),
               "sheets": sheets})


@app.get("/api/examples")
def examples():
    with open(os.path.join(EXAMPLES, "examples.json"), encoding="utf-8") as f:
        ex = json.load(f)
    return [{k: e.get(k) for k in ("id", "title", "subtitle", "lane", "analysis_id")} for e in ex]


@app.get("/api/examples/{ex_id}")
def example(ex_id: str):
    with open(os.path.join(EXAMPLES, "examples.json"), encoding="utf-8") as f:
        ex = {e["id"]: e for e in json.load(f)}
    if ex_id not in ex:
        raise HTTPException(404, "No such example")
    e = dict(ex[ex_id])
    df = pd.read_csv(os.path.join(EXAMPLES, e["file"]))
    e["columns"] = list(df.columns)
    e["rows"] = df.replace({np.nan: None}).to_dict(orient="records")
    return ok(e)


@app.post("/api/project/save")
def project_save(body: dict):
    """Build a .dlab file: a zip with project.json, data/*.csv and report/."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        proj = {k: v for k, v in body.items() if k not in ("datasets",)}
        z.writestr("project.json", json.dumps(proj, indent=2, default=str))
        for name, ds in (body.get("datasets") or {}).items():
            df = pd.DataFrame(ds.get("rows", []), columns=ds.get("columns"))
            z.writestr(f"data/{name}.csv", df.to_csv(index=False))
            z.writestr(f"data/{name}.meta.json", json.dumps({k: v for k, v in ds.items() if k != "rows"}))
        if body.get("report_html"):
            z.writestr("report/report.html", body["report_html"])
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="project.dlab"'})


@app.post("/api/project/open")
async def project_open(file: UploadFile = File(...)):
    raw = await file.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        proj = json.loads(z.read("project.json"))
        datasets = {}
        for n in z.namelist():
            if n.startswith("data/") and n.endswith(".csv"):
                key = n[5:-4]
                df = pd.read_csv(io.BytesIO(z.read(n)))
                meta = {}
                if f"data/{key}.meta.json" in z.namelist():
                    meta = json.loads(z.read(f"data/{key}.meta.json"))
                datasets[key] = {**meta, "columns": list(df.columns),
                                 "rows": df.replace({np.nan: None}).to_dict(orient="records")}
        proj["datasets"] = datasets
    return ok(proj)


@app.post("/api/report/pdf")
def report_pdf(body: dict):
    html = body.get("html", "")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise HTTPException(501, "Playwright is not installed; use the browser's Print → Save as PDF instead.")
    try:
        with sync_playwright() as p:
            exe = os.environ.get("DESIGNLAB_CHROMIUM")
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            pdf = page.pdf(format="A4", print_background=True,
                           margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
            browser.close()
    except Exception as e:  # browser binary missing, etc.
        raise HTTPException(501, f"PDF export needs Chromium for Playwright ({e}). Use Print → Save as PDF instead.")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="DesignLab_report.pdf"'})


# ------------------------------------------------------------------ frontend
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = os.path.join(DIST, full_path)
        if full_path and os.path.isfile(f):
            return FileResponse(f)
        return FileResponse(os.path.join(DIST, "index.html"))
