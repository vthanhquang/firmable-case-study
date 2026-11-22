"""Download the three researched government sources; no mapping rules are authored here.

The published API date interval is a frozen experimental cohort, not a claim to
cover every contract. Publisher content is data, not executable instructions.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("austender_new", "historical-australian-government-contract-data",
     "https://api.tenders.gov.au/ocds/findByDates/contractPublished/2026-10-01T00:00:00Z/2026-10-02T00:00:00Z",
     "austender_recent.json", "Government customer relationships, contract scope, procurement category, value and dates. One published-date interval; not all contracts.",
     "https://github.com/austender/austender-ocds-api"),
    ("brisbane_grants_new", "grants-recipients",
     "https://data.brisbane.qld.gov.au/api/explore/v2.1/catalog/datasets/grants-recipients/exports/json",
     "grants-candidate-2.json", "Funding awards, programmes, project descriptions, recipient names and ABNs. Includes individuals and community organisations; do not infer all recipients are companies.",
     "https://data.brisbane.qld.gov.au/explore/dataset/grants-recipients/export/"),
    ("npi_facilities_new", "npi",
     "https://data.gov.au/data/dataset/043f58e0-a188-4458-b61c-04e5b540aea4/resource/f83cdee9-ebcb-4f24-941b-34bb2f0996cf/download/facilities.csv",
     "npi_facilities.csv", "Operating footprint, facility-level ANZSIC/activity, operator identifiers and reporting history. Facilities table alone does not measure emissions or prove environmental compliance.",
     "https://www.dcceew.gov.au/environment/protection/npi/data")
]


def main():
    folder = ROOT / "data/autonomous-ontology"
    research = ROOT / "outputs/experiments/autonomous-ontology/research"
    folder.mkdir(parents=True, exist_ok=True)
    sources = []
    for sid, package, url, filename, rationale, docs in CASES:
        meta_path = research / (package + ".json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            response = httpx.get("https://data.gov.au/data/api/3/action/package_show", params={"id": package}, timeout=40)
            response.raise_for_status()
            meta = response.json()["result"]
        path = folder / filename
        if not path.exists() or not path.stat().st_size:
            response = httpx.get(url, timeout=90, follow_redirects=True)
            response.raise_for_status()
            if response.status_code != 200 or not response.content:
                raise ValueError("Publisher did not return a dataset: " + sid)
            path.write_bytes(response.content)
        licence_url = meta.get("license_url")
        if package == "grants-recipients":
            licence_url = "https://creativecommons.org/licenses/by/4.0/"
        if not licence_url or "creativecommons.org/licenses/by/" not in licence_url:
            raise ValueError("Inspect licence terms before using " + sid)
        publisher = (meta.get("organization") or {}).get("title") or meta.get("author")
        source = {"source_id": sid, "title": meta["title"], "publisher": publisher,
                  "dataset_id": meta["id"], "catalogue_url": "https://data.gov.au/data/dataset/" + package,
                  "url": url, "documentation_url": docs, "selection_rationale": rationale,
                  "notes": meta.get("notes", "")[:7000], "licence": meta.get("license_id"),
                  "licence_detail": {"id": meta.get("license_id"), "title": meta.get("license_title", "Creative Commons Attribution"),
                    "url": licence_url, "known": True, "attribution": f"{publisher}: {meta['title']}; {url}"},
                  "local_path": path.relative_to(ROOT).as_posix(),
                  "snapshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "snapshot_bytes": path.stat().st_size,
                  "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        sources.append(source)
    target = ROOT / "config/evolution_sources.json"
    # Preserve the original retrieval metadata/checkpoint identity when inputs have not changed.
    if target.exists():
        old = {s["source_id"]: s for s in json.loads(target.read_text(encoding="utf-8"))}
        sources = [old[s["source_id"]] if old.get(s["source_id"], {}).get("snapshot_sha256") == s["snapshot_sha256"] else s for s in sources]
    target.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    print("Prepared three government sources; no mapping rules or ontology concepts supplied.")


if __name__ == "__main__":
    main()
