"""Shared helpers: number formatting (APA rules), result containers, data cleaning."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

ALPHA = 0.05


# ---------------------------------------------------------------- formatting
def _isnum(x: Any) -> bool:
    try:
        return x is not None and not (isinstance(x, float) and math.isnan(x)) and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def fmt_p(p: float, digits: int = 3) -> str:
    """APA p: exact to 3 decimals, '< .001' below that, never '.000', no leading zero."""
    if not _isnum(p):
        return "–"
    if p < 0.001:
        return "< .001"
    s = f"{p:.{digits}f}"
    if s.startswith("1."):
        return "1.000"
    return s.lstrip("0") if s.startswith("0") else s


def p_eq(p: float) -> str:
    """'p = .029' or 'p < .001' (italics added by the renderer through *p*)."""
    s = fmt_p(p)
    return f"*p* {s}" if s.startswith("<") else f"*p* = {s}"


def fmt_num(x: float, digits: int = 3) -> str:
    if not _isnum(x):
        return "–"
    s = f"{x:.{digits}f}"
    if s.startswith("-") and float(s) == 0:
        s = s[1:]
    return s.replace("-", "−")


def fmt_unit(x: float, digits: int = 3) -> str:
    """Values that cannot exceed 1 in magnitude (p, eta², R², r): drop the leading zero."""
    s = fmt_num(x, digits)
    if s.startswith("0."):
        return s[1:]
    if s.startswith("−0."):
        return "−" + s[2:]
    return s


def fmt_df(df: float) -> str:
    if not _isnum(df):
        return "–"
    if abs(df - round(df)) < 1e-9:
        return str(int(round(df)))
    return f"{df:.3f}"


def clean(x: Any) -> Any:
    """Make numpy/pandas values JSON-safe (NaN/inf -> None)."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return clean(x.tolist())
    if isinstance(x, pd.DataFrame):
        return clean(x.to_dict(orient="records"))
    if isinstance(x, pd.Series):
        return clean(x.tolist())
    if x is pd.NA or x is pd.NaT:
        return None
    return x


# ---------------------------------------------------------------- bands
def band_d(d: float) -> str:
    a = abs(d)
    return "negligible" if a < 0.2 else "small" if a < 0.5 else "medium" if a < 0.8 else "large"


def band_eta(e: float) -> str:  # Cohen: .01 / .06 / .14
    return "negligible" if e < 0.01 else "small" if e < 0.06 else "medium" if e < 0.14 else "large"


def band_f2(f2: float) -> str:
    return "negligible" if f2 < 0.02 else "small" if f2 < 0.15 else "medium" if f2 < 0.35 else "large"


def band_r(r: float) -> str:
    a = abs(r)
    return "negligible" if a < 0.1 else "small" if a < 0.3 else "medium" if a < 0.5 else "large"


def band_w(w: float) -> str:
    a = abs(w)
    return "negligible" if a < 0.1 else "small" if a < 0.3 else "medium" if a < 0.5 else "large"


# ---------------------------------------------------------------- result container
@dataclass
class Result:
    analysis_id: str
    title: str
    tables: list = field(default_factory=list)
    plots: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    effect_sizes: list = field(default_factory=list)
    followups: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    apa: str = ""
    interpretation: str = ""
    python_code: str = ""
    extra: dict = field(default_factory=dict)

    def table(self, title: str, columns: list[str], rows: list[list], footnotes: list[str] | None = None,
              section: str = "main") -> dict:
        t = {"title": title, "columns": columns, "rows": rows, "footnotes": footnotes or [], "section": section}
        self.tables.append(t)
        return t

    def check(self, name: str, test: str, statistic: float | None, p: float | None, ok: bool,
              detail: str = "", df: Any = None) -> None:
        self.checks.append({
            "name": name, "test": test, "statistic": statistic, "df": df, "p": p, "p_fmt": fmt_p(p) if p is not None else "",
            "ok": bool(ok), "verdict": "OK" if ok else "Violated", "detail": detail,
        })

    def decide(self, text: str, switched: bool = False, rule: str = "", key: str = "") -> None:
        self.decisions.append({"text": text, "switched": switched, "rule": rule, "key": key})

    def effect(self, name: str, value: float, band: str = "", ci: tuple | None = None, note: str = "") -> None:
        self.effect_sizes.append({"name": name, "value": value, "value_fmt": fmt_num(value), "band": band,
                                  "ci": list(ci) if ci else None, "note": note})

    def to_dict(self) -> dict:
        return clean(self.__dict__)


# ---------------------------------------------------------------- data helpers
def to_frame(data: Any) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    df = pd.DataFrame(data)
    for c in df.columns:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            conv = pd.to_numeric(df[c].replace("", np.nan), errors="coerce")
            nonblank = df[c].replace("", np.nan).notna()
            if nonblank.sum() > 0 and conv[nonblank].notna().all():
                df[c] = conv
    return df


def normalize_labels(s: pd.Series) -> pd.Series:
    """Strip whitespace and merge case variants ('yes'/'Yes ') into the most common spelling."""
    if not (s.dtype == object or pd.api.types.is_string_dtype(s)):
        return s
    st = s.map(lambda v: v.strip() if isinstance(v, str) else v)
    canon = {}
    for key, grp in st.dropna().groupby(st.dropna().map(lambda v: str(v).lower())):
        canon[key] = grp.value_counts().index[0]
    return st.map(lambda v: canon.get(v.lower(), v) if isinstance(v, str) else v)


def level_order(s: pd.Series) -> list:
    vals = [v for v in pd.unique(s.dropna())]
    try:
        return sorted(vals)
    except TypeError:
        return vals


def describe(x: pd.Series | np.ndarray) -> dict:
    from scipy import stats

    x = pd.Series(x).dropna().astype(float)
    n = len(x)
    m = x.mean() if n else np.nan
    sd = x.std(ddof=1) if n > 1 else np.nan
    se = sd / math.sqrt(n) if n > 1 else np.nan
    tcrit = stats.t.ppf(0.975, n - 1) if n > 1 else np.nan
    q1, q3 = (x.quantile(0.25), x.quantile(0.75)) if n else (np.nan, np.nan)
    return {"N": n, "Mean": m, "SD": sd, "SE": se, "Median": x.median() if n else np.nan,
            "Min": x.min() if n else np.nan, "Max": x.max() if n else np.nan,
            "Q1": q1, "Q3": q3, "IQR": q3 - q1,
            "CI low": m - tcrit * se if n > 1 else np.nan, "CI high": m + tcrit * se if n > 1 else np.nan}


def familywise(m: int, alpha: float = ALPHA) -> float:
    return 1 - (1 - alpha) ** m
