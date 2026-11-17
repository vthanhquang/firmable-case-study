"""Change signals (review 4.3): diff claims between two snapshots, and between reporting periods.

Snapshot diffing is generic. Claims are grouped by the stable entity refs the mapping declares: a licence
keyed by its number, a site by its site code, the business by its record key. Field changes become typed
events. Only entities present in the sampled rows of the OLD snapshot are compared, so "new" entities
can't be detected from a sample; removals and changes can.
  ENTERED_DISTRESS      status detail moved into a distress code (crosswalk signal: distress)
  DEREGISTERED          entity.status became deregistered
  STATUS_CHANGED / STATUS_DETAIL_CHANGED / NAME_CHANGED / REVENUE_BAND_CHANGED
  LICENCE_REMOVED / ESTABLISHMENT_REMOVED / LICENCE_STATUS_CHANGED / LICENCE_CONDITION_EVENT / PROGRAM_CHANGED
  FIELD_CHANGED         any other claim change
Period events come from financial facts of the same business in different periods (any source):
  REVENUE_YOY           growth between consecutive periods (derived, L2)
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .. import crosswalk
from ..identity import resolve as R
from ..mapping.engine import Engine
from ..paths import ROOT
from ..sources.readers import iter_records
from ..sources.select import load_manifest
from . import OUT_RD_EVAL, OUT_RD_OBS
from .extract import load_ext_config

SECOND_SNAPSHOTS = {"qbcc_licensees": "data/raw/qbcc_licensees_live_20261112"}
TYPED = {"entity.status": "STATUS_CHANGED", "ext.entity.status_detail": "STATUS_DETAIL_CHANGED",
         "entity.legal_name": "NAME_CHANGED", "ext.financial.revenue_band": "REVENUE_BAND_CHANGED",
         "ext.licence.status": "LICENCE_STATUS_CHANGED", "ext.establishment.program": "PROGRAM_CHANGED"}


def _distress_codes() -> set[str]:
    entries = crosswalk.load("asic_company_status").get("entries") or {}
    return {f"{k}: {v['label']}" for k, v in entries.items() if (v or {}).get("signal") == "distress"}


def view(obs: list[dict]) -> dict[str, dict[str, set]]:
    out = defaultdict(lambda: defaultdict(set))
    for o in obs:
        if o.get("privacy") == "personal":
            continue
        out[o.get("entity_ref") or o["source_record_id"]][o["field"]].add(json.dumps(o["value"], default=str))
    return out


def diff(old: dict, new: dict, sid: str, old_sha: str, new_sha: str, observed_at: str | None = None) -> list[dict]:
    distress = {json.dumps(c) for c in _distress_codes()}
    events = []

    def ev(kind, ref, **kw):
        events.append({"event_type": kind, "source_id": sid, "entity_ref": ref, "old_snapshot": old_sha[:16],
                       "new_snapshot": new_sha[:16], "detected_from": "snapshot diff", "derivation_level": "L1",
                       **({"new_observed_at": observed_at} if observed_at else {}), **kw})

    for ref in sorted(old):
        if ref not in new:
            kind = ref.split(":")[0] if ":" in ref else "record"
            ev({"licence": "LICENCE_REMOVED", "establishment": "ESTABLISHMENT_REMOVED"}.get(kind, "RECORD_REMOVED"), ref)
            continue
        for field in sorted(set(old[ref]) | set(new[ref])):
            a, b = old[ref].get(field, set()), new[ref].get(field, set())
            if a == b:
                continue
            values = {"old": sorted(json.loads(x) for x in a), "new": sorted(json.loads(x) for x in b)}
            if field == "ext.entity.status_detail" and (b & distress) and not (a & distress):
                ev("ENTERED_DISTRESS", ref, field=field, **values)
            elif field == "entity.status" and '"deregistered"' in b:
                ev("DEREGISTERED", ref, field=field, **values)
            elif field == "ext.licence.status_event" and b - a:
                ev("LICENCE_CONDITION_EVENT", ref, field=field, **values)
            else:
                ev(TYPED.get(field, "FIELD_CHANGED"), ref, field=field, **values)
    return events


def snapshot_events(sid: str, new_path: str) -> tuple[list[dict], dict]:
    """Run the source's mapping over the sampled rows of the stored snapshot and over the same entities in a
    newer file, then diff. Matching uses the key columns the mapping declares for each role."""
    from .store import iter_rows
    cfg, prov = load_ext_config(sid)
    man = load_manifest()[sid]
    path = ROOT / new_path
    if not path.exists():
        return [], {"source_id": sid, "status": f"no second snapshot at {new_path}"}
    keys = [b.key_paths for b in (cfg.entities or {}).values() if b.key_paths]
    key_cols = keys[0] if keys else cfg.record_id.source_paths
    old_rows = [r["row"] for r in iter_rows(sid) if r["stratum"] != "cohort_ext"]
    wanted = {tuple((row.get(c) or "").strip() for c in key_cols) for row in old_rows}
    new_rows, n_new = [], 0
    for rec in iter_records(path, cfg.reader):
        n_new += 1
        if tuple((rec.get(c) or "").strip() for c in key_cols) in wanted:
            new_rows.append(rec)
    meta_new = man | {"resource_last_modified": None}
    old_eng, new_eng = Engine(cfg, man), Engine(cfg, meta_new)
    old_view = view([o for row in old_rows for o in old_eng.process(row)])
    new_view = view([o for row in new_rows for o in new_eng.process(row)])
    import hashlib
    new_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    events = diff(old_view, new_view, sid, man["snapshot"]["sha256"], new_sha)
    return events, {"source_id": sid, "mapping": prov, "key_columns": key_cols, "old_rows_compared": len(old_rows),
                    "new_file_rows": n_new, "matched_in_new_file": len(new_rows),
                    "events": dict(Counter(e["event_type"] for e in events)),
                    "note": "compares the sampled entities only; new entities are not detectable from a sample"}


def period_events() -> list[dict]:
    """REVENUE_YOY from financial facts in any extension observations, grouped by ABN (or record)."""
    facts = defaultdict(lambda: defaultdict(dict))
    abn_of = {}
    rows = []
    for f in sorted(OUT_RD_OBS.glob("*.jsonl")):
        if f.name.endswith(".edges.jsonl"):
            continue
        for line in open(f, encoding="utf-8"):
            o = json.loads(line)
            k = f"{o['source_id']}::{o['source_record_id']}"
            if o["field"] == "entity.abn":
                abn_of[k] = o["value"]
            elif o["field"].startswith("ext.financial.") and o["field"] != "ext.financial.revenue_band":
                rows.append((k, o))
    for k, o in rows:
        who = "abn:" + abn_of[k] if k in abn_of else k
        period = (o.get("qualifiers") or {}).get("period")
        if period:
            facts[(who, o["field"].split(".")[-1])][period] = o
    events = []
    for (who, measure), periods in sorted(facts.items()):
        ordered = sorted(periods)
        for prev, cur in zip(ordered, ordered[1:]):
            a, b = periods[prev]["value"], periods[cur]["value"]
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)) or a == 0:
                continue
            events.append({"event_type": "REVENUE_YOY" if measure == "total_income" else f"{measure.upper()}_YOY",
                           "entity": who, "measure": measure, "from_period": prev, "to_period": cur,
                           "old": a, "new": b, "growth": round((b - a) / abs(a), 4), "derivation_level": "L2",
                           "detected_from": "period comparison",
                           "inputs": [periods[prev]["observation_id"], periods[cur]["observation_id"]],
                           "sources": sorted({periods[prev]["source_id"], periods[cur]["source_id"]})})
    return events


def run() -> dict:
    OUT_RD_EVAL.mkdir(parents=True, exist_ok=True)
    events, reports = [], {}
    for sid, path in SECOND_SNAPSHOTS.items():
        ev, rep = snapshot_events(sid, path)
        events += ev
        reports[sid] = rep
    pe = period_events()
    events += pe
    with open(OUT_RD_EVAL / "change_events.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for e in events:
            fh.write(json.dumps(e, default=str) + "\n")
    summary = {"snapshot_diffs": reports, "period_events": dict(Counter(e["event_type"] for e in pe)),
               "events_total": len(events), "by_type": dict(Counter(e["event_type"] for e in events))}
    (OUT_RD_EVAL / "change_events_summary.json").write_text(json.dumps(summary, indent=1, default=str),
                                                            encoding="utf-8", newline="\n")
    return summary
