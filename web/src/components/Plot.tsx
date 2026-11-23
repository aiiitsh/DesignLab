import { useEffect, useRef } from "react";
// @ts-ignore - plotly ships no types for the min bundle
import Plotly from "plotly.js-dist-min";

export default function Plot({ fig, height }: { fig: { data: any[]; layout: any }; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !fig) return;
    const dark = document.documentElement.dataset.theme === "dark";
    const ink = dark ? "#e8eaf2" : "#1d2233";
    const grid = dark ? "#2e3242" : "#e6e9f0";
    const layout = {
      ...fig.layout,
      height: height ?? fig.layout?.height ?? 320,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Inter, Segoe UI, system-ui, sans-serif", color: ink, size: 12 },
      xaxis: { gridcolor: grid, zerolinecolor: grid, ...(fig.layout?.xaxis || {}) },
      yaxis: { gridcolor: grid, zerolinecolor: grid, ...(fig.layout?.yaxis || {}) },
      legend: { orientation: "h", y: -0.2, ...(fig.layout?.legend || {}) },
    };
    Plotly.react(ref.current, fig.data, layout, { displaylogo: false, responsive: true });
  }, [fig, height]);
  useEffect(() => {
    const el = ref.current;
    return () => { if (el) Plotly.purge(el); };
  }, []);
  return <div ref={ref} className="plot" />;
}
