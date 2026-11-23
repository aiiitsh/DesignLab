import { useState } from "react";
import { api } from "../api";
import PowerCalc from "../components/PowerCalc";
import { useStore } from "../store";

export function PowerPage() {
  const [m, setM] = useState(10);
  return (
    <div>
      <h1 className="page-title">Power analysis</h1>
      <p className="page-sub">Built-in G*Power: same noncentral t, F and χ² calculations, four modes, power curve and a "how to report" sentence.</p>
      <PowerCalc />
      <div className="card role-coral">
        <h3>Why not many t-tests? (Meeting 6)</h3>
        <div className="row">
          <label className="field">Number of tests<input type="number" min={1} value={m} onChange={(e) => setM(Number(e.target.value))} /></label>
          <div>Familywise α = 1 − (1 − .05)<sup>{m}</sup> = <b>{(1 - Math.pow(0.95, m)).toFixed(3)}</b>. Bonferroni α per test = .05 / {m} = <b>{(0.05 / m).toFixed(4)}</b>.</div>
        </div>
      </div>
    </div>
  );
}

export function DesignTools() {
  const [conds, setConds] = useState("A, B, C, D");
  const [method, setMethod] = useState("latin");
  const [n, setN] = useState(8);
  const [cb, setCb] = useState<any>(null);
  const [ci, setCi] = useState({ m: 50, sd: 10, n: 25 });
  const tcrit = (df: number) => { // two-sided 95% t critical value (approximation good to 3 decimals for df ≥ 2)
    const z = 1.959964; const g1 = (z ** 3 + z) / 4, g2 = (5 * z ** 5 + 16 * z ** 3 + 3 * z) / 96, g3 = (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / 384;
    return z + g1 / df + g2 / df ** 2 + g3 / df ** 3;
  };
  const se = ci.sd / Math.sqrt(ci.n);
  const t = tcrit(ci.n - 1);
  return (
    <div>
      <h1 className="page-title">Design utilities</h1>
      <p className="page-sub">Counterbalancing (full permutations or balanced Latin square) and a confidence-interval calculator.</p>
      <div className="card role-indigo">
        <h3>Counterbalancing generator</h3>
        <div className="row">
          <label className="field" style={{ flex: 1 }}>Conditions<input type="text" value={conds} onChange={(e) => setConds(e.target.value)} /></label>
          <label className="field">Method<select value={method} onChange={(e) => setMethod(e.target.value)}><option value="latin">Balanced Latin square (Williams)</option><option value="full">Full permutations (n!)</option></select></label>
          <label className="field">Participants<input type="number" value={n} onChange={(e) => setN(Number(e.target.value))} /></label>
          <button className="btn primary" onClick={async () => setCb(await api("/api/design/counterbalance", { conditions: conds.split(",").map((s) => s.trim()).filter(Boolean), method, participants: n }))}>Generate</button>
        </div>
        {cb && (
          <>
            <p className="small">{cb.method}: {cb.n_orders} orders. {cb.check && <>Each condition once per row {cb.check.each_once_per_row ? "✓" : "✗"}, once per column {cb.check.each_once_per_column ? "✓" : "✗"}, first-order carryover balanced {cb.check.carryover_balanced ? "✓" : "✗"}.</>}</p>
            {cb.note && <div className="warn">{cb.note}</div>}
            <table className="res"><thead><tr><th>Participant</th><th>Order #</th>{cb.orders[0].map((_: any, i: number) => <th key={i}>{i + 1}</th>)}</tr></thead>
              <tbody>{cb.assignment.map((a: any) => <tr key={a.participant}><td>{a.participant}</td><td>{a.order_no}</td>{a.order.map((c: string, j: number) => <td key={j}>{c}</td>)}</tr>)}</tbody></table>
          </>
        )}
      </div>
      <div className="card role-sky">
        <h3>Confidence interval calculator</h3>
        <div className="row">
          {(["m", "sd", "n"] as const).map((k) => <label key={k} className="field">{{ m: "Mean", sd: "SD", n: "n" }[k]}<input type="number" value={ci[k]} onChange={(e) => setCi({ ...ci, [k]: Number(e.target.value) })} /></label>)}
          <div>SE = SD/√n = <b>{se.toFixed(3)}</b>; t<sub>.975</sub>({ci.n - 1}) ≈ {t.toFixed(3)}; 95% CI = [<b>{(ci.m - t * se).toFixed(3)}</b>, <b>{(ci.m + t * se).toFixed(3)}</b>]</div>
        </div>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { settings, setSettings } = useStore();
  return (
    <div>
      <h1 className="page-title">Settings</h1>
      <div className="card" style={{ maxWidth: 560 }}>
        <div className="col">
          <label className="field">Name (report header)<input type="text" value={settings.name} onChange={(e) => setSettings({ name: e.target.value })} /></label>
          <label className="field">Student ID<input type="text" value={settings.studentId} onChange={(e) => setSettings({ studentId: e.target.value })} /></label>
          <label className="field">Default α<input type="number" step={0.01} value={settings.alpha} onChange={(e) => setSettings({ alpha: Number(e.target.value) })} /></label>
          <label className="chk"><input type="checkbox" checked={settings.theme === "dark"} onChange={(e) => setSettings({ theme: e.target.checked ? "dark" : "light" })} />Dark theme</label>
          <label className="chk"><input type="checkbox" checked={settings.learn} onChange={(e) => setSettings({ learn: e.target.checked })} />Learn mode (hover over numbers and column names)</label>
          <label className="chk"><input type="checkbox" checked={settings.helpDots !== false} onChange={(e) => setSettings({ helpDots: e.target.checked })} />Help dots (?) next to every label</label>
        </div>
      </div>
    </div>
  );
}
