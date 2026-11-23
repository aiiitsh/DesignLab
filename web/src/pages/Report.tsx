import { download, postBlob } from "../api";
import { useStore } from "../store";

const REPORT_CSS = `body{font-family:Inter,Segoe UI,system-ui,sans-serif;color:#1d2233;max-width:820px;margin:24px auto;padding:0 20px;line-height:1.5;font-size:13.5px}
h1{font-size:22px;margin:0}h2{font-size:16px;border-bottom:2px solid #e9a400;padding-bottom:4px;margin-top:26px}
.hdr{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid #0d8a87;padding-bottom:10px;margin-bottom:16px}
table.res{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0;font-variant-numeric:tabular-nums}
table.res caption{text-align:left;font-weight:600;padding:4px 0}
table.res th{border-bottom:2px solid #1d2233;text-align:right;padding:4px 6px}table.res td{border-bottom:1px solid #ddd;text-align:right;padding:3px 6px}
table.res th:first-child,table.res td:first-child{text-align:left}.foot{font-size:11.5px;color:#555}
.apa{background:#e2f4f3;padding:10px 12px;border-radius:8px}dl{display:grid;grid-template-columns:170px 1fr;gap:4px 10px}dt{color:#666}dd{margin:0}
section{break-inside:avoid}@page{size:A4;margin:16mm 14mm}`;

export function reportHtml(project: any, settings: any): string {
  const date = new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
  const body = project.pinned.map((c: any) => `<section><h2>${c.title}</h2>${c.html ?? ""}</section>`).join("\n");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${project.name} – DesignLab report</title><style>${REPORT_CSS}</style></head><body>
<div class="hdr"><div><h1>${project.name}</h1><div>${project.outcome?.design_name ?? ""}</div></div><div style="text-align:right"><b>${settings.name}</b><br>Student ID: ${settings.studentId}<br>${date}</div></div>
${body || "<p>No cards pinned yet.</p>"}
<p style="color:#888;font-size:11px;margin-top:30px">Generated with DesignLab (SYDE 640).</p></body></html>`;
}

export default function Report() {
  const { project, setProject, settings, toast } = useStore();
  const move = (i: number, d: number) => {
    const p = project.pinned.slice();
    const j = i + d;
    if (j < 0 || j >= p.length) return;
    [p[i], p[j]] = [p[j], p[i]];
    setProject({ ...project, pinned: p });
  };
  const html = reportHtml(project, settings);
  const pdf = async () => {
    try {
      download("DesignLab_report.pdf", await postBlob("/api/report/pdf", { html }));
    } catch (e: any) {
      toast("Server PDF unavailable; opening the print dialog (choose Save as PDF)");
      const w = window.open("", "_blank");
      if (w) { w.document.write(html); w.document.close(); setTimeout(() => w.print(), 400); }
    }
  };
  return (
    <div>
      <h1 className="page-title">Report</h1>
      <p className="page-sub">Pin cards from any page (📌). Order: design → power → descriptives → assumptions → results → APA text. The header uses the name and student ID from Settings.</p>
      <div className="card">
        <div className="row">
          <button className="btn primary" onClick={pdf} disabled={!project.pinned.length}>Export PDF</button>
          <button className="btn" onClick={() => download(`${project.name.replace(/\W+/g, "_")}_report.html`, html, "text/html")} disabled={!project.pinned.length}>Export HTML</button>
          <span className="muted small">Header: {settings.name} · {settings.studentId}</span>
        </div>
      </div>
      {project.pinned.length === 0 && <p className="muted">Nothing pinned yet.</p>}
      {project.pinned.map((c, i) => (
        <div className="card" key={c.id}>
          <div className="card-head">
            <h3>{c.title}</h3>
            <span className="row">
              <button className="btn small" onClick={() => move(i, -1)} aria-label="Move up">↑</button>
              <button className="btn small" onClick={() => move(i, 1)} aria-label="Move down">↓</button>
              <button className="btn small" onClick={() => setProject({ ...project, pinned: project.pinned.filter((x) => x.id !== c.id) })}>Remove</button>
            </span>
          </div>
          <div dangerouslySetInnerHTML={{ __html: c.html ?? "" }} />
        </div>
      ))}
    </div>
  );
}
