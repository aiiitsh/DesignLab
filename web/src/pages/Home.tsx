import { useEffect, useRef, useState } from "react";
import { api, upload } from "../api";
import { guessType } from "../components/DataGrid";
import { ColType, newProject, Project, useStore } from "../store";

const LANE_COLOR: Record<string, string> = { A: "var(--laneA)", B: "var(--laneB)", C: "var(--laneC)", D: "var(--laneD)" };

export async function loadExample(id: string): Promise<Project> {
  const e = await api(`/api/examples/${id}`);
  const types: Record<string, ColType> = {};
  for (const c of e.columns) types[c] = (e.column_types?.[c] as ColType) ?? guessType(e.rows.map((r: any) => r[c]));
  const p: Project = {
    ...newProject(e.title),
    answers: e.wizard ?? {},
    data: { columns: e.columns, types, rows: e.rows },
    exampleId: id,
    example: e,
    pinned: [],
  };
  if (e.analysis_id) p.analysis = { id: e.analysis_id, roles: e.roles, options: { ...(e.options || {}), dv_labels: e.dv_labels } };
  return p;
}

export default function Home() {
  const { go, setProject, recent, toast } = useStore();
  const [examples, setExamples] = useState<any[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => { api("/api/examples").then(setExamples).catch(() => {}); }, []);

  const open = async (f: File) => {
    try {
      const p = await upload("/api/project/open", f);
      const ds = p.datasets?.main ?? Object.values(p.datasets ?? {})[0];
      setProject({ ...newProject(p.name), ...p, data: ds ? { columns: ds.columns, types: ds.types ?? {}, rows: ds.rows } : newProject().data });
      toast(`Opened ${p.name}`);
      go(p.outcome ? "analysis" : "wizard");
    } catch (e: any) { toast(e.message); }
  };

  return (
    <div>
      <h1 className="page-title">DesignLab</h1>
      <p className="page-sub">Plan, power, analyse and report experiments the SYDE 640 way. Everything runs on this computer.</p>
      <div className="hero-cards">
        <button className="hero" onClick={() => { setProject(newProject()); go("wizard"); }}>
          <div className="hex">1</div><h2>Start a new experiment (guided)</h2>
          <p>Walk the course flow chart one question at a time: design, sample size, data sheet, analysis, APA report.</p>
        </button>
        <button className="hero" onClick={() => fileRef.current?.click()}>
          <div className="hex" style={{ background: "var(--indigo)" }}>2</div><h2>Open project</h2>
          <p>Open a saved .dlab project file (a zip with project.json, data and report).</p>
        </button>
        <button className="hero" onClick={() => go("analysis")}>
          <div className="hex" style={{ background: "var(--teal)" }}>3</div><h2>Quick analysis (expert mode)</h2>
          <p>Skip the wizard and pick any analysis directly, as in JASP's menus.</p>
        </button>
        <input ref={fileRef} type="file" accept=".dlab,.zip" hidden onChange={(e) => e.target.files?.[0] && open(e.target.files[0])} />
      </div>

      <h2 style={{ fontSize: 17 }}>Course examples</h2>
      <p className="muted small">Each opens as a ready-made project with the wizard answers filled in.</p>
      <div className="grid3" style={{ marginBottom: 24 }}>
        {examples.map((e) => (
          <button key={e.id} className="example" style={{ borderLeftColor: LANE_COLOR[e.lane] }}
            onClick={async () => {
              try {
                const p = await loadExample(e.id);
                setProject(p);
                go(e.lane === "D" ? "doe" : "analysis");
              } catch (err: any) { toast(err.message); }
            }}>
            <b>{e.title}</b><span className="small muted">{e.subtitle}</span>
            <div className="small" style={{ marginTop: 6 }}><span className="pill">Lane {e.lane}</span></div>
          </button>
        ))}
      </div>

      {recent.length > 0 && (
        <>
          <h2 style={{ fontSize: 17 }}>Recent projects</h2>
          <div className="grid3">
            {recent.map((r) => (
              <button key={r.name + r.updated} className="example" onClick={() => { setProject(r.project); go(r.project.outcome ? "analysis" : "wizard"); }}>
                <b>{r.name}</b><span className="small muted">{new Date(r.updated).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
