"""Replay the saved mapping sample and collect bounded, non-contact review evidence."""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from firmable.mapping.engine import Engine
from firmable.mapping.schema import MappingConfig
from firmable.mapping.validate import static_issues
from firmable.rawdata.store import iter_rows
from firmable.sources.select import load_manifest

RUN = ROOT / "outputs/raw-data"


def signature(row):
    keys = ("field", "value", "source_fields", "entity_role", "qualifiers", "claim_scope", "valid_from", "valid_to")
    return json.dumps({key: row.get(key) for key in keys}, sort_keys=True)


def main():
    manifest = load_manifest()
    report = {"reviewed_at": datetime.now(timezone.utc).isoformat(),
              "method": "Replay all saved sample rows; compare values, columns, roles, qualifiers, scopes and validity. This is reproducibility evidence, not independent accuracy measurement.",
              "sources": {}}
    for path in sorted((RUN / "mappings").glob("*.json")):
        doc = json.loads(path.read_text())
        cfg = MappingConfig.model_validate(doc["config"])
        sid = cfg.source_id
        if cfg.digest() != doc["config_digest"]:
            raise ValueError("Mapping digest mismatch: " + sid)
        saved = defaultdict(list)
        obs_path = RUN / "observations" / (sid + ".jsonl")
        for row in map(json.loads, obs_path.read_text().splitlines()):
            saved[row["source_row_ordinal"]].append(row)
        engine = Engine(cfg, manifest[sid])
        seen, columns, mismatches = set(), set(), []
        counts, examples = Counter(), defaultdict(list)

        def flag(name, ordinal, evidence=None):
            counts[name] += 1
            if len(examples[name]) < 4:
                examples[name].append({"source_row_ordinal": ordinal, "evidence": evidence})

        for stored in iter_rows(sid):
            ordinal, raw = stored["ordinal"], stored["row"]
            columns.update(raw)
            if ordinal not in saved:
                continue
            seen.add(ordinal)
            output = engine.process(raw, rid=saved[ordinal][0]["source_record_id"])
            if Counter(map(signature, output)) != Counter(map(signature, saved[ordinal])):
                mismatches.append(ordinal)
            if sid == "acnc_charities":
                address = " ".join(str(raw.get(k) or "") for k in ["Address_Line_1", "Address_Line_2", "Address_Line_3"])
                if re.search(r"\b(?:P\.?\s*O\.?\s*BOX|GPO\s*BOX|LOCKED\s*BAG)\b", address, re.I) and any(
                        o["field"].startswith("address.") and o.get("entity_role") != "subject" for o in output):
                    flag("postal_addresses_as_establishments", ordinal, {"Address_Type": raw.get("Address_Type")})
                for o in output:
                    if o["field"] == "address.country" and o["value"] != "AU":
                        flag("non_AU_country_claims", ordinal, {"Country": raw.get("Country"), "State": raw.get("State"), "value": o["value"]})
            if sid == "asic_companies":
                code = raw.get("Sub Class", "").strip()
                expected = {"LISN": "omit Limited", "LISS": "omit Limited", "NLTD": "Not Limited"}
                if code in expected and not any(o["field"] == "ext.entity.legal_form_detail" and expected[code] in o["value"] for o in output):
                    flag("incorrect_subclass_labels", ordinal, {"Sub Class": code})
                counts["subclass_" + code] += 1
            if sid == "asic_credit_licensees":
                if raw.get("CRED_LIC_START_DT") and not any(o["field"] == "ext.licence.start_date" for o in output):
                    flag("licence_start_not_emitted", ordinal, {"licence": raw.get("CRED_LIC_NUM"), "date": raw.get("CRED_LIC_START_DT")})
                for o in output:
                    if o["field"] == "ext.licence.authorisation" and str(o["value"]).lower().startswith(("where the service", "by providing")):
                        flag("detached_authorisation_clauses", ordinal, {"licence": raw.get("CRED_LIC_NUM"), "value": o["value"]})
                    if o["field"] == "ext.licence.authorisation" and "..." in str(o["value"]):
                        flag("truncated_authorisation_claims", ordinal, {"licence": raw.get("CRED_LIC_NUM")})
            if sid == "vic_liquor":
                postcode = str(raw.get("Postal Postcode") or "").strip()
                if re.fullmatch(r"[124567]\d{3}", postcode):
                    flag("postal_postcode_outside_VIC_ranges", ordinal, {"licence": raw.get("Licence Number"), "postal_suburb": raw.get("Postal Suburb"), "postal_postcode": postcode})
                postal = str(raw.get("Postal Address") or "")
                match = re.search(r"\b(NSW|QLD|SA|WA|TAS|ACT|NT)\b\s*\d{4}\b", postal, re.I)
                if match and any(o["field"] == "address.state" and o["value"] == "VIC" and o.get("entity_role") == "subject" for o in output):
                    flag("non_VIC_postal_address_with_subject_VIC_constant", ordinal, {"licence": raw.get("Licence Number"), "postal_state": match[1].upper()})
            if sid == "dewr_employment_providers":
                phones = [o for o in output if o["field"] == "ext.contact.phone"]
                if len(phones) > len({o["value"] for o in phones}):
                    flag("phone_repeated_across_source_roles", ordinal)
            if sid.startswith("ato_tax_transparency"):
                for o in output:
                    if o["field"].startswith("ext.financial."):
                        counts["financial_claims"] += 1
                        if o.get("qualifiers", {}).get("currency") != "AUD" or not o.get("qualifiers", {}).get("period"):
                            flag("missing_financial_qualifier", ordinal)
            counts["constant_address_claims"] += sum(o["field"].startswith("address.") and o["transform"] == ["constant"] for o in output)
        result = {"run_id": doc["run_id"], "config_digest": doc["config_digest"], "snapshot_sha256": doc["snapshot_sha256"],
                  "observations_sha256": hashlib.sha256(obs_path.read_bytes()).hexdigest(),
                  "records_checked": len(seen), "saved_observations": sum(map(len, saved.values())),
                  "missing_raw_rows": sorted(set(saved) - seen), "replay_mismatches": mismatches,
                  "static_issues": static_issues(cfg, columns), "counts": dict(counts), "examples": dict(examples),
                  "replay_report": engine.report()}
        report["sources"][sid] = result
        print(sid, "records", len(seen), "mismatches", len(mismatches), "findings", dict(counts), flush=True)
    out = RUN / "evaluation/mapping_review_checks.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
