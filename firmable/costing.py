"""Reprice recorded token usage without changing historical billing evidence or calling a model."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .paths import ROOT, RUNS


def load_pricing() -> dict:
    return json.loads((ROOT / "config/report_pricing.json").read_text(encoding="utf-8"))


def call_cost(row: dict, pricing: dict) -> tuple[str, float | None]:
    if row.get("model") != pricing["model"]:
        return "unpriced", None
    when = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
    from datetime import timezone
    when = when.astimezone(timezone.utc)
    peak = when.weekday() < 5 and when.date().isoformat() not in pricing["holiday_dates"] and any(
        start <= when.hour < end for start, end in pricing["peak_utc_hours"])
    band = "peak" if peak else "off_peak"
    rate = pricing[band + "_per_million"]
    inp, out = row.get("prompt_tokens", 0), row.get("completion_tokens", 0)
    cached = min(inp, max(0, row.get("cached_input_tokens", 0)))
    cost = ((inp - cached) * rate["input"] + cached * rate["cached_input"] + out * rate["output"])
    return band, cost / 1_000_000 * (1 - pricing["discount_fraction"])


def summarize_rows(rows: list[dict], pricing: dict) -> dict:
    buckets = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0})
    unpriced = set()
    for row in rows:
        band, cost = call_cost(row, pricing)
        if cost is None:
            unpriced.add(row.get("model"))
        bucket = buckets[band]
        bucket["calls"] += 1
        bucket["input_tokens"] += row.get("prompt_tokens", 0)
        bucket["output_tokens"] += row.get("completion_tokens", 0)
        bucket["estimated_usd"] += cost or 0
    result = {"calls": len(rows), "input_tokens": sum(r.get("prompt_tokens", 0) for r in rows),
              "output_tokens": sum(r.get("completion_tokens", 0) for r in rows),
              "failed_calls_without_usage": sum(bool(r.get("error")) and not (r.get("prompt_tokens") or r.get("completion_tokens")) for r in rows),
              "unpriced_models": sorted(unpriced),
              "estimated_usd": round(sum(x["estimated_usd"] for x in buckets.values()), 6)}
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    result["bands"] = {name: bucket | {"estimated_usd": round(bucket["estimated_usd"], 6)} for name, bucket in sorted(buckets.items())}
    return result


def read_ledger(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def report() -> dict:
    pricing = load_pricing()
    paths = {"base_and_triage": RUNS / "usage_ledger.jsonl", "extension": ROOT / "outputs/raw-data/usage_ledger.jsonl"}
    ledgers = {name: read_ledger(path) for name, path in paths.items()}
    all_rows = [row for rows in ledgers.values() for row in rows]
    source_rows = defaultdict(list)
    for row in all_rows:
        source_rows[row["source_id"]].append(row)
    doc = json.loads((ROOT / "outputs/raw-data/mappings/asic_companies.json").read_text())
    run_id = doc.get("local_revision", {}).get("parent_run_id", doc["run_id"])
    state = json.loads((RUNS / "asic_companies" / run_id / "state.json").read_text())
    example = summarize_rows([r for r in all_rows if r["run_id"] == run_id and r["source_id"] == "asic_companies"], pricing)
    example.update(source_id="asic_companies", run_id=run_id, tool_calls=state["tool_calls"],
                   proposal_rounds=len(state["proposals"]), recorded_stages=len(state["stages"]),
                   wall_seconds=int((datetime.fromisoformat(state["finished_at"]) - datetime.fromisoformat(state["started_at"])).total_seconds()))
    return {"pricing": pricing, "scopes": {name: summarize_rows(rows, pricing) for name, rows in ledgers.items()},
            "total": summarize_rows(all_rows, pricing), "by_source": {sid: summarize_rows(rows, pricing) for sid, rows in sorted(source_rows.items())},
            "example_onboarding": example, "per_record_model_usd": 0,
            "receipts": {"coverage": "Partial billing snapshots only; complete actual project spend is not known.",
                         "measured_window_usd": 3.0214, "measured_window_tokens": 1925132,
                         "path": "runs/billing_snapshots.jsonl"}}
