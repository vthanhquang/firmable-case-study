"""Collect the measured numbers into outputs/evaluation/run_metrics.json (+ a printable summary)."""
from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter

from . import llm
from .paths import OUT_EVAL, OUT_IDENTITY, OUT_MAPPINGS, OUT_OBS, OUT_PROFILES, RUNS


def _wall(st: dict) -> float:
    a = dt.datetime.fromisoformat(st["started_at"])
    b = dt.datetime.fromisoformat(st.get("finished_at") or st["stages"][-1]["at"])
    return (b - a).total_seconds()


def onboarding() -> list[dict]:
    from .agent.review import current_review

    usage = llm.summarize()
    ledger = []
    if llm.LEDGER.exists():
        with llm.LEDGER.open(encoding="utf-8") as fh:
            ledger = [json.loads(line) for line in fh]
    out = []
    for doc_path in sorted(OUT_MAPPINGS.glob("*.json")):
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        sid, rid = doc_path.stem, doc["run_id"]
        st = json.loads((RUNS / sid / rid / "state.json").read_text(encoding="utf-8"))
        u = usage.get((sid, rid), {})
        last = current_review(sid, doc)
        effort = None
        if last and last["decision"] == "approved":
            through = dt.datetime.fromisoformat(last["decided_at"])
            calls = [row for row in ledger if row["source_id"] == sid and not row.get("error")
                     and dt.datetime.fromisoformat(row["ts"]) <= through]
            prices = [llm.usd(row["model"], row["prompt_tokens"], row["completion_tokens"]) for row in calls]
            effort = {"tokens": sum(row["prompt_tokens"] + row["completion_tokens"] for row in calls),
                      "calls": len(calls), "reviewer_kind": last["reviewer_kind"],
                      "estimated_usd": round(sum(prices), 4) if calls and all(p is not None for p in prices) else None}
        out.append({"source_id": sid, "run_id": rid, "status": st["status"], "proposals": len(st["proposals"]),
                    "revisions": len(st["proposals"]) - 1, "logical_stages": len(st["stages"]),
                    "tool_calls": st["tool_calls"], "model_calls": u.get("calls", 0),
                    "transient_errors": u.get("errors", 0),
                    "prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0),
                    "model_latency_s": round(u.get("latency_ms", 0) / 1000, 1), "wall_clock_s": round(_wall(st), 1),
                    "fields_mapped": len(doc["config"]["fields"]), "unmapped": len(doc["config"]["unmapped"]),
                    "approval": (last or {}).get("decision"), "approved_by": (last or {}).get("reviewer_kind"),
                    "review_minutes": (last or {}).get("review_minutes"), "effort_through_approval": effort})
    return out


def audit_reviewer_kind(row: dict) -> str:
    reviewer = (row.get("reviewer") or "").strip()
    kind = row.get("reviewer_kind")
    if "AI assistant" in reviewer:
        return "ai_assistant_proxy"
    return kind if reviewer and kind in {"human", "ai_assistant_proxy"} else "unverified"


def proxy_agreement(before: list[dict], after: list[dict]) -> dict:
    comparisons = [a["label"] == b["label"] for a, b in zip(before, after)
                   if audit_reviewer_kind(a) == "ai_assistant_proxy" and audit_reviewer_kind(b) == "human"]
    return {"compared": len(comparisons), "agreed": sum(comparisons),
            "rate": round(sum(comparisons) / len(comparisons), 3) if comparisons else None}


def triage_scores(rows: list[dict]) -> dict:
    c = Counter(r["label"] for r in rows)
    data_rows = [r for r in rows if r["basis"].startswith("data")]
    cd = Counter(r["label"] for r in data_rows)
    decided = c["YES"] + c["NO"]
    return {"sampled": len(rows), "labels": dict(c),
            "false_positive_rate_decided": round(c["NO"] / decided, 3) if decided else None,
            "false_positive_rate_uncertain_as_no": round((c["NO"] + c["UNCERTAIN"]) / len(rows), 3) if rows else None,
            "data_verified_subset": dict(cd)}


def triage(name: str = "triage_audit_20.csv") -> dict:
    p = OUT_EVAL / name
    if not p.exists():
        return {}
    with p.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    from .review_workbook import reviewed_rows

    reviewed = reviewed_rows("triage", rows, OUT_EVAL) if name == "triage_audit_20.csv" else rows
    human = [r for r in reviewed if audit_reviewer_kind(r) == "human" and r["label"] in {"YES", "NO", "UNCERTAIN"}]
    return triage_scores(rows) | {
        "reviewer_kinds": dict(Counter(map(audit_reviewer_kind, reviewed))),
        "human_review": {"reviewed": len(human), "remaining": len(rows) - len(human),
                         "scores": triage_scores(human) if human else None,
                         "agreement_with_proxy": proxy_agreement(rows, reviewed)},
    }


def link_audits(path) -> dict:
    from .identity.audit import ACTIVE_AUDIT_CSV, score_rows
    from .review_workbook import reviewed_rows

    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    scores = score_rows(rows)
    active = path.name == ACTIVE_AUDIT_CSV
    reviewed = reviewed_rows("strict_v2_links" if active else "strict_links", rows, path.parent)
    historical_proxy = {}
    historical = path.with_name("link_audit_50.csv")
    if active and historical.exists():
        with historical.open(encoding="utf-8", newline="") as fh:
            historical_proxy = {(r["record_a"], r["record_b"]): r for r in csv.DictReader(fh)
                                if r["band"] == "strict" and audit_reviewer_kind(r) == "ai_assistant_proxy"}
    for band, audit in scores.items():
        baseline_rows = [r for r in rows if r["band"] == band]
        band_rows = [r for r in reviewed if r["band"] == band]
        human = [r for r in band_rows if audit_reviewer_kind(r) == "human"]
        audit["reviewer_kinds"] = dict(Counter(map(audit_reviewer_kind, band_rows)))
        audit["human_review"] = {"reviewed": len(human), "remaining": len(band_rows) - len(human),
                                 "scores": score_rows(human).get(band),
                                 "agreement_with_proxy": proxy_agreement(baseline_rows, band_rows)}
        if active:
            overlap = [historical_proxy.get((r["record_a"], r["record_b"]), {}) for r in band_rows]
            audit["human_review"]["agreement_with_historical_proxy"] = proxy_agreement(overlap, band_rows)
            audit["historical_proxy_overlap"] = sum(bool(row) for row in overlap)
            audit["sample_groups"] = dict(Counter(r["sample_group"] for r in band_rows))
            audit["human_review"]["scores_by_sample_group"] = {
                group: score_rows(r for r in human if r["sample_group"] == group).get(band)
                for group in audit["sample_groups"]}
    return scores


def run() -> str:
    from .identity.audit import ACTIVE_AUDIT_CSV

    ob = onboarding()
    tot_p = sum(o["prompt_tokens"] for o in ob)
    tot_c = sum(o["completion_tokens"] for o in ob)
    all_usage = llm.summarize()
    m = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "model": llm.DEFAULT_MODEL, "price_per_mtok_known": llm.PRICE_PER_MTOK.get(llm.DEFAULT_MODEL) is not None,
         "onboarding": ob,
         "onboarding_tokens_final_runs": {"prompt": tot_p, "completion": tot_c},
         "all_llm_usage_including_dev_and_superseded_runs": {
             "calls": sum(v["calls"] for v in all_usage.values()),
             "prompt_tokens": sum(v["prompt_tokens"] for v in all_usage.values()),
             "completion_tokens": sum(v["completion_tokens"] for v in all_usage.values())},
         "triage_audit": triage(),
         "triage_audit_v2_column_reranker_experiment": triage("triage_audit_v2_20.csv")}
    for f, key in ((OUT_IDENTITY / "summary.json", "identity"),):
        if f.exists():
            m[key] = json.loads(f.read_text(encoding="utf-8"))
    link_audit_path = OUT_EVAL / "link_audit_50.csv"
    if link_audit_path.exists():
        m["link_audit_strict_v1"] = link_audits(link_audit_path)
    active_audit_path = OUT_EVAL / ACTIVE_AUDIT_CSV
    if m.get("identity", {}).get("policy_version") == "strict-v2" and active_audit_path.exists():
        m["link_audit"] = link_audits(active_audit_path)
    elif m.get("identity", {}).get("policy_version") == "strict-v1" and link_audit_path.exists():
        m["link_audit"] = m["link_audit_strict_v1"]
    if (OUT_EVAL / "source_deletion_impact.json").exists():
        imp = json.loads((OUT_EVAL / "source_deletion_impact.json").read_text(encoding="utf-8"))
        m["source_deletion"] = {s: {k: v for k, v in d.items() if k != "examples"} for s, d in imp.items()}
    corruption = OUT_EVAL / "source_corruption_impact.json"
    if corruption.exists():
        m["source_corruption"] = json.loads(corruption.read_text(encoding="utf-8"))
    stab = OUT_EVAL / "agent_stability_rerun-v3.json"
    if stab.exists():
        s = json.loads(stab.read_text(encoding="utf-8"))
        m["agent_stability"] = {k: v for k, v in s.items() if k != "per_source"}
    obs = {}
    for f in OUT_OBS.glob("*.sample.json"):
        s = json.loads(f.read_text(encoding="utf-8"))
        obs[s["source_id"]] = {k: s[k] for k in ("records_in_resource", "sample_size", "random", "cohort", "observations")}
    m["extraction"] = obs
    if (OUT_PROFILES / "company_profiles_50.jsonl").exists():
        profs = [json.loads(l) for l in open(OUT_PROFILES / "company_profiles_50.jsonl", encoding="utf-8")]
        m["profiles"] = {"count": len(profs), "with_conflicts": sum(1 for p in profs if p["conflicts"]),
                         "avg_fields": round(sum(len(p["fields"]) for p in profs) / max(len(profs), 1), 1),
                         "sources_per_profile": dict(Counter(len(p["sources"]) for p in profs))}
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_EVAL / "run_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8", newline="\n")
    lines = ["| source | agent status | review | revisions | stages | tool calls | model calls | prompt tok | completion tok | wall s |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for o in ob:
        lines.append(f"| {o['source_id']} | {o['status']} | {o['approval']} ({o['approved_by']}) | {o['revisions']} | "
                     f"{o['logical_stages']} | {o['tool_calls']} | "
                     f"{o['model_calls']} | {o['prompt_tokens']:,} | {o['completion_tokens']:,} | {o['wall_clock_s']} |")
    return "\n".join(lines)
