"""Part 3: conservative cross-source entity resolution.

Model (see WRITEUP): identity is a DECISION about source records, written to a pairwise decision log
with evidence and policy version. Each resolution run replaces the log. Entities are derived: clusters formed only
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

Strict-v2 adds holder and registered-name ambiguity checks. Evidence-v3 keeps those vetoes,
refers conflicting licence holder names, and scores eligible links using observed claim quality,
name distinctiveness, and location evidence. Each link retains the score contributions.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from math import log1p

from ..paths import OUT_IDENTITY, OUT_OBS, ROOT

EVIDENCE_POLICY = "evidence-v3"
POLICIES = ("strict-v1", "strict-v2", EVIDENCE_POLICY)
POLICY_VERSION = json.loads((ROOT / "config" / "matcher_policy.json").read_text(encoding="utf-8"))["active_policy"]
if POLICY_VERSION not in POLICIES:
    raise ValueError(f"Unknown active matcher policy {POLICY_VERSION!r}")
THRESHOLD = 0.85          # strict: precision audit runs at this threshold
LOOSE_THRESHOLD = 0.75    # exploratory: reported separately, never mixed into the strict number
MAX_BLOCK = 50            # name blocks larger than this are too generic to compare pairwise
PLAUSIBLE_NAME_SIM = 0.85 # an ID conflict below this name similarity is a confident NON_MATCH, not a refusal
HOLDER_MISMATCH_RULE = "abn_equal_but_person_vs_company"
LICENCE_NAME_MISMATCH_RULE = "identifier_equal_but_licence_name_conflicts"
REVIEW_VETOES = {HOLDER_MISMATCH_RULE: "IDENTIFIER_HOLDER_MISMATCH",
                 LICENCE_NAME_MISMATCH_RULE: "IDENTIFIER_LICENCE_NAME_MISMATCH"}
POSITIVE_EVIDENCE = {"ABN_EQUAL_VALID", "ACN_EQUAL_VALID", "ABN_CONTAINS_ACN",
                     "NAME_EXACT_NORMALISED", "NAME_SIMILARITY", "LOCATION_AGREES"}
NAME_FIELDS = {"entity.legal_name", "entity.trading_name"}
MATCH_FIELDS = NAME_FIELDS | {"entity.abn", "entity.acn"}

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


def load_records(exclude: set[str] = frozenset(), *, observations=None) -> dict:
    """(source_id, record_id) -> record view of its observations."""
    recs = {}
    for f in sorted((observations or OUT_OBS).glob("*.jsonl")):
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            if o["source_id"] in exclude:
                continue
            k = f"{o['source_id']}::{o['source_record_id']}"
            r = recs.setdefault(k, {"key": k, "source_id": o["source_id"], "record_id": o["source_record_id"],
                                    "grain": o["record_grain"], "stratum": o.get("sample_stratum"),
                                    "f": defaultdict(list), "claim_quality": {}})
            field, value = o["field"], o["value"]
            if o.get("claim_scope") == "former_legal_name":
                continue
            r["f"][field].append(value)
            if field in MATCH_FIELDS and o.get("derivation_level") != "L3":
                confidence = o.get("confidence", {})
                quality = (confidence.get("field_confidence") or 0) * (confidence.get("source_reliability") or 0)
                key = (field, norm_name(value) if field in NAME_FIELDS else value)
                r["claim_quality"][key] = max(quality, r["claim_quality"].get(key, 0))
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


def _baseline_evidence(a: dict, b: dict, policy: str) -> tuple[float, str, list, list]:
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
            return 0.80, HOLDER_MISMATCH_RULE, ev, contra
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


def _shared_quality(a: dict, b: dict, field: str, values: set) -> float:
    qa, qb = a.get("claim_quality", {}), b.get("claim_quality", {})
    return max((min(qa.get((field, value), 0), qb.get((field, value), 0)) for value in values), default=0)


def _name_quality(record: dict, value: str) -> float:
    quality = record.get("claim_quality", {})
    return max(quality.get((field, value), 0) for field in NAME_FIELDS)


def evidence(a: dict, b: dict, policy: str = POLICY_VERSION, *, token_counts=None,
             record_count: int = 0) -> tuple[float, str, list, list]:
    baseline = "strict-v2" if policy == EVIDENCE_POLICY else policy
    score, rule, ev, contra = _baseline_evidence(a, b, baseline)
    # The challenger only ranks candidates the strict policy could accept. Vetoes,
    # holder review and ambiguous-name abstentions keep their original decisions.
    if policy != EVIDENCE_POLICY or score < THRESHOLD:
        return score, rule, ev, contra

    exact = a["names"] & b["names"]
    name_only = rule.startswith("registered_name_exact")
    if name_only:
        exact = {name for name in exact if is_registered_company_name(name)}
    legal_exact = exact & a["legal"] & b["legal"]
    if (not name_only and a["legal"] and b["legal"] and not legal_exact and
            (a.get("grain") == "licence_or_permit") != (b.get("grain") == "licence_or_permit")):
        legal_similarity = max(name_sim(x, y) for x in a["legal"] for y in b["legal"])
        if legal_similarity < 0.45:
            ev.append({"type": "LICENCE_HOLDER_NAME_CONFLICT", "value": round(legal_similarity, 4)})
            return 0.80, LICENCE_NAME_MISMATCH_RULE, ev, contra
    common = legal_exact or exact
    distinctiveness = 0.0
    if common and token_counts is not None and record_count:
        scale = log1p(record_count)
        distinctiveness = max((sum(log1p(record_count / max(token_counts[t], 1)) / scale for t in tokens)
                               / (len(tokens) + 1)
                               for name in common if (tokens := set(name_core(name).split()))), default=0)
    name_quality = max((min(_name_quality(a, name), _name_quality(b, name)) for name in common), default=0)
    postcode = bool(a["postcode"] & b["postcode"])
    locality = bool(a["locality"] & b["locality"])
    location = 0.016 if postcode else 0.009 if locality else 0.0
    if name_only:
        base = 0.817
        parts = {"name_claim_quality": 0.039 * name_quality, "distinctive_name_tokens": 0.024 * distinctiveness,
                 "legal_names_agree": 0.009 * bool(legal_exact), "matching_location": location}
    else:
        abn_quality = _shared_quality(a, b, "entity.abn", a["abn"] & b["abn"])
        acn_quality = _shared_quality(a, b, "entity.acn", a["acn"] & b["acn"])
        base = {"abn_equal": 0.925, "acn_equal": 0.912, "abn_contains_acn_and_name": 0.869}[rule]
        similarity = max((signal["value"] for signal in ev if signal["type"] == "NAME_SIMILARITY"), default=0)
        parts = {"identifier_claim_quality": 0.024 * max(abn_quality, acn_quality),
                 "name_claim_quality": 0.022 * name_quality,
                 "distinctive_name_tokens": 0.009 * distinctiveness,
                 "legal_names_agree": 0.009 * bool(legal_exact), "matching_location": 0.5 * location,
                 "names_disagree": -0.025 * (1 - similarity) if not exact and a["legal"] and b["legal"] else 0}
    score = round(min(0.997, base + sum(parts.values())), 4)
    ev.append({"type": "EVIDENCE_SCORE_COMPONENTS", "value": {"rule_base": base, **{
        key: round(value, 4) for key, value in parts.items() if value
    }}})
    return score, rule, ev, contra


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

    def __init__(self, recs, review_pairs=()):
        self.parent = {}
        self.ids = {}
        self.members = {}
        self.review_neighbors = defaultdict(set)
        for a, b in review_pairs:
            self.review_neighbors[a].add(b)
            self.review_neighbors[b].add(a)
        for k, r in recs.items():
            self.parent[k] = k
            self.ids[k] = {"abn": set(r["abn"]), "acn": set(r["acn"])}
            self.members[k] = {k}

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
        if any(self.review_neighbors.get(member, set()) & self.members[rb] for member in self.members[ra]):
            return "CLUSTER_WOULD_JOIN_HOLDER_MISMATCH"
        self.parent[rb] = ra
        self.members[ra].update(self.members.pop(rb))
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


# Rules whose pairs are DIFFERENT entities with a stated relationship (e.g. a licensed individual working for
# the company whose ABN the licence register records): never linked, never queued as a doubtful match.
NON_LINK_RELATIONSHIP_RULES = {"licensed_individual_for_company"}


def resolve(exclude: set[str] = frozenset(), threshold: float = THRESHOLD, policy: str = POLICY_VERSION,
            *, score_reference=None, observations=None, recs=None, extra_pairs=(), evidence_fn=None) -> dict:
    """`recs`, `extra_pairs` and `evidence_fn` let a challenger policy (rawdata.match) add record evidence,
    candidate pairs and scoring while reusing this decision loop and the cluster constraints unchanged."""
    if policy not in POLICIES and evidence_fn is None:
        raise ValueError(f"Unknown matcher policy {policy!r}")
    if recs is None:
        recs = load_records(exclude, observations=observations) if observations is not None else load_records(exclude)
    pairs, oversized = candidates(recs)
    pairs |= set(extra_pairs)
    if policy == EVIDENCE_POLICY and score_reference is None:
        score_reference = (len(recs), Counter(t for record in recs.values() for t in {
            token for name in record["names"] for token in name_core(name).split()
        }))
    record_count, token_counts = score_reference or (0, None)
    scored = []
    score_fn = evidence_fn or (lambda a, b: evidence(a, b, policy, token_counts=token_counts, record_count=record_count))
    for a, b in pairs:
        s, rule, ev, contra = score_fn(recs[a], recs[b])
        scored.append({"a": a, "b": b, "score": s, "rule": rule, "evidence": ev, "contradictions": contra})
    scored.sort(key=lambda x: (-x["score"], x["a"], x["b"]))   # strongest evidence merges first
    cl = Clusters(recs, ((d["a"], d["b"]) for d in scored
                         if d["rule"] in REVIEW_VETOES or d["rule"] in NON_LINK_RELATIONSHIP_RULES))
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
        elif p["rule"] in REVIEW_VETOES:
            p["decision"], p["reason"] = "REVIEW", REVIEW_VETOES[p["rule"]]
        elif p["rule"] in NON_LINK_RELATIONSHIP_RULES:
            p["decision"], p["reason"] = "RELATIONSHIP", p["rule"].upper()
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
            "oversized_blocks": oversized, "score_reference": score_reference}


def _rec_summary(r: dict) -> dict:
    return {"source_id": r["source_id"], "record_id": r["record_id"], "grain": r["grain"],
            "names": sorted(r["f"].get("entity.legal_name", []) + r["f"].get("entity.trading_name", []))[:4],
            "abn": sorted(r["abn"]), "acn": sorted(r["acn"]), "postcode": sorted(r["postcode"])}


def _unlinked_queue(recs: dict, decisions: list[dict], linked: set[str]) -> list[dict]:
    def rank(d):
        return -d["score"], -d["name_sim"], d["a"], d["b"]

    best = {}
    for d in sorted(decisions, key=rank):
        if d["decision"] == "LINK" or not any(e["type"] in POSITIVE_EVIDENCE for e in d["evidence"]):
            continue
        for key, other in ((d["a"], d["b"]), (d["b"], d["a"])):
            if key not in linked and recs[key]["is_business"]:
                best.setdefault(key, (d, other))

    queue = []
    for key, (d, other) in best.items():
        reason = d["reason"]
        if d["rule"] == "ambiguous_registered_name":
            reason = "REGISTERED_NAME_NOT_UNIQUE"
        elif reason == "WEAK_NAME_ONLY" and d["name_sim"] >= 0.92:
            reason = "NEAR_NAME_WITHOUT_LOCATION"
        next_action = {
            "CONFLICTING_VALID_IDENTIFIER": "check whether the records describe related entities or a source error",
            "DIFFERENT_IDENTIFIERS_AND_NAMES": "keep separate unless independent evidence resolves the identifier conflict",
            "IDENTIFIER_HOLDER_MISMATCH": "check who holds the licence and whose ABN the source supplied",
            "IDENTIFIER_LICENCE_NAME_MISMATCH": "verify whether the identifier belongs to the named licence holder",
            "BELOW_STRICT_THRESHOLD": "review the available identifier, name and location evidence",
            "AMBIGUOUS_NAME": "seek a common identifier or address",
            "REGISTERED_NAME_NOT_UNIQUE": "use an identifier to distinguish the registered companies",
            "NEAR_NAME_WITHOUT_LOCATION": "check for a shared location or identifier",
            "WEAK_NAME_ONLY": "seek an identifier or shared address before linking",
        }.get(reason, "review cluster constraint")
        queue.append({"source_record": key, "reason": reason, "best_candidate": other,
                      "candidate_decision": d["decision"], "best_score": d["score"], "name_similarity": d["name_sim"],
                      "rule": d["rule"], "evidence": d["evidence"], "contradictions": d["contradictions"],
                      "record": _rec_summary(recs[key]), "candidate": _rec_summary(recs[other]),
                      "next_action": next_action})
    return queue


def run(policy: str | None = None, output=None, *, observations=None) -> dict:
    policy = policy or POLICY_VERSION
    output = output or OUT_IDENTITY
    res = resolve(policy=policy, observations=observations)
    recs, decisions, key_of = res["recs"], res["decisions"], res["key_of"]
    output.mkdir(parents=True, exist_ok=True)
    links = [d for d in decisions if d["decision"] == "LINK"]
    with open(output / "proposed_links.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for d in links:
            fh.write(json.dumps({
                "link_id": "lk_" + hashlib.sha256(f"{d['a']}|{d['b']}|{policy}".encode()).hexdigest()[:16],
                "source_a_record": d["a"], "source_b_record": d["b"],
                "canonical_entity_key": key_of[d["a"]], "confidence": d["score"],
                "confidence_kind": "link_confidence (policy score, not a calibrated probability)",
                "rule": d["rule"], "evidence": d["evidence"], "policy_version": policy,
                "threshold": THRESHOLD, "a": _rec_summary(recs[d["a"]]), "b": _rec_summary(recs[d["b"]]),
                "strata": [recs[d["a"]]["stratum"], recs[d["b"]]["stratum"]]}) + "\n")
    # All decisions, including rejections, are kept: a future matcher must be able to re-score them.
    with open(output / "link_decisions.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for d in decisions:
            fh.write(json.dumps({k: d[k] for k in ("a", "b", "score", "rule", "decision", "reason", "name_sim",
                                                   "evidence", "contradictions")} | {"policy_version": policy}) + "\n")
    linked = {k for d in links for k in (d["a"], d["b"])}
    review_pairs = [d for d in decisions if d["decision"] == "REVIEW"]
    with open(output / "review_queue.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for d in review_pairs:
            fh.write(json.dumps(d | {"policy_version": policy,
                                     "record_a": _rec_summary(recs[d["a"]]),
                                     "record_b": _rec_summary(recs[d["b"]])}) + "\n")
    queue = _unlinked_queue(recs, decisions, linked)
    with open(output / "unlinked_queue.jsonl", "w", encoding="utf-8", newline="\n") as fh:
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
    with open(output / "relationships.jsonl", "w", encoding="utf-8", newline="\n") as fh:
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
    summary = {"policy_version": policy, "threshold": THRESHOLD, "records": len(recs),
               "business_records": sum(r["is_business"] for r in recs.values()),
               "candidate_pairs": len(decisions), "links": len(links), "links_by_rule": dict(by_rule),
               "links_by_sample_strata": dict(by_strata), "links_by_source_pair": dict(by_sources),
               "review_pairs": sum(d["decision"] == "REVIEW" for d in decisions),
               "rejected_pairs": sum(d["decision"] == "REJECT" for d in decisions),
               "non_match_pairs": sum(d["decision"] == "NON_MATCH" for d in decisions),
               "abstained_pairs": sum(d["decision"] == "ABSTAIN" for d in decisions),
               "entities_in_multiple_sources": len(cross),
               "unlinked_queue": len(queue), "unlinked_by_reason": dict(by_reason),
               "unlinked_records_without_positive_candidate": sum(r["is_business"] for k, r in recs.items()
                                                                 if k not in linked) - len(queue),
               "relationships": len(rel), "oversized_blocks_skipped": len(res["oversized_blocks"])}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8", newline="\n")
    (output / "entity_membership.json").write_text(json.dumps(
        {"policy_version": policy, "membership": key_of}, indent=0), encoding="utf-8", newline="\n")
    return summary
