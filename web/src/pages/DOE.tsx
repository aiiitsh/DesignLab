import { useEffect, useState } from "react";
import { api, download, toCSV } from "../api";
import DataGrid, { coerce } from "../components/DataGrid";
import Plot from "../components/Plot";
import { fmt, tableHtml } from "../components/Results";
import { Dataset, useStore } from "../store";

const LETTERS = "ABCDEFGHJKLMNOP".split("");
const ds = (columns: string[], rows: any[]): Dataset => ({ columns, types: Object.fromEntries(columns.map((c) => [c, c === "Run label" ? "nominal" : "scale"])) as any, rows });

function Tbl({ title, columns, rows }: { title: string; columns: string[]; rows: any[][] }) {
  return (
    <div className="tbl-wrap"><table className="res"><caption>{title}</caption>
      <thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{typeof v === "number" ? fmt(v, columns[j]) : v ?? ""}</td>)}</tr>)}</tbody></table></div>
  );
}

function effectPlots(r: any) {
  const ME = r.lenth?.ME;
  const normal = { data: [{ type: "scatter", mode: "markers+text", x: r.normal_plot.map((p: any) => p.effect), y: r.normal_plot.map((p: any) => p.z), text: r.normal_plot.map((p: any) => p.term), textposition: "middle right", marker: { color: "#0d8a87", size: 8 } }],
    layout: { title: { text: "Normal probability plot of effects" }, xaxis: { title: { text: "Effect" } }, yaxis: { title: { text: "Normal quantile" } }, showlegend: false,
      shapes: ME ? [-ME, ME].map((x) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", color: "#e0532c" } })) : [] } };
  const half = { data: [{ type: "scatter", mode: "markers+text", x: r.half_normal_plot.map((p: any) => p.abs_effect), y: r.half_normal_plot.map((p: any) => p.z), text: r.half_normal_plot.map((p: any) => p.term), textposition: "middle right", marker: { color: "#2483cc", size: 8 } }],
    layout: { title: { text: "Half-normal plot (Lenth ME dotted)" }, xaxis: { title: { text: "|Effect|" } }, yaxis: { title: { text: "Half-normal quantile" } }, showlegend: false,
      shapes: ME ? [{ type: "line", x0: ME, x1: ME, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", color: "#e0532c" } }] : [] } };
  const sorted = [...r.effects].sort((a: any, b: any) => Math.abs(b.effect) - Math.abs(a.effect));
  const pareto = { data: [{ type: "bar", orientation: "h", y: sorted.map((e: any) => e.term).reverse(), x: sorted.map((e: any) => Math.abs(e.effect)).reverse(), marker: { color: sorted.map((e: any) => (Math.abs(e.effect) > (ME ?? Infinity) ? "#e0532c" : "#2483cc")).reverse() } }],
    layout: { title: { text: "Pareto chart of |effects|" }, height: 360, showlegend: false, shapes: ME ? [{ type: "line", x0: ME, x1: ME, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", color: "#e0532c" } }] : [] } };
  return [normal, half, pareto];
}

function TwoK() {
  const { project, pin, toast } = useStore();
  const ex = project.example?.doe?.type === "2k" ? project.example : null;
  const [k, setK] = useState(ex?.doe.k ?? 3);
  const [reps, setReps] = useState(1);
  const [center, setCenter] = useState(0);
  const [seed, setSeed] = useState(640);
  const [sheet, setSheet] = useState<Dataset | null>(null);
  const [res, setRes] = useState<any>(null);
  const [terms, setTerms] = useState<string[] | null>(null);
  const [drop, setDrop] = useState(ex?.doe.drop ?? "");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (ex) {
      const rows = project.data.rows.map((r: any) => ({ ...r, y: r[ex.doe.response] }));
      setSheet(ds(["Run label", ...LETTERS.slice(0, ex.doe.k), "y"], rows.map((r: any) => ({ "Run label": "", ...r }))));
    }
  }, [ex?.id]);

  const generate = async () => {
    const g = await api("/api/doe/design", { type: "2k", k, replicates: reps, center, seed });
    setSheet(ds(["Std order", "Run order", "Run label", ...g.factor_letters, "y"], g.runs.map((r: any) => ({ ...r, y: "" }))));
    setRes(null);
  };
  const analyze = async (mt?: string[] | null, dr?: string) => {
    setErr("");
    try {
      const data = coerce(sheet!).filter((r) => r.y !== null);
      const r = await api("/api/doe/analyze", { type: "2k", k, data, response: "y", model_terms: mt ?? undefined, drop: dr || undefined });
      setRes(r);
      setTerms(r.model_terms);
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <div>
      <div className="card role-indigo">
        <h3>Two-level factorial 2ᵏ (Meeting 10)</h3>
        <div className="row">
          <label className="field">Factors k<input type="number" min={2} max={7} value={k} onChange={(e) => setK(Number(e.target.value))} /></label>
          <label className="field">Replicates<input type="number" min={1} value={reps} onChange={(e) => setReps(Number(e.target.value))} /></label>
          <label className="field">Centre points<input type="number" min={0} value={center} onChange={(e) => setCenter(Number(e.target.value))} /></label>
          <label className="field">Seed<input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} /></label>
          <button className="btn" onClick={generate}>Generate run sheet ({2 ** k * reps + center} runs)</button>
          {sheet && <button className="btn" onClick={() => download("run_sheet.csv", toCSV(sheet.columns, coerce(sheet)), "text/csv")}>Download CSV</button>}
        </div>
        <p className="small muted">Standard order (1), a, b, ab, c, … with a seeded random run order. Enter the responses in the y column (or paste them), then analyse. Sensitivity tips: more replicates, levels farther apart, a DV free of ceiling/floor effects.</p>
      </div>
      {sheet && (
        <>
          <DataGrid ds={sheet} onChange={setSheet} />
          <div className="row" style={{ margin: "12px 0" }}><button className="btn primary" onClick={() => analyze(null)}>▶ Estimate effects</button></div>
        </>
      )}
      {err && <div className="err">{err}</div>}
      {res && (
        <>
          <div className="card role-teal">
            <div className="card-head"><h3>Effect estimates</h3><button className="btn small" onClick={() => pin({ title: "2^k effects", kind: "table", html: tableHtml({ title: "Effect estimates", columns: ["Term", "Effect", "Coefficient", "SS", "% contribution"], rows: res.effects.map((e: any) => [e.term, e.effect, e.coef, e.ss, e.pct]), footnotes: [] }) })}>📌 Pin</button></div>
            <Tbl title={`N = ${res.N} runs, ${res.replicates} replicate(s). Lenth PSE = ${fmt(res.lenth.PSE)}, ME = ${fmt(res.lenth.ME)}`} columns={["Term", "Contrast", "Effect", "Coefficient", "SS", "% contribution", "In model"]}
              rows={res.effects.map((e: any) => [e.term, e.contrast, e.effect, e.coef, e.ss, e.pct,
                <input key={e.term} type="checkbox" aria-label={`Keep ${e.term}`} checked={terms?.includes(e.term) ?? false} onChange={(ev) => setTerms(ev.target.checked ? [...(terms ?? []), e.term] : (terms ?? []).filter((t) => t !== e.term))} />])} />
            <p className="small">Effect = ȳ₊ − ȳ₋; SS = N·effect²/4; an interaction's sign is the product of its factors' signs. Lenth's active terms: <b>{res.lenth_active.join(", ") || "none"}</b>.</p>
            <div className="row">
              <button className="btn" onClick={() => analyze(terms)}>Refit reduced model with ticked terms</button>
              <label className="field">Drop an inactive factor (collapse to 2ᵏ⁻¹ with replicates)
                <select value={drop} onChange={(e) => setDrop(e.target.value)}><option value="">–</option>{LETTERS.slice(0, k).map((l) => <option key={l}>{l}</option>)}</select></label>
              <button className="btn" disabled={!drop} onClick={() => analyze(terms, drop)}>Collapse and run ANOVA</button>
            </div>
          </div>
          <div className="grid3">{effectPlots(res).map((p, i) => <div className="card" key={i}><Plot fig={p} /></div>)}</div>
          <div className="card role-teal">
            <h3>ANOVA (model terms: {res.model_terms.join(", ") || "none"})</h3>
            {res.df_error > 0 ? <Tbl title="Analysis of variance" columns={["Source", "SS", "df", "MS", "F", "p"]} rows={res.anova.map((a: any) => [a.term, a.ss, a.df, a.ms, a.F, a.p == null ? "" : a.p < 0.001 ? "< .001" : a.p.toFixed(3)])} /> : <div className="warn">No error df (single replicate, full model). Judge the effects with the normal/half-normal plot and % contribution, then tick a reduced model.</div>}
            <p className="mono small">{res.equation_coded}</p>
            {res.curvature && <div className="warn">Curvature test (centre points): F(1, {res.curvature.df[1]}) = {fmt(res.curvature.F)}, p = {res.curvature.p.toFixed(3)} → {res.curvature.p < 0.05 ? "significant curvature: move to a second-order (RSM) design" : "no evidence of curvature"}.</div>}
          </div>
          {res.collapsed && (
            <div className="card role-sky">
              <h3>Collapsed design: {drop} dropped → 2^{k - 1} with {res.collapsed.replicates} replicates</h3>
              <Tbl title="ANOVA" columns={["Source", "SS", "df", "MS", "F", "p"]} rows={res.collapsed.anova.map((a: any) => [a.term, a.ss, a.df, a.ms, a.F, a.p == null ? "" : a.p < 0.001 ? "< .001" : a.p.toFixed(3)])} />
              <button className="btn small" onClick={() => { pin({ title: `Collapsed ANOVA (drop ${drop})`, kind: "table", html: tableHtml({ title: "ANOVA", columns: ["Source", "SS", "df", "MS", "F", "p"], rows: res.collapsed.anova.map((a: any) => [a.term, a.ss, a.df, a.ms, a.F, a.p == null ? "" : a.p.toFixed(3)]), footnotes: [] }) }); toast("Pinned"); }}>📌 Pin</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Fraction() {
  const { project, pin } = useStore();
  const ex = project.example?.doe?.type === "fraction" ? project.example : null;
  const [k, setK] = useState(ex?.doe.k ?? 4);
  const [p, setP] = useState(1);
  const [gens, setGens] = useState("");
  const [design, setDesign] = useState<any>(null);
  const [sheet, setSheet] = useState<Dataset | null>(null);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");
  const relation = () => design?.defining_relation?.replace(/−/g, "-").split(" = ").slice(0, (design?.generators?.length ?? 1) + 1).join("=") ?? ex?.doe.relation;

  useEffect(() => {
    if (ex) {
      setSheet(ds([...LETTERS.slice(0, ex.doe.k), "y"], project.data.rows.map((r: any) => ({ ...r, y: r[ex.doe.response] }))));
      setDesign({ defining_relation: ex.doe.relation.replace("=", " = "), generators: ["x"], resolution_roman: "", aliases: [] });
    }
  }, [ex?.id]);

  const make = async (g?: string[]) => {
    setErr("");
    try {
      const d = await api("/api/doe/design", { type: "fraction", k, p, generators: g ?? (gens.trim() ? gens.split(",").map((x) => x.trim()) : undefined) });
      setDesign(d);
      setSheet(ds(["Std order", "Run order", "Run label", ...d.factor_letters, "y"], d.runs.map((r: any) => ({ ...r, y: "" }))));
      setRes(null);
    } catch (e: any) { setErr(e.message); }
  };
  const analyze = async () => {
    setErr("");
    try {
      const gensList = design?.generators?.[0] !== "x" ? design.generators : undefined;
      setRes(await api("/api/doe/analyze", { type: "fraction", k, relation: gensList ? undefined : ex?.doe.relation, generators: gensList, data: coerce(sheet!).filter((r) => r.y !== null), response: "y" }));
    } catch (e: any) { setErr(e.message); }
  };
  const foldover = () => {
    const g = (design?.generators ?? []).map((x: string) => { const [n, w] = x.replace(/\s/g, "").split("="); return w.startsWith("-") ? `${n}=${w.slice(1)}` : `${n}=-${w}`; });
    setGens(g.join(", "));
    make(g);
  };
  return (
    <div>
      <div className="card role-indigo">
        <h3>Fractional factorial 2ᵏ⁻ᵖ (Meeting 11)</h3>
        <div className="row">
          <label className="field">k factors<input type="number" min={3} max={11} value={k} onChange={(e) => setK(Number(e.target.value))} /></label>
          <label className="field">p (1 = half, 2 = quarter…)<input type="number" min={1} max={7} value={p} onChange={(e) => setP(Number(e.target.value))} /></label>
          <label className="field" style={{ flex: 1 }}>Generators (blank = Montgomery Table XII; e.g. D=ABC or E=-ABCD)<input type="text" value={gens} onChange={(e) => setGens(e.target.value)} /></label>
          <button className="btn" onClick={() => make()}>Build design ({2 ** (k - p)} runs)</button>
          {design?.generators?.[0] !== "x" && design && <button className="btn" onClick={foldover}>Other half (fold-over)</button>}
        </div>
      </div>
      {err && <div className="err">{err}</div>}
      {design && (
        <div className="card role-teal">
          <h3>Defining relation and aliases</h3>
          <p><b className="mono">{design.defining_relation}</b> {design.resolution_roman && <span className="pill">Resolution {design.resolution_roman}</span>}</p>
          {design.aliases?.length > 0 && <Tbl title="Alias structure (up to 3-factor interactions)" columns={["Effect", "Alias chain"]} rows={design.aliases.map((a: any) => [a.effect, a.chain])} />}
          <p className="small muted">Multiply by I and cancel squares (A·A = I). Credit a large estimate to the lower-order effect. Running the other half (I = −…) and combining both halves gives back the full factorial and de-aliases the effects.</p>
        </div>
      )}
      {sheet && (<><DataGrid ds={sheet} onChange={setSheet} /><div className="row" style={{ margin: "12px 0" }}><button className="btn primary" onClick={analyze}>▶ Estimate effects</button></div></>)}
      {res && (
        <div className="card role-sky">
          <div className="card-head"><h3>Effect estimates ({res.defining_relation})</h3><button className="btn small" onClick={() => pin({ title: "Fractional factorial estimates", kind: "table", html: tableHtml({ title: res.defining_relation, columns: ["Alias chain", "Estimate"], rows: res.estimates.map((e: any) => [e.chain, e.estimate]), footnotes: [] }) })}>📌 Pin</button></div>
          <Tbl title="Estimates = contrast / (N/2)" columns={["Alias chain", "Estimate"]} rows={res.estimates.map((e: any) => [e.chain, e.estimate])} />
          <Plot fig={{ data: [{ type: "bar", x: res.estimates.map((e: any) => `[${e.effect}]`), y: res.estimates.map((e: any) => e.estimate), marker: { color: "#2483cc" } }], layout: { title: { text: "Estimates" }, showlegend: false } }} />
        </div>
      )}
    </div>
  );
}

function Calculators() {
  const [runs, setRuns] = useState({ k: 6, p: 2 });
  const [rel, setRel] = useState("I=-ABCDE");
  const [effect, setEffect] = useState("BCE");
  const [known, setKnown] = useState("A=+, B=-, C=+, D=+");
  const [target, setTarget] = useState("E");
  const [out, setOut] = useState<any>(null);
  const [err, setErr] = useState("");
  const go = async () => {
    setErr("");
    try {
      const kn = Object.fromEntries(known.split(",").map((s) => s.trim()).filter(Boolean).map((s) => { const [a, b] = s.split("="); return [a.trim().toUpperCase(), b.trim().startsWith("-") || b.trim().startsWith("−") ? -1 : 1]; }));
      setOut(await api("/api/doe/alias", { relation: rel, effect, known: kn, target: target.toUpperCase() }));
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="grid2">
      <div className="card role-amber">
        <h3>Number of runs</h3>
        <div className="row"><label className="field">k<input type="number" value={runs.k} onChange={(e) => setRuns({ ...runs, k: Number(e.target.value) })} /></label>
          <label className="field">p<input type="number" value={runs.p} onChange={(e) => setRuns({ ...runs, p: Number(e.target.value) })} /></label>
          <div className="kpi">2^{runs.k}{runs.p ? `−${runs.p}` : ""} = {2 ** (runs.k - runs.p)}</div></div>
      </div>
      <div className="card role-amber">
        <h3>Alias and missing-level calculator (midterm style)</h3>
        <div className="grid2" style={{ gap: 8 }}>
          <label className="field">Defining relation<input type="text" value={rel} onChange={(e) => setRel(e.target.value)} /></label>
          <label className="field">Alias of effect<input type="text" value={effect} onChange={(e) => setEffect(e.target.value)} /></label>
          <label className="field">Known levels in the run<input type="text" value={known} onChange={(e) => setKnown(e.target.value)} /></label>
          <label className="field">Missing factor<input type="text" value={target} onChange={(e) => setTarget(e.target.value)} /></label>
        </div>
        <button className="btn primary" style={{ marginTop: 8 }} onClick={go}>Calculate</button>
        {err && <div className="err">{err}</div>}
        {out && (
          <div style={{ marginTop: 10 }}>
            <p><b className="mono">{out.defining_relation}</b> · resolution {out.resolution} · {out.runs} runs</p>
            {out.aliases && <p>{effect.toUpperCase()} is aliased with <b>{out.aliases.join(", ")}</b></p>}
            {out.level !== undefined && <p>{target.toUpperCase()} = <b>{out.level > 0 ? "+" : "−"}</b> in this run</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function RSM() {
  const [cv, setCv] = useState({ f: "39.3, 40.9, 40.0, 41.5", c: "40.3, 40.5, 40.7, 40.2, 40.6" });
  const [cvOut, setCvOut] = useState<any>(null);
  const [st, setSt] = useState({ coefs: "x1=0.775, x2=0.325", step: 1, n: 10, centers: "35, 155", halfs: "5, 5" });
  const [stOut, setStOut] = useState<any>(null);
  const [kD, setKD] = useState(2);
  const [kind, setKind] = useState("ccd");
  const [alpha, setAlpha] = useState("rotatable");
  const [nc, setNc] = useState(5);
  const [sheet, setSheet] = useState<Dataset | null>(null);
  const [fit, setFit] = useState<any>(null);
  const [err, setErr] = useState("");
  const nums = (s: string) => s.split(",").map((x) => Number(x.trim())).filter((x) => !isNaN(x));
  return (
    <div>
      <div className="grid2">
        <div className="card role-indigo">
          <h3>Step 1 · Curvature test (centre points)</h3>
          <label className="field">Factorial-point responses<input type="text" value={cv.f} onChange={(e) => setCv({ ...cv, f: e.target.value })} /></label>
          <label className="field">Centre-point responses<input type="text" value={cv.c} onChange={(e) => setCv({ ...cv, c: e.target.value })} /></label>
          <button className="btn" style={{ marginTop: 8 }} onClick={async () => setCvOut(await api("/api/doe/rsm", { action: "curvature", y_factorial: nums(cv.f), y_center: nums(cv.c) }))}>Test</button>
          {cvOut && <p>SS<sub>curvature</sub> = n<sub>F</sub>n<sub>C</sub>(ȳ<sub>F</sub> − ȳ<sub>C</sub>)²/(n<sub>F</sub> + n<sub>C</sub>) = {fmt(cvOut.ss_curvature)}; F(1, {cvOut.df[1]}) = {fmt(cvOut.F)}, p = {cvOut.p.toFixed(3)} → <b>{cvOut.p < 0.05 ? "curvature: use a second-order design" : "no curvature: first-order model / steepest ascent"}</b></p>}
        </div>
        <div className="card role-indigo">
          <h3>Step 2 · Path of steepest ascent</h3>
          <div className="grid2" style={{ gap: 8 }}>
            <label className="field">First-order coefficients (coded)<input type="text" value={st.coefs} onChange={(e) => setSt({ ...st, coefs: e.target.value })} /></label>
            <label className="field">Step in the base variable (coded)<input type="number" value={st.step} onChange={(e) => setSt({ ...st, step: Number(e.target.value) })} /></label>
            <label className="field">Centres (real units)<input type="text" value={st.centers} onChange={(e) => setSt({ ...st, centers: e.target.value })} /></label>
            <label className="field">Half-ranges (real units)<input type="text" value={st.halfs} onChange={(e) => setSt({ ...st, halfs: e.target.value })} /></label>
          </div>
          <button className="btn" style={{ marginTop: 8 }} onClick={async () => {
            const coefs = Object.fromEntries(st.coefs.split(",").map((s) => s.split("=").map((x) => x.trim())).map(([a, b]) => [a, Number(b)]));
            setStOut(await api("/api/doe/rsm", { action: "steepest", coefs, step: st.step, n_steps: st.n, centers: nums(st.centers), halfs: nums(st.halfs) }));
          }}>Compute path</button>
          {stOut && <Tbl title={`Base variable ${stOut.base}`} columns={Object.keys(stOut.path[0])} rows={stOut.path.map((r: any) => Object.values(r))} />}
          <p className="small muted">Run experiments along the path; when the response stops improving, fit a new first-order model there.</p>
        </div>
      </div>
      <div className="card role-teal">
        <h3>Step 3 · Second-order design and model</h3>
        <div className="row">
          <select value={kind} onChange={(e) => setKind(e.target.value)}><option value="ccd">Central composite (CCD)</option><option value="bbd">Box-Behnken</option></select>
          <label className="field">Factors<input type="number" min={2} max={6} value={kD} onChange={(e) => setKD(Number(e.target.value))} /></label>
          {kind === "ccd" && <label className="field" data-help="Axial distance of the star points in a CCD. Rotatable = (2ᵏ)^¼ gives equal prediction variance at equal distance from the centre; face-centred = 1 keeps every run inside the cube.">α<select value={alpha} onChange={(e) => setAlpha(e.target.value)}><option value="rotatable">Rotatable (2ᵏ)^¼</option><option value="face">Face-centred (1)</option><option value="orthogonal">Orthogonal</option></select></label>}
          <label className="field">Centre points<input type="number" value={nc} onChange={(e) => setNc(Number(e.target.value))} /></label>
          <button className="btn" onClick={async () => {
            const d = await api("/api/doe/design", { type: kind, k: kD, alpha, center: nc });
            const xc = Array.from({ length: kD }, (_, i) => `x${i + 1}`);
            setSheet(ds([...xc, "y"], d.runs.map((r: any) => ({ ...r, y: "" }))));
            setFit(null);
          }}>Generate design</button>
          <button className="btn" onClick={() => {
            const ex = [[-1, -1, 76.5], [-1, 1, 77.0], [1, -1, 78.0], [1, 1, 79.5], [0, 0, 79.9], [0, 0, 80.3], [0, 0, 80.0], [0, 0, 79.7], [0, 0, 79.8], [1.414, 0, 78.4], [-1.414, 0, 75.6], [0, 1.414, 78.5], [0, -1.414, 77.0]];
            setKD(2); setSheet(ds(["x1", "x2", "y"], ex.map(([a, b, c]) => ({ x1: a, x2: b, y: c })))); setFit(null);
          }}>Load Montgomery Ex. 11.2</button>
        </div>
        {sheet && <><div style={{ marginTop: 10 }}><DataGrid ds={sheet} onChange={setSheet} /></div>
          <button className="btn primary" style={{ marginTop: 10 }} onClick={async () => {
            setErr("");
            try { setFit(await api("/api/doe/rsm", { action: "fit", data: coerce(sheet).filter((r) => r.y !== null), xcols: sheet.columns.filter((c) => c !== "y"), response: "y" })); } catch (e: any) { setErr(e.message); }
          }}>▶ Fit second-order model</button></>}
        {err && <div className="err">{err}</div>}
        {fit && (
          <div style={{ marginTop: 12 }}>
            <Tbl title={`Coefficients (R² = ${fmt(fit.r2)}, adj. R² = ${fmt(fit.r2_adj)})`} columns={["Term", "Estimate", "SE", "t", "p"]} rows={fit.coefficients.map((c: any) => [c[0], c[1], c[2], c[3], c[4] < 0.001 ? "< .001" : c[4].toFixed(3)])} />
            <Tbl title="ANOVA" columns={["Source", "SS", "df", "MS", "F", "p"]} rows={fit.anova.map((a: any) => [a[0], a[1], a[2], a[3], a[4], a[5] == null ? "" : a[5] < 0.001 ? "< .001" : a[5].toFixed(3)])} />
            {fit.stationary_point && <p>Stationary point x<sub>s</sub> = −½B⁻¹b = ({fit.stationary_point.map((v: number) => fmt(v)).join(", ")}), ŷ<sub>s</sub> = {fmt(fit.y_stationary)}. Eigenvalues {fit.eigenvalues.map((v: number) => fmt(v)).join(", ")} → <b>{fit.nature}</b>.</p>}
            {fit.surface && <div className="grid2">
              <Plot fig={{ data: [{ type: "contour", x: fit.surface.x, y: fit.surface.y, z: fit.surface.z, colorscale: "Viridis", contours: { showlabels: true } }], layout: { title: { text: "Contour plot (x1, x2)" }, xaxis: { title: { text: "x1" } }, yaxis: { title: { text: "x2" } } } }} height={380} />
              <Plot fig={{ data: [{ type: "surface", x: fit.surface.x, y: fit.surface.y, z: fit.surface.z, colorscale: "Viridis", showscale: false }], layout: { title: { text: "Response surface" }, scene: { xaxis: { title: { text: "x1" } }, yaxis: { title: { text: "x2" } } } } }} height={380} />
            </div>}
          </div>
        )}
      </div>
    </div>
  );
}

function Robust() {
  const [mode, setMode] = useState<"crossed" | "combined">("crossed");
  const [oa, setOa] = useState("L4");
  const [controls, setControls] = useState("A, B, C");
  const [nOuter, setNOuter] = useState(4);
  const [kind, setKind] = useState("nominal");
  const [sheet, setSheet] = useState<Dataset | null>(null);
  const [out, setOut] = useState<any>(null);
  const [cb, setCb] = useState({ x: "x1, x2", z: "z1", target: "", tol: 1, s2: 1 });
  const [err, setErr] = useState("");
  const names = controls.split(",").map((s) => s.trim()).filter(Boolean);
  return (
    <div>
      <div className="tabs"><button className={`tab ${mode === "crossed" ? "active" : ""}`} onClick={() => setMode("crossed")}>(a) Crossed array (Taguchi)</button><button className={`tab ${mode === "combined" ? "active" : ""}`} onClick={() => setMode("combined")}>(b) Combined array (response model)</button></div>
      {mode === "crossed" ? (
        <div className="card role-indigo">
          <div className="row">
            <label className="field">Inner array<select value={oa} onChange={(e) => setOa(e.target.value)}>{["L4", "L8", "L9", "L12", "L16", "L27"].map((x) => <option key={x}>{x}</option>)}</select></label>
            <label className="field">Control factors (x)<input type="text" value={controls} onChange={(e) => setControls(e.target.value)} /></label>
            <label className="field">Outer-array runs (noise conditions)<input type="number" value={nOuter} onChange={(e) => setNOuter(Number(e.target.value))} /></label>
            <label className="field">SN ratio<select value={kind} onChange={(e) => setKind(e.target.value)}><option value="smaller">Smaller-the-better</option><option value="larger">Larger-the-better</option><option value="nominal">Nominal-the-best</option></select></label>
            <button className="btn" onClick={async () => {
              const a = await api("/api/doe/design", { type: "oa", name: oa });
              const cols = [...names, ...Array.from({ length: nOuter }, (_, i) => `y${i + 1}`)];
              setSheet(ds(cols, a.array.map((r: number[]) => Object.fromEntries(names.map((n, i) => [n, r[i]])))));
              setOut(null);
            }}>Build inner × outer sheet</button>
          </div>
          {sheet && <><div style={{ marginTop: 10 }}><DataGrid ds={sheet} onChange={setSheet} /></div>
            <button className="btn primary" style={{ marginTop: 10 }} onClick={async () => {
              setErr("");
              try {
                const rows = coerce(sheet).filter((r) => r[names[0]] !== null);
                const ys = sheet.columns.filter((c) => /^y\d+$/.test(c));
                setOut(await api("/api/doe/robust", { mode: "crossed", inner: rows.map((r) => names.map((n) => r[n])), outer_responses: rows.map((r) => ys.map((y) => r[y])), control_names: names, kind }));
              } catch (e: any) { setErr(e.message); }
            }}>▶ Analyse</button></>}
          {err && <div className="err">{err}</div>}
          {out && (
            <div style={{ marginTop: 12 }}>
              <Tbl title="Per inner run" columns={["Run", "ȳ", "s", "ln s²", "SN"]} rows={out.run_stats.map((r: any) => [r.run, r.ybar, r.s, r.ln_s2, r.SN])} />
              <div className="grid2">
                <Plot fig={{ data: names.map((n, i) => ({ type: "scatter", mode: "lines+markers", x: out.effects[n].levels.map((l: string) => `${n}${l}`), y: out.effects[n].SN, name: n })), layout: { title: { text: "Main effects on the SN ratio" } } }} />
                <Plot fig={{ data: names.map((n) => ({ type: "scatter", mode: "lines+markers", x: out.effects[n].levels.map((l: string) => `${n}${l}`), y: out.effects[n].mean, name: n })), layout: { title: { text: "Main effects on the mean" } } }} />
              </div>
              <p><b>Settings that maximize SN:</b> {Object.entries(out.best_SN_settings).map(([k, v]) => `${k} = ${v}`).join(", ")}. {out.adjustment_candidates.length > 0 && <>Adjustment factor candidates (move the mean, little effect on SN): <b>{out.adjustment_candidates.join(", ")}</b>.</>}</p>
              <div className="warn">{out.caveat}</div>
            </div>
          )}
        </div>
      ) : (
        <div className="card role-indigo">
          <div className="row">
            <label className="field">Control factors x<input type="text" value={cb.x} onChange={(e) => setCb({ ...cb, x: e.target.value })} /></label>
            <label className="field">Noise factors z<input type="text" value={cb.z} onChange={(e) => setCb({ ...cb, z: e.target.value })} /></label>
            <label className="field">σ_z² (coded)<input type="number" value={cb.s2} onChange={(e) => setCb({ ...cb, s2: Number(e.target.value) })} /></label>
            <label className="field">Mean target (optional)<input type="text" value={cb.target} onChange={(e) => setCb({ ...cb, target: e.target.value })} /></label>
            <label className="field">± tolerance<input type="number" value={cb.tol} onChange={(e) => setCb({ ...cb, tol: Number(e.target.value) })} /></label>
            <button className="btn" onClick={async () => {
              const xs = cb.x.split(",").map((s) => s.trim()), zs = cb.z.split(",").map((s) => s.trim());
              const k = xs.length + zs.length;
              const d = await api("/api/doe/design", { type: "2k", k, replicates: 1, center: 0 });
              const L = d.factor_letters;
              setSheet(ds([...xs, ...zs, "y"], d.runs.map((r: any) => ({ ...Object.fromEntries([...xs, ...zs].map((n, i) => [n, r[L[i]]])), y: "" }))));
            }}>Build combined 2ᵏ array</button>
          </div>
          {sheet && <><div style={{ marginTop: 10 }}><DataGrid ds={sheet} onChange={setSheet} /></div>
            <button className="btn primary" style={{ marginTop: 10 }} onClick={async () => {
              setErr("");
              try {
                setOut(await api("/api/doe/robust", { mode: "combined", data: coerce(sheet).filter((r) => r.y !== null), x_names: cb.x.split(",").map((s) => s.trim()), z_names: cb.z.split(",").map((s) => s.trim()), response: "y", sigma_z2: cb.s2, target: cb.target ? Number(cb.target) : undefined, tol: cb.tol }));
              } catch (e: any) { setErr(e.message); }
            }}>▶ Fit response model</button></>}
          {err && <div className="err">{err}</div>}
          {out && out.params && (
            <div style={{ marginTop: 12 }}>
              <p className="mono">{out.mean_model}</p><p className="mono">{out.variance_model}, σ² = MSE = {fmt(out.mse)}</p>
              <Tbl title="Control × noise interactions (they make robustness possible)" columns={["Term", "Estimate", "p"]} rows={out.control_noise_interactions.map((t: any) => [t.term, t.estimate, t.p < 0.001 ? "< .001" : t.p.toFixed(3)])} />
              {out.optimum && <p><b>Robust setting:</b> x = ({out.optimum.x.map((v: number) => v.toFixed(2)).join(", ")}), mean {fmt(out.optimum.mean)}, SD {fmt(out.optimum.sd)}.</p>}
              {out.contours && <div className="grid2">
                <Plot fig={{ data: [{ type: "contour", x: out.contours.x, y: out.contours.y, z: out.contours.mean, colorscale: "Blues", contours: { showlabels: true } }], layout: { title: { text: "Mean model" } } }} />
                <Plot fig={{ data: [{ type: "contour", x: out.contours.x, y: out.contours.y, z: out.contours.sd, colorscale: "Oranges", contours: { showlabels: true } }], layout: { title: { text: "SD model" } } }} />
              </div>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function DOE() {
  const { project } = useStore();
  const exType = project.example?.doe?.type;
  const [tab, setTab] = useState(exType === "fraction" ? "frac" : "2k");
  return (
    <div>
      <h1 className="page-title">Engineering DOE workspace (Lane D)</h1>
      <p className="page-sub">Screen → optimize → make robust. 2ᵏ designs are for screening (early engineering, linear effects), not for finding causal mechanisms.</p>
      <div className="tabs">
        {[["2k", "2ᵏ factorial"], ["frac", "Fractional 2ᵏ⁻ᵖ"], ["calc", "Calculators"], ["rsm", "Response surface"], ["robust", "Robust design"]].map(([k, l]) => (
          <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "2k" && <TwoK />}
      {tab === "frac" && <Fraction />}
      {tab === "calc" && <Calculators />}
      {tab === "rsm" && <RSM />}
      {tab === "robust" && <Robust />}
    </div>
  );
}
