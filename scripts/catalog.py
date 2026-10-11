#!/usr/bin/env python3
"""Build the list of texts to convert from the Legilux SPARQL endpoint.

Writes _raw/lu/catalog.json: a list of entries
  {kind, eli, member, date, title, status, consolidated, cons_eli, cons_date, files{fmt: url}}

Selection:
- Constitution: the applicable consolidated version.
- Codes: for every code (resource-type CODE or CODE_RECUEIL), the latest consolidated version
  whose applicability date is <= today.
- Lois and règlements grand-ducaux whose jolux:inForceStatus is "in-force": the currently
  applicable consolidated version when Legilux has one, else the original text as published
  in the Journal officiel (Mémorial).
"""
from __future__ import annotations

import datetime as dt
import json
import sys

from common import CATALOG, J, RAW, RT, ST, UF, sparql

PFX = f"PREFIX j: <{J}>\n"
TODAY = dt.date.today().isoformat()


def files_of(concat: str) -> dict:
    out = {}
    for item in filter(None, (concat or "").split(" ")):
        fmt, _, url = item.partition("|")
        fmt = fmt.replace(UF, "")
        out.setdefault(fmt, url)
    return out


def acts(rtype: str, year: int | None = None) -> list[dict]:
    yf = f"FILTER(YEAR(?d) = {year})" if year else ""
    q = PFX + f"""
SELECT ?s ?d ?m ?t ?pd ?ef (GROUP_CONCAT(DISTINCT CONCAT(STR(?f), "|", STR(?x)); separator=" ") AS ?files)
WHERE {{
  ?s a j:Act ; j:typeDocument <{RT}{rtype}> ;
     j:inForceStatus <{ST}in-force> ; j:dateDocument ?d .
  {yf}
  OPTIONAL {{ ?s j:isMemberOf ?m }}
  OPTIONAL {{ ?s j:publicationDate ?pd }}
  OPTIONAL {{ ?s j:dateEntryInForce ?ef }}
  OPTIONAL {{ ?s j:isRealizedBy ?e . ?e j:language <http://publications.europa.eu/resource/authority/language/FRA> .
             OPTIONAL {{ ?e j:title ?t }}
             OPTIONAL {{ ?e j:isEmbodiedBy ?mf . ?mf j:userFormat ?f ; j:isExemplifiedBy ?x }} }}
}} GROUP BY ?s ?d ?m ?t ?pd ?ef"""
    return sparql(q)


def consolidations(rtypes: list[str]) -> list[dict]:
    vals = " ".join(f"<{RT}{t}>" for t in rtypes)
    q = PFX + f"""
SELECT ?s ?td ?m ?da ?st ?t ?pd (GROUP_CONCAT(DISTINCT CONCAT(STR(?f), "|", STR(?x)); separator=" ") AS ?files)
WHERE {{
  VALUES ?td {{ {vals} }}
  ?s a j:Consolidation ; j:typeDocument ?td ; j:isMemberOf ?m ; j:dateApplicability ?da .
  OPTIONAL {{ ?s j:inForceStatus ?st }}
  OPTIONAL {{ ?s j:publicationDate ?pd }}
  OPTIONAL {{ ?s j:isRealizedBy ?e .
             OPTIONAL {{ ?e j:title ?t }}
             OPTIONAL {{ ?e j:isEmbodiedBy ?mf . ?mf j:userFormat ?f ; j:isExemplifiedBy ?x }} }}
}} GROUP BY ?s ?td ?m ?da ?st ?t ?pd"""
    return sparql(q)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    out = []

    # --- consolidations -------------------------------------------------------------------
    cons = consolidations(["LOI", "RGD", "Constitution", "CODE", "CODE_RECUEIL"])
    print(f"{len(cons)} consolidations", file=sys.stderr)
    best: dict[tuple, dict] = {}
    for c in cons:
        td = c["td"].replace(RT, "")
        st = (c.get("st") or "").replace(ST, "")
        if c["da"] > TODAY:
            continue
        if td in ("LOI", "RGD", "Constitution") and st != "applicable":
            continue
        key = (td if td.startswith("CODE") else "act", c["m"] if not td.startswith("CODE") else c["s"].rsplit("/", 1)[0])
        prev = best.get(key)
        if prev is None or c["da"] > prev["da"] or (c["da"] == prev["da"] and c["s"] > prev["s"]):
            best[key] = c
    cons_by_member = {k[1]: v for k, v in best.items() if k[0] == "act"}
    # one code per complex work (e.g. the Code d'instruction criminelle was renamed Code de
    # procédure pénale: keep only the latest)
    by_member: dict[str, tuple] = {}
    for k, c in best.items():
        if k[0].startswith("CODE"):
            o = by_member.get(c["m"])
            if o is None or c["da"] > best[o]["da"]:
                by_member[c["m"]] = k
    for k in [k for k in best if k[0].startswith("CODE") and by_member[best[k]["m"]] != k]:
        del best[k]
    code_members = set()
    for (kind, key), c in sorted(best.items()):
        if not kind.startswith("CODE"):
            continue
        if key.endswith("/cooperation_judiciaire"):
            continue  # 2017 brochure of links to EU judicial-cooperation portals, not legislation
        code_members.add(c["m"])
        out.append({
            "kind": "code", "subtype": kind, "eli": key, "member": c["m"], "date": None,
            "title": c.get("t") or "", "status": "in_force", "consolidated": True,
            "cons_eli": c["s"], "cons_date": c["da"], "pubdate": c.get("pd"),
            "files": files_of(c.get("files")),
        })

    # --- constitution -----------------------------------------------------------------------
    for a in acts("Constitution"):
        c = cons_by_member.get(a.get("m"))
        out.append(entry("constitution", a, c))

    # --- lois / RGD, per year to keep responses small ------------------------------------------
    for rtype, kind in (("LOI", "loi"), ("RGD", "rgd")):
        first = 1795
        for year in range(first, dt.date.today().year + 1):
            rows = acts(rtype, year)
            n = 0
            for a in rows:
                if "/eli/etat/adm/" in a["s"]:
                    continue  # Mémorial B (administrative notices) mis-typed as LOI/RGD
                if a.get("m") in code_members:
                    continue  # the text is published as a code under codes/
                out.append(entry(kind, a, cons_by_member.get(a.get("m"))))
                n += 1
            if rows:
                print(f"{rtype} {year}: {n}", file=sys.stderr, flush=True)

    seen, uniq = set(), []
    for e in out:
        if e["eli"] not in seen:
            seen.add(e["eli"])
            uniq.append(e)
    out = uniq
    CATALOG.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    from collections import Counter
    print(Counter((e["kind"], e["consolidated"]) for e in out), file=sys.stderr)


def entry(kind: str, a: dict, c: dict | None) -> dict:
    e = {
        "kind": kind, "eli": a["s"], "member": a.get("m"), "date": a["d"],
        "title": a.get("t") or "", "status": "in_force", "pubdate": a.get("pd"),
        "entry_into_force": a.get("ef"), "consolidated": bool(c),
        "files": files_of(a.get("files")),
    }
    if c:
        e["cons_eli"] = c["s"]
        e["cons_date"] = c["da"]
        e["cons_files"] = files_of(c.get("files"))
    return e


if __name__ == "__main__":
    main()
