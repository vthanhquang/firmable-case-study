"""Build and score a fresh random proxy audit of the evidence-ranked shortlist."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

SEED = 20261112
LABELS = {"KEEP": "YES", "EXCLUDE": "NO", "REVIEW": "UNCERTAIN"}


def prepare(discovery: Path, audit: Path) -> Path:
    shortlist = [json.loads(line) for line in (discovery / "shortlist.jsonl").read_text(encoding="utf-8").splitlines()]
    evidence = {row["dataset_id"]: row for row in json.loads((discovery / "review-input.json").read_text(encoding="utf-8"))}
    if len(shortlist) != 50:
        raise ValueError("The discovery shortlist must contain 50 candidates before drawing the audit")
    rows = sorted(random.Random(SEED).sample(shortlist, 20), key=lambda row: row["rank"])
    cases = [evidence[row["dataset_id"]] | {"rank": row["rank"]} for row in rows]
    audit.mkdir(parents=True, exist_ok=True)
    path = audit / "evidence.json"
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def complete(discovery: Path, audit: Path) -> dict:
    shortlist_path = discovery / "shortlist.jsonl"
    shortlist = {row["dataset_id"]: row for line in shortlist_path.read_text(encoding="utf-8").splitlines()
                 if (row := json.loads(line))}
    case_path = audit / "evidence.json"
    sampled = json.loads(case_path.read_text(encoding="utf-8"))
    run = audit / "run"
    source = json.loads((run / "input.json").read_text(encoding="utf-8"))
    if hashlib.sha256(case_path.read_bytes()).hexdigest() != source["evidence_sha256"]:
        raise ValueError("Audit evidence changed during the review")
    decisions = {row["dataset_id"]: row for line in (run / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
                 if (row := json.loads(line))}
    if len(sampled) != 20 or set(decisions) != {row["dataset_id"] for row in sampled}:
        raise ValueError("The fresh audit is incomplete")
    audit_path = audit / "audit_20.csv"
    if audit_path.exists():
        with audit_path.open(encoding="utf-8", newline="") as stream:
            if any(row.get("human_label") or row.get("human_note") for row in csv.DictReader(stream)):
                raise ValueError("This audit CSV contains human review work")
    rows = []
    for case in sampled:
        row, decision = shortlist[case["dataset_id"]], decisions[case["dataset_id"]]
        if row["rank"] != case["rank"]:
            raise ValueError("The shortlist ranking changed after sampling")
        rows.append({"seed": SEED, "rank": row["rank"], "dataset_id": row["dataset_id"], "title": row["title"],
                     "proxy_label": LABELS[decision["decision"]], "proxy_reviewer": source["model"],
                     "evidence_url": row["evidence"]["url"], "proxy_reason": decision["reason"],
                     "human_label": "", "human_note": ""})
    with audit_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["proxy_label"] for row in rows)
    result = {"seed": SEED, "reviewer_kind": "ai_proxy", "model": source["model"], "sampled": len(rows),
              "shortlist_sha256": hashlib.sha256(shortlist_path.read_bytes()).hexdigest(),
              "yes": counts["YES"], "no": counts["NO"], "uncertain": counts["UNCERTAIN"],
              "confirmed_positive_share": counts["YES"] / len(rows), "false_positive_share": counts["NO"] / len(rows),
              "human_verdicts": 0}
    (audit / "metrics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def carry_forward(discovery: Path, audit: Path, previous: Path) -> dict:
    """Rebind a direct resource audit after an order-only change."""
    def read_shortlist(path):
        body = (path / "shortlist.jsonl").read_bytes()
        rows = [json.loads(line) for line in body.decode("utf-8").splitlines() if line]
        if len(rows) != 50 or len({row["dataset_id"] for row in rows}) != 50:
            raise ValueError("An order-only audit replay requires two complete shortlists")
        return {row["dataset_id"]: row for row in rows}, hashlib.sha256(body).hexdigest()

    original, original_sha = read_shortlist(previous)
    current, current_sha = read_shortlist(discovery)
    if original.keys() != current.keys() or any(
        current[key]["evidence"] != row["evidence"] for key, row in original.items()
    ):
        raise ValueError("Shortlist membership or publisher evidence changed. Draw a fresh audit.")

    prior_audit = previous / "audit"
    metrics = json.loads((prior_audit / "metrics.json").read_text(encoding="utf-8"))
    sample = json.loads((prior_audit / "sample.json").read_text(encoding="utf-8"))
    if metrics["shortlist_sha256"] != original_sha or sample["shortlist_sha256"] != original_sha:
        raise ValueError("The prior audit does not identify the original shortlist")
    with (prior_audit / "audit_20.csv").open(encoding="utf-8-sig", newline="") as stream:
        verdicts = list(csv.DictReader(stream))
    by_id = {row["dataset_id"]: row for row in verdicts}
    if len(verdicts) != metrics["sampled"] or len(by_id) != len(verdicts) or by_id.keys() != {
        row["dataset_id"] for row in sample["sample"]
    } or Counter(row["label"].lower() for row in verdicts) != {
        key: metrics[key] for key in ("yes", "no", "uncertain") if metrics[key]
    }:
        raise ValueError("The saved sample and verdicts do not agree")

    def rebind(case):
        key = case["dataset_id"]
        row = original[key]
        if int(case["rank"]) != row["rank"] or case["resource_id"] != row["evidence"]["resource_id"]:
            raise ValueError(f"Audit case {key} does not match the original evidence")
        return case | {"rank": current[key]["rank"], "original_rank": row["rank"]}

    result = metrics | {"shortlist_sha256": current_sha, "carried_forward_from_sha256": original_sha,
                        "unchanged_dataset_resource_population": len(current)}
    sample = sample | {"shortlist_sha256": current_sha, "carried_forward_from_sha256": original_sha,
                       "sample": sorted(map(rebind, sample["sample"]), key=lambda row: row["rank"])}
    verdicts = [
        rebind(row) | {"ranking_points": current[row["dataset_id"]]["score_components"]["ranking_points"]}
        for row in verdicts
    ]
    verdicts.sort(key=lambda row: row["rank"])
    audit.mkdir(parents=True, exist_ok=True)
    path = audit / "audit_20.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as stream:
            if any(row.get("human_label") or row.get("human_note") for row in csv.DictReader(stream)):
                raise ValueError("The target audit already contains human review work")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(verdicts[0]))
        writer.writeheader()
        writer.writerows(verdicts)
    (audit / "sample.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audit / "metrics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "complete", "carry-forward"))
    parser.add_argument("discovery", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--previous", type=Path, help="previous shortlist and direct resource audit")
    args = parser.parse_args()
    if args.action == "prepare":
        print(prepare(args.discovery, args.audit))
    elif args.action == "complete":
        print(json.dumps(complete(args.discovery, args.audit), indent=2))
    else:
        if not args.previous:
            parser.error("carry-forward requires --previous")
        print(json.dumps(carry_forward(args.discovery, args.audit, args.previous), indent=2))
