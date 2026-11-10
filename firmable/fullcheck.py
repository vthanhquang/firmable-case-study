"""Run an APPROVED config, unchanged, over an alternative (e.g. complete) snapshot of the same resource.

Used to test "config, not code" under load: the QBCC config was approved on a 32k-row prefix; this runs it over
all 195k rows (fetched by `fetch.datastore_all`) through the engine and the current gates. No model calls.

    python -m firmable.fullcheck qbcc_licensees qbcc_licensees_full
"""
from __future__ import annotations

import json
import sys
import time

from .agent.workspace import Workspace
from .extract import load_config
from .mapping.engine import Engine
from .mapping.validate import holdout_issues
from .paths import OUT_EVAL, ROOT
from .sources.readers import iter_records
from .sources.select import load_manifest


def run(source_id: str, snapshot_name: str | None = None) -> dict:
    """snapshot_name=None: the source's own approved snapshot, i.e. measure the config over the WHOLE resource."""
    cfg, _ = load_config(source_id)
    src = dict(load_manifest()[source_id])
    if snapshot_name:
        meta = json.loads((ROOT / "data" / "raw" / f"{snapshot_name}.meta.json").read_text(encoding="utf-8"))
        src["snapshot"] = {"path": meta["path"].replace("\\", "/"), "sha256": meta["sha256"]}
    else:
        meta = src["snapshot"]
        snapshot_name = "approved_snapshot"
    t0 = time.perf_counter()
    eng = Engine(cfg, src)
    for rec in iter_records(ROOT / src["snapshot"]["path"], cfg.reader):
        eng.process(rec)
    rep = eng.report()
    ws = Workspace(src)
    disc, hold, _, _ = ws.pool(cfg.reader)
    issues, _ = holdout_issues(cfg, disc, hold, src)
    out = {"source_id": source_id, "snapshot": snapshot_name, "snapshot_sha256": meta["sha256"],
           "config_digest": cfg.digest(), "config_unchanged": True, "rows": rep["records_in"],
           "rows_with_output": rep["records_with_output"], "seconds": round(time.perf_counter() - t0, 1),
           "fields": [{k: f[k] for k in ("target", "source_present", "emitted", "error_rate_of_present", "errors")}
                      for f in rep["fields"]],
           "gate_errors": [i["code"] + ":" + str(i.get("target")) for i in issues if i["severity"] == "error"],
           "gate_warnings": [i["code"] + ":" + str(i.get("target")) for i in issues if i["severity"] == "warning"]}
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    name = f"{source_id}_full_register_check.json" if snapshot_name != "approved_snapshot" else f"{source_id}_full_scale.json"
    (OUT_EVAL / name).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def _work(args):
    cfg_json, meta, chunk = args
    from .mapping.schema import MappingConfig
    eng = Engine(MappingConfig.model_validate_json(cfg_json), meta)
    for rec in chunk:
        eng.process(rec)
    return eng.report()


def parallel_stats(source_id: str, workers: int = 4, chunk: int = 50_000) -> dict:
    """Partitioned extraction: the reader streams chunks, worker processes run the engine, statistics are merged.
    Record ids that rely on in-order duplicate counters are per chunk here, so this mode is for measurement, not
    for writing observations."""
    from concurrent.futures import ProcessPoolExecutor
    from itertools import islice
    cfg, _ = load_config(source_id)
    src = load_manifest()[source_id]
    it = iter_records(ROOT / src["snapshot"]["path"], cfg.reader)
    t0 = time.perf_counter()
    rows = emitted = 0
    errors = {}
    with ProcessPoolExecutor(workers) as ex:
        futs = []
        while True:
            part = list(islice(it, chunk))
            if not part:
                break
            futs.append(ex.submit(_work, (cfg.model_dump_json(), src, part)))
        for f in futs:
            r = f.result()
            rows += r["records_in"]
            for fld in r["fields"]:
                emitted += fld["emitted"]
                for k, v in fld["errors"].items():
                    errors[f"{fld['target']}:{k}"] = errors.get(f"{fld['target']}:{k}", 0) + v
    secs = time.perf_counter() - t0
    return {"source_id": source_id, "workers": workers, "rows": rows, "emitted": emitted, "errors": errors,
            "seconds": round(secs, 1), "rows_per_second": round(rows / secs)}


def _bases(args):
    cfg_json, chunk = args
    from .mapping.engine import record_base
    from .mapping.schema import MappingConfig
    cfg = MappingConfig.model_validate_json(cfg_json)
    empty = lambda r: not r or all(v is None or str(v).strip() == "" for v in r.values())
    return [None if empty(r) else record_base(r, cfg) for r in chunk]


def _emit(args):
    cfg_json, meta, ingested_at, chunk, rids = args
    import hashlib
    from .mapping.schema import MappingConfig
    eng = Engine(MappingConfig.model_validate_json(cfg_json), meta, ingested_at=ingested_at)
    h, n = hashlib.sha256(), 0
    for rec, rid in zip(chunk, rids):
        for o in eng.process(rec, rid=rid):
            h.update(o["observation_id"].encode())
            n += 1
    return h.hexdigest(), n


def parallel_extract_digest(source_id: str, workers: int = 6, chunk: int = 50_000) -> dict:
    """Two-phase partitioned extraction that yields exactly the serial observations:
    phase 1 (parallel) computes order-independent base keys; the main process numbers duplicates in file
    order, as the serial engine does; phase 2 (parallel) emits observations with those keys. Returns a digest
    over every observation id in file order (chunk digests chained), comparable with `serial_extract_digest`."""
    import hashlib
    from collections import Counter
    from concurrent.futures import ProcessPoolExecutor
    from itertools import islice
    from .mapping.engine import number_duplicate
    cfg, _ = load_config(source_id)
    src = load_manifest()[source_id]
    cfg_json, t0 = cfg.model_dump_json(), time.perf_counter()
    parts = []
    it = iter_records(ROOT / src["snapshot"]["path"], cfg.reader)
    while True:
        part = list(islice(it, chunk))
        if not part:
            break
        parts.append(part)
    with ProcessPoolExecutor(workers) as ex:
        bases = list(ex.map(_bases, [(cfg_json, p) for p in parts]))
        seen = Counter()
        rids = [[None if b is None else number_duplicate(b, seen) for b in bs] for bs in bases]
        results = list(ex.map(_emit, [(cfg_json, src, "fixed", p, r) for p, r in zip(parts, rids)]))
    h = hashlib.sha256()
    for d, _ in results:
        h.update(d.encode())
    return {"digest": h.hexdigest(), "observations": sum(n for _, n in results),
            "seconds": round(time.perf_counter() - t0, 1)}


def serial_extract_digest(source_id: str, chunk: int = 50_000) -> dict:
    """The serial engine, digested with the same chunk boundaries, for an exact comparison."""
    import hashlib
    cfg, _ = load_config(source_id)
    src = load_manifest()[source_id]
    eng, t0 = Engine(cfg, src, ingested_at="fixed"), time.perf_counter()
    outer, inner, n, i = hashlib.sha256(), hashlib.sha256(), 0, 0
    for rec in iter_records(ROOT / src["snapshot"]["path"], cfg.reader):
        for o in eng.process(rec):
            inner.update(o["observation_id"].encode())
            n += 1
        i += 1
        if i % chunk == 0:
            outer.update(inner.hexdigest().encode())
            inner = hashlib.sha256()
    if i % chunk:
        outer.update(inner.hexdigest().encode())
    return {"digest": outer.hexdigest(), "observations": n, "seconds": round(time.perf_counter() - t0, 1)}


def all_sources() -> dict:
    """Every approved config over its entire resource: mapping quality at full scale, not on a sample."""
    from .paths import OUT_MAPPINGS
    out = {}
    for p in sorted(OUT_MAPPINGS.glob("*.json")):
        r = run(p.stem)
        out[p.stem] = {"rows": r["rows"], "rows_with_output": r["rows_with_output"], "seconds": r["seconds"],
                       "worst_field_error_rate": max((f["error_rate_of_present"] for f in r["fields"]), default=0),
                       "gate_errors": r["gate_errors"]}
        print(p.stem, out[p.stem], flush=True)
    (OUT_EVAL / "mapping_quality_full_scale.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) == 1:
        all_sources()
    else:
        print(json.dumps(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
