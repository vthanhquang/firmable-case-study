"""Verify and summarize the artifacts and provider usage from a completed quality replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from . import llm
from .mapping.schema import MappingConfig
from .paths import OUT_DISCOVERY, OUT_SOURCES


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping_metrics(folder, replay, holdout):
    counts = {"baseline": Counter(), "replay": Counter()}
    sources = {}
    for sid, choice in replay["mappings"].items():
        source = holdout["sources"][sid]
        versions = source["versions"]
        baseline, selected = versions["approved_baseline"], versions[choice["variant"]]
        published = _json(folder / "selected-mappings" / f"{sid}.json")
        effective = MappingConfig.model_validate(published["config"]).digest()
        if (selected["config_digest"] != choice["config_digest"] or effective != choice["config_digest"] or
                not selected["reference_reader_rows_match"] or published["run_id"] != choice["run_id"]):
            raise ValueError(f"The replay config for {sid} does not match the held-out evaluation")
        sources[sid] = {"variant": choice["variant"], "run_id": choice["run_id"], "replayed": choice["rows_replayed"],
                        "observations": choice["canonical_observations"], "evaluation_rows": source["validation_rows"]}
        for label, result in (("baseline", baseline), ("replay", selected)):
            for key in ("rows", "matched_claims", "expected_claims", "unexpected_claims", "checked_rows_and_fields", "exact"):
                counts[label][key] += result[key]
            counts[label]["scope_findings"] += sum(result["scope_issues"].values())
    return {"sources": sources, **counts}


def run(folder: Path) -> dict:
    replay = _json(folder / "replay.json")
    holdout = _json(folder / "evaluation" / "mapping-holdout.json")
    discovery = _json(folder / "discovery" / "metrics.json")
    discovery_audit = _json(folder / "discovery" / "audit" / "metrics.json")
    identity = _json(folder / "evaluation" / "identity-benchmark.json")
    link_audit = _json(folder / "evaluation" / "link_audit_metrics.json")
    profiles = _json(folder / "evaluation" / "profile-benchmark.json")
    if discovery["shortlist"] != 50 or discovery_audit["sampled"] != 20 or link_audit["sampled"] != 50:
        raise ValueError("The final shortlist or audits are incomplete")
    if _digest(folder / "discovery" / "shortlist.jsonl") != discovery_audit["shortlist_sha256"]:
        raise ValueError("Discovery audit is bound to a different shortlist")
    if _digest(folder / "identity" / "proposed_links.jsonl") != link_audit["proposed_links_sha256"]:
        raise ValueError("Identity audit is bound to a different link population")
    adjudication_path = folder / "evaluation" / "link_audit_adjudications.json"
    if adjudication_path.exists():
        adjudication = _json(adjudication_path)
        evidence_path = folder / "evaluation" / "link_audit_evidence.json"
        if (_digest(evidence_path) != adjudication["proxy_evidence_sha256"] or
                _digest(folder / "evaluation" / "asic_name_history_crosscheck.json") != adjudication["asic_name_history_sha256"]):
            raise ValueError("Registry adjudication evidence changed")
        labels = {row["link_id"]: row["proxy_label"] for row in _json(evidence_path)}
        for case in adjudication["cases"]:
            if labels[case["link_id"]] != case["original_proxy_label"]:
                raise ValueError("Registry adjudication disagrees with the original proxy verdict")
            labels[case["link_id"]] = case["adjudicated_label"]
        link_audit["after_registry_adjudication"] = {"reviewer_kind": adjudication["reviewer_kind"],
                                                      "cases_checked": len(adjudication["cases"]),
                                                      "labels": dict(Counter(labels.values()))}
    registry_path = folder / "evaluation" / "registry_audit_crosscheck.json"
    if registry_path.exists():
        registry = _json(registry_path)
        if _digest(folder / "evaluation" / "link_audit_evidence.json") != registry["audit_evidence_sha256"]:
            raise ValueError("Registry cross-check is bound to a different audit sample")
        link_audit["registry_crosscheck"] = registry["summary"]
    if profiles["challenger"]["profiles"] != 50 or profiles["challenger"]["provenance_errors"]:
        raise ValueError("The 50-profile replay failed integrity checks")
    if len(replay["mappings"]) != 6 or any(row["rows_without_observations"] for row in replay["mappings"].values()):
        raise ValueError("The six-source replay is incomplete")
    final_ids = {row["dataset_id"] for row in _lines(folder / "discovery" / "shortlist.jsonl")}
    manifest = {row["source_id"]: row for row in _json(OUT_SOURCES / "selected_sources.json")}
    if any(manifest[sid]["dataset_id"] not in final_ids for sid in replay["mappings"]):
        raise ValueError("A replayed source is absent from the final shortlist")
    ledger = _lines(folder / "usage.jsonl")
    measured = _lines(folder / "billing.jsonl")
    start, end = measured[0], measured[-1]
    prompt_tokens = sum(row["prompt_tokens"] for row in ledger)
    completion_tokens = sum(row["completion_tokens"] for row in ledger)
    token_count = prompt_tokens + completion_tokens
    if (start["label"] != "quality-final-start" or start["ledger_tokens"] or end["label"] != "quality-final-end" or
            end["ledger_tokens"] != token_count):
        raise ValueError("Final provider billing snapshots do not bound the complete usage ledger")
    known_cost = sum(llm.usd(row["model"], row["prompt_tokens"], row["completion_tokens"]) or 0 for row in ledger)
    meter_usd = round((end["total_usage_cents"] - start["total_usage_cents"]) / 100, 4)
    baseline = _lines(OUT_DISCOVERY / "shortlist_50.jsonl")
    result = {
        "discovery": {"shortlist": discovery["shortlist"], "catalogue_candidates": discovery["catalogue_candidates"],
                      "publisher_tables_read": discovery["rows_read"],
                      "benchmark_sources_in_shortlist": len(replay["mappings"]),
                      "baseline_distinct_scores": len({row["confidence"] for row in baseline}),
                      "replay_distinct_scores": discovery["distinct_shortlist_scores"], "proxy_audit": discovery_audit},
        "mapping": _mapping_metrics(folder, replay, holdout),
        "identity": {"summary": replay["identity"], "benchmark": identity, "proxy_audit": link_audit},
        "profiles": {"summary": profiles,
                     "asic_date_corruption": _json(folder / "evaluation" / "source_corruption_impact.json"),
                     "asic_name_corruption": _json(folder / "evaluation" / "source_name_corruption_impact.json")},
        "usage": {"window_start": start["ts"], "window_end": end["ts"], "final_tokens": token_count,
                  "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                  "successful_calls": sum(not row.get("error") for row in ledger), "failed_attempts": sum(bool(row.get("error")) for row in ledger),
                  "models": dict(Counter(row["model"] for row in ledger)), "estimated_usd": round(known_cost, 4),
                  "provider_meter_delta_usd": meter_usd, "budget_usd": 10,
                  "provider_meter_within_budget": 0 <= meter_usd <= 10},
    }
    (folder / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    result = run(args.experiment)
    print(json.dumps(result["usage"], indent=2))
