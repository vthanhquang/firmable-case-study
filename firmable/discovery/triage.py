"""Part 1: build a catalogue pool from CKAN and rank it with transparent, deterministic features.

Why no model here: 1,000 catalogue records x a model call is spend with no validation story,
while metadata keywords + resource formats are cheap, reproducible and explainable. The model
budget is better spent in Part 2 where it does work rules cannot.
"""
from __future__ import annotations

import csv
import json
import math
import re

from ..paths import OUT_DISCOVERY
from ..sources.fetch import ckan

PORTAL = "https://data.gov.au/data"
QUERIES = ["business", "company", "register", "licence", "licensed", "permit", "contract", "tender",
           "supplier", "ABN", "charity", "employer", "approved provider", "accredited", "grant recipients",
           "procurement"]
ROWS = 100

MACHINE_FORMATS = {"CSV", "XLSX", "XLS", "JSON", "XML", "ZIP", "TSV", "TXT", "API", "GEOJSON"}

# (feature name, weight, regex, which text it looks at)
FEATURES = [
    ("identifier_terms", 3, r"\babns?\b|australian business number|\bacns?\b|australian company number", "all"),
    ("entity_name_terms", 2, r"business names?|trading names?|legal names?|company names?|entity names?|registered names?", "all"),
    ("entity_title", 3, r"\b(licensees?|licence holders?|license holders?|suppliers?|contractors?|businesses|compan(y|ies)|"
                        r"charit(y|ies)|operators?|providers?|employers?|traders?|retailers?|dealers?|builders?|venues?|"
                        r"establishments?|organisations?|organizations?|vendors?|manufacturers?|agents?|brokers?)\b", "title"),
    ("register_title", 2, r"\b(register|registry|directory|listing|list of|licences?|licenses?|permits?|approvals?)\b", "title"),
    ("contract_terms", 2, r"\b(contracts? awarded|tenders?|procurement|purchase orders?|grants? (recipients?|awarded|funding))\b", "all"),
    ("aggregate_terms", -3, r"\b(statistics|statistical|survey|census|summary|aggregated?|indicators?|index|time series|"
                            r"rainfall|population|forecast|estimates?|counts? of|number of|by (lga|region|state|industry|month|year))\b", "all"),
    ("spatial_terms", -2, r"\b(boundar(y|ies)|shapefile|polygons?|spatial|wms|wfs|imagery|elevation)\b", "title"),
    ("officials_terms", -2, r"gifts? and benefits|declarations? of interest|pecuniary interests?|travel expenses|hospitality", "all"),
    ("publisher_regulator", 1, r"securities|charities|taxation|fair trading|consumer|liquor|gaming|regulat|commission|authority|"
                               r"building|workcover|safework|procurement|treasury", "org"),
]


def discover(min_pool: int = 200) -> list[dict]:
    pool = {}
    for q in QUERIES:
        res = ckan(PORTAL, "package_search", q=q, rows=ROWS, start=0)
        for p in res["result"]["results"]:
            if p["id"] not in pool:
                pool[p["id"]] = {"query": q, "retrieved_at": res["retrieved_at"], "package": p}
    if len(pool) < min_pool:
        raise RuntimeError(f"pool too small: {len(pool)} < {min_pool}")
    return list(pool.values())


def _text(p: dict) -> dict:
    res_text = " ".join(f"{r.get('name') or ''} {r.get('description') or ''}" for r in p.get("resources", []))
    tags = " ".join(t.get("name", "") for t in p.get("tags", []))
    org = (p.get("organization") or {}).get("title") or ""
    title = p.get("title") or ""
    return {"title": title.lower(), "org": org.lower(),
            "all": f"{title} {p.get('notes') or ''} {tags} {res_text}".lower()}


def score_package(p: dict) -> tuple[float, list[str]]:
    t = _text(p)
    score, reasons = 0.0, []
    for name, w, rx, field in FEATURES:
        if re.search(rx, t[field]):
            score += w
            reasons.append(f"{name}({w:+d})")
    fmts = {(r.get("format") or "").upper().strip() for r in p.get("resources", [])}
    if fmts & MACHINE_FORMATS:
        score += 2
        reasons.append("machine_readable(+2)")
    elif fmts:
        score -= 3
        reasons.append("documents_only(-3)")
    return score, reasons


def confidence(score: float) -> float:
    """Monotone squash of the heuristic score into [0,1]. A ranking aid, NOT a calibrated probability."""
    return round(1 / (1 + math.exp(-(score - 4) / 2)), 3)


def rank(pool: list[dict], top: int = 50, per_org_cap: int = 4) -> list[dict]:
    scored = []
    for item in pool:
        p = item["package"]
        s, reasons = score_package(p)
        scored.append((s, p["id"], p, reasons))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out, per_org = [], {}
    for s, pid, p, reasons in scored:
        org = (p.get("organization") or {}).get("title") or "unknown"
        if per_org.get(org, 0) >= per_org_cap:  # keep the shortlist from being one publisher's catalogue
            continue
        per_org[org] = per_org.get(org, 0) + 1
        fmts = sorted({(r.get("format") or "?").upper() for r in p.get("resources", [])})
        out.append({
            "rank": len(out) + 1, "dataset_id": pid, "name": p.get("name"), "title": p.get("title"),
            "publishing_organisation": org, "resource_formats": "|".join(fmts),
            "licence": p.get("license_id") or "unknown", "score": s, "confidence": confidence(s),
            "reason": "; ".join(reasons), "url": f"https://data.gov.au/data/dataset/{p.get('name')}",
        })
        if len(out) >= top:
            break
    return out


def run(min_pool: int = 200, top: int = 50) -> dict:
    OUT_DISCOVERY.mkdir(parents=True, exist_ok=True)
    pool = discover(min_pool)
    with open(OUT_DISCOVERY / "catalogue_pool.jsonl", "w", encoding="utf-8") as fh:
        for item in pool:
            p = item["package"]
            fh.write(json.dumps({
                "dataset_id": p["id"], "name": p.get("name"), "title": p.get("title"),
                "organisation": (p.get("organization") or {}).get("title"), "licence": p.get("license_id"),
                "query": item["query"], "retrieved_at": item["retrieved_at"],
                "metadata_modified": p.get("metadata_modified"),
                "resources": [{"id": r.get("id"), "name": r.get("name"), "format": r.get("format"),
                               "url": r.get("url"), "last_modified": r.get("last_modified"),
                               "size": r.get("size")} for r in p.get("resources", [])],
            }) + "\n")
    short = rank(pool, top)
    with open(OUT_DISCOVERY / "shortlist_50.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(short[0].keys()))
        w.writeheader()
        w.writerows(short)
    with open(OUT_DISCOVERY / "shortlist_50.jsonl", "w", encoding="utf-8") as fh:
        for row in short:
            fh.write(json.dumps(row) + "\n")
    return {"pool": len(pool), "shortlist": len(short)}
