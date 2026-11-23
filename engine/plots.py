"""Plotly figure builders (plain JSON dicts so the frontend just renders them)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

PALETTE = ["#0d8a87", "#2f6fd0", "#8a4fc9", "#e07a1f", "#e0532c", "#2483cc", "#4f55c9", "#e9a400"]


def _layout(title: str, xt: str = "", yt: str = "", **kw) -> dict:
    lay = {"title": {"text": title, "font": {"size": 14}}, "xaxis": {"title": {"text": xt}},
           "yaxis": {"title": {"text": yt}}, "margin": {"l": 55, "r": 20, "t": 40, "b": 50},
           "height": 340, "showlegend": kw.pop("showlegend", True)}
    lay.update(kw)
    return lay


def boxplot(groups: dict, title: str, ylabel: str = "") -> dict:
    """Box plot with the median line, whiskers at 1.5 IQR, outliers as dots, jittered raw points."""
    data = []
    for i, (name, vals) in enumerate(groups.items()):
        vals = [float(v) for v in pd.Series(vals).dropna()]
        data.append({"type": "box", "y": vals, "name": str(name), "boxpoints": "all", "jitter": 0.35,
                     "pointpos": 0, "marker": {"color": PALETTE[i % len(PALETTE)], "size": 5, "opacity": .6},
                     "line": {"color": PALETTE[i % len(PALETTE)]}, "boxmean": True})
    return {"data": data, "layout": _layout(title, "", ylabel, showlegend=False)}


def qqplot(x, title: str) -> dict:
    x = np.sort(pd.Series(x).dropna().astype(float).values)
    n = len(x)
    if n < 3:
        return {"data": [], "layout": _layout(title)}
    (osm, osr), (slope, inter, _) = stats.probplot(x, dist="norm")
    line_x = [float(osm.min()), float(osm.max())]
    return {"data": [
        {"type": "scatter", "mode": "markers", "x": osm.tolist(), "y": osr.tolist(), "name": "data",
         "marker": {"color": "#7a4ed6"}},
        {"type": "scatter", "mode": "lines", "x": line_x, "y": [inter + slope * v for v in line_x],
         "name": "normal", "line": {"color": "#e0532c", "dash": "dash"}}],
        "layout": _layout(title, "Theoretical quantiles", "Observed", showlegend=False, height=300)}


def interaction_plot(df: pd.DataFrame, dv: str, x: str, trace: str, title: str = "",
                     err: str = "se") -> dict:
    data = []
    xs = sorted(df[x].dropna().unique(), key=lambda v: (str(type(v)), v))
    for i, (lvl, sub) in enumerate(df.groupby(trace, sort=True)):
        g = sub.groupby(x)[dv]
        means = g.mean().reindex(xs)
        se = (g.std(ddof=1) / np.sqrt(g.count())).reindex(xs)
        data.append({"type": "scatter", "mode": "lines+markers", "x": [str(v) for v in xs],
                     "y": means.tolist(), "name": f"{trace} = {lvl}",
                     "error_y": {"type": "data", "array": se.fillna(0).tolist(), "visible": True},
                     "line": {"color": PALETTE[i % len(PALETTE)]}})
    return {"data": data, "layout": _layout(title or f"{dv}: {x} × {trace}", x, f"Mean {dv} (±SE)")}


def means_plot(labels, means, errs, title: str, ylabel: str = "") -> dict:
    return {"data": [{"type": "scatter", "mode": "lines+markers", "x": [str(l) for l in labels],
                      "y": list(means), "error_y": {"type": "data", "array": list(errs), "visible": True},
                      "line": {"color": "#0d8a87"}}],
            "layout": _layout(title, "", ylabel, showlegend=False)}


def scatter_fit(x, y, xlab: str, ylab: str, fit_x=None, fit_y=None, lo=None, hi=None) -> dict:
    data = [{"type": "scatter", "mode": "markers", "x": list(x), "y": list(y), "name": "data",
             "marker": {"color": "#2f6fd0", "opacity": .7}}]
    if fit_x is not None:
        if lo is not None:
            data.append({"type": "scatter", "mode": "lines", "x": list(fit_x) + list(fit_x)[::-1],
                         "y": list(hi) + list(lo)[::-1], "fill": "toself", "fillcolor": "rgba(13,138,135,.15)",
                         "line": {"width": 0}, "name": "95% CI", "hoverinfo": "skip"})
        data.append({"type": "scatter", "mode": "lines", "x": list(fit_x), "y": list(fit_y), "name": "fit",
                     "line": {"color": "#0d8a87"}})
    return {"data": data, "layout": _layout(f"{ylab} vs {xlab}", xlab, ylab, showlegend=False)}


def resid_fitted(fitted, resid) -> dict:
    return {"data": [{"type": "scatter", "mode": "markers", "x": list(fitted), "y": list(resid),
                      "marker": {"color": "#7a4ed6"}}],
            "layout": _layout("Residuals vs fitted", "Fitted", "Residual", showlegend=False,
                              shapes=[{"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": 0, "y1": 0,
                                       "line": {"dash": "dash", "color": "#888"}}])}


def bar(labels, values, title: str, ylabel: str = "", colors=None, horizontal=False) -> dict:
    tr = {"type": "bar", "marker": {"color": colors or "#2483cc"}}
    if horizontal:
        tr.update({"y": [str(l) for l in labels], "x": list(values), "orientation": "h"})
    else:
        tr.update({"x": [str(l) for l in labels], "y": list(values)})
    return {"data": [tr], "layout": _layout(title, "" if horizontal else "", ylabel, showlegend=False)}


def line(x, ys: dict, title: str, xt: str, yt: str, hlines=None) -> dict:
    data = []
    for i, (name, y) in enumerate(ys.items()):
        data.append({"type": "scatter", "mode": "lines", "x": list(x), "y": list(y), "name": name,
                     "line": {"color": PALETTE[i % len(PALETTE)]}})
    shapes = []
    for h in hlines or []:
        shapes.append({"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": h, "y1": h,
                       "line": {"dash": "dot", "color": "#e0532c"}})
    return {"data": data, "layout": _layout(title, xt, yt, shapes=shapes)}
