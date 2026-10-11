#!/usr/bin/env python3
"""Regenerate README.md counts from the files present in the repository."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from common import CATALOG, REPO
from fetch import source

TEMPLATE = Path(__file__).with_name("README.template.md")


def count(d: str) -> tuple[int, int, str]:
    files = list((REPO / d).rglob("*.md"))
    cons = 0
    years = set()
    for f in files:
        head = f.read_text(encoding="utf-8")[:1500]
        if "\nconsolidated: true" in head:
            cons += 1
        m = re.search(r"\ndate: (\d{4})", head)
        if m:
            years.add(int(m.group(1)))
    span = f"{min(years)}–{max(years)}" if years else ""
    return len(files), cons, span


def main():
    cat = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    pdf_only = {"loi": 0, "rgd": 0}
    for e in cat:
        if e["kind"] in pdf_only and not source(e):
            pdf_only[e["kind"]] += 1
    vals = {}
    total = 0
    for key, d in (("const", "constitution"), ("codes", "codes"), ("lois", "lois"),
                   ("rgd", "reglements-grand-ducaux")):
        n, c, span = count(d)
        vals[f"{key}_n"] = n
        vals[f"{key}_cons"] = c
        vals[f"{key}_span"] = span
        total += n
    vals["total"] = total
    vals["pdf_only_loi"] = pdf_only["loi"]
    vals["pdf_only_rgd"] = pdf_only["rgd"]
    vals["images"] = sum(1 for _ in (REPO / "images").rglob("*") if _.is_file()) if (REPO / "images").exists() else 0
    vals["date"] = dt.date.today().isoformat()
    text = TEMPLATE.read_text(encoding="utf-8")
    for k, v in vals.items():
        text = text.replace("{{" + k + "}}", f"{v:,}" if isinstance(v, int) else str(v))
    (REPO / "README.md").write_text(text, encoding="utf-8")
    print(vals)


if __name__ == "__main__":
    main()
