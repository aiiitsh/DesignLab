import { download, postBlob } from "./api";
import Analysis from "./pages/Analysis";
import Data from "./pages/Data";
import DOE from "./pages/DOE";
import Home from "./pages/Home";
import { DesignTools, PowerPage, SettingsPage } from "./pages/Misc";
import Report, { reportHtml } from "./pages/Report";
import Wizard from "./pages/Wizard";
import FlowChart from "./pages/FlowChart";
import HelpDots from "./components/HelpDots";
import { Page, useStore } from "./store";

const NAV: [Page, string, string][] = [
  ["home", "Home", "var(--amber)"],
  ["wizard", "Guided design", "var(--amber)"],
  ["flowchart", "Flow chart", "var(--amber)"],
  ["data", "Data", "var(--indigo)"],
  ["analysis", "Analysis", "var(--teal)"],
  ["power", "Power", "var(--sky)"],
  ["doe", "DOE workspace", "var(--laneD)"],
  ["design", "Design utilities", "var(--indigo)"],
  ["report", "Report", "var(--violet)"],
  ["settings", "Settings", "var(--muted)"],
];

export default function App() {
  const { page, go, project, update, settings, setSettings, toast, remember } = useStore();
  const saveProject = async () => {
    try {
      const blob = await postBlob("/api/project/save", {
        ...project,
        datasets: { main: { ...project.data } },
        report_html: project.pinned.length ? reportHtml(project, settings) : undefined,
      });
      download(`${project.name.replace(/\W+/g, "_") || "project"}.dlab`, blob);
      remember();
      toast("Project saved");
    } catch (e: any) { toast(e.message); }
  };
  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><div className="hex">D</div>DesignLab</div>
        {NAV.map(([p, label, color]) => (
          <button key={p} className={`nav ${page === p ? "active" : ""}`} onClick={() => go(p)} aria-current={page === p ? "page" : undefined}>
            <span className="dot" style={{ color }} />{label}
          </button>
        ))}
        <div className="spacer" />
        <div className="toggles">
          <input type="text" aria-label="Project name" value={project.name} onChange={(e) => update({ name: e.target.value })} style={{ fontWeight: 600 }} />
          <button className="btn small" onClick={saveProject}>💾 Save project (.dlab)</button>
          <label className="chk"><input type="checkbox" checked={settings.learn} onChange={(e) => setSettings({ learn: e.target.checked })} />Learn mode</label>
          <label className="chk"><input type="checkbox" checked={settings.helpDots !== false} onChange={(e) => setSettings({ helpDots: e.target.checked })} />Help dots</label>
          <label className="chk"><input type="checkbox" checked={settings.theme === "dark"} onChange={(e) => setSettings({ theme: e.target.checked ? "dark" : "light" })} />Dark theme</label>
          {project.pinned.length > 0 && <span className="small muted">{project.pinned.length} card(s) in the report</span>}
        </div>
      </aside>
      <main className="main">
        {page === "home" && <Home />}
        {page === "wizard" && <Wizard />}
        {page === "data" && <Data />}
        {page === "analysis" && <Analysis />}
        {page === "power" && <PowerPage />}
        {page === "doe" && <DOE />}
        {page === "design" && <DesignTools />}
        {page === "report" && <Report />}
        {page === "settings" && <SettingsPage />}
        {page === "flowchart" && <FlowChart />}
      </main>
      <HelpDots />
    </div>
  );
}
