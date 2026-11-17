"""Evidence-bound review decisions kept separately from regenerated audit samples."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def evidence_digest(link: dict) -> str:
    payload = {key: link[key] for key in (
        "link_id", "source_a_record", "source_b_record", "canonical_entity_key",
        "policy_version", "confidence", "rule", "evidence", "a", "b",
    )}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode()).hexdigest()


def load_reviews(path: Path, links: dict) -> dict:
    latest = {}
    if not path.exists():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["reviewer_kind"] not in {"ai_assistant", "human"} or row["verdict"] not in {"pass", "fail", "uncertain"}:
            raise ValueError("Invalid review kind or verdict")
        if not row.get("reviewer", "").strip() or not row.get("note", "").strip():
            raise ValueError("Review must identify the reviewer and explain the verdict")
        link = links.get(row["link_id"])
        if link is None or row["evidence_sha256"] != evidence_digest(link):
            continue
        latest.setdefault(row["link_id"], {})[row["reviewer_kind"]] = row
    return latest


def mapping_evidence_digest(doc: dict, observations: Path, dependencies: list[Path]) -> str:
    """Bind an assessment to the proposal, frozen outputs and interpretation dependencies."""
    payload = {key: doc[key] for key in ("source_id", "run_id", "config_digest", "snapshot_sha256")}
    # A deterministic replay changes ingestion time, not the reviewed source evidence.
    # Retain all other provenance, source dates, roles, values and approval metadata.
    claims = []
    for line in observations.read_text(encoding="utf-8").splitlines():
        if line.strip():
            claim = json.loads(line)
            claim.pop("ingested_at", None)
            claim.pop("approval_state", None)  # Approval changes workflow state, not the assessed claim.
            claims.append(json.dumps(claim, sort_keys=True, separators=(",", ":")))
    payload["observations"] = hashlib.sha256("\n".join(sorted(claims)).encode()).hexdigest()
    payload["dependencies"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in dependencies}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def mapping_dependencies(config: dict, root: Path) -> list[Path]:
    tables = {step["args"]["table"] for rule in config["fields"] for step in rule["steps"]
              if step["op"] == "crosswalk"}
    return [root / name for name in ("firmable_ontology.yaml", "config/ontology_extensions.yaml",
            "firmable/mapping/engine.py", "firmable/mapping/transforms.py", "firmable/crosswalk.py")] + [
            root / "config/crosswalks" / (name + ".yaml") for name in sorted(tables)]


def load_mapping_assessments(path: Path, digests: dict[str, str]) -> dict:
    """Advisory assessments do not write or imply a human approval."""
    latest = {}
    if not path.exists():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["reviewer_kind"] != "ai_assistant" or row["verdict"] not in {"ready", "needs_changes"}:
            raise ValueError("Invalid mapping assessment kind or verdict")
        if not row.get("reviewer") or not row.get("summary"):
            raise ValueError("Mapping assessment must name its reviewer and explain its verdict")
        if digests.get(row["source_id"]) == row["evidence_sha256"]:
            latest[row["source_id"]] = row
    return latest
