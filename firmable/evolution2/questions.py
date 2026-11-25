"""Executable evidence requirements for business questions, independent of mapping.

These checks establish availability, scope and connectivity, not semantic precision.
Question specifications are evaluation contracts, never source parsing rules.
"""
from collections import defaultdict
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Question:
    key: str
    text: str
    columns: tuple[tuple[str, ...], ...]
    allowed_owners: tuple[str, ...] = ()
    require_period: bool = False
    require_currency: bool = False
    requires_context_columns: tuple[str, ...] = ()


def matches(obs, columns):
    return any(path.rsplit(".", 1)[-1].casefold() in {c.casefold() for c in columns} for path in obs.get("source_fields", []))


def has_period(obs):
    q = obs.get("qualifiers", {})
    if (obs.get("valid_from") and obs.get("valid_to")) or (q.get("period_start") and q.get("period_end")):
        return True
    # A lone start date is not a reporting interval. Named reporting years are.
    return any(re.fullmatch(r"(?:FY\s*)?\d{4}(?:\s*[-/]\s*\d{2,4})?", str(v), re.I)
               for k, v in q.items() if k in ("period", "reporting_period", "reporting_year", "financial_year"))


def company_connected(observations, edges):
    """Only declared edges count. Co-occurring rows do not imply identity."""
    connected = {o["entity_ref"] for o in observations if o.get("entity_kind") == "business" and o.get("privacy") != "personal"}
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if edge["from_ref"] in connected or edge["to_ref"] in connected:
                before = len(connected)
                connected.update((edge["from_ref"], edge["to_ref"]))
                changed |= len(connected) != before
    return connected


def evaluate_question(question, observations, edges, *, input_records):
    by_row = defaultdict(list)
    for obs in observations:
        by_row[obs["source_record_id"]].append(obs)
    connected = company_connected(observations, edges)
    raw_rows, bounded_rows, profile_rows, violations, examples = 0, 0, 0, defaultdict(int), []
    for rid, row in by_row.items():
        groups = [[o for o in row if matches(o, cols)] for cols in question.columns]
        if not all(groups):
            continue
        raw_rows += 1
        evidence = [o for group in groups for o in group]
        failures = set()
        for obs in evidence:
            if question.allowed_owners and obs.get("entity_kind") not in question.allowed_owners:
                failures.add("wrong_owner")
            if question.require_period and not has_period(obs):
                failures.add("missing_period")
            if question.require_currency and not obs.get("qualifiers", {}).get("currency"):
                failures.add("missing_currency")
            if not all(obs.get(k) for k in ("snapshot_sha256", "source_row_ordinal", "source_fields", "observation_id")):
                failures.add("missing_provenance")
            if obs.get("privacy") == "personal":
                failures.add("privacy_suppressed")
        if question.requires_context_columns and not any(matches(o, question.requires_context_columns) for o in row):
            failures.add("missing_scope_context")
        for reason in failures:
            violations[reason] += 1
        if not failures:
            bounded_rows += 1
            if all(o["entity_ref"] in connected for o in evidence):
                profile_rows += 1
            if len(examples) < 3:
                examples.append({"record_id": rid, "claims": [{k: o.get(k) for k in (
                    "observation_id", "field", "value", "qualifiers", "entity_kind", "entity_role", "source_fields", "source_row_ordinal", "valid_from", "valid_to")} for o in evidence]})
    return {"question": question.text, "key": question.key, "input_records": input_records,
        "rows_with_requested_values": raw_rows, "rows_meeting_evidence_contract": bounded_rows,
        "rows_connected_to_business": profile_rows, "violations_by_row": dict(violations),
        "status": "SUPPORTED_IN_CANDIDATE" if profile_rows == bounded_rows and bounded_rows else "PARTIAL" if raw_rows else "UNSUPPORTED",
        "examples": examples, "scope": "Structural evidence check on this sample; not measured semantic accuracy or a production profile merge."}
