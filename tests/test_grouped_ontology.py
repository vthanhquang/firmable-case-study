import json

import pytest
from pydantic import ValidationError

from firmable.evolution.registry import bootstrap
from firmable.evolution.schema import Inspection
from firmable.evolution2.contracts import GroupPlan, GroupIntent, SemanticField, ConceptPatch, resolve_patch, compile_fields, compile_mapping
from firmable.evolution2.quality import quality, ProgressGuard, select_concepts
from firmable.evolution2.pipeline import Controller, SourceBudget


def test_abstentions_are_separate_but_malformed_values_still_fail():
    report = {"present_values": 100, "observations": 60, "record_errors": {},
              "fields": [{"errors": {"QUALIFIER_MISSING_PERIOD": 40}}]}
    q = quality(report)
    assert q["withheld_missing_context"] == 40 and q["malformed_values"] == 0
    assert q["passes_technical_gate"] and q["abstention_rate"] == .4
    report["fields"][0]["errors"]["INVALID_DATE"] = 5
    assert not quality(report)["passes_technical_gate"]
    report["observations"] = 0
    assert not quality(report)["passes_technical_gate"]


def test_unparseable_record_time_is_not_hidden_by_value_gate():
    assert not quality({"present_values": 20, "observations": 20,
                        "record_errors": {"OBSERVED_AT_UNPARSEABLE": 1}, "fields": []})["passes_technical_gate"]


def test_semantic_date_compiler_scopes_dates_to_exact_claim():
    intent = GroupIntent.model_validate({"fields": [
        {"source_paths": ["Role"], "target": "dyn.party.role", "confidence": .9,
         "rationale": "The reported party role", "claim_period": {"from_column": "Start", "to_column": "End",
         "meaning": "Period during which this party holds this role"}},
        {"source_paths": ["Name"], "target": "entity.legal_name", "confidence": .9, "rationale": "Source legal name"}]})
    fields = compile_fields(intent)
    assert fields[0].valid_from_path == "Start" and fields[0].valid_to_path == "End"
    assert fields[1].valid_from_path is None and fields[1].valid_to_path is None
    assert all(not f.target.startswith("observation.") for f in fields)
    with pytest.raises(ValidationError, match="Metadata is generated"):
        SemanticField(source_paths=["Start"], target="observation.valid_from", confidence=.9, rationale="Reported start date")


def test_group_plan_requires_each_column_once_and_no_invented_keys():
    plan = GroupPlan.model_validate({"grain": "company", "groups": [
        {"name": "identity", "purpose": "Identifiers", "columns": ["ABN"]},
        {"name": "finance", "purpose": "Annual amounts", "columns": ["Amount"]}]})
    plan.check_columns(["ABN", "Amount"])
    with pytest.raises(ValueError, match="missing"):
        plan.check_columns(["ABN", "Amount", "Period"])
    plan.groups[1].columns.append("ABN")
    with pytest.raises(ValueError, match="Duplicates"):
        plan.check_columns(["ABN", "Amount"])


def test_progress_guard_stops_repeated_failure_but_allows_changed_mapping():
    guard = ProgressGuard()
    assert not guard.stagnant({"concept": 1}, {"value": 1}, ["wrong scope"])
    assert guard.stagnant({"concept": 1}, {"value": 1}, ["wrong scope"])
    assert not guard.stagnant({"concept": 1}, {"value": 2}, ["wrong scope"])


def test_retrieval_is_bounded_and_does_not_offer_executor_metadata():
    result = select_concepts(bootstrap(), ["ABN", "business name"], {}, "business identity", limit=5)
    assert 0 < len(result["concepts"]) <= 5
    assert not any(k.startswith("observation.") for k in result["concepts"])
    assert "entity.abn" in result["concepts"]


def test_source_budget_reserves_each_call_without_consuming_other_source_allowance(tmp_path, monkeypatch):
    from firmable import llm
    monkeypatch.setattr(llm, "LEDGER", llm.LEDGER)
    controller = Controller(tmp_path, live=True, per_source_budget=20000, total_budget=100000)
    (tmp_path / "usage.jsonl").write_text(json.dumps({"source_id": "expensive", "prompt_tokens": 19000}) + "\n")
    calls = []
    def fake_chat(*a, **kw):
        calls.append(kw["source_id"])
        return type("Message", (), {"content": '{"grain":"one row","groups":[{"name":"identity","purpose":"Name","columns":["Name"]}]} '})()
    monkeypatch.setattr(llm, "chat", fake_chat)
    with pytest.raises(SourceBudget):
        controller.agent("group_planner", "expensive", "0", {}, GroupPlan)
    response = controller.agent("group_planner", "other", "0", {}, GroupPlan)
    assert response.groups[0].columns == ["Name"]
    assert calls == ["other"]


def test_revision_retains_only_explicitly_reused_drafts_without_approving_them():
    from firmable.evolution.schema import Concept
    a = Concept(path="dyn.example.status", type="string", owner="business", definition="Status explicitly reported by the source",
                source_paths=["Status"], why_not_existing="No existing concept has this reported meaning")
    b = a.model_copy(update={"path": "dyn.example.other"})
    prior = ConceptPatch(concepts=[a, b])
    revised = resolve_patch(ConceptPatch(reuse={a.path: "Keep the prior draft unchanged", "entity.abn": "Identifier"}), prior, bootstrap()["concepts"])
    assert revised.concepts == [a] and revised.reuse == {"entity.abn": "Identifier"}
    assert a.path not in bootstrap()["concepts"]
    with pytest.raises(ValueError, match="Unknown reuse"):
        resolve_patch(ConceptPatch(reuse={"dyn.missing.value": "Not observed"}), prior, {})
    with pytest.raises(ValueError, match="both define and reuse"):
        resolve_patch(ConceptPatch(concepts=[a], reuse={a.path: "Conflicting instruction"}), prior, {})


def test_final_compiler_reconciles_only_cross_group_omissions():
    from firmable.evolution2.quality import mapping_findings
    inspection = Inspection(reader={"format": "delimited"}, grain="company", identity_cautions=[], rationale="CSV header")
    plan = GroupPlan(grain="company", groups=[{"name": "identity", "purpose": "Identity", "columns": ["Name", "ABN"]}])
    name = GroupIntent.model_validate({"fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": .9, "rationale": "Legal name"}], "unmapped": [{"source_path": "ABN", "reason": "Other group"}]})
    abn = GroupIntent.model_validate({"fields": [{"source_paths": ["ABN"], "target": "entity.abn", "confidence": .9, "rationale": "Identifier", "steps": [{"op": "abn"}]}]})
    cfg = compile_mapping({"source_id": "test"}, inspection, plan, [name, abn])
    assert not cfg.unmapped
    abn.unmapped = name.unmapped
    cfg = compile_mapping({"source_id": "test"}, inspection, plan, [name, abn])
    assert any(f["code"] == "MAPPED_AND_DECLINED" for f in mapping_findings(cfg, bootstrap(), ["Name", "ABN"]))


def test_group_validation_sees_only_populated_roles_but_final_keeps_plan():
    inspection = Inspection(reader={"format": "delimited"}, grain="company", identity_cautions=[], rationale="CSV header")
    plan = GroupPlan.model_validate({"grain": "company", "groups": [{"name": "identity", "purpose": "Name", "columns": ["Name"]}],
        "entities": {"site": {"kind": "establishment", "key_paths": ["Address"], "rationale": "Operating site"}},
        "relationships": [{"type": "OPERATES_ESTABLISHMENT", "from_role": "subject", "to_role": "site", "rationale": "Source-stated site"}]})
    intent = GroupIntent.model_validate({"fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": .9, "rationale": "Legal name"}]})
    group = compile_mapping({"source_id": "test"}, inspection, plan, [intent], scoped=True)
    final = compile_mapping({"source_id": "test"}, inspection, plan, [intent])
    assert not group.entities and not group.relationships
    assert "site" in final.entities and len(final.relationships) == 1
