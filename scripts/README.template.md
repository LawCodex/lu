# Luxembourg — LawCodex

Luxembourg legislation **in force**, as plain Markdown: the Constitution, the codes, and every
*loi* and *règlement grand-ducal* that the official database **Legilux** (Journal officiel du
Grand-Duché de Luxembourg, Service central de législation) flags as in force — in the current
consolidated version where Legilux publishes one, otherwise as originally published in the
Journal officiel / Mémorial. Language: French (the language of legislation in Luxembourg).

Part of [LawCodex](https://github.com/LawCodex) — the laws of every country as Markdown in git.

Retrieved: {{date}}.

## Contents

| Category | Directory | Files | of which consolidated | Years |
|---|---|---:|---:|---|
| Constitution (consolidated, incl. the 2023 revision) | [`constitution/`](constitution/) | {{const_n}} | {{const_cons}} | |
| Codes (official consolidations) | [`codes/`](codes/) | {{codes_n}} | {{codes_cons}} | |
| Lois (acts of the Chambre des Députés) | [`lois/<year>/`](lois/) | {{lois_n}} | {{lois_cons}} | {{lois_span}} |
| Règlements grand-ducaux | [`reglements-grand-ducaux/<year>/`](reglements-grand-ducaux/) | {{rgd_n}} | {{rgd_cons}} | {{rgd_span}} |
| **Total** | | **{{total}}** | | |

Images embedded in the official XML (formulas, diagrams, signs, forms; {{images}} files) are
extracted to [`images/`](images/) and linked from the texts. Images larger than 500 KB (scanned
maps, cadastral plans, large forms — about 340 images, ~1 GB in total) are not copied; the text
then contains a note *"[image omitted (… MB) — see the official version: <URL>]"*.

### Codes

| Code | File | Source format |
|---|---|---|
| Code civil | [`codes/code-civil.md`](codes/code-civil.md) | XML |
| Code pénal | [`codes/code-penal.md`](codes/code-penal.md) | XML |
| Nouveau Code de procédure civile | [`codes/nouveau-code-de-procedure-civile.md`](codes/nouveau-code-de-procedure-civile.md) | XML |
| Code de procédure pénale (formerly Code d'instruction criminelle) | [`codes/code-de-procedure-penale.md`](codes/code-de-procedure-penale.md) | XML |
| Code de commerce | [`codes/code-de-commerce.md`](codes/code-de-commerce.md) | XML |
| Code du travail | [`codes/code-du-travail.md`](codes/code-du-travail.md) | XML |
| Code de la consommation | [`codes/code-de-la-consommation.md`](codes/code-de-la-consommation.md) | XML |
| Code de la fonction publique (compilation) | [`codes/code-de-la-fonction-publique.md`](codes/code-de-la-fonction-publique.md) | XML |
| Code de la santé (compilation) | [`codes/code-de-la-sante.md`](codes/code-de-la-sante.md) | XML |
| Code de la sécurité sociale (compilation, incl. related laws and regulations) | [`codes/code-de-la-securite-sociale.md`](codes/code-de-la-securite-sociale.md) | PDF → text |
| Code communal (compilation) | [`codes/code-communal.md`](codes/code-communal.md) | PDF → text |
| Code de l'éducation nationale (compilation) | [`codes/code-de-l-education-nationale.md`](codes/code-de-l-education-nationale.md) | PDF → text |
| Code de l'environnement (compilation) and its annexes | [`codes/code-de-l-environnement.md`](codes/code-de-l-environnement.md), [`codes/code-de-l-environnement-annexes.md`](codes/code-de-l-environnement-annexes.md) | PDF → text |
| Code de la route (compilation) | [`codes/code-de-la-route.md`](codes/code-de-la-route.md) | PDF → text |

The "compilation" codes (*codes-recueils*) are official thematic collections of the
consolidated laws and regulations of a field, published by the Service central de législation;
the laws they contain also appear individually under `lois/` and `reglements-grand-ducaux/`.
The laws that *are* a code (e.g. the Code civil, the Code du travail, the Code de la consommation)
appear only under `codes/`. Seven compilations are published by Legilux only as PDF; their text
was extracted with `pdftotext` and is kept as plain paragraphs (no heading structure; occasional
layout artefacts such as split marginal notes).

## Structure

```
constitution/constitution.md
codes/<code>.md
lois/<year>/<yyyy>-<mm>-<dd>-<n>-<subject>.md
reglements-grand-ducaux/<year>/<yyyy>-<mm>-<dd>-<n>-<subject>.md
images/<xx>/<sha1>.<ext>
scripts/
```

`<year>` and the date in the file name are the date of the act (signature/promulgation); `<n>`
is the number Legilux uses in the ELI (`n1`, `n2`… for older acts, `a123` = Journal officiel
Mémorial A issue number for recent ones). File names are derived from the ELI, so they are stable.

Each file has YAML front matter:

```yaml
title: "Loi du 16 décembre 2010 relative à l’aménagement du boulevard Raiffeisen …"
identifier: "http://data.legilux.public.lu/eli/etat/leg/loi/2010/12/16/n1"   # ELI
type: act                    # constitution | code | act (loi) | regulation (règlement grand-ducal)
jurisdiction: lu
language: fr
date: 2010-12-16             # date of the act
last_amended: 2024-01-01     # consolidation (applicability) date, consolidated texts only
consolidated: false          # true = current consolidated version, false = original JO text
publication_date: 2010-12-21
entry_into_force: 2010-12-25
status: in_force
source: "https://legilux.public.lu/eli/etat/leg/loi/2010/12/16/n1/jo"
retrieved: 2026-10-12
```

The hierarchy of each text (livre / titre / chapitre / section …) is mapped to Markdown headings,
articles are the deepest headings (bold labels below `######`). Footnotes of consolidated texts
(the list of amending acts, editorial notes) are rendered as Markdown footnotes. Simple tables
become Markdown tables, tables with merged cells are kept as HTML. Provisions quoted by amending
acts are rendered as block quotes. The preamble (*Nous Henri, Grand-Duc…*), the enacting formula
and the signatures are kept.

## What is not covered

- **Texts that are not flagged as in force** by Legilux (`jolux:inForceStatus` = *no longer in
  force* / *not yet in force*), i.e. repealed or expired laws and regulations.
- **{{pdf_only_loi}} lois and {{pdf_only_rgd}} règlements grand-ducaux** flagged as in force for which
  Legilux has no text manifestation (XML/HTML), only the PDF of the whole Mémorial issue in which
  they were published (scanned images for older issues, often bilingual French/German columns,
  shared by many acts). About 750 of the lois date from 1840–1899 (mostly individual
  naturalisations, budget and local acts); the rest, and the règlements, are scattered over
  1920–2016. They could not be extracted reliably and are skipped.
- **Arrêtés grand-ducaux, arrêtés royaux grand-ducaux (pre-1890), règlements and arrêtés
  ministériels, règlements communaux**, conventions/treaties and other secondary or
  administrative texts (tens of thousands, mostly individual decisions).
- The thematic **recueils** of Legilux other than the codes (e.g. *Marchés publics*,
  *Protection des données*): they only re-publish laws that are already included individually.
- German and Luxembourgish texts (Legilux publishes legislation in French; translations are
  unofficial and rare).

Note that Legilux flags as "in force" many amending acts whose provisions have since been
incorporated in the texts they amend; these are included as published, as the official status says.

## Sources

- Legilux — https://legilux.public.lu (ELI URIs, e.g. `https://legilux.public.lu/eli/etat/leg/code/civil/20251226`).
- Legilux SPARQL endpoint (JOLux ontology) — https://data.legilux.public.lu/sparqlendpoint — used
  to list the texts, their in-force status, their consolidated versions and their manifestations.
- Document files (Akoma Ntoso XML; PDF for some compilations) from
  `https://legilux.public.lu/filestore/eli/…`, the location the Legilux web application itself
  uses (`manifestation_prefix` in `https://legilux.public.lu/api/settings`).
  `data.legilux.public.lu/robots.txt` disallows `/filestore/` and `/eli/` on that host, so the
  files were fetched from `legilux.public.lu`, whose robots.txt allows them (no Crawl-delay is
  set; requests were throttled, ≤ 4 in parallel). Open data: https://data.public.lu (Legilux
  datasets).

## Licence

The texts are official legislation. Legilux manifestations are published under the
**Creative Commons Attribution 4.0** licence (`jolux:license` = `http://creativecommons.org/licenses/by/4.0/`),
"Copyright : Ministère d'État du Grand-Duché de Luxembourg – Service central de législation".
Attribution: *Source: Legilux — Journal officiel du Grand-Duché de Luxembourg, Service central de
législation.* Only the official versions published in the Journal officiel are authentic; the
consolidated texts are produced by the SCL for information, and this Markdown conversion is
unofficial.

## Regenerating

```sh
python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
# poppler's `pdftotext` is used for the PDF-only codes (falls back to pypdf)
cd scripts
python catalog.py      # SPARQL → _raw/lu/catalog.json (texts in force + consolidations)
python fetch.py        # downloads XML/PDF into _raw/lu/cache/ (resumable)
python convert.py      # writes constitution/ codes/ lois/ reglements-grand-ducaux/ images/
python build_readme.py # refreshes the counts in this README
```

Raw downloads go to `../_raw/lu/` (override with `LAWCODEX_RAW`) and are not committed.
