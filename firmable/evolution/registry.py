"""Immutable candidate versions, additive diffs and explicit production promotion."""
import copy
import json
import os
from pathlib import Path

from .. import ontology
from .schema import Proposal, digest


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def bootstrap():
    base = ontology.load(None, "ext-v1")
    concepts = {}
    for key, spec in base.fields.items():
        owner = ontology.FAMILY_ROLE_KINDS.get(spec.family, "business")
        concepts[key] = {"path": key, "type": spec.type, "owner": owner, "definition": spec.notes,
                         "values": list(spec.values), "multi": spec.multi,
                         "required_qualifiers": sorted(spec.required_qualifiers()),
                         "personal_data": spec.personal_data, "pattern": spec.pattern}
    return {"parent": None, "legacy_ontology_sha256": base.sha256,
            "entity_types": {"business": "The source's business/legal-person subject; legal form remains unknown unless stated.",
                             "licence": "An authorisation held by a business.",
                             "establishment": "A physical operating facility, separate from its operator."},
            "concepts": concepts, "relationships": {
                "HOLDS_LICENCE": {"from_type": "business", "to_type": "licence", "definition": "Business holds this licence."},
                "OPERATES_ESTABLISHMENT": {"from_type": "business", "to_type": "establishment", "definition": "Business operates this facility."}}}


def propose(base, proposal: Proposal, columns):
    result = copy.deepcopy(base)
    result["parent"] = digest(base)
    for entry in proposal.entity_types:
        if entry.name in result["entity_types"]:
            raise ValueError("Reuse existing entity type instead of redefining: " + entry.name)
        result["entity_types"][entry.name] = entry.definition
    for entry in proposal.concepts:
        if entry.path in result["concepts"]:
            raise ValueError("Cannot mutate an existing concept: " + entry.path)
        if entry.owner not in result["entity_types"]:
            raise ValueError("Unknown concept owner: " + entry.owner)
        if not set(entry.source_paths) <= set(columns):
            raise ValueError("Concept must cite observed source columns: " + entry.path)
        result["concepts"][entry.path] = entry.model_dump()
    for entry in proposal.relationships:
        if entry.name in result["relationships"]:
            raise ValueError("Cannot redefine a relationship: " + entry.name)
        if {entry.from_type, entry.to_type} - set(result["entity_types"]):
            raise ValueError("Unknown relationship endpoint type")
        result["relationships"][entry.name] = entry.model_dump(exclude={"name"})
    if set(proposal.reuse) - set(base["concepts"]):
        raise ValueError("Reuse names an unknown concept")
    return result


def compile_ontology(doc):
    """Build an isolated Ontology consumed by the unchanged generic Engine."""
    fields = {}
    for key, item in doc["concepts"].items():
        fields[key] = ontology.FieldSpec(path=key, type=item["type"], notes=item["definition"],
            values=tuple(item.get("values", [])), pattern=item.get("pattern"), multi=item.get("multi", False),
            qualifiers=tuple((q, "required") for q in item.get("required_qualifiers", [])),
            personal_data=item.get("personal_data", "never"))
    return ontology.Ontology(version="candidate-" + digest(doc)[:12], sha256=digest(doc), fields=fields)


class Registry:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def save(self, doc):
        version = digest(doc)
        path = self.root / "versions" / (version + ".json")
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != doc:
            raise ValueError("Immutable version collision")
        if not path.exists():
            write(path, doc)
        return version

    def load(self, version):
        if len(version) != 64 or any(c not in "0123456789abcdef" for c in version):
            raise ValueError("Invalid version hash")
        doc = json.loads((self.root / "versions" / (version + ".json")).read_text(encoding="utf-8"))
        if digest(doc) != version:
            raise ValueError("Ontology version hash mismatch")
        return doc

    def promote(self, version, reviewer, expected_current=None):
        if not reviewer.strip():
            raise ValueError("An explicit human reviewer is required")
        self.load(version)
        ready = self.root / "ready" / (version + ".json")
        if not ready.exists():
            raise ValueError("Version has not passed candidate validation")
        gate = json.loads(ready.read_text(encoding="utf-8"))
        import hashlib
        manifest_path = self.root.parent / "evidence-manifest.json"
        if not manifest_path.exists() or "manifest_sha256" not in gate:
            raise ValueError("Candidate evidence must be sealed before promotion")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if digest(manifest) != gate["manifest_sha256"]:
            raise ValueError("Evidence manifest changed")
        for name, expected in manifest.items():
            if hashlib.sha256((self.root.parent / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Evidence changed after sealing: " + name)
        result_path = self.root.parent / gate["source_id"] / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if digest(result) != gate["result_sha256"] or result["status"] != "AGENT_VALIDATED_CANDIDATE":
            raise ValueError("Candidate evidence changed since evaluation")
        from .schema import DynamicMapping
        mapping = DynamicMapping.model_validate_json((result_path.parent / "mapping.json").read_text(encoding="utf-8"))
        if mapping.digest() != result["mapping_digest"] or result["ontology_version"] != version:
            raise ValueError("Candidate mapping/version differs from evaluated evidence")
        lock = self.root / ".promotion.lock"
        with lock.open("x"):
            pass
        try:
            pointer = self.root / "production.json"
            current = json.loads(pointer.read_text()) if pointer.exists() else None
            if (current or {}).get("version") != expected_current:
                raise ValueError("Production changed since review; inspect the new diff")
            receipt = {"version": version, "previous": expected_current, "reviewer": reviewer,
                       "reviewer_kind": "human", "decision": "approved", "evidence_sha256": gate["result_sha256"]}
            with (self.root / "decisions.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(receipt) + "\n")
            write(pointer, receipt)
            return receipt
        finally:
            lock.unlink(missing_ok=True)
