"""Model-proposed equijoins verified on values before materialising a source view.

No arbitrary SQL and no entity-equivalence/ownership inference from a successful
join. The initial executor supports many-to-one/one-to-one star joins only.
"""
from collections import Counter, defaultdict
from typing import Literal

from pydantic import Field, model_validator

from ..mapping.schema import Strict
from ..evolution.schema import digest


class JoinStep(Strict):
    left_table: str
    right_table: str
    left_columns: list[str] = Field(min_length=1)
    right_columns: list[str] = Field(min_length=1)
    cardinality: Literal["many_to_one", "one_to_one"]
    meaning: str = Field(min_length=20)
    cautions: list[str]

    @model_validator(mode="after")
    def same_width(self):
        if len(self.left_columns) != len(self.right_columns):
            raise ValueError("Join keys have different arity")
        if self.left_table == self.right_table:
            raise ValueError("Self-joins require a separately reviewed role alias")
        return self


class JoinPlan(Strict):
    anchor: str
    steps: list[JoinStep] = Field(min_length=1, max_length=4)
    unsupported_requests: list[str] = Field(default_factory=list)

    def validate_tables(self, headers):
        if self.anchor not in headers:
            raise ValueError("Unknown anchor table")
        right_tables = set()
        for step in self.steps:
            if step.left_table != self.anchor:
                raise ValueError("Only star joins from the anchor are supported; do not pretend a multi-hop join ran")
            if step.right_table not in headers or step.right_table in right_tables:
                raise ValueError("Unknown or duplicate right table")
            right_tables.add(step.right_table)
            if set(step.left_columns) - set(headers[step.left_table]) or set(step.right_columns) - set(headers[step.right_table]):
                raise ValueError("Join references nonexistent source columns")


def key(row, columns):
    values = tuple("" if row.get(c) is None else str(row[c]).strip() for c in columns)
    return values if all(values) else None


def inspect_join(left_rows, right_rows, step):
    """Scan all supplied right rows; measure cardinality for the anchor cohort."""
    left_keys = Counter(k for row in left_rows if (k := key(row, step.left_columns)) is not None)
    index = defaultdict(list)
    right_count = 0
    for ordinal, row in enumerate(right_rows, 1):
        right_count += 1
        k = key(row, step.right_columns)
        if k in left_keys:
            index[k].append({"ordinal": ordinal, "row": row, "record_id": digest(row)})
    ambiguous = {k: len(v) for k, v in index.items() if len(v) != 1}
    bad_left = {k for k, n in left_keys.items() if step.cardinality == "one_to_one" and n != 1}
    matches, refusals = [], []
    for ordinal, row in enumerate(left_rows, 1):
        k = key(row, step.left_columns)
        reason = ("MISSING_LEFT_KEY" if k is None else "RIGHT_KEY_NOT_UNIQUE" if k in ambiguous else
                  "LEFT_KEY_NOT_UNIQUE" if k in bad_left else "NO_RIGHT_MATCH" if k not in index else None)
        if reason:
            matches.append(None)
            refusals.append({"left_ordinal": ordinal, "reason": reason, "key": k, "right_matches": len(index.get(k, []))})
        else:
            matches.append(index[k][0])
    counts = Counter(r["reason"] for r in refusals)
    joined = len(left_rows) - len(refusals)
    return matches, {"left_rows": len(left_rows), "right_rows_scanned": right_count, "matched_left_rows": joined,
        "match_rate": joined / max(1, len(left_rows)), "unique_left_keys": len(left_keys),
        "right_duplicate_keys_in_cohort": len(ambiguous), "left_duplicate_keys_in_cohort": sum(n > 1 for n in left_keys.values()),
        "refusal_reasons": dict(counts), "refusals": refusals,
        "would_be_inner_join_rows_without_guard": sum(left_keys[k] * len(v) for k, v in index.items()),
        "materialized_rows_per_left_max": 1, "semantic_equivalence_established": False,
        "passes_cardinality_gate": not ambiguous and not bad_left,
        "scope": "Key/cardinality checks cover the supplied anchor cohort, not all business identities."}


def materialize(plan, anchor_rows, table_readers, headers, source_fingerprints):
    plan.validate_tables(headers)
    view = [{plan.anchor + "." + k: v for k, v in row.items()} for row in anchor_rows]
    lineage = [{plan.anchor: {"record_id": digest(row), "ordinal": i,
                            "snapshot_sha256": source_fingerprints[plan.anchor]}} for i, row in enumerate(anchor_rows, 1)]
    reports = []
    for step in plan.steps:
        matches, report = inspect_join(anchor_rows, table_readers[step.right_table](), step)
        reports.append({"step": step.model_dump(), "measurement": report})
        for i, match in enumerate(matches):
            # Refuse ambiguous/nonmatching relationships; preserve the anchor and explicit nulls.
            for column in headers[step.right_table]:
                view[i][step.right_table + "." + column] = match["row"][column] if match else ""
            if match:
                lineage[i][step.right_table] = {"record_id": match["record_id"], "ordinal": match["ordinal"],
                                              "snapshot_sha256": source_fingerprints[step.right_table]}
    linked = [{"view_record_id": digest(row), "sources": evidence} for row, evidence in zip(view, lineage)]
    return view, linked, reports
