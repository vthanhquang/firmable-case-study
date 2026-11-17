"""Evidence sheet for the Part-3 precision audit.

The threshold and policy are frozen in resolve.py BEFORE sampling. We draw a seeded random 50 from the
strict-threshold links (and, separately, up to 25 from the looser REVIEW band, reported as exploratory)
and print both records' full canonical views side by side for a reviewer to label CORRECT / INCORRECT /
UNCERTAIN in outputs/evaluation/link_audit_50.csv.
"""
from __future__ import annotations

import csv
import io
import json
import random
from collections import defaultdict

from ..paths import OUT_EVAL, OUT_IDENTITY, OUT_OBS

SEED = 20261109
ACTIVE_AUDIT_CSV = "link_audit_strict_v2_50.csv"
ACTIVE_AUDIT_EVIDENCE = "link_audit_strict_v2_evidence.json"


def _views(observations=None) -> dict:
    v = defaultdict(lambda: defaultdict(list))
    for f in (observations or OUT_OBS).glob("*.jsonl"):
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            if o.get("claim_scope") != "former_legal_name":
                v[f"{o['source_id']}::{o['source_record_id']}"][o["field"]].append(o["value"])
    return v


def build() -> dict:
    views = _views()
    links = [json.loads(l) for l in open(OUT_IDENTITY / "proposed_links.jsonl", encoding="utf-8")]
    decisions = [json.loads(l) for l in open(OUT_IDENTITY / "link_decisions.jsonl", encoding="utf-8")]
    # Looser band: what a lower threshold would start linking. The strict policy has no pairs scored between
    # 0.75 and 0.85, so the next band down is name-only candidates (core-name similarity >= 0.6).
    review = [d for d in decisions if d["decision"] == "REVIEW"
              or (d["decision"] == "ABSTAIN" and d.get("name_sim", 0) >= 0.6)]
    rng = random.Random(SEED)
    strict = rng.sample(links, min(50, len(links)))
    loose = rng.sample(review, min(25, len(review)))
    rows = []
    for band, items in (("strict", strict), ("review_band", loose)):
        for d in items:
            a, b = d.get("source_a_record", d.get("a")), d.get("source_b_record", d.get("b"))
            rows.append({"band": band, "seed": SEED, "a": a, "b": b, "rule": d["rule"],
                         "score": d.get("confidence", d.get("score")),
                         "a_view": {k: v[:3] for k, v in views[a].items()},
                         "b_view": {k: v[:3] for k, v in views[b].items()},
                         "evidence": d["evidence"]})
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_EVAL / "link_audit_evidence.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return {"strict_sampled": len(strict), "strict_population": len(links),
            "review_sampled": len(loose), "review_population": len(review)}


def build_active() -> dict:
    """Draw a fresh review sample after promotion, with random-pair and rule-family coverage."""
    summary = json.loads((OUT_IDENTITY / "summary.json").read_text(encoding="utf-8"))
    if summary["policy_version"] != "strict-v2":
        raise ValueError("Generate the strict-v2 identity outputs before building its audit")
    with (OUT_IDENTITY / "proposed_links.jsonl").open(encoding="utf-8") as fh:
        links = [json.loads(line) for line in fh]
    groups = {"random_pair": [], "cohort_identifier": [], "cohort_name": []}
    for link in links:
        if link["policy_version"] != summary["policy_version"]:
            raise ValueError("Proposed links and matcher summary use different policies")
        group = ("random_pair" if link["strata"] == ["random", "random"] else
                 "cohort_name" if link["rule"].startswith("registered_name") else "cohort_identifier")
        groups[group].append(link)
    seed = SEED + 2
    rng = random.Random(seed)
    sampled = {group: rng.sample(rows, len(rows)) for group, rows in groups.items()}
    limits = {"random_pair": min(10, len(groups["random_pair"]))}
    limits["cohort_identifier"] = min((50 - limits["random_pair"] + 1) // 2, len(groups["cohort_identifier"]))
    limits["cohort_name"] = min(50 - sum(limits.values()), len(groups["cohort_name"]))
    for group, rows in sampled.items():
        limits[group] += min(50 - sum(limits.values()), len(rows) - limits[group])

    views, evidence, labels = _views(), [], []
    for group, rows in sampled.items():
        for link in rows[:limits[group]]:
            a, b = link["source_a_record"], link["source_b_record"]
            record = {"band": "strict", "seed": seed, "rule": link["rule"], "score": link["confidence"],
                      "policy_version": link["policy_version"], "sample_group": group}
            evidence.append(record | {"a": a, "b": b, "strata": link["strata"], "evidence": link["evidence"],
                                      "a_view": dict(views[a]), "b_view": dict(views[b])})
            labels.append(record | {"idx": len(labels), "record_a": a, "record_b": b,
                                    "label": "", "note": "", "reviewer": "", "reviewer_kind": ""})
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO(newline="")
    fields = ["band", "idx", "seed", "policy_version", "sample_group", "record_a", "record_b", "rule", "score",
              "label", "note", "reviewer", "reviewer_kind"]
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(labels)
    path = OUT_EVAL / ACTIVE_AUDIT_CSV
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            if any(row.get("label") for row in csv.DictReader(fh)):
                raise ValueError("The active audit CSV already contains decisions")
    path.write_text(stream.getvalue(), encoding="utf-8", newline="\n")
    (OUT_EVAL / ACTIVE_AUDIT_EVIDENCE).write_text(json.dumps(evidence, indent=1), encoding="utf-8", newline="\n")
    return {"policy_version": summary["policy_version"], "population": {g: len(rows) for g, rows in groups.items()},
            "sample": limits, "labels_recorded": 0}


def score(path=None) -> dict:
    path = path or OUT_EVAL / "link_audit_50.csv"
    with open(path, encoding="utf-8", newline="") as fh:
        return score_rows(csv.DictReader(fh))


def score_rows(rows) -> dict:
    out = {}
    for r in rows:
        b = out.setdefault(r["band"], {"CORRECT": 0, "INCORRECT": 0, "UNCERTAIN": 0, "by_rule": {}})
        if not r["label"]:
            continue
        b[r["label"]] += 1
        br = b["by_rule"].setdefault(r["rule"], {"CORRECT": 0, "INCORRECT": 0, "UNCERTAIN": 0})
        br[r["label"]] += 1
    for band, c in out.items():
        decided = c["CORRECT"] + c["INCORRECT"]
        c["precision_decided"] = round(c["CORRECT"] / decided, 3) if decided else None
        labelled = decided + c["UNCERTAIN"]
        c["precision_all_sampled"] = round(c["CORRECT"] / labelled, 3) if labelled else None
    return out
