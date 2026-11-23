import React from "react";
import Plot from "./Plot";
import { Learn } from "./Learn";
import { useStore } from "../store";

export function fmt(v: any, col = ""): string {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "string") return v;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v !== "number") return String(v);
  if (!isFinite(v)) return "∞";
  const intCols = /^(N|n|df|df1|df2|Valid|Missing|Case|Dimension|Run|Std order|Run order)$/;
  if (Number.isInteger(v) && (intCols.test(col) || Math.abs(v) >= 1000 || col === "")) return String(v).replace("-", "−");
  if (Number.isInteger(v) && intCols.test(col)) return String(v);
  let s = v.toFixed(3);
  if (s === "-0.000") s = "0.000";
  return s.replace("-", "−");
}

/** Render *x* markdown-italics used by the APA templates. */
export function Italic({ text }: { text: string }) {
  const parts = text.split(/(\*[^*]+\*)/g);
  return <>{parts.map((p, i) => (p.startsWith("*") && p.endsWith("*") && p.length > 2 ? <i key={i}>{p.slice(1, -1)}</i> : <React.Fragment key={i}>{p}</React.Fragment>))}</>;
}
export const apaHtml = (t: string) => t.replace(/\*([^*]+)\*/g, "<i>$1</i>");

export function ResultTable({ t }: { t: any }) {
  const usedIdx = t.columns.indexOf("Used");
  return (
    <div className="tbl-wrap">
      <table className="res">
        <caption>{t.title}</caption>
        <thead>
          <tr>{t.columns.map((c: string, i: number) => (i === usedIdx ? null : <th key={i}><Learn term={c}>{c}</Learn></th>))}</tr>
        </thead>
        <tbody>
          {t.rows.map((r: any[], i: number) => (
            <tr key={i} className={usedIdx >= 0 && r[usedIdx] === "✓" ? "used" : ""}>
              {r.map((v, j) => (j === usedIdx ? null : <td key={j}>{fmt(v, t.columns[j])}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
      {t.footnotes?.map((f: string, i: number) => <div key={i} className="foot">Note. {f}</div>)}
    </div>
  );
}

export function tableHtml(t: any): string {
  const usedIdx = t.columns.indexOf("Used");
  const head = t.columns.map((c: string, i: number) => (i === usedIdx ? "" : `<th>${c}</th>`)).join("");
  const body = t.rows.map((r: any[]) => `<tr>${r.map((v, j) => (j === usedIdx ? "" : `<td>${fmt(v, t.columns[j])}</td>`)).join("")}</tr>`).join("");
  const notes = (t.footnotes || []).map((f: string) => `<div class="foot">Note. ${f}</div>`).join("");
  return `<table class="res"><caption>${t.title}</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>${notes}`;
}

function PinBtn({ title, html, kind }: { title: string; html: string; kind: string }) {
  const { pin } = useStore();
  return <button className="btn small no-print" onClick={() => pin({ title, html, kind })} title="Add this card to the report">📌 Pin</button>;
}

function Copy({ text }: { text: string }) {
  const { toast } = useStore();
  return <button className="btn small no-print" onClick={() => { navigator.clipboard?.writeText(text); toast("Copied"); }}>Copy</button>;
}

export default function Results({ r, extraTop }: { r: any; extraTop?: React.ReactNode }) {
  const sec = (s: string) => r.tables.filter((t: any) => t.section === s);
  const desc = sec("descriptives"), assum = sec("assumptions"), main = sec("main"), fol = sec("followups");
  const switched = r.decisions.some((d: any) => d.switched);
  const plotsDesc = r.plots.filter((p: any) => p.data?.[0]?.type === "box");
  const plotsQQ = r.plots.filter((p: any) => /Q-Q/.test(p.layout?.title?.text || ""));
  const plotsOther = r.plots.filter((p: any) => !plotsDesc.includes(p) && !plotsQQ.includes(p));
  const plain = r.apa.replace(/\*/g, "");
  return (
    <div>
      {extraTop}
      {r.warnings?.map((w: string, i: number) => <div className="warn" key={i}>⚠ {w}</div>)}

      <div className="card role-indigo">
        <div className="card-head"><h3>1 · Descriptives</h3><PinBtn title="Descriptives" kind="table" html={desc.map(tableHtml).join("")} /></div>
        {desc.map((t: any, i: number) => <ResultTable key={i} t={t} />)}
        <div className="grid2">{plotsDesc.map((p: any, i: number) => <Plot key={i} fig={p} />)}</div>
      </div>

      <div className="card role-violet">
        <div className="card-head"><h3>2 · Assumption checks</h3><PinBtn title="Assumption checks" kind="table" html={assum.map(tableHtml).join("")} /></div>
        <p className="small muted">Read the checks backwards: <i>p</i> &gt; .05 means the assumption is OK; <i>p</i> &lt; .05 means it is violated.</p>
        <div className="col">
          {r.checks.map((c: any, i: number) => (
            <div key={i} className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--line)", padding: "4px 0" }}>
              <span>{c.name} <span className="muted small">({c.test}{c.statistic != null && c.test !== "count" ? `, ${fmt(c.statistic)}` : ""}{c.p_fmt ? `, p ${c.p_fmt.startsWith("<") ? c.p_fmt : "= " + c.p_fmt}` : ""})</span>
                {c.detail && <div className="small muted">{c.detail}</div>}</span>
              <span className={`verdict ${c.ok ? "ok" : "bad"}`}>{c.ok ? "✓ OK" : "✗ Violated"}</span>
            </div>
          ))}
        </div>
        {assum.map((t: any, i: number) => <ResultTable key={i} t={t} />)}
        <div className="grid3">{plotsQQ.map((p: any, i: number) => <Plot key={i} fig={p} height={260} />)}</div>
      </div>

      <div className={`card ${switched ? "role-coral" : "role-indigo"}`}>
        <div className="card-head"><h3>3 · Decision log</h3><PinBtn title="Decision log" kind="text" html={`<ul>${r.decisions.map((d: any) => `<li>${d.text}</li>`).join("")}</ul>`} /></div>
        {r.decisions.map((d: any, i: number) => <div key={i} className={`decision ${d.switched ? "switched" : ""}`}>{d.switched ? "↪ " : "✓ "}{d.text}</div>)}
      </div>

      <div className="card role-teal">
        <div className="card-head"><h3>4 · Main result</h3><PinBtn title={r.title} kind="table" html={main.map(tableHtml).join("")} /></div>
        {main.map((t: any, i: number) => <ResultTable key={i} t={t} />)}
      </div>

      {(fol.length > 0 || plotsOther.length > 0) && (
        <div className="card role-sky">
          <div className="card-head"><h3>5 · Follow-ups</h3><PinBtn title="Follow-ups" kind="table" html={fol.map(tableHtml).join("")} /></div>
          {fol.map((t: any, i: number) => <ResultTable key={i} t={t} />)}
          <div className="grid2">{plotsOther.map((p: any, i: number) => <Plot key={i} fig={p} />)}</div>
        </div>
      )}

      <div className="card role-sky">
        <h3>6 · Effect sizes</h3>
        {r.effect_sizes.map((e: any, i: number) => (
          <div className="es" key={i}>
            <span><Learn term={e.name.split(" ")[0] === "Cohen's" ? "Cohen's d" : e.name.split(" ")[0]}>{e.name}</Learn>{e.note && <span className="small muted"> · {e.note}</span>}</span>
            <span className="row">
              <b className="mono">{fmt(e.value)}</b>
              {e.ci && e.ci[0] != null && <span className="small muted">95% CI [{fmt(e.ci[0])}, {fmt(e.ci[1])}]</span>}
              {e.band && <span className="band">{e.band}</span>}
            </span>
          </div>
        ))}
      </div>

      <div className="card role-teal">
        <div className="card-head"><h3>7 · APA paragraph</h3><span className="row"><Copy text={plain} /><PinBtn title="APA paragraph" kind="apa" html={`<p class="apa">${apaHtml(r.apa)}</p>`} /></span></div>
        <div className="apa"><Italic text={r.apa} /></div>
        {r.interpretation && <p><b>In plain words:</b> {r.interpretation}</p>}
      </div>

      <div className="card">
        <div className="card-head"><h3>8 · Python code</h3><Copy text={r.python_code} /></div>
        <pre className="code">{r.python_code}</pre>
      </div>
    </div>
  );
}
