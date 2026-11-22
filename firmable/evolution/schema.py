"""Strict, source-independent contracts for ontology proposals and mappings."""
import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator
from ..mapping.schema import Strict, ReaderSpec, RecordId, ObservedAt, FieldRule, Unmapped


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class Binding(Strict):
    """Select exactly one nested object by a discriminator, never silently take index zero."""
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    collection: str
    filter_path: str | None = None
    filter_value: str | None = None


class Inspection(Strict):
    reader: ReaderSpec
    bindings: list[Binding] = Field(default_factory=list)
    grain: str
    identity_cautions: list[str]
    rationale: str


class Concept(Strict):
    path: str = Field(pattern=r"^dyn\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    type: Literal["string", "integer", "decimal", "date", "datetime", "enum"]
    owner: str
    definition: str = Field(min_length=20)
    values: list[str] = Field(default_factory=list)
    multi: bool = False
    required_qualifiers: list[str] = Field(default_factory=list)
    source_paths: list[str] = Field(min_length=1)
    why_not_existing: str = Field(min_length=20)
    personal_data: Literal["never", "always"] = "never"

    @model_validator(mode="after")
    def enum_values(self):
        if self.type == "enum" and not self.values:
            raise ValueError("Enums need explicit values")
        return self


class EntityType(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    definition: str = Field(min_length=20)


class Relation(Strict):
    name: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    from_type: str
    to_type: str
    definition: str = Field(min_length=20)


class Proposal(Strict):
    entity_types: list[EntityType] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    relationships: list[Relation] = Field(default_factory=list)
    reuse: dict[str, str] = Field(default_factory=dict, description="existing target -> why it fits")
    unmapped: list[Unmapped] = Field(default_factory=list)


class Role(Strict):
    kind: str
    key_paths: list[str] = Field(default_factory=list)
    rationale: str


class Edge(Strict):
    type: str
    from_role: str
    to_role: str
    rationale: str


class DynamicMapping(Strict):
    source_id: str
    record_grain: str
    grain_rationale: str
    reader: ReaderSpec
    record_id: RecordId
    observed_at: ObservedAt = Field(default_factory=ObservedAt)
    fields: list[FieldRule] = Field(min_length=1)
    entities: dict[str, Role] = Field(default_factory=dict)
    relationships: list[Edge] = Field(default_factory=list)
    unmapped: list[Unmapped] = Field(default_factory=list)
    notes: str = ""
    # Interface consumed by the existing Engine. No new constant/default claims.
    constants: list = Field(default_factory=list, max_length=0)
    profile_context: None = None
    extensions: str | None = "dynamic"

    def digest(self):
        return digest(self.model_dump(exclude_none=True))

    def role_kind(self, role):
        return "business" if role in (None, "subject") else self.entities[role].kind


class BlockingFinding(Strict):
    field: str
    actual: str = Field(min_length=3)
    expected: str = Field(min_length=3)
    evidence: str = Field(min_length=10)
    correction: str = Field(min_length=10)


class Critique(Strict):
    verdict: Literal["accept", "revise", "reject"]
    findings: list[str]
    semantic_risks: list[str]
    checked_reuse: list[str]
    rationale: str
    blocking_findings: list[BlockingFinding] = Field(default_factory=list)
