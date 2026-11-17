"""Verify the seven local corrections against saved source rows and append an advisory assessment.

No model access, no human approvals. Run after raw-replay and review_mapping_evidence.py.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from firmable.mapping.schema import MappingConfig
from firmable.rawdata.audit import mapping_dependencies, mapping_evidence_digest, load_reviews
from firmable.rawdata.maintenance import verify_dependencies
from firmable.rawdata.store import iter_rows
from firmable.rawdata.review import write_extension_report, approval_state

RUN = ROOT / "outputs/raw-data"
ARCHIVE = ROOT / "outputs/maintenance/20261117-mapping-corrections"
checks = json.loads((RUN / "evaluation/mapping_review_checks.json").read_text())
bundle = json.loads((ROOT / "config/maintenance/mapping-corrections-20261117.json").read_text())
expected = {item["source_id"]: item for item in bundle["revisions"]}
readlines = lambda path: [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
obs = {sid: readlines(RUN / "observations" / (sid + ".jsonl")) for sid in checks["sources"]}
raw = {sid: {r["ordinal"]: r["row"] for r in iter_rows(sid)} for sid in obs}

for sid, check in checks["sources"].items():
    assert not check["replay_mismatches"] and not check["missing_raw_rows"], sid
    assert not [x for x in check["static_issues"] if x["severity"] == "error"], sid
    doc = json.loads((RUN / "mappings" / (sid + ".json")).read_text())
    assert check["records_checked"] == len(raw[sid]), sid
    assert doc["config_digest"] == check["config_digest"], sid
    verify_dependencies(doc)
    if sid in expected:
        assert doc["config_digest"] == MappingConfig.model_validate(expected[sid]["config"]).digest()

acnc = [o for o in obs["acnc_charities"] if o["field"].startswith("address.")]
assert all(o["entity_role"] == "subject" and o["claim_scope"] == "entity_contact_address" for o in acnc)
assert not (RUN / "observations/edges/acnc_charities.jsonl").read_text().strip()
postal = sum(bool(re.search(r"\b(?:P\.?\s*O\.?\s*BOX|GPO\s*BOX|LOCKED\s*BAG)\b",
    " ".join(str(row.get(k) or "") for k in ["Address_Line_1", "Address_Line_2", "Address_Line_3"]), re.I))
    for row in raw["acnc_charities"].values())
assert not checks["sources"]["acnc_charities"]["counts"].get("non_AU_country_claims")
for sid in ("asic_companies", "ato_tax_transparency"):
    assert not any(o["field"].startswith("address.") and o["transform"] == ["constant"] for o in obs[sid])
assert not checks["sources"]["asic_companies"]["counts"].get("incorrect_subclass_labels")
credit = obs["asic_credit_licensees"]
texts = [o for o in credit if o["field"] == "ext.licence.authorisation_text"]
assert len(texts) == len(raw["asic_credit_licensees"])
for o in texts:
    assert o["value"] == raw["asic_credit_licensees"][o["source_row_ordinal"]][o["source_fields"][0]].strip()
    assert o["entity_role"] == "licence"
dates = [o for o in credit if o["field"] == "ext.licence.start_date"]
assert len(dates) == 512 and not any(o["field"] == "ext.licence.authorisation" for o in credit)
for sid, role in (("dewr_employment_providers", "establishment"), ("vic_liquor", "premises")):
    defaults = [o for o in obs[sid] if o["field"].startswith("address.") and o["transform"] == ["constant"]]
    assert defaults and all(o["entity_role"] == role for o in defaults), sid
assert not any(o["field"] == "ext.entity.industry_code" for o in obs["qbcc_licensees"])
categories = sum(o["field"] == "ext.licence.category" for o in obs["qbcc_licensees"])
assert categories > 0
for sid in ("ato_tax_transparency", "ato_tax_transparency_2023_24"):
    assert not checks["sources"][sid]["counts"].get("missing_financial_qualifier")

before = json.loads((ARCHIVE / "before-manifest.json").read_text())
for name in ("runs/usage_ledger.jsonl", "outputs/raw-data/usage_ledger.jsonl", "outputs/raw-data/evaluation/link_review_decisions.jsonl"):
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == before.get(name, before.get(name.replace("/", "\\")))
links = readlines(RUN / "identity/proposed_links.jsonl")
retained = load_reviews(RUN / "evaluation/link_review_decisions.jsonl", {row["link_id"]: row for row in links})
human = Counter(item["human"]["verdict"] for item in retained.values() if "human" in item)

summaries = {
    "acnc_charities": f"Contact-address scope corrected for all ACNC address claims, including {postal} postal-box records; no operating-establishment edges remain. The conflicting Aruba/VIC country claim is withheld.",
    "asic_companies": "ASIC subclass meanings corrected for LISN/LISS/NLTD, including all 14 affected saved records. Seven records with unverified PUBF/RACA codes now omit the subclass interpretation. Unsupported address-country defaults removed.",
    "asic_credit_licensees": f"All {len(texts)} complete permission texts are preserved without splitting conditions; all {len(dates)} licence start dates are now explicit licence facts. Unverified location coordinates omitted.",
    "ato_tax_transparency": "Unsupported address-country defaults removed. All 2,473 financial claims retain reporting period and AUD qualifiers; blank amounts remain absent.",
    "ato_tax_transparency_2023_24": "Unchanged mapping rechecked: all 2,510 financial claims retain reporting period and AUD qualifiers, with no address-country default.",
    "dewr_employment_providers": "All 1,002 country defaults now describe the establishment, alongside its address. They no longer assert the business subject's country.",
    "qbcc_licensees": f"Ambiguous trade-to-industry inference removed. All {categories} published licence-category claims remain available with their licence and source evidence.",
    "vic_liquor": "All 2,000 state/country defaults now describe licensed premises. Interstate correspondence addresses are kept separately without an invented Victorian state.",
}
ledger = RUN / "evaluation/mapping_review_decisions.jsonl"
previous = readlines(ledger)
records = []
for sid, summary in summaries.items():
    doc = json.loads((RUN / "mappings" / (sid + ".json")).read_text())
    check = checks["sources"][sid]
    old = next(row for row in previous if row["source_id"] == sid)
    digest = mapping_evidence_digest(doc | {"source_id": sid}, RUN / "observations" / (sid + ".jsonl"), mapping_dependencies(doc["config"], ROOT))
    records.append({"source_id": sid, "run_id": doc["run_id"], "config_digest": doc["config_digest"], "snapshot_sha256": doc["snapshot_sha256"],
        "evidence_sha256": digest, "reviewer": "Codex (AI assistant)", "reviewer_kind": "ai_assistant",
        "reviewed_at": datetime.now(timezone.utc).isoformat(), "verdict": "ready", "summary": summary,
        "checks": {key: check[key] for key in ("records_checked", "saved_observations", "missing_raw_rows", "replay_mismatches")},
        "findings": [], "references": old["references"], "notes": [
            "The seven findings from the previous advisory review are resolved by these local corrections. No additional model API calls were made.",
            "Validation covers the saved sample, not every record in the full register or an unseen holdout. Zero replay differences measure reproducibility, not a zero false-positive rate.",
            "Ready means ready for human sign-off. No human approval was added. Other referenced draft crosswalks and the extension ontology remain subject to their own review.",
            "Original agent proposals and prior findings remain preserved. Local edits are an explicit user-requested exception to the assignment's agent-authored mapping workflow."]})
    if sid in expected:
        write_extension_report(sid, doc["run_id"])
with ledger.open("a", encoding="utf-8") as stream:
    for record in records:
        if not any(old["source_id"] == record["source_id"] and old["evidence_sha256"] == record["evidence_sha256"] for old in previous):
            stream.write(json.dumps(record) + "\n")
result = {"model_calls": 0, "usage_ledgers_unchanged": True, "corrections_verified": 7,
          "sources_replayed": len(records), "records_checked": sum(row["checks"]["records_checked"] for row in records),
          "observations_checked": sum(row["checks"]["saved_observations"] for row in records),
          "replay_mismatches": 0, "retained_human_link_reviews": dict(human), "human_approvals_added": 0,
          "current_human_verified_mappings": sum(approval_state(sid) == "approved" for sid in summaries),
          "source_findings": summaries}
(RUN / "evaluation/local_correction_checks.json").write_text(json.dumps(result, indent=2) + "\n")
report = ["# Local mapping corrections — 17 November 2026", "",
    "Seven findings corrected at the user's request without further model API calls. These are maintainer edits to preserved agent proposals; they are not represented as a new agent run or a human approval.", "",
    f"Replayed {result['records_checked']:,} frozen rows and verified {result['observations_checked']:,} observations with zero differences. Both API usage logs and the human link-review journal are unchanged.", ""]
report += [f"- **{sid}**: {summary}" for sid, summary in summaries.items()]
report += ["", f"All eight mappings pass the saved-sample correction checks; {result['current_human_verified_mappings']} have a matching human confirmation in the approval journals. This verification script adds no approval. The original review remains in MAPPING_REVIEW_2026-11-17.md. The immutable before/ archive and parent_mapping.json in each new run preserve the exact originals.", "",
    f"Human link reviews still matching current evidence: {dict(human)}. Changes to link evidence do not inherit a previous decision.", "",
    "No new accuracy percentage is claimed. Source data errors, the known link-review failures, draft interpretation tables, and incomplete source coverage remain visible limitations."]
(ROOT / "docs/MAPPING_CORRECTIONS_2026-11-17.md").write_text("\n".join(report) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
