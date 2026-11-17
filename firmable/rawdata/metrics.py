"""Measurement for the raw-data work (review section 8), computed from the output files, never restated by hand."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from .. import crosswalk
from ..extract import load_config
from ..paths import RUNS
from . import OUT_RAWDATA, OUT_RD_EVAL, OUT_RD_IDENTITY, OUT_RD_MAPPINGS, OUT_RD_OBS, OUT_RD_PROFILES
from .extract import load_ext_config
from .review import approval_state

CONTENT_MIN_SHARE = 0.01


def _columns(cfg) -> set:
    used = set()
    for r in cfg.fields:
        used.update(r.source_paths)
        used.update(p for p in (r.valid_from_path, r.valid_to_path) if p)
        used.update(q.source_path for q in (r.qualifiers or {}).values() if q.source_path)
        if r.when:
            used.add(r.when.source_path)
    for b in (cfg.entities or {}).values():
        used.update(b.key_paths)
    used.update(cfg.record_id.source_paths)
    return used


def column_usage() -> dict:
    """Raw columns, columns with content, and columns any rule reads - approved config vs extension config."""
    from .store import iter_rows
    out = {}
    for f in sorted(OUT_RD_OBS.glob("*.sample.json")):
        sid = f.name.split(".")[0]
        present, n = Counter(), 0
        for r in iter_rows(sid):
            n += 1
            for k, v in r["row"].items():
                if v is not None and str(v).strip() not in ("", "NULL"):
                    present[k] += 1
            for k in r["row"]:
                present.setdefault(k, 0)
        cols = set(present)
        content = {c for c in cols if present[c] / max(n, 1) >= CONTENT_MIN_SHARE and not c.startswith(("_", "column_"))}
        base, _ = load_config(sid)
        ext, prov = load_ext_config(sid)
        before, after = _columns(base) & cols, _columns(ext) & cols
        out[sid] = {"raw_columns": len(cols), "columns_with_content": len(content),
                    "read_by_approved_config": len(before), "read_by_extension_config": len(after),
                    "content_columns_still_unread": sorted(content - after), "extension_mapping": prov["mapping"]}
    tot = {k: sum(v[k] for v in out.values()) for k in ("raw_columns", "columns_with_content",
                                                          "read_by_approved_config", "read_by_extension_config")}
    return {"by_source": out, "total": tot,
            "note": "columns counted over the stored sample rows; 'content' = non-blank in >= 1% of rows"}


def coverage() -> dict:
    """Share of entities that gained each firmographic, over all entities and over multi-source entities."""
    membership = json.loads((OUT_RD_IDENTITY / "entity_membership.json").read_text(encoding="utf-8"))["membership"]
    has = defaultdict(set)
    sources = defaultdict(set)
    business = set()
    checks = {"industry_code": "ext.entity.industry_code", "financial_fact": "ext.financial.total_income",
              "revenue_band": "ext.financial.revenue_band", "date_established": "ext.entity.date_established",
              "legal_form": "ext.entity.legal_form", "status_detail": "ext.entity.status_detail",
              "former_name": "ext.entity.former_name", "operating_region": "ext.entity.operating_region",
              "sector_tag": "ext.entity.sector_tag"}
    rev = {v: k for k, v in checks.items()}
    for f in sorted(OUT_RD_OBS.glob("*.jsonl")):
        if f.name.endswith(".edges.jsonl"):
            continue
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            k = f"{o['source_id']}::{o['source_record_id']}"
            e = membership.get(k)
            if e is None:
                continue
            sources[e].add(o["source_id"])
            if o["field"] in ("entity.abn", "entity.acn", "entity.legal_name", "entity.trading_name"):
                business.add(e)
            if o["field"] in rev:
                has[rev[o["field"]]].add(e)
            if o.get("entity_role") not in (None, "subject"):
                has["establishment_or_licence"].add(e)
            if o["field"].startswith("ext.contact.") and o.get("privacy") != "personal":
                has["contact_point"].add(e)
    multi = {e for e in business if len(sources[e]) > 1}
    share = lambda pool: {k: {"entities": len(v & pool), "share": round(len(v & pool) / max(len(pool), 1), 3)}
                          for k, v in sorted(has.items())}
    return {"business_entities": len(business), "multi_source_entities": len(multi),
            "all_entities": share(business), "multi_source": share(multi),
            "baseline_note": "before the extension the case-study profiles had none of these fields "
                             "(industry_code was in the core ontology but no approved config mapped it)"}


def agent_cost() -> dict:
    from ..costing import report, read_ledger, summarize_rows
    costs = report()
    rows = read_ledger(OUT_RAWDATA / "usage_ledger.jsonl")
    groups = defaultdict(list)
    for row in rows:
        groups[row["source_id"]].append(row)
    by_source = {}
    for sid, source_rows in sorted(groups.items()):
        summary = summarize_rows(source_rows, costs["pricing"])
        by_source[sid] = {"runs": len({r["run_id"] for r in source_rows}), "calls": summary["calls"],
            "transient_errors": summary["failed_calls_without_usage"], "tokens": summary["total_tokens"],
            "input_tokens": summary["input_tokens"], "output_tokens": summary["output_tokens"],
            "estimated_usd": summary["estimated_usd"]}
    extension = costs["scopes"]["extension"]
    return {"by_source": by_source, "total_tokens": extension["total_tokens"],
            "total_estimated_usd": extension["estimated_usd"],
            "rate": "Declared DeepSeek Flash off-peak input/output tariff; estimate, not invoiced spend",
            "per_record_model_cost_usd": 0.0, "cost_report": costs}


def review_state() -> dict:
    out = {}
    for p in sorted(OUT_RD_MAPPINGS.glob("*.json")):
        sid = p.stem
        doc = json.loads(p.read_text(encoding="utf-8"))
        st = json.loads((RUNS / sid / doc["run_id"] / "state.json").read_text(encoding="utf-8"))
        last = st["proposals"][-1] if st["proposals"] else {}
        verdicts = Counter(f["verdict"] for f in (last.get("critic") or {}).get("fields", []))
        tables = sorted({s["args"]["table"] for r in doc["config"]["fields"] for s in r.get("steps", [])
                         if s["op"] == "crosswalk"})
        out[sid] = {"status": doc["status"], "approval_state": approval_state(sid), "run_id": doc["run_id"],
                    "proposals_in_run": len(st["proposals"]), "tool_calls": st["tool_calls"],
                    "critic_verdicts": dict(verdicts), "revised_after_feedback": bool(st.get("human_feedback")),
                    "feedback_source": st.get("feedback_source"), "crosswalks": tables,
                    "crosswalks_reviewed": [t for t in tables if not str(crosswalk.load(t).get("review_status", "")).startswith("draft")]}
    return out


def privacy() -> dict:
    out = Counter()
    for f in sorted(OUT_RD_OBS.glob("*.sample.json")):
        rep = json.loads(f.read_text(encoding="utf-8")).get("engine_report", {})
        for field in rep.get("fields", []):
            for code, n in (field.get("dropped") or {}).items():
                out[code] += n
    personal = 0
    for f in sorted(OUT_RD_OBS.glob("*.jsonl")):
        if not f.name.endswith(".edges.jsonl"):
            personal += sum('"privacy": "personal"' in line for line in open(f, encoding="utf-8"))
    return {"values_dropped": dict(out), "observations_flagged_personal": personal,
            "profiles": "personal contact points are withheld from profiles and counted only"}


def run() -> dict:
    def load(path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    identity = load(OUT_RD_IDENTITY / "summary.json") or {}
    report = {"columns": column_usage(), "coverage": coverage(), "agent_cost": agent_cost(),
              "review_state": review_state(), "privacy": privacy(),
              "matching": {k: identity.get(k) for k in ("challenger", "strict_v2_on_same_observations",
                                                          "relationships", "records_by_stratum")}
              | {"comparison": {k: v for k, v in (identity.get("comparison") or {}).items()
                                if not isinstance(v, list)}},
              "deletion_impact_v3": load(OUT_RD_EVAL / "source_deletion_impact_v3.json"),
              "financial_corruption_v3": load(OUT_RD_EVAL / "financial_corruption_v3.json"),
              "change_events": load(OUT_RD_EVAL / "change_events_summary.json"),
              "profiles_v3": sum(1 for _ in open(OUT_RD_PROFILES / "company_profiles_v3_50.jsonl", encoding="utf-8"))
              if (OUT_RD_PROFILES / "company_profiles_v3_50.jsonl").exists() else 0}
    OUT_RD_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_RD_EVAL / "raw_data_metrics.json").write_text(json.dumps(report, indent=1, default=str),
                                                       encoding="utf-8", newline="\n")
    return report
