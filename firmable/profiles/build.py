"""Part 4: company profiles materialised from observations of linked records.

A profile is a VIEW over claims: every field names the observation that won, why it won, and the
values that lost. Nothing is written back into observations. Fields with no claim are absent.

Per-field confidence is shown as its parts (ontology: keep confidence kinds apart) plus one derived
number for convenience:
  value_confidence = field_confidence x source_reliability x link_confidence, then raised by
  independent corroboration: 1 - prod(1 - c_i) over sources that agree with the winner.
The parts are always printed next to it, so a reader can see WHY a value is (un)certain.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

from ..identity.resolve import THRESHOLD, norm_name, resolve
from ..paths import OUT_EVAL, OUT_OBS, OUT_PROFILES

PROFILE_VERSION = "profile-v1"
MULTI_VALUED = {"entity.trading_name"}
SEED = 20261110


def _obs_index(exclude=frozenset()):
    idx = defaultdict(list)
    for f in sorted(OUT_OBS.glob("*.jsonl")):
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            if o["source_id"] not in exclude:
                idx[f"{o['source_id']}::{o['source_record_id']}"].append(o)
    return idx


def _agree_key(field: str, v: str) -> str:
    return norm_name(v) if field in ("entity.legal_name", "entity.trading_name") else str(v).strip().upper()


def _membership_conf(res) -> dict:
    """Link confidence of each record's attachment to its entity: best accepted link touching it."""
    best = {}
    for d in res["decisions"]:
        if d["decision"] == "LINK":
            for k in (d["a"], d["b"]):
                best[k] = max(best.get(k, 0), d["score"])
    return best


def build_profile(ek, members, obs_idx, link_conf) -> dict:
    by_field = defaultdict(list)
    for m in members:
        for o in obs_idx.get(m, []):
            by_field[o["field"]].append(o)
    fields, conflicts = {}, []
    for field, claims in sorted(by_field.items()):
        groups = defaultdict(list)
        for o in claims:
            groups[_agree_key(field, o["value"])].append(o)

        def strength(o):
            c = o["confidence"]
            return (c.get("field_confidence") or 0) * (c.get("source_reliability") or 0.5) * link_conf.get(
                f"{o['source_id']}::{o['source_record_id']}", 1.0)

        def group_rank(item):
            key, obs = item
            srcs = {o["source_id"] for o in obs}
            return (len(srcs), max(strength(o) for o in obs), max(o["observed_at"] or "" for o in obs), key)

        ranked = sorted(groups.items(), key=group_rank, reverse=True)

        def render(key, obs, role):
            win = max(obs, key=lambda o: (strength(o), o["observed_at"] or ""))
            srcs = sorted({o["source_id"] for o in obs})
            p = 1.0
            for s in srcs:
                p *= 1 - max(strength(o) for o in obs if o["source_id"] == s)
            return {"value": win["value"],
                    "value_confidence": round(1 - p, 3),
                    "confidence_parts": {"field_confidence": win["confidence"]["field_confidence"],
                                         "source_reliability": win["confidence"]["source_reliability"],
                                         "link_confidence": link_conf.get(f"{win['source_id']}::{win['source_record_id']}"),
                                         "agreeing_sources": srcs},
                    "provenance": {"observation_id": win["observation_id"], "source_id": win["source_id"],
                                   "source_record_id": win["source_record_id"], "source_fields": win["source_fields"],
                                   "observed_at": win["observed_at"], "derivation_level": win["derivation_level"],
                                   "extractor_version": win["extractor_version"]},
                    "supporting_observations": [o["observation_id"] for o in obs]}

        if field in MULTI_VALUED:
            fields[field] = [render(k, obs, "member") for k, obs in ranked]
            continue
        win_key, win_obs = ranked[0]
        entry = render(win_key, win_obs, "winner")
        # Values that differ only between records of the SAME source (several premises/licences of one business)
        # are variants, not disagreements; a conflict needs another source to say something different.
        win_sources = {o["source_id"] for o in win_obs}
        variants = [(k, obs) for k, obs in ranked[1:] if {o["source_id"] for o in obs} <= win_sources]
        losers = [(k, obs) for k, obs in ranked[1:] if (k, obs) not in variants]
        if variants:
            entry["same_source_variants"] = [{"value": obs[0]["value"], "source_record_ids": sorted(
                {o["source_record_id"] for o in obs}), "note": "another record of the same source (e.g. another premises)"}
                for _, obs in variants]
        if losers:
            reason = ("more independent sources agree" if group_rank(ranked[0])[0] > group_rank(losers[0])[0]
                      else "higher field_confidence x source_reliability x link_confidence"
                      if max(strength(o) for o in win_obs) > max(strength(o) for o in losers[0][1])
                      else "more recent observed_at")
            entry["resolution"] = {"rule": "corroboration > reliability-weighted confidence > recency",
                                   "why_this_won": reason,
                                   "losing_values": [{"value": obs[0]["value"],
                                                      "sources": sorted({o["source_id"] for o in obs}),
                                                      "observation_ids": [o["observation_id"] for o in obs]}
                                                     for _, obs in losers]}
            conflicts.append({"field": field, "winner": entry["value"],
                              "losers": [obs[0]["value"] for _, obs in losers]})
        fields[field] = entry
    return {"entity_key": ek, "profile_version": PROFILE_VERSION,
            "member_records": sorted(members),
            "sources": sorted({m.split("::")[0] for m in members}),
            "fields": fields, "conflicts": conflicts}


def materialise_with_policy(policy: str) -> dict:
    return materialise(policy=policy)[0]


def materialise(exclude=frozenset(), policy: str | None = None) -> tuple[dict, dict]:
    """Profiles of every multi-source entity, plus the resolution (and a builder for any entity)."""
    res = resolve(exclude, policy=policy) if policy else resolve(exclude)
    obs_idx = _obs_index(exclude)
    link_conf = _membership_conf(res)
    ents = defaultdict(list)
    for k, e in res["key_of"].items():
        ents[e].append(k)
    res["build"] = lambda e: build_profile(e, ents[e], obs_idx, link_conf)
    multi = {e: m for e, m in ents.items() if len({x.split("::")[0] for x in m}) > 1}
    return {e: build_profile(e, m, obs_idx, link_conf) for e, m in multi.items()}, res


def _fingerprint(p: dict) -> dict:
    out = {}
    for f, v in p["fields"].items():
        out[f] = sorted(x["value"] for x in v) if isinstance(v, list) else v["value"]
    return out


def run(count: int = 50) -> dict:
    profiles, res = materialise()
    eligible = sorted(profiles)
    chosen = sorted(random.Random(SEED).sample(eligible, min(count, len(eligible))))
    OUT_PROFILES.mkdir(parents=True, exist_ok=True)
    with open(OUT_PROFILES / "company_profiles_50.jsonl", "w", encoding="utf-8") as fh:
        for e in chosen:
            fh.write(json.dumps(profiles[e]) + "\n")

    # Counterfactual: delete each source in turn, re-resolve and re-materialise. Each chosen profile is
    # compared with the profile rebuilt from its SURVIVING records (identity can change, not just fields).
    from ..sources.select import CHOICES
    impact = {}
    base = {e: _fingerprint(profiles[e]) for e in chosen}
    total_fields = sum(len(base[e]) for e in chosen)
    for s in sorted(c[0] for c in CHOICES):
        alt, alt_res = materialise(exclude={s})
        stats = {"profiles_affected": 0, "profiles_unchanged": 0, "no_longer_multi_source": 0,
                 "fields_removed": 0, "fields_value_changed": 0, "fields_unchanged": 0, "examples": []}
        for e in chosen:
            survivors = [m for m in profiles[e]["member_records"] if not m.startswith(s + "::")]
            alt_key = alt_res["key_of"][survivors[0]]
            alt_p = alt.get(alt_key) or alt_res["build"](alt_key)
            fa, fb = base[e], _fingerprint(alt_p)
            rm = [f for f in fa if f not in fb]
            ch = [f for f in fa if f in fb and fa[f] != fb[f]]
            stats["fields_removed"] += len(rm)
            stats["fields_value_changed"] += len(ch)
            stats["fields_unchanged"] += len(fa) - len(rm) - len(ch)
            if len(alt_p["sources"]) < 2:
                stats["no_longer_multi_source"] += 1
            if rm or ch or len(alt_p["sources"]) < 2:
                stats["profiles_affected"] += 1
                if len(stats["examples"]) < 3 and (rm or ch):
                    stats["examples"].append({"entity_key": e, "removed": rm,
                                              "changed": {f: [fa[f], fb[f]] for f in ch}})
            else:
                stats["profiles_unchanged"] += 1
        stats["share_of_fields_lost_or_changed"] = round(
            (stats["fields_removed"] + stats["fields_value_changed"]) / max(total_fields, 1), 3)
        impact[s] = stats
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_EVAL / "source_deletion_impact.json").write_text(json.dumps(impact, indent=2), encoding="utf-8")
    n_conf = sum(1 for e in chosen if profiles[e]["conflicts"])
    return {"multi_source_entities": len(profiles), "profiles_written": len(chosen),
            "profiles_with_conflicts": n_conf, "link_threshold": THRESHOLD, "deletion_impact": {
                s: {k: v for k, v in d.items() if k != "examples"} for s, d in impact.items()}}
