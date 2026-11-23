import { useEffect, useState } from "react";
import { api } from "../api";
import Plot from "./Plot";
import { useStore } from "../store";

const EXTRA: Record<string, { key: string; label: string; def: number; help?: string }[]> = {
  ttest_ind: [{ key: "ratio", label: "Allocation ratio N2/N1", def: 1 }, { key: "tails", label: "Tails (1 or 2)", def: 2 }],
  ttest_paired: [{ key: "tails", label: "Tails (1 or 2)", def: 2 }],
  anova_oneway: [{ key: "k", label: "Number of groups", def: 3 }],
  anova_special: [{ key: "df1", label: "Numerator df (effect df)", def: 1, help: "e.g. (a − 1)(b − 1) for an interaction" }, { key: "cells", label: "Number of groups (cells)", def: 4, help: "a × b cells" }],
  rm_within: [{ key: "groups", label: "Number of groups", def: 1, help: "combinations of the between factors" }, { key: "m", label: "Number of measurements", def: 3, help: "combinations of the within factors (3 × 3 → 9)" }, { key: "rho", label: "Corr among rep measures ρ", def: 0.5 }, { key: "eps", label: "Nonsphericity correction ε", def: 1 }],
  rm_between: [{ key: "groups", label: "Number of groups", def: 2 }, { key: "m", label: "Number of measurements", def: 3 }, { key: "rho", label: "Corr among rep measures ρ", def: 0.5 }],
  rm_interaction: [{ key: "groups", label: "Number of groups", def: 2 }, { key: "m", label: "Number of measurements", def: 3 }, { key: "rho", label: "Corr among rep measures ρ", def: 0.5 }, { key: "eps", label: "Nonsphericity correction ε", def: 1 }],
  reg_r2: [{ key: "predictors", label: "Number of predictors", def: 3 }],
  reg_r2_increase: [{ key: "tested", label: "Number of tested predictors", def: 1 }, { key: "predictors", label: "Total number of predictors", def: 3 }],
  chisq: [{ key: "df", label: "df", def: 1, help: "(rows − 1)(columns − 1)" }],
  logistic: [{ key: "p0", label: "Pr(Y = 1 | X = 1) under H₀", def: 0.5 }, { key: "tails", label: "Tails (1 or 2)", def: 2 }],
};
const ES_LABEL: Record<string, string> = { d: "Effect size d", dz: "Effect size d_z", f: "Effect size f", f2: "Effect size f²", w: "Effect size w", OR: "Odds ratio" };

export default function PowerCalc({ family: fam0, params0, compact }: { family?: string; params0?: Record<string, number>; compact?: boolean }) {
  const { pin, settings } = useStore();
  const [families, setFamilies] = useState<Record<string, any>>({});
  const [family, setFamily] = useState(fam0 || "ttest_ind");
  const [mode, setMode] = useState("apriori");
  const [p, setP] = useState<Record<string, number>>({});
  const [out, setOut] = useState<any>(null);
  const [err, setErr] = useState("");
  const [helper, setHelper] = useState({ m1: 0, m2: 0, sd1: 1, sd2: 1, r2: 0.13, peta: 0.06 });

  useEffect(() => { api("/api/power/families").then(setFamilies); }, []);
  useEffect(() => { if (fam0) setFamily(fam0); }, [fam0]);
  useEffect(() => {
    const f = families[family];
    if (!f) return;
    const base: Record<string, number> = { es: f.default, alpha: settings.alpha, power: 0.8, N: 50, n1: 13, n2: 13 };
    for (const e of EXTRA[family] || []) base[e.key] = e.def;
    setP({ ...base, ...(params0 || {}) });
    setOut(null);
  }, [family, families, JSON.stringify(params0)]);

  const run = async () => {
    setErr("");
    try {
      const params: Record<string, number> = { alpha: p.alpha };
      for (const e of EXTRA[family] || []) params[e.key] = p[e.key];
      if (mode !== "sensitivity") params.es = p.es;
      if (mode !== "posthoc") params.power = p.power;
      if (mode !== "apriori") {
        if (family === "ttest_ind") { params.n1 = p.n1; params.n2 = p.n2; } else params.N = p.N;
      }
      setOut(await api(`/api/power/${family}`, { mode, params }));
    } catch (e: any) { setErr(e.message); }
  };
  useEffect(() => { if (Object.keys(p).length) run(); }, [mode, family, JSON.stringify(p)]); // eslint-disable-line

  const f = families[family];
  const num = (key: string, label: string, step = 0.01, help?: string) => (
    <label className="field" key={key} title={help}>
      {label}{help && <span className="small">{help}</span>}
      <input type="number" step={step} value={p[key] ?? ""} onChange={(e) => setP({ ...p, [key]: Number(e.target.value) })} />
    </label>
  );
  const esName = f?.es ?? "d";

  return (
    <div className="grid2">
      <div className="card role-indigo">
        <h3>Input</h3>
        {!compact && (
          <label className="field">Test family / statistical test
            <select value={family} onChange={(e) => setFamily(e.target.value)}>
              {Object.entries(families).map(([k, v]: any) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </label>
        )}
        <div className="row" style={{ margin: "10px 0" }}>
          {[["apriori", "A priori: N"], ["posthoc", "Post hoc: power"], ["sensitivity", "Sensitivity: effect"], ["criterion", "Criterion: α"]].map(([m, l]) => (
            <button key={m} className={`btn small ${mode === m ? "amber" : ""}`} onClick={() => setMode(m)}>{l}</button>
          ))}
        </div>
        <div className="grid3" style={{ gap: 10 }}>
          {mode !== "sensitivity" && num("es", ES_LABEL[esName] ?? "Effect size")}
          {mode !== "criterion" && num("alpha", "α error probability", 0.005)}
          {mode !== "posthoc" && num("power", "Power (1 − β)", 0.01)}
          {mode !== "apriori" && (family === "ttest_ind" ? <>{num("n1", "Sample size group 1", 1)}{num("n2", "Sample size group 2", 1)}</> : num("N", "Total sample size", 1))}
          {(EXTRA[family] || []).map((e) => num(e.key, e.label, e.key === "rho" || e.key === "eps" || e.key === "p0" ? 0.05 : 1, e.help))}
        </div>
        {!compact && (
          <details className="why">
            <summary>Effect-size helper</summary>
            <div className="grid3" style={{ gap: 8, marginTop: 8 }}>
              {(["m1", "m2", "sd1", "sd2"] as const).map((k) => (
                <label className="field" key={k}>{k.toUpperCase()}<input type="number" value={helper[k]} onChange={(e) => setHelper({ ...helper, [k]: Number(e.target.value) })} /></label>
              ))}
              <button className="btn small" onClick={async () => { const r = await api("/api/power_helper/d", { m1: helper.m1, m2: helper.m2, sd1: helper.sd1, sd2: helper.sd2 }); setP({ ...p, es: Number(r.value.toFixed(3)) }); }}>d from means / SDs</button>
              <label className="field">R²<input type="number" step={0.01} value={helper.r2} onChange={(e) => setHelper({ ...helper, r2: Number(e.target.value) })} /></label>
              <button className="btn small" onClick={async () => { const r = await api("/api/power_helper/f2", { r2: helper.r2 }); setP({ ...p, es: Number(r.value.toFixed(4)) }); }}>f² from R²</button>
              <label className="field">partial η²<input type="number" step={0.01} value={helper.peta} onChange={(e) => setHelper({ ...helper, peta: Number(e.target.value) })} /></label>
              <button className="btn small" onClick={async () => { const r = await api("/api/power_helper/f_from_peta2", { e: helper.peta }); setP({ ...p, es: Number(r.value.toFixed(4)) }); }}>f from partial η²</button>
            </div>
            <p className="small muted">Defaults: d = .5, f = .25, f² = .15, w = .3 (medium). G*Power "number of groups" = combinations of the between factors; "number of measurements" = combinations of the within factors (3 × 3 → 9); for factorial ANOVA, groups = cells and numerator df = the effect's df.</p>
          </details>
        )}
        {err && <div className="err">{err}</div>}
      </div>
      <div className="card role-teal">
        <div className="card-head"><h3>Output</h3>{out && <button className="btn small" onClick={() => pin({ title: "Sample size / power", kind: "power", html: `<p>${out.report}</p>` })}>📌 Pin</button>}</div>
        {out && (
          <>
            <div className="grid3" style={{ gap: 8 }}>
              <div><div className="muted small">Total sample size</div><div className="kpi">{out.N}</div>{out.n1 && <div className="small muted">{out.n1} + {out.n2} per group</div>}</div>
              <div><div className="muted small">Power</div><div className="kpi">{Number(out.power).toFixed(3)}</div></div>
              <div><div className="muted small">{ES_LABEL[out.es_name] ?? "Effect"}</div><div className="kpi">{Number(out.es).toFixed(3)}</div></div>
              <div><div className="muted small">α</div><div className="kpi">{Number(out.alpha).toFixed(mode === "criterion" ? 4 : 3)}</div></div>
            </div>
            {out.note && <div className="warn">{out.note}</div>}
            <p className="apa">{out.report}</p>
            <Plot fig={{ data: [{ type: "scatter", mode: "lines", x: out.curve.map((c: any) => c.N), y: out.curve.map((c: any) => c.power), line: { color: "#0d8a87" } }], layout: { title: { text: "Power vs total N" }, xaxis: { title: { text: "Total N" } }, yaxis: { title: { text: "Power" }, range: [0, 1] }, showlegend: false, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0.8, y1: 0.8, line: { dash: "dot", color: "#e0532c" } }] } }} height={260} />
          </>
        )}
      </div>
    </div>
  );
}
