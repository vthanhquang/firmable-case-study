"""Replay selected mapping proposals on the frozen benchmark rows in an isolated experiment."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ..agent.review import current_approval
from ..extract import load_config, reliability, verify_snapshot
from ..identity.resolve import EVIDENCE_POLICY, run as resolve
from ..paths import OUT_MAPPINGS, OUT_OBS, ROOT
from ..profiles.build import EVIDENCE_PROFILE, run as profiles
from ..sources.readers import iter_records
from ..sources.select import load_manifest
from .engine import Engine
from .schema import MappingConfig


def _rank(version):
    return (-version["unexpected_claims"], version["matched_claims"], -sum(version["scope_issues"].values()),
            version["exact"])


def select(benchmark: dict, proposal_dirs: list[Path]) -> dict:
    directories = {"approved_baseline": OUT_MAPPINGS} | {path.name: path for path in proposal_dirs}
    selected = {}
    for sample in sorted(OUT_OBS.glob("*.jsonl")):
        sid = sample.stem
        versions = benchmark["sources"][sid]["versions"]
        baseline = versions["approved_baseline"]
        eligible = {label: record for label, record in versions.items() if label in directories and
                    record["reference_reader_rows_match"] and record["status"] == "PENDING_REVIEW" and
                    (label == "approved_baseline" or not record.get("semantic_gate_errors")) and
                    record["matched_claims"] >= baseline["matched_claims"] and
                    record["unexpected_claims"] <= baseline["unexpected_claims"] and
                    sum(record["scope_issues"].values()) <= sum(baseline["scope_issues"].values())}
        # Preserve the baseline when a new draft offers no measured improvement.
        winner = max(eligible, key=lambda label: (_rank(eligible[label]), label == "approved_baseline"))
        path = directories[winner] / f"{sid}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if winner == "approved_baseline" and not current_approval(sid, doc):
            raise ValueError(f"Approval no longer matches the frozen baseline for {sid}")
        effective_digest = MappingConfig.model_validate(doc["config"]).digest()
        if effective_digest != versions[winner]["config_digest"]:
            raise ValueError(f"{path} changed since the benchmark was written")
        selected[sid] = (winner, doc | {"config_digest": effective_digest})
    return selected


def _replay_source(source, doc, original: Path, output: Path, source_reliability: dict, ingested_at: str) -> dict:
    cfg = MappingConfig.model_validate(doc["config"])
    if cfg.digest() != doc["config_digest"] or source["snapshot"]["sha256"] != doc["snapshot_sha256"]:
        raise ValueError(f"Replay inputs changed for {cfg.source_id}")
    verify_snapshot(source)
    ordinals = {}
    with original.open(encoding="utf-8") as stream:
        for line in stream:
            obs = json.loads(line)
            ordinals[obs["source_row_ordinal"]] = obs["sample_stratum"]
    observations, replayed, missing = 0, 0, []
    engine = Engine(cfg, source, source_reliability, ingested_at=ingested_at)
    output.parent.mkdir(parents=True, exist_ok=True)
    last_row = max(ordinals)
    path = ROOT / source["snapshot"]["path"]
    original_reader = load_config(cfg.source_id)[0].reader
    proposed_rows = iter_records(path, cfg.reader)
    reference_rows = proposed_rows if cfg.reader == original_reader else iter_records(path, original_reader)
    staging = output.with_suffix(".part")
    try:
        with staging.open("w", encoding="utf-8", newline="\n") as stream:
            paired = ((record, record) for record in proposed_rows) if reference_rows is proposed_rows else zip(proposed_rows, reference_rows)
            for ordinal, (record, reference) in enumerate(paired, 1):
                if ordinal in ordinals:
                    if record != reference:
                        raise ValueError(f"Proposed reader changed frozen row {ordinal} of {cfg.source_id}")
                    replayed += 1
                    extracted = engine.process(record)
                    if not extracted:
                        missing.append(ordinal)
                    for obs in extracted:
                        obs.update(sample_stratum=ordinals[ordinal], source_row_ordinal=ordinal)
                        stream.write(json.dumps(obs) + "\n")
                    observations += len(extracted)
                if ordinal >= last_row:
                    break
        if replayed != len(ordinals):
            raise ValueError(f"Replayed {replayed}/{len(ordinals)} source rows for {cfg.source_id}")
        staging.replace(output)
    finally:
        staging.unlink(missing_ok=True)
    return {"rows_replayed": replayed, "canonical_observations": observations, "rows_without_observations": missing,
            "snapshot_sha256": doc["snapshot_sha256"], "config_digest": cfg.digest()}


def run(benchmark_path: Path, output: Path, proposal_dirs: list[Path]) -> dict:
    manifest = load_manifest()
    selected = select(json.loads(benchmark_path.read_text(encoding="utf-8")), proposal_dirs)
    rel = reliability()
    observations = output / "observations"
    mappings = output / "selected-mappings"
    mappings.mkdir(parents=True, exist_ok=True)
    stats = {}
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for sid, (variant, doc) in selected.items():
        result = _replay_source(manifest[sid], doc, OUT_OBS / f"{sid}.jsonl", observations / f"{sid}.jsonl",
                                rel.get(sid, rel["default"]), ingested_at)
        (mappings / f"{sid}.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        stats[sid] = {"variant": variant, "run_id": doc["run_id"], **result}
        print(f"{sid}: replayed {result['rows_replayed']} frozen rows with {variant}", flush=True)
    identity = resolve(EVIDENCE_POLICY, output / "identity", observations=observations)
    profile = profiles(policy=EVIDENCE_POLICY, version=EVIDENCE_PROFILE, output=output / "profiles",
                       evaluation=output / "evaluation", observations=observations)
    result = {"status": "experimental_replay", "mappings": stats, "identity": identity, "profiles": profile}
    (output / "replay.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("proposals", nargs="*", type=Path)
    args = parser.parse_args()
    run(args.benchmark, args.output, args.proposals)
