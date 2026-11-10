"""The human gate: approvals are append-only, bound to the exact config digest, and extraction refuses anything else."""
import json

import pytest

import firmable.agent.review as rv


@pytest.fixture
def maps(tmp_path, monkeypatch):
    monkeypatch.setattr(rv, "OUT_MAPPINGS", tmp_path)
    cfg = {"source_id": "s", "record_grain": "legal_entity", "grain_rationale": "one per row",
           "reader": {"format": "delimited", "delimiter": ","},
           "record_id": {"strategy": "content_hash"},
           "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "name col"}]}
    (tmp_path / "s.json").write_text(json.dumps({"run_id": "r1", "status": "PENDING_REVIEW", "config": cfg}))
    return tmp_path


def test_no_approval_means_no_extraction(maps):
    assert rv.current_approval("s") is None


def test_approval_is_bound_to_the_digest(maps):
    rv.approve("s", "Jane", "human")
    assert rv.current_approval("s")["reviewer"] == "Jane"
    doc = json.loads((maps / "s.json").read_text())
    doc["config"]["fields"][0]["confidence"] = 0.99          # any edit after approval...
    (maps / "s.json").write_text(json.dumps(doc))
    assert rv.current_approval("s") is None                 # ...voids it


def test_feedback_revisions_start_from_last_approved_not_rejected_draft(maps):
    # Regression: revising after a rejection used to start from the rejected draft, carrying its changes forward.
    rv.approve("s", "Jane", "human")
    approved_cfg = json.loads((maps / "s.json").read_text())["config"]
    (maps / "superseded").mkdir()
    (maps / "s.json").rename(maps / "superseded" / "s.r1.json")
    bad = dict(approved_cfg, grain_rationale="rejected draft with unrequested changes")
    (maps / "s.json").write_text(json.dumps({"run_id": "r2", "status": "PENDING_REVIEW", "config": bad}))
    rv.approve("s", "Jane", "human", reject=True, comment="scope creep")
    assert rv.last_approved_config("s") == approved_cfg
    assert rv.restore_last_approved("s") == "r1" and rv.current_approval("s") is None   # restored, needs re-approval
    rv.approve("s", "Jane", "human")
    assert rv.current_approval("s")


def test_scoped_revision_keeps_everything_else_from_approved():
    from firmable.agent.onboard import scope_to_targets
    from firmable.mapping.schema import MappingConfig
    base = MappingConfig.model_validate({
        "source_id": "s", "record_grain": "legal_entity", "grain_rationale": "one per row",
        "reader": {"format": "delimited", "delimiter": ","}, "record_id": {"strategy": "content_hash"},
        "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "name col"},
                   {"source_paths": ["Country"], "target": "address.country", "confidence": 0.7, "rationale": "old rule"}]}).model_dump()
    proposal = MappingConfig.model_validate(dict(base, reader={"format": "delimited", "delimiter": ";"}, fields=[
        {"source_paths": ["Name"], "target": "entity.trading_name", "confidence": 0.9, "rationale": "scope creep"},
        {"source_paths": ["Name"], "target": "entity.entity_type", "confidence": 0.5, "rationale": "a guess",
         "steps": [{"op": "map_enum", "args": {"mapping": {}, "default": "unknown"}}]},
        {"source_paths": ["Country"], "target": "address.country", "confidence": 0.8, "rationale": "the fix",
         "steps": [{"op": "upper"}]}]))
    merged, discarded = scope_to_targets(base, proposal, ["address.country"])
    m = merged.model_dump()
    assert m["reader"] == base["reader"]
    assert {f["target"] for f in m["fields"]} == {"entity.legal_name", "address.country"}
    assert next(f for f in m["fields"] if f["target"] == "address.country")["rationale"] == "the fix"
    assert any("entity.entity_type" in d for d in discarded) and any("reader" in d for d in discarded)


def test_rejection_after_approval_wins_and_history_is_kept(maps):
    rv.approve("s", "Jane", "human")
    rv.approve("s", "Sam", "human", reject=True, comment="wrong legal name column")
    assert rv.current_approval("s") is None
    lines = (maps / "s.approvals.jsonl").read_text().splitlines()
    assert [json.loads(l)["decision"] for l in lines] == ["approved", "rejected"]
