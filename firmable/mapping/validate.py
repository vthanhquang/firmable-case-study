"""Deterministic validation gates for an agent-proposed mapping.

static_issues:  does the config reference real ontology targets and real source columns?
holdout_issues: does it actually work on records the agent never saw?
"""
from __future__ import annotations

import re

from .. import ontology
from .engine import ENVELOPE_TARGETS, TERMINAL_STATUS_VALID_TO, Engine
from .schema import MappingConfig

MAX_ERROR_RATE = 0.05        # of non-empty source cells, per field
MIN_COVERAGE_RATIO = 0.6     # holdout coverage must be >= 60% of discovery coverage
PLACEHOLDER = re.compile(r"^[\[(]?\s*(__.*__|null|none|nil|n/?a|undefined|unknown|tbc|tba|not applicable|not provided|"
                         r"not known|-+|\?+|\.+|0)\s*[\])]?\s*[-.]*$", re.I)
AMBIGUOUS_SOLE_TRADER = re.compile(r"\b(?:individuals?\s*(?:or|/)\s*(?:an?\s+)?sole traders?"
                                   r"|sole traders?\s*(?:or|/)\s*(?:an?\s+)?individuals?)\b", re.I)
HISTORIC_JURISDICTION = re.compile(r"\b(?:previous|former|original|prior) (?:state|country|jurisdiction) of registration\b")
UNSCOPED_OTHER_NAMES = re.compile(r"\b(?:other (?:organisation|organization|entity)|former legal) names?\b")
RECORD_EVENT = re.compile(r"\b(?:lic|licence|license|permit|contract|award|grant|site|suitable operator)\b")


FORMER_NAME_TEXT = re.compile(r"\b(?:previously|formerly|former(?:ly)?\s+known|was\s+known|prev\.?\s+known|"
                              r"name\s+changed\s+from|f/k/a|fka)\b", re.I)
# ';' '~' '|' or ', <word>' -> an unsplit list. One legitimate comma in a name is common, so the gate fires
# only when the share of list-like values exceeds MAX_LIST_LIKE_SHARE.
LIST_DELIMITERS = re.compile(r"[;~|]|,\s+\S")
MAX_LIST_LIKE_SHARE = 0.02
# Steps a value of each extension type must pass through (review 5.5): the gate refuses raw text.
TYPE_REQUIRED_OPS = {"decimal": {"parse_decimal", "parse_integer"}, "integer": {"parse_integer"},
                     "point": {"geo_point"}, "phone": {"phone_au"}, "domain": {"email_domain", "url_domain"},
                     "email": {"role_email"}, "date": {"parse_date"}}


def _column_words(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def extension_issues(cfg: MappingConfig, known_columns: set[str]) -> list[dict]:
    """Static gate for ext-v1 concepts, roles, qualifiers and crosswalks (review 5.2-5.5)."""
    from .. import crosswalk
    if not cfg.extensions:
        return []
    onto = ontology.load(cfg.profile_context, cfg.extensions)
    out = []
    for block_role, block in (cfg.entities or {}).items():
        for p in block.key_paths:
            if p not in known_columns:
                out.append(issue("UNKNOWN_SOURCE_PATH", "error", f"entity {block_role!r} key column {p!r} not seen",
                                 None, [p]))
    for r in cfg.fields:
        spec = onto.fields.get(r.target)
        kind = cfg.role_kind(r.entity)
        ops = [s.op for s in r.steps]
        for q in (r.qualifiers or {}).values():
            if q.source_path and q.source_path not in known_columns:
                out.append(issue("UNKNOWN_SOURCE_PATH", "error", f"qualifier column {q.source_path!r} not seen",
                                 r.target, [q.source_path]))
        for s in r.steps:
            if s.op == "crosswalk":
                try:
                    table = crosswalk.load(s.args.get("table", ""))
                except crosswalk.CrosswalkMissing as e:
                    out.append(issue("CROSSWALK_MISSING", "error", str(e), r.target, r.source_paths))
                    continue
                if r.target.startswith("ext.") and table.get("target") not in (None, r.target) \
                        and s is r.steps[-1]:
                    out.append(issue("CROSSWALK_TARGET_MISMATCH", "error",
                                     f"table {table['name']!r} produces {table.get('target')}, not {r.target}",
                                     r.target, r.source_paths))
        if not r.target.startswith("ext."):
            if r.entity not in (None, "subject") and r.target.startswith("entity.") and kind != "business":
                out.append(issue("ROLE_TARGET_MISMATCH", "error",
                                 f"entity.* fields describe a business; role {r.entity!r} is a {kind}",
                                 r.target, r.source_paths))
            continue
        if spec is None:
            continue    # reported as ONTOLOGY_PATH_INVALID by static_issues
        need = ontology.FAMILY_ROLE_KINDS[spec.family]
        if need != "any" and need != kind:
            out.append(issue("ROLE_TARGET_MISMATCH", "error",
                             f"{r.target} attaches to a {need} role; rule.entity {r.entity or 'subject'!r} is a {kind}",
                             r.target, r.source_paths))
        missing = spec.required_qualifiers() - set(r.qualifiers or {})
        if missing:
            out.append(issue("QUALIFIER_REQUIRED", "error",
                             f"{r.target} needs qualifiers {sorted(missing)} (e.g. period and currency for a "
                             "financial fact, scheme for a band, tag or industry code)", r.target, r.source_paths))
        unknown = set(r.qualifiers or {}) - {name for name, _ in spec.qualifiers}
        if unknown:
            out.append(issue("QUALIFIER_UNKNOWN", "error", f"{r.target} does not take qualifiers {sorted(unknown)}",
                             r.target, r.source_paths))
        tables = [s.args.get("table") for s in r.steps if s.op == "crosswalk"]
        if spec.crosswalk and not tables:
            out.append(issue("CROSSWALK_REQUIRED", "error",
                             f"{r.target} must come from a reviewed crosswalk table, not free text", r.target,
                             r.source_paths))
        scheme = (r.qualifiers or {}).get("scheme")
        if r.target == "ext.entity.industry_code" and scheme is not None and scheme.value != "anzsic2006":
            out.append(issue("SCHEME_INVALID", "error", "industry_code scheme must be anzsic2006", r.target))
        if r.target == "ext.financial.revenue_band":
            if scheme is None or scheme.value is None or scheme.value not in tables:
                out.append(issue("BAND_SCHEME_MISMATCH", "error",
                                 "revenue_band's scheme qualifier must be the constant name of the band table the "
                                 "rule's crosswalk step uses", r.target, r.source_paths))
            elif crosswalk.load(scheme.value).get("kind") != "band":
                out.append(issue("BAND_SCHEME_MISMATCH", "error", f"{scheme.value!r} is not a band table", r.target))
        required_ops = TYPE_REQUIRED_OPS.get(spec.type)
        if required_ops and not required_ops & set(ops) and not (spec.type == "integer" and "parse_decimal" in ops):
            out.append(issue("TYPE_TRANSFORM_REQUIRED", "error",
                             f"{r.target} ({spec.type}) must use one of {sorted(required_ops)}", r.target, r.source_paths))
        if spec.type == "enum" and not {"map_enum", "flag", "crosswalk", "state"} & set(ops):
            out.append(issue("ENUM_WITHOUT_MAPPING", "error", f"{r.target} is an enum; use map_enum, flag or crosswalk",
                             r.target, r.source_paths))
        if spec.type == "enum" and "flag" in ops:
            bad = [s.args.get("value") for s in r.steps if s.op == "flag" and s.args.get("value") not in spec.values]
            if bad:
                out.append(issue("ENUM_VALUE_INVALID", "error", f"flag values {bad} are not in {list(spec.values)}",
                                 r.target, r.source_paths))
        if spec.temporal is False and (r.valid_from_path or r.valid_to_path) and spec.family == "financial":
            out.append(issue("PERIOD_NOT_VALIDITY", "error",
                             "A financial fact's period is a qualifier, not claim validity", r.target, r.source_paths))
    return out


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
    onto = ontology.load(cfg.profile_context, cfg.extensions)
    mappable = set(onto.mappable())
    out = []
    seen_pairs = set()
    for r in cfg.fields:
        if r.target not in mappable:
            out.append(issue("ONTOLOGY_PATH_INVALID", "error",
                             f"target {r.target!r} is not a mappable ontology path", r.target))
        if r.target.startswith("context."):
            required_grain = {"tax": "legal_entity", "charity": "legal_entity", "company": "legal_entity",
                              "licence": "licence_or_permit", "establishment": "establishment"}.get(r.target.split(".")[1])
            if required_grain != cfg.record_grain:
                out.append(issue("CONTEXT_GRAIN_MISMATCH", "error", "Context target describes a different record grain.",
                                 r.target, r.source_paths))
        for p in r.source_paths:
            if p not in known_columns:
                out.append(issue("UNKNOWN_SOURCE_PATH", "error", f"source column {p!r} not seen in the data",
                                 r.target, r.source_paths))
        columns = [_column_words(path) for path in r.source_paths]
        if r.target.startswith("address.") and any(HISTORIC_JURISDICTION.search(path) for path in columns):
            out.append(issue("REGISTRATION_JURISDICTION_AS_ADDRESS", "error",
                             "Historic registration jurisdiction does not establish a record address.", r.target, r.source_paths))
        if r.target == "entity.trading_name" and any(UNSCOPED_OTHER_NAMES.search(path) for path in columns):
            out.append(issue("AMBIGUOUS_ALIAS_AS_TRADING_NAME", "error",
                             "An unclassified alias or former legal name does not establish a trading name.", r.target, r.source_paths))
        if (r.target in {"entity.date_registered", "entity.status"} and
                cfg.record_grain in {"licence_or_permit", "contract_or_grant", "establishment"} and
                any(RECORD_EVENT.search(path) for path in columns)):
            out.append(issue("RECORD_EVENT_AS_ENTITY_FACT", "error",
                             "This column describes the source record's event or status rather than the business itself.",
                             r.target, r.source_paths))
        if ((r.claim_scope == "former_legal_name" or r.target == "ext.entity.former_name") and r.valid_to_path and
                "current name start" in _column_words(r.valid_to_path)):
            out.append(issue("UNSUPPORTED_FORMER_NAME_END", "error",
                             "A current name's start date does not establish the end date of each former name.",
                             r.target, [r.valid_to_path]))
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
        if onto.fields.get(r.target) and onto.fields[r.target].type == "enum" and not r.target.startswith("ext."):
            if not any(s.op in ("map_enum", "state") for s in r.steps):
                out.append(issue("ENUM_WITHOUT_MAPPING", "error",
                                 f"{r.target} is an enum; use map_enum (or state) to produce allowed values", r.target))
            # The ontology's "default to unknown": an unlisted raw value must not become a specific class.
            if "unknown" in onto.fields[r.target].values:
                for s in r.steps:
                    if s.op != "map_enum":
                        continue
                    d = s.args.get("default")
                    if d not in (None, "unknown"):
                        out.append(issue("ENUM_DEFAULT_GUESS", "error",
                                         f"{r.target}: map_enum default {d!r} assigns a class to every unlisted value; "
                                         "the ontology says default to 'unknown'", r.target, r.source_paths))
                    mapping = s.args.get("mapping")
                    if (r.target == "entity.entity_type" and len(r.source_paths) == 1
                            and (r.when is None or r.when.source_path == r.source_paths[0])
                            and isinstance(mapping, dict)):
                        ambiguous = [label for label, value in mapping.items()
                                     if value == "sole_trader" and AMBIGUOUS_SOLE_TRADER.search(str(label))]
                        if ambiguous:
                            out.append(issue("AMBIGUOUS_ENTITY_TYPE", "error",
                                             "A combined individual or sole-trader label needs separate evidence "
                                             "to identify a sole trader. Use unknown when the label is the only evidence.",
                                             r.target, r.source_paths, ambiguous[:5]))
    for c in cfg.constants:
        if c.entity not in (None, "subject") and c.target.startswith("entity.") and cfg.role_kind(c.entity) != "business":
            out.append(issue("ROLE_TARGET_MISMATCH", "error", "Company constants require a business role", c.target))
        if (c.target not in mappable or c.target in ENVELOPE_TARGETS
                or c.target.startswith(("context.", "ext."))):
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
    out.extend(extension_issues(cfg, known_columns))
    return out


def list_issues(obs: list[dict], onto) -> list[dict]:
    """Review 5.5 'tag lists must be split' and 2.2 (ACNC): a multi-valued field must hold one value per
    observation, and a trading name must not carry a former name in prose."""
    out = []
    by_field = {}
    for o in obs:
        if isinstance(o["value"], str):
            by_field.setdefault(o["field"], []).append(o["value"])
    for target, values in by_field.items():
        spec = onto.fields.get(target)
        multi = target == "entity.trading_name" or (spec is not None and spec.multi)
        if not multi or (spec is not None and spec.type in ("enum", "point")):
            continue
        listy = [v for v in values if LIST_DELIMITERS.search(v)]
        if listy and len(listy) / len(values) > MAX_LIST_LIKE_SHARE:
            out.append(issue("UNSPLIT_LIST_VALUES", "error",
                             f"{len(listy)}/{len(values)} values look like delimiter-separated lists; split them so "
                             "each value is its own observation", target, None, [v[:80] for v in listy[:4]]))
    former = [v for v in by_field.get("entity.trading_name", []) if FORMER_NAME_TEXT.search(v)]
    if former:
        out.append(issue("FORMER_NAME_AS_TRADING_NAME", "error",
                         f"{len(former)} trading-name values describe a former name ('previously known as ...'); "
                         "a former name is not a trading name", "entity.trading_name", None, [v[:80] for v in former[:4]]))
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
        if f["errors"].get(TERMINAL_STATUS_VALID_TO):
            out.append(issue(TERMINAL_STATUS_VALID_TO, "error",
                             "A deregistered status cannot end on a date taken from the same record.",
                             f["target"], f["source_paths"], f["error_examples"]))
        elif f["error_rate_of_present"] > MAX_ERROR_RATE:
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
        if f["target"] in {"observation.valid_from", "observation.valid_to"} and f["emitted"]:
            out.append(issue("RECORD_VALIDITY_IGNORED", "warning",
                             "The engine ignores this legacy record-level date. Set a rule's validity path "
                             "only when the source dates that claim.", f["target"], f["source_paths"]))
        if f.get("dropped"):
            out.append(issue("VALUES_DROPPED", "warning",
                             f"{sum(f['dropped'].values())} values deliberately discarded: {f['dropped']}",
                             f["target"], f["source_paths"]))
    # Deterministic guard for the failure the critic once missed: sentinel/placeholder strings emitted as data.
    onto = ontology.load(cfg.profile_context, cfg.extensions)
    out.extend(list_issues(h_obs, onto))
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
