"""Challenger matcher `strict-v3-raw`: strict-v2 plus the matching evidence the raw files carried (review 4.1).

New evidence, each a separate, auditable item on the link:
  DOMAIN_EQUAL        email domain / website domain shared (free-mail, ISP and government domains ignored;
                      a domain held by records with different ABNs is ambiguous and never links)
  PHONE_EQUAL         normalised phone shared (mobiles are personal data and never used)
  GEO_WITHIN_100M     two points within 100 m
  FORMER_NAME_EQUAL   a current name equals the other record's former legal name (refused when the former
                      name was later held by a different company: names are reused on the register)
  HOLDER_KIND         the source states the holder is an individual
Policy changes against strict-v2:
  * a registered-name-only link needs one corroborating field (place, phone, domain or geo); otherwise REVIEW
  * an individual licence holder sharing a company's ABN is a LICENSED_INDIVIDUAL_FOR relationship, not a link
  * domain or former-name evidence can link only with a corroborating name / place, else REVIEW
Relationships (review 4.4): HOLDS_LICENCE and OPERATES_ESTABLISHMENT from the mapping's declared roles,
DELIVERS_PROGRAM_FOR, TRUSTEE_OF, LICENSED_INDIVIDUAL_FOR, and SAME_GROUP_CANDIDATE (review only, never merges).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from itertools import combinations

from .. import crosswalk
from ..identity import resolve as R
from . import OUT_RD_EVAL, OUT_RD_IDENTITY, OUT_RD_OBS
from .extract import SHARED_DOMAINS, domain_of, name_stem

POLICY = "strict-v3-raw"
GEO_METRES = 100
NAME_CORROBORATION = 0.5
_TRUSTEE = re.compile(r"^(?P<trustee>.+?)\s+(?:AS\s+)?(?:TRUSTEE\s+FOR|ATF)\s+(?P<trust>.+)$")
NAME_REUSE_PATH = OUT_RD_IDENTITY / "former_name_reuse.json"


# ---- record view -----------------------------------------------------------------------------------------
def load(observations=OUT_RD_OBS) -> dict:
    recs = R.load_records(observations=observations)
    for r in recs.values():
        r.update(domains=set(), phones=set(), geo=set(), former={}, holder_kind=None, grade=None,
                 corr_address=set(), programs=set(), legal_form=None)
    for f in sorted(observations.glob("*.jsonl")):
        if f.name.endswith(".edges.jsonl"):
            continue
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            r = recs.get(f"{o['source_id']}::{o['source_record_id']}")
            if r is None:
                continue
            field, v = o["field"], o["value"]
            r["stratum"] = r.get("stratum") or o.get("sample_stratum")
            if field in ("ext.contact.email_domain", "ext.contact.website_domain", "entity.website"):
                d = domain_of(field, v)
                if d:
                    r["domains"].add(d)
            elif field == "ext.contact.phone" and o.get("privacy") != "personal":
                r["phones"].add(v)
            elif field == "ext.establishment.geo":
                r["geo"].add(tuple(float(x) for x in v.split(",")))
            elif field == "ext.entity.former_name" or (field == "entity.legal_name"
                                                        and o.get("claim_scope") == "former_legal_name"):
                r["former"][R.norm_name(v)] = (o.get("valid_from"), o.get("valid_to"))
            elif field == "ext.entity.holder_kind":
                r["holder_kind"] = v
            elif field == "ext.licence.grade":
                r["grade"] = v
            elif field == "ext.entity.legal_form":
                r["legal_form"] = v
            elif field == "ext.establishment.program":
                r["programs"].add(v)
            elif field == "address.full" and o.get("claim_scope") == "correspondence_address":
                r["corr_address"].add(" ".join(v.upper().split()))
    for r in recs.values():
        r["former_stems"] = {name_stem(n): n for n in r["former"] if len(name_stem(n).split()) >= 2}
        r["stems"] = {name_stem(n) for n in r["names"]}
    return recs


def _haversine(p, q) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*p, *q))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(h))


def _token_overlap(a_names: set, b_names: set) -> float:
    best = 0.0
    for x in a_names:
        tx = set(R.name_core(x).split())
        for y in b_names:
            ty = set(R.name_core(y).split())
            if tx and ty:
                best = max(best, len(tx & ty) / min(len(tx), len(ty)))
    return best


# ---- name reuse on the register (former names) -----------------------------------------------------------
def build_name_reuse() -> dict:
    """Names held by more than one ACN as a current OR former name, read through the ASIC extension mapping
    (no source-specific code). A former name in this set never supports a link."""
    from ..mapping.engine import Engine
    from ..paths import ROOT
    from ..sources.readers import iter_records
    from ..sources.select import load_manifest
    from .extract import load_ext_config
    cfg, prov = load_ext_config("asic_companies")
    keep = [f for f in cfg.fields if f.target in ("entity.legal_name", "ext.entity.former_name", "entity.acn")]
    if not any(f.target == "ext.entity.former_name" for f in keep):
        doc = {"note": "the ASIC mapping in use emits no former names", "names": []}
    else:
        probe = cfg.model_copy(update={"fields": keep, "constants": [], "relationships": None})
        man = load_manifest()["asic_companies"]
        eng = Engine(probe, man)
        holders = defaultdict(set)
        for rec in iter_records(ROOT / man["snapshot"]["path"], cfg.reader):
            obs = eng.process(rec)
            acns = {o["value"] for o in obs if o["field"] == "entity.acn"}
            for o in obs:
                if o["field"] in ("entity.legal_name", "ext.entity.former_name"):
                    holders[R.norm_name(o["value"])].update(acns)
        reused = sorted(n for n, a in holders.items() if len(a) > 1)
        doc = {"mapping": prov, "names_seen": len(holders), "count": len(reused), "names": reused}
    OUT_RD_IDENTITY.mkdir(parents=True, exist_ok=True)
    NAME_REUSE_PATH.write_text(json.dumps(doc), encoding="utf-8", newline="\n")
    return {k: v for k, v in doc.items() if k != "names"}


def _reused_names() -> frozenset:
    if not NAME_REUSE_PATH.exists():
        build_name_reuse()
    return frozenset(json.loads(NAME_REUSE_PATH.read_text(encoding="utf-8"))["names"])


# ---- candidates and evidence -----------------------------------------------------------------------------
def extra_pairs(recs: dict) -> tuple[set, dict]:
    blocks = defaultdict(set)
    for k, r in recs.items():
        for d in r["domains"]:
            blocks[("domain", d)].add(k)
        for p in r["phones"]:
            blocks[("phone", p)].add(k)
        for n in r["former"]:
            blocks[("name", n)].add(k)
        for s in r.get("former_stems", ()):
            blocks[("stem", s)].add(k)
        for s in r.get("stems", ()):
            if len(s.split()) >= 2:
                blocks[("stem", s)].add(k)
        for lat, lon in r["geo"]:
            blocks[("geo", round(lat, 3), round(lon, 3))].add(k)
    pairs = set()
    for bk, members in blocks.items():
        if len(members) > 200:
            continue
        for a, b in combinations(sorted(members), 2):
            if recs[a]["source_id"] != recs[b]["source_id"]:
                pairs.add((a, b))
    # A domain or phone shared by records with different valid ABNs identifies a group, not a business.
    ambiguous = {}
    for bk, members in blocks.items():
        if bk[0] in ("domain", "phone"):
            abns = {x for m in members for x in recs[m]["abn"]}
            if len(abns) > 1:
                ambiguous[bk] = sorted(abns)
    return pairs, ambiguous


def make_evidence(ambiguous: dict, reused: frozenset):
    def ev_fn(a: dict, b: dict):
        score, rule, ev, contra = R.evidence(a, b, "strict-v2")
        dom = a["domains"] & b["domains"]
        dom_ok = {d for d in dom if ("domain", d) not in ambiguous}
        phone = {p for p in a["phones"] & b["phones"] if ("phone", p) not in ambiguous}
        geo = any(_haversine(p, q) <= GEO_METRES for p in a["geo"] for q in b["geo"])
        former = {n for n in (a["names"] & set(b["former"])) | (b["names"] & set(a["former"]))
                  if R.is_registered_company_name(n)}
        if dom:
            ev.append({"type": "DOMAIN_EQUAL", "value": sorted(dom)[0], "ambiguous": not dom_ok})
        if phone:
            ev.append({"type": "PHONE_EQUAL", "value": sorted(phone)[0][:6] + "...",
                       "inbound": sorted(phone)[0].startswith(("+611300", "+611800"))})
        if geo:
            ev.append({"type": "GEO_WITHIN_100M"})
        for n in sorted(former):
            holder = a if n in a["former"] else b
            ev.append({"type": "FORMER_NAME_EQUAL", "value": n, "valid": holder["former"][n], "reused": n in reused})
        corroborated = any(e["type"] == "LOCATION_AGREES" for e in ev) or bool(dom_ok or phone or geo)
        if contra:
            return score, rule, ev, contra
        kinds = {a.get("holder_kind"), b.get("holder_kind")}
        if a["abn"] & b["abn"] and "individual" in kinds and (
                R._kind(a) == "company" or R._kind(b) == "company" or "organisation" in kinds):
            ev.append({"type": "HOLDER_KIND", "value": "individual"})
            return 0.80, "licensed_individual_for_company", ev, contra
        if rule in ("registered_name_exact", "registered_name_exact_and_location"):
            if corroborated:
                return 0.90, "registered_name_exact_corroborated", ev, contra
            return 0.84, "registered_name_exact_uncorroborated", ev, contra
        if score >= R.THRESHOLD:
            return score, rule, ev, contra
        overlap = _token_overlap(a["names"], b["names"])
        if overlap:
            ev.append({"type": "NAME_TOKEN_OVERLAP", "value": round(overlap, 3)})
        usable_former = {n for n in former if n not in reused}
        if usable_former:
            if corroborated:
                return 0.88, "former_name_exact_corroborated", ev, contra
            return 0.82, "former_name_exact_uncorroborated", ev, contra
        if former:
            return 0.40, "former_name_reused_on_register", ev, contra
        stem_hits = {s: x["former_stems"][s] for x, y in ((a, b), (b, a)) for s in x.get("former_stems", {})
                     if s in y.get("stems", set())}
        if stem_hits:
            for s, full in sorted(stem_hits.items()):
                ev.append({"type": "FORMER_NAME_STEM_EQUAL", "value": s, "former_name": full, "reused": full in reused})
            if all(full in reused for full in stem_hits.values()):
                return 0.40, "former_name_reused_on_register", ev, contra
            if corroborated:
                return 0.86, "former_name_stem_corroborated", ev, contra
            return 0.78, "former_name_stem_uncorroborated", ev, contra
        if dom_ok:
            if overlap >= NAME_CORROBORATION:
                return 0.88, "domain_equal_and_name", ev, contra
            return 0.80, "domain_equal_only", ev, contra
        if dom:
            return 0.50, "domain_shared_by_several_abns", ev, contra
        if phone and overlap >= NAME_CORROBORATION:
            return 0.86, "phone_equal_and_name", ev, contra
        if phone:
            return 0.78, "phone_equal_only", ev, contra
        return score, rule, ev, contra
    return ev_fn


# ---- relationships ---------------------------------------------------------------------------------------
def relationships(recs: dict, res: dict, ambiguous: dict) -> list[dict]:
    key_of = res["key_of"]
    rel = []
    for f in sorted((OUT_RD_OBS / "edges").glob("*.jsonl")):
        for line in open(f, encoding="utf-8"):
            e = json.loads(line)
            k = f"{e['source_id']}::{e['source_record_id']}"
            if k in key_of:
                rel.append({"type": e["type"], "entity": key_of[k], "record": k, "to": e["to_ref"],
                            "approval_state": e.get("approval_state"), "derivation_level": "L0",
                            "basis": "declared by the source mapping (one row describes both)"})
    programmes = {k: v for k, v in (crosswalk.load("anzsic_dewr_program").get("entries") or {}).items()}
    for k, r in recs.items():
        for p in sorted(r["programs"]):
            label = (programmes.get(p) or {}).get("programme", "unlisted programme code")
            rel.append({"type": "DELIVERS_PROGRAM_FOR", "entity": key_of[k], "record": k,
                        "to": "agency:Department of Employment and Workplace Relations",
                        "programme": p, "programme_label": label, "derivation_level": "L1",
                        "basis": "the publisher lists this site under the programme contract"})
    by_name = defaultdict(set)
    for k, r in recs.items():
        for n in r["legal"]:
            by_name[n].add(k)
    for k, r in recs.items():
        for n in r["names"]:
            m = _TRUSTEE.match(n)
            if not m:
                continue
            trustee = m.group("trustee").strip()
            holders = {h for h in by_name.get(trustee, ()) if h != k}
            if R.is_registered_company_name(trustee) and holders:
                for h in sorted(holders):
                    rel.append({"type": "TRUSTEE_OF", "entity": key_of[h], "record": h, "to_entity": key_of[k],
                                "to_record": k, "evidence": {"name": n, "trustee": trustee},
                                "derivation_level": "L1", "basis": "the source names the trustee in the name"})
            else:
                rel.append({"type": "TRUSTEE_NAMED", "entity": key_of[k], "record": k,
                            "evidence": {"name": n, "trustee": trustee}, "derivation_level": "L1",
                            "basis": "trustee named in the source name but not found among sampled records"})
    for d in res["decisions"]:
        if d["decision"] == "RELATIONSHIP":
            person, company = (d["a"], d["b"]) if recs[d["a"]].get("holder_kind") == "individual" else (d["b"], d["a"])
            rel.append({"type": "LICENSED_INDIVIDUAL_FOR", "entity": key_of[person], "record": person,
                        "to_entity": key_of[company], "to_record": company, "evidence": d["evidence"],
                        "derivation_level": "L1",
                        "basis": "an individual licence holder recorded with the company's ABN; not the same entity"})
    # Groups: the same non-shared contact point on records of DIFFERENT entities with different ABNs.
    groups = defaultdict(set)
    for k, r in recs.items():
        for d in r["domains"]:
            groups[("domain", d)].add(k)
        for p in r["phones"]:
            groups[("phone", p)].add(k)
        for a in r["corr_address"]:
            groups[("postal_address", a)].add(k)
    seen = set()
    for (kind, value), members in sorted(groups.items()):
        ents = {key_of[m] for m in members}
        abns = {x for m in members for x in recs[m]["abn"]}
        if len(ents) < 2 or len(abns) < 2 or value in SHARED_DOMAINS or len(ents) > 25:
            continue
        for e1, e2 in combinations(sorted(ents), 2):
            if (e1, e2, kind) in seen:
                continue
            seen.add((e1, e2, kind))
            rel.append({"type": "SAME_GROUP_CANDIDATE", "entity": e1, "to_entity": e2, "shared": kind,
                        "value": value if kind != "phone" else value[:6] + "...", "derivation_level": "L2",
                        "basis": "shared contact point across different ABNs; a candidate for review, never a merge"})
    return rel


# ---- run --------------------------------------------------------------------------------------------------
def _summarise(res: dict, recs: dict) -> dict:
    links = [d for d in res["decisions"] if d["decision"] == "LINK"]
    by_rule, by_pair, by_strata = Counter(), Counter(), Counter()
    for d in links:
        by_rule[d["rule"]] += 1
        by_pair[" <-> ".join(sorted([recs[d["a"]]["source_id"], recs[d["b"]]["source_id"]]))] += 1
        by_strata["+".join(sorted([recs[d["a"]].get("stratum") or "?", recs[d["b"]].get("stratum") or "?"]))] += 1
    ent_sources = defaultdict(set)
    for k, e in res["key_of"].items():
        ent_sources[e].add(recs[k]["source_id"])
    return {"links": len(links), "links_by_rule": dict(by_rule), "links_by_source_pair": dict(by_pair),
            "links_by_sample_strata": dict(by_strata),
            "decisions": dict(Counter(d["decision"] for d in res["decisions"])),
            "entities_in_multiple_sources": sum(len(s) > 1 for s in ent_sources.values()),
            "linked_records_by_source": dict(Counter(recs[k]["source_id"] for k in
                                                     {x for d in links for x in (d["a"], d["b"])}))}


def run() -> dict:
    recs = load()
    pairs, ambiguous = extra_pairs(recs)
    reused = _reused_names()
    res = R.resolve(recs=recs, extra_pairs=pairs, evidence_fn=make_evidence(ambiguous, reused), policy=POLICY)
    baseline = R.resolve(recs=load(), policy="strict-v2")     # same observations, audited policy
    out = OUT_RD_IDENTITY
    out.mkdir(parents=True, exist_ok=True)
    key_of = res["key_of"]
    links = [d for d in res["decisions"] if d["decision"] == "LINK"]
    with open(out / "proposed_links.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for d in links:
            fh.write(json.dumps({
                "link_id": "lk_" + hashlib.sha256(f"{d['a']}|{d['b']}|{POLICY}".encode()).hexdigest()[:16],
                "source_a_record": d["a"], "source_b_record": d["b"], "canonical_entity_key": key_of[d["a"]],
                "confidence": d["score"], "confidence_kind": "link_confidence (policy score, not a calibrated probability)",
                "rule": d["rule"], "evidence": d["evidence"], "policy_version": POLICY, "threshold": R.THRESHOLD,
                "a": R._rec_summary(recs[d["a"]]), "b": R._rec_summary(recs[d["b"]]),
                "strata": [recs[d["a"]].get("stratum"), recs[d["b"]].get("stratum")]}, default=str) + "\n")
    with open(out / "link_decisions.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for d in res["decisions"]:
            fh.write(json.dumps({k: d[k] for k in ("a", "b", "score", "rule", "decision", "reason", "name_sim",
                                                   "evidence", "contradictions")} | {"policy_version": POLICY},
                                default=str) + "\n")
    with open(out / "review_queue.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for d in res["decisions"]:
            if d["decision"] == "REVIEW":
                fh.write(json.dumps(d | {"policy_version": POLICY, "record_a": R._rec_summary(recs[d["a"]]),
                                         "record_b": R._rec_summary(recs[d["b"]])}, default=str) + "\n")
    linked = {k for d in links for k in (d["a"], d["b"])}
    R.POSITIVE_EVIDENCE.update({"DOMAIN_EQUAL", "PHONE_EQUAL", "GEO_WITHIN_100M", "FORMER_NAME_EQUAL"})
    queue = R._unlinked_queue(recs, res["decisions"], linked)
    with open(out / "unlinked_queue.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for q in queue:
            fh.write(json.dumps(q, default=str) + "\n")
    rel = relationships(recs, res, ambiguous)
    with open(out / "relationships.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in rel:
            fh.write(json.dumps(x, default=str) + "\n")
    (out / "entity_membership.json").write_text(json.dumps({"policy_version": POLICY, "membership": key_of}, indent=0),
                                                encoding="utf-8", newline="\n")
    summary = {"policy_version": POLICY, "threshold": R.THRESHOLD, "records": len(recs),
               "records_by_stratum": dict(Counter(r.get("stratum") for r in recs.values())),
               "challenger": _summarise(res, recs), "strict_v2_on_same_observations": _summarise(baseline, recs),
               "relationships": dict(Counter(x["type"] for x in rel)),
               "ambiguous_contact_points": len(ambiguous), "former_names_reused_on_register": len(reused),
               "unlinked_queue": len(queue), "unlinked_by_reason": dict(Counter(q["reason"] for q in queue))}
    summary["comparison"] = compare(baseline, res, recs)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8", newline="\n")
    audit_sample(res, recs)
    return {k: v for k, v in summary.items() if k != "comparison"} | {"comparison": {
        k: v for k, v in summary["comparison"].items() if not isinstance(v, list)}}


def compare(baseline: dict, challenger: dict, recs: dict) -> dict:
    pair = lambda d: tuple(sorted((d["a"], d["b"])))
    b = {pair(d): d for d in baseline["decisions"] if d["decision"] == "LINK"}
    c = {pair(d): d for d in challenger["decisions"] if d["decision"] == "LINK"}
    cdec = {pair(d): d for d in challenger["decisions"]}
    added = [c[p] for p in sorted(set(c) - set(b))]
    removed = [b[p] for p in sorted(set(b) - set(c))]
    by_source = lambda ds: dict(Counter(" <-> ".join(sorted([recs[d["a"]]["source_id"], recs[d["b"]]["source_id"]]))
                                        for d in ds))
    examples = {}
    for needle in ("JOB CENTRE AUSTRALIA",):
        hits = [d for d in challenger["decisions"] if any(needle in n for k in (d["a"], d["b"])
                                                          for n in recs[k]["names"] | set(recs[k]["former"]))]
        examples[needle] = [{"a": d["a"], "b": d["b"], "decision": d["decision"], "rule": d["rule"],
                             "score": d["score"]} for d in hits[:10]]
    return {"links_kept": len(set(b) & set(c)), "links_added": len(added), "links_removed": len(removed),
            "added_by_rule": dict(Counter(d["rule"] for d in added)), "added_by_source_pair": by_source(added),
            "removed_now": dict(Counter(f"{cdec[pair(d)]['decision']}:{cdec[pair(d)]['rule']}" if pair(d) in cdec
                                        else "not a candidate" for d in removed)),
            "removed_by_source_pair": by_source(removed),
            "dewr_links": {"strict_v2": sum("dewr_employment_providers" in d["a"] + d["b"] for d in b.values()),
                           "strict_v3_raw": sum("dewr_employment_providers" in d["a"] + d["b"] for d in c.values())},
            "named_examples": examples,
            "added": [{"a": d["a"], "b": d["b"], "rule": d["rule"], "score": d["score"]} for d in added[:200]],
            "removed": [{"a": d["a"], "b": d["b"], "rule": d["rule"]} for d in removed[:300]]}


def audit_sample(res: dict, recs: dict, n: int = 50, seed: int = 20261112) -> None:
    """Stratified 50-link sample for HUMAN labelling: every new-evidence rule is represented. Labels blank."""
    links = [d for d in res["decisions"] if d["decision"] == "LINK"]
    by_rule = defaultdict(list)
    for d in links:
        by_rule[d["rule"]].append(d)
    rng = random.Random(seed)
    quota = {rule: min(len(ds), max(4, n * len(ds) // max(len(links), 1))) for rule, ds in by_rule.items()}
    while sum(quota.values()) > n:
        biggest = max(quota, key=lambda r: quota[r])
        quota[biggest] -= 1
    sample = [d for rule, ds in sorted(by_rule.items()) for d in rng.sample(ds, quota[rule])]
    OUT_RD_EVAL.mkdir(parents=True, exist_ok=True)
    with open(OUT_RD_EVAL / "link_audit_strict_v3_raw_50.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["idx", "seed", "policy_version", "rule", "score", "record_a", "names_a", "ids_a", "record_b",
                    "names_b", "ids_b", "evidence", "label", "note", "reviewer"])
        for i, d in enumerate(sample):
            ra, rb = recs[d["a"]], recs[d["b"]]
            w.writerow([i, seed, POLICY, d["rule"], d["score"], d["a"], "; ".join(sorted(ra["names"]))[:200],
                        " ".join(sorted(ra["abn"] | ra["acn"])), d["b"], "; ".join(sorted(rb["names"]))[:200],
                        " ".join(sorted(rb["abn"] | rb["acn"])),
                        json.dumps([e for e in d["evidence"] if e["type"] != "EVIDENCE_SCORE_COMPONENTS"], default=str)[:600],
                        "", "", ""])
