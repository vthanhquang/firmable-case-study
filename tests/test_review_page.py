"""The review page is the human gate's only interface: it must show what the WRITEUP promises."""
import json

import pytest

import firmable.agent.review as rv
import firmable.paths as P

CFG = {"source_id": "s", "record_grain": "legal_entity", "grain_rationale": "one company per row",
       "reader": {"format": "delimited", "delimiter": ","}, "record_id": {"strategy": "content_hash"},
       "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "registered name"}],
       "unmapped": [{"source_path": "Phone", "reason": "no ontology target"}]}


@pytest.fixture
def page(tmp_path, monkeypatch):
    runs, maps, reviews, out = tmp_path / "runs", tmp_path / "maps", tmp_path / "reviews", tmp_path / "out"
    for d in (runs / "s" / "r1", maps, reviews, out / "experiments" / "alt"):
        d.mkdir(parents=True)
    monkeypatch.setattr(rv, "RUNS", runs)
    monkeypatch.setattr(rv, "OUT_MAPPINGS", maps)
    monkeypatch.setattr(rv, "OUT_REVIEWS", reviews)
    monkeypatch.setattr(P, "OUT", out)
    monkeypatch.setattr("firmable.sources.select.load_manifest", lambda: {"s": {
        "title": "T", "publisher": "P", "resource_name": "r", "advertised_format": "CSV", "licence": "cc-by"}})
    monkeypatch.setattr(rv.llm, "summarize", lambda: {})
    from firmable.mapping.schema import MappingConfig
    full = lambda c: MappingConfig.model_validate(c).model_dump()   # stored exactly as onboard stores it
    cfg = full(CFG)
    v0 = full(dict(CFG, fields=CFG["fields"] + [{"source_paths": ["Phone"], "target": "entity.trading_name",
                                                  "confidence": 0.5, "rationale": "wrong guess"}]))
    report = {"records_in": 10, "records_with_output": 10, "record_errors": {},
              "fields": [{"emitted": 10, "source_present": 10, "errors": {}}]}
    st = {"status": "PENDING_REVIEW", "prompt_version": "p", "model": "m", "snapshot_sha256": "a" * 64, "tool_calls": 5,
          "proposals": [
              {"round": 0, "digest": "d0", "config": v0, "holdout_report": report, "holdout_issues": [],
               "critic": {"summary": "x", "fields": [{"target": "entity.trading_name", "verdict": "wrong", "reason": "phone"}]}},
              {"round": 1, "digest": "d1", "config": cfg, "holdout_report": report, "holdout_issues": [],
               "critic": {"summary": "ok", "fields": []}}]}
    (runs / "s" / "r1" / "state.json").write_text(json.dumps(st))
    (maps / "s.json").write_text(json.dumps({"run_id": "r1", "status": "PENDING_REVIEW", "config": cfg,
                                             "snapshot_sha256": st["snapshot_sha256"]}))
    alt = full(dict(CFG, fields=[dict(CFG["fields"][0], target="entity.trading_name")]))
    (out / "experiments" / "alt" / "s.json").write_text(json.dumps({"config": alt}))
    rv.approve("s", "Jane", "human")
    return (reviews / "s.md").read_text(encoding="utf-8") if rv.write_report("s", "r1") else ""


def test_page_shows_mapping_unmapped_and_trace(page):
    assert "`entity.legal_name`" in page and "registered name" in page
    assert "`Phone` — no ontology target" in page
    assert "Self-correction trace" in page and "critic 'wrong' ['entity.trading_name']" in page


def test_page_shows_decision_and_second_opinion(page):
    assert "Latest review decision:** approved by Jane" in page and "not yet decided" not in page
    assert "Second opinion" in page and "check these first" in page


def test_experimental_report_does_not_offer_main_mapping_approval(page, tmp_path):
    state_path = rv.RUNS / "s" / "r1" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["experiment"] = "trial"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    rv.write_report("s", "r1", out_dir=tmp_path / "trial")
    report = (tmp_path / "trial" / "s.md").read_text(encoding="utf-8")
    assert "outside the approval queue" in report
    assert "firmable.cli approve" not in report
