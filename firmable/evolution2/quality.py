"""Evidence accounting, actionable gates and bounded revision decisions."""
import re
from collections import Counter

from ..evolution.engine import validate_mapping
from ..evolution.schema import digest


def quality(report):
    reasons = Counter()
    for field in report["fields"]:
        reasons.update(field["errors"])
    abstentions = {k: n for k, n in reasons.items() if k.startswith("QUALIFIER_MISSING_")}
    rejected = sum(abstentions.values())
    malformed = sum(reasons.values()) - rejected
    eligible = max(0, report["present_values"] - rejected)
    record_failures = sum(report.get("record_errors", {}).values())
    return {"present_values": report["present_values"], "emitted_observations": report["observations"],
            "withheld_missing_context": rejected, "abstention_reasons": abstentions,
            "malformed_values": malformed, "malformed_reasons": {k: n for k, n in reasons.items() if k not in abstentions},
            "eligible_present_values": eligible, "malformed_rate": malformed / max(eligible, 1),
            "abstention_rate": rejected / max(report["present_values"], 1),
            "record_errors": report.get("record_errors", {}),
            "passes_technical_gate": bool(report["observations"]) and malformed / max(eligible, 1) <= .05 and record_failures == 0,
            "semantic_precision": None,
            "note": "Missing required context remains withheld. This gate does not establish semantic truth or useful coverage."}


def mapping_findings(cfg, registry, columns):
    errors = validate_mapping(cfg, registry, columns)
    findings = []
    for i, field in enumerate(cfg.fields):
        if field.target in ("observation.valid_from", "observation.valid_to"):
            findings.append({"code": "METADATA_AS_FIELD", "location": f"fields[{i}]", "target": field.target,
                "correction": "Remove this metadata field. Put claim_period.from_column/to_column on the actual dated claim, or propose an owned date concept for a standalone reported date."})
    for error in errors:
        findings.append({"code": "STATIC_MAPPING_GATE", "detail": error})
    consumed = {c for f in cfg.fields for c in f.source_paths}
    overlap = consumed & {u.source_path for u in cfg.unmapped}
    if overlap:
        findings.append({"code": "MAPPED_AND_DECLINED", "columns": sorted(overlap), "correction": "A value column cannot be both emitted and declared unmapped."})
    return findings


class ProgressGuard:
    def __init__(self):
        self.previous = None

    def stagnant(self, proposal, mapping, findings):
        signature = digest({"proposal": proposal, "mapping": mapping, "findings": findings})
        repeated = self.previous == signature
        self.previous = signature
        return repeated


def select_concepts(registry, columns, profile, purpose, limit=24):
    """Local lexical retrieval; candidate similarity never establishes equivalence."""
    terms = set(re.findall(r"[a-z]+", " ".join(columns).lower() + " " + purpose.lower()))
    stop = {"the", "of", "and", "a", "to", "in", "from", "for", "is", "as"}
    terms -= stop
    ranked = []
    for key, concept in registry["concepts"].items():
        if key.startswith(("observation.", "confidence.")):
            continue
        tokens = set(re.findall(r"[a-z]+", key.lower() + " " + concept["definition"].lower())) - stop
        score = len(terms & tokens) / max(1, len(terms | tokens))
        ranked.append((score, key))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    chosen = [key for score, key in ranked[:limit] if score > 0]
    return {"concepts": {key: registry["concepts"][key] for key in chosen},
            "entity_types": registry["entity_types"], "relationships": registry["relationships"],
            "retrieval": "Lexical shortlist only; reuse requires identical meaning, owner, units and scope. Missing candidates can be requested with a narrower task."}
