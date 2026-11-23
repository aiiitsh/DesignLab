import { useEffect, useMemo, useState } from "react";
import { api, download, toCSV } from "../api";
import PowerCalc from "../components/PowerCalc";
import { ColType, Dataset, useStore } from "../store";

type IV = { name: string; levels: string[]; role: "between" | "within"; type?: string };
type DV = { name: string; type?: string; unit?: string };

function answerText(node: any, v: any): string {
  if (v === undefined) return "";
  if (node.type === "question") return node.options.find((o: any) => String(o.value) === String(v))?.label ?? String(v);
  if (node.type === "multi") return (v as string[]).map((x) => node.options.find((o: any) => o.value === x)?.label ?? x).join(", ") || "none";
  if (node.type === "form") return `${v?.ivs?.length ?? 0} IV(s), ${v?.dvs?.length ?? 0} DV(s)`;
  if (node.type === "text") return String(v).slice(0, 60) + (String(v).length > 60 ? "…" : "");
  return String(v);
}

function VarsForm({ value, onDone }: { value: any; onDone: (v: any) => void }) {
  const [ivs, setIvs] = useState<IV[]>(value?.ivs ?? [{ name: "Condition", levels: ["A", "B"], role: "between", type: "nominal" }]);
  const [dvs, setDvs] = useState<DV[]>(value?.dvs ?? [{ name: "Score", type: "interval/ratio" }]);
  const [controls, setControls] = useState<string>(value?.controls ?? "");
  return (
    <div className="card">
      <h3>Independent variables (IVs)</h3>
      {ivs.map((iv, i) => (
        <div key={i} className="row" style={{ marginBottom: 8 }}>
          <label className="field">Name<input type="text" value={iv.name} onChange={(e) => setIvs(ivs.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} /></label>
          <label className="field" style={{ flex: 1 }}>Levels (comma-separated)<input type="text" value={iv.levels.join(", ")} onChange={(e) => setIvs(ivs.map((x, j) => (j === i ? { ...x, levels: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } : x)))} /></label>
          <label className="field">Every participant does every level?
            <select value={iv.role} onChange={(e) => setIvs(ivs.map((x, j) => (j === i ? { ...x, role: e.target.value as any } : x)))}>
              <option value="between">No (between)</option><option value="within">Yes (within)</option>
            </select></label>
          <button className="btn small" onClick={() => setIvs(ivs.filter((_, j) => j !== i))} aria-label="Remove IV">×</button>
        </div>
      ))}
      <button className="btn small" onClick={() => setIvs([...ivs, { name: `IV${ivs.length + 1}`, levels: ["1", "2"], role: "between" }])}>+ Add IV</button>
      <hr />
      <h3>Dependent variables (DVs)</h3>
      {dvs.map((dv, i) => (
        <div key={i} className="row" style={{ marginBottom: 8 }}>
          <label className="field" style={{ flex: 1 }}>Name<input type="text" value={dv.name} onChange={(e) => setDvs(dvs.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} /></label>
          <label className="field">Data type (NOIR)
            <select value={dv.type ?? "interval/ratio"} onChange={(e) => setDvs(dvs.map((x, j) => (j === i ? { ...x, type: e.target.value } : x)))}>
              <option>interval/ratio</option><option>ordinal (1–7, treated as interval)</option><option>ordinal</option><option>nominal (binary)</option><option>nominal (counts)</option>
            </select></label>
          <label className="field">Unit<input type="text" value={dv.unit ?? ""} onChange={(e) => setDvs(dvs.map((x, j) => (j === i ? { ...x, unit: e.target.value } : x)))} /></label>
          <button className="btn small" onClick={() => setDvs(dvs.filter((_, j) => j !== i))} aria-label="Remove DV">×</button>
        </div>
      ))}
      <button className="btn small" onClick={() => setDvs([...dvs, { name: `DV${dvs.length + 1}`, type: "interval/ratio" }])}>+ Add DV</button>
      <hr />
      <label className="field">Control variables (held constant) and operational definitions<textarea value={controls} onChange={(e) => setControls(e.target.value)} /></label>
      <div style={{ marginTop: 12 }}><button className="btn primary" onClick={() => onDone({ ivs, dvs, controls })}>Next →</button></div>
    </div>
  );
}

function NotSure({ onPick }: { onPick: (v: string) => void }) {
  const [f, setF] = useState({ learning_effects: false, long_session: false, few_people: false, person_attribute: false, large_individual_diff: false });
  const [r, setR] = useState<any>(null);
  return (
    <details className="notsure">
      <summary><b>Not sure? Answer four quick questions</b></summary>
      {([["learning_effects", "Large learning / carryover effects that are hard to counterbalance?"], ["long_session", "Would doing every condition make the session long (fatigue)?"], ["few_people", "Are only a few participants available?"], ["large_individual_diff", "Are individual differences large?"], ["person_attribute", "Is the IV a person attribute (gender, age)?"]] as const).map(([k, l]) => (
        <label key={k} className="chk"><input type="checkbox" checked={(f as any)[k]} onChange={(e) => setF({ ...f, [k]: e.target.checked })} />{l}</label>
      ))}
      <button className="btn small" style={{ marginTop: 8 }} onClick={async () => setR(await api("/api/tree/helper", f))}>Suggest</button>
      {r && <p><b>Suggestion: {r.suggest}.</b> {r.why}. <button className="btn small" onClick={() => onPick(r.suggest.startsWith("within") ? "within" : "between")}>Use it</button></p>}
    </details>
  );
}

function designName(outcome: any, ivs: IV[]): string {
  if (!ivs.length) return outcome.design;
  const kind = outcome.outcome === "anova_mixed" ? "mixed" : ivs.every((i) => i.role === "within") ? "within-subjects" : "between-subjects";
  if (ivs.length === 1) return `${kind[0].toUpperCase() + kind.slice(1)} design: ${ivs[0].name} with ${ivs[0].levels.length} levels`;
  return `${ivs.map((i) => i.levels.length).join(" × ")} ${kind} design: ${ivs.map((i) => `${i.name} ${i.role}`).join(", ")}`;
}

export function buildTemplate(outcome: any, answers: any): { ds: Dataset; roles: Record<string, any> } {
  const ivs: IV[] = answers.plan_vars?.ivs ?? [];
  const dvs: DV[] = answers.plan_vars?.dvs ?? [{ name: "Score" }];
  const types: Record<string, ColType> = { Participant: "nominal" };
  const columns = ["Participant"];
  const roles: Record<string, any> = {};
  const id = outcome.analysis_id;
  const dvName = (dvs[0]?.name || "Score").replace(/\s+/g, "_");
  if (outcome.data_shape === "wide") {
    const within = ivs.filter((i) => i.role === "within");
    const between = ivs.filter((i) => i.role === "between");
    for (const b of between) { columns.push(b.name); types[b.name] = "nominal"; }
    const w = within.length ? within : [{ name: "Condition", levels: ["C1", "C2", "C3"], role: "within" as const }];
    const combos = w.reduce<string[][]>((acc, f) => acc.flatMap((a) => f.levels.map((l) => [...a, l])), [[]]);
    const cols = combos.map((c) => c.join("_"));
    cols.forEach((c) => { columns.push(c); types[c] = "scale"; });
    if (id === "ttest_paired") roles.within_cols = cols.slice(0, 2);
    else {
      roles.within_cols = cols;
      if (w.length > 1) roles.within_factors = w.map((f) => ({ name: f.name, levels: f.levels }));
      else roles.within_name = w[0].name;
      if (between.length) roles.factors_between = between.map((b) => b.name);
    }
  } else if (outcome.data_shape === "long") {
    for (const iv of ivs) { columns.push(iv.name); types[iv.name] = id === "regression" ? "scale" : "nominal"; }
    for (const dv of dvs) { const n = dv.name.replace(/\s+/g, "_"); columns.push(n); types[n] = dv.type?.startsWith("nominal") ? "nominal" : dv.type?.startsWith("ordinal") ? "ordinal" : "scale"; }
    if (id === "regression") { roles.dv = dvName; roles.covariates = ivs.map((i) => i.name); }
    else if (id === "logistic") { roles.dv = dvName; roles.covariates = ivs.map((i) => i.name); }
    else if (id === "chisquare") { roles.row = ivs[0]?.name; roles.col = dvName; }
    else { roles.dv = dvName; roles.factors_between = ivs.map((i) => i.name); }
  }
  const n = 20;
  const rows = Array.from({ length: n }, (_, i) => ({ Participant: String(i + 1) }));
  return { ds: { columns, types, rows }, roles };
}

/** Make the variable list agree with the lane answers (role and level count), and say what changed. */
export function reconcile(outcome: any, answers: any): { answers: any; notes: string[] } {
  const ivs: IV[] = (answers.plan_vars?.ivs ?? []).map((i: IV) => ({ ...i, levels: [...i.levels] }));
  const notes: string[] = [];
  const id = outcome.outcome;
  const force = (role: "within" | "between", all = false) => {
    (all ? ivs : ivs.slice(0, 1)).forEach((iv) => {
      if (iv.role !== role) { notes.push(`${iv.name} was listed as ${iv.role}; your answers make it ${role}.`); iv.role = role; }
    });
  };
  if (["ttest_paired", "anova_rm1"].includes(id)) force("within");
  if (["ttest_ind", "anova_oneway"].includes(id)) force("between");
  if (id === "anova_factorial") force("between", true);
  if (id === "anova_rm") force("within", true);
  const first = ivs[0];
  if (first && id?.startsWith("ttest") && first.levels.length !== 2) notes.push(`A t-test needs exactly 2 levels, but ${first.name} lists ${first.levels.length}. Go back to "List your variables" to fix it.`);
  if (first && ["anova_oneway", "anova_rm1"].includes(id) && first.levels.length < 3) {
    while (first.levels.length < 3) first.levels.push(`L${first.levels.length + 1}`);
    notes.push(`A one-way ANOVA needs 3+ levels, so ${first.name} now has placeholder level(s): ${first.levels.join(", ")}. Rename them in "List your variables".`);
  }
  return { answers: { ...answers, plan_vars: { ...(answers.plan_vars ?? {}), ivs } }, notes };
}

function Summary({ outcome, answers: rawAnswers, tree }: { outcome: any; answers: any; tree: any }) {
  const { update, go, project, pin, toast } = useStore();
  const { answers, notes } = reconcile(outcome, rawAnswers);
  const ivs: IV[] = answers.plan_vars?.ivs ?? [];
  const within = ivs.filter((i) => i.role === "within");
  const conds = within.length ? within.reduce<string[][]>((acc, f) => acc.flatMap((a) => f.levels.map((l) => [...a, l])), [[]]).map((c) => c.join(" × ")) : [];
  const [cb, setCb] = useState<any>(null);
  const [cbMethod, setCbMethod] = useState(answers.plan_controls?.includes("counterbalance_full") ? "full" : "latin");
  const [nPart, setNPart] = useState(24);
  const [seed, setSeed] = useState(640);
  const [rnd, setRnd] = useState<any>(null);
  const betweenLevels = ivs.filter((i) => i.role === "between").reduce<string[][]>((acc, f) => acc.flatMap((a) => f.levels.map((l) => [...a, l])), [[]]).map((c) => c.join(" × "));

  const powerParams = useMemo((): Record<string, number> => {
    const k = betweenLevels.length || 1;
    const m = conds.length || 3;
    const pf = outcome.power_family;
    if (pf === "anova_oneway") return { k: ivs[0]?.levels.length || 3 };
    if (pf === "rm_within") return { groups: 1, m: conds.length || ivs[0]?.levels.length || 3 };
    if (pf === "rm_interaction") return { groups: k, m };
    if (pf === "anova_special") { const cells = ivs.reduce((a, f) => a * (f.levels.length || 2), 1); return { cells, df1: ivs.reduce((a, f) => a * ((f.levels.length || 2) - 1), 1) }; }
    if (pf === "reg_r2") return { predictors: ivs.length || 1 };
    return {};
  }, [outcome, answers]);

  if (!outcome.analysis_id) {
    return <div className="card role-coral"><h3>{outcome.name}</h3><p>{outcome.note}</p></div>;
  }
  const tmpl = buildTemplate(outcome, answers);
  const summaryHtml = `<dl><dt>Design</dt><dd>${outcome.design_name}</dd><dt>Analysis</dt><dd>${outcome.name}</dd><dt>Research question</dt><dd>${answers.plan_rq ?? ""}</dd></dl>`;
  return (
    <div>
      <div className="card role-teal">
        <div className="card-head"><h3>Design summary</h3><button className="btn small" onClick={() => pin({ title: "Design summary", kind: "design", html: summaryHtml })}>📌 Pin</button></div>
        <dl className="summary-grid">
          <dt>Design</dt><dd><b>{notes.length ? designName(outcome, ivs) : outcome.design_name}</b></dd>
          <dt>Recommended analysis</dt><dd><b style={{ color: "var(--teal)" }}>{outcome.name}</b> <span className="lecture">{outcome.lecture}</span></dd>
          <dt>Course fallbacks</dt><dd>{outcome.fallbacks}</dd>
          <dt>Research question</dt><dd>{answers.plan_rq}</dd>
          <dt>Hypothesis</dt><dd>{{ two: "Two-sided (≠)", greater: "One-sided (>)", less: "One-sided (<)" }[answers.plan_hyp as string] ?? "–"}</dd>
          <dt>IVs</dt><dd>{ivs.map((i) => `${i.name} (${i.role}; ${i.levels.length} levels: ${i.levels.join(", ")})`).join(" · ") || "–"}</dd>
          <dt>DVs</dt><dd>{(answers.plan_vars?.dvs ?? []).map((d: DV) => `${d.name}${d.type ? ` [${d.type}]` : ""}${d.unit ? ` (${d.unit})` : ""}`).join(" · ") || "–"}</dd>
          <dt>Control variables</dt><dd>{answers.plan_vars?.controls || "–"}</dd>
          <dt>Controls</dt><dd>{answerText(tree.nodes.plan_controls, answers.plan_controls ?? [])}</dd>
          <dt>Data layout</dt><dd>{outcome.data_shape === "wide" ? "Wide: one row per person, one column per within condition (as JASP)" : outcome.data_shape === "long" ? "Long: one row per person, one group column + one DV column" : "Run sheet"}</dd>
        </dl>
        {outcome.flags?.map((f: string, i: number) => <div className="warn" key={i}>⚠ {f}</div>)}
        {notes.map((f: string, i: number) => <div className="warn" key={`n${i}`}>⚠ {f}</div>)}
        <div className="warn">Ethics reminder: get ethics approval (TCPS 2: respect for persons, welfare, justice) before collecting data.</div>
      </div>

      {conds.length >= 2 && (
        <div className="card role-indigo">
          <h3>Counterbalancing plan</h3>
          <div className="row">
            <select value={cbMethod} onChange={(e) => setCbMethod(e.target.value)}><option value="latin">Balanced Latin square (Williams)</option><option value="full">Full permutations (n!)</option></select>
            <label className="field">Participants<input type="number" value={nPart} onChange={(e) => setNPart(Number(e.target.value))} /></label>
            <button className="btn" onClick={async () => setCb(await api("/api/design/counterbalance", { conditions: conds, method: cbMethod, participants: nPart }))}>Generate</button>
            {cb && <button className="btn" onClick={() => download("counterbalancing.csv", toCSV(["participant", "order_no", ...conds.map((_, i) => `position_${i + 1}`)], cb.assignment.map((a: any) => ({ participant: a.participant, order_no: a.order_no, ...Object.fromEntries(a.order.map((c: string, i: number) => [`position_${i + 1}`, c])) }))), "text/csv")}>Download CSV</button>}
          </div>
          {cb && (
            <>
              <p className="small">{cb.method}: {cb.n_orders} orders. {cb.check && `Each condition once per row: ${cb.check.each_once_per_row ? "✓" : "✗"} · once per column: ${cb.check.each_once_per_column ? "✓" : "✗"} · carryover balanced: ${cb.check.carryover_balanced ? "✓" : "✗"}`}</p>
              {cb.note && <div className="warn">{cb.note}</div>}
              <div className="tbl-wrap"><table className="res"><thead><tr><th>Order</th>{conds.map((_, i) => <th key={i}>Position {i + 1}</th>)}</tr></thead>
                <tbody>{cb.orders.slice(0, 24).map((o: string[], i: number) => <tr key={i}><td>{i + 1}</td>{o.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody></table></div>
            </>
          )}
        </div>
      )}

      {betweenLevels.length >= 2 && (
        <div className="card role-indigo">
          <h3>Randomization schedule</h3>
          <div className="row">
            <label className="field">Participants<input type="number" value={nPart} onChange={(e) => setNPart(Number(e.target.value))} /></label>
            <label className="field">Seed<input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} /></label>
            <button className="btn" onClick={async () => setRnd(await api("/api/design/randomize", { participants: nPart, groups: betweenLevels, seed }))}>Randomize</button>
            {rnd && <button className="btn" onClick={() => download("randomization.csv", toCSV(["participant", "condition", "run_order"], rnd.rows), "text/csv")}>Download CSV</button>}
          </div>
          {rnd && <div className="tbl-wrap" style={{ maxHeight: 260 }}><table className="res"><thead><tr><th>Participant</th><th>Condition</th><th>Run order</th></tr></thead>
            <tbody>{rnd.rows.map((r: any) => <tr key={r.participant}><td>{r.participant}</td><td>{r.condition}</td><td>{r.run_order}</td></tr>)}</tbody></table></div>}
        </div>
      )}

      {outcome.power_family && (
        <div>
          <h3 style={{ margin: "18px 0 8px" }}>Sample size (a priori, G*Power-equivalent)</h3>
          <PowerCalc family={outcome.power_family} params0={powerParams} compact />
        </div>
      )}

      <div className="card role-amber">
        <h3>Data template</h3>
        <p className="small muted">Columns: {tmpl.ds.columns.join(", ")}</p>
        <div className="row">
          <button className="btn primary" onClick={() => {
            if (project.data.rows.some((r) => Object.keys(r).length > 0) && project.exampleId) { /* keep example data */ }
            else update({ data: tmpl.ds });
            update({ outcome, analysis: { id: outcome.analysis_id, roles: project.analysis?.roles ?? tmpl.roles, options: { ...(outcome.options || {}), tails: answers.plan_hyp ?? "two", ...(project.analysis?.options || {}) } } });
            toast("Data sheet ready");
            go(outcome.data_shape === "runsheet" ? "doe" : "data");
          }}>Create the data sheet →</button>
          <button className="btn" onClick={() => download("data_template.csv", toCSV(tmpl.ds.columns, []), "text/csv")}>Download empty template (CSV)</button>
        </div>
      </div>
    </div>
  );
}

export default function Wizard() {
  const { project, update } = useStore();
  const [tree, setTree] = useState<any>(null);
  const [state, setState] = useState<any>(null);
  const [text, setText] = useState("");
  const [multi, setMulti] = useState<string[]>([]);
  const [numv, setNumv] = useState(2);
  const answers = project.answers;

  useEffect(() => { api("/api/tree").then(setTree); }, []);
  useEffect(() => {
    api("/api/tree/next", { answers }).then((s) => {
      setState(s);
      if (s.done) update({ outcome: s });
      const n = s.node;
      if (n?.type === "text") setText(answers[n.id] ?? "");
      if (n?.type === "multi") setMulti(answers[n.id] ?? []);
      if (n?.type === "numeric") setNumv(answers[n.id] ?? n.default ?? 2);
    });
  }, [JSON.stringify(answers)]); // eslint-disable-line

  if (!tree || !state) return <p>Loading the flow chart…</p>;
  const answer = (id: string, v: any) => update({ answers: { ...answers, [id]: v } });
  const backTo = (id: string) => {
    const keep: Record<string, any> = {};
    for (const k of state.path) { if (k === id) break; keep[k] = answers[k]; }
    update({ answers: keep, outcome: undefined });
  };
  const node = state.node;
  const names = (ids: string[]) => ids.map((o) => tree.outcomes[o]?.name).filter(Boolean);

  return (
    <div>
      <h1 className="page-title">Guided experiment design</h1>
      <p className="page-sub">Follows the SYDE 640 HW3 flow chart: Plan → Choose the lane → Report.</p>
      <div className="wizard">
        <nav className="rail" aria-label="Path so far">
          <div className="small muted" style={{ fontWeight: 600 }}>YOUR PATH</div>
          {state.path.map((id: string) => {
            const n = tree.nodes[id];
            return (
              <button key={id} className={`chip lane-${n.lane}`} onClick={() => backTo(id)} title="Go back to this question">
                <span className="q">{n.text}</span><span className="a">{answerText(n, answers[id])}</span>
              </button>
            );
          })}
          {state.done && <div className="chip lane-A" style={{ borderLeftColor: "var(--teal)" }}><span className="q">Recommended</span><span className="a">{state.name}</span></div>}
          {state.path.length > 0 && <button className="btn small" onClick={() => update({ answers: {}, outcome: undefined })}>Start over</button>}
        </nav>

        <section>
          {!state.done && node && (
            <>
              <div className="question">
                <div className="qhead"><div className="hex">?</div>
                  <div><h2 data-help={node.help}>{node.text}</h2><span className="lecture">{node.lecture}</span>{node.stage && <span className="small muted"> · Stage {node.stage}: {node.stage === 1 ? "Plan" : "Choose the analysis"}</span>}</div>
                </div>
                <details className="why"><summary>Why does this matter?</summary><p>{node.help}</p></details>
              </div>
              {node.type === "question" && (
                <div className="options" role="radiogroup" aria-label={node.text}>
                  {node.options.map((o: any) => (
                    <button key={o.value} role="radio" aria-checked={answers[node.id] === o.value} className={`option ${answers[node.id] === o.value ? "selected" : ""}`} onClick={() => answer(node.id, o.value)}>
                      <b>{o.label}</b>{o.consequence && <div className="cons">Choose this if… {o.consequence}</div>}
                    </button>
                  ))}
                  {node.helper === "within_between" && <NotSure onPick={(v) => {
                    const opt = node.options.find((o: any) => o.value === v) ?? node.options.find((o: any) => o.value === "within");
                    if (opt) answer(node.id, opt.value);
                  }} />}
                </div>
              )}
              {node.type === "text" && (
                <div className="card">
                  <textarea value={text} placeholder={node.placeholder} onChange={(e) => setText(e.target.value)} aria-label={node.text} />
                  <button className="btn primary" style={{ marginTop: 10 }} disabled={!text.trim()} onClick={() => answer(node.id, text.trim())}>Next →</button>
                </div>
              )}
              {node.type === "form" && <VarsForm value={answers[node.id]} onDone={(v) => answer(node.id, v)} />}
              {node.type === "multi" && (
                <div className="card">
                  {node.options.map((o: any) => (
                    <label key={o.value} className="chk" style={{ padding: "4px 0" }}>
                      <input type="checkbox" checked={multi.includes(o.value)} onChange={(e) => setMulti(e.target.checked ? [...multi, o.value] : multi.filter((x) => x !== o.value))} />{o.label}
                    </label>
                  ))}
                  <button className="btn primary" style={{ marginTop: 10 }} onClick={() => answer(node.id, multi)}>Next →</button>
                </div>
              )}
              {node.type === "numeric" && (
                <div className="card">
                  <div className="stepper">
                    <button onClick={() => setNumv(Math.max(node.min ?? 1, numv - 1))} aria-label="Decrease">−</button>
                    <span aria-live="polite">{numv}</span>
                    <button onClick={() => setNumv(Math.min(node.max ?? 10, numv + 1))} aria-label="Increase">+</button>
                  </div>
                  {node.warn_at && numv >= node.warn_at && <div className="warn">⚠ {node.warn}</div>}
                  <div><button className="btn primary" style={{ marginTop: 10 }} onClick={() => answer(node.id, numv)}>Next →</button></div>
                </div>
              )}
            </>
          )}
          {state.done && <Summary outcome={state} answers={answers} tree={tree} />}
        </section>

        <aside className="rec">
          <div className="card role-teal">
            <h3>Live recommendation</h3>
            {state.done ? (
              <>
                <div className="cand"><b>{state.name}</b></div>
                <p className="small">{state.design_name}</p>
                <span className="lecture">{state.lecture}</span>
              </>
            ) : (
              <>
                <p className="small muted">Still possible ({state.candidates.length}):</p>
                {names(state.candidates).map((n: string) => <div key={n} className="cand">{n}</div>)}
                {node && <p className="small" style={{ marginTop: 10 }}>This question is covered in <span className="lecture">{node.lecture}</span></p>}
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
