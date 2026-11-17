"""Pydantic contract for a mapping config. The agent emits this; the engine executes it.

One schema for everything: reader settings, record identity, field rules, constants,
and the explicit list of fields the agent declined to map.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .transforms import OPS

Grain = Literal["legal_entity", "business_name", "establishment", "licence_or_permit",
                "contract_or_grant", "event_or_notice", "mixed", "unknown"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReaderSpec(Strict):
    format: Literal["delimited", "xlsx", "json", "jsonl", "xml"]
    archive_member: str | None = Field(None, description="If the resource is a ZIP, the member file to read.")
    encoding: str = "utf-8-sig"
    delimiter: str | None = Field(None, description="delimited only, e.g. ',' or '\\t'")
    skip_rows: int = Field(0, ge=0, le=50, description="delimited/xlsx: rows to skip before the header row")
    sheet: str | None = Field(None, description="xlsx only")
    record_path: str | None = Field(None, description="json: dotted path to the record list; xml: record element tag")


class Step(Strict):
    op: str
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("op")
    @classmethod
    def known_op(cls, v):
        if v not in OPS:
            raise ValueError(f"unknown transform op '{v}'; allowed: {sorted(OPS)}")
        return v

    @model_validator(mode="after")
    def known_args(self):
        # Fail closed on arguments the op does not define: an invented arg would otherwise be ignored.
        import inspect
        params = set(inspect.signature(OPS[self.op][0]).parameters) - {"v", "_"}
        unknown = set(self.args) - params
        if unknown:
            raise ValueError(f"op '{self.op}' does not accept args {sorted(unknown)}; allowed: {sorted(params)}")
        return self


class RecordId(Strict):
    strategy: Literal["columns", "content_hash"]
    source_paths: list[str] = Field(default_factory=list, description="columns strategy: key columns")
    rationale: str = ""

    @model_validator(mode="after")
    def need_columns(self):
        if self.strategy == "columns" and not self.source_paths:
            raise ValueError("columns strategy needs source_paths")
        return self


class Condition(Strict):
    """Row-level guard: the rule applies only to records where this holds (e.g. a current-name flag)."""
    source_path: str
    op: Literal["equals", "not_equals", "in", "not_in", "present", "absent"]
    values: list[str] = Field(default_factory=list, description="compared case-insensitively after trimming")


class Qualifier(Strict):
    """A value that travels with a claim (period, currency, scheme, role): from a column or a constant."""
    source_path: str | None = None
    value: str | None = None
    steps: list[Step] = Field(default_factory=list)

    @model_validator(mode="after")
    def one_source(self):
        if (self.source_path is None) == (self.value is None):
            raise ValueError("a qualifier needs exactly one of source_path or value")
        return self


class FieldRule(Strict):
    source_paths: list[str] = Field(min_length=1, description="1 column, or several joined with join_with")
    join_with: str = " "
    when: Condition | None = None
    target: str
    valid_from_path: str | None = Field(None, description="column dating when THIS rule's claim became true")
    valid_to_path: str | None = Field(None, description="column dating when THIS rule's claim stopped being true")
    # None (not []) so configs that do not use it keep their digest - approvals stay valid.
    validity_date_formats: list[str] | None = Field(None, description="strptime formats for the two columns")
    claim_scope: Literal["current_legal_name", "former_legal_name", "company_registration", "charity_registration",
                         "entity_registration", "entity_contact_address", "registered_office", "licence_holder_address",
                         "licensed_premises", "establishment_address", "correspondence_address"] | None = None
    steps: list[Step] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, description="field_confidence: how sure the mapping+parse is right")
    rationale: str = Field(min_length=5)
    # Extension DSL (None keeps the digests of configs written before it existed).
    entity: str | None = Field(None, description="record role this claim describes (see MappingConfig.entities); "
                                                 "None = the subject business")
    qualifiers: dict[str, Qualifier] | None = Field(None, description="period / currency / scheme / role values "
                                                                      "carried with each claim")
    one_hot: bool | None = Field(None, description="source_paths are indicator columns (Y / blank): each column "
                                                   "that is set contributes its COLUMN NAME as one raw value, "
                                                   "which then goes through steps")

    @model_validator(mode="after")
    def one_hot_needs_columns(self):
        if self.one_hot and len(self.source_paths) < 2:
            raise ValueError("a one_hot rule reads two or more indicator columns")
        return self

    @model_validator(mode="after")
    def scope_matches_target(self):
        scope = self.claim_scope
        if scope is None:
            return self
        expected = ("entity.legal_name" if scope.endswith("legal_name") else
                    "entity.date_registered" if scope.endswith("registration") else "address.")
        if self.target != expected and not (expected == "address." and self.target.startswith(expected)):
            raise ValueError(f"claim scope {scope!r} does not apply to {self.target!r}")
        return self


class ConstantRule(Strict):
    target: str
    value: str
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=5)
    entity: str | None = None
    claim_scope: Literal["entity_contact_address", "registered_office", "licence_holder_address",
                         "licensed_premises", "establishment_address", "correspondence_address"] | None = None

    @model_validator(mode="after")
    def address_scope(self):
        if self.claim_scope and not self.target.startswith("address."):
            raise ValueError("An address scope requires an address target")
        return self


class Unmapped(Strict):
    source_path: str
    reason: str


class ObservedAt(Strict):
    source_path: str | None = Field(None, description="column holding when the source stated the claim, if any")
    steps: list[Step] = Field(default_factory=list)
    fallback: Literal["resource_last_modified", "dataset_metadata_modified"] = "resource_last_modified"


class EntityBlock(Strict):
    """A second thing one row describes (review 5.3): a licence or a premises/site next to the business."""
    kind: Literal["business", "licence", "establishment"]
    key_paths: list[str] = Field(default_factory=list, description="columns that identify this entity across "
                                                                   "snapshots (e.g. licence number); empty = row-scoped")
    rationale: str = Field(min_length=5)


RELATIONSHIP_KINDS = {"HOLDS_LICENCE": ("business", "licence"),
                      "OPERATES_ESTABLISHMENT": ("business", "establishment"),
                      "LICENCE_AT_ESTABLISHMENT": ("licence", "establishment")}


class RelationshipRule(Strict):
    type: Literal["HOLDS_LICENCE", "OPERATES_ESTABLISHMENT", "LICENCE_AT_ESTABLISHMENT"]
    from_role: str
    to_role: str
    rationale: str = Field(min_length=5)


SUBJECT = "subject"


class MappingConfig(Strict):
    source_id: str
    record_grain: Grain
    grain_rationale: str
    reader: ReaderSpec
    record_id: RecordId
    observed_at: ObservedAt = Field(default_factory=ObservedAt)
    fields: list[FieldRule]
    constants: list[ConstantRule] = Field(default_factory=list)
    unmapped: list[Unmapped] = Field(default_factory=list)
    notes: str = ""
    profile_context: Literal["v1"] | None = None
    extensions: Literal["ext-v1"] | None = None
    entities: dict[str, EntityBlock] | None = Field(None, description="extra roles one row describes; the business "
                                                                      "the row is about is the implicit 'subject'")
    relationships: list[RelationshipRule] | None = None

    @model_validator(mode="after")
    def roles_declared(self):
        roles = {SUBJECT: "business"} | {k: v.kind for k, v in (self.entities or {}).items()}
        if self.entities and SUBJECT in self.entities:
            raise ValueError("'subject' is the implicit business role; do not redeclare it")
        for rule in [*self.fields, *self.constants]:
            if rule.entity is not None and rule.entity not in roles:
                raise ValueError(f"rule for {rule.target} uses undeclared entity role {rule.entity!r}")
        for rel in self.relationships or []:
            kinds = (roles.get(rel.from_role), roles.get(rel.to_role))
            if None in kinds:
                raise ValueError(f"relationship {rel.type} uses an undeclared role")
            if kinds != RELATIONSHIP_KINDS[rel.type]:
                raise ValueError(f"{rel.type} must link {RELATIONSHIP_KINDS[rel.type]}, not {kinds}")
        if (self.entities or self.relationships or any(r.entity or r.qualifiers for r in self.fields)
                or any(c.entity for c in self.constants)) \
                and not self.extensions:
            raise ValueError("entities, relationships, roles and qualifiers need extensions: ext-v1")
        return self

    def role_kind(self, role: str | None) -> str:
        if role in (None, SUBJECT):
            return "business"
        return self.entities[role].kind

    def digest(self) -> str:
        # exclude_none keeps digests stable when optional DSL features are added later.
        return hashlib.sha256(json.dumps(self.model_dump(exclude_none=True), sort_keys=True).encode()).hexdigest()


class ProfileContextDraft(Strict):
    fields: list[FieldRule] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def scoped_fields(cls, fields):
        if any(not rule.target.startswith("context.") or len(rule.source_paths) != 1 for rule in fields):
            raise ValueError("Each supplemental rule must map one source column to a context.* field")
        return fields

    def extend(self, base: MappingConfig) -> MappingConfig:
        if base.profile_context:
            raise ValueError("Expected a canonical-only base mapping")
        covered = {rule.source_paths[0] for rule in self.fields}
        new_columns = covered - {item.source_path for item in base.unmapped}
        if new_columns:
            raise ValueError(f"Context rules must use previously unmapped columns: {sorted(new_columns)}")
        return base.model_copy(update={"profile_context": "v1", "fields": base.fields + self.fields,
                                       "unmapped": [item for item in base.unmapped if item.source_path not in covered]})


class BaseRuleEdit(Strict):
    """A change to one rule of the APPROVED config. Attribute edits (role, scope, claim validity) are always
    allowed. Replacing or removing a rule is allowed only where a current deterministic gate fails on it, or
    for legacy record-level observation.* rules the engine ignores."""
    index: int = Field(ge=0)
    entity: str | None = None
    claim_scope: str | None = None
    valid_from_path: str | None = None
    valid_to_path: str | None = None
    validity_date_formats: list[str] | None = None
    replace_with: FieldRule | None = None
    remove: bool = False
    reason: str = Field(min_length=5)


class ExtensionDraft(Strict):
    """What the extension agent submits: additions to an approved mapping, never a rewrite of it."""
    entities: dict[str, EntityBlock] | None = None
    relationships: list[RelationshipRule] | None = None
    new_rules: list[FieldRule] = Field(default_factory=list)
    base_rule_edits: list[BaseRuleEdit] = Field(default_factory=list)
    unmapped: list[Unmapped] = Field(default_factory=list)
    notes: str = ""

    def apply(self, base: MappingConfig, editable: set[int]) -> tuple[MappingConfig, list[str], list[dict]]:
        """Merge into `base`. Returns (config, discarded edits, change log). Reader, record_id, grain and
        observed_at always come from the approved config."""
        if base.extensions or base.profile_context:
            raise ValueError("Expected a canonical-only approved mapping as the base")
        fields = [rule.model_copy(deep=True) for rule in base.fields]
        discarded, changes, removed = [], [], set()
        for edit in self.base_rule_edits:
            if edit.index >= len(fields):
                discarded.append(f"edit #{edit.index}: no such base rule")
                continue
            rule = fields[edit.index]
            legacy = rule.target.startswith("observation.")
            if edit.remove:
                if edit.index in editable or legacy:
                    removed.add(edit.index)
                    changes.append({"index": edit.index, "change": "removed", "target": rule.target,
                                    "reason": edit.reason})
                else:
                    discarded.append(f"remove #{edit.index} {rule.target}: approved rule passes the current gates")
                continue
            if edit.replace_with is not None:
                if edit.index in editable:
                    fields[edit.index] = edit.replace_with
                    changes.append({"index": edit.index, "change": "replaced", "target": rule.target,
                                    "new_target": edit.replace_with.target, "reason": edit.reason})
                else:
                    discarded.append(f"replace #{edit.index} {rule.target}: approved rule passes the current gates")
                continue
            update = {k: getattr(edit, k) for k in ("entity", "claim_scope", "valid_from_path", "valid_to_path",
                                                     "validity_date_formats") if getattr(edit, k) is not None}
            if not update:
                discarded.append(f"edit #{edit.index}: nothing to change")
                continue
            try:
                fields[edit.index] = FieldRule.model_validate(rule.model_dump() | update)
            except ValueError as e:
                discarded.append(f"edit #{edit.index} {rule.target}: {str(e)[:200]}")
                continue
            changes.append({"index": edit.index, "change": "attributes", "target": rule.target, **update,
                            "reason": edit.reason})
        fields = [rule for i, rule in enumerate(fields) if i not in removed] + list(self.new_rules)
        changes.extend({"change": "added", "target": rule.target, "source_paths": rule.source_paths,
                        "entity": rule.entity} for rule in self.new_rules)
        used = set()
        for rule in fields:
            used.update(rule.source_paths)
            used.update(p for p in (rule.valid_from_path, rule.valid_to_path) if p)
            used.update(q.source_path for q in (rule.qualifiers or {}).values() if q.source_path)
            if rule.when:
                used.add(rule.when.source_path)
        for block in (self.entities or {}).values():
            used.update(block.key_paths)
        reasons = {u.source_path: u for u in base.unmapped} | {u.source_path: u for u in self.unmapped}
        unmapped = [u for p, u in reasons.items() if p not in used]
        notes = (base.notes + "\n\n" if base.notes else "") + f"[ext-v1] {self.notes}".strip()
        cfg = MappingConfig.model_validate(base.model_dump() | {
            "fields": [rule.model_dump() for rule in fields], "unmapped": [u.model_dump() for u in unmapped],
            "notes": notes, "extensions": "ext-v1",
            "entities": {k: v.model_dump() for k, v in (self.entities or {}).items()} or None,
            "relationships": [r.model_dump() for r in self.relationships or []] or None})
        return cfg, discarded, changes


def json_schema() -> dict:
    return MappingConfig.model_json_schema()
