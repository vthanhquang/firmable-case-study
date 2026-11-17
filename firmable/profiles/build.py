"""Part 4: company profiles materialised from observations of linked records.

A profile is a VIEW over claims: every field names the observation that won, why it won, and the
values that lost. Nothing is written back into observations. Fields with no claim are absent.

Per-field confidence exposes the mapping, source reliability and link components. Profile-v1
combines agreeing sources with a noisy-or formula. Profile-v2 limits corroboration, discounts
competing evidence, and uses the strongest path to an identifier-bearing cluster anchor. It keeps
registration, location and historical name claims scoped to the records that describe them.
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from datetime import date, timedelta
from hashlib import sha256
from heapq import heappop, heappush
from math import prod

from ..identity.resolve import THRESHOLD, name_sim, norm_name, resolve
from ..paths import OUT_EVAL, OUT_OBS, OUT_PROFILES

PROFILE_VERSION = "profile-v1"
EVIDENCE_PROFILE = "profile-v2"
PROFILE_VERSIONS = (PROFILE_VERSION, EVIDENCE_PROFILE)
MULTI_VALUED = {"entity.trading_name"}
REGISTRATION_ROLES = {"asic_companies": "company_registration", "acnc_charities": "charity_registration"}
ADDRESS_ROLES = {"acnc_charities": "entity_contact_address", "qbcc_licensees": "licence_holder_address",
                 "vic_liquor": "licensed_premises", "dewr_employment_providers": "establishment_address"}
SEED = 20261110


def _obs_index(exclude=frozenset(), *, observations=None):
    idx = defaultdict(list)
    for f in sorted((observations or OUT_OBS).glob("*.jsonl")):
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            if o["source_id"] not in exclude:
                idx[f"{o['source_id']}::{o['source_record_id']}"].append(o)
    return idx


def _agree_key(field: str, v: str) -> str:
    return norm_name(v) if field in ("entity.legal_name", "entity.trading_name") else str(v).strip().upper()


def _membership_conf(res, *, path_aware=False) -> dict:
    """Use the widest path to an identifier-bearing anchor when scoring transitive membership."""
    best, graph = {}, defaultdict(list)
    for d in res["decisions"]:
        if d["decision"] == "LINK":
            for k in (d["a"], d["b"]):
                best[k] = max(best.get(k, 0), d["score"])
            if path_aware:
                graph[d["a"]].append((d["b"], d["score"]))
                graph[d["b"]].append((d["a"], d["score"]))
    if not path_aware:
        return best
    paths = {}

    def priority(key):
        record = res["recs"][key]
        quality = record.get("claim_quality", {})
        return (bool(record["abn"]), bool(record["acn"]),
                max((value for (field, _), value in quality.items() if field in {"entity.abn", "entity.acn"}), default=0),
                best[key], key)

    for members in res["clusters"].values():
        if len(members) < 2:
            continue
        anchor = max(members, key=priority)
        paths[anchor] = best[anchor]
        queue = [(-best[anchor], anchor)]
        while queue:
            neg_score, key = heappop(queue)
            if -neg_score < paths[key]:
                continue
            for neighbor, link in graph[key]:
                score = min(-neg_score, link)
                if score > paths.get(neighbor, 0):
                    paths[neighbor] = score
                    heappush(queue, (-score, neighbor))
    return paths


def _source_strengths(claims, strength):
    by_source = {}
    for claim in claims:
        source = claim["source_id"]
        by_source[source] = max(strength(claim), by_source.get(source, 0))
    return by_source


def _corroborated_strength(weights):
    strongest, *others = sorted(weights, reverse=True)
    # Publishers can reuse the same registers. Bound corroboration instead of
    # treating every agreement as an independent probability estimate.
    return strongest + 0.35 * (1 - strongest) * (1 - prod(1 - value for value in others))


def _render_claim(claims, strength, link_conf, *, evidence_aware=False, alternative=0.0):
    win = max(claims, key=lambda claim: (strength(claim), claim["observed_at"] or ""))
    weights = _source_strengths(claims, strength)
    parts = {"field_confidence": win["confidence"]["field_confidence"],
             "source_reliability": win["confidence"]["source_reliability"],
             "link_confidence": link_conf.get(f"{win['source_id']}::{win['source_record_id']}"),
             "agreeing_sources": sorted(weights)}
    if evidence_aware:
        support = _corroborated_strength(weights.values())
        confidence = round(support * (1 - 0.35 * alternative), 4)
        parts.update({"support_by_source": {source: round(value, 4) for source, value in sorted(weights.items())},
                      "strongest_competing_support": round(alternative, 4)})
    else:
        confidence = round(1 - prod(1 - weights[source] for source in sorted(weights)), 3)
    provenance = {key: win[key] for key in ("observation_id", "source_id", "source_record_id", "source_fields",
                                           "observed_at", "derivation_level", "extractor_version")}
    if evidence_aware:
        provenance.update({key: win[key] for key in ("claim_scope", "valid_from", "valid_to") if win.get(key)})
    return {"value": win["value"], "value_confidence": confidence, "confidence_parts": parts, "provenance": provenance,
            "supporting_observations": [claim["observation_id"] for claim in claims]}


def build_profile(ek, members, obs_idx, link_conf, version=PROFILE_VERSION) -> dict:
    if version not in PROFILE_VERSIONS:
        raise ValueError(f"Unknown profile policy {version!r}")
    evidence_aware = version == EVIDENCE_PROFILE
    by_field = defaultdict(list)
    defaults, registration_claims, historical_names = defaultdict(list), defaultdict(list), defaultdict(list)
    address_claims = defaultdict(lambda: defaultdict(list))
    for m in members:
        for o in obs_idx.get(m, []):
            field = o["field"]
            scope = o.get("claim_scope")
            if evidence_aware and o["derivation_level"] == "L3":
                defaults[field].append(o)
            elif evidence_aware and scope == "former_legal_name":
                historical_names[(o["source_id"], _agree_key(field, o["value"]))].append(o)
            elif evidence_aware and field.startswith("address."):
                address_scope = scope or ADDRESS_ROLES.get(o["source_id"], "unscoped_address")
                address_claims[m, address_scope][field].append(o)
            elif evidence_aware and field == "entity.date_registered":
                role = scope or REGISTRATION_ROLES.get(o["source_id"], "source_registration")
                registration_claims[(role, o["source_id"], o["value"])].append(o)
                if role == "company_registration":
                    by_field[field].append(o)
            elif evidence_aware and field in {"entity.status", "entity.entity_type"} and o["value"] == "unknown":
                continue
            else:
                by_field[field].append(o)

    def strength(o):
        c = o["confidence"]
        reliability = c.get("source_reliability")
        reliability = (0.5 if reliability is None else reliability) if evidence_aware else reliability or 0.5
        return (c.get("field_confidence") or 0) * reliability * link_conf.get(
            f"{o['source_id']}::{o['source_record_id']}", 1.0)

    fields, conflicts = {}, []
    for field, claims in sorted(by_field.items()):
        groups = defaultdict(list)
        for o in claims:
            groups[_agree_key(field, o["value"])].append(o)

        def group_rank(item):
            key, obs = item
            weights = _source_strengths(obs, strength)
            primary = _corroborated_strength(weights.values()) if evidence_aware else len(weights)
            return (primary, max(weights.values()), max(o["observed_at"] or "" for o in obs), key)

        ranked = sorted(groups.items(), key=group_rank, reverse=True)

        if field in MULTI_VALUED:
            fields[field] = [_render_claim(obs, strength, link_conf, evidence_aware=evidence_aware) for _, obs in ranked]
            continue
        _, win_obs = ranked[0]
        # Values that differ only between records of the SAME source (several premises/licences of one business)
        # are variants, not disagreements; a conflict needs another source to say something different.
        win_sources = {o["source_id"] for o in win_obs}
        variants = [(k, obs) for k, obs in ranked[1:] if {o["source_id"] for o in obs} <= win_sources]
        losers = [(k, obs) for k, obs in ranked[1:] if (k, obs) not in variants]
        alternative = group_rank(losers[0])[0] if evidence_aware and losers else 0
        entry = _render_claim(win_obs, strength, link_conf, evidence_aware=evidence_aware, alternative=alternative)
        if variants:
            entry["same_source_variants"] = [{"value": obs[0]["value"], "source_record_ids": sorted(
                {o["source_record_id"] for o in obs}), "note": "another record of the same source (e.g. another premises)"}
                for _, obs in variants]
        if losers:
            reason = ("more independent sources agree" if group_rank(ranked[0])[0] > group_rank(losers[0])[0]
                      else "higher field_confidence x source_reliability x link_confidence"
                      if max(strength(o) for o in win_obs) > max(strength(o) for o in losers[0][1])
                      else "more recent observed_at")
            rule = "corroboration > reliability-weighted confidence > recency"
            if evidence_aware:
                rule = "weighted source evidence with bounded corroboration, then recency"
                reason = ("stronger reliability-weighted evidence" if group_rank(ranked[0])[0] > alternative
                          else "observed time and stable tie-break")
            entry["resolution"] = {"rule": rule, "why_this_won": reason,
                                   "losing_values": [{"value": obs[0]["value"],
                                                      "sources": sorted({o["source_id"] for o in obs}),
                                                      "observation_ids": [o["observation_id"] for o in obs]}
                                                     for _, obs in losers]}
            if (evidence_aware and alternative >= 0.55 and field == "entity.legal_name" and
                    name_sim(norm_name(entry["value"]), norm_name(losers[0][1][0]["value"])) < 0.72):
                # Different legal parties may have been joined through a bad
                # source assertion. Keep the provisional winner for inspection.
                entry["resolution"]["decision"] = "review_required"
                entry["value_confidence"] = min(entry["value_confidence"], 0.55)
            conflicts.append({"field": field, "winner": entry["value"],
                              "losers": [obs[0]["value"] for _, obs in losers]})
        fields[field] = entry
    profile = {"entity_key": ek, "profile_version": version, "member_records": sorted(members),
               "sources": sorted({m.split("::")[0] for m in members}), "fields": fields, "conflicts": conflicts}
    if evidence_aware:
        locations = []
        for (member, scope), claims in sorted(address_claims.items()):
            entries = {}
            for field, observations in sorted(claims.items()):
                winner = max(observations, key=strength)
                agreeing = [claim for claim in observations if _agree_key(field, claim["value"]) ==
                            _agree_key(field, winner["value"])]
                entries[field] = _render_claim(agreeing, strength, link_conf, evidence_aware=True)
            grain = next(iter(claims.values()))[0].get("record_grain")
            locations.append({"source_record": member, "scope": scope, "record_grain": grain, "fields": entries})
        entity_locations = [location for location in locations if location["scope"] in {"registered_office", "entity_contact_address"}
                            or (location["scope"] == "unscoped_address" and location["record_grain"] == "legal_entity")]
        if entity_locations:
            primary = max(entity_locations, key=lambda location: (
                "address.full" in location["fields"], location["scope"] == "registered_office", len(location["fields"]),
                sum(field["value_confidence"] for field in location["fields"].values()), location["source_record"],
            ))
            fields.update(primary["fields"])
            profile["primary_address_record"] = primary["source_record"]
            profile["address_resolution"] = {
                "scope": primary["scope"], "source_record": primary["source_record"],
                "reason": "selected one entity address record by street coverage, address scope and field evidence",
                "alternative_records": [location["source_record"] for location in entity_locations if location is not primary],
            }
        profile["locations"] = locations
        profile["registration_events"] = [
            {"scope": scope, **_render_claim(claims, strength, link_conf, evidence_aware=True)}
            for (scope, _, _), claims in sorted(registration_claims.items())
        ]
        profile["historical_names"] = [_render_claim(claims, strength, link_conf, evidence_aware=True)
                                       for _, claims in sorted(historical_names.items())]
        profile["mapping_defaults"] = {
            field: [{"value": claim["value"], "source_id": claim["source_id"], "observation_id": claim["observation_id"]}
                    for claim in claims] for field, claims in sorted(defaults.items())
        }
    return profile


def materialise_with_policy(policy: str) -> dict:
    return materialise(policy=policy)[0]


def materialise(exclude=frozenset(), policy: str | None = None, version=PROFILE_VERSION,
                *, score_reference=None, observations=None) -> tuple[dict, dict]:
    """Profiles of every multi-source entity, plus the resolution (and a builder for any entity)."""
    options = {"policy": policy} if policy else {}
    if score_reference is not None:
        options["score_reference"] = score_reference
    if observations is not None:
        options["observations"] = observations
    res = resolve(exclude, **options)
    obs_idx = _obs_index(exclude, observations=observations) if observations is not None else _obs_index(exclude)
    link_conf = _membership_conf(res, path_aware=version == EVIDENCE_PROFILE)
    ents = defaultdict(list)
    for k, e in res["key_of"].items():
        ents[e].append(k)
    res["build"] = lambda e: build_profile(e, ents[e], obs_idx, link_conf, version)
    multi = {e: m for e, m in ents.items() if len({x.split("::")[0] for x in m}) > 1}
    return {e: build_profile(e, m, obs_idx, link_conf, version) for e, m in multi.items()}, res


def _fingerprint(p: dict) -> dict:
    out = {}
    for f, v in p["fields"].items():
        out[f] = sorted(x["value"] for x in v) if isinstance(v, list) else v["value"]
    return out


def _field_changes(before: dict, after: dict) -> dict[str, list[str]]:
    left, right = before["fields"], after["fields"]
    changes = {"removed": sorted(left.keys() - right.keys()), "added": sorted(right.keys() - left.keys()),
               "value": [], "confidence": [], "provenance": []}

    def entries(field, value):
        items = value if isinstance(value, list) else [value]
        return sorted(items, key=lambda x: _agree_key(field, x["value"]))

    for field in sorted(left.keys() & right.keys()):
        a, b = entries(field, left[field]), entries(field, right[field])
        if [_agree_key(field, item["value"]) for item in a] != [_agree_key(field, item["value"]) for item in b]:
            changes["value"].append(field)
        if [(item["value_confidence"], item["confidence_parts"]) for item in a] != [
                (item["value_confidence"], item["confidence_parts"]) for item in b]:
            changes["confidence"].append(field)
        if [(item["provenance"], sorted(item["supporting_observations"])) for item in a] != [
                (item["provenance"], sorted(item["supporting_observations"])) for item in b]:
            changes["provenance"].append(field)
    return changes


def corruption_check(profiles: dict, obs_idx: dict, link_conf: dict, source: str, *, field="entity.date_registered") -> dict:
    """Corrupt one source field with identity membership held fixed."""
    registration = field == "entity.date_registered"
    stats = {"source_id": source, "field": field, "profiles_sampled": len(profiles),
             "profiles_with_corrupted_claims": 0, "corrupted_observations": 0, "profiles_value_changed": 0,
             "profiles_confidence_changed": 0, "profiles_provenance_changed": 0,
             "profiles_showing_date_conflict" if registration else "profiles_showing_name_conflict": 0}
    stats.update({"shift_days": 365} if registration else {"substitution": "CORRUPTED BENCHMARK NAME PTY LTD"})
    if not registration:
        stats.update(corrupted_winners=0, corrupted_winners_requiring_review=0, corrupted_winners_above_0_75=0)
    conflict_key = "profiles_showing_date_conflict" if registration else "profiles_showing_name_conflict"
    for key, original in profiles.items():
        corrupted = {}
        changed = 0
        for member in original["member_records"]:
            rows = []
            for obs in obs_idx[member]:
                if obs["source_id"] == source and obs["field"] == field:
                    shifted = ((date.fromisoformat(obs["value"]) + timedelta(days=365)).isoformat()
                               if registration else stats["substitution"])
                    oid = sha256(f"corruption-check|{obs['observation_id']}|{shifted}".encode()).hexdigest()[:24]
                    obs = obs | {"value": shifted, "observation_id": oid}
                    changed += 1
                rows.append(obs)
            corrupted[member] = rows
        if changed:
            stats["profiles_with_corrupted_claims"] += 1
            stats["corrupted_observations"] += changed
            replay = build_profile(key, original["member_records"], corrupted, link_conf, original["profile_version"])
            changes = _field_changes(original, replay)
            for dimension in ("value", "confidence", "provenance"):
                stats[f"profiles_{dimension}_changed"] += bool(changes[dimension])
            stats[conflict_key] += any(c["field"] == field for c in replay["conflicts"])
            if not registration:
                winner = replay["fields"].get(field, {})
                if winner.get("value") == stats["substitution"]:
                    stats["corrupted_winners"] += 1
                    stats["corrupted_winners_requiring_review"] += winner.get("resolution", {}).get("decision") == "review_required"
                    stats["corrupted_winners_above_0_75"] += winner["value_confidence"] > 0.75
    return stats


def run(count: int = 50, *, policy: str | None = None, version=PROFILE_VERSION, output=None, evaluation=None,
        observations=None) -> dict:
    options = {} if policy is None and version == PROFILE_VERSION else {"policy": policy, "version": version}
    if observations is not None:
        options["observations"] = observations
    profiles, res = materialise(**options)
    eligible = sorted(profiles)
    chosen = sorted(random.Random(SEED).sample(eligible, min(count, len(eligible))))
    output, evaluation = output or OUT_PROFILES, evaluation or OUT_EVAL
    output.mkdir(parents=True, exist_ok=True)
    with open(output / "company_profiles_50.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for e in chosen:
            fh.write(json.dumps(profiles[e]) + "\n")

    # Counterfactual: delete each source in turn, re-resolve and re-materialise. Each chosen profile is
    # compared with the profile rebuilt from its SURVIVING records (identity can change, not just fields).
    impact = {}
    base = {e: _fingerprint(profiles[e]) for e in chosen}
    total_fields = sum(len(base[e]) for e in chosen)
    if res.get("score_reference") is not None:
        options["score_reference"] = res["score_reference"]
    for s in sorted({record["source_id"] for record in res["recs"].values()}):
        alt, alt_res = materialise(exclude={s}, **options)
        stats = {"profiles_affected": 0, "profiles_unchanged": 0, "no_longer_multi_source": 0,
                 "fields_removed": 0, "fields_added": 0, "fields_value_changed": 0,
                 "fields_confidence_changed": 0, "fields_provenance_changed": 0, "fields_unchanged": 0, "examples": []}
        if version == EVIDENCE_PROFILE:
            stats.update(split_survivors=0, profiles_with_context_changes=0)
        for e in chosen:
            survivors = [m for m in profiles[e]["member_records"] if not m.startswith(s + "::")]
            targets = Counter(alt_res["key_of"][member] for member in survivors)
            alt_key = max(targets, key=lambda key: (targets[key], key))
            alt_p = alt.get(alt_key) or alt_res["build"](alt_key)
            fa, fb = base[e], _fingerprint(alt_p)
            changes = _field_changes(profiles[e], alt_p)
            rm, ch = changes["removed"], changes["value"]
            stats["fields_removed"] += len(rm)
            stats["fields_added"] += len(changes["added"])
            stats["fields_value_changed"] += len(ch)
            stats["fields_confidence_changed"] += len(changes["confidence"])
            stats["fields_provenance_changed"] += len(changes["provenance"])
            changed_fields = set().union(*(changes[d] for d in ("removed", "value", "confidence", "provenance")))
            stats["fields_unchanged"] += len(fa) - len(changed_fields)
            if len(alt_p["sources"]) < 2:
                stats["no_longer_multi_source"] += 1
            context_changed = False
            if version == EVIDENCE_PROFILE:
                stats["split_survivors"] += len(targets) > 1
                context_changed = any(profiles[e].get(key) != alt_p.get(key) for key in (
                    "locations", "registration_events", "historical_names", "mapping_defaults",
                ))
                stats["profiles_with_context_changes"] += context_changed
            if changed_fields or changes["added"] or len(alt_p["sources"]) < 2 or len(targets) > 1 or context_changed:
                stats["profiles_affected"] += 1
                if len(stats["examples"]) < 3 and (rm or ch):
                    stats["examples"].append({"entity_key": e, "removed": rm,
                                              "changed": {f: [fa[f], fb[f]] for f in ch}})
            else:
                stats["profiles_unchanged"] += 1
        stats["share_of_fields_lost_or_changed"] = round(
            (stats["fields_removed"] + stats["fields_value_changed"]) / max(total_fields, 1), 3)
        impact[s] = stats
    evaluation.mkdir(parents=True, exist_ok=True)
    (evaluation / "source_deletion_impact.json").write_text(json.dumps(impact, indent=2), encoding="utf-8", newline="\n")
    observations_index = _obs_index(observations=observations) if observations is not None else _obs_index()
    sample = {e: profiles[e] for e in chosen}
    links = _membership_conf(res, path_aware=version == EVIDENCE_PROFILE)
    corruption = corruption_check(sample, observations_index, links, "asic_companies")
    (evaluation / "source_corruption_impact.json").write_text(json.dumps(corruption, indent=2),
                                                          encoding="utf-8", newline="\n")
    if version == EVIDENCE_PROFILE:
        name_corruption = corruption_check(sample, observations_index, links, "asic_companies", field="entity.legal_name")
        (evaluation / "source_name_corruption_impact.json").write_text(json.dumps(name_corruption, indent=2),
                                                                       encoding="utf-8", newline="\n")
    n_conf = sum(1 for e in chosen if profiles[e]["conflicts"])
    return {"multi_source_entities": len(profiles), "profiles_written": len(chosen),
            "profiles_with_conflicts": n_conf, "link_threshold": THRESHOLD, "deletion_impact": {
                s: {k: v for k, v in d.items() if k != "examples"} for s, d in impact.items()}}
