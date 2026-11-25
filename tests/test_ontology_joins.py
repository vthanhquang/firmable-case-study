import pytest

from firmable.evolution2.joins import JoinPlan, JoinStep, inspect_join, materialize


def step(cardinality="many_to_one"):
    return JoinStep(left_table="activity", right_table="application", left_columns=["type", "number"],
                    right_columns=["type", "number"], cardinality=cardinality,
                    meaning="Party activity references the IP application; not evidence of current ownership", cautions=["Agent is not owner"])


def test_composite_key_prevents_cross_type_matches_and_preserves_role():
    left = [{"type": "patent", "number": "1", "role": "agent"}, {"type": "trademark", "number": "1", "role": "applicant"}]
    right = [{"type": "patent", "number": "1", "status": "expired"}]
    matches, report = inspect_join(left, right, step())
    assert matches[0]["row"]["status"] == "expired" and matches[1] is None
    assert report["refusal_reasons"] == {"NO_RIGHT_MATCH": 1}
    assert not report["semantic_equivalence_established"]


def test_duplicate_right_keys_are_refused_not_multiplied():
    left = [{"type": "patent", "number": "1"}] * 3
    right = [{"type": "patent", "number": "1", "status": "expired"}, {"type": "patent", "number": "1", "status": "active"}]
    matches, report = inspect_join(left, right, step())
    assert matches == [None] * 3
    assert not report["passes_cardinality_gate"]
    assert report["would_be_inner_join_rows_without_guard"] == 6


def test_one_to_one_and_null_keys_do_not_silently_match():
    left = [{"type": "patent", "number": "1"}, {"type": "patent", "number": "1"}, {"type": "patent", "number": ""}]
    matches, report = inspect_join(left, [{"type": "patent", "number": "1"}], step("one_to_one"))
    assert not any(matches)
    assert report["refusal_reasons"] == {"LEFT_KEY_NOT_UNIQUE": 2, "MISSING_LEFT_KEY": 1}
    matches, report = inspect_join([{"type": "patent", "number": None}], [{"type": "patent", "number": None}], step())
    assert matches == [None] and report["refusal_reasons"] == {"MISSING_LEFT_KEY": 1}


def test_materialized_view_retains_both_source_hashes_without_entity_merge():
    left = [{"type": "patent", "number": "1", "role": "agent"}]
    right = [{"type": "patent", "number": "1", "status": "expired"}]
    plan = JoinPlan(anchor="activity", steps=[step()])
    view, lineage, reports = materialize(plan, left, {"application": lambda: iter(right)},
        {"activity": list(left[0]), "application": list(right[0])}, {"activity": "hash-a", "application": "hash-b"})
    assert view[0]["activity.role"] == "agent" and view[0]["application.status"] == "expired"
    assert lineage[0]["sources"]["activity"]["snapshot_sha256"] == "hash-a"
    assert lineage[0]["sources"]["application"]["snapshot_sha256"] == "hash-b"
    plan.steps[0].left_columns = ["invented"]
    with pytest.raises(ValueError):
        plan.validate_tables({"activity": list(left[0]), "application": list(right[0])})
