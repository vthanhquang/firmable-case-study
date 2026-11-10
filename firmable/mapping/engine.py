"""The one generic extractor: (mapping config, raw records) -> canonical observations.

An observation is one claim: one canonical field, one value, one source record. Multi-valued
fields (e.g. several trading names) produce one observation each. The engine never reconciles.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .. import ENGINE_VERSION, ontology
from . import transforms
from .schema import FieldRule, MappingConfig

L0_OPS = {"trim", "collapse_whitespace", "null_if"}
ENVELOPE_TARGETS = {"observation.valid_from", "observation.valid_to", "observation.observed_at"}


@dataclass
class RuleStats:
    target: str
    source_paths: list
    records: int = 0
    source_present: int = 0     # records where the source cell was non-empty
    emitted: int = 0            # valid observations produced
    errors: Counter = field(default_factory=Counter)
    error_examples: dict = field(default_factory=lambda: defaultdict(list))

    def as_dict(self) -> dict:
        present = max(self.source_present, 1)
        n_err = sum(self.errors.values())
        return {"target": self.target, "source_paths": self.source_paths, "records": self.records,
                "source_present": self.source_present, "emitted": self.emitted,
                "coverage_of_records": round(self.emitted / max(self.records, 1), 3),
                "error_rate_of_present": round(n_err / present, 3),
                "errors": dict(self.errors),
                "error_examples": {k: v[:4] for k, v in self.error_examples.items()}}


def _get(rec: dict, path: str):
    v = rec.get(path)
    if v is None:
        return None
    return v if isinstance(v, str) else str(v)


def condition_holds(rec: dict, cond) -> bool:
    if cond is None:
        return True
    v = (_get(rec, cond.source_path) or "").strip()
    vals = {x.strip().casefold() for x in cond.values}
    if cond.op == "present":
        return v != ""
    if cond.op == "absent":
        return v == ""
    if cond.op in ("equals", "in"):
        return v.casefold() in vals
    return v.casefold() not in vals


def _gather(rec: dict, rule: FieldRule):
    if not condition_holds(rec, rule.when):
        return None
    vals = [_get(rec, p) for p in rule.source_paths]
    vals = [v for v in vals if v is not None and v.strip() != ""]
    if not vals:
        return None
    return rule.join_with.join(vals) if len(vals) > 1 else vals[0]


def record_base(rec: dict, cfg: MappingConfig) -> str:
    """Record key before duplicate numbering (order-independent, so it can be computed in parallel)."""
    if cfg.record_id.strategy == "columns":
        return "|".join((_get(rec, p) or "").strip() for p in cfg.record_id.source_paths)
    return "h:" + hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()[:16]


def number_duplicate(base: str, seen: Counter) -> str:
    seen[base] += 1
    return base if seen[base] == 1 else f"{base}#{seen[base]}"


def record_id(rec: dict, cfg: MappingConfig, seen: Counter) -> str:
    """Deterministic record key. Columns strategy: key column values. Content hash: sha256 of the
    record's canonical JSON, with an occurrence counter so exact duplicate rows stay distinct."""
    base = record_base(rec, cfg)
    seen[base] += 1
    return base if seen[base] == 1 else f"{base}#{seen[base]}"


def _derivation(rule: FieldRule) -> str:
    if len(rule.source_paths) == 1 and all(s.op in L0_OPS for s in rule.steps):
        return "L0"
    return "L1"


def _date_to_dt(d: str) -> str:
    return d if "T" in d else f"{d}T00:00:00+00:00"


class Engine:
    def __init__(self, cfg: MappingConfig, source_meta: dict, reliability: dict | None = None,
                 ingested_at: str | None = None):
        self.cfg = cfg
        self.onto = ontology.load()
        self.meta = source_meta
        self.reliability = reliability or {}
        self.digest = cfg.digest()
        self.extractor_version = f"{ENGINE_VERSION}+map:{self.digest[:12]}"
        self.ingested_at = ingested_at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        self.stats = {i: RuleStats(r.target, r.source_paths) for i, r in enumerate(cfg.fields)}
        self.records_in = 0
        self.records_with_output = 0
        self.record_errors = Counter()
        self._seen = Counter()

    def _fallback_observed_at(self) -> str:
        key = self.cfg.observed_at.fallback
        v = self.meta.get("resource_last_modified") if key == "resource_last_modified" else None
        v = v or self.meta.get("dataset_metadata_modified") or self.meta.get("snapshot", {}).get("downloaded_at")
        return v if v and ("+" in v or v.endswith("Z")) else (v + "+00:00" if v else self.ingested_at)

    def _reliability(self, target: str) -> float | None:
        group = ("identifiers" if target in ("entity.abn", "entity.acn", "entity.nzbn") else
                 "names" if target in ("entity.legal_name", "entity.trading_name") else
                 "address" if target.startswith("address.") else "other")
        return self.reliability.get(group, self.reliability.get("default"))

    def process(self, rec: dict, rid: str | None = None) -> list[dict]:
        """`rid` may be pre-assigned (two-phase parallel extraction); otherwise numbered here in arrival order."""
        self.records_in += 1
        if not rec or all(v is None or str(v).strip() == "" for v in rec.values()):
            self.record_errors["EMPTY_RECORD"] += 1
            return []
        rid = rid or record_id(rec, self.cfg, self._seen)
        envelope = {"observed_at": None, "valid_from": None, "valid_to": None}
        # observed_at: the source's own statement time if it has one, else resource metadata.
        oa = self.cfg.observed_at
        if oa.source_path:
            try:
                v = transforms.apply(oa.steps, _get(rec, oa.source_path))
                if v and not self.onto.check_value("observation.valid_from", v):
                    envelope["observed_at"] = _date_to_dt(v)
            except transforms.TransformError:
                self.record_errors["OBSERVED_AT_UNPARSEABLE"] += 1
        envelope["observed_at"] = envelope["observed_at"] or self._fallback_observed_at()

        claims = []
        for i, rule in enumerate(self.cfg.fields):
            st = self.stats[i]
            st.records += 1
            raw = _gather(rec, rule)
            if raw is None:
                continue
            st.source_present += 1
            try:
                out = transforms.apply(rule.steps, raw)
            except transforms.TransformError as e:
                st.errors[e.code] += 1
                if len(st.error_examples[e.code]) < 6:
                    st.error_examples[e.code].append(raw[:120])
                continue
            if out is None:
                continue
            values = out if isinstance(out, list) else [out]
            if rule.target in ENVELOPE_TARGETS:
                v = values[0]
                err = self.onto.check_value("observation.valid_from", v)
                if err:
                    st.errors["INVALID_" + err] += 1
                    continue
                key = rule.target.split(".")[1]
                envelope[key] = _date_to_dt(v) if key == "observed_at" else v
                st.emitted += 1
                continue
            validity = {}
            for key, path in (("valid_from", rule.valid_from_path), ("valid_to", rule.valid_to_path)):
                if path:
                    try:
                        d = transforms.op_parse_date(_get(rec, path), formats=rule.validity_date_formats or None)
                    except transforms.TransformError:
                        st.errors["VALIDITY_DATE_UNPARSEABLE"] += 1
                        d = None
                    if d:
                        validity[key] = d
            for v in values:
                err = self.onto.check_value(rule.target, v)
                if err:
                    st.errors["INVALID_" + err] += 1
                    if len(st.error_examples["INVALID_" + err]) < 6:
                        st.error_examples["INVALID_" + err].append(str(v)[:120])
                    continue
                st.emitted += 1
                claims.append((rule.target, v, raw, rule.source_paths, [s.op for s in rule.steps],
                               _derivation(rule), rule.confidence, validity))
        if not claims:
            return []
        for c in self.cfg.constants:
            claims.append((c.target, c.value, None, [], ["constant"], "L3", c.confidence, {}))
        self.records_with_output += 1
        # One claim per (field, value) per record: if two rules (or a split cell) yield the same value, keep
        # the first and record every contributing source column - otherwise observation_ids would collide.
        merged, order = {}, []
        for c in claims:
            k = (c[0], c[1])
            if k in merged:
                merged[k] = merged[k][:3] + (sorted(set(merged[k][3]) | set(c[3])),) + merged[k][4:]
            else:
                merged[k] = c
                order.append(k)
        obs = []
        for target, value, raw, src, ops, level, conf, validity in (merged[k] for k in order):
            oid = hashlib.sha256(f"{self.cfg.source_id}|{rid}|{target}|{value}|{self.digest}".encode()).hexdigest()[:24]
            obs.append({
                "observation_id": oid, "source_id": self.cfg.source_id, "source_record_id": rid,
                "record_grain": self.cfg.record_grain, "field": target, "value": value,
                "raw_value": raw, "source_fields": src, "transform": ops, "derivation_level": level,
                "observed_at": envelope["observed_at"], "ingested_at": self.ingested_at,
                # A rule's own validity columns override the record-level envelope for that claim only.
                "valid_from": validity.get("valid_from", envelope["valid_from"]),
                "valid_to": validity.get("valid_to", envelope["valid_to"]),
                "licence": self.meta.get("licence") or "unknown",
                "extractor_version": self.extractor_version,
                "confidence": {"source_reliability": self._reliability(target), "field_confidence": conf},
            })
        return obs

    def report(self) -> dict:
        return {"records_in": self.records_in, "records_with_output": self.records_with_output,
                "record_errors": dict(self.record_errors),
                "fields": [s.as_dict() for s in self.stats.values()]}
