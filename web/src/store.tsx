import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ColType = "scale" | "ordinal" | "nominal";
export interface Dataset {
  columns: string[];
  types: Record<string, ColType>;
  rows: Record<string, any>[];
  labels?: Record<string, Record<string, string>>;
}
export interface Card {
  id: string;
  title: string;
  kind: string;
  html?: string;
  payload?: any;
}
export interface AnalysisSpec {
  id: string;
  roles: Record<string, any>;
  options: Record<string, any>;
}
export interface Project {
  name: string;
  answers: Record<string, any>;
  outcome?: any;
  data: Dataset;
  analysis?: AnalysisSpec;
  pinned: Card[];
  exampleId?: string;
  example?: any;
  power?: any;
  updated?: string;
}
export interface Settings {
  name: string;
  studentId: string;
  theme: "light" | "dark";
  learn: boolean;
  alpha: number;
  helpDots?: boolean;
}
export type Page = "home" | "wizard" | "data" | "analysis" | "power" | "doe" | "design" | "report" | "settings" | "flowchart";

export const emptyData = (): Dataset => ({
  columns: ["A", "B", "C"],
  types: { A: "scale", B: "scale", C: "scale" },
  rows: Array.from({ length: 10 }, () => ({})),
});
export const newProject = (name = "Untitled experiment"): Project => ({ name, answers: {}, data: emptyData(), pinned: [] });

function load<T>(key: string, fallback: T): T {
  try {
    const s = localStorage.getItem(key);
    return s ? (JSON.parse(s) as T) : fallback;
  } catch {
    return fallback;
  }
}
function save(key: string, v: unknown) {
  try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage unavailable */ }
}

interface Ctx {
  project: Project;
  setProject: React.Dispatch<React.SetStateAction<Project>>;
  update: (p: Partial<Project>) => void;
  settings: Settings;
  setSettings: (s: Partial<Settings>) => void;
  page: Page;
  go: (p: Page) => void;
  toast: (msg: string) => void;
  pin: (c: Omit<Card, "id">) => void;
  recent: { name: string; updated: string; project: Project }[];
  remember: () => void;
}
const C = createContext<Ctx>(null as any);
export const useStore = () => useContext(C);

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [project, setProject] = useState<Project>(() => load("dl.project", newProject()));
  const [settings, setSettingsState] = useState<Settings>(() =>
    load("dl.settings", { name: "Ahmed Hesham Desoky", studentId: "21280040", theme: "light", learn: false, alpha: 0.05 }),
  );
  const [page, setPage] = useState<Page>(() => (location.hash.slice(1) as Page) || "home");
  const [msg, setMsg] = useState<string | null>(null);
  const [recent, setRecent] = useState(() => load<Ctx["recent"]>("dl.recent", []));

  useEffect(() => save("dl.project", project), [project]);
  useEffect(() => {
    save("dl.settings", settings);
    document.documentElement.dataset.theme = settings.theme;
  }, [settings]);
  useEffect(() => {
    const h = () => setPage(((location.hash.slice(1) as Page) || "home"));
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      project,
      setProject,
      update: (p) => setProject((old) => ({ ...old, ...p, updated: new Date().toISOString() })),
      settings,
      setSettings: (s) => setSettingsState((o) => ({ ...o, ...s })),
      page,
      go: (p) => { location.hash = p; setPage(p); document.querySelector(".main")?.scrollTo(0, 0); },
      toast: (m) => { setMsg(m); setTimeout(() => setMsg(null), 2600); },
      pin: (c) => {
        setProject((old) => ({ ...old, pinned: [...old.pinned, { ...c, id: Math.random().toString(36).slice(2) }] }));
        setMsg("Added to the report");
        setTimeout(() => setMsg(null), 1800);
      },
      recent,
      remember: () => {
        const r = [{ name: project.name, updated: new Date().toISOString(), project }, ...recent.filter((x) => x.name !== project.name)].slice(0, 8);
        setRecent(r);
        save("dl.recent", r);
      },
    }),
    [project, settings, page, recent],
  );
  return (
    <C.Provider value={value}>
      {children}
      {msg && <div className="toast" role="status">{msg}</div>}
    </C.Provider>
  );
}
