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
from ..mapping.schema import ExtensionDraft, MappingConfig, ProfileContextDraft, ReaderSpec
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


_EMAIL_IN_TEXT = re.compile(r"([A-Za-z0-9._%+'-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
_MOBILE_IN_TEXT = re.compile(r"(?<!\d)(?:\+?61\s?|0)4\d{2}\s?\d{3}\s?\d{3}(?!\d)")


def mask_personal(s: str) -> str:
    """Review section 6: personal mailboxes and mobile numbers never leave the machine. Model-facing text
    keeps the shape (domain, role mailbox, 'mobile') so the agent can still choose a mapping."""
    s = _EMAIL_IN_TEXT.sub(lambda m: m.group(0) if m.group(1).lower() in transforms.ROLE_MAILBOXES
                           else f"<personal>@{m.group(2)}", s)
    return _MOBILE_IN_TEXT.sub("<mobile number>", s)


def _short(v, n=80):
    if v is None:
        return None
    s = mask_personal(str(v))
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
        base = source.get("profile_context_base")
        self.context_base = MappingConfig.model_validate(base) if base else None
        ext = source.get("extension_base")
        self.ext_base = MappingConfig.model_validate(ext) if ext else None
        locked = self.context_base or self.ext_base
        self.reader: ReaderSpec | None = locked.reader if locked else None
        self.inspection = inspect_file(self.path)
        self.ext_editable: set[int] = set()     # base rules a current gate fails on (extension mode)
        self.ext_base_findings: list[dict] = []
        self.ext_last_discarded: list[str] = []
        self.ext_last_changes: list[dict] = []
        if self.ext_base:
            self._ext_base_gate()

    def _ext_base_gate(self):
        """Run today's gates (including the extension gates) over the approved base. Rules that fail are the
        only base rules the agent may replace or remove."""
        from ..mapping.validate import holdout_issues
        disc, hold, cols, _ = self.pool(self.ext_base.reader)
        issues, _ = holdout_issues(self.ext_base, disc, hold, self.source)
        issues = static_issues(self.ext_base, set(cols)) + issues
        self.ext_base_findings = [i for i in issues if i["severity"] == "error"]
        failing = {(i.get("target"), tuple(i.get("source_paths") or ())) for i in self.ext_base_findings}
        failing_targets = {t for t, _ in failing}
        for idx, rule in enumerate(self.ext_base.fields):
            if (rule.target, tuple(rule.source_paths)) in failing or (
                    rule.target in failing_targets and (rule.target, ()) in failing):
                self.ext_editable.add(idx)

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
        locked = self.context_base or self.ext_base
        if locked and spec != locked.reader:
            return {"ok": False, "error": "READER_LOCKED", "detail": "Use the frozen base mapping reader."}
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
        if self.ext_base:
            onto = ontology.load(None, "ext-v1")
            return {"ontology_version": onto.version, "mappable_targets": onto.describe(),
                    "extension_note": "ext.* targets come from the extension registry. Each says which record role "
                                      "it attaches to (business / licence / establishment / any), its required "
                                      "qualifiers, whether it must come from a crosswalk table, and whether it is "
                                      "multi-valued (split lists so each value is one observation)."}
        onto = ontology.load("v1" if self.context_base else None)
        targets = [d for d in onto.describe() if d["path"].startswith("context.")] if self.context_base else onto.describe()
        return {"ontology_version": onto.version, "mappable_targets": targets,
                "envelope_note": "observation.valid_from/valid_to/observed_at targets set the record's envelope "
                                 "(when the claim became true / stopped / was stated), not an entity field."}

    def tool_list_transforms(self) -> dict:
        return {"ops": transforms.describe()}

    def tool_list_crosswalks(self) -> dict:
        from .. import crosswalk
        return {"tables": crosswalk.describe(),
                "note": "Human-reviewed lookup tables. Reference one with a step {op: crosswalk, args: {table, "
                        "output}}. Use a table only when its keys are the values this source actually holds."}

    def parse_config(self, config_json: str | dict) -> tuple[MappingConfig | None, list[dict]]:
        try:
            data = config_json.copy() if isinstance(config_json, dict) else json.loads(config_json)
        except (TypeError, json.JSONDecodeError) as e:
            return None, [{"code": "CONFIG_NOT_JSON", "severity": "error", "message": str(e)[:300]}]
        if isinstance(data, dict) and not (self.context_base or self.ext_base):
            data["source_id"] = self.source["source_id"]
        try:
            if self.ext_base:
                cfg, self.ext_last_discarded, self.ext_last_changes = \
                    ExtensionDraft.model_validate(data).apply(self.ext_base, self.ext_editable)
            elif self.context_base:
                cfg = ProfileContextDraft.model_validate(data).extend(self.context_base)
            else:
                cfg = MappingConfig.model_validate(data)
        except Exception as e:
            return None, [{"code": "CONFIG_SCHEMA_INVALID", "severity": "error", "message": str(e)[:1500]}]
        disc, _, cols, _ = self.pool(cfg.reader)
        issues = static_issues(cfg, set(cols))
        if self.context_base:
            issues = [item for item in issues if item.get("target", "").startswith("context.")]
        if self.ext_base:
            issues += [{"code": "EDIT_DISCARDED", "severity": "warning", "message": m} for m in self.ext_last_discarded]
        return cfg, issues

    def ext_scope(self, cfg: MappingConfig) -> set[int]:
        """Indices (in cfg.fields) of rules this extension run is responsible for: added, edited or replaced
        rules, plus base rules a current gate fails on. Unchanged approved rules are not re-judged."""
        base = [r.model_dump_json() for r in self.ext_base.fields]
        failing = {self.ext_base.fields[i].model_dump_json() for i in self.ext_editable}
        return {i for i, r in enumerate(cfg.fields) if r.model_dump_json() not in base or r.model_dump_json() in failing}

    def tool_dry_run(self, config_json: str | dict) -> dict:
        cfg, issues = self.parse_config(config_json)
        if cfg is None or any(i["severity"] == "error" for i in issues):
            return {"ok": False, "issues": issues}
        disc, _, _, _ = self.pool(cfg.reader)
        eng, obs = run_engine(cfg, disc, self.source)
        rep = eng.report()
        if self.context_base:
            rep["fields"] = [field for field in rep["fields"] if field["target"].startswith("context.")]
            obs = [item for item in obs if item["field"].startswith("context.")]
        if self.ext_base:
            from ..mapping.validate import list_issues
            scope = self.ext_scope(cfg)
            rep["fields"] = [f for i, f in enumerate(rep["fields"]) if i in scope]
            targets = {cfg.fields[i].target for i in scope}
            obs = [o for o in obs if o["field"] in targets]
            issues = issues + list_issues(obs, ontology.load(None, "ext-v1"))
            # Compact report: every turn re-sends history, so a full report per dry run inflates cost quickly.
            rep["fields"] = [{k: f[k] for k in ("target", "source_paths", "entity", "source_present", "emitted",
                                                "errors", "dropped", "error_examples") if f.get(k)}
                             for f in rep["fields"]]
        first_ids = list(dict.fromkeys(o["source_record_id"] for o in obs))[:2]
        examples = [{"field": o["field"], "value": _short(o["value"]), "raw": _short(o["raw_value"]),
                     **({"entity_role": o["entity_role"]} if o.get("entity_role") else {}),
                     **({"qualifiers": o["qualifiers"]} if o.get("qualifiers") else {})}
                    for o in obs if o["source_record_id"] in first_ids]
        out = {"ok": True, "partition": "discovery", "issues": issues, "report": rep, "example_observations": examples}
        if self.ext_base:
            out["change_log"] = self.ext_last_changes
        return out
