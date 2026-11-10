"""Deterministic validation gates for an agent-proposed mapping.

static_issues:  does the config reference real ontology targets and real source columns?
holdout_issues: does it actually work on records the agent never saw?
"""
from __future__ import annotations

import re

from .. import ontology
from .engine import ENVELOPE_TARGETS, Engine
from .schema import MappingConfig

MAX_ERROR_RATE = 0.05        # of non-empty source cells, per field
MIN_COVERAGE_RATIO = 0.6     # holdout coverage must be >= 60% of discovery coverage
PLACEHOLDER = re.compile(r"^[\[(]?\s*(__.*__|null|none|nil|n/?a|undefined|unknown|tbc|tba|not applicable|not provided|"
                         r"not known|-+|\?+|\.+|0)\s*[\])]?\s*[-.]*$", re.I)


def issue(code, severity, message, target=None, source_paths=None, examples=None) -> dict:
    d = {"code": code, "severity": severity, "message": message}
    if target:
        d["target"] = target
    if source_paths:
        d["source_paths"] = source_paths
    if examples:
        d["examples"] = examples
    return d


def static_issues(cfg: MappingConfig, known_columns: set[str]) -> list[dict]:
    onto = ontology.load()
    mappable = set(onto.mappable())
    out = []
    seen_pairs = set()
    for r in cfg.fields:
        if r.target not in mappable:
            out.append(issue("ONTOLOGY_PATH_INVALID", "error",
                             f"target {r.target!r} is not a mappable ontology path", r.target))
        for p in r.source_paths:
            if p not in known_columns:
                out.append(issue("UNKNOWN_SOURCE_PATH", "error", f"source column {p!r} not seen in the data",
                                 r.target, r.source_paths))
        for vp in (r.valid_from_path, r.valid_to_path):
            if vp and vp not in known_columns:
                out.append(issue("UNKNOWN_SOURCE_PATH", "error", f"validity column {vp!r} not seen", r.target, [vp]))
        if r.when and r.when.source_path not in known_columns:
            out.append(issue("UNKNOWN_SOURCE_PATH", "error", f"condition column {r.when.source_path!r} not seen",
                             r.target, [r.when.source_path]))
        key = (r.target, tuple(r.source_paths), r.when.model_dump_json() if r.when else None)
        if key in seen_pairs:
            out.append(issue("DUPLICATE_RULE", "error", "same source->target rule twice", r.target))
        seen_pairs.add(key)
        if r.target in ("entity.abn", "entity.acn", "entity.nzbn"):
            needed = r.target.split(".")[1]
            if needed not in [s.op for s in r.steps]:
                out.append(issue("IDENTIFIER_NOT_VALIDATED", "error",
                                 f"{r.target} must use the '{needed}' checksum transform", r.target))
        if onto.fields.get(r.target) and onto.fields[r.target].type == "enum":
            if not any(s.op in ("map_enum", "state") for s in r.steps):
                out.append(issue("ENUM_WITHOUT_MAPPING", "error",
                                 f"{r.target} is an enum; use map_enum (or state) to produce allowed values", r.target))
            # The ontology's "default to unknown": an unlisted raw value must not become a specific class.
            if "unknown" in onto.fields[r.target].values:
                for s in r.steps:
                    d = s.args.get("default") if s.op == "map_enum" else None
                    if d not in (None, "unknown"):
                        out.append(issue("ENUM_DEFAULT_GUESS", "error",
                                         f"{r.target}: map_enum default {d!r} assigns a class to every unlisted value; "
                                         "the ontology says default to 'unknown'", r.target, r.source_paths))
    for c in cfg.constants:
        if c.target not in mappable or c.target in ENVELOPE_TARGETS:
            out.append(issue("ONTOLOGY_PATH_INVALID", "error", f"constant target {c.target!r} not allowed", c.target))
        elif onto.check_value(c.target, c.value):
            out.append(issue("CONSTANT_INVALID", "error",
                             f"constant {c.value!r} invalid for {c.target}: {onto.check_value(c.target, c.value)}",
                             c.target))
    for p in cfg.record_id.source_paths:
        if p not in known_columns:
            out.append(issue("UNKNOWN_SOURCE_PATH", "error", f"record_id column {p!r} not seen", None, [p]))
    if cfg.observed_at.source_path and cfg.observed_at.source_path not in known_columns:
        out.append(issue("UNKNOWN_SOURCE_PATH", "error", "observed_at column not seen", None,
                         [cfg.observed_at.source_path]))
    if not any(r.target in ("entity.legal_name", "entity.trading_name", "entity.abn", "entity.acn")
               for r in cfg.fields):
        out.append(issue("NO_ENTITY_IDENTITY", "warning",
                         "no name or identifier mapped: records cannot be linked to a business"))
    return out


def run_engine(cfg: MappingConfig, records: list[dict], meta: dict) -> tuple[Engine, list[dict]]:
    eng = Engine(cfg, meta)
    obs = []
    for r in records:
        obs.extend(eng.process(r))
    return eng, obs


def holdout_issues(cfg: MappingConfig, discovery: list[dict], holdout: list[dict], meta: dict) -> tuple[list, dict]:
    d_eng, _ = run_engine(cfg, discovery, meta)
    h_eng, h_obs = run_engine(cfg, holdout, meta)
    rep = h_eng.report()
    disc_fields = d_eng.report()["fields"]  # same order as cfg.fields
    out = []
    for i, f in enumerate(rep["fields"]):
        if f["error_rate_of_present"] > MAX_ERROR_RATE:
            out.append(issue("HIGH_ERROR_RATE", "error",
                             f"{f['error_rate_of_present']:.1%} of non-empty values failed: {f['errors']}",
                             f["target"], f["source_paths"],
                             {k: v for k, v in f["error_examples"].items()}))
        elif f["errors"]:
            out.append(issue("SOME_ERRORS", "warning", f"{sum(f['errors'].values())} values rejected: {f['errors']}",
                             f["target"], f["source_paths"], f["error_examples"]))
        d = disc_fields[i]
        if d and d["coverage_of_records"] > 0.05 and f["coverage_of_records"] < MIN_COVERAGE_RATIO * d["coverage_of_records"]:
            out.append(issue("COVERAGE_REGRESSION", "error",
                             f"coverage {d['coverage_of_records']:.0%} on discovery vs {f['coverage_of_records']:.0%} on holdout",
                             f["target"], f["source_paths"]))
        if f["source_present"] and f["emitted"] == 0:
            out.append(issue("NOTHING_EMITTED", "error", "source has values but no valid observation was produced",
                             f["target"], f["source_paths"]))
    # Deterministic guard for the failure the critic once missed: sentinel/placeholder strings emitted as data.
    onto = ontology.load()
    bad = {}
    for o in h_obs:
        v = o["value"]
        spec = onto.fields.get(o["field"])
        if isinstance(v, str) and spec is not None and spec.type != "enum" and PLACEHOLDER.match(v.strip()):
            bad.setdefault(o["field"], set()).add(v)
    for target, vals in bad.items():
        out.append(issue("PLACEHOLDER_VALUE_EMITTED", "error",
                         f"placeholder-like values emitted as data: {sorted(vals)[:5]}", target, None, sorted(vals)[:5]))
    if cfg.record_id.strategy == "columns":
        dups = sum(1 for o in set((o["source_record_id"]) for o in h_obs) if "#" in o)
        if dups:
            out.append(issue("RECORD_ID_NOT_UNIQUE", "error",
                             f"{dups} holdout records share a key built from {cfg.record_id.source_paths}; "
                             "choose unique key columns or content_hash"))
    if rep["records_with_output"] < 0.5 * max(rep["records_in"], 1):
        out.append(issue("LOW_RECORD_YIELD", "warning",
                         f"only {rep['records_with_output']}/{rep['records_in']} holdout records produced observations"))
    return out, rep
