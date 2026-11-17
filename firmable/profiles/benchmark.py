"""Check profile provenance and score distributions against the source observations."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from ..identity.benchmark import score_distribution
from ..paths import OUT_OBS, OUT_PROFILES
from .build import EVIDENCE_PROFILE, _agree_key


def _read(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _entries(fields):
    for field, value in fields.items():
        for entry in value if isinstance(value, list) else [value]:
            yield field, entry


def _scope_entries(profile):
    yield from _entries(profile["fields"])
    for location in profile.get("locations", []):
        yield from _entries(location["fields"])
    for event in profile.get("registration_events", []):
        yield "entity.date_registered", event
    for name in profile.get("historical_names", []):
        yield "entity.legal_name", name


def _check(profiles, observations):
    scores = defaultdict(list)
    errors = []
    by_id = {row["observation_id"]: row for file in observations.glob("*.jsonl") for row in _read(file)}
    metrics = {"profiles": len(profiles), "with_conflicts": 0, "core_claims": 0, "scoped_claims": 0,
               "core_mapping_defaults": 0, "profiles_with_locations": 0, "address_components_from_multiple_records": 0,
               "profiles_with_multiple_registration_scopes": 0, "historical_name_claims": 0}
    for profile in profiles:
        entity = profile["entity_key"]
        metrics["with_conflicts"] += bool(profile["conflicts"])
        metrics["profiles_with_locations"] += bool(profile.get("locations"))
        metrics["historical_name_claims"] += len(profile.get("historical_names", []))
        metrics["profiles_with_multiple_registration_scopes"] += len({event["scope"] for event in
                                                                     profile.get("registration_events", [])}) > 1
        core = list(_entries(profile["fields"]))
        address_records = {(entry["provenance"]["source_id"], entry["provenance"]["source_record_id"])
                           for field, entry in core if field.startswith("address.") and
                           entry["provenance"]["derivation_level"] != "L3"}
        metrics["address_components_from_multiple_records"] += len(address_records) > 1
        if profile["profile_version"] == EVIDENCE_PROFILE:
            primary = profile.get("primary_address_record")
            if address_records and {f"{sid}::{rid}" for sid, rid in address_records} != {primary}:
                errors.append({"entity": entity, "field": "address", "reason": "components leave the primary address record"})
            for field, defaults in profile["mapping_defaults"].items():
                for default in defaults:
                    observation = by_id.get(default["observation_id"])
                    if (observation is None or observation["derivation_level"] != "L3" or observation["field"] != field or
                            observation["value"] != default["value"] or observation["source_id"] != default["source_id"]):
                        errors.append({"entity": entity, "field": field, "reason": "mapping default provenance does not match"})
        metrics["core_claims"] += len(core)
        for field, entry in core:
            scores[field].append(entry["value_confidence"])
            if entry["provenance"]["derivation_level"] == "L3":
                metrics["core_mapping_defaults"] += 1
                if profile["profile_version"] == EVIDENCE_PROFILE:
                    errors.append({"entity": entity, "field": field, "reason": "mapping default used as observed field"})
        for field, entry in _scope_entries(profile):
            metrics["scoped_claims"] += 1
            provenance = entry["provenance"]
            observation = by_id.get(provenance["observation_id"])
            if (observation is None or observation["value"] != entry["value"] or observation["field"] != field or
                    any(observation.get(key) != value for key, value in provenance.items())):
                errors.append({"entity": entity, "field": field, "reason": "winning observation does not match provenance"})
            for key in entry["supporting_observations"]:
                supporting = by_id.get(key)
                if (supporting is None or supporting["field"] != field or
                        _agree_key(field, supporting["value"]) != _agree_key(field, entry["value"])):
                    errors.append({"entity": entity, "field": field, "reason": "supporting observation does not match value"})
    metrics["confidence_by_field"] = {field: score_distribution(values) for field, values in sorted(scores.items())}
    metrics["provenance_errors"] = errors
    return metrics


def run(candidate: Path, observations: Path, output: Path) -> dict:
    baseline = _read(OUT_PROFILES / "company_profiles_50.jsonl")
    challenger = _read(candidate)
    report = {"common_profile_keys": len({row["entity_key"] for row in baseline} &
                                         {row["entity_key"] for row in challenger}),
              "baseline": _check(baseline, OUT_OBS), "challenger": _check(challenger, observations)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["challenger"]["provenance_errors"]:
        raise ValueError(f"Profile provenance failures are recorded in {output}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profiles", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--observations", type=Path, default=OUT_OBS)
    args = parser.parse_args()
    result = run(args.profiles, args.observations, args.output)
    print({key: result["challenger"][key] for key in ("profiles", "with_conflicts", "core_claims", "core_mapping_defaults")})
