import { useEffect, useRef } from "react";
import { useStore } from "../store";
import { GLOSSARY } from "./Learn";
import { HELP, RULES } from "./helpText";

/**
 * Puts a small (?) dot next to every label, field, heading, table header, checkbox and nav item.
 * Hovering (or focusing) the dot explains what that thing is for.
 * Help text comes from, in order: a data-help attribute, the element's title, the HELP dictionary,
 * the Learn-mode glossary, then keyword rules.
 */
const TARGETS = [
  ".side .nav", ".side label.chk",
  ".main h1", ".main h2", ".main h3", ".main h4", ".main summary",
  ".main label.field", ".main div.field", ".main label.chk", ".main th", ".main [data-help]",
].join(",");

const norm = (s: string) => s.replace(/\s+/g, " ").replace(/^[\p{Extended_Pictographic}\uFE0F\s]+/u, "").replace(/^[\d]+\s*·\s*/, "").replace(/[:：]\s*$/, "").trim();

function ownText(el: Element): string {
  let t = "";
  el.childNodes.forEach((n) => {
    if (n.nodeType === Node.TEXT_NODE) t += n.textContent;
    else if (n instanceof HTMLElement && ["B", "I", "EM", "SUB", "SUP", "SPAN"].includes(n.tagName) && !n.classList.contains("qdot") && !n.classList.contains("small") && !n.classList.contains("lecture")) t += n.textContent;
  });
  return norm(t);
}

export function helpFor(key: string): string | undefined {
  if (!key) return undefined;
  if (HELP[key]) return HELP[key];
  const lower = key.toLowerCase();
  for (const k of Object.keys(HELP)) if (k.toLowerCase() === lower) return HELP[k];
  if (GLOSSARY[key]) return GLOSSARY[key];
  for (const k of Object.keys(HELP)) if (k.length > 6 && lower.startsWith(k.toLowerCase())) return HELP[k];
  for (const [re, text] of RULES) if (re.test(key)) return text;
  return undefined;
}

function decorate(root: HTMLElement) {
  root.querySelectorAll<HTMLElement>(TARGETS).forEach((el) => {
    if (el.closest(".qdot, .tip, .no-help, .plot, .js-plotly-plot")) return;
    if (el.querySelector(":scope > .qdot")) return;
    const key = ownText(el);
    const text = el.dataset.help || el.getAttribute("title") || helpFor(key);
    let tip = text;
    if (!tip && key && el.matches("label.chk") && el.closest(".field")) tip = `"${key}" is a column in your data. Tick it to use it in this role.`;
    if (!tip && key && el.matches("label.field, div.field")) tip = `"${key}": a column or setting from your data. Enter or pick its value here.`;
    if (!tip && key && el.tagName === "TH") tip = `"${key}": a variable, factor or level from your data.`;
    if (!tip) { if (key) (window as any).__qdMissing?.add(`${el.tagName.toLowerCase()}: ${key}`); return; }
    const dot = document.createElement("span");
    dot.className = "qdot";
    dot.tabIndex = 0;
    dot.setAttribute("role", "img");
    dot.setAttribute("aria-label", `Help: ${tip}`);
    dot.dataset.tip = tip;
    dot.textContent = "?";
    // put the dot right after the element's label text (before any input it wraps)
    const firstEl = Array.from(el.childNodes).find((n) => n.nodeType === Node.ELEMENT_NODE && /^(INPUT|SELECT|TEXTAREA|DIV|BUTTON)$/.test((n as HTMLElement).tagName) && !(n as HTMLElement).classList.contains("qdot"));
    if (firstEl && el.tagName !== "TH" && !(el.tagName === "LABEL" && el.classList.contains("chk"))) el.insertBefore(dot, firstEl);
    else el.appendChild(dot);
  });
}

export default function HelpDots() {
  const { settings } = useStore();
  const tip = useRef<HTMLDivElement>(null);
  const on = settings.helpDots !== false;

  useEffect(() => {
    document.documentElement.classList.toggle("no-qdots", !on);
    if (!on) return;
    const app = document.querySelector<HTMLElement>(".app");
    if (!app) return;
    let raf = 0;
    const run = () => { raf = 0; decorate(app); };
    run();
    const mo = new MutationObserver(() => { if (!raf) raf = requestAnimationFrame(run); });
    mo.observe(app, { childList: true, subtree: true, characterData: true });

    const show = (e: Event) => {
      const t = (e.target as HTMLElement).closest?.(".qdot") as HTMLElement | null;
      const box = tip.current;
      if (!t || !box) return;
      box.textContent = t.dataset.tip || "";
      box.style.display = "block";
      const r = t.getBoundingClientRect();
      const w = box.offsetWidth, h = box.offsetHeight;
      let x = r.left + r.width / 2 - w / 2, y = r.bottom + 8;
      if (y + h > window.innerHeight - 8) y = r.top - h - 8;
      x = Math.max(8, Math.min(x, window.innerWidth - w - 8));
      box.style.left = `${x}px`; box.style.top = `${y}px`;
    };
    const hide = (e: Event) => {
      if ((e.target as HTMLElement).closest?.(".qdot") && tip.current) tip.current.style.display = "none";
    };
    const stopClick = (e: Event) => {
      if ((e.target as HTMLElement).closest?.(".qdot")) { e.preventDefault(); e.stopPropagation(); show(e); }
    };
    document.addEventListener("mouseover", show);
    document.addEventListener("mouseout", hide);
    document.addEventListener("focusin", show);
    document.addEventListener("focusout", hide);
    document.addEventListener("click", stopClick, true);
    return () => {
      mo.disconnect(); if (raf) cancelAnimationFrame(raf);
      document.removeEventListener("mouseover", show);
      document.removeEventListener("mouseout", hide);
      document.removeEventListener("focusin", show);
      document.removeEventListener("focusout", hide);
      document.removeEventListener("click", stopClick, true);
    };
  }, [on]);

  return <div ref={tip} className="qtip" role="tooltip" style={{ display: "none" }} />;
}
