"""Raw row store (review 5.1): keep each raw row once, keyed by (source_id, snapshot_sha256, source_record_id).

Adding a column later then means re-running a config over stored rows, not re-downloading, and every
observation can be traced back to the exact cell it came from. Rows live under data/rawstore/ (gitignored,
like the downloads): they contain public-register entries that include natural persons' names.

File layout: data/rawstore/<source_id>/<snapshot_sha256[:16]>.jsonl.gz, one line per row:
  {"ordinal": file position (1-based), "source_record_id": key or null, "stratum": ..., "row": {...}}
plus <snapshot_sha256[:16]>.index.json describing what was kept and why.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
from collections import Counter
from pathlib import Path

from ..extract import load_config, verify_snapshot
from ..paths import DATA, OUT_OBS, ROOT
from ..sources.readers import iter_records
from ..sources.select import load_manifest

STORE = DATA / "rawstore"


def store_path(sid: str, snapshot_sha256: str) -> Path:
    return STORE / sid / f"{snapshot_sha256[:16]}.jsonl.gz"


def baseline_sample(sid: str) -> dict[int, dict]:
    """ordinal -> {source_record_id, stratum} for the rows the audited extraction sampled."""
    out = {}
    path = OUT_OBS / f"{sid}.jsonl"
    if not path.exists():
        return out
    for line in open(path, encoding="utf-8"):
        o = json.loads(line)
        out.setdefault(o["source_row_ordinal"], {"source_record_id": o["source_record_id"],
                                                  "stratum": o.get("sample_stratum")})
    return out


def build(sid: str, keep: dict[int, dict] | None, *, full: bool = False) -> dict:
    """Stream the snapshot once and keep the rows in `keep` (ordinal -> metadata), or every row if full."""
    man = load_manifest()[sid]
    verify_snapshot(man)
    cfg, _ = load_config(sid)
    keep = keep or {}
    path = store_path(sid, man["snapshot"]["sha256"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    n = kept = 0
    strata = Counter()
    with gzip.open(tmp, "wt", encoding="utf-8", newline="\n") as fh:
        for n, rec in enumerate(iter_records(ROOT / man["snapshot"]["path"], cfg.reader), start=1):
            meta = keep.get(n)
            if meta is None and not full:
                continue
            meta = meta or {}
            fh.write(json.dumps({"ordinal": n, "source_record_id": meta.get("source_record_id"),
                                 "stratum": meta.get("stratum"), "row": rec}, default=str) + "\n")
            kept += 1
            strata[meta.get("stratum") or "unsampled"] += 1
    tmp.replace(path)
    index = {"source_id": sid, "snapshot_sha256": man["snapshot"]["sha256"], "reader": cfg.reader.model_dump(),
             "rows_in_resource": n, "rows_kept": kept, "by_stratum": dict(strata), "full": full,
             "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "missing_ordinals": sorted(set(keep) - set(range(1, n + 1)))[:20]}
    path.with_name(path.name.replace(".jsonl.gz", ".index.json")).write_text(
        json.dumps(index, indent=1), encoding="utf-8", newline="\n")
    return index


def iter_rows(sid: str):
    man = load_manifest()[sid]
    path = store_path(sid, man["snapshot"]["sha256"])
    if not path.exists():
        raise FileNotFoundError(f"{sid}: no raw store for snapshot {man['snapshot']['sha256'][:16]}; "
                                "run `python -m firmable.cli raw-store`")
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def new_source_sample(sid: str, n_random: int = 500, n_cohort: int = 500) -> dict[int, dict]:
    """A source the audited extraction never sampled (a related dataset onboarded later): a seeded random
    reservoir plus rows whose ABN occurs in another source's sample - the same cohort idea as extract.py."""
    import random
    from ..extract import SEED
    from ..mapping.engine import Engine
    abns = set()
    for f in OUT_OBS.glob("*.jsonl"):
        for line in open(f, encoding="utf-8"):
            if '"entity.abn"' in line:
                o = json.loads(line)
                if o["field"] == "entity.abn":
                    abns.add(o["value"])
    man = load_manifest()[sid]
    cfg, _ = load_config(sid)
    probe = cfg.model_copy(update={"fields": [f for f in cfg.fields if f.target == "entity.abn"], "constants": []})
    eng = Engine(probe, man)
    rng = random.Random(SEED)
    res, cohort, n = [], [], 0
    for n, rec in enumerate(iter_records(ROOT / man["snapshot"]["path"], cfg.reader), start=1):
        if {o["value"] for o in eng.process(rec)} & abns:
            cohort.append(n)
            continue
        if len(res) < n_random:
            res.append(n)
        else:
            j = rng.randrange(n)
            if j < n_random:
                res[j] = n
    cohort = sorted(random.Random(SEED + 1).sample(cohort, min(n_cohort, len(cohort))))
    return {i: {"source_record_id": None, "stratum": "random"} for i in res} | \
           {i: {"source_record_id": None, "stratum": "cohort"} for i in cohort}


def build_all(sids: list[str] | None = None, *, full: bool = False) -> dict:
    """Baseline sample rows plus the extension cohort chosen by rawdata.extract.choose_ext_cohort."""
    from . import OUT_RD_MAPPINGS
    from .extract import choose_ext_cohort
    man = load_manifest()
    sids = sids or [s for s in man if (OUT_OBS / f"{s}.jsonl").exists() or (OUT_RD_MAPPINGS / f"{s}.json").exists()]
    keep = {sid: baseline_sample(sid) or new_source_sample(sid) for sid in sids}
    extra = choose_ext_cohort(sids, keep)
    out = {}
    for sid in sids:
        rows = dict(keep[sid])
        for ordinal in extra.get(sid, []):
            rows.setdefault(ordinal, {"source_record_id": None, "stratum": "cohort_ext"})
        out[sid] = build(sid, rows, full=full)
        print(f"{sid}: stored {out[sid]['rows_kept']} rows {out[sid]['by_stratum']}", flush=True)
    return out
