"""Part 3: conservative cross-source entity resolution.

Model (see WRITEUP): identity is a DECISION about source records, stored as an append-only list of
pairwise link decisions with evidence + policy version. Entities are derived: clusters formed only
from accepted links, under a constraint that a cluster may never hold two different valid ABNs (or
ACNs). The canonical_entity_key is derived from the cluster's strongest anchor so it is stable across
re-runs. Relationships between DIFFERENT businesses are separate typed edges and never merge clusters.

Policy strict-v1 (decided before any audit; see THRESHOLDS):
  ABN equal (both checksum-valid)                         -> link 0.97
  ACN equal                                               -> link 0.95
  ABN's last 9 digits == other's ACN AND names agree      -> link 0.90
  identical normalised REGISTERED-company name (Pty Ltd, Ltd, Inc...) and no ID conflict
      + same postcode/locality                            -> link 0.90
      alone                                               -> link 0.86   (company names are unique on the
                                                             ASIC register at a point in time)
  near-identical name (token similarity >= 0.92) + same postcode/locality -> 0.78  (below threshold: REVIEW)
  identical name without a company suffix (people, trading names)        -> abstain AMBIGUOUS_NAME
  any two different valid ABNs or ACNs                                   -> veto CONFLICTING_VALID_IDENTIFIER
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations

from ..paths import OUT_IDENTITY, OUT_OBS

POLICY_VERSION = "strict-v1"
THRESHOLD = 0.85          # strict: precision audit runs at this threshold
LOOSE_THRESHOLD = 0.75    # exploratory: reported separately, never mixed into the strict number
MAX_BLOCK = 50            # name blocks larger than this are too generic to compare pairwise
PLAUSIBLE_NAME_SIM = 0.85 # an ID conflict below this name similarity is a confident NON_MATCH, not a refusal
QUEUE_MIN_SIM = 0.6       # abstentions with a candidate at least this similar are listed in the unlinked queue

_SUFFIXES = [(r"\bPROPRIETARY\b", "PTY"), (r"\bPTY\.?\b", "PTY"), (r"\bLIMITED\b", "LTD"), (r"\bLTD\.?\b", "LTD"),
             (r"\bINCORPORATED\b", "INC"), (r"\bINC\.?\b", "INC"), (r"\bCOMPANY\b", "CO"), (r"\bCORPORATION\b", "CORP"),
             (r"\bAUSTRALIA\b", "AUSTRALIA"), (r"\bAND\b", "&")]
_COMPANY = re.compile(r"\b(PTY LTD|LTD|INC|NL|CORP|PLC|LIMITED)\b|\bPTY\b")
_TRUSTEE = re.compile(r"\b(THE TRUSTEE FOR|TRUSTEE FOR|AS TRUSTEE FOR|ATF)\b")


def norm_name(v: str) -> str:
    s = v.upper().replace("&", " & ")
    s = re.sub(r"[^A-Z0-9& ]", " ", s)
    s = " ".join(s.split())
    for pat, rep in _SUFFIXES:
        s = re.sub(pat, rep, s)
    s = re.sub(r"^THE ", "", s)
    return " ".join(s.split())


def is_registered_company_name(n: str) -> bool:
    return bool(_COMPANY.search(n)) and not _TRUSTEE.search(n)


_GENERIC = {"PTY", "LTD", "INC", "CO", "CORP", "NL", "PLC", "THE", "&", "OF", "FOR", "TRUSTEE", "TRUST",
            "HOLDINGS", "HOLDING", "GROUP", "AUSTRALIA", "AUSTRALIAN", "NZ", "NEW", "ZEALAND", "INVESTMENTS",
            "INVESTMENT", "ENTERPRISES", "SERVICES", "SERVICE", "INTERNATIONAL", "MANAGEMENT", "PROPERTY",
            "CAPITAL", "SOLUTIONS", "INDUSTRIES", "CONSTRUCTION", "FOODS", "ASSOCIATION", "CLUB"}


def name_core(n: str) -> str:
    """Distinctive tokens only: legal suffixes and generic business words carry no identity."""
    return " ".join(sorted(t for t in n.split() if t not in _GENERIC))


def name_sim(a: str, b: str) -> float:
    ca, cb = name_core(a), name_core(b)
    if not ca or not cb:
        return 1.0 if a == b else 0.0
    return SequenceMatcher(None, ca, cb).ratio()


def load_records(exclude: set[str] = frozenset()) -> dict:
    """(source_id, record_id) -> record view of its observations."""
    recs = {}
    for f in sorted(OUT_OBS.glob("*.jsonl")):
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            if o["source_id"] in exclude:
                continue
            k = f"{o['source_id']}::{o['source_record_id']}"
            r = recs.setdefault(k, {"key": k, "source_id": o["source_id"], "record_id": o["source_record_id"],
                                    "grain": o["record_grain"], "stratum": o.get("sample_stratum"), "f": defaultdict(list)})
            r["f"][o["field"]].append(o["value"])
    for r in recs.values():
        f = r["f"]
        r["abn"] = set(f.get("entity.abn", []))
        r["acn"] = set(f.get("entity.acn", []))
        r["names"] = {norm_name(v) for v in f.get("entity.legal_name", []) + f.get("entity.trading_name", [])}
        r["legal"] = {norm_name(v) for v in f.get("entity.legal_name", [])}
        r["postcode"] = set(f.get("address.postcode", []))
        r["locality"] = {v.upper().strip() for v in f.get("address.locality", [])}
        r["is_business"] = bool(r["abn"] or r["acn"] or r["names"])
    return recs


def _kind(r: dict) -> str | None:
    """'company' if every legal name looks registered, 'other' if none does, None if unknown/mixed."""
    # Also accept a suffix glued to the previous word ('...GROUPLIMITED' occurs in ATO data).
    kinds = {is_registered_company_name(n) or bool(re.search(r"(LIMITED|LTD|PTY)$", n)) for n in r["legal"]}
    return None if len(kinds) != 1 else ("company" if kinds.pop() else "other")


def evidence(a: dict, b: dict, policy: str = POLICY_VERSION) -> tuple[float, str, list, list]:
    """Score one candidate pair. Returns (score, rule, evidence, contradictions)."""
    ev, contra = [], []
    if a["abn"] and b["abn"]:
        if a["abn"] & b["abn"]:
            ev.append({"type": "ABN_EQUAL_VALID", "value": sorted(a["abn"] & b["abn"])[0]})
        else:
            contra.append({"type": "ABN_CONFLICT", "a": sorted(a["abn"]), "b": sorted(b["abn"])})
    if a["acn"] and b["acn"]:
        if a["acn"] & b["acn"]:
            ev.append({"type": "ACN_EQUAL_VALID", "value": sorted(a["acn"] & b["acn"])[0]})
        else:
            contra.append({"type": "ACN_CONFLICT", "a": sorted(a["acn"]), "b": sorted(b["acn"])})
    embed = any(x[2:] == y for x in a["abn"] for y in b["acn"]) or any(x[2:] == y for x in b["abn"] for y in a["acn"])
    if embed:
        ev.append({"type": "ABN_CONTAINS_ACN"})
    best = max((name_sim(x, y) for x in a["names"] for y in b["names"]), default=0.0)
    exact = a["names"] & b["names"]
    if exact:
        ev.append({"type": "NAME_EXACT_NORMALISED", "value": sorted(exact)[0]})
    elif best:
        ev.append({"type": "NAME_SIMILARITY", "value": round(best, 3)})
    loc = bool(a["postcode"] & b["postcode"]) or bool(a["locality"] & b["locality"])
    if loc:
        ev.append({"type": "LOCATION_AGREES"})
    elif a["postcode"] and b["postcode"]:
        ev.append({"type": "POSTCODE_DIFFERS"})  # weak: licence premises vs registered office legitimately differ

    if contra:
        return 0.0, "veto_conflicting_identifier", ev, contra
    if a["abn"] & b["abn"]:
        ka, kb = _kind(a), _kind(b)
        if policy == "strict-v2" and ka and kb and ka != kb:
            # Found by the v1 precision audit: licence registers record an INDIVIDUAL licensee next to the
            # ABN of the company they work for. Same ABN, different legal entities -> review, never auto-link.
            ev.append({"type": "LEGAL_NAME_KIND_DIFFERS", "a": ka, "b": kb})
            return 0.80, "abn_equal_but_person_vs_company", ev, contra
        return 0.97, "abn_equal", ev, contra
    if a["acn"] & b["acn"]:
        return 0.95, "acn_equal", ev, contra
    if embed and (exact or best >= 0.85):
        return 0.90, "abn_contains_acn_and_name", ev, contra
    company_exact = {n for n in exact if is_registered_company_name(n)}
    if company_exact and policy == "strict-v2":
        from .ambiguity import ambiguous_names
        if company_exact <= ambiguous_names():
            # Measured: 0.1% of current registered names belong to more than one ACN. Never link on those alone.
            ev.append({"type": "NAME_NOT_UNIQUE_ON_REGISTER"})
            return 0.40, "ambiguous_registered_name", ev, contra
    if company_exact:
        return (0.90, "registered_name_exact_and_location", ev, contra) if loc else \
               (0.86, "registered_name_exact", ev, contra)
    if best >= 0.92 and loc:
        return 0.78, "near_name_and_location", ev, contra
    if exact:
        return 0.40, "ambiguous_name_exact", ev, contra
    return round(0.5 * best, 3), "weak_name", ev, contra


def candidates(recs: dict):
    """Blocking: shared ABN, ACN, ABN-suffix/ACN, or normalised name. Cross-source pairs only."""
    blocks = defaultdict(set)
    for k, r in recs.items():
        for v in r["abn"]:
            blocks[("id", v[2:])].add(k)      # ABN suffix block catches ABN==ABN and ABN-contains-ACN
        for v in r["acn"]:
            blocks[("id", v)].add(k)
        for n in r["names"]:
            blocks[("name", n)].add(k)
            toks = n.split()
            if len(toks) >= 2:
                blocks[("name2", " ".join(sorted(toks)[:2]))].add(k)  # coarse block for near-name candidates
    pairs, oversized = set(), []
    for bk, members in blocks.items():
        if len(members) > MAX_BLOCK:
            oversized.append((bk, len(members)))
            if bk[0] != "id":
                continue
        for a, b in combinations(sorted(members), 2):
            if recs[a]["source_id"] != recs[b]["source_id"]:
                pairs.add((a, b))
    return pairs, oversized


class Clusters:
    """Union-find with an identifier-consistency constraint on every merge."""

    def __init__(self, recs):
        self.parent = {}
        self.ids = {}
        for k, r in recs.items():
            self.parent[k] = k
            self.ids[k] = {"abn": set(r["abn"]), "acn": set(r["acn"])}

    def find(self, k):
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def try_union(self, a, b) -> str | None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return None
        for t in ("abn", "acn"):
            if len(self.ids[ra][t] | self.ids[rb][t]) > 1:
                return f"CLUSTER_WOULD_HOLD_TWO_{t.upper()}S"
        self.parent[rb] = ra
        for t in ("abn", "acn"):
            self.ids[ra][t] |= self.ids[rb][t]
        return None


def entity_key(members: list[str], recs: dict, ids: dict) -> str:
    """Stable, opaque key from the strongest anchor: ABN, else ACN, else the smallest member record."""
    if ids["abn"]:
        anchor = "abn:" + sorted(ids["abn"])[0]
    elif ids["acn"]:
        anchor = "acn:" + sorted(ids["acn"])[0]
    else:
        anchor = "rec:" + min(members)
    return "fe_" + hashlib.sha256(anchor.encode()).hexdigest()[:16]


def resolve(exclude: set[str] = frozenset(), threshold: float = THRESHOLD, policy: str = POLICY_VERSION) -> dict:
    recs = load_records(exclude)
    pairs, oversized = candidates(recs)
    scored = []
    for a, b in pairs:
        s, rule, ev, contra = evidence(recs[a], recs[b], policy)
        scored.append({"a": a, "b": b, "score": s, "rule": rule, "evidence": ev, "contradictions": contra})
    scored.sort(key=lambda x: (-x["score"], x["a"], x["b"]))   # strongest evidence merges first
    cl = Clusters(recs)
    decisions = []
    for p in scored:
        sims = [1.0 if e["type"] == "NAME_EXACT_NORMALISED" else e["value"]
                for e in p["evidence"] if e["type"] in ("NAME_EXACT_NORMALISED", "NAME_SIMILARITY")]
        p["name_sim"] = max(sims, default=0.0)
        if p["contradictions"] and p["name_sim"] < PLAUSIBLE_NAME_SIM:
            # Different identifiers AND dissimilar names: a confident non-match, not a refusal.
            p["decision"], p["reason"] = "NON_MATCH", "DIFFERENT_IDENTIFIERS_AND_NAMES"
        elif p["contradictions"]:
            p["decision"], p["reason"] = "REJECT", "CONFLICTING_VALID_IDENTIFIER"
        elif p["score"] >= threshold:
            refusal = cl.try_union(p["a"], p["b"])
            p["decision"], p["reason"] = ("REJECT", refusal) if refusal else ("LINK", None)
        elif p["score"] >= LOOSE_THRESHOLD:
            p["decision"], p["reason"] = "REVIEW", "BELOW_STRICT_THRESHOLD"
        elif p["rule"] == "ambiguous_name_exact":
            p["decision"], p["reason"] = "ABSTAIN", "AMBIGUOUS_NAME"
        else:
            p["decision"], p["reason"] = "ABSTAIN", "WEAK_NAME_ONLY"
        decisions.append(p)
    clusters = defaultdict(list)
    for k in recs:
        clusters[cl.find(k)].append(k)
    key_of, used = {}, set()
    # Largest cluster first keeps the plain anchor key; a smaller cluster that shares the anchor (e.g. a
    # record that was deliberately NOT linked to the company whose ABN it carries) gets its own key.
    for root, members in sorted(clusters.items(), key=lambda kv: (-len(kv[1]), min(kv[1]))):
        ek = entity_key(members, recs, cl.ids[root])
        if ek in used:
            ek = "fe_" + hashlib.sha256(f"{ek}|{min(members)}".encode()).hexdigest()[:16]
        used.add(ek)
        for m in members:
            key_of[m] = ek
    return {"recs": recs, "decisions": decisions, "key_of": key_of, "clusters": clusters,
            "oversized_blocks": oversized}


def _rec_summary(r: dict) -> dict:
    return {"source_id": r["source_id"], "record_id": r["record_id"], "grain": r["grain"],
            "names": sorted(r["f"].get("entity.legal_name", []) + r["f"].get("entity.trading_name", []))[:4],
            "abn": sorted(r["abn"]), "acn": sorted(r["acn"]), "postcode": sorted(r["postcode"])}


def run() -> dict:
    res = resolve()
    recs, decisions, key_of = res["recs"], res["decisions"], res["key_of"]
    OUT_IDENTITY.mkdir(parents=True, exist_ok=True)
    links = [d for d in decisions if d["decision"] == "LINK"]
    with open(OUT_IDENTITY / "proposed_links.jsonl", "w", encoding="utf-8") as fh:
        for d in links:
            fh.write(json.dumps({
                "link_id": "lk_" + hashlib.sha256(f"{d['a']}|{d['b']}|{POLICY_VERSION}".encode()).hexdigest()[:16],
                "source_a_record": d["a"], "source_b_record": d["b"],
                "canonical_entity_key": key_of[d["a"]], "confidence": d["score"],
                "confidence_kind": "link_confidence (policy score, not a calibrated probability)",
                "rule": d["rule"], "evidence": d["evidence"], "policy_version": POLICY_VERSION,
                "threshold": THRESHOLD, "a": _rec_summary(recs[d["a"]]), "b": _rec_summary(recs[d["b"]]),
                "strata": [recs[d["a"]]["stratum"], recs[d["b"]]["stratum"]]}) + "\n")
    # All decisions, including rejections, are kept: a future matcher must be able to re-score them.
    with open(OUT_IDENTITY / "link_decisions.jsonl", "w", encoding="utf-8") as fh:
        for d in decisions:
            fh.write(json.dumps({k: d[k] for k in ("a", "b", "score", "rule", "decision", "reason", "name_sim",
                                                   "evidence", "contradictions")} | {"policy_version": POLICY_VERSION}) + "\n")
    linked = {k for d in links for k in (d["a"], d["b"])}
    best_refusal = {}
    for d in decisions:
        # Queue only refusals of PLAUSIBLE matches: that is where the line was drawn.
        if d["decision"] in ("LINK", "NON_MATCH"):
            continue
        if d["reason"] == "WEAK_NAME_ONLY" and d["name_sim"] < QUEUE_MIN_SIM:
            continue
        for k, other in ((d["a"], d["b"]), (d["b"], d["a"])):
            if k in linked:
                continue
            cur = best_refusal.get(k)
            if cur is None or d["score"] > cur["score"] or (d["contradictions"] and not cur["contradictions"]):
                best_refusal[k] = d | {"other": other}
    queue = []
    for k, d in sorted(best_refusal.items()):
        r = recs[k]
        if not r["is_business"]:
            continue
        queue.append({"source_record": k, "reason": d["reason"], "best_candidate": d["other"],
                      "best_score": d["score"], "rule": d["rule"], "evidence": d["evidence"],
                      "contradictions": d["contradictions"], "record": _rec_summary(r),
                      "candidate": _rec_summary(recs[d["other"]]),
                      "next_action": {"CONFLICTING_VALID_IDENTIFIER": "investigate: related entities or data error",
                                      "BELOW_STRICT_THRESHOLD": "human review (looser-threshold candidate)",
                                      "AMBIGUOUS_NAME": "needs an identifier or address to decide",
                                      "WEAK_NAME_ONLY": "needs an identifier or a shared address before any link"}
                      .get(d["reason"], "review cluster constraint")})
    with open(OUT_IDENTITY / "unlinked_queue.jsonl", "w", encoding="utf-8") as fh:
        for q in queue:
            fh.write(json.dumps(q) + "\n")
    # Typed relationships: never merges.
    rel = []
    for d in decisions:
        if d["contradictions"] and any(e["type"] == "NAME_EXACT_NORMALISED" for e in d["evidence"]):
            rel.append({"type": "SAME_NAME_DIFFERENT_IDENTIFIER", "a": d["a"], "b": d["b"],
                        "note": "possible related entities (e.g. trustee/trust, group members) or reused name; not merged",
                        "evidence": d["evidence"], "contradictions": d["contradictions"]})
    for k, r in recs.items():
        if r["grain"] in ("establishment", "licence_or_permit", "contract_or_grant") and k in linked:
            rel.append({"type": {"establishment": "OPERATES_ESTABLISHMENT", "licence_or_permit": "HOLDS_LICENCE",
                                 "contract_or_grant": "PARTY_TO_CONTRACT"}[r["grain"]],
                        "entity": key_of[k], "record": k})
    with open(OUT_IDENTITY / "relationships.jsonl", "w", encoding="utf-8") as fh:
        for x in rel:
            fh.write(json.dumps(x) + "\n")
    ent_sources = defaultdict(set)
    for k, e in key_of.items():
        ent_sources[e].add(recs[k]["source_id"])
    cross = {e: s for e, s in ent_sources.items() if len(s) > 1}
    by_rule, by_reason, by_strata, by_sources = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    for d in links:
        by_rule[d["rule"]] += 1
        by_strata["+".join(sorted([recs[d["a"]]["stratum"] or "?", recs[d["b"]]["stratum"] or "?"]))] += 1
        by_sources[" <-> ".join(sorted([recs[d["a"]]["source_id"], recs[d["b"]]["source_id"]]))] += 1
    for q in queue:
        by_reason[q["reason"]] += 1
    summary = {"policy_version": POLICY_VERSION, "threshold": THRESHOLD, "records": len(recs),
               "business_records": sum(r["is_business"] for r in recs.values()),
               "candidate_pairs": len(decisions), "links": len(links), "links_by_rule": dict(by_rule),
               "links_by_sample_strata": dict(by_strata), "links_by_source_pair": dict(by_sources),
               "review_pairs": sum(d["decision"] == "REVIEW" for d in decisions),
               "rejected_pairs": sum(d["decision"] == "REJECT" for d in decisions),
               "non_match_pairs": sum(d["decision"] == "NON_MATCH" for d in decisions),
               "abstained_pairs": sum(d["decision"] == "ABSTAIN" for d in decisions),
               "entities_in_multiple_sources": len(cross),
               "unlinked_queue": len(queue), "unlinked_by_reason": dict(by_reason),
               "records_with_no_plausible_candidate": sum(1 for k, r in recs.items() if r["is_business"]
                                                          and k not in linked and k not in best_refusal),
               "relationships": len(rel), "oversized_blocks_skipped": len(res["oversized_blocks"])}
    (OUT_IDENTITY / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_IDENTITY / "entity_membership.json").write_text(json.dumps(
        {"policy_version": POLICY_VERSION, "membership": key_of}, indent=0), encoding="utf-8")
    return summary
