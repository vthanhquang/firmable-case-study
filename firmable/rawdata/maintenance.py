"""Explicit local mapping corrections and a replay path that disables model access.

Corrections create new provenance records; original agent runs and human decisions remain immutable.
The frozen replay sample is regression evidence, not a new unseen holdout.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import runpy
from datetime import datetime, timezone
from pathlib import Path

from ..mapping.schema import MappingConfig
from ..mapping.validate import holdout_issues, static_issues
from ..paths import ROOT, RUNS
from ..sources.select import load_manifest
from . import OUT_RAWDATA, OUT_RD_EVAL, OUT_RD_MAPPINGS
from .audit import mapping_dependencies
from .store import iter_rows


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependencies(config: dict) -> dict:
    return {path.relative_to(ROOT).as_posix(): file_digest(path) for path in mapping_dependencies(config, ROOT)}


def verify_dependencies(doc: dict) -> None:
    expected = doc.get("local_revision", {}).get("dependencies")
    # Historical Windows journals used backslashes; path spelling must not make
    # an unchanged interpretation invalid on Linux/macOS. Keep the byte hashes.
    if expected is not None and {name.replace("\\", "/"): sha for name, sha in expected.items()} != dependencies(doc["config"]):
        raise ValueError("Local correction dependencies changed; validate a new revision before replay")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def apply_bundle(path: Path) -> dict:
    os.environ["FIRMABLE_OFFLINE"] = "1"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    bundle_sha = file_digest(path)
    manifest = load_manifest()
    prepared, unchanged = [], []
    for change in bundle["revisions"]:
        sid = change["source_id"]
        if sid not in manifest:
            raise ValueError("Unknown source " + sid)
        current = json.loads((OUT_RD_MAPPINGS / (sid + ".json")).read_text(encoding="utf-8"))
        if current.get("local_revision", {}).get("bundle_sha256") == bundle_sha:
            verify_dependencies(current)
            unchanged.append(sid)
            continue
        if current["config_digest"] != change["expected_config_digest"]:
            raise ValueError("Correction baseline changed for " + sid)
        cfg = MappingConfig.model_validate(change["config"])
        if cfg.source_id != sid or current["snapshot_sha256"] != manifest[sid]["snapshot"]["sha256"]:
            raise ValueError("Correction source or snapshot mismatch")
        rows = [item["row"] for item in iter_rows(sid)]
        if len(rows) < 2:
            raise ValueError("Need frozen sample records to validate " + sid)
        columns = set().union(*(row.keys() for row in rows))
        # The frozen store concatenates random and targeted records. Avoid comparing
        # those acquisition strata as if they were discovery/holdout distributions.
        random.Random(20261117).shuffle(rows)
        split = max(1, len(rows) // 4)
        issues, report = holdout_issues(cfg, rows[:split], rows[split:], manifest[sid])
        issues = static_issues(cfg, columns) + issues
        errors = [issue for issue in issues if issue["severity"] == "error"]
        if errors:
            raise ValueError(sid + " failed local validation: " + json.dumps(errors))
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-local-" + cfg.digest()[:8]
        revision = {"kind": "maintainer_correction", "actor": bundle["actor"], "reason": change["reason"],
                    "parent_run_id": current["run_id"], "parent_config_digest": current["config_digest"],
                    "bundle_sha256": bundle_sha, "dependencies": dependencies(cfg.model_dump()),
                    "model_calls": 0, "validation_scope": "Frozen replay sample partition; not an unseen holdout"}
        proposal = {"round": 1, "digest": cfg.digest(), "config": cfg.model_dump(),
                    "holdout_report": report, "holdout_issues": issues,
                    "critic": {"fields": [], "missed": [], "summary": "No model critic called. Local deterministic regression checks; semantic corrections documented in the revision."}}
        state = {"source_id": sid, "run_id": run_id, "status": "PENDING_REVIEW", "started_at": now,
                 "finished_at": now, "snapshot_sha256": current["snapshot_sha256"], "final_digest": cfg.digest(),
                 "model": "local-maintainer", "critic_model": "Not called (local correction)", "tool_calls": 0,
                 "proposals": [proposal], "local_revision": revision,
                 "stages": [{"stage": "LOCAL_CORRECTION_VALIDATED", "at": now}, {"stage": "PENDING_REVIEW", "at": now}]}
        doc = current | {"run_id": run_id, "status": "PENDING_REVIEW", "model": "local-maintainer",
                         "config": cfg.model_dump(), "config_digest": cfg.digest(), "local_revision": revision}
        prepared.append((sid, current, doc, state))
        print(sid + ": local correction validated", flush=True)
    # No proposal is replaced unless the whole bundle passes its regression gates.
    for sid, previous, doc, state in prepared:
        folder = RUNS / sid / state["run_id"]
        write_json(folder / "parent_mapping.json", previous)
        write_json(folder / "state.json", state)
        write_json(OUT_RD_MAPPINGS / (sid + ".json"), doc)
    result = {"bundle_sha256": bundle_sha, "updated": [item[0] for item in prepared], "unchanged": unchanged,
              "model_calls": 0, "approval": "New mapping digests require human sign-off"}
    write_json(OUT_RD_EVAL / "local_mapping_revision.json", result)
    return result


def replay(sync_demo: bool = False) -> dict:
    os.environ["FIRMABLE_OFFLINE"] = "1"
    from . import extract, match, profiles, changes, metrics
    ledger_paths = [RUNS / "usage_ledger.jsonl", OUT_RAWDATA / "usage_ledger.jsonl"]
    before = {str(path): file_digest(path) if path.exists() else None for path in ledger_paths}
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "mode": "local_frozen_sample",
              "model_calls_disabled": True, "stages": []}
    path = OUT_RD_EVAL / "local_replay.json"
    try:
        for name, fn in (("extract", extract.run), ("resolve", match.run), ("profiles", profiles.run),
                         ("changes", changes.run), ("metrics", metrics.run)):
            print("Local replay: " + name, flush=True)
            fn()
            report["stages"].append(name)
            write_json(path, report)
        if sync_demo:
            runpy.run_path(str(ROOT / "frontend/scripts/sync-raw-demo.py"), run_name="__main__")
            report["stages"].append("sync_demo")
        report["status"] = "complete"
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        raise
    finally:
        after = {str(p): file_digest(p) if p.exists() else None for p in ledger_paths}
        report["usage_ledgers_unchanged"] = before == after
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(path, report)
        if before != after:
            raise RuntimeError("Usage ledger changed during local replay")
    return report
