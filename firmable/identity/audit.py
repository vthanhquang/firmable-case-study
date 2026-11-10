"""Evidence sheet for the Part-3 precision audit.

The threshold and policy are frozen in resolve.py BEFORE sampling. We draw a seeded random 50 from the
strict-threshold links (and, separately, up to 25 from the looser REVIEW band, reported as exploratory)
and print both records' full canonical views side by side for a reviewer to label CORRECT / INCORRECT /
UNCERTAIN in outputs/evaluation/link_audit_50.csv.
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict

from ..paths import OUT_EVAL, OUT_IDENTITY, OUT_OBS

SEED = 20261109


def _views() -> dict:
    v = defaultdict(lambda: defaultdict(list))
    for f in OUT_OBS.glob("*.jsonl"):
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
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


def score(path=None) -> dict:
    path = path or OUT_EVAL / "link_audit_50.csv"
    out = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            b = out.setdefault(r["band"], {"CORRECT": 0, "INCORRECT": 0, "UNCERTAIN": 0, "by_rule": {}})
            b[r["label"]] += 1
            br = b["by_rule"].setdefault(r["rule"], {"CORRECT": 0, "INCORRECT": 0, "UNCERTAIN": 0})
            br[r["label"]] += 1
    for band, c in out.items():
        decided = c["CORRECT"] + c["INCORRECT"]
        c["precision_decided"] = round(c["CORRECT"] / decided, 3) if decided else None
        c["precision_all_sampled"] = round(c["CORRECT"] / max(sum(c[k] for k in ("CORRECT", "INCORRECT", "UNCERTAIN")), 1), 3)
    return out
