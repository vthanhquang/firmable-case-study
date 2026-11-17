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

from .. import ENGINE_VERSION, crosswalk, licences, ontology
from . import transforms
from .schema import SUBJECT, FieldRule, MappingConfig

L0_OPS = {"trim", "collapse_whitespace", "null_if"}
ENVELOPE_TARGETS = {"observation.valid_from", "observation.valid_to", "observation.observed_at"}
TERMINAL_STATUS_VALID_TO = "TERMINAL_STATUS_VALID_TO"
LEVELS = ("L0", "L1", "L2", "L3", "L4")


@dataclass
class RuleStats:
    target: str
    source_paths: list
    entity: str | None = None
    records: int = 0
    source_present: int = 0     # records where the source cell was non-empty
    emitted: int = 0            # valid observations produced
    errors: Counter = field(default_factory=Counter)
    error_examples: dict = field(default_factory=lambda: defaultdict(list))
    dropped: Counter = field(default_factory=Counter)   # values the config deliberately discards (counted, not errors)

    def as_dict(self) -> dict:
        present = max(self.source_present, 1)
        n_err = sum(self.errors.values())
        d = {"target": self.target, "source_paths": self.source_paths, "records": self.records,
             "source_present": self.source_present, "emitted": self.emitted,
             "coverage_of_records": round(self.emitted / max(self.records, 1), 3),
             "error_rate_of_present": round(n_err / present, 3),
             "errors": dict(self.errors),
             "error_examples": {k: v[:4] for k, v in self.error_examples.items()}}
        if self.entity:
            d["entity"] = self.entity
        if self.dropped:
            d["dropped"] = dict(self.dropped)
        return d


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


def _one_hot(rec: dict, rule: FieldRule) -> list[str]:
    """Indicator columns (Y / blank): the names of the columns that are set, in rule order."""
    if not condition_holds(rec, rule.when):
        return []
    return [p for p in rule.source_paths if (_get(rec, p) or "").strip().upper() in transforms.TRUTHY]


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
    level = "L1"
    for s in rule.steps:
        if s.op == "crosswalk":
            try:
                table_level = crosswalk.load(s.args.get("table", "")).get("derivation_level", "L1")
            except crosswalk.CrosswalkMissing:
                continue
            level = max(level, table_level, key=LEVELS.index)
    return level


def _date_to_dt(d: str) -> str:
    return d if "T" in d else f"{d}T00:00:00+00:00"


class Engine:
    def __init__(self, cfg: MappingConfig, source_meta: dict, reliability: dict | None = None,
                 ingested_at: str | None = None):
        self.cfg = cfg
        self.onto = ontology.load(cfg.profile_context, cfg.extensions)
        self.meta = source_meta
        self.reliability = reliability or {}
        self.digest = cfg.digest()
        self.extractor_version = f"{ENGINE_VERSION}+map:{self.digest[:12]}"
        self.ingested_at = ingested_at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        self.stats = {i: RuleStats(r.target, r.source_paths, r.entity) for i, r in enumerate(cfg.fields)}
        self.records_in = 0
        self.records_with_output = 0
        self.record_errors = Counter()
        self._seen = Counter()
        self.licence = licences.detail(source_meta)
        self.edges: list[dict] = []          # relationships declared in the config, one per record and rule
        self.edge_counts = Counter()

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
        observed_at = None
        # observed_at: the source's own statement time if it has one, else resource metadata.
        oa = self.cfg.observed_at
        if oa.source_path:
            try:
                v = transforms.apply(oa.steps, _get(rec, oa.source_path))
                if v and not self.onto.check_value("observation.valid_from", v):
                    observed_at = _date_to_dt(v)
            except transforms.TransformError:
                self.record_errors["OBSERVED_AT_UNPARSEABLE"] += 1
        observed_at = observed_at or self._fallback_observed_at()

        claims = []
        for i, rule in enumerate(self.cfg.fields):
            st = self.stats[i]
            st.records += 1
            if rule.one_hot:
                raws = _one_hot(rec, rule)
            else:
                raws = [r for r in [_gather(rec, rule)] if r is not None]
            if not raws:
                continue
            st.source_present += 1
            quals = None
            for raw in raws:
                try:
                    out = transforms.apply(rule.steps, raw)
                except transforms.TransformDrop as e:
                    st.dropped[e.code] += 1
                    continue
                except transforms.TransformError as e:
                    st.errors[e.code] += 1
                    if len(st.error_examples[e.code]) < 6:
                        st.error_examples[e.code].append(self._example(rule, raw))
                    continue
                if out is None:
                    continue
                if quals is None:
                    quals = self._qualifiers(rec, rule, st)
                    if quals is None:
                        break
                new_claims, envelope_time = self._claims(rec, rule, st, raw, out, quals)
                claims.extend(new_claims)
                observed_at = envelope_time or observed_at
        if not claims:
            return []
        evidenced_roles = {claim[9] for claim in claims}
        for c in self.cfg.constants:
            role = c.entity or SUBJECT
            if role != SUBJECT and role not in evidenced_roles:
                continue  # A metadata default cannot create a premises with no source facts.
            claims.append((c.target, c.value, None, [], ["constant"], "L3", c.confidence, {}, c.claim_scope, role, {}))
        self.records_with_output += 1
        # One claim per (field, value, scope, role, qualifiers) per record: if two rules yield the same claim,
        # keep the first and record every contributing source column - otherwise observation_ids would collide.
        merged, order = {}, []
        for c in claims:
            k = (c[0], c[1], c[8], c[9], json.dumps(c[10], sort_keys=True))
            if k in merged:
                merged[k] = merged[k][:3] + (sorted(set(merged[k][3]) | set(c[3])),) + merged[k][4:]
            else:
                merged[k] = c
                order.append(k)
        refs = self._entity_refs(rec, rid)
        obs = []
        for target, value, raw, src, ops, level, conf, validity, scope, role, quals in (merged[k] for k in order):
            anchor = f"{self.cfg.source_id}|{rid}|{target}|{value}|{self.digest}"
            if scope:
                anchor += f"|{scope}"
            if role != SUBJECT or quals:
                anchor += f"|{role}|{json.dumps(quals, sort_keys=True)}"
            oid = hashlib.sha256(anchor.encode()).hexdigest()[:24]
            o = {
                "observation_id": oid, "source_id": self.cfg.source_id, "source_record_id": rid,
                "record_grain": self.cfg.record_grain, "field": target, "value": value,
                "raw_value": raw, "source_fields": src, "transform": ops, "derivation_level": level,
                "observed_at": observed_at, "ingested_at": self.ingested_at,
                "valid_from": validity.get("valid_from"),
                "valid_to": validity.get("valid_to"),
                "licence": self.meta.get("licence") or "unknown",
                "licence_detail": self.licence,
                "extractor_version": self.extractor_version,
                "confidence": {"source_reliability": self._reliability(target), "field_confidence": conf},
                **({"claim_scope": scope} if scope else {}),
            }
            if self.cfg.extensions:
                o["entity_role"] = role
                o["entity_ref"] = refs[role]
                if quals:
                    o["qualifiers"] = quals
                if self._personal(target, value):
                    o["privacy"] = "personal"
            obs.append(o)
        if self.cfg.relationships:
            emitted_roles = {c[9] for c in claims}
            for rel in self.cfg.relationships:
                if rel.from_role in emitted_roles and rel.to_role in emitted_roles:
                    self.edge_counts[rel.type] += 1
                    self.edges.append({"type": rel.type, "source_id": self.cfg.source_id, "source_record_id": rid,
                                       "from_ref": refs[rel.from_role], "to_ref": refs[rel.to_role],
                                       "from_role": rel.from_role, "to_role": rel.to_role,
                                       "observed_at": observed_at, "extractor_version": self.extractor_version,
                                       "derivation_level": "L0"})
        return obs

    def _claims(self, rec: dict, rule: FieldRule, st: RuleStats, raw: str, out, quals: dict):
        """Typed, checked claims for one transformed value (or list of values) of one rule.
        Returns (claims, observed_at override from an observation.observed_at rule, if any)."""
        values = out if isinstance(out, list) else [out]
        if rule.target in ENVELOPE_TARGETS:
            v = values[0]
            err = self.onto.check_value("observation.valid_from", v)
            if err:
                st.errors["INVALID_" + err] += 1
                return [], None
            st.emitted += 1
            return [], (_date_to_dt(v) if rule.target == "observation.observed_at" else None)
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
        claims = []
        for v in values:
            err = self.onto.check_value(rule.target, v)
            if not err and rule.target == "ext.financial.revenue_band":
                labels = crosswalk.band_labels(quals.get("scheme", "")) if quals.get("scheme") in crosswalk.names() else set()
                err = None if v in labels else "BAND_LABEL_NOT_IN_SCHEME"
            if err:
                st.errors["INVALID_" + err] += 1
                if len(st.error_examples["INVALID_" + err]) < 6:
                    st.error_examples["INVALID_" + err].append(self._example(rule, str(v)))
                continue
            st.emitted += 1
            claim_validity = validity
            if rule.target == "entity.status" and v == "deregistered" and "valid_to" in validity:
                st.errors[TERMINAL_STATUS_VALID_TO] += 1
                examples = st.error_examples[TERMINAL_STATUS_VALID_TO]
                if len(examples) < 6:
                    examples.append(validity["valid_to"])
                claim_validity = {"valid_from": validity.get("valid_from")}
            claims.append((rule.target, v, raw, rule.source_paths, [s.op for s in rule.steps],
                           _derivation(rule), rule.confidence, claim_validity, rule.claim_scope,
                           rule.entity or SUBJECT, quals))
        return claims, None

    # ---- extension helpers ------------------------------------------------------------------------
    def _example(self, rule: FieldRule, value: str) -> str:
        """Error examples are shown to models and reviewers: never echo a value that may be personal."""
        spec = self.onto.fields.get(rule.target)
        if spec is not None and (spec.personal_data != "never" or spec.family == "contact"
                                 or spec.type in ("email", "phone")):
            return "<withheld: personal data>"
        return value[:120]

    def _qualifiers(self, rec: dict, rule: FieldRule, st: RuleStats) -> dict | None:
        out = {}
        for name, q in (rule.qualifiers or {}).items():
            if q.value is not None:
                out[name] = q.value
                continue
            try:
                v = transforms.apply(q.steps, _get(rec, q.source_path))
            except transforms.TransformError:
                v = None
            if v not in (None, "") and not isinstance(v, list):
                out[name] = v
        spec = self.onto.fields.get(rule.target)
        missing = (spec.required_qualifiers() if spec is not None else set()) - set(out)
        if missing:
            code = "QUALIFIER_MISSING_" + "_".join(sorted(missing)).upper()
            st.errors[code] += 1
            return None
        return out

    def _entity_refs(self, rec: dict, rid: str) -> dict:
        """subject -> the record; other roles -> a key that is stable across snapshots when the config names
        key columns (e.g. a licence number), else scoped to the record."""
        refs = {SUBJECT: rid}
        for role, block in (self.cfg.entities or {}).items():
            key = "|".join((_get(rec, p) or "").strip() for p in block.key_paths)
            refs[role] = (f"{block.kind}:{self.cfg.source_id}:{key}" if block.key_paths and key.strip("|")
                          else f"{rid}#{role}")
        return refs

    def _personal(self, target: str, value) -> bool:
        spec = self.onto.fields.get(target)
        if spec is None:
            return False
        if spec.personal_data == "always":
            return True
        return spec.personal_data == "mobile_numbers" and isinstance(value, str) and value.startswith("+614")

    def report(self) -> dict:
        rep = {"records_in": self.records_in, "records_with_output": self.records_with_output,
               "record_errors": dict(self.record_errors),
               "fields": [s.as_dict() for s in self.stats.values()]}
        if self.cfg.relationships:
            rep["relationships"] = dict(self.edge_counts)
        return rep
