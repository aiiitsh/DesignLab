"""Extract the data set (and stored results, if any) from a .jasp file.

A .jasp file is a zip archive. The data live in internal.sqlite (table
DataSet_1, columns Column_<id>_DBL / Column_<id>_INT; nominal columns store an
integer key that maps to a label in the Labels table). Stored analysis output
(if present) is in resources/<n>/jaspResults.json.

Usage:  python tests/tools/jasp_extract.py file.jasp [out_dir]
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import zipfile

import pandas as pd


def read_jasp(path: str) -> tuple[pd.DataFrame, list[dict]]:
    with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as tmp:
        z.extract("internal.sqlite", tmp)
        results = []
        for name in z.namelist():
            if name.endswith("jaspResults.json"):
                try:
                    results.append(json.loads(z.read(name)))
                except Exception:
                    pass
        con = sqlite3.connect(os.path.join(tmp, "internal.sqlite"))
        cols = con.execute(
            "select id, name, columnType from Columns order by colIdx"
        ).fetchall()
        labels: dict[int, dict] = {}
        for cid, value, label in con.execute("select columnId, value, label from Labels"):
            labels.setdefault(cid, {})[value] = label
        raw = pd.read_sql("select * from DataSet_1 order by rowNumber", con)
        con.close()
    out = {}
    for cid, name, ctype in cols:
        dbl, inti = f"Column_{cid}_DBL", f"Column_{cid}_INT"
        if ctype == "scale" or cid not in labels:
            s = raw[dbl] if dbl in raw else raw[inti]
            out[name] = pd.to_numeric(s, errors="coerce")
        else:
            lab = labels[cid]
            s = raw[inti].map(lambda v: lab.get(v, v) if pd.notna(v) else None)
            num = pd.to_numeric(s, errors="coerce")
            out[name] = num if num.notna().all() else s
    df = pd.DataFrame(out)
    scale_cols = [name for _, name, t in cols if t == "scale"]
    if scale_cols:  # JASP pads the sheet with empty rows (nominal = -1)
        df = df[df[scale_cols].notna().any(axis=1)]
    df = df.dropna(how="all").reset_index(drop=True)
    for c in df.columns:  # 160.0 -> 160 when a column holds whole numbers only
        if df[c].dtype.kind == "f" and df[c].notna().all() and (df[c] % 1 == 0).all():
            df[c] = df[c].astype(int)
    return df, results


def main() -> None:
    path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    df, results = read_jasp(path)
    base = os.path.splitext(os.path.basename(path))[0]
    df.to_csv(os.path.join(out_dir, base + ".csv"), index=False)
    if results:
        with open(os.path.join(out_dir, base + ".results.json"), "w") as f:
            json.dump(results, f)
    print(df.head(), "\n", len(df), "rows;", len(results), "stored result sets")


if __name__ == "__main__":
    main()
