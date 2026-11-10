"""Deterministic tool backend for one onboarding run. The model can only reach the data through here.

Scope: exactly one pre-downloaded resource. No network, no arbitrary paths, no code execution.
Sampling: a seeded reservoir sample over the (first MAX_SCAN) records, split by content hash into a
DISCOVERY partition (visible to the agent's tools) and a HOLDOUT partition (controller + critic only).
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter

from .. import ids, ontology
from ..mapping import transforms
from ..mapping.schema import MappingConfig, ReaderSpec
from ..mapping.validate import run_engine, static_issues
from ..paths import ROOT
from ..sources.inspect import inspect_file
from ..sources.readers import ReaderError, iter_records

MAX_SCAN = 300_000
SAMPLE = 1600
DISCOVERY_SHARE = 3  # out of 10 hash buckets
SEED = 20261110
RARE_MAX_DISTINCT = 40  # stratify only columns with at most this many distinct values in the scan
RARE_MAX_WIDTH = 500    # records wider than this (a mis-chosen reader) are not stratified


def _digest(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()


def _bucket(rec: dict) -> int:
    """Stable 0-9 hash bucket: 0..DISCOVERY_SHARE-1 is discovery, the rest is holdout."""
    return int(_digest(rec), 16) % 10


def _short(v, n=80):
    if v is None:
        return None
    s = str(v)
    return s if len(s) <= n else s[:n] + "..."


def _shape(v: str) -> str:
    """Character-class shape of a value, e.g. '12/03/2020' -> '99/99/9999'."""
    s = re.sub(r"[A-Za-z]", "a", v[:24])
    s = re.sub(r"\d", "9", s)
    return re.sub(r"a+", "a", s)


class Workspace:
    def __init__(self, source: dict):
        self.source = source
        self.path = ROOT / source["snapshot"]["path"]
        self._pools: dict[str, tuple] = {}
        self.rare_count: dict[str, int] = {}
        self.reader: ReaderSpec | None = None
        self.inspection = inspect_file(self.path)

    # ---- sampling ---------------------------------------------------------------------------
    def pool(self, spec: ReaderSpec):
        """(discovery, holdout, columns, scanned). Holdout = hash-split random records PLUS 'rare-value'
        records: one example of every value of each low-cardinality column seen in the scan, so validation
        and the critic see values (e.g. a non-Australian country) a random sample would almost never hold."""
        key = spec.model_dump_json()
        if key not in self._pools:
            rng = random.Random(SEED)
            res, n = [], 0
            rare: dict[str, dict] = {}          # column -> {value: first record with it}
            dropped: set[str] = set()           # columns too high-cardinality to stratify
            for rec in iter_records(self.path, spec):
                n += 1
                # A wrong reader choice can flatten a whole document into one enormous "record"; stratifying
                # its columns is meaningless and was quadratic. Only ordinary-width records are stratified.
                for c, v in (rec.items() if len(rec) <= RARE_MAX_WIDTH else ()):
                    if c in dropped or v is None or str(v).strip() == "":
                        continue
                    vals = rare.setdefault(c, {})
                    if str(v) not in vals:
                        if len(vals) >= RARE_MAX_DISTINCT:
                            dropped.add(c)
                            rare.pop(c, None)
                        else:
                            vals[str(v)] = rec
                if len(res) < SAMPLE:
                    res.append(rec)
                else:
                    j = rng.randrange(n)
                    if j < SAMPLE:
                        res[j] = rec
                if n >= MAX_SCAN:
                    break
            disc, hold = [], []
            for rec in res:
                (disc if _bucket(rec) < DISCOVERY_SHARE else hold).append(rec)
            # Rare-value records go to holdout only (never shown to the agent's tools), de-duplicated.
            # The same record object is often the example for many columns: hash each object once.
            digests: dict[int, str] = {}

            def dig(r):
                if id(r) not in digests:
                    digests[id(r)] = _digest(r)
                return digests[id(r)]

            seen = {dig(r) for r in res}
            rare_recs = []
            for c, vals in sorted(rare.items()):
                for v, rec in vals.items():
                    d = dig(rec)
                    # Not in the sample at all => the agent never saw it, whatever its hash bucket: safe for held-out.
                    if d not in seen:
                        seen.add(d)
                        rare_recs.append(rec)
            cols = list(dict.fromkeys(k for r in res for k in r))
            self._pools[key] = (disc, rare_recs + hold, cols, n)
            self.rare_count[key] = len(rare_recs)
        return self._pools[key]

    def rare_holdout(self, spec: ReaderSpec) -> int:
        return self.rare_count.get(spec.model_dump_json(), 0)

    def require_reader(self) -> ReaderSpec:
        if self.reader is None:
            raise ValueError("no working reader yet: call try_reader first")
        return self.reader

    # ---- model-callable tools ---------------------------------------------------------------
    def tool_inspect_resource(self) -> dict:
        return self.inspection

    def tool_try_reader(self, reader: dict) -> dict:
        try:
            spec = ReaderSpec.model_validate(reader)
        except Exception as e:
            return {"ok": False, "error": "READER_SPEC_INVALID", "detail": str(e)[:600]}
        try:
            disc, hold, cols, scanned = self.pool(spec)
        except ReaderError as e:
            return {"ok": False, "error": e.code, "detail": str(e)[:600]}
        if not disc:
            return {"ok": False, "error": "NO_RECORDS", "detail": "reader produced no records"}
        self.reader = spec
        width = Counter(len(r) for r in disc)
        return {"ok": True, "records_scanned": scanned, "scan_capped": scanned >= MAX_SCAN,
                "columns": cols[:120], "n_columns": len(cols),
                "fields_per_record": dict(width.most_common(3)),
                "sample_records": [{k: _short(v) for k, v in list(r.items())[:40]} for r in disc[:3]]}

    def tool_profile_columns(self, columns: list[str]) -> dict:
        disc, _, cols, _ = self.pool(self.require_reader())
        out = {}
        for c in columns[:25]:
            if c not in cols:
                out[c] = {"error": "UNKNOWN_COLUMN"}
                continue
            vals = [r.get(c) for r in disc]
            present = [str(v) for v in vals if v is not None and str(v).strip() != ""]
            cnt = Counter(present)
            prof = {"present_rate": round(len(present) / max(len(vals), 1), 3),
                    "distinct": len(cnt), "top_values": [[_short(k, 60), n] for k, n in cnt.most_common(6)],
                    "examples": [_short(v, 60) for v in random.Random(SEED).sample(present, min(6, len(present)))],
                    "shapes": [[s, n] for s, n in Counter(_shape(v) for v in present).most_common(5)]}
            if present:
                prof["abn_checksum_valid_rate"] = round(sum(ids.is_valid_abn(v) for v in present) / len(present), 3)
                prof["acn_checksum_valid_rate"] = round(sum(ids.is_valid_acn(v) or ids.is_valid_acn(ids.digits(v).zfill(9))
                                                            for v in present) / len(present), 3)
            out[c] = prof
        return {"partition": "discovery", "records": len(disc), "columns": out}

    def tool_get_ontology(self) -> dict:
        onto = ontology.load()
        return {"ontology_version": onto.version, "mappable_targets": onto.describe(),
                "envelope_note": "observation.valid_from/valid_to/observed_at targets set the record's envelope "
                                 "(when the claim became true / stopped / was stated), not an entity field."}

    def tool_list_transforms(self) -> dict:
        return {"ops": transforms.describe()}

    def parse_config(self, config_json: str) -> tuple[MappingConfig | None, list[dict]]:
        try:
            data = json.loads(config_json)
        except json.JSONDecodeError as e:
            return None, [{"code": "CONFIG_NOT_JSON", "severity": "error", "message": str(e)[:300]}]
        if isinstance(data, dict):
            data["source_id"] = self.source["source_id"]
        try:
            cfg = MappingConfig.model_validate(data)
        except Exception as e:
            return None, [{"code": "CONFIG_SCHEMA_INVALID", "severity": "error", "message": str(e)[:1500]}]
        disc, _, cols, _ = self.pool(cfg.reader)
        return cfg, static_issues(cfg, set(cols))

    def tool_dry_run(self, config_json: str) -> dict:
        cfg, issues = self.parse_config(config_json)
        if cfg is None or any(i["severity"] == "error" for i in issues):
            return {"ok": False, "issues": issues}
        disc, _, _, _ = self.pool(cfg.reader)
        eng, obs = run_engine(cfg, disc, self.source)
        rep = eng.report()
        first_ids = list(dict.fromkeys(o["source_record_id"] for o in obs))[:2]
        examples = [{"field": o["field"], "value": _short(o["value"]), "raw": _short(o["raw_value"])}
                    for o in obs if o["source_record_id"] in first_ids]
        return {"ok": True, "partition": "discovery", "issues": issues, "report": rep, "example_observations": examples}
