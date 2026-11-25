"""Independent workbook checks and a targeted, unpromoted WGEA profile demo.

This is evaluation code, not an input parser or a hand-authored mapping. The
demo executes the exact recorded agent mapping through the shared extractor.
"""
import csv
import gzip
import json
import math
import random
from collections import defaultdict
from pathlib import Path

import openpyxl

from firmable.evolution.engine import extract
from firmable.evolution.registry import Registry, write
from firmable.evolution.schema import DynamicMapping, Inspection, digest
from firmable.sources.readers import iter_records

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/experiments/profile-enrichment"


def main():
    folder = EXP / "wgea-retest/wgea_employers_new"
    result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    if result["status"] != "AGENT_VALIDATED_CANDIDATE":
        raise ValueError("Only evaluate an accepted candidate; no manual mapping substitute")
    source = next(s for s in json.loads((ROOT / "config/profile_enrichment_sources.json").read_text(encoding="utf-8"))
                  if s["source_id"] == "wgea_employers_new")
    workbook = openpyxl.load_workbook(ROOT / source["local_path"], read_only=True, data_only=True)
    raw = list(workbook["2. Employers "].values)
    workbook.close()
    # Independent publisher-column positions, rather than the parser under test.
    headers = [" ".join(str(h).split()) for h in raw[3]]
    headers = [h + "_2" if i in range(10, 14) else h for i, h in enumerate(headers)]
    with gzip.open(folder / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream]
    sample = random.Random(20261123).sample([r for r in records if r["partition"] == "test"], 20)
    by_record = defaultdict(list)
    for line in (folder / "observations.jsonl").read_text(encoding="utf-8").splitlines():
        claim = json.loads(line)
        by_record[claim["source_record_id"]].append(claim)
    checks = []
    for record in sample:
        row = raw[record["ordinal"] + 3]
        for claim in by_record[record["record_id"]]:
            field = claim["source_fields"][0]
            index = headers.index(field)
            expected, value = row[index], claim["value"]
            equal = math.isclose(float(value), float(expected), rel_tol=1e-12, abs_tol=1e-12) if isinstance(expected, (int, float)) else str(value) == " ".join(str(expected).split())
            period = ("2024-25" if index < 10 else "2023-24") if 6 <= index <= 13 else None
            actual_period = claim.get("qualifiers", {}).get("period", "")
            checks.append({"source_row_ordinal": record["ordinal"], "employer": row[0], "column": field,
                "source_value": expected, "emitted_value": value, "expected_period": period or "",
                "actual_period": actual_period, "value_matches": equal,
                "period_matches": period is None or actual_period == period,
                "review_type": "automated_source_comparison_not_human_label"})
    with (EXP / "wgea-20-record-check.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=checks[0].keys())
        writer.writeheader()
        writer.writerows(checks)
    summary = {"records": 20, "seed": 20261123, "claims_checked": len(checks),
        "value_mismatches": sum(not x["value_matches"] for x in checks),
        "period_mismatches": sum(not x["period_matches"] for x in checks),
        "scope": "Direct original workbook comparison of emitted values and pay-gap years in 20 seeded sealed-test records. Not human-measured semantic precision or non-emitted coverage."}
    write(EXP / "wgea-audit-summary.json", summary)
    if summary["value_mismatches"] or summary["period_mismatches"]:
        raise ValueError("Independent comparison failed")

    profiles = [json.loads(line) for line in (ROOT / "outputs/raw-data/profiles/company_profiles_v3_50.jsonl").read_text(encoding="utf-8").splitlines()]
    targets = {str(p["fields"].get("entity.abn", {}).get("value")): p for p in profiles if p["fields"].get("entity.abn", {}).get("value")}
    cfg = DynamicMapping.model_validate_json((folder / "mapping.json").read_text(encoding="utf-8"))
    inspection = Inspection.model_validate_json((folder / "inspection.json").read_text(encoding="utf-8"))
    ontology = Registry(folder.parent / "registry").load(result["ontology_version"])
    abn_column = next(f.source_paths[0] for f in cfg.fields if f.target == "entity.abn")
    selected = []
    for ordinal, row in enumerate(iter_records(ROOT / source["local_path"], inspection.reader), 1):
        if str(row.get(abn_column, "")) in targets:
            selected.append({"ordinal": ordinal, "row": row, "record_id": digest(row)})
    observations, edges, refusals, metrics = extract(cfg, source, ontology, selected, inspection,
                                                    review_state="targeted_demo_pending_human_review")
    grouped = defaultdict(list)
    for claim in observations:
        grouped[claim["source_record_id"]].append(claim)
    demos = []
    for record in selected:
        claims = grouped[record["record_id"]]
        identifier = next((c["value"] for c in claims if c["field"] == "entity.abn"), None)
        if identifier not in targets:
            continue
        old = targets[identifier]
        demos.append({"existing_entity_key": old["entity_key"], "existing_name": old["fields"].get("entity.legal_name", {}).get("value"),
            "abn": identifier, "match_basis": "Exact checksum-validated ABN; proposal, not a hand-audited link",
            "review_state": "targeted_demo_pending_human_review", "new_observations": claims})
    write(EXP / "targeted-wgea-profiles.json", {"selection": "All exact ABN matches to the existing 50; targeted demonstration, not a random evaluation cohort.",
        "production_modified": False, "profiles": demos, "metrics": metrics, "refusals": refusals})
    print(json.dumps({"audit": summary, "targeted_profiles": len(demos), "targeted_observations": len(observations)}))


if __name__ == "__main__":
    main()
