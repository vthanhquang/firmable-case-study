"""The human gate: approvals are append-only, bound to the exact config digest, and extraction refuses anything else."""
import json

import pytest

import firmable.agent.review as rv


def write_proposal(maps, cfg, run_id="r1", status="PENDING_REVIEW", snapshot="a" * 64):
    doc = {"run_id": run_id, "status": status, "config": cfg, "snapshot_sha256": snapshot}
    (maps / "s.json").write_text(json.dumps(doc), encoding="utf-8")
    run = rv.RUNS / "s" / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "state.json").write_text(json.dumps(doc | {"proposals": [{"config": cfg}]}), encoding="utf-8")
    return doc


@pytest.fixture
def maps(tmp_path, monkeypatch):
    monkeypatch.setattr(rv, "OUT_MAPPINGS", tmp_path)
    monkeypatch.setattr(rv, "RUNS", tmp_path / "runs")
    cfg = {"source_id": "s", "record_grain": "legal_entity", "grain_rationale": "one per row",
           "reader": {"format": "delimited", "delimiter": ","},
           "record_id": {"strategy": "content_hash"},
           "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "name col"}]}
    write_proposal(tmp_path, cfg)
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


def test_stale_reviewer_decision_and_snapshot_are_rejected(maps):
    original = rv.load_proposal("s")
    expected = rv.proposal_ref(original)
    rv.approve("s", "Jane", "human", expected=expected)
    write_proposal(maps, original["config"], snapshot="b" * 64)
    assert rv.current_approval("s") is None
    with pytest.raises(ValueError, match="changed after the review"):
        rv.approve("s", "Jane", "human", expected=expected)


def test_failed_validation_can_be_rejected_but_cannot_be_approved(maps):
    write_proposal(maps, rv.load_proposal("s")["config"], status="NEEDS_ATTENTION")
    with pytest.raises(ValueError, match="passed validation"):
        rv.approve("s", "Jane", "human")
    assert rv.approve("s", "Jane", "human", reject=True)["decision"] == "rejected"


def test_feedback_revisions_start_from_last_approved_not_rejected_draft(maps):
    # Regression: revising after a rejection used to start from the rejected draft, carrying its changes forward.
    rv.approve("s", "Jane", "human")
    approved_cfg = json.loads((maps / "s.json").read_text())["config"]
    (maps / "superseded").mkdir()
    (maps / "s.json").rename(maps / "superseded" / "s.r1.json")
    bad = dict(approved_cfg, grain_rationale="rejected draft with unrequested changes")
    write_proposal(maps, bad, run_id="r2")
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


def test_human_audit_scores_exclude_proxy_labels(tmp_path, monkeypatch):
    from firmable import report

    monkeypatch.setattr(report, "OUT_EVAL", tmp_path)
    (tmp_path / "triage_audit_20.csv").write_text(
        "label,basis,reviewer,reviewer_kind\n"
        "NO,data,Reviewer,human\nYES,data,AI assistant,human\nUNCERTAIN,metadata,,\n", encoding="utf-8")
    links = tmp_path / "link_audit_50.csv"
    links.write_text("band,label,rule,reviewer,reviewer_kind\n"
                     "strict,INCORRECT,abn,Reviewer,human\nstrict,CORRECT,abn,AI assistant,\n", encoding="utf-8")

    triage = report.triage()
    assert triage["false_positive_rate_decided"] == 0.5
    assert triage["human_review"]["remaining"] == 2
    assert triage["human_review"]["scores"]["false_positive_rate_decided"] == 1.0
    strict = report.link_audits(links)["strict"]
    assert strict["precision_decided"] == 0.5
    assert strict["human_review"]["remaining"] == 1
    assert strict["human_review"]["scores"]["precision_decided"] == 0.0


def test_workbook_import_binds_decisions_and_preserves_proxy_baseline(maps, monkeypatch):
    from openpyxl import Workbook

    from firmable import report, review_workbook as rw

    monkeypatch.setattr(rw, "CHOICES", [("s",)])
    monkeypatch.setattr(rw, "OUT_EVAL", maps)
    monkeypatch.setattr(report, "OUT_EVAL", maps)
    triage = maps / "triage_audit_20.csv"
    links = maps / "link_audit_50.csv"
    triage.write_text("rank,dataset_id,label,basis,evidence,reviewer\n1,d,YES,data,proxy,AI assistant\n", encoding="utf-8")
    links.write_text("band,record_a,record_b,label,rule,note,reviewer\n"
                     "strict,a,b,CORRECT,abn,proxy,AI assistant\n", encoding="utf-8")
    original_csv = triage.read_bytes(), links.read_bytes()
    for audit, (_, _, evidence, _) in rw.AUDITS.items():
        (maps / evidence).write_text(json.dumps([audit]), encoding="utf-8")

    book = Workbook()
    mapping_sheet = book.active
    mapping_sheet.title = "Mappings"
    triage_sheet = book.create_sheet("Triage audit")
    link_sheet = book.create_sheet("Link audit")
    ref = rv.proposal_ref(rv.load_proposal("s"))
    for sheet, headers, values in [
        (mapping_sheet, ["Decision", "Reviewer", "Source ID", "Mapping digest", "Run ID", "Snapshot SHA-256"],
         ["APPROVE", "Jane", "s", ref["config_digest"], ref["run_id"], ref["snapshot_sha256"]]),
        (triage_sheet, ["Verdict", "Reviewer", "Rank", "Dataset ID", "Basis"], ["NO", "Jane", 1, "d", "data"]),
        (link_sheet, ["Verdict", "Reviewer", "Record A key", "Record B key"], ["INCORRECT", "Jane", "a", "b"]),
    ]:
        for col, (header, value) in enumerate(zip(headers, values), 1):
            sheet.cell(7, col, header)
            sheet.cell(8, col, value)
    triage_sheet["A6"] = f"Evidence SHA-256 {rw._evidence_hash('triage', maps)}"
    link_sheet["A6"] = "Evidence SHA-256 old"
    path = maps / "review.xlsx"
    book.save(path)
    with pytest.raises(ValueError, match="evidence changed"):
        rw.import_reviews(path)
    assert rv.current_review("s") is None

    link_sheet["A6"] = f"Evidence SHA-256 {rw._evidence_hash('strict_links', maps)}"
    book.save(path)
    pending = rw.import_reviews(path, dry_run=True)
    assert (pending["mapping_decisions"], pending["triage_decisions"], pending["strict_link_decisions"]) == (1, 1, 1)
    assert rv.current_review("s") is None
    assert not (maps / "human_audit_decisions.jsonl").exists()
    rw.import_reviews(path)
    assert rv.current_approval("s")["reviewer"] == "Jane"
    assert (triage.read_bytes(), links.read_bytes()) == original_csv
    assert report.triage()["human_review"]["scores"]["false_positive_rate_decided"] == 1.0
    assert report.link_audits(links)["strict"]["human_review"]["scores"]["precision_decided"] == 0.0
    repeated = rw.import_reviews(path)
    assert (repeated["mapping_decisions"], repeated["triage_decisions"], repeated["strict_link_decisions"]) == (0, 0, 0)

    mapping_sheet["A8"] = "NEEDS EVIDENCE"
    mapping_sheet["G7"] = "Decision note"
    mapping_sheet["G8"] = "Check which date applies to the company status"
    book.save(path)
    deferred = rw.import_reviews(path)
    assert (deferred["mapping_decisions"], deferred["mappings_needing_evidence"]) == (1, 1)
    assert rv.current_approval("s") is None
    assert rv.current_review("s")["decision"] == "needs_evidence"
    assert rv.current_review("s")["comment"] == mapping_sheet["G8"].value
    assert rw.import_reviews(path)["mapping_decisions"] == 0
