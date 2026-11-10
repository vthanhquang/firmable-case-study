"""Loads firmable_ontology.yaml and exposes it as a registry of canonical paths.

The YAML is the contract: mapping configs may only target paths that exist here,
and every emitted value is type-checked against it.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from . import ids
from .paths import ONTOLOGY

# Sections whose fields a source column may be mapped to. `observation.*` fields that
# describe validity time are mappable too (a source may say when a claim became true).
MAPPABLE_SECTIONS = ("entity", "address")
MAPPABLE_OBSERVATION_FIELDS = ("valid_from", "valid_to", "observed_at")

_CHECKSUMS = {"entity.abn": ids.is_valid_abn, "entity.acn": ids.is_valid_acn, "entity.nzbn": ids.is_valid_nzbn}


@dataclass(frozen=True)
class FieldSpec:
    path: str
    type: str
    values: tuple = ()
    pattern: str | None = None
    notes: str = ""
    default: str | None = None
    required: bool = False


@dataclass
class Ontology:
    version: str
    sha256: str
    fields: dict[str, FieldSpec] = field(default_factory=dict)

    def has(self, path: str) -> bool:
        return path in self.fields

    def mappable(self) -> dict[str, FieldSpec]:
        return {p: f for p, f in self.fields.items()
                if p.split(".")[0] in MAPPABLE_SECTIONS
                or (p.startswith("observation.") and p.split(".")[1] in MAPPABLE_OBSERVATION_FIELDS)}

    def describe(self) -> list[dict]:
        """Compact, model-facing description of mappable targets."""
        out = []
        for p, f in self.mappable().items():
            d = {"path": p, "type": f.type}
            if f.values:
                d["values"] = list(f.values)
            if f.pattern:
                d["pattern"] = f.pattern
            if f.notes:
                d["notes"] = f.notes
            if f.default:
                d["default"] = f.default
            out.append(d)
        return out

    def check_value(self, path: str, value) -> str | None:
        """Return None if `value` is a valid instance of the canonical field, else an error code."""
        f = self.fields.get(path)
        if f is None:
            return "UNKNOWN_TARGET"
        if value is None or value == "":
            return "EMPTY"
        if f.type == "enum":
            return None if value in f.values else "ENUM_VALUE_INVALID"
        if f.type == "date":
            try:
                dt.date.fromisoformat(str(value))
            except ValueError:
                return "DATE_INVALID"
            return None
        if f.type == "datetime":
            try:
                dt.datetime.fromisoformat(str(value))
            except ValueError:
                return "DATETIME_INVALID"
            return None
        if f.type == "float":
            return None if isinstance(value, (int, float)) else "FLOAT_INVALID"
        if not isinstance(value, str):
            return "STRING_EXPECTED"
        if f.pattern and not re.match(f.pattern, value):
            return "PATTERN_MISMATCH"
        if path in _CHECKSUMS and not _CHECKSUMS[path](value):
            return "CHECKSUM_INVALID"
        return None


@lru_cache(maxsize=1)
def load() -> Ontology:
    raw_bytes = ONTOLOGY.read_bytes()
    doc = yaml.safe_load(raw_bytes)
    onto = Ontology(version=str(doc.get("version")), sha256=hashlib.sha256(raw_bytes).hexdigest())
    for section in ("entity", "address", "observation", "confidence"):
        for name, spec in (doc.get(section) or {}).items():
            path = f"{section}.{name}"
            onto.fields[path] = FieldSpec(
                path=path,
                type=spec.get("type", "string"),
                values=tuple(spec.get("values", ()) or ()),
                pattern=spec.get("pattern"),
                notes=" ".join(str(spec.get("notes", "")).split()),
                default=spec.get("default"),
                required=bool(spec.get("required", False)),
            )
    return onto
