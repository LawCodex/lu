"""Shared helpers for the LawCodex Luxembourg (Legilux) scraper."""
from __future__ import annotations

import csv
import io
import os
import sys
import threading
import time
from pathlib import Path

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
SPARQL = "https://data.legilux.public.lu/sparqlendpoint"
# Manifestation prefix used by the legilux.public.lu web app itself (see /api/settings).
# data.legilux.public.lu/robots.txt disallows /filestore/, legilux.public.lu does not.
FILE_PREFIX = "https://legilux.public.lu"
DATA_PREFIX = "http://data.legilux.public.lu"
REPO = Path(__file__).resolve().parent.parent
RAW = Path(os.environ.get("LAWCODEX_RAW", REPO.parent / "_raw" / "lu"))
CACHE = RAW / "cache"
CATALOG = RAW / "catalog.json"

J = "http://data.legilux.public.lu/resource/ontology/jolux#"
RT = "http://data.legilux.public.lu/resource/authority/resource-type/"
ST = "http://data.legilux.public.lu/resource/authority/application-status/"
UF = "http://data.legilux.public.lu/resource/authority/user-format/"

_local = threading.local()
_lock = threading.Lock()
_last = [0.0]
MIN_INTERVAL = float(os.environ.get("LEGILUX_INTERVAL", "0.25"))


def session() -> requests.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        _local.s = s
    return s


def _throttle():
    with _lock:
        now = time.monotonic()
        wait = _last[0] + MIN_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()


def http_get(url: str, params=None, headers=None, tries: int = 6) -> bytes:
    delay = 5
    err = ""
    for attempt in range(tries):
        _throttle()
        try:
            r = session().get(url, params=params, headers=headers, timeout=300)
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                raise FileNotFoundError(url)
            if r.status_code == 429:
                pause = int(r.headers.get("Retry-After", "30") or 30)
                with _lock:
                    _last[0] = max(_last[0], time.monotonic() + pause)
            err = f"HTTP {r.status_code}"
        except requests.RequestException as e:  # noqa: PERF203
            err = repr(e)
        print(f"retry {attempt + 1}: {url}: {err}", file=sys.stderr, flush=True)
        time.sleep(delay)
        delay = min(delay * 2, 300)
    raise RuntimeError(f"{url}: {err}")


def sparql(query: str) -> list[dict]:
    body = http_get(SPARQL, params={"query": query}, headers={"Accept": "text/csv"})
    return list(csv.DictReader(io.StringIO(body.decode("utf-8"))))


def file_url(data_url: str) -> str:
    """Map a data.legilux filestore URL to the legilux.public.lu one."""
    for p in ("http://data.legilux.public.lu", "https://data.legilux.public.lu"):
        if data_url.startswith(p):
            return FILE_PREFIX + data_url[len(p):]
    return data_url


def cached_file(data_url: str) -> bytes:
    """Fetch a filestore document, caching it under _raw/lu/cache/."""
    path = data_url.split("/filestore/", 1)[-1]
    p = CACHE / path
    if p.exists():
        return p.read_bytes()
    b = http_get(file_url(data_url))
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".part")
    tmp.write_bytes(b)
    tmp.replace(p)
    return b
