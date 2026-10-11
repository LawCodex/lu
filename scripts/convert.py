#!/usr/bin/env python3
"""Convert the cached Legilux documents listed in catalog.json to Markdown files in the repo.

Usage: convert.py [--kinds code,constitution,loi,rgd] [--years 1800-1900]
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import logging
import os
import re
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from common import CACHE, CATALOG, RAW, REPO
from fetch import source

TODAY = dt.date.today().isoformat()
DIRS = {"constitution": "constitution", "code": "codes", "loi": "lois", "rgd": "reglements-grand-ducaux"}
TYPES = {"constitution": "constitution", "code": "code", "loi": "act", "rgd": "regulation"}
MONTHS = "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre"


def slugify(s: str, maxlen: int = 80) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s


def eli_path(eli: str) -> str:
    return eli.split("/eli/", 1)[1]


def public_url(eli: str) -> str:
    return "https://legilux.public.lu/eli/" + eli_path(eli)


def short_subject(title: str) -> str:
    t = re.sub(r"\s+", " ", title).strip()
    t = re.sub(r"^Version consolidée applicable au [0-9/]+ ?: ?", "", t)
    # drop "Loi (modifiée) du 16 décembre 2010" / "Règlement grand-ducal du 1er mars 2004"
    t = re.sub(r"^(Loi|Règlement grand-ducal|Reglement grand-ducal|Règlement grand ducal|Constitution)"
               r"( modifiée| modifié)? (du |des )?(\d{1,2}(er)? (" + MONTHS + r") \d{4}[, ]*(et )?)+",
               "", t, flags=re.I)
    return t.strip(" ,.-")


def target(e: dict) -> Path:
    kind = e["kind"]
    if kind == "constitution":
        return REPO / "constitution" / "constitution.md"
    if kind == "code":
        return REPO / "codes" / (slugify(e["title"]) + ".md")
    p = eli_path(e["eli"]).split("/")  # etat/leg/loi/2010/12/16/n1/jo
    y, m, d, n = p[3], p[4], p[5], p[6]
    base = f"{y}-{m}-{d}-{n}"
    subj = slugify(short_subject(e["title"]), 70)
    name = f"{base}-{subj}" if subj else base
    return REPO / DIRS[kind] / y / (name + ".md")


def yq(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def front_matter(e: dict, extra: dict) -> str:
    title = re.sub(r"\s+", " ", e["title"]).strip()
    title = re.sub(r"^Version consolidée applicable au [0-9/]+ ?: ?", "", title)
    eli = e["eli"] if e["kind"] != "code" else e["eli"]
    ident = eli.replace("http://data.legilux.public.lu/", "http://data.legilux.public.lu/") \
        .removesuffix("/jo")
    date = e.get("date")
    if e["kind"] == "constitution":
        date = "1868-10-17"
    lines = ["---", f"title: {yq(title)}", f"identifier: {yq(ident)}",
             f"type: {TYPES[e['kind']]}", "jurisdiction: lu", "language: fr"]
    if date:
        lines.append(f"date: {date}")
    if e.get("consolidated"):
        lines.append(f"last_amended: {e['cons_date']}")
        lines.append("consolidated: true")
    else:
        lines.append("consolidated: false")
    if e.get("pubdate") and e["kind"] != "code":
        lines.append(f"publication_date: {e['pubdate']}")
    if e.get("entry_into_force"):
        lines.append(f"entry_into_force: {e['entry_into_force']}")
    lines.append("status: in_force")
    src = public_url(e["cons_eli"]) if e.get("consolidated") else public_url(e["eli"])
    lines.append(f"source: {yq(src)}")
    for k, v in extra.items():
        lines.append(f"{k}: {yq(v)}")
    lines.append(f"retrieved: {TODAY}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def tidy(md: str) -> str:
    md = re.sub(r"(\]\([^)\s]+\)) ([.,])", r"\1\2", md)
    md = re.sub(r"\( \[", "([", md)
    md = re.sub(r"(\]\([^)\s]+\)) \)", r"\1)", md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    return md


def pdf_pages(data: bytes) -> list[str]:
    """Text of each page: poppler's pdftotext when available (much better spacing), else pypdf."""
    import shutil
    import subprocess
    import tempfile
    if shutil.which("pdftotext"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", dir=RAW) as f:
            f.write(data)
            f.flush()
            out = subprocess.run(["pdftotext", "-enc", "UTF-8", f.name, "-"], capture_output=True,
                                 check=True).stdout.decode("utf-8", "replace")
        return out.split("\f")
    import pypdf
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    pages = []
    for pg in pypdf.PdfReader(io.BytesIO(data)).pages:
        try:
            pages.append(pg.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")
    return pages


NEWPARA = re.compile(r"^(Art\.|Article|Chapitre|CHAPITRE|Titre|TITRE|Livre|LIVRE|Section|SECTION|Partie|PARTIE)\b")


def pdf_to_md(data: bytes) -> str:
    from collections import Counter
    from akn2md import esc_start
    pages = pdf_pages(data)
    # running headers / footers: short lines repeated on many pages
    freq = Counter()
    for p in pages:
        for l in {l.strip() for l in p.splitlines() if l.strip()}:
            freq[l] += 1
    limit = max(5, len(pages) // 10)
    rep = {l for l, n in freq.items() if n >= limit and len(l) < 80}
    paras, cur = [], []
    for p in pages:
        for raw in p.splitlines() + [""]:
            l = raw.strip()
            if l in rep or re.fullmatch(r"\d{1,4}", l or "x"):
                continue
            if not l:
                if cur:
                    paras.append(cur)
                    cur = []
                continue
            if NEWPARA.match(l) and cur:
                paras.append(cur)
                cur = []
            cur.append(esc_start(l))
    if cur:
        paras.append(cur)
    out = []
    for para in paras:
        if para == ["\\-"] or para == ["-"]:
            continue
        out.append("\n".join(para))
    return "\n\n".join(out) + "\n"


def convert_one(e: dict) -> tuple[str, str, int, int]:
    """Returns (status, path, md_bytes, n_images)."""
    from akn2md import convert
    src = source(e)
    if not src:
        return ("skip-pdf-only", e["eli"], 0, 0)
    fmt, url = src
    cpath = CACHE / url.split("/filestore/", 1)[-1]
    if not cpath.exists():
        return ("missing", e["eli"], 0, 0)
    out = target(e)
    data = cpath.read_bytes()
    extra = {}
    nimg = 0
    if fmt == "pdf":
        body = pdf_to_md(data)
        extra["source_format"] = "pdf (text extracted with pdftotext)"
    else:
        rel = os.path.relpath(REPO / "images", out.parent) + "/"
        body, images, _ = convert(data, image_prefix=rel)
        for name, blob in images:
            ip = REPO / "images" / name[:2] / name
            if not ip.exists():
                ip.parent.mkdir(parents=True, exist_ok=True)
                ip.write_bytes(blob)
            nimg += 1
    title = re.sub(r"\s+", " ", e["title"]).strip()
    title = re.sub(r"^Version consolidée applicable au [0-9/]+ ?: ?", "", title)
    md = front_matter(e, extra) + f"# {title}\n\n" + tidy(body)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8", newline="\n")
    return ("ok", str(out.relative_to(REPO)), len(md.encode()), nimg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kinds", default="constitution,code,loi,rgd")
    ap.add_argument("--years", default="")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    kinds = a.kinds.split(",")
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    sel = [e for e in cat if e["kind"] in kinds]
    if a.years:
        y0, _, y1 = a.years.partition("-")
        y1 = y1 or y0
        sel = [e for e in sel if e.get("date") and y0 <= e["date"][:4] <= y1]
    # detect filename collisions
    seen = {}
    for e in sel:
        t = target(e)
        if t in seen:
            print(f"COLLISION {t} {e['eli']} {seen[t]}", file=sys.stderr)
        seen[t] = e["eli"]
    stats = {}
    with ProcessPoolExecutor(a.jobs) as ex:
        for st, path, size, nimg in ex.map(convert_one, sel, chunksize=8):
            stats[st] = stats.get(st, 0) + 1
            if st != "ok":
                print(st, path, file=sys.stderr)
            elif size > 45_000_000:
                print(f"TOO BIG {path} {size}", file=sys.stderr)
    print(stats, file=sys.stderr)
    (RAW / "convert-stats.json").write_text(json.dumps(stats))


if __name__ == "__main__":
    main()
