"""Run approved mapping configs through the generic engine and write canonical observations.

Sampling (per source, seeded, documented in outputs/observations/<id>.sample.json):
  pass 1  RANDOM  - reservoir sample of N records over the whole resource.
  pass 2  COHORT  - up to N/2 of those slots are replaced by records whose ABN, ACN or normalised
                    registered name also appears in ANOTHER source's random sample. Without this, two
                    random 1,000-row samples of large registers share almost no businesses and
                    Parts 3-4 would have nothing to measure. Stratum is recorded per record, so link
                    and profile statistics can be reported on the random stratum alone.
Only configs whose current digest carries an approval are executed.
"""
from __future__ import annotations

import json
import random
import re

import yaml

from .agent.review import current_approval
from .mapping.engine import Engine
from .mapping.schema import MappingConfig
from .paths import OUT_MAPPINGS, OUT_OBS, ROOT
from .sources.readers import iter_records
from .sources.select import load_manifest

SEED = 20261110
KEY_FIELDS = ("entity.abn", "entity.acn", "entity.legal_name")
_SUFFIX = re.compile(r"\b(PTY\.?\s*LTD|PROPRIETARY LIMITED|LIMITED|LTD|INCORPORATED|INC)\b\.?")


def name_key(v: str) -> str:
    """Strict normalisation used for cohort selection only (resolution has its own)."""
    s = re.sub(r"[^A-Z0-9 ]", " ", v.upper().replace("&", " AND "))
    return " ".join(s.split())


def verify_snapshot(source: dict):
    """Refuse to extract from bytes that are not the snapshot the config was approved against."""
    import hashlib
    p = ROOT / source["snapshot"]["path"]
    if not p.exists():
        raise SystemExit(f"{source['source_id']}: snapshot missing ({p}); run `python -m firmable.cli fetch`")
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    if h.hexdigest() != source["snapshot"]["sha256"]:
        raise SystemExit(f"{source['source_id']}: snapshot sha256 differs from the approved manifest; refusing to extract")


def reliability() -> dict:
    return yaml.safe_load((ROOT / "config" / "source_reliability.yaml").read_text(encoding="utf-8"))


def load_config(sid: str) -> tuple[MappingConfig, dict]:
    doc = json.loads((OUT_MAPPINGS / f"{sid}.json").read_text(encoding="utf-8"))
    return MappingConfig.model_validate(doc["config"]), doc


def _keys(obs: list[dict]) -> set:
    out = set()
    for o in obs:
        if o["field"] in ("entity.abn", "entity.acn"):
            out.add((o["field"], o["value"]))
        elif o["field"] == "entity.legal_name" and _SUFFIX.search(o["value"].upper()):
            out.add(("name", name_key(o["value"])))  # only registered-company-style names are cohort keys
    return out


PARALLEL_MIN_ROWS = 500_000   # partition the cohort probe only where it pays (ASIC: 4.46M rows)
PROBE_CHUNK = 50_000


def _probe_chunk(args):
    cfg_json, meta, others, chunk = args
    eng = Engine(MappingConfig.model_validate_json(cfg_json), meta)
    return [(i, rec) for i, rec in chunk if _keys(eng.process(rec)) & others]


def _probe_parallel(rows, probe_cfg, meta, others, workers: int = 6) -> list:
    """Cohort probe across processes. Keys depend only on identifier/name values, never on record ids or order,
    so the result equals the serial probe; it is re-sorted by file ordinal so seeded sampling is unchanged."""
    from concurrent.futures import ProcessPoolExecutor
    from itertools import islice
    cfg_json, out = probe_cfg.model_dump_json(), []
    with ProcessPoolExecutor(workers) as ex:
        futs = []
        while True:
            part = list(islice(rows, PROBE_CHUNK))
            if not part:
                break
            futs.append(ex.submit(_probe_chunk, (cfg_json, meta, others, part)))
        for f in futs:
            out.extend(f.result())
    return sorted(out, key=lambda x: x[0])


def _engine(sid, cfg, man, rel, ingested_at):
    return Engine(cfg, man[sid], rel.get(sid, rel.get("default", {})), ingested_at)


def run_all(sample_size: int = 1000, sources: list[str] | None = None):
    man = load_manifest()
    rel = reliability()
    sids = [s for s in (sources or [p.stem for p in OUT_MAPPINGS.glob("*.json")])
            if not s.endswith(".history") and s in man]
    approved = {}
    for sid in sids:
        if current_approval(sid):
            verify_snapshot(man[sid])
            approved[sid] = load_config(sid)[0]
        else:
            print(f"skip {sid}: no approval for the current config digest")
    from datetime import datetime, timezone
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # pass 1: random reservoir per source (records kept raw so pass 2 can reuse the engine)
    random_sets, random_keys = {}, {}
    for sid, cfg in approved.items():
        rng = random.Random(SEED)
        res, n = [], 0
        for rec in iter_records(ROOT / man[sid]["snapshot"]["path"], cfg.reader):
            n += 1
            if len(res) < sample_size:
                res.append((n, rec))
            else:
                j = rng.randrange(n)
                if j < sample_size:
                    res[j] = (n, rec)
        res.sort(key=lambda x: x[0])
        random_sets[sid] = (res, n)
        eng = _engine(sid, cfg, man, rel, ingested_at)
        keys = set()
        for _, rec in res:
            keys |= _keys(eng.process(rec))
        random_keys[sid] = keys
        print(f"{sid}: scanned {n} records, random sample {len(res)}, {len(keys)} cohort keys", flush=True)

    # pass 2: cohort records matching other sources' random-sample keys
    for sid, cfg in approved.items():
        others = set().union(*[k for s, k in random_keys.items() if s != sid]) if len(random_keys) > 1 else set()
        res, n_total = random_sets[sid]
        random_idx = {i for i, _ in res}
        cohort = []
        # The probe only needs the key rules (ids, legal name): ~3x faster on the 4.5M-row ASIC file.
        probe_cfg = cfg.model_copy(update={"fields": [f for f in cfg.fields if f.target in KEY_FIELDS],
                                           "constants": []})
        rows = ((i, rec) for i, rec in enumerate(iter_records(ROOT / man[sid]["snapshot"]["path"], cfg.reader), start=1)
                if i not in random_idx)
        if n_total > PARALLEL_MIN_ROWS:
            cohort = _probe_parallel(rows, probe_cfg, man[sid], others)
        else:
            probe = _engine(sid, probe_cfg, man, rel, ingested_at)
            cohort = [(i, rec) for i, rec in rows if _keys(probe.process(rec)) & others]
        rng = random.Random(SEED + 1)
        cohort = rng.sample(cohort, min(len(cohort), sample_size // 2))
        keep_random = res[: sample_size - len(cohort)] if cohort else res
        # Drop random records by a seeded shuffle rather than by file order.
        if cohort:
            shuffled = res[:]
            rng.shuffle(shuffled)
            keep_random = sorted(shuffled[: sample_size - len(cohort)], key=lambda x: x[0])
        final = [(i, r, "random") for i, r in keep_random] + [(i, r, "cohort") for i, r in sorted(cohort, key=lambda x: x[0])]
        eng = _engine(sid, cfg, man, rel, ingested_at)
        OUT_OBS.mkdir(parents=True, exist_ok=True)
        strata = {}
        n_obs = 0
        with open(OUT_OBS / f"{sid}.jsonl", "w", encoding="utf-8") as fh:
            for i, rec, stratum in final:
                obs = eng.process(rec)
                for o in obs:
                    o["sample_stratum"] = stratum
                    o["source_row_ordinal"] = i
                    fh.write(json.dumps(o) + "\n")
                    n_obs += 1
                if obs:
                    strata[obs[0]["source_record_id"]] = stratum
        summary = {"source_id": sid, "records_in_resource": n_total, "sample_size": len(final),
                   "random": sum(1 for x in final if x[2] == "random"),
                   "cohort": sum(1 for x in final if x[2] == "cohort"),
                   "cohort_candidates_found": len(cohort), "observations": n_obs,
                   "config_digest": cfg.digest(), "extractor_version": eng.extractor_version,
                   "engine_report": eng.report(), "seed": SEED, "record_strata": strata}
        (OUT_OBS / f"{sid}.sample.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
        print(f"{sid}: wrote {n_obs} observations from {len(final)} records "
              f"({summary['random']} random + {summary['cohort']} cohort)", flush=True)
