"""Compare matcher scores, frozen audit decisions, and an identifier-masking stress test."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ..paths import OUT_EVAL, OUT_IDENTITY, OUT_OBS
from .resolve import EVIDENCE_POLICY, THRESHOLD, evidence, is_registered_company_name, name_sim, resolve


def score_distribution(values) -> dict:
    counts = Counter(values)
    largest = max(counts.values(), default=0)
    return {"count": counts.total(), "distinct_scores": len(counts), "largest_tie": largest,
            "range": [min(counts), max(counts)] if counts else None}


def _pairs(result):
    return {(row["a"], row["b"]): row for row in result["decisions"]}


def _audit(result) -> dict:
    pairs = _pairs(result)
    scored = defaultdict(Counter)
    with (OUT_EVAL / "link_audit_50.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = tuple(sorted((row["record_a"], row["record_b"])))
            if row["label"] in {"CORRECT", "INCORRECT"}:
                decision = pairs.get(key, {}).get("decision", "NOT_GENERATED")
                scored[row["band"]][f"{row['label']}_{decision}"] += 1
    return dict(scored)


def _auc(scored):
    counts = defaultdict(Counter)
    for score, label in scored:
        counts[score][label] += 1
    negatives, credit = 0, 0.0
    for _, group in sorted(counts.items()):
        credit += group[1] * (negatives + 0.5 * group[0])
        negatives += group[0]
    positives = sum(group[1] for group in counts.values())
    return round(credit / (positives * negatives), 4) if positives and negatives else None


def _mask_stress(baseline, challenger) -> dict:
    n, counts = challenger["score_reference"]
    masked = {}
    for key, row in baseline["recs"].items():
        masked[key] = row | {"abn": set(), "acn": set()}
    results = defaultdict(list)
    for row in baseline["decisions"]:
        same = row["rule"] == "abn_equal" and row["decision"] == "LINK"
        different = bool(row["contradictions"])
        if not (same or different):
            continue
        # The stress sample is selected independently of challenger scores.
        key = f"mask-v1|{row['a']}|{row['b']}"
        if hashlib.sha256(key.encode()).digest()[0] % 3 != 0:
            continue
        for policy in ("strict-v2", EVIDENCE_POLICY):
            score, _, _, _ = evidence(masked[row["a"]], masked[row["b"]], policy,
                                       token_counts=counts, record_count=n)
            results[policy].append((score, int(same)))
    return {policy: {"proxy_positive_pairs": sum(label for _, label in rows),
                     "proxy_negative_pairs": sum(not label for _, label in rows),
                     "positives_at_strict_threshold": sum(label and score >= THRESHOLD for score, label in rows),
                     "negatives_at_strict_threshold": sum(not label and score >= THRESHOLD for score, label in rows),
                     "ranking_auc": _auc(rows)} for policy, rows in results.items()}


def _licence_stress(baseline, challenger) -> dict:
    recs = baseline["recs"]
    n, counts = challenger["score_reference"]
    company_names = sorted({name for record in recs.values() if record["grain"] == "licence_or_permit"
                            for name in record["legal"] if is_registered_company_name(name)})
    results = Counter()
    for row in baseline["decisions"]:
        if row["decision"] != "LINK" or row["rule"] != "abn_equal":
            continue
        a, b = recs[row["a"]], recs[row["b"]]
        if (a["grain"] == "licence_or_permit") == (b["grain"] == "licence_or_permit"):
            continue
        licence, other = (a, b) if a["grain"] == "licence_or_permit" else (b, a)
        if not other["legal"] or not all(is_registered_company_name(name) for name in other["legal"]):
            continue
        unrelated = next((name for name in company_names if max(name_sim(name, current) for current in other["legal"]) < 0.45), None)
        if unrelated is None:
            continue
        changed = licence | {"names": {unrelated}, "legal": {unrelated}}
        results["synthetic_cases"] += 1
        for policy in ("strict-v2", EVIDENCE_POLICY):
            score, _, _, _ = evidence(changed, other, policy, token_counts=counts, record_count=n)
            results[f"{policy}_above_link_threshold"] += score >= THRESHOLD
    return dict(results)


def _ordinal_links(identity: Path, observations: Path) -> dict:
    ordinals = {}
    for path in observations.glob("*.jsonl"):
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                claim = json.loads(line)
                ordinals[f"{claim['source_id']}::{claim['source_record_id']}"] = (claim["source_id"], claim["source_row_ordinal"])
    with (identity / "proposed_links.jsonl").open(encoding="utf-8") as stream:
        links = [json.loads(line) for line in stream]
    return {tuple(sorted((ordinals[row["source_a_record"]], ordinals[row["source_b_record"]]))): row for row in links}


def _replay_delta(shadow: Path) -> dict:
    baseline = _ordinal_links(OUT_IDENTITY, OUT_OBS)
    final = _ordinal_links(shadow / "identity", shadow / "observations")
    return {"baseline_links": len(baseline), "replay_links": len(final), "same_frozen_row_pairs": len(baseline.keys() & final.keys()),
            "removed_pairs": sorted(baseline.keys() - final.keys()), "new_pairs": sorted(final.keys() - baseline.keys()),
            "replay_score_distribution": score_distribution(row["confidence"] for row in final.values()),
            "displayed_score_distribution": score_distribution(round(row["confidence"], 3) for row in final.values())}


def run(output: Path, *, shadow: Path | None = None) -> dict:
    baseline, challenger = resolve(policy="strict-v2"), resolve(policy=EVIDENCE_POLICY)
    pa, pb = _pairs(baseline), _pairs(challenger)
    changes = [{"record_a": a, "record_b": b, "baseline": pa.get((a, b), {}).get("decision"),
                "challenger": pb.get((a, b), {}).get("decision")}
               for a, b in sorted(pa.keys() | pb.keys())
               if pa.get((a, b), {}).get("decision") != pb.get((a, b), {}).get("decision")]
    metrics = {"threshold": THRESHOLD, "paired_candidates": len(pa.keys() & pb.keys()),
               "changed_pair_decisions": changes, "membership_identical": baseline["key_of"] == challenger["key_of"],
               "matched_score_summary": {policy: score_distribution(row["score"] for row in result["decisions"]
                                                                    if row["decision"] == "LINK")
                                         for policy, result in (("strict-v2", baseline), (EVIDENCE_POLICY, challenger))},
               "historical_ai_proxy_audit": {"strict-v2": _audit(baseline), EVIDENCE_POLICY: _audit(challenger)},
               "identifier_masking_stress_test": _mask_stress(baseline, challenger),
               "synthetic_incorrect_licence_identifier_stress_test": _licence_stress(baseline, challenger)}
    if shadow:
        metrics["paired_mapping_replay"] = _replay_delta(shadow)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--shadow", type=Path, help="compare the experimental mapping replay by frozen source row ordinals")
    args = parser.parse_args()
    print(json.dumps(run(args.output, shadow=args.shadow), indent=2))
