#!/usr/bin/env python3
"""Download the source document of every catalog entry into _raw/lu/cache/ (resumable).

Preferred manifestation: Akoma Ntoso XML ("xml" / "xml-akomantoso"); the PDF is used only for the
codes that Legilux publishes as PDF compilations. Acts only available as scanned Mémorial PDFs
(whole issues, 19th century) are skipped.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import CATALOG, cached_file


def source(e: dict) -> tuple[str, str] | None:
    files = e.get("cons_files") or e["files"]
    for fmt in ("xml-akomantoso", "xml"):
        if fmt in files:
            return "xml", files[fmt]
    if e["kind"] == "code" and "pdf" in files:
        return "pdf", files["pdf"]
    return None


def main():
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    jobs = [s[1] for e in cat if (s := source(e))]
    jobs = list(dict.fromkeys(jobs))
    print(f"{len(jobs)} files", file=sys.stderr)
    errors = 0
    with ThreadPoolExecutor(4) as ex:
        futs = {ex.submit(cached_file, u): u for u in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                f.result()
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"ERROR {futs[f]}: {exc}", file=sys.stderr, flush=True)
            if i % 500 == 0:
                print(f"{i}/{len(jobs)}", file=sys.stderr, flush=True)
    print(f"done, {errors} errors", file=sys.stderr)


if __name__ == "__main__":
    main()
