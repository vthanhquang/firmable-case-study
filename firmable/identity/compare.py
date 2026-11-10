"""Shadow-run a challenger matching policy against the active one and diff the outcome.

This is the Part-5 "change" procedure in miniature: nothing is overwritten. We compare pair decisions
and cluster memberships, list exactly which links/clusters would change, and which canonical entity
keys would split, so only the CHANGED decisions need a human check before promotion.
"""
from __future__ import annotations

import json
from collections import defaultdict

from ..paths import OUT_EVAL
from .resolve import POLICY_VERSION, resolve


def _clusters(res) -> dict:
    out = defaultdict(set)
    for k, e in res["key_of"].items():
        out[e].add(k)
    return {e: m for e, m in out.items() if len(m) > 1}


def run(challenger: str = "strict-v2") -> dict:
    base, chal = resolve(policy=POLICY_VERSION), resolve(policy=challenger)
    db = {(d["a"], d["b"]): d for d in base["decisions"]}
    dc = {(d["a"], d["b"]): d for d in chal["decisions"]}
    changed = []
    for k in sorted(set(db) | set(dc)):
        x, y = db.get(k), dc.get(k)
        if (x or {}).get("decision") != (y or {}).get("decision"):
            changed.append({"a": k[0], "b": k[1],
                            "active": {"decision": x and x["decision"], "rule": x and x["rule"], "score": x and x["score"]},
                            "challenger": {"decision": y and y["decision"], "rule": y and y["rule"], "score": y and y["score"]}})
    cb, cc = _clusters(base), _clusters(chal)
    member_b = {m: e for e, ms in cb.items() for m in ms}
    member_c = {m: e for e, ms in cc.items() for m in ms}
    split = []
    for e, ms in cb.items():
        now = {member_c.get(m) for m in ms}
        if len(now) > 1 or None in now:
            split.append({"entity_key": e, "members_before": sorted(ms),
                          "after": {str(k): sorted(m for m in ms if member_c.get(m) == k) for k in now}})
    merged = [e for e, ms in cc.items() if len({member_b.get(m) for m in ms}) > 1]
    # Blast radius of promotion: which entity profiles would actually change? (reverse index entity -> decisions)
    from ..profiles.build import _fingerprint, materialise_with_policy
    pa, pb = materialise_with_policy(POLICY_VERSION), materialise_with_policy(challenger)
    member_to_new = {m: e for e, p in pb.items() for m in p["member_records"]}
    profile_changes = 0
    for e, p in pa.items():
        targets = {member_to_new.get(m) for m in p["member_records"]}
        if len(targets) != 1 or None in targets or _fingerprint(pb[targets.pop()]) != _fingerprint(p):
            profile_changes += 1
    out = {"active_policy": POLICY_VERSION, "challenger_policy": challenger,
           "multi_source_profiles_active": len(pa), "multi_source_profiles_challenger": len(pb),
           "profiles_to_recompute_on_promotion": profile_changes,
           "pairs_compared": len(set(db) | set(dc)), "decisions_changed": len(changed),
           "links_active": sum(d["decision"] == "LINK" for d in base["decisions"]),
           "links_challenger": sum(d["decision"] == "LINK" for d in chal["decisions"]),
           "clusters_split_or_shrunk": len(split), "clusters_newly_merged": len(merged),
           "entity_keys_kept": len(set(cb) & set(cc)),
           "changed_decisions": changed, "split_clusters": split}
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_EVAL / f"matcher_{POLICY_VERSION}_vs_{challenger}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return {k: v for k, v in out.items() if k not in ("changed_decisions", "split_clusters")}
