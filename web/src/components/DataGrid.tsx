import React from "react";
import { ColType, Dataset } from "../store";

export const isNum = (v: any) => v !== null && v !== undefined && v !== "" && !isNaN(Number(v));

export function guessType(values: any[]): ColType {
  const vals = values.filter((v) => v !== null && v !== undefined && v !== "");
  if (!vals.length) return "scale";
  if (vals.every(isNum)) {
    const uniq = new Set(vals.map(Number));
    return uniq.size <= 2 ? "nominal" : "scale";
  }
  return "nominal";
}

export function coerce(ds: Dataset): Record<string, any>[] {
  return ds.rows
    .filter((r) => ds.columns.some((c) => r[c] !== undefined && r[c] !== null && r[c] !== ""))
    .map((r) => {
      const o: Record<string, any> = {};
      for (const c of ds.columns) {
        const v = r[c];
        if (v === undefined || v === null || v === "") o[c] = null;
        else if (ds.types[c] !== "nominal" && isNum(v)) o[c] = Number(v);
        else if (isNum(v) && ds.types[c] === "nominal") o[c] = Number(v);
        else o[c] = typeof v === "string" ? v : v;
      }
      return o;
    });
}

const TYPE_LABEL: Record<ColType, string> = { scale: "Scale", ordinal: "Ordinal", nominal: "Nominal" };
const TYPE_ICON: Record<ColType, string> = { scale: "📏", ordinal: "📶", nominal: "🏷" };

export default function DataGrid({ ds, onChange }: { ds: Dataset; onChange: (d: Dataset) => void }) {
  const setCell = (ri: number, c: string, v: string) => {
    const rows = ds.rows.slice();
    while (rows.length <= ri) rows.push({});
    rows[ri] = { ...rows[ri], [c]: v };
    if (ri === rows.length - 1) rows.push({});
    onChange({ ...ds, rows });
  };
  const onPaste = (e: React.ClipboardEvent, ri: number, ci: number) => {
    const text = e.clipboardData.getData("text");
    if (!text.includes("\t") && !text.includes("\n")) return;
    e.preventDefault();
    const lines = text.replace(/\r/g, "").split("\n").filter((l, i, a) => l !== "" || i < a.length - 1);
    const cols = ds.columns.slice();
    const types = { ...ds.types };
    const rows = ds.rows.slice();
    lines.forEach((line, dr) => {
      const cells = line.split("\t");
      cells.forEach((val, dc) => {
        let c = cols[ci + dc];
        if (!c) {
          c = `V${cols.length + 1}`;
          cols.push(c);
          types[c] = "scale";
        }
        while (rows.length <= ri + dr) rows.push({});
        rows[ri + dr] = { ...rows[ri + dr], [c]: val.trim() };
      });
    });
    rows.push({});
    onChange({ ...ds, columns: cols, types, rows });
  };
  const rename = (old: string, nu: string) => {
    if (!nu || nu === old || ds.columns.includes(nu)) return;
    const columns = ds.columns.map((c) => (c === old ? nu : c));
    const types: Record<string, ColType> = {};
    columns.forEach((c, i) => (types[c] = ds.types[ds.columns[i]] ?? "scale"));
    const rows = ds.rows.map((r) => { const o = { ...r, [nu]: r[old] }; delete o[old]; return o; });
    onChange({ ...ds, columns, types, rows });
  };
  const setType = (c: string, t: ColType) => onChange({ ...ds, types: { ...ds.types, [c]: t } });
  const removeCol = (c: string) => onChange({ ...ds, columns: ds.columns.filter((x) => x !== c) });
  const display: Record<string, any>[] = ds.rows.length < 30 ? [...ds.rows, ...Array.from({ length: 30 - ds.rows.length }, () => ({}))] : ds.rows;

  return (
    <div className="grid-wrap">
      <table className="grid">
        <thead>
          <tr>
            <th className="rn">#</th>
            {ds.columns.map((c, ci) => (
              <th key={c + ci}>
                <div className="colhead">
                  <div className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
                    <span className={`ticon ${ds.types[c]}`} title={TYPE_LABEL[ds.types[c]]} aria-label={TYPE_LABEL[ds.types[c]]}>{TYPE_ICON[ds.types[c] ?? "scale"]}</span>
                    <input defaultValue={c} aria-label={`Column name ${c}`} onBlur={(e) => rename(c, e.target.value.trim())} />
                    <button className="btn small" style={{ padding: "0 5px" }} title="Delete column" onClick={() => removeCol(c)}>×</button>
                  </div>
                  <select value={ds.types[c] ?? "scale"} onChange={(e) => setType(c, e.target.value as ColType)} aria-label={`Type of ${c}`}>
                    <option value="scale">Scale (interval/ratio)</option>
                    <option value="ordinal">Ordinal</option>
                    <option value="nominal">Nominal</option>
                  </select>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {display.map((r, ri) => (
            <tr key={ri}>
              <td className="rn">{ri + 1}</td>
              {ds.columns.map((c, ci) => {
                const v = r[c];
                const empty = v === undefined || v === null || v === "";
                const bad = !empty && ds.types[c] === "scale" && !isNum(v);
                const rowHas = ds.columns.some((x) => r[x] !== undefined && r[x] !== null && r[x] !== "");
                return (
                  <td key={c} className={bad ? "bad" : empty && rowHas ? "missing" : ""}>
                    <input value={v ?? ""} onChange={(e) => setCell(ri, c, e.target.value)} onPaste={(e) => onPaste(e, ri, ci)} aria-label={`Row ${ri + 1} ${c}`} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function validate(ds: Dataset, groupCols: string[] = []): string[] {
  const rows = coerce(ds);
  const out: string[] = [];
  for (const c of ds.columns) {
    const vals = rows.map((r) => r[c]);
    const miss = vals.filter((v) => v === null).length;
    if (miss) out.push(`${c}: ${miss} missing value(s).`);
    if (ds.types[c] === "scale") {
      const bad = vals.filter((v) => v !== null && typeof v !== "number").length;
      if (bad) out.push(`${c}: ${bad} cell(s) are not numeric.`);
    }
    if (ds.types[c] === "nominal") {
      const strs = vals.filter((v) => typeof v === "string") as string[];
      const norm = new Set(strs.map((s) => s.trim().toLowerCase()));
      const raw = new Set(strs);
      if (norm.size < raw.size) out.push(`${c}: labels differ only in case or spaces (e.g. "yes"/"Yes"). Use "Normalize labels".`);
    }
  }
  for (const g of groupCols) {
    const counts: Record<string, number> = {};
    rows.forEach((r) => { if (r[g] !== null) counts[r[g]] = (counts[r[g]] || 0) + 1; });
    const small = Object.entries(counts).filter(([, n]) => n < 2).map(([k]) => k);
    if (small.length) out.push(`${g}: group(s) ${small.join(", ")} have fewer than 2 values.`);
    const ns = new Set(Object.values(counts));
    if (ns.size > 1) out.push(`${g}: unbalanced groups (${Object.entries(counts).map(([k, n]) => `${k} = ${n}`).join(", ")}). This is allowed.`);
  }
  return out;
}
