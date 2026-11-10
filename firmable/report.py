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
    usage = llm.summarize()
    out = []
    for doc_path in sorted(OUT_MAPPINGS.glob("*.json")):
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        sid, rid = doc_path.stem, doc["run_id"]
        st = json.loads((RUNS / sid / rid / "state.json").read_text(encoding="utf-8"))
        u = usage.get((sid, rid), {})
        approvals = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
        last = json.loads(approvals.read_text(encoding="utf-8").splitlines()[-1]) if approvals.exists() else None
        out.append({"source_id": sid, "run_id": rid, "status": st["status"], "proposals": len(st["proposals"]),
                    "revisions": len(st["proposals"]) - 1, "logical_stages": len(st["stages"]),
                    "tool_calls": st["tool_calls"], "model_calls": u.get("calls", 0),
                    "transient_errors": u.get("errors", 0),
                    "prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0),
                    "model_latency_s": round(u.get("latency_ms", 0) / 1000, 1), "wall_clock_s": round(_wall(st), 1),
                    "fields_mapped": len(doc["config"]["fields"]), "unmapped": len(doc["config"]["unmapped"]),
                    "approval": (last or {}).get("decision"), "approved_by": (last or {}).get("reviewer_kind")})
    return out


def triage(name: str = "triage_audit_20.csv") -> dict:
    p = OUT_EVAL / name
    if not p.exists():
        return {}
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    c = Counter(r["label"] for r in rows)
    data_rows = [r for r in rows if r["basis"].startswith("data")]
    cd = Counter(r["label"] for r in data_rows)
    return {"sampled": len(rows), "labels": dict(c),
            "false_positive_rate_decided": round(c["NO"] / max(c["YES"] + c["NO"], 1), 3),
            "false_positive_rate_uncertain_as_no": round((c["NO"] + c["UNCERTAIN"]) / len(rows), 3),
            "data_verified_subset": dict(cd)}


def run() -> str:
    from .identity.audit import score
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
    if (OUT_EVAL / "link_audit_50.csv").exists():
        m["link_audit"] = score()
    if (OUT_EVAL / "source_deletion_impact.json").exists():
        imp = json.loads((OUT_EVAL / "source_deletion_impact.json").read_text(encoding="utf-8"))
        m["source_deletion"] = {s: {k: v for k, v in d.items() if k != "examples"} for s, d in imp.items()}
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
    (OUT_EVAL / "run_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    lines = ["| source | agent status | review | revisions | stages | tool calls | model calls | prompt tok | completion tok | wall s |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for o in ob:
        lines.append(f"| {o['source_id']} | {o['status']} | {o['approval']} ({o['approved_by']}) | {o['revisions']} | "
                     f"{o['logical_stages']} | {o['tool_calls']} | "
                     f"{o['model_calls']} | {o['prompt_tokens']:,} | {o['completion_tokens']:,} | {o['wall_clock_s']} |")
    return "\n".join(lines)
