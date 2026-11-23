import { useEffect, useRef, useState } from "react";
import { useStore } from "../store";

/** The HW3 flow chart, drawn live inside the app (same HTML source as the PDF). Zoom, drag and search. */
const W = 4494, H = 3179;

export default function FlowChart() {
  const { go } = useStore();
  const wrap = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const [z, setZ] = useState(0.3);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<HTMLElement[]>([]);
  const [hitIx, setHitIx] = useState(0);
  const [ready, setReady] = useState(false);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);

  const fit = () => {
    const el = wrap.current; if (!el) return;
    const s = Math.min(el.clientWidth / W, el.clientHeight / H);
    setZ(s); setPos({ x: (el.clientWidth - W * s) / 2, y: (el.clientHeight - H * s) / 2 });
  };
  useEffect(() => { fit(); window.addEventListener("resize", fit); return () => window.removeEventListener("resize", fit); }, []);

  const zoomAt = (factor: number, cx?: number, cy?: number) => {
    const el = wrap.current; if (!el) return;
    const ox = cx ?? el.clientWidth / 2, oy = cy ?? el.clientHeight / 2;
    setZ((oz) => {
      const nz = Math.max(0.08, Math.min(2.5, oz * factor));
      setPos((p) => ({ x: ox - (ox - p.x) * (nz / oz), y: oy - (oy - p.y) * (nz / oz) }));
      return nz;
    });
  };

  const focusBox = (el: HTMLElement) => {
    const w = wrap.current; if (!w) return;
    const doc = frame.current?.contentDocument; if (!doc) return;
    const r = el.getBoundingClientRect(); // in iframe (unscaled) coordinates
    const nz = Math.max(z, 0.7);
    setZ(nz);
    setPos({ x: w.clientWidth / 2 - (r.left + r.width / 2) * nz, y: w.clientHeight / 2 - (r.top + r.height / 2) * nz });
  };

  // search: highlight matching boxes in the chart
  useEffect(() => {
    const doc = frame.current?.contentDocument;
    if (!doc || !ready) return;
    doc.querySelectorAll(".dl-hit").forEach((e) => e.classList.remove("dl-hit"));
    if (q.trim().length < 2) { setHits([]); return; }
    const needle = q.trim().toLowerCase();
    const cands = Array.from(doc.querySelectorAll<HTMLElement>("#page .n, #page .lane, #page .note"));
    const found = cands.filter((e) => e.textContent?.toLowerCase().includes(needle));
    const uniq = found.filter((e) => !found.some((o) => o !== e && e.contains(o)));
    uniq.forEach((e) => e.classList.add("dl-hit"));
    setHits(uniq); setHitIx(0);
    if (uniq[0]) focusBox(uniq[0]);
  }, [q, ready]);

  const onLoad = () => {
    const doc = frame.current?.contentDocument; if (!doc) return;
    const st = doc.createElement("style");
    st.textContent = `html,body{overflow:hidden} .dl-hit{outline:8px solid #ff3b7f !important; outline-offset:4px; box-shadow:0 0 0 18px rgba(255,59,127,.18) !important}`;
    doc.head.appendChild(st);
    setReady(true);
  };

  const presets: [string, string][] = [["Lane A", "Compare conditions"], ["Lane B", "Relationship"], ["Lane C", "Categorical"], ["Lane D", "Engineering"], ["Plan", "research question"]];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 48px)" }}>
      <div className="row" style={{ alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <h1 className="page-title" style={{ margin: 0 }} data-help="The HW3 design and analysis flow chart, built into DesignLab. Drag to move, scroll or use the buttons to zoom, and search for any test or term.">Flow chart</h1>
        <div className="spacer" style={{ flex: 1 }} />
        <input type="search" placeholder="Search the chart (e.g. Welch, Mauchly, CCD)…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 280 }} aria-label="Search the chart" />
        {hits.length > 0 && <span className="small muted">{hitIx + 1} / {hits.length}</span>}
        {hits.length > 1 && <button className="btn small" onClick={() => { const i = (hitIx + 1) % hits.length; setHitIx(i); focusBox(hits[i]); }}>Next match</button>}
        <button className="btn small" onClick={() => zoomAt(1 / 1.25)} aria-label="Zoom out">−</button>
        <span className="small" style={{ width: 44, textAlign: "center" }}>{Math.round(z * 100)}%</span>
        <button className="btn small" onClick={() => zoomAt(1.25)} aria-label="Zoom in">+</button>
        <button className="btn small" onClick={fit}>Fit</button>
        <button className="btn small" onClick={() => { const w = wrap.current!; setZ(1); setPos({ x: w.clientWidth / 2 - W / 2, y: 20 }); }}>100%</button>
        <button className="btn small primary" onClick={() => go("wizard")}>Walk it as a wizard →</button>
      </div>
      <div className="row" style={{ gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
        {presets.map(([label, term]) => <button key={label} className="pill" style={{ cursor: "pointer", border: "1px solid var(--line)" }} onClick={() => setQ(term)}>{label}</button>)}
        {q && <button className="pill" style={{ cursor: "pointer", border: "1px solid var(--line)" }} onClick={() => setQ("")}>Clear</button>}
      </div>
      <div
        ref={wrap}
        className="flow-wrap no-help"
        style={{ flex: 1, position: "relative", overflow: "hidden", borderRadius: 12, border: "1px solid var(--line)", background: "#fbfaf7", cursor: drag.current ? "grabbing" : "grab", touchAction: "none" }}
        onWheel={(e) => { const r = wrap.current!.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX - r.left, e.clientY - r.top); }}
        onPointerDown={(e) => { (e.target as HTMLElement).setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, px: pos.x, py: pos.y }; }}
        onPointerMove={(e) => { const d = drag.current; if (d) setPos({ x: d.px + e.clientX - d.x, y: d.py + e.clientY - d.y }); }}
        onPointerUp={() => { drag.current = null; }}
        onDoubleClick={(e) => { const r = wrap.current!.getBoundingClientRect(); zoomAt(1.6, e.clientX - r.left, e.clientY - r.top); }}
      >
        <iframe
          ref={frame}
          src="/flowchart.html"
          title="HW3 design and analysis flow chart"
          onLoad={onLoad}
          scrolling="no"
          style={{ position: "absolute", left: 0, top: 0, width: W, height: H, border: 0, transformOrigin: "0 0", transform: `translate(${pos.x}px, ${pos.y}px) scale(${z})`, pointerEvents: "none" }}
        />
      </div>
      <p className="small muted" style={{ margin: "6px 2px 0" }}>Drag to move · scroll or double-click to zoom · search highlights every box that mentions a term.</p>
    </div>
  );
}
