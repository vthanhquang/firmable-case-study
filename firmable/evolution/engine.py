"""Dynamic contracts around the existing generic extractor, not source-specific parsers."""
import hashlib
import json
import math
import re
from collections import Counter

from ..mapping.engine import Engine
from .registry import compile_ontology
from .schema import DynamicMapping, Inspection, digest


def bind(row, inspection: Inspection):
    """Discriminator-based singleton projections over the shared reader's flat JSON.

    Multiple matches are refused explicitly rather than selecting the first
    supplier/contract and dropping the rest. Such records enter the refusal queue.
    """
    result, lineage = dict(row), {}
    for binding in inspection.bindings:
        pattern = re.compile(r"^" + re.escape(binding.collection) + r"\[(\d+)\]\.(.+)$")
        objects = {}
        for key, value in row.items():
            match = pattern.match(key)
            if match:
                objects.setdefault(match[1], {})[match[2]] = value
        selected = [(idx, obj) for idx, obj in objects.items() if not binding.filter_path or
                    str(obj.get(binding.filter_path, "")) == binding.filter_value or
                    binding.filter_value in str(obj.get(binding.filter_path, "")).split("; ")]
        if len(selected) != 1:
            return None, {"reason": "BINDING_CARDINALITY", "binding": binding.name, "matches": len(selected)}
        idx, obj = selected[0]
        for key, value in obj.items():
            alias = binding.name + "." + key
            if alias in result:
                raise ValueError("Binding shadows a source column")
            result[alias] = value
            lineage[alias] = f"{binding.collection}[{idx}].{key}"
    return result, lineage


def validate_mapping(cfg: DynamicMapping, ontology, columns):
    errors = []
    roles = {"subject": "business"} | {k: v.kind for k, v in cfg.entities.items()}
    if "subject" in cfg.entities:
        errors.append("subject is the implicit business; do not redeclare it")
    for name, kind in roles.items():
        if kind not in ontology["entity_types"]:
            errors.append("Unknown role type: " + name)
    for rule in cfg.fields:
        spec = ontology["concepts"].get(rule.target)
        role = rule.entity or "subject"
        if not spec:
            errors.append("Unknown target: " + rule.target)
            continue
        if role not in roles:
            errors.append(f"Undeclared entity role '{role}' for {rule.target}; declare it in entities with its kind and key_paths")
        elif spec["owner"] not in (roles[role], "any"):
            errors.append(f"Wrong owner: {rule.target} describes {spec['owner']}, but role '{role}' has kind '{roles[role]}'")
        required_op = {"entity.abn": "abn", "entity.acn": "acn", "entity.nzbn": "nzbn"}.get(rule.target)
        if required_op and (not rule.steps or rule.steps[-1].op != required_op):
            errors.append(f"Identifier {rule.target} must end with the {required_op} checksum transform")
        paths = set(rule.source_paths)
        if rule.when:
            paths.add(rule.when.source_path)
        for q in (rule.qualifiers or {}).values():
            if q.source_path:
                paths.add(q.source_path)
        paths.update(p for p in (rule.valid_from_path, rule.valid_to_path) if p)
        if paths - set(columns):
            errors.append("Unobserved source paths: " + str(sorted(paths - set(columns))))
        if set(spec.get("required_qualifiers", [])) - set(rule.qualifiers or {}):
            errors.append("Missing required qualifier definitions: " + rule.target)
        # A time attached to a source row is not automatically valid for every claim.
        if rule.target in ("observation.valid_from", "observation.valid_to"):
            errors.append("Use explicit per-claim validity, not record-wide validity rules")
    for edge in cfg.relationships:
        spec = ontology["relationships"].get(edge.type)
        if not spec or (roles.get(edge.from_role), roles.get(edge.to_role)) != (spec["from_type"], spec["to_type"]):
            errors.append("Invalid relationship types/roles: " + edge.type)
    key_paths = cfg.record_id.source_paths + [p for r in cfg.entities.values() for p in r.key_paths]
    if cfg.observed_at.source_path:
        key_paths.append(cfg.observed_at.source_path)
    if set(key_paths) - set(columns):
        errors.append("Record/entity keys reference unknown columns")
    covered = {p for f in cfg.fields for p in f.source_paths} | set(key_paths)
    covered |= {f.when.source_path for f in cfg.fields if f.when}
    covered |= {q.source_path for f in cfg.fields for q in (f.qualifiers or {}).values() if q.source_path}
    covered |= {p for f in cfg.fields for p in (f.valid_from_path, f.valid_to_path) if p}
    explicit = {u.source_path for u in cfg.unmapped}
    # Original nested index paths are represented by inspected, traceable bindings.
    unexplained = {p for p in columns if "[" not in p and p not in covered | explicit}
    if unexplained:
        errors.append("Columns neither read nor explicitly declined: " + str(sorted(unexplained)))
    return errors


def indexed_cardinality(cfg, row):
    """A concrete array index is allowed only when its collection is a singleton."""
    paths = {p for f in cfg.fields for p in f.source_paths}
    paths |= {f.when.source_path for f in cfg.fields if f.when}
    paths |= {q.source_path for f in cfg.fields for q in (f.qualifiers or {}).values() if q.source_path}
    paths |= {p for r in cfg.entities.values() for p in r.key_paths}
    for path in sorted(paths):
        for match in re.finditer(r"\[\d+\]", path):
            prefix = path[:match.start()]
            pattern = re.compile(r"^" + re.escape(prefix) + r"\[(\d+)\]")
            indices = {m.group(1) for key in row if (m := pattern.match(key))}
            if len(indices) > 1:
                return {"reason": "INDEXED_COLLECTION_NOT_SINGLETON", "collection": prefix, "members": len(indices)}
    return None


class DynamicEngine(Engine):
    def __init__(self, cfg, source, registry):
        # Initialise the unchanged engine using its core registry, then supply a
        # private immutable ontology instance. No global registry is modified.
        super().__init__(cfg.model_copy(update={"extensions": None}), source,
                         reliability={"default": .9}, ingested_at=source["retrieved_at"])
        self.cfg = cfg
        self.onto = compile_ontology(registry)
        self.digest = cfg.digest()
        self.extractor_version = "dynamic-v1+map:" + self.digest[:12] + "+onto:" + self.onto.sha256[:12]
        self.licence = source["licence_detail"]


def extract(cfg, source, registry, records, inspection, *, review_state="draft"):
    engine = DynamicEngine(cfg, source, registry)
    observations, refusals, provenance = [], [], {}
    for record in records:
        raw = record["row"]
        row, trace = bind(raw, inspection)
        rid = record["record_id"]
        if row is None:
            refusals.append({"source_record_id": rid, **trace})
            continue
        cardinality = indexed_cardinality(cfg, row)
        if cardinality:
            refusals.append({"source_record_id": rid, **cardinality})
            continue
        claims = engine.process(row, rid=rid)
        if not claims:
            refusals.append({"source_record_id": rid, "reason": "NO_VALID_CLAIMS"})
        for claim in claims:
            spec = registry["concepts"][claim["field"]]
            if isinstance(claim["value"], float) and not math.isfinite(claim["value"]):
                continue
            claim.update(ontology_version=engine.onto.sha256, mapping_digest=engine.digest,
                         snapshot_sha256=source["snapshot_sha256"], source_row_ordinal=record["ordinal"],
                         entity_kind=cfg.role_kind(claim.get("entity_role")),
                         source_bindings={p: trace.get(p, p) for p in claim["source_fields"]},
                         review_state=review_state, canonical_definition=spec["definition"])
            observations.append(claim)
        provenance[rid] = trace
    for edge in engine.edges:
        edge.update(ontology_version=engine.onto.sha256, mapping_digest=engine.digest,
                    review_state=review_state, snapshot_sha256=source["snapshot_sha256"])
    report = engine.report()
    errors = sum(sum(f["errors"].values()) for f in report["fields"])
    present = sum(f["source_present"] for f in report["fields"])
    report.update(input_records=len(records), refused_records=len(refusals), observations=len(observations),
                  value_errors=errors, present_values=present, error_rate=errors / max(present, 1))
    return observations, engine.edges, refusals, report


def drift(baseline, records, inspection=None):
    expected = set(baseline)
    rows, binding_refusals = [], 0
    for record in records:
        row = record["row"]
        if inspection:
            row, _ = bind(row, inspection)
        if row is None:
            binding_refusals += 1
        else:
            rows.append(row)
    found = set().union(*(row.keys() for row in rows)) if rows else set()
    return {"added_columns": sorted(found - expected), "missing_columns": sorted(expected - found),
            "binding_refusals": binding_refusals, "requires_reinspection": found != expected or bool(binding_refusals)}


def project(observations, edges, legacy_observations):
    """Generic concept-driven facets, with identifier-only links to the existing sample."""
    existing = {}
    for obs in legacy_observations:
        if obs["field"] == "entity.abn":
            existing.setdefault(str(obs["value"]), set()).add(obs["source_id"] + "::" + obs["source_record_id"])
    entities, linked, unlinked = {}, [], []
    for obs in observations:
        if obs.get("privacy") == "personal":
            continue
        ref = obs["source_id"] + "::" + obs["entity_ref"]
        entity = entities.setdefault(ref, {"ref": ref, "kind": obs["entity_kind"], "facets": {}})
        entity["facets"].setdefault(obs["field"], []).append({k: obs.get(k) for k in (
            "value", "canonical_definition", "qualifiers", "confidence", "observed_at", "observation_time_basis", "observation_id", "source_id", "source_record_id", "ontology_version")})
    for ref, entity in entities.items():
        if entity["kind"] != "business":
            continue
        abns = {str(o["value"]) for o in entity["facets"].get("entity.abn", [])}
        matches = sorted(set().union(*(existing.get(abn, set()) for abn in abns))) if abns else []
        if len(abns) == 1 and matches:
            linked.append({"new_entity_ref": ref, "existing_records": matches, "rule": "validated_abn_exact",
                           "abn": next(iter(abns)), "review_state": "not_human_audited"})
        else:
            unlinked.append({"ref": ref, "reason": "CONFLICTING_IDENTIFIERS" if len(abns) > 1 else
                             "NO_VALID_ABN" if not abns else "ABN_NOT_IN_EXISTING_SAMPLE"})
    return {"entities": list(entities.values()), "relationships": edges,
            "links_to_existing_sample": linked, "unlinked_businesses": unlinked,
            "note": "Proposed identifier links, not a measured-precision claim; no name-only merges."}
