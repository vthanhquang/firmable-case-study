import json

import pytest

from firmable.rawdata.audit import evidence_digest, load_reviews
from firmable.rawdata import match
from firmable.rawdata.audit import mapping_evidence_digest, load_mapping_assessments


def example_link():
    return dict(link_id="l1", source_a_record="a::1", source_b_record="b::1", canonical_entity_key="e1",
                policy_version="test", confidence=.9, rule="abn_equal", evidence=[], a={}, b={})


def decision(link, kind="ai_assistant", **extra):
    return dict(link_id=link["link_id"], evidence_sha256=evidence_digest(link), reviewer_kind=kind,
                verdict="pass", reviewer="Test reviewer", note="Compared source records.", **extra)


def test_review_survives_audit_regeneration_and_keeps_reviewer_kind(tmp_path, monkeypatch):
    link = example_link()
    path = tmp_path / "link_review_decisions.jsonl"
    path.write_text(json.dumps(decision(link)) + "\n" + json.dumps(decision(link, "human")) + "\n")
    before = path.read_bytes()
    monkeypatch.setattr(match, "OUT_RD_EVAL", tmp_path)
    record = dict(names={"Example Pty Ltd"}, abn=set(), acn=set())
    match.audit_sample({"decisions": [dict(decision="LINK", a="a::1", b="b::1", rule="abn_equal",
                                           score=.9, evidence=[])]}, {"a::1": record, "b::1": record}, n=1)
    assert path.read_bytes() == before
    assert set(load_reviews(path, {"l1": link})["l1"]) == {"human", "ai_assistant"}


def test_changed_evidence_does_not_inherit_a_previous_pass(tmp_path):
    link = example_link()
    path = tmp_path / "reviews.jsonl"
    path.write_text(json.dumps(decision(link)) + "\n")
    assert load_reviews(path, {"l1": link})
    assert not load_reviews(path, {"l1": link | {"evidence": [{"type": "CONTRADICTING_ABN"}]}})


def test_invalid_verdict_is_not_counted_as_a_review(tmp_path):
    link = example_link()
    path = tmp_path / "reviews.jsonl"
    path.write_text(json.dumps(decision(link) | {"verdict": "anything"}) + "\n")
    with pytest.raises(ValueError):
        load_reviews(path, {"l1": link})


@pytest.mark.parametrize("changed", ["config", "observations", "crosswalk"])
def test_mapping_assessment_expires_when_its_evidence_changes(tmp_path, changed):
    observations = tmp_path / "observations.jsonl"
    crosswalk = tmp_path / "crosswalk.yaml"
    observations.write_text(json.dumps({"value": "original", "ingested_at": "first"}))
    crosswalk.write_text("original labels")
    doc = dict(source_id="source", run_id="run", config_digest="config1", snapshot_sha256="snapshot1")
    digest = mapping_evidence_digest(doc, observations, [crosswalk])
    path = tmp_path / "assessments.jsonl"
    path.write_text(json.dumps(dict(source_id="source", evidence_sha256=digest, reviewer_kind="ai_assistant",
        reviewer="Test reviewer", verdict="ready", summary="Evidence checked.")) + "\n")
    assert load_mapping_assessments(path, {"source": digest})["source"]["verdict"] == "ready"
    if changed == "config":
        doc["config_digest"] = "config2"
    else:
        (observations if changed == "observations" else crosswalk).write_text(json.dumps({"value": "changed"}))
    assert not load_mapping_assessments(path, {"source": mapping_evidence_digest(doc, observations, [crosswalk])})


def test_mapping_assessment_survives_only_ingestion_timestamp_change(tmp_path):
    observations = tmp_path / "observations.jsonl"
    observations.write_text(json.dumps({"value": "same", "ingested_at": "first", "approval_state": "pending_human_review"}))
    doc = dict(source_id="source", run_id="run", config_digest="config1", snapshot_sha256="snapshot1")
    digest = mapping_evidence_digest(doc, observations, [])
    observations.write_text(json.dumps({"value": "same", "ingested_at": "second", "approval_state": "approved"}))
    assert mapping_evidence_digest(doc, observations, []) == digest
