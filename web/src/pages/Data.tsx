import { useRef, useState } from "react";
import { download, toCSV, upload } from "../api";
import DataGrid, { coerce, guessType, validate } from "../components/DataGrid";
import { ColType, Dataset, useStore } from "../store";

export default function Data() {
  const { project, update, go, toast } = useStore();
  const ds = project.data;
  const set = (d: Dataset) => update({ data: d });
  const fileRef = useRef<HTMLInputElement>(null);
  const [sheets, setSheets] = useState<{ file: File; names: string[] } | null>(null);
  const [reshape, setReshape] = useState<null | "long" | "wide">(null);
  const [rs, setRs] = useState<any>({ ids: [], values: [], factor: "Condition", value: "Value", subject: "", key: "", val: "" });

  const importFile = async (f: File, sheet?: string) => {
    try {
      const r = await upload(`/api/import${sheet ? `?sheet=${encodeURIComponent(sheet)}` : ""}`, f);
      if (r.sheets && r.sheets.length > 1 && !sheet) setSheets({ file: f, names: r.sheets });
      const types: Record<string, ColType> = {};
      r.columns.forEach((c: string) => (types[c] = guessType(r.rows.map((x: any) => x[c]))));
      set({ columns: r.columns, types, rows: r.rows });
      toast(`Imported ${r.rows.length} rows`);
    } catch (e: any) { toast(e.message); }
  };

  const normalize = () => {
    const rows = ds.rows.map((r) => {
      const o = { ...r };
      for (const c of ds.columns) if (ds.types[c] === "nominal" && typeof o[c] === "string") {
        const s = o[c].trim();
        o[c] = s ? s[0].toUpperCase() + s.slice(1).toLowerCase() : s;
      }
      return o;
    });
    set({ ...ds, rows });
    toast("Labels normalized (trimmed, first letter upper case)");
  };

  const toLong = () => {
    const rows = coerce(ds);
    const out: any[] = [];
    rows.forEach((r, i) => {
      for (const v of rs.values) out.push({ Subject: r[rs.ids[0]] ?? i + 1, ...Object.fromEntries(rs.ids.map((c: string) => [c, r[c]])), [rs.factor]: v, [rs.value]: r[v] });
    });
    const cols = ["Subject", ...rs.ids.filter((c: string) => c !== "Subject"), rs.factor, rs.value];
    const types: Record<string, ColType> = Object.fromEntries(cols.map((c) => [c, c === rs.value ? "scale" : "nominal"]));
    set({ columns: cols, types, rows: out.map((o) => Object.fromEntries(cols.map((c) => [c, o[c]]))) });
    setReshape(null);
  };
  const toWide = () => {
    const rows = coerce(ds);
    const levels = Array.from(new Set(rows.map((r) => String(r[rs.key]))));
    const by = new Map<string, any>();
    for (const r of rows) {
      const s = String(r[rs.subject]);
      if (!by.has(s)) by.set(s, { [rs.subject]: r[rs.subject] });
      by.get(s)[String(r[rs.key])] = r[rs.val];
    }
    const cols = [rs.subject, ...levels];
    set({ columns: cols, types: Object.fromEntries(cols.map((c) => [c, c === rs.subject ? "nominal" : "scale"])), rows: Array.from(by.values()) });
    setReshape(null);
  };

  const issues = validate(ds, project.analysis?.roles?.factors_between ?? []);
  const nRows = coerce(ds).length;

  return (
    <div>
      <h1 className="page-title">Data</h1>
      <p className="page-sub">Type, paste from Excel (Ctrl+V into any cell), or import CSV / XLSX. Within factors are wide (one column per condition), between factors long, as in JASP.</p>
      <div className="card">
        <div className="row">
          <button className="btn" onClick={() => fileRef.current?.click()}>📂 Import CSV / XLSX</button>
          <input ref={fileRef} type="file" accept=".csv,.tsv,.txt,.xlsx,.xls" hidden onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} />
          <button className="btn" onClick={() => download(`${project.name.replace(/\W+/g, "_")}.csv`, toCSV(ds.columns, coerce(ds)), "text/csv")}>⬇ Export CSV</button>
          <button className="btn" onClick={() => { const c = `V${ds.columns.length + 1}`; set({ ...ds, columns: [...ds.columns, c], types: { ...ds.types, [c]: "scale" } }); }}>+ Column</button>
          <button className="btn" onClick={normalize}>Normalize labels</button>
          <button className="btn" onClick={() => setReshape(reshape ? null : "long")}>⇄ Reshape</button>
          <button className="btn" onClick={() => { if (confirm("Clear all data?")) set({ columns: ["A", "B"], types: { A: "scale", B: "scale" }, rows: [] }); }}>Clear</button>
          <span className="spacer" style={{ flex: 1 }} />
          <span className="pill">{nRows} rows × {ds.columns.length} columns</span>
          <button className="btn primary" onClick={() => go("analysis")}>Analyse →</button>
        </div>
        {sheets && (
          <div className="row" style={{ marginTop: 10 }}>
            <span>Workbook sheets:</span>
            {sheets.names.map((n) => <button key={n} className="btn small" onClick={() => { importFile(sheets.file, n); setSheets(null); }}>{n}</button>)}
          </div>
        )}
        {reshape && (
          <div className="card" style={{ marginTop: 12, background: "var(--hover)" }}>
            <div className="tabs">
              <button className={`tab ${reshape === "long" ? "active" : ""}`} onClick={() => setReshape("long")}>Wide → long</button>
              <button className={`tab ${reshape === "wide" ? "active" : ""}`} onClick={() => setReshape("wide")}>Long → wide</button>
            </div>
            {reshape === "long" ? (
              <div className="col">
                <div>Identifier / between columns (kept): {ds.columns.map((c) => <label key={c} className="chk" style={{ display: "inline-flex", marginRight: 10 }}><input type="checkbox" checked={rs.ids.includes(c)} onChange={(e) => setRs({ ...rs, ids: e.target.checked ? [...rs.ids, c] : rs.ids.filter((x: string) => x !== c) })} />{c}</label>)}</div>
                <div>Condition columns (stacked): {ds.columns.map((c) => <label key={c} className="chk" style={{ display: "inline-flex", marginRight: 10 }}><input type="checkbox" checked={rs.values.includes(c)} onChange={(e) => setRs({ ...rs, values: e.target.checked ? [...rs.values, c] : rs.values.filter((x: string) => x !== c) })} />{c}</label>)}</div>
                <div className="row"><label className="field">New factor name<input type="text" value={rs.factor} onChange={(e) => setRs({ ...rs, factor: e.target.value })} /></label>
                  <label className="field">New value name<input type="text" value={rs.value} onChange={(e) => setRs({ ...rs, value: e.target.value })} /></label>
                  <button className="btn primary" disabled={!rs.values.length} onClick={toLong}>Reshape</button></div>
              </div>
            ) : (
              <div className="row">
                {(["subject", "key", "val"] as const).map((k) => (
                  <label key={k} className="field">{{ subject: "Subject column", key: "Within factor column", val: "Value column" }[k]}
                    <select value={rs[k]} onChange={(e) => setRs({ ...rs, [k]: e.target.value })}><option value="">–</option>{ds.columns.map((c) => <option key={c}>{c}</option>)}</select></label>
                ))}
                <button className="btn primary" disabled={!rs.subject || !rs.key || !rs.val} onClick={toWide}>Reshape</button>
              </div>
            )}
          </div>
        )}
      </div>
      <DataGrid ds={ds} onChange={set} />
      <div className="card role-violet" style={{ marginTop: 14 }}>
        <h3>Validation</h3>
        {issues.length ? issues.map((i, k) => <div key={k} className="warn">{i}</div>) : <p className="muted">No problems found.</p>}
        <p className="small muted">Warnings never block an analysis. Missing values are excluded listwise and reported.</p>
      </div>
    </div>
  );
}
