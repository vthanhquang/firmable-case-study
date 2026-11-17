"""Choose the six Part-2 sources from the shortlist and snapshot them.

Selection is an engineering decision (the brief says *choose* 6 from your shortlist), made for
diversity of publisher/format/shape AND for expected cross-source overlap, which Parts 3-4 need.
Every choice must come from shortlist_50; the code refuses anything else.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..paths import OUT_DISCOVERY, OUT_SOURCES
from .fetch import download

# (source_id, shortlist dataset title, resource-name substring, format substring, why)
CHOICES = [
    ("asic_companies", "ASIC - Company Dataset", "Company Dataset - Current", "ZIP",
     "National company register (ACN+ABN). Overlap anchor. ZIP containing a tab-delimited file named .csv: a format trap."),
    ("acnc_charities", "ACNC Registered Charities", "ACNC Register of Australian charities", "XLSX",
     "Different regulator; ABN-keyed; spreadsheet; many charities are also ASIC companies."),
    ("ato_tax_transparency", "Corporate Tax Transparency", "2024-25 Report of Entity Tax Information", "XLSX",
     "ATO publication of large entities by ABN; spreadsheet with report-style header rows above the table."),
    ("qbcc_licensees", "QBCC Licensed Contractors Register", "QBCC register", "CSV",
     "State licensing regulator (QLD); licence x class grain (one licensee repeats). The direct CSV is behind a "
     "bot challenge (HTTP 202, empty body), so it is read through the CKAN DataStore JSON API: nested JSON shape."),
    ("vic_liquor", "Victorian liquor licences by location", "August 2026", "XLSX",
     "Licensee + premises address, no ABN: forces name/address resolution and abstention."),
    ("dewr_employment_providers", "Employment Services Provider Locations and Contacts", "", "CSV",
     "Federal department; site-grain records of contracted providers (many are charities/companies)."),
]
# Attempted and rejected at download time (kept for the record, see README):
#   act_contracts  (Contracts Register, ACT)          -> HTTP 403 on every endpoint (WAF), not downloadable.
#   vic_liquor_general (liquor licences by type, CSV) -> HTTP 404.
#   qbcc direct CSV                                    -> HTTP 202 empty body (bot challenge); DataStore API used.
DATASTORE_API = {"qbcc_licensees"}
DATASTORE_LIMIT = 32000
SEVENTH = ("asic_credit_licensees", "ASIC – Credit Licensee Dataset", "Credit Licence Dataset - Current", "TSV",
           "Held back: unseen source for the 'seventh dataset' test.")


def _pool_index() -> dict:
    out = {}
    for line in open(OUT_DISCOVERY / "catalogue_pool.jsonl", encoding="utf-8"):
        r = json.loads(line)
        out[r["dataset_id"]] = r
    return out


def resolve(choice) -> dict:
    sid, title, res_name, fmt, why = choice
    short = [json.loads(l) for l in open(OUT_DISCOVERY / "shortlist_50.jsonl", encoding="utf-8")]
    hit = [s for s in short if s["title"].strip() == title]
    if not hit:
        raise ValueError(f"{title!r} is not in the shortlist - refusing to hand-insert a source")
    s = hit[0]
    pkg = _pool_index()[s["dataset_id"]]
    res = [r for r in pkg["resources"]
           if res_name.lower() in (r.get("name") or "").lower() and fmt.lower() in (r.get("format") or "").lower()]
    if not res:
        raise ValueError(f"no resource {res_name!r}/{fmt} in {title}")
    r = res[-1] if not res_name else res[0]
    url = r["url"]
    if sid in DATASTORE_API:
        url = f"https://data.gov.au/data/api/3/action/datastore_search?resource_id={r['id']}&limit={DATASTORE_LIMIT}"
    return {"source_id": sid, "dataset_id": s["dataset_id"], "shortlist_rank": s["rank"], "title": title,
            "publisher": s["publishing_organisation"], "licence": pkg.get("licence") or "unknown",
            "dataset_metadata_modified": pkg.get("metadata_modified"),
            "resource_id": r["id"], "resource_name": r["name"], "advertised_format": r["format"],
            "resource_last_modified": r.get("last_modified"), "url": url, "catalogue_url": r["url"],
            "rationale": why}


def run(include_seventh: bool = True) -> list[dict]:
    OUT_SOURCES.mkdir(parents=True, exist_ok=True)
    manifest = []
    for c in CHOICES + ([SEVENTH] if include_seventh else []):
        entry = resolve(c)
        try:
            meta = download(entry["url"], f"{entry['source_id']}__{entry['resource_id'][:8]}")
            entry.update(downloadable=True, snapshot=meta)
        except Exception as e:  # record, never silently substitute
            entry.update(downloadable=False, error=str(e)[:300])
        manifest.append(entry)
        print(entry["source_id"], entry.get("downloadable"), entry.get("snapshot", {}).get("bytes"), entry.get("error", ""))
    (OUT_SOURCES / "selected_sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def fetch_from_manifest() -> list[dict]:
    """Re-download exactly the committed manifest's resources and verify their sha256 (clean-checkout path)."""
    out = []
    for m in json.loads((OUT_SOURCES / "selected_sources.json").read_text(encoding="utf-8")):
        if not m.get("downloadable"):
            continue
        name = Path(m["snapshot"]["path"]).name
        try:
            meta = download(m["url"], name)
            ok = meta["sha256"] == m["snapshot"]["sha256"]
            out.append({"source_id": m["source_id"], "sha256_matches_manifest": ok,
                        "note": "" if ok else "upstream resource changed since the committed run; configs may need re-validation"})
        except Exception as e:
            out.append({"source_id": m["source_id"], "error": str(e)[:200]})
        print(out[-1], flush=True)
    bad = [o["source_id"] for o in out if o.get("error") or not o.get("sha256_matches_manifest")]
    if bad:  # fail loudly so a pipeline never runs on a missing or changed snapshot
        raise SystemExit(f"fetch failed or snapshot changed for: {bad}. Re-run `fetch` (transient errors) or re-onboard.")
    return out


def load_manifest() -> dict[str, dict]:
    from .register import local_sources

    manifest = OUT_SOURCES / "selected_sources.json"
    selected = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    return {m["source_id"]: m for m in [*local_sources(), *selected]}
