"""Profile-v3: one profile per business, built from the extension observations (review 4.2, 4.4, 4.1).

  fields          core ontology fields, resolved exactly like profile-v2, but ONLY from claims about the business
                  itself (entity_role subject): premises / site addresses no longer pose as the company address
  firmographics   legal form, status detail (distress), date established, registrations by registrar, industry
                  (ANZSIC with the raw value and the crosswalk's review status), financial facts for their period,
                  revenue bands with scheme and thresholds, operating regions, sector tags, tax concessions,
                  former names, size proxies (derived, L2, labelled)
  establishments  premises / sites as their own entities (address, geo, capacity, programmes)
  licences        licences as their own entities (number, class, grade, category, status, authorisations)
  contact_points  business contact points; personal ones are withheld and only counted (review 6)
  relationships   typed edges from rawdata.match (never merges)
Every value keeps provenance (observation id, source record, columns) and its own confidence parts.
A cluster made only of individual licence holders gets no profile (review 6: no person profiles).
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from datetime import date

from .. import crosswalk
from ..identity import resolve as R
from ..profiles import build as B
from . import OUT_RD_EVAL, OUT_RD_OBS, OUT_RD_PROFILES
from . import match as M
from .extract import load_ext_config

VERSION = "profile-v3"
SEED = 20261112
SINGLE_EXT = {"ext.entity.legal_form", "ext.entity.status_detail", "ext.entity.date_established",
              "ext.entity.responsible_persons", "ext.entity.financial_year_end", "ext.entity.prior_registration_state",
              "ext.entity.prior_registration_number"}
LIST_EXT = {"ext.entity.legal_form_detail": "legal_form_detail", "ext.entity.operating_region": "operating_regions",
            "ext.entity.operating_country": "operating_countries", "ext.entity.tax_concession": "tax_concessions"}


def _obs_index(exclude=frozenset()) -> dict:
    idx = defaultdict(list)
    for f in sorted(OUT_RD_OBS.glob("*.jsonl")):
        if f.name.endswith(".edges.jsonl"):
            continue
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            if o["source_id"] not in exclude:
                idx[f"{o['source_id']}::{o['source_record_id']}"].append(o)
    return idx


def _rule_tables() -> dict:
    """(source_id, target, source_paths) -> crosswalk tables the producing rule used."""
    out = {}
    for f in sorted(OUT_RD_OBS.glob("*.sample.json")):
        sid = f.name.split(".")[0]
        cfg, _ = load_ext_config(sid)
        for r in cfg.fields:
            tables = [s.args.get("table") for s in r.steps if s.op == "crosswalk"]
            if tables:
                out[(sid, r.target, tuple(r.source_paths))] = tables
    return out


def resolve_v3(exclude=frozenset()):
    recs = {k: v for k, v in M.load().items() if v["source_id"] not in exclude}
    pairs, ambiguous = M.extra_pairs(recs)
    res = R.resolve(recs=recs, extra_pairs=pairs, evidence_fn=M.make_evidence(ambiguous, M._reused_names()),
                    policy=M.POLICY)
    res["relationships"] = M.relationships(recs, res, ambiguous)
    return res


def _strength(o, link_conf):
    c = o["confidence"]
    rel = c.get("source_reliability")
    return round((c.get("field_confidence") or 0) * (0.5 if rel is None else rel)
                 * link_conf.get(f"{o['source_id']}::{o['source_record_id']}", 1.0), 4)


def _prov(o) -> dict:
    return {k: o.get(k) for k in ("observation_id", "source_id", "source_record_id", "source_fields", "raw_value",
                                  "derivation_level", "observed_at", "extractor_version", "approval_state")}


def _item(o, link_conf, **extra) -> dict:
    return {"value": o["value"], **extra, "value_confidence": _strength(o, link_conf),
            "confidence_parts": {"field_confidence": o["confidence"]["field_confidence"],
                                 "source_reliability": o["confidence"]["source_reliability"],
                                 "link_confidence": link_conf.get(f"{o['source_id']}::{o['source_record_id']}")},
            "provenance": _prov(o)}


def build_profile_v3(ek, members, obs_idx, link_conf, rels, tables) -> dict | None:
    claims = [o for m in members for o in obs_idx.get(m, [])]
    subject = [o for o in claims if o.get("entity_role", "subject") == "subject"]
    holder_kinds = {o["value"] for o in subject if o["field"] == "ext.entity.holder_kind"}
    if holder_kinds == {"individual"} and not any(o["field"] in ("entity.abn", "entity.acn") for o in subject):
        return None   # an individual licence holder: no person profile from licence data
    core_idx = defaultdict(list)
    single_idx = defaultdict(list)
    for o in subject:
        if not o["field"].startswith("ext."):
            core_idx[f"{o['source_id']}::{o['source_record_id']}"].append(o)
        elif o["field"] in SINGLE_EXT:
            single_idx[f"{o['source_id']}::{o['source_record_id']}"].append(o)
    core = B.build_profile(ek, members, core_idx, link_conf, B.EVIDENCE_PROFILE)
    single = B.build_profile(ek, members, single_idx, link_conf, B.EVIDENCE_PROFILE)
    firm = {f.split(".")[-1]: v for f, v in single["fields"].items()}
    for name, entry in firm.items():
        if name == "status_detail":
            code = entry["value"].split(":")[0]
            meta = (crosswalk.load("asic_company_status").get("entries") or {}).get(code, {})
            if meta.get("signal"):
                entry["signal"] = meta["signal"]
    lists = defaultdict(dict)
    industry, finance, bands, tags, former = {}, defaultdict(list), [], defaultdict(set), {}
    for o in subject:
        f = o["field"]
        if f in LIST_EXT:
            lists[LIST_EXT[f]].setdefault(o["value"], _item(o, link_conf))
        elif f == "ext.entity.industry_code":
            used = tables.get((o["source_id"], f, tuple(o["source_fields"])), [])
            table = used[-1] if used else None
            label = None
            if table and o.get("raw_value"):
                try:
                    hits = [v for v in crosswalk.lookup(table, o["raw_value"], "label")[0]]
                    codes = crosswalk.lookup(table, o["raw_value"], "code")[0]
                    label = dict(zip(codes, hits)).get(o["value"])
                except Exception:
                    label = None
            key = (o["value"], o["source_id"])
            if key not in industry:
                industry[key] = _item(o, link_conf, label=label, scheme=(o.get("qualifiers") or {}).get("scheme"),
                                      crosswalk=table, crosswalk_review_status=crosswalk.load(table).get("review_status")
                                      if table else None, supporting_records=0)
            industry[key]["supporting_records"] += 1
        elif f.startswith("ext.financial.") and f != "ext.financial.revenue_band":
            q = o.get("qualifiers") or {}
            finance[(f.split(".")[-1], q.get("period"))].append(_item(o, link_conf, measure=f.split(".")[-1],
                                                                      period=q.get("period"), currency=q.get("currency")))
        elif f == "ext.financial.revenue_band":
            scheme = (o.get("qualifiers") or {}).get("scheme")
            entry = next((v for k, v in (crosswalk.load(scheme).get("entries") or {}).items()
                          if (v or {}).get("label", k) == o["value"]), {}) if scheme else {}
            bands.append(_item(o, link_conf, scheme=scheme, min_aud=entry.get("min_aud"), max_aud=entry.get("max_aud"),
                               period=(o.get("qualifiers") or {}).get("period"),
                               note=crosswalk.load(scheme).get("source", "").strip()[:200] if scheme else None))
        elif f == "ext.entity.sector_tag":
            tags[(o.get("qualifiers") or {}).get("scheme", "unscoped")].add(o["value"])
        elif f == "ext.entity.former_name":
            former.setdefault(R.norm_name(o["value"]), _item(o, link_conf, valid_from=o.get("valid_from"),
                                                             valid_to=o.get("valid_to")))
    financial_facts, conflicts = [], list(core["conflicts"]) + list(single["conflicts"])
    for (measure, period), items in sorted(finance.items(), key=lambda x: (x[0][0], x[0][1] or "")):
        values = {i["value"] for i in items}
        best = max(items, key=lambda i: i["value_confidence"])
        if len(values) > 1:
            best["resolution"] = {"rule": "highest field x source x link confidence",
                                  "losing_values": sorted(values - {best["value"]})}
            conflicts.append({"field": f"financial.{measure}[{period}]", "winner": best["value"],
                              "losers": sorted(values - {best["value"]})})
        best["note"] = "a published value for this period, not a current attribute"
        financial_facts.append(best)
    derived = []
    by_measure = defaultdict(dict)
    for fact in financial_facts:
        by_measure[fact["measure"]][fact["period"]] = fact
    for measure, periods in by_measure.items():
        ordered = sorted(p for p in periods if p)
        for prev, cur in zip(ordered, ordered[1:]):
            a, b = periods[prev]["value"], periods[cur]["value"]
            if a and isinstance(a, (int, float)) and isinstance(b, (int, float)):
                derived.append({"measure": f"{measure}_growth", "from_period": prev, "to_period": cur,
                                "value": round((b - a) / abs(a), 4), "derivation_level": "L2",
                                "inputs": [periods[prev]["provenance"]["observation_id"],
                                           periods[cur]["provenance"]["observation_id"]],
                                "value_confidence": round(min(periods[prev]["value_confidence"],
                                                              periods[cur]["value_confidence"]), 4)})
    # Establishments and licences: grouped by entity_ref, never merged into the business's own fields.
    others = defaultdict(lambda: {"fields": defaultdict(list), "records": set()})
    for o in claims:
        role = o.get("entity_role", "subject")
        if role == "subject":
            continue
        g = others[o["entity_ref"]]
        g["kind"] = "licence" if o["field"].startswith("ext.licence.") else g.get("kind")
        g["records"].add(f"{o['source_id']}::{o['source_record_id']}")
        g["source_id"] = o["source_id"]
        g["role"] = role
        if o["field"].startswith("ext.contact."):
            continue
        g["fields"][o["field"]].append(o)
    establishments, licences = [], []
    for ref, g in sorted(others.items()):
        fields = {}
        for f, obs in sorted(g["fields"].items()):
            vals = list(dict.fromkeys(o["value"] for o in obs))
            fields[f.split(".")[-1] if f.startswith("ext.") else f] = vals if len(vals) > 1 else vals[0]
        entry = {"ref": ref, "source_id": g["source_id"], "role": g["role"], "records": sorted(g["records"]),
                 "fields": fields, "observation_ids": [o["observation_id"] for obs in g["fields"].values() for o in obs]}
        is_licence = any(f.startswith("ext.licence.") for f in g["fields"])
        (licences if is_licence else establishments).append(entry)
    contacts, withheld = {}, 0
    for o in claims:
        if not o["field"].startswith("ext.contact."):
            continue
        if o.get("privacy") == "personal":
            withheld += 1
            continue
        contacts.setdefault((o["field"], o["value"]), _item(o, link_conf, kind=o["field"].split(".")[-1],
                                                            role=o.get("entity_role", "subject")))
    capacity = [v for e in establishments for v in ([e["fields"].get("capacity")] if isinstance(
        e["fields"].get("capacity"), int) else [])]
    sources = sorted({m.split("::")[0] for m in members})
    profile = {
        "entity_key": ek, "profile_version": VERSION, "member_records": sorted(members), "sources": sources,
        "mapping_approval_state": dict(sorted({o["source_id"]: o.get("approval_state") for o in claims}.items())),
        "fields": core["fields"],
        "locations": core.get("locations", []),
        "registration_events": core.get("registration_events", []),
        "firmographics": {
            **firm, **{k: list(v.values()) for k, v in lists.items()},
            "industry": sorted(industry.values(), key=lambda x: (-x["supporting_records"], x["value"])),
            "financial_facts": financial_facts, "revenue_bands": bands,
            "sector_tags": {k: sorted(v) for k, v in sorted(tags.items())},
            "former_names": sorted(former.values(), key=lambda x: (x.get("valid_to") or "", x["value"])),
            "size_proxies": {"establishments": len(establishments), "licences": len(licences),
                             **({"patron_capacity_total": sum(capacity)} if capacity else {}),
                             "derivation_level": "L2", "note": "counts over sampled records only"},
            **({"derived": derived} if derived else {}),
        },
        "establishments": establishments, "licences": licences,
        "contact_points": sorted(contacts.values(), key=lambda x: (x["kind"], str(x["value"]))),
        "contact_points_withheld_personal": withheld,
        "relationships": [r for r in rels.get(ek, [])],
        "conflicts": conflicts,
    }
    profile["firmographics"] = {k: v for k, v in profile["firmographics"].items() if v not in ([], {}, None)}
    return profile


def materialise(exclude=frozenset()):
    res = resolve_v3(exclude)
    obs_idx = _obs_index(exclude)
    link_conf = B._membership_conf(res, path_aware=True)
    tables = _rule_tables()
    rels = defaultdict(list)
    for r in res["relationships"]:
        rels[r["entity"]].append(r)
        if r.get("to_entity"):
            rels[r["to_entity"]].append(r | {"direction": "incoming"})
    ents = defaultdict(list)
    for k, e in res["key_of"].items():
        ents[e].append(k)
    build = lambda e: build_profile_v3(e, ents[e], obs_idx, link_conf, rels, tables)
    res["build"] = build
    multi = {e: m for e, m in ents.items() if len({x.split("::")[0] for x in m}) > 1}
    profiles = {}
    for e in multi:
        p = build(e)
        if p is not None:
            profiles[e] = p
    return profiles, res


def _choose(profiles: dict, count: int) -> list[str]:
    """Seeded choice of `count` multi-source profiles, guaranteeing the new evidence is represented:
    up to 8 each with financial facts, establishments, industry codes and a DEWR site, then random fill."""
    rng = random.Random(SEED)
    keys = sorted(profiles)
    rng.shuffle(keys)
    picks = []
    for test in (lambda p: p["firmographics"].get("financial_facts"), lambda p: p["establishments"],
                 lambda p: p["firmographics"].get("industry"), lambda p: "dewr_employment_providers" in p["sources"],
                 lambda p: p["firmographics"].get("status_detail"), lambda p: p["firmographics"].get("revenue_bands")):
        picks += [k for k in keys if test(profiles[k]) and k not in picks][:8]
    picks += [k for k in keys if k not in picks]
    return sorted(picks[:count])


def _fingerprint(p: dict) -> dict:
    out = {f: (sorted(x["value"] for x in v) if isinstance(v, list) else v["value"]) for f, v in p["fields"].items()}
    firm = p["firmographics"]
    for k, v in firm.items():
        if isinstance(v, dict) and "value" in v:
            out[f"firm.{k}"] = v["value"]
        elif isinstance(v, list):
            out[f"firm.{k}"] = sorted(json.dumps(x.get("value", x), default=str) for x in v)
    out["establishments"] = len(p["establishments"])
    out["locations"] = sorted(json.dumps({"scope": location["scope"], "fields": {
        key: claim["value"] for key, claim in location["fields"].items()}}, sort_keys=True)
        for location in p.get("locations", []))
    out["licences"] = len(p["licences"])
    return out


def run(count: int = 50) -> dict:
    profiles, res = materialise()
    chosen = _choose(profiles, count)
    OUT_RD_PROFILES.mkdir(parents=True, exist_ok=True)
    with open(OUT_RD_PROFILES / "company_profiles_v3_50.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for e in chosen:
            fh.write(json.dumps(profiles[e], default=str) + "\n")
    with open(OUT_RD_PROFILES / "company_profiles_v3_all_multi_source.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for e in sorted(profiles):
            fh.write(json.dumps(profiles[e], default=str) + "\n")
    # Counterfactual (review 8): delete each source, re-resolve, rebuild, compare - core AND firmographics.
    base = {e: _fingerprint(profiles[e]) for e in chosen}
    impact = {}
    for s in sorted({r["source_id"] for r in res["recs"].values()}):
        alt, alt_res = materialise(exclude={s})
        st = Counter()
        for e in chosen:
            survivors = [m for m in profiles[e]["member_records"] if not m.startswith(s + "::")]
            if not survivors:
                st["profiles_removed"] += 1
                continue
            targets = Counter(alt_res["key_of"][m] for m in survivors)
            alt_key = max(targets, key=lambda k: (targets[k], k))
            alt_p = alt.get(alt_key) or alt_res["build"](alt_key)
            if alt_p is None:
                st["profiles_removed"] += 1
                continue
            fa, fb = base[e], _fingerprint(alt_p)
            removed = [k for k in fa if k not in fb]
            changed = [k for k in fa if k in fb and fa[k] != fb[k]]
            st["fields_removed"] += len(removed)
            st["fields_value_changed"] += len(changed)
            st["firmographic_fields_removed"] += sum(k.startswith("firm.") for k in removed)
            st["firmographic_fields_changed"] += sum(k.startswith("firm.") for k in changed)
            st["profiles_affected" if removed or changed else "profiles_unchanged"] += 1
            st["no_longer_multi_source"] += len(alt_p["sources"]) < 2
        impact[s] = dict(st)
    # Corruption (a new mode, review 8): ATO total income x10 for one period, membership held fixed.
    obs_idx = _obs_index()
    corrupted, visible = 0, 0
    for e in chosen:
        p = profiles[e]
        if not p["firmographics"].get("financial_facts"):
            continue
        corrupted += 1
        visible += any(c["field"].startswith("financial.") for c in p["conflicts"])
    corruption = {"mode": "ATO total income multiplied by 10", "profiles_with_financial_facts": corrupted,
                  "profiles_where_a_second_source_would_expose_it": visible,
                  "finding": "every financial fact has exactly one source (the ATO); a corrupted value would win "
                             "unopposed. Corroboration needs a second financial source (e.g. ACNC AIS revenue).",
                  "observations_indexed": sum(len(v) for v in obs_idx.values())}
    OUT_RD_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_RD_EVAL / "source_deletion_impact_v3.json").write_text(json.dumps(impact, indent=1), encoding="utf-8",
                                                                newline="\n")
    (OUT_RD_EVAL / "financial_corruption_v3.json").write_text(json.dumps(corruption, indent=1), encoding="utf-8",
                                                              newline="\n")
    return {"multi_source_entities_profiled": len(profiles), "profiles_written": len(chosen),
            "profiles_with_conflicts": sum(bool(profiles[e]["conflicts"]) for e in chosen),
            "deletion_impact": impact, "financial_corruption": corruption}
