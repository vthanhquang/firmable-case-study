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


class FieldRule(Strict):
    source_paths: list[str] = Field(min_length=1, description="1 column, or several joined with join_with")
    join_with: str = " "
    when: Condition | None = None
    target: str
    valid_from_path: str | None = Field(None, description="column dating when THIS rule's claim became true")
    valid_to_path: str | None = Field(None, description="column dating when THIS rule's claim stopped being true")
    # None (not []) so configs that do not use it keep their digest - approvals stay valid.
    validity_date_formats: list[str] | None = Field(None, description="strptime formats for the two columns")
    steps: list[Step] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1, description="field_confidence: how sure the mapping+parse is right")
    rationale: str = Field(min_length=5)


class ConstantRule(Strict):
    target: str
    value: str
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=5)


class Unmapped(Strict):
    source_path: str
    reason: str


class ObservedAt(Strict):
    source_path: str | None = Field(None, description="column holding when the source stated the claim, if any")
    steps: list[Step] = Field(default_factory=list)
    fallback: Literal["resource_last_modified", "dataset_metadata_modified"] = "resource_last_modified"


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

    def digest(self) -> str:
        # exclude_none keeps digests stable when optional DSL features are added later.
        return hashlib.sha256(json.dumps(self.model_dump(exclude_none=True), sort_keys=True).encode()).hexdigest()


def json_schema() -> dict:
    return MappingConfig.model_json_schema()
