"""Part 1, stage 2 (experiment): re-rank the top candidates using their actual COLUMN NAMES.

Stage 1 (triage.py) only sees catalogue metadata, and the hand-check showed its typical false positive:
a title says "permit"/"licence" but the table holds aggregates or prices. Stage 2 stays deterministic and
cheap: for the top N stage-1 candidates it reads the column header (CKAN DataStore field list when the
resource is in the DataStore, else the first bytes of a CSV) and scores whether the table has columns
that NAME a business. v1 remains the official shortlist (the six Part-2 sources were chosen from it);
v2 is measured on a fresh, independently seeded audit sample.
"""
from __future__ import annotations

import csv
import io
import json
import re

import httpx

from ..paths import HTTP_CACHE, OUT_DISCOVERY
from .triage import PORTAL, confidence, discover, score_package

TOP_N = 150
ID_COLS = re.compile(r"\b(?:abn|acn|nzbn|business number|company number)\b")
ID_QUALIFIERS = re.compile(r"\b(?:status|date|type|flag|required|valid|validation)\b")
ENTITY_ROLE = re.compile(r"\b(?:business|company|legal|trading|entity|organi[sz]ation|supplier|vendor|contractor|"
                         r"provider|employer|operator|licensee|licen[cs]e holder|charity|tenderer|firm|non individual)\b")
NON_ENTITY = re.compile(r"\b(?:business unit|contact person|(?:first|given|last|family) name)\b")
AGG_COLS = re.compile(r"\b(?:counts?|totals?|number of|percent(?:age)?|average|median|rate|sum|value|amount|price)\b")
UA = {"User-Agent": "firmable-case-study/0.1"}


def _datastore_fields(resource_id: str) -> list[str] | None:
    """One attempt, short timeout, cached (including misses): harvested packages often claim a DataStore
    that data.gov.au does not hold, and retrying those is pure waiting."""
    cache = HTTP_CACHE / f"dsfields_{resource_id}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    fields = None
    try:
        r = httpx.get(f"{PORTAL}/api/3/action/datastore_search", params={"resource_id": resource_id, "limit": 0},
                      headers=UA, timeout=10)
        body = r.json() if r.status_code == 200 else {}
        if body.get("success"):
            fields = [f["id"] for f in body["result"]["fields"] if f["id"] != "_id"]
    except (httpx.HTTPError, ValueError):
        pass
    HTTP_CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(fields), encoding="utf-8")
    return fields


def _columns(pkg: dict) -> tuple[list[str], str]:
    for r in pkg.get("resources", [])[:3]:
        if r.get("datastore_active"):
            fields = _datastore_fields(r["id"])
            if fields:
                return fields, "datastore"
    tabular = [r for r in pkg.get("resources", []) if (r.get("format") or "").upper() in ("CSV", "TSV")]
    for r in tabular[:2]:  # bounded: some packages list dozens of monthly files
        try:
            with httpx.stream("GET", r["url"], headers=UA, timeout=8, follow_redirects=True) as resp:
                buf = b""
                for ch in resp.iter_bytes():
                    buf += ch
                    if len(buf) > 8000:
                        break
            if resp.status_code == 200 and buf:
                line = buf.decode("utf-8", errors="replace").lstrip("﻿").splitlines()[0]
                delim = "\t" if line.count("\t") > line.count(",") else ","
                return next(csv.reader(io.StringIO(line), delimiter=delim)), "csv_header"
        except Exception:  # blocked/slow hosts are common; the table is simply "unavailable"
            pass
    return [], "unavailable"


def column_score(cols: list[str]) -> tuple[float, list[str]]:
    if not cols:
        return 0.0, ["columns_unavailable(0)"]
    labels = []
    for col in cols:
        words = re.sub(r"([a-z])([A-Z])", r"\1 \2", col)
        labels.append((col, re.sub(r"[^a-z0-9]+", " ", words.lower()).strip()))
    eligible = [(c, label) for c, label in labels if not (AGG_COLS.search(label) or NON_ENTITY.search(label))]
    ids = [c for c, label in eligible if ID_COLS.search(label) and not ID_QUALIFIERS.search(label)]
    names = [c for c, label in eligible if {"name", "names"}.intersection(label.split()) and ENTITY_ROLE.search(label)]
    aggs = [c for c, label in labels if AGG_COLS.search(label)]
    s, why = 0.0, []
    if ids:
        s += 3; why.append(f"identifier_column:{ids[0]}(+3)")
    if names:
        s += 3; why.append(f"business_name_column:{names[0]}(+3)")
    if not ids and not names:
        s -= 3; why.append("no_entity_columns(-3)")
        if len(aggs) >= max(1, len(cols) // 2):
            s -= 1; why.append("mostly_aggregate_columns(-1)")
    return s, why


def run(top: int = 50) -> dict:
    # Same cached package_search responses as stage 1 (full package dicts, incl. datastore flags).
    stage1 = []
    for item in discover():
        pkg = item["package"]
        s, why = score_package(pkg)
        stage1.append((s, pkg["id"], pkg, why))
    stage1.sort(key=lambda x: (-x[0], x[1]))
    rows = []
    for s, pid, pkg, why in stage1[:TOP_N]:
        cols, how = _columns(pkg)
        cs, cwhy = column_score(cols)
        rows.append({"package": pkg, "s1": s, "s2": s + cs, "why": why + cwhy, "columns_from": how,
                     "columns": cols[:40]})
    rows.sort(key=lambda r: (-r["s2"], r["package"]["id"]))
    out, per_org = [], {}
    for r in rows:
        pkg = r["package"]
        org = (pkg.get("organization") or {}).get("title") or "unknown"
        if per_org.get(org, 0) >= 4:
            continue
        per_org[org] = per_org.get(org, 0) + 1
        out.append({"rank": len(out) + 1, "dataset_id": pkg["id"], "title": pkg.get("title"),
                    "publishing_organisation": org,
                    "resource_formats": "|".join(sorted({(x.get("format") or "?").upper() for x in pkg.get("resources", [])})),
                    "licence": pkg.get("license_id") or "unknown", "stage1_score": r["s1"], "score": r["s2"],
                    "confidence": confidence(r["s2"]), "columns_from": r["columns_from"],
                    "reason": "; ".join(r["why"])})
        if len(out) >= top:
            break
    with open(OUT_DISCOVERY / "shortlist_50_v2_columns.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    with open(OUT_DISCOVERY / "shortlist_50_v2_columns.jsonl", "w", encoding="utf-8") as fh:
        for row in out:
            fh.write(json.dumps(row) + "\n")
    v1 = {json.loads(l)["dataset_id"] for l in open(OUT_DISCOVERY / "shortlist_50.jsonl", encoding="utf-8")}
    return {"stage2_candidates": len(rows), "columns_found": sum(r["columns_from"] != "unavailable" for r in rows),
            "shortlist": len(out), "overlap_with_v1": len(v1 & {o["dataset_id"] for o in out})}
