import json

import pytest

from firmable.discovery import agentic
from firmable.discovery.agentic import checked_decision


def test_triage_needs_inspected_resource_evidence_for_admission():
    keep = '{"decision":"KEEP","evidence_id":"r1","reason":"Supplier names are present."}'
    for evidence in ({}, {"r1": {"kind": "related_fields"}}, {"r1": {"kind": "records", "sampled_rows": 0}}):
        assert checked_decision(keep, evidence)["decision"] == "REVIEW"
    assert checked_decision(f"```json\n{keep}\n```", {"r1": {"kind": "publisher_fields"}})["decision"] == "KEEP"


def test_triage_cannot_exclude_a_whole_dataset_from_a_resource_index():
    exclude = '{"decision":"EXCLUDE","evidence_id":"r1","reason":"Only download links."}'
    assert checked_decision(exclude, {"r1": {"kind": "resource_index"}})["decision"] == "REVIEW"
    assert checked_decision(exclude, {"r1": {"kind": "publisher_scope"}})["decision"] == "EXCLUDE"


def test_resume_skips_saved_decisions_and_checks_input(tmp_path, monkeypatch):
    cases = [{"rank": 1, "dataset_id": "one", "title": "One"},
             {"rank": 2, "dataset_id": "two", "title": "Two"}]
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(cases), encoding="utf-8")
    output = tmp_path / "run"
    output.mkdir()
    decisions = output / "decisions.jsonl"
    decisions.write_text(json.dumps(cases[0] | {"decision": "KEEP"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(agentic, "triage", lambda case, run_id: case | {"decision": "EXCLUDE"})
    monkeypatch.setattr(agentic.llm, "summarize", lambda: {})

    stats = agentic.run(evidence, output, workers=1, resume=True)
    saved = [json.loads(line) for line in decisions.read_text(encoding="utf-8").splitlines()]
    assert stats["datasets"] == 2
    assert [row["decision"] for row in saved] == ["KEEP", "EXCLUDE"]
    evidence.write_text(json.dumps(cases[:1]), encoding="utf-8")
    with pytest.raises(ValueError, match="differs from the saved run"):
        agentic.run(evidence, output, workers=1, resume=True)
