from firmable.evolution2.questions import Question, evaluate_question


def observation(**kwargs):
    return {"source_record_id": "r", "source_fields": ["Revenue"], "value": 10,
            "entity_kind": "business", "entity_ref": "b", "observation_id": "o", "source_row_ordinal": 1,
            "snapshot_sha256": "sha", "qualifiers": {"period": "2024", "currency": "AUD"}, **kwargs}


def test_question_requires_owner_currency_period_and_provenance():
    question = Question("revenue", "Reported revenue for which period?", (("Revenue",),), ("business",), True, True)
    assert evaluate_question(question, [observation()], [], input_records=1)["status"] == "SUPPORTED_IN_CANDIDATE"
    for changed, reason in [({"entity_kind": "contract"}, "wrong_owner"), ({"qualifiers": {"currency": "AUD"}}, "missing_period"),
                            ({"qualifiers": {"period": "2024-01-01", "currency": "AUD"}}, "missing_period"),
                            ({"qualifiers": {"period": "2024"}}, "missing_currency"), ({"snapshot_sha256": None}, "missing_provenance")]:
        result = evaluate_question(question, [observation(**changed)], [], input_records=1)
        assert result["status"] == "PARTIAL" and result["violations_by_row"][reason] == 1


def test_source_cooccurrence_does_not_attach_facts_to_business():
    question = Question("revenue", "Reported charity revenue?", (("Revenue",),), ("charity",), True, True)
    obs = [observation(entity_kind="charity", entity_ref="c"), observation(source_fields=["ABN"])]
    result = evaluate_question(question, obs, [], input_records=1)
    assert result["rows_meeting_evidence_contract"] == 1 and result["rows_connected_to_business"] == 0
    result = evaluate_question(question, obs, [{"from_ref": "c", "to_ref": "b"}], input_records=1)
    assert result["rows_connected_to_business"] == 1


def test_privacy_suppressed_and_missing_values_are_not_useful_coverage():
    question = Question("revenue", "Reported revenue?", (("Revenue",),))
    result = evaluate_question(question, [observation(privacy="personal")], [], input_records=1)
    assert result["rows_meeting_evidence_contract"] == 0
    assert evaluate_question(question, [], [], input_records=1)["status"] == "UNSUPPORTED"
