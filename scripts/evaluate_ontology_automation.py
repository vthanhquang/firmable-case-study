"""Evaluate saved ontology runs and size the human-review inventory, offline.

No model calls, mapping changes, approvals or production writes. Time estimates
are explicit planning assumptions; measured human working time is unavailable.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/experiments/profile-enrichment"
CASES = [("ACNC AIS", "run", "acnc_ais2024_new"),
         ("WGEA", "wgea-retest", "wgea_employers_new"),
         ("IP Australia", "ip-pilot", "ip_party_activity_new")]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checkpoints(folder, role):
    return sorted(folder.glob(f"*-{role}.json"), key=lambda p: int(p.name.split("-")[0]))


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "/").replace("\n", " ")
    return ["| " + " | ".join(map(cell, headers)) + " |", "| " + " | ".join("---" for _ in headers) + " |"] + [
        "| " + " | ".join(map(cell, row)) + " |" for row in rows]


def main():
    inventory_path = BASE / "human-review-inventory.csv"
    if inventory_path.exists():
        with inventory_path.open(encoding="utf-8", newline="") as stream:
            if any(any(row.get(k, "").strip() for k in ("human_verdict", "reviewer", "review_minutes", "notes")) for row in csv.DictReader(stream)):
                raise ValueError("Human review work exists; preserve it and create a new evaluation snapshot instead of regenerating this inventory.")
    sources, inventory = [], []
    for name, run, sid in CASES:
        folder = BASE / run / sid
        result, sample = read(folder / "result.json"), read(folder / "sampling.json")
        architects, mappers, validations = [checkpoints(folder, role) for role in ("architect", "mapper", "validation")]
        proposal, mapping = read(architects[-1])["response"], read(mappers[-1])["response"]
        usage = [json.loads(line) for line in (BASE / run / "usage.jsonl").read_text().splitlines()]
        usage = [u for u in usage if u["source_id"] == sid]
        evaluations = [(p.name, read(p)) for p in validations if "heldout" in read(p)]
        latest = evaluations[-1][1] if evaluations else {}
        errors = Counter()
        for field in latest.get("heldout", {}).get("fields", []):
            errors.update(field["errors"])
        row = {"source": name, "source_id": sid, "run": run, "status": result["status"],
            "sample_records": sample["sample_rows"], "partitions": sample["partitions"],
            "architect_attempts": len(architects), "mapper_attempts": len(mappers),
            "unique_mapping_responses": len({json.dumps(read(p)["response"], sort_keys=True) for p in mappers}),
            "executed_evaluations": len(evaluations),
            "critic_verdicts": [v["critic"]["verdict"] for _, v in evaluations],
            "latest_validation_observations": latest.get("heldout", {}).get("observations"),
            "latest_validation_present_values": latest.get("heldout", {}).get("present_values"),
            "latest_validation_rejection_reasons": dict(errors),
            "new_concepts": len(proposal["concepts"]), "reuse_decisions": len(proposal["reuse"]),
            "new_entity_types": len(proposal["entity_types"]), "new_relationship_types": len(proposal["relationships"]),
            "mapping_rules": len(mapping["fields"]),
            "mapped_source_columns": len({p for f in mapping["fields"] for p in f["source_paths"]}),
            "unmapped_declarations": len(mapping["unmapped"]),
            "accepted_observations": result.get("extraction", {}).get("observations", 0),
            "sealed_test": {k: result.get("test", {}).get(k) for k in ("input_records", "present_values", "value_errors")},
            "model_calls": sum("error" not in u for u in usage), "failed_requests": sum("error" in u for u in usage),
            "input_tokens": sum(u.get("prompt_tokens", 0) for u in usage),
            "output_tokens": sum(u.get("completion_tokens", 0) for u in usage),
            "cumulative_request_seconds": round(sum(u.get("latency_ms", 0) for u in usage) / 1000, 1),
            "proposal_file": architects[-1].relative_to(ROOT).as_posix(),
            "mapping_file": mappers[-1].relative_to(ROOT).as_posix()}
        sources.append(row)
        readiness = "ready_for_domain_review" if row["status"] == "AGENT_VALIDATED_CANDIDATE" else "technical_block_first"
        common = {"source": name, "readiness": readiness, "human_verdict": "", "reviewer": "", "review_minutes": "", "notes": ""}
        for kind, items, key in [("new_concept", proposal["concepts"], "path"),
                                 ("new_entity_type", proposal["entity_types"], "name"),
                                 ("new_relationship_type", proposal["relationships"], "name")]:
            inventory += [common | {"kind": kind, "item": v[key], "evidence": row["proposal_file"], "review_question": v["definition"]} for v in items]
        inventory += [common | {"kind": "reuse_decision", "item": k, "evidence": row["proposal_file"], "review_question": v} for k, v in proposal["reuse"].items()]
        inventory += [common | {"kind": "mapping_rule", "item": f"{i + 1}: {f['target']}", "evidence": row["mapping_file"],
                       "review_question": f"Columns {f['source_paths']}; role {f.get('entity') or 'subject'}; {f['rationale']}"}
                      for i, f in enumerate(mapping["fields"])]
    totals = {k: sum(s[k] for s in sources) for k in ("sample_records", "new_concepts", "reuse_decisions", "new_entity_types", "new_relationship_types", "mapping_rules", "model_calls", "failed_requests", "input_tokens", "output_tokens")}
    totals.update(accepted_sources=sum(s["status"] == "AGENT_VALIDATED_CANDIDATE" for s in sources),
                  sources=3, recorded_human_semantic_verdicts=0, recorded_human_work_minutes=None,
                  manually_edited_mappings=0, external_shared_reader_repairs=1)
    history = []
    for sid in ("austender_new", "brisbane_grants_new", "npi_facilities_new"):
        r = read(ROOT / "outputs/experiments/autonomous-ontology/run" / sid / "result.json")
        history.append({"source_id": sid, "status": r["status"], "rounds": r["rounds"], "new_concepts": r["new_concepts"],
                        "observations": r["extraction"]["observations"], "test_present_values": r["test"]["present_values"]})
    # Transparent sizing model, not a forecast or time saved versus a manual baseline.
    effort = []
    for s in sources:
        ontology_items = s["new_concepts"] + s["new_entity_types"] + s["new_relationship_types"]
        low = 10 + ontology_items * 2 + s["mapping_rules"] * .5 + 20 + 5
        high = 15 + ontology_items * 4 + s["mapping_rules"] + 40 + 10
        effort.append({"source": s["source"], "review_minutes_low": low, "review_minutes_high": high,
                       "condition": "After technical blockers are fixed; includes 20 record checks, excludes engineering and new audit findings."})
    payload = {"scope": "Three latest sources; WGEA repaired run and independent IP run are separate assisted attempts, not duplicates of budget-skipped baseline attempts.",
        "sources": sources, "totals": totals, "historical_assisted_runs": history, "human_effort_scenario": effort,
        "effort_assumptions_minutes": {"source_scope": [10, 15], "per_new_ontology_item": [2, 4], "per_mapping_rule": [.5, 1], "per_sample_record": [1, 2], "records_per_source": 20, "signoff": [5, 10]},
        "limitations": ["No measured human semantic precision or manual-work baseline.", "No measured autonomy/time-saving percentage.",
            "Rules and ontology concepts overlap in reviewer effort; the itemized scenario may double-count bundled work and undercount difficult cases.",
            "Reused concepts are examined through mapping review; provenance-only reuse is not an additional full semantic review in the time model.",
            "Twenty records are a debugging/review sample, not evidence of high population precision. Sample informative edge cases as well as random records."]}
    (BASE / "automation-evaluation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for item in inventory:
        item["evidence_sha256"] = hashlib.sha256((ROOT / item["evidence"]).read_bytes()).hexdigest()
    with inventory_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(inventory[0])); writer.writeheader(); writer.writerows(inventory)
    lines = ["# Auto-ontology evaluation and human review", "", "## What the experiments establish", "",
        "The pipeline automates proposal writing, executable mapping generation, validation, evidence capture and candidate replay. It is not yet a reliable unattended onboarding system. The latest trial accepted 1 of 3 sources (33.3%) after external assistance. This is a small, selected experiment outcome, not an estimated production success rate or semantic accuracy.", ""]
    lines += table(["Source", "Sample", "New concepts", "Mapping rules", "Mapper attempts", "Executed evaluations", "Outcome"], [
        [s["source"], s["sample_records"], s["new_concepts"], s["mapping_rules"], s["mapper_attempts"], s["executed_evaluations"], s["status"]] for s in sources])
    lines += ["", "All 130 latest mapping rules and 86 proposed concepts were model-authored. This is an authorship count, not proof that they are correct or that 100% of onboarding work is automated. Only WGEA's 10 concepts/24 rules reached an accepted candidate; ACNC's 63 and IP's 13 concepts remain draft proposals. The latest ACNC fifth-round proposal was not mapped before the budget stopped; its last evaluated mapping is from the fourth round.", "",
        "The original three-source process exhausted its shared budget on ACNC before trying WGEA or IP. WGEA and IP therefore use their separate processes here; the skipped attempts are not counted as extra source failures. The WGEA process used a shared-reader repair. No untouched three-source autonomy rate can be estimated from this run.", "",
        "Historical context: AusTender, Brisbane grants and NPI eventually produced three accepted candidates after generic controller fixes and explicit resumes (8, 6 and 7 total numbered rounds respectively). Across the six distinct sources, 4/6 eventually reached candidates with supervision; that 66.7% must not be advertised as autonomous success. Accepted sources total 47 new concepts and 32,464 observations. Their 0/6,172 sealed-test rejected values measures types/constraints only, not semantic precision.", "",
        "## Where automation works and where it stops", ""]
    lines += table(["Stage", "Measured evidence", "Human or engineering role"], [
        ["Source discovery/intake", "3 sources researched and registered externally; not autonomous discovery", "Confirm usefulness, licence, scope and entity granularity"],
        ["Reader and sample", "3/3 created 600-record samples; WGEA originally lost 4/24 columns", "Schema-fidelity checks; one external shared-reader repair"],
        ["Ontology/mapping proposals", "3/3 produced drafts: 86 concepts, 130 rules, 2 entity types, 1 relationship type", "Assess meaning, reuse, ownership, units, periods and unsupported assumptions"],
        ["Static gates", "IP blocked in all 5 mapping rounds", "Engineer improves exact-field feedback and repeated-proposal stop; do not ask reviewers to approve invalid mappings"],
        ["Extraction and critic", "ACNC and WGEA reached validation; IP did not", "Review abstention policy and spot-check critic findings"],
        ["Sealed test / replay", "Only WGEA reached test: 0/2,556 rejected values; offline replay succeeds", "Check semantics and sampled evidence before approval"],
        ["Production promotion", "0 promoted; no recorded human semantic verdicts", "Explicit approval of the exact candidate version"]])
    lines += ["", "## The two unresolved technical blocks", "",
        "ACNC's last validation emitted 8,158 observations from 140 records. It withheld 728 present financial values because 26/140 records (18.6%) lacked reporting periods. The same omission affects 28 rules per affected record: 26 × 28 = 728. The controller rejected an 8.2074% rejection rate against its 5% threshold, although the critic accepted the latest mapping. These are correlated missing-data conditions, not 728 separate manual-review tasks or 728 demonstrated wrong emitted claims. A reviewer should decide the period/abstention policy once, supported by representative examples; an engineer must separate abstentions from malformed values without fabricating dates.", "",
        "IP repeated a mapping targeting observation.valid_from and observation.valid_to, which the controller forbids as ordinary field targets. Its last three mapping responses were identical. It never reached extraction or the critic, so zero accepted IP observations does not establish that its dataset is unusable. Improve actionable field-level feedback and loop-stagnation detection before semantic sign-off. Agent-versus-applicant roles and activity-versus-enforceability dates still need domain review after a valid mapping exists.", "",
        "## How much human review is needed", "",
        "The inventory CSV contains 242 review entries: 86 concept definitions, 23 reuse decisions (including repeated provenance concepts), 130 mapping rules, two entity types and one relationship type. These entries overlap and are not 242 independent tasks. WGEA has 40 entries ready for domain review; the other 202 are draft inventory behind technical blocks. Do not review every superseded proposal or every generated observation.", "",
        "For WGEA now: review 10 concepts and their 24 mapping rules together, including the reused ABN/provenance semantics; check a 20-record sample with both reporting years, missing values, negative gaps and extreme sizes; then approve or reject its immutable candidate. The existing 468 comparisons across 20 records were automated and cannot be counted as human labels. The targeted 21-profile/500-observation demonstration likewise remains unpromoted.", "",
        "For ACNC/IP: resolve the technical blocks first, rerun evaluation, and review the final concept/rule bundles. Add focused checks for consolidated financial scope and missing periods (ACNC), and individuals versus organisations, patent agents versus applicants, and historical versus current roles (IP).", "",
        "### Illustrative effort scenario — not measured working time", "",
        "Assumptions: source scope 10–15 minutes; each new concept/entity/relationship 2–4 minutes; each mapping rule 0.5–1 minute; 20 record checks at 1–2 minutes each; sign-off 5–10 minutes. Reuse is checked within the mapping review. Complex cases may take longer; reviewing rules with concepts may reduce overlap.", ""]
    lines += table(["Source", "Calculated reviewer minutes", "When"], [[s["source"], f"{s['review_minutes_low']:g}–{s['review_minutes_high']:g}", s["condition"]] for s in effort])
    low, high = sum(s["review_minutes_low"] for s in effort), sum(s["review_minutes_high"] for s in effort)
    lines += ["", f"Total scenario: {low:g}–{high:g} reviewer minutes ({low/60:.1f}–{high/60:.1f} hours) for all three after technical repair. Engineering time, source acquisition, further corrections and statistical precision auditing are excluded. These are planning assumptions, not measured savings or a commitment.", "",
        "## Measurements to add to the next trial", "",
        "Freeze the engine and preregister new sources before starting. Measure separately: candidate acceptance without intervention; external interventions per source; new-concept accept/modify/reject rates; mapping-rule accept/modify/reject rates; stratified record/claim audit precision; abstention counts and reasons; unsupported-claim errors; ontology reuse/duplication; and elapsed versus active human minutes. Record reviewer verdicts against immutable concept/mapping versions. Label mixed purposive/random samples explicitly; do not treat every field in a record as an independent accuracy trial.", "",
        "Human time saved requires a comparable manual baseline: (manual active minutes − assisted active minutes) / manual active minutes. Neither baseline minutes nor assisted human minutes were collected, so no 80–90% automation or time-saving claim is supported. The estimated review times above should be replaced with observed timings from the inventory.", "",
        "## Recorded model usage", ""]
    lines += table(["Source", "Calls", "Input tokens", "Output tokens", "Cumulative request seconds"], [[s["source"], s["model_calls"], s["input_tokens"], s["output_tokens"], s["cumulative_request_seconds"]] for s in sources])
    lines += ["", "Request times are cumulative model latency, not end-to-end or human working time; some runs overlapped. No new model calls were made for this evaluation. No mapping, approval, production state, commit or push was changed.", ""]
    (BASE / "AUTOMATION_EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")
    assert totals["new_concepts"] == 86 and totals["mapping_rules"] == 130
    assert len(inventory) == 242
    print(json.dumps({"totals": totals, "review_inventory": len(inventory), "reviewer_minutes_scenario": [low, high]}))


if __name__ == "__main__":
    main()
