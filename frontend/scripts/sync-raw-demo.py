"""Build review-sized website data from the completed raw-data replay."""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "outputs/raw-data"
OUT = ROOT / "frontend/data"
sys.path.insert(0, str(ROOT))

from firmable.mapping.schema import MappingConfig  # noqa: E402
from firmable.rawdata.audit import (load_reviews, load_mapping_assessments, mapping_dependencies,
                                   mapping_evidence_digest)  # noqa: E402


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def lines(path):
    with path.open(encoding="utf-8-sig") as stream:
        yield from (json.loads(line) for line in stream if line.strip())


def write(name, value):
    path = OUT / name
    staging = path.with_suffix(".part")
    staging.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    staging.replace(path)


def pick(row, *keys):
    return {key: row[key] for key in keys if key in row}


def safe_claim(row):
    return row.get("privacy") != "personal" and not row["field"].startswith("ext.contact.") and (
        row["field"] not in {"ext.establishment.geo", "ext.entity.address_point"} and
        (row["field"] != "address.full" or row["source_id"] in {"vic_liquor", "dewr_employment_providers"})
    )


def evidence(row):
    item = pick(row, "observation_id", "source_id", "source_record_id", "source_row_ordinal", "field", "raw_value",
                "value", "source_fields", "transform", "derivation_level", "entity_role", "qualifiers",
                "confidence", "observed_at", "valid_from", "valid_to", "licence_detail", "approval_state")
    # A multi-column source can embed a business address or mailbox in the raw cell.
    if row["field"] != "address.full" and any(
        word in column.lower() for column in row["source_fields"] for word in ("phone", "email", "street", "address")
    ):
        item.pop("raw_value", None)
    return item


def safe_ref(ref):
    if ref.startswith("establishment:"):
        return ":".join(ref.split(":")[:2]) + ":" + hashlib.sha256(ref.encode()).hexdigest()[:12]
    return ref


def clean_relationship(row):
    item = pick(row, "type", "record", "to", "to_entity", "programme_label", "basis", "derivation_level", "approval_state")
    if "to" in item:
        item["to"] = safe_ref(item["to"])
    if item["type"] in {"TRUSTEE_NAMED", "LICENSED_INDIVIDUAL_FOR"}:
        item.pop("record", None)
        item.pop("to_entity", None)
    return item


def profile_view(row):
    item = pick(row, "entity_key", "profile_version", "sources", "mapping_approval_state", "registration_events",
                "firmographics", "conflicts")
    item["fields"] = {key: claim for key, claim in row["fields"].items() if key != "address.full"}
    item["locations"] = [{"source_id": location["source_record"].split("::")[0],
                          "scope": location["scope"], "fields": {
                              key: claim for key, claim in location["fields"].items() if key != "address.full"}}
                         for location in row.get("locations", [])]
    for key in ("establishments", "licences"):
        item[key] = []
        for raw in row[key]:
            fields = {name: value for name, value in raw["fields"].items()
                      if name != "geo" and (name != "address.full" or raw["source_id"] in {
                          "vic_liquor", "dewr_employment_providers"})}
            item[key].append(pick(raw, "source_id", "role", "records", "observation_ids") |
                             {"ref": safe_ref(raw["ref"]), "fields": fields})
    item["contact_count"] = len(row["contact_points"])
    item["contact_points_withheld_personal"] = row["contact_points_withheld_personal"]
    item["relationships"] = [clean_relationship(edge) for edge in row["relationships"]]
    # Raw values are displayed via the filtered observation index.
    def strip_raw(value):
        if isinstance(value, dict):
            value.pop("raw_value", None)
            for child in value.values():
                strip_raw(child)
        elif isinstance(value, list):
            for child in value:
                strip_raw(child)

    strip_raw(item)
    return item


def observation_ids(value):
    if isinstance(value, dict):
        if value.get("observation_id"):
            yield value["observation_id"]
        for key in ("observation_ids", "inputs", "supporting_observations"):
            yield from value.get(key, [])
        for child in value.values():
            yield from observation_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from observation_ids(child)


def audit_links(proposed, reviews):
    path = RUN / "evaluation/link_audit_strict_v3_raw_50.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result = []
    for row in rows:
        pair = (row["record_a"], row["record_b"])
        match = proposed[pair]
        if row["policy_version"] != match["policy_version"] or float(row["score"]) != match["confidence"]:
            raise ValueError("The saved audit does not match the selected matcher output")
        result.append({"index": int(row["idx"]), "link": match["link_id"], "label": row["label"].strip(),
                       "note": row["note"].strip(), "reviews": reviews.get(match["link_id"], {})})
    if len(result) != 50 or len({row["link"] for row in result}) != 50:
        raise ValueError("Expected 50 distinct saved audit links")
    with (OUT / "raw-link-audit.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = list(rows[0]) + ["ai_verdict", "ai_reviewer", "ai_note", "human_verdict", "human_reviewer"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for raw, item in zip(rows, result):
            ai = item["reviews"].get("ai_assistant", {})
            human = item["reviews"].get("human", {})
            writer.writerow(raw | {"ai_verdict": ai.get("verdict", ""), "ai_reviewer": ai.get("reviewer", ""),
                                   "ai_note": ai.get("note", ""), "human_verdict": human.get("verdict", ""),
                                   "human_reviewer": human.get("reviewer", "")})
    return result


def link_view(row):
    return pick(row, "link_id", "source_a_record", "source_b_record", "canonical_entity_key", "confidence",
                "policy_version", "threshold", "rule", "strata") | {
        "a": pick(row["a"], "source_id", "record_id", "grain", "names", "abn", "acn", "postcode"),
        "b": pick(row["b"], "source_id", "record_id", "grain", "names", "abn", "acn", "postcode"),
        "evidence": [pick(item, "type") if any(key in item["type"] for key in ("PHONE", "EMAIL", "GEO"))
                     else pick(item, "type", "value") for item in row["evidence"]],
    }


def queue_view(row):
    return pick(row, "source_record", "reason", "candidate_decision", "best_score", "rule", "next_action",
                "best_candidate") | {
        "record": pick(row.get("record") or {}, "source_id", "names"),
        "candidate": pick(row.get("candidate") or {}, "source_id", "names"),
    }


def main():
    OUT.mkdir(exist_ok=True)
    metrics = read(RUN / "evaluation/raw_data_metrics.json")
    summary = read(RUN / "identity/summary.json")
    sources = {row["source_id"]: pick(row, "title", "publisher", "catalogue_url", "url")
               for row in read(ROOT / "outputs/sources/selected_sources.json")}
    previous = read(ROOT / "data/registered/ato_tax_transparency_2023_24/source.json")
    sources[previous["source_id"]] = pick(previous, "title", "publisher", "catalogue_url")
    sources["ato_tax_transparency"]["title"] = "Corporate Tax Transparency · 2024–25"
    sources["ato_tax_transparency_2023_24"]["title"] = "Corporate Tax Transparency · 2023–24"

    profiles = [profile_view(row) for row in lines(RUN / "profiles/company_profiles_v3_50.jsonl")]
    if len(profiles) != metrics["profiles_v3"] or len({row["entity_key"] for row in profiles}) != len(profiles):
        raise ValueError("Profile sample and replay metrics disagree")
    needed = set(observation_ids(profiles))
    profile_evidence, mappings, mapping_digests = {}, [], {}
    usage = defaultdict(Counter)
    for row in lines(RUN / "usage_ledger.jsonl"):
        entry = usage[row.get("run_id")]
        if "prompt_tokens" in row:
            entry.update(calls=1, tokens=row["prompt_tokens"] + row.get("completion_tokens", 0),
                         ms=row.get("latency_ms", 0))

    for sid in metrics["review_state"]:
        doc = read(RUN / f"mappings/{sid}.json")
        cfg = doc["config"]
        mapping_digests[sid] = mapping_evidence_digest(doc | {"source_id": sid},
            RUN / f"observations/{sid}.jsonl", mapping_dependencies(cfg, ROOT))
        state = read(ROOT / f"runs/{sid}/{doc['run_id']}/state.json")
        sample = read(RUN / f"observations/{sid}.sample.json")
        proposal = state["proposals"][-1]
        if not (cfg["source_id"] == sid and state["source_id"] == sid and
                doc["run_id"] == sample["run_id"] == metrics["review_state"][sid]["run_id"] and
                MappingConfig.model_validate(cfg).digest() == doc["config_digest"] == state["final_digest"] ==
                proposal["digest"] == sample["config_digest"] and
                doc["snapshot_sha256"] == state["snapshot_sha256"] and
                doc["status"] == state["status"] == sample["mapping_status"]):
            raise ValueError(f"Mapping, agent state and extracted evidence disagree for {sid}")
        examples = {}
        field_counts = Counter()
        field_columns = defaultdict(set)
        for row in lines(RUN / f"observations/{sid}.jsonl"):
            field_counts[row["field"]] += 1
            field_columns[row["field"]].update(row["source_fields"])
            if row["extractor_version"] != sample["extractor_version"] or row["approval_state"] != sample["approval_state"]:
                raise ValueError(f"Mixed extraction versions in {sid}")
            if not safe_claim(row):
                continue
            if row["observation_id"] in needed:
                profile_evidence[row["observation_id"]] = pick(
                    evidence(row), "source_id", "source_row_ordinal", "source_fields", "raw_value", "value",
                    "observed_at", "derivation_level",
                ) | {"confidence": pick(row["confidence"], "field_confidence")}
            if row["field"].startswith("ext.") and row["field"] not in examples:
                examples[row["field"]] = evidence(row)
        if field_counts.total() != sample["observations"]:
            raise ValueError(f"Observation count mismatch for {sid}")
        crosswalks = []
        for name in metrics["review_state"][sid]["crosswalks"]:
            data = yaml.safe_load((ROOT / f"config/crosswalks/{name}.yaml").read_text(encoding="utf-8"))
            crosswalks.append(pick(data, "name", "version", "target", "derivation_level", "review_status") |
                              {"entries": len(data["entries"])})
        mappings.append({
            "id": sid, **sources[sid], "config": cfg,
            **pick(doc, "run_id", "status", "snapshot_sha256", "config_digest", "model"),
            "sample": pick(sample, "records", "observations", "edges", "approval_state"),
            "extracted_fields": [{"field": field, "observations": total, "columns": sorted(field_columns[field])}
                                 for field, total in sorted(field_counts.items())],
            "columns": metrics["columns"]["by_source"][sid], "examples": list(examples.values()),
            "holdout": {"records": proposal["holdout_report"]["records_in"],
                        "fields": [pick(f, "target", "source_paths", "source_present", "emitted", "errors", "dropped")
                                   for f in proposal["holdout_report"]["fields"]],
                        "issues": [pick(issue, "code", "severity", "target") for issue in proposal["holdout_issues"]]},
            "critic": [pick(f, "target", "source_paths", "verdict") for f in proposal["critic"]["fields"]],
            "crosswalks": crosswalks,
            "human_verification": next((decision for decision in reversed(list(lines(RUN / "mappings" / (sid + ".approvals.jsonl"))))
                if decision["config_digest"] == doc["config_digest"] and decision["snapshot_sha256"] == doc["snapshot_sha256"]), None)
                if (RUN / "mappings" / (sid + ".approvals.jsonl")).exists() else None,
            "trace": pick(state, "stages", "tool_calls", "started_at", "finished_at", "critic_model", "draft_source",
                          "previous_extension_run_id", "feedback_source", "local_revision") |
                     {"proposals": len(state["proposals"]), "usage": dict(usage[doc["run_id"]])},
        })

    assessments = load_mapping_assessments(RUN / "evaluation/mapping_review_decisions.jsonl", mapping_digests)
    for mapping in mappings:
        mapping["assessment"] = assessments.get(mapping["id"])

    for profile in profiles:
        for claim in profile["firmographics"].get("financial_facts", []):
            if claim["provenance"]["observation_id"] not in profile_evidence:
                raise ValueError(f"Missing financial provenance for {profile['entity_key']}")
    raw_links = list(lines(RUN / "identity/proposed_links.jsonl"))
    reviews = load_reviews(RUN / "evaluation/link_review_decisions.jsonl", {r["link_id"]: r for r in raw_links})
    links = [link_view(row) | {"reviews": reviews.get(row["link_id"], {})} for row in raw_links]
    pairs = {(row["source_a_record"], row["source_b_record"]): row for row in links}
    audit = audit_links(pairs, reviews)
    for profile in profiles:
        profile["link_review_findings"] = [review for row in links
            if row["canonical_entity_key"] == profile["entity_key"]
            for review in [row["reviews"].get("human") or row["reviews"].get("ai_assistant")]
            if review and review["verdict"] != "pass"]
    queue = [queue_view(row) for row in lines(RUN / "identity/unlinked_queue.jsonl")]
    review_count = sum(1 for _ in lines(RUN / "identity/review_queue.jsonl"))
    if len(links) != summary["challenger"]["links"] or len(queue) != summary["unlinked_queue"] or +            review_count != summary["challenger"]["decisions"]["REVIEW"]:
        raise ValueError("Link or queue artifacts disagree with the run summary")
    changes = list(lines(RUN / "evaluation/change_events.jsonl"))
    if Counter(row["event_type"] for row in changes) != metrics["change_events"]["by_type"]:
        raise ValueError("Change events disagree with the run metrics")
    # Include the bounded licence examples and period events that can be tied to displayed profiles.
    by_abn = {p["fields"]["entity.abn"]["value"]: p["entity_key"] for p in profiles if "entity.abn" in p["fields"]}
    event_examples = [row for row in changes if row.get("entity", "").removeprefix("abn:") in by_abn]
    event_examples += [row for row in changes if row["event_type"] == "FIELD_CHANGED" and
                       row["field"] in {"ext.licence.category", "ext.licence.grade"}][:40]

    review = {"pending_mappings": sum(row["sample"]["approval_state"] == "pending_human_review" for row in mappings),
              "verified_mappings": sum(row["sample"]["approval_state"] == "approved" for row in mappings),
              "mapping_assessed": len(assessments),
              "mapping_verdicts": dict(Counter(row["verdict"] for row in assessments.values())),
              "mappings": len(mappings), "audit_rows": len(audit),
              "audit_labelled": sum("human" in row["reviews"] for row in audit),
              "human_verdicts": dict(Counter(row["reviews"]["human"]["verdict"] for row in audit
                                             if "human" in row["reviews"])),
              "ai_labelled": sum("ai_assistant" in row["reviews"] for row in audit),
              "ai_verdicts": dict(Counter(row["reviews"]["ai_assistant"]["verdict"] for row in audit
                                          if "ai_assistant" in row["reviews"]))}
    replay = pick(summary, "policy_version", "threshold", "records", "records_by_stratum", "challenger",
                  "strict_v2_on_same_observations", "relationships", "unlinked_by_reason")
    replay["comparison"] = pick(summary["comparison"], "links_kept", "links_added", "links_removed", "dewr_links")
    featured = []
    for key, theme in (("fe_88da5b8124fc8be9", "financial"),
                       ("fe_0af37c51f3ce6b18", "establishments"),
                       ("fe_4e9aa5a41fed9c58", "licence")):
        profile = next((row for row in profiles if row["entity_key"] == key), None)
        if profile:
            featured.append({"id": key, "theme": theme, "name": profile["fields"]["entity.legal_name"]["value"],
                             "sources": profile["sources"], "establishments": len(profile["establishments"]),
                             "income": [pick(claim, "period", "value") for claim in
                                        profile["firmographics"].get("financial_facts", [])
                                        if claim["measure"] == "total_income"]})
    overview = {
        "date": max(row["trace"]["finished_at"] for row in mappings)[:10],
        "columns": metrics["columns"]["total"], "review": review, "replay": replay,
        "profiles": len(profiles), "observations": sum(row["sample"]["observations"] for row in mappings),
        "cost": pick(metrics["agent_cost"], "total_tokens", "total_estimated_usd", "rate", "per_record_model_cost_usd", "cost_report"),
        "changes": metrics["change_events"], "coverage": metrics["coverage"],
        "financial_corruption": metrics["financial_corruption_v3"], "featured": featured,
    }
    write("raw-demo.json", overview)
    write("raw-mapping.json", {"sources": sources, "mappings": mappings, "overview": overview})
    write("raw-identity.json", {"sources": sources, "links": links, "queue": queue, "audit": audit,
                               "overview": overview, "profileKeys": [row["entity_key"] for row in profiles]})
    write("raw-profiles.json", {"sources": sources, "profiles": profiles, "evidence": profile_evidence,
                               "events": event_examples, "overview": overview, "deletion": metrics["deletion_impact_v3"]})
    print(f"Exported {len(mappings)} mapping drafts, {len(links)} proposed links, {len(audit)} audit rows, "
          f"and {len(profiles)} profiles with {len(profile_evidence)} source observations.")


if __name__ == "__main__":
    main()
    import runpy
    runpy.run_path(str(ROOT / "frontend/scripts/build-assignment-writeup.py"), run_name="__main__")
