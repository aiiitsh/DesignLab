import { useEffect, useState } from "react";
import { api } from "../api";
import { coerce } from "../components/DataGrid";
import Results, { apaHtml, Italic } from "../components/Results";
import PowerCalc from "../components/PowerCalc";
import { useStore } from "../store";

const MENU: { lane: string; color: string; items: [string, string][] }[] = [
  { lane: "Descriptives", color: "var(--indigo)", items: [["descriptives", "Descriptive statistics"]] },
  { lane: "A · Compare conditions", color: "var(--laneA)", items: [["ttest_ind", "Independent samples t-test"], ["ttest_paired", "Paired samples t-test"], ["anova_oneway", "One-way ANOVA"], ["anova_factorial", "Factorial ANOVA"], ["anova_rm1", "One-way repeated measures ANOVA"], ["anova_rm", "N-way repeated measures ANOVA"], ["anova_mixed", "Mixed ANOVA"]] },
  { lane: "B · Relationship", color: "var(--laneB)", items: [["regression", "Linear regression"]] },
  { lane: "C · Categorical", color: "var(--laneC)", items: [["logistic", "Binary logistic regression"], ["chisquare", "χ² test of independence"]] },
];

function Pick({ label, value, cols, onChange }: { label: string; value?: string; cols: string[]; onChange: (v: string) => void }) {
  return (
    <label className="field">{label}
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}><option value="">–</option>{cols.map((c) => <option key={c} value={c}>{c}</option>)}</select>
    </label>
  );
}
function Multi({ label, value, cols, onChange }: { label: string; value?: string[]; cols: string[]; onChange: (v: string[]) => void }) {
  const v = value ?? [];
  return (
    <div className="field" style={{ fontSize: 12, color: "var(--muted)" }}>{label} <span className="small">(order = click order)</span>
      <div className="row" style={{ gap: 6 }}>
        {cols.map((c) => (
          <label key={c} className={`pill chk ${v.includes(c) ? "" : ""}`} style={{ background: v.includes(c) ? "var(--teal-bg)" : undefined, color: "var(--ink)" }}>
            <input type="checkbox" checked={v.includes(c)} onChange={(e) => onChange(e.target.checked ? [...v, c] : v.filter((x) => x !== c))} />{c}{v.includes(c) && <b className="small"> {v.indexOf(c) + 1}</b>}
          </label>
        ))}
      </div>
    </div>
  );
}

function parseFactors(s: string) {
  // "Task: easy, hard; Display: 1, 2, 3"
  return s.split(";").map((p) => p.trim()).filter(Boolean).map((p) => {
    const [n, l] = p.split(":");
    return { name: n.trim(), levels: (l ?? "").split(",").map((x) => x.trim()).filter(Boolean) };
  });
}

export default function Analysis() {
  const { project, update, settings, pin, go } = useStore();
  const spec = project.analysis ?? { id: "descriptives", roles: {}, options: {} };
  const [res, setRes] = useState<any>(null);
  const [batch, setBatch] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [factorText, setFactorText] = useState(() => (spec.roles.within_factors ?? []).map((f: any) => `${f.name}: ${f.levels.join(", ")}`).join("; "));
  const [blocksText, setBlocksText] = useState(() => (spec.options.blocks ?? []).map((b: string[]) => b.join(", ")).join(" | "));
  const cols = project.data.columns;
  const num = cols.filter((c) => project.data.types[c] !== "nominal");
  const setSpec = (p: Partial<typeof spec>) => update({ analysis: { ...spec, ...p } });
  const setRole = (k: string, v: any) => setSpec({ roles: { ...spec.roles, [k]: v } });
  const setOpt = (k: string, v: any) => setSpec({ options: { ...spec.options, [k]: v } });
  const ex = project.example;

  const run = async () => {
    setErr(""); setBusy(true); setBatch(null);
    try {
      const data = coerce(project.data);
      const options: Record<string, any> = { alpha: settings.alpha, ...spec.options };
      const roles = { ...spec.roles };
      if (["anova_rm", "anova_mixed"].includes(spec.id) && factorText.trim()) roles.within_factors = parseFactors(factorText);
      if (spec.id === "regression" && options.method === "hierarchical") options.blocks = blocksText.split("|").map((b: string) => b.split(",").map((x) => x.trim()).filter(Boolean));
      setRes(await api(`/api/analyze/${spec.id}`, { data, roles, options }));
    } catch (e: any) { setErr(e.message); setRes(null); }
    setBusy(false);
  };
  const runAll = async () => {
    setErr(""); setBusy(true);
    try {
      const dvs = ex?.dvs ?? num.filter((c) => c !== spec.roles.factors_between?.[0]);
      setBatch(await api(`/api/analyze_batch/${spec.id}`, { data: coerce(project.data), roles: spec.roles, dvs, options: { alpha: settings.alpha, ...spec.options, dv_labels: spec.options.dv_labels ?? ex?.dv_labels } }));
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  useEffect(() => { if (project.analysis && project.data.rows.length && !res) run(); }, []); // eslint-disable-line

  const id = spec.id;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "250px 1fr", gap: 18 }}>
      <nav aria-label="Analyses" style={{ position: "sticky", top: 0, alignSelf: "start" }}>
        {MENU.map((g) => (
          <div key={g.lane} style={{ marginBottom: 12 }}>
            <div className="small" style={{ fontWeight: 700, color: g.color, margin: "4px 0" }}>{g.lane}</div>
            {g.items.map(([k, l]) => (
              <button key={k} className={`nav ${id === k ? "active" : ""}`} style={{ width: "100%" }} onClick={() => { setSpec({ id: k }); setRes(null); setBatch(null); }}>{l}</button>
            ))}
          </div>
        ))}
        <button className="nav" style={{ width: "100%" }} onClick={() => go("doe")}>D · Engineering DOE →</button>
      </nav>

      <div>
        <h1 className="page-title">{MENU.flatMap((m) => m.items).find(([k]) => k === id)?.[1]}</h1>
        <p className="page-sub">{project.outcome?.design_name ?? "Expert mode: assign variables, then run."}</p>

        <div className="card">
          <div className="grid3" style={{ gap: 10 }}>
            {id === "descriptives" && <><Multi label="Variables" value={spec.roles.dvs} cols={num} onChange={(v) => setRole("dvs", v)} /><Pick label="Split by" value={spec.roles.factors_between?.[0]} cols={cols} onChange={(v) => setRole("factors_between", v ? [v] : [])} /></>}
            {["ttest_ind", "anova_oneway"].includes(id) && <><Pick label="Dependent variable" value={spec.roles.dv} cols={num} onChange={(v) => setRole("dv", v)} /><Pick label="Grouping variable" value={spec.roles.factors_between?.[0]} cols={cols} onChange={(v) => setRole("factors_between", [v])} /></>}
            {id === "anova_factorial" && <><Pick label="Dependent variable" value={spec.roles.dv} cols={num} onChange={(v) => setRole("dv", v)} /><Multi label="Fixed factors" value={spec.roles.factors_between} cols={cols.filter((c) => c !== spec.roles.dv)} onChange={(v) => setRole("factors_between", v)} /></>}
            {id === "ttest_paired" && <Multi label="Two paired columns" value={spec.roles.within_cols} cols={num} onChange={(v) => setRole("within_cols", v.slice(0, 2))} />}
            {["anova_rm1", "anova_rm", "anova_mixed"].includes(id) && (
              <>
                <Multi label="Repeated-measures cells (columns)" value={spec.roles.within_cols} cols={num} onChange={(v) => setRole("within_cols", v)} />
                {id === "anova_rm1" ? (
                  <label className="field">Within factor name<input type="text" value={spec.roles.within_name ?? "Condition"} onChange={(e) => setRole("within_name", e.target.value)} /></label>
                ) : (
                  <label className="field">Within factors and levels (last factor varies fastest across the columns)
                    <input type="text" placeholder="Task: easy, hard; Display: 1, 2, 3" value={factorText} onChange={(e) => setFactorText(e.target.value)} /></label>
                )}
                {id !== "anova_rm1" && <Multi label="Between-subject factors" value={spec.roles.factors_between} cols={cols.filter((c) => !(spec.roles.within_cols ?? []).includes(c))} onChange={(v) => setRole("factors_between", v)} />}
              </>
            )}
            {id === "regression" && (
              <>
                <Pick label="Dependent variable" value={spec.roles.dv} cols={num} onChange={(v) => setRole("dv", v)} />
                <Multi label="Covariates (continuous)" value={spec.roles.covariates} cols={num.filter((c) => c !== spec.roles.dv)} onChange={(v) => setRole("covariates", v)} />
                <Multi label="Factors (dummy coded, k − 1)" value={spec.roles.factors_between} cols={cols.filter((c) => project.data.types[c] === "nominal")} onChange={(v) => setRole("factors_between", v)} />
              </>
            )}
            {id === "logistic" && (
              <>
                <Pick label="Binary outcome" value={spec.roles.dv} cols={cols} onChange={(v) => setRole("dv", v)} />
                <Multi label="Covariates" value={spec.roles.covariates} cols={num.filter((c) => c !== spec.roles.dv)} onChange={(v) => setRole("covariates", v)} />
                <Multi label="Factors" value={spec.roles.factors_between} cols={cols.filter((c) => c !== spec.roles.dv)} onChange={(v) => setRole("factors_between", v)} />
              </>
            )}
            {id === "chisquare" && (
              <>
                <Pick label="Rows (IV)" value={spec.roles.row} cols={cols} onChange={(v) => setRole("row", v)} />
                <Pick label="Columns (DV)" value={spec.roles.col} cols={cols} onChange={(v) => setRole("col", v)} />
                <Pick label="Counts (optional)" value={spec.roles.counts} cols={num} onChange={(v) => setRole("counts", v || undefined)} />
              </>
            )}
          </div>
          <hr />
          <div className="row">
            {id.startsWith("ttest") && (
              <label className="field">Alternative<select value={spec.options.tails ?? "two"} onChange={(e) => setOpt("tails", e.target.value)}>
                <option value="two">Two-sided (≠)</option><option value="greater">Group 1 &gt; group 2</option><option value="less">Group 1 &lt; group 2</option></select></label>
            )}
            {id === "ttest_ind" && (
              <label className="field">Test override<select value={spec.options.force ?? ""} onChange={(e) => setOpt("force", e.target.value || undefined)}>
                <option value="">Automatic (course rules)</option><option value="student">Student</option><option value="welch">Welch</option><option value="mannwhitney">Mann-Whitney</option></select></label>
            )}
            {["anova_oneway", "anova_factorial"].includes(id) && (
              <label className="field">Post hoc<select value={spec.options.posthoc ?? "tukey"} onChange={(e) => setOpt("posthoc", e.target.value)}>
                {["tukey", "bonferroni", "holm", "sidak", "scheffe", "lsd"].map((m) => <option key={m} value={m}>{m === "lsd" ? "LSD (uncorrected)" : m[0].toUpperCase() + m.slice(1)}</option>)}</select></label>
            )}
            {id === "anova_oneway" && (
              <>
                <label className="field">Contrasts<select value={spec.options.contrast ?? "polynomial"} onChange={(e) => setOpt("contrast", e.target.value)}>
                  {["none", "polynomial", "treatment", "deviation"].map((m) => <option key={m}>{m}</option>)}</select></label>
                <label className="field">Override<select value={spec.options.force ?? ""} onChange={(e) => setOpt("force", e.target.value || undefined)}>
                  <option value="">Automatic (course rules)</option><option value="classic">Classical ANOVA</option><option value="welch">Welch</option><option value="kruskal">Kruskal-Wallis</option></select></label>
              </>
            )}
            {id === "anova_factorial" && (
              <label className="field">Assumption fallback<select value={spec.options.transform ?? ""} onChange={(e) => setOpt("transform", e.target.value || undefined)}>
                <option value="">Proceed with caveat</option><option value="log">Log-transform DV</option><option value="sqrt">Square-root transform DV</option></select></label>
            )}
            {["anova_rm1", "anova_rm", "anova_mixed"].includes(id) && (
              <label className="field">Sphericity correction<select value={spec.options.correction ?? ""} onChange={(e) => setOpt("correction", e.target.value || undefined)}>
                <option value="">Automatic (ε &lt; .60 → GG, else HF)</option><option value="none">None</option><option value="Greenhouse-Geisser">Greenhouse-Geisser</option><option value="Huynh-Feldt">Huynh-Feldt</option></select></label>
            )}
            {id === "regression" && (
              <>
                <label className="field">Method<select value={spec.options.method ?? "enter"} onChange={(e) => setOpt("method", e.target.value)}>
                  {["enter", "hierarchical", "forward", "backward", "stepwise"].map((m) => <option key={m}>{m}</option>)}</select></label>
                {spec.options.method === "hierarchical" && <label className="field">Blocks (separate with |)<input type="text" placeholder="adverts | airplay, attract" value={blocksText} onChange={(e) => setBlocksText(e.target.value)} /></label>}
              </>
            )}
            {id === "logistic" && <label className="field">Event level (Y = 1)<input type="text" value={spec.options.event ?? ""} onChange={(e) => setOpt("event", e.target.value || undefined)} /></label>}
            <span style={{ flex: 1 }} />
            {id === "ttest_ind" && <button className="btn" onClick={runAll} disabled={busy}>Run for every DV</button>}
            <button className="btn primary" onClick={run} disabled={busy}>{busy ? "Running…" : "▶ Run"}</button>
          </div>
        </div>

        {err && <div className="card role-coral"><h3>Cannot run this analysis</h3><p>{err}</p></div>}

        {batch && (
          <div className="card role-coral">
            <div className="card-head"><h3>Familywise error: {batch.m} tests</h3>
              <button className="btn small" onClick={() => pin({ title: "Multiple DVs", kind: "table", html: `<p>${batch.warning}</p><table class="res"><tr><th>DV</th><th>Test</th><th>p</th><th>Bonferroni</th><th>Holm p</th></tr>${batch.summary.map((r: any) => `<tr><td>${r.dv}</td><td>${r.test}</td><td>${r.p_fmt}</td><td>${r.sig_bonferroni ? "significant" : "n.s."}</td><td>${r.p_holm?.toFixed(3)}</td></tr>`).join("")}</table>` })}>📌 Pin</button></div>
            <div className="warn">{batch.warning}</div>
            <table className="res"><thead><tr><th>DV</th><th>Primary test</th><th>p</th><th>α = .05</th><th>Bonferroni (α = {batch.bonferroni_alpha.toFixed(4)})</th><th>Holm p</th><th>Holm</th></tr></thead>
              <tbody>{batch.summary.map((r: any) => (
                <tr key={r.dv}><td>{r.dv}</td><td>{r.test}</td><td>{r.p_fmt}</td><td>{r.sig_uncorrected ? "✓" : "–"}</td><td>{r.sig_bonferroni ? "✓ significant" : "– n.s."}</td><td>{r.p_holm?.toFixed(3)}</td><td>{r.sig_holm ? "✓" : "–"}</td></tr>))}</tbody></table>
            <details className="why"><summary>APA paragraphs for every DV</summary>{batch.results.map((r: any, i: number) => <p key={i} className="apa" style={{ marginTop: 8 }}><Italic text={r.apa} /></p>)}</details>
          </div>
        )}

        {res && <Results r={res} extraTop={ex?.paper_comparison && id === "ttest_ind" ? <ExampleCards ex={ex} /> : undefined} />}
      </div>
    </div>
  );
}

function ExampleCards({ ex }: { ex: any }) {
  const { pin } = useStore();
  const pc = ex.paper_comparison;
  const html = `<h4>${pc.title}</h4><p><b>Replicated:</b> ${pc.replicated.join(" ")}</p><p><b>Not replicated:</b> ${pc.not_replicated.join(" ")}</p><p>${pc.extra.join(" ")}</p><p>${pc.caveat}</p>`;
  return (
    <>
      <div className="card role-amber">
        <div className="card-head"><h3>📄 {pc.title}</h3><button className="btn small" onClick={() => pin({ title: pc.title, kind: "text", html })}>📌 Pin</button></div>
        <div className="grid2">
          <div><b style={{ color: "var(--ok)" }}>✓ Replicated</b><ul>{pc.replicated.map((x: string) => <li key={x}>{x}</li>)}</ul></div>
          <div><b style={{ color: "var(--bad)" }}>✗ Not replicated</b><ul>{pc.not_replicated.map((x: string) => <li key={x}>{x}</li>)}</ul></div>
        </div>
        {pc.extra.map((x: string) => <p key={x} className="small">{x}</p>)}
        <div className="warn">{pc.caveat}</div>
        {ex.notes?.map((n: string) => <div key={n} className="small muted">• {n}</div>)}
      </div>
      <details className="card role-indigo"><summary><b>Power for the replication</b> (post hoc for Q1 d = 0.957, n = 13/13)</summary>
        <PowerCalc family="ttest_ind" params0={{ es: 0.957, n1: 13, n2: 13 }} compact />
      </details>
    </>
  );
}
