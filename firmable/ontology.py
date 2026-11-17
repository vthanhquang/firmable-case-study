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
from .paths import ONTOLOGY, ROOT

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
    # Extension-registry metadata (config/ontology_extensions.yaml); defaults describe a core field.
    family: str | None = None
    multi: bool = False
    temporal: bool = False
    key: bool = False
    crosswalk: bool = False
    qualifiers: tuple = ()          # ((name, "required"|"optional"), ...)
    personal_data: str = "never"
    max_level: str = "L1"

    def required_qualifiers(self) -> set[str]:
        return {name for name, need in self.qualifiers if need == "required"}


@dataclass
class Ontology:
    version: str
    sha256: str
    fields: dict[str, FieldSpec] = field(default_factory=dict)

    def has(self, path: str) -> bool:
        return path in self.fields

    def mappable(self) -> dict[str, FieldSpec]:
        return {p: f for p, f in self.fields.items()
                if p.split(".")[0] in MAPPABLE_SECTIONS or p.startswith(("context.", "ext."))
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
            if f.family:
                d.update({k: v for k, v in (("multi", f.multi), ("temporal", f.temporal), ("crosswalk_required", f.crosswalk),
                                            ("qualifiers", dict(f.qualifiers)), ("personal_data", f.personal_data),
                                            ("attaches_to", FAMILY_ROLE_KINDS[f.family]))
                          if v and v != "never"})
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
        if f.type == "integer":
            return None if type(value) is int else "INTEGER_INVALID"
        if f.type == "decimal":
            return None if type(value) in (int, float) else "DECIMAL_INVALID"
        if f.type == "point":
            return None if isinstance(value, str) and _point_ok(value) else "POINT_INVALID"
        if f.type == "phone":
            return None if isinstance(value, str) and re.fullmatch(r"\+61[0-9]{8,10}", value) else "PHONE_INVALID"
        if f.type == "domain":
            return None if isinstance(value, str) and re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", value) else "DOMAIN_INVALID"
        if f.type == "email":
            return None if isinstance(value, str) and re.fullmatch(r"[a-z0-9._%+'-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", value)                 else "EMAIL_INVALID"
        if not isinstance(value, str):
            return "STRING_EXPECTED"
        if f.pattern and not re.match(f.pattern, value):
            return "PATTERN_MISMATCH"
        if path in _CHECKSUMS and not _CHECKSUMS[path](value):
            return "CHECKSUM_INVALID"
        return None


# Which declared record role (mapping config `entities`) each extension family may attach to.
FAMILY_ROLE_KINDS = {"entity": "business", "financial": "business", "licence": "licence",
                     "establishment": "establishment", "contact": "any"}
EXTENSIONS = ROOT / "config" / "ontology_extensions.yaml"


def _point_ok(value: str) -> bool:
    try:
        lat, lon = (float(x) for x in value.split(","))
    except ValueError:
        return False
    from .mapping.transforms import AU_BBOX
    return AU_BBOX["lat"][0] <= lat <= AU_BBOX["lat"][1] and AU_BBOX["lon"][0] <= lon <= AU_BBOX["lon"][1]


@lru_cache(maxsize=8)
def load(profile_context: str | None = None, extensions: str | None = None) -> Ontology:
    raw_bytes = ONTOLOGY.read_bytes()
    doc = yaml.safe_load(raw_bytes)
    sections = {key: doc.get(key) or {} for key in ("entity", "address", "observation", "confidence")}
    version = str(doc["version"])
    if profile_context:
        extension = (ROOT / "config/profile_context.yaml").read_bytes()
        context = yaml.safe_load(extension)
        if profile_context != context["version"]:
            raise ValueError(f"Unknown profile context schema {profile_context}")
        sections["context"] = context["fields"]
        raw_bytes += b"\0" + extension
        version += f"+profile-context-{profile_context}"
    registry = {}
    if extensions:
        ext_bytes = EXTENSIONS.read_bytes()
        doc_ext = yaml.safe_load(ext_bytes)
        if extensions != doc_ext["version"]:
            raise ValueError(f"Unknown extension registry {extensions}")
        registry = doc_ext["families"]
        raw_bytes += b"\0" + ext_bytes
        version += f"+{extensions}"
    onto = Ontology(version=version, sha256=hashlib.sha256(raw_bytes).hexdigest())
    for family, concepts in registry.items():
        if family not in FAMILY_ROLE_KINDS:
            raise ValueError(f"Unknown extension family {family}")
        for name, spec in concepts.items():
            path = f"ext.{family}.{name}"
            onto.fields[path] = FieldSpec(
                path=path, type=spec.get("type", "string"), values=tuple(spec.get("values", ()) or ()),
                pattern=spec.get("pattern"), notes=" ".join(str(spec.get("notes", "")).split()),
                family=family, multi=bool(spec.get("multi")), temporal=bool(spec.get("temporal")),
                key=bool(spec.get("key")), crosswalk=bool(spec.get("crosswalk")),
                qualifiers=tuple(sorted((spec.get("qualifiers") or {}).items())),
                personal_data=spec.get("personal_data", "never"), max_level=spec.get("max_level", "L1"))
    for section, fields in sections.items():
        for name, spec in fields.items():
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
