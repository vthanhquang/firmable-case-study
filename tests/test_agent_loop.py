"""Agent controller tests with a scripted fake model (no network): the tool loop, the held-out gate
driving a revision, and resume-after-crash."""
import json
import types

import pytest

from firmable.agent import onboard as ob

GOOD_ABN = "51824753556"


def test_usage_budget_counts_the_current_run(tmp_path, monkeypatch):
    ledger = tmp_path / "usage.jsonl"
    ledger.write_text(json.dumps({"source_id": "s", "run_id": "old", "prompt_tokens": 300,
                                  "completion_tokens": 50}) + "\n", encoding="utf-8")
    monkeypatch.setattr(ob.llm, "LEDGER", ledger)
    monkeypatch.setattr(ob.llm, "TOKEN_BUDGET", 350)
    monkeypatch.setattr(ob.llm, "TOTAL_TOKEN_BUDGET", None)
    assert ob.llm.tokens_used() == 350
    assert ob.llm.tokens_used("fresh", "s") == 0
    with pytest.raises(ob.llm.BudgetExceeded, match="run token budget"):
        ob.llm.chat([], stage="test", source_id="s", run_id="old")


def _msg(content="", calls=()):
    tcs = [types.SimpleNamespace(id=f"c{i}", function=types.SimpleNamespace(name=n, arguments=json.dumps(a)))
           for i, (n, a) in enumerate(calls)]
    return types.SimpleNamespace(content=content, tool_calls=tcs or None)


def _config(abn_steps):
    return json.dumps({
        "record_grain": "legal_entity", "grain_rationale": "one company per row",
        "reader": {"format": "delimited", "delimiter": ","},
        "record_id": {"strategy": "content_hash", "rationale": "no key"},
        "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "registered name"},
                   {"source_paths": ["Id"], "target": "entity.abn", "steps": abn_steps, "confidence": 0.9, "rationale": "abn col"}],
        "unmapped": []})


@pytest.fixture
def env(tmp_path, monkeypatch):
    rows = ["Name,Id"] + [f"Co {i} Pty Ltd,{GOOD_ABN if i % 2 else 'X' + str(i)}" for i in range(200)]
    f = tmp_path / "src.csv"
    f.write_text("\n".join(rows))
    source = {"source_id": "t_src", "title": "T", "publisher": "P", "licence": "cc-by", "advertised_format": "CSV",
              "resource_name": "r", "snapshot": {"path": str(f), "sha256": "x"}}
    monkeypatch.setattr(ob, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(ob, "OUT_MAPPINGS", tmp_path / "maps")
    import firmable.agent.review as rv
    monkeypatch.setattr(rv, "write_report", lambda sid, rid, **kw: None)
    return source


def _script(monkeypatch, replies, critic_replies=()):
    it = iter(replies)
    reviews = iter(critic_replies)
    def fake_chat(messages, **kw):
        if kw.get("json_mode"):  # critic
            reply = next(reviews, None)
            if reply is not None:
                return _msg(reply)
            rules = json.loads(messages[1]["content"])["mapping"]
            fields = [{"rule_index": r["rule_index"], "verdict": "ok", "reason": "checked"} for r in rules]
            return _msg(json.dumps({"fields": fields, "missed": [], "summary": "ok"}))
        return next(it)
    monkeypatch.setattr(ob.llm, "chat", fake_chat)


def test_holdout_errors_drive_a_revision(env, monkeypatch):
    # v0 maps a half-garbage column as ABN with a checksum -> held-out HIGH_ERROR_RATE -> agent revises (unmaps).
    v1 = json.loads(_config([{"op": "abn"}]))
    v1["fields"] = v1["fields"][:1]
    v1["unmapped"] = [{"source_path": "Id", "reason": "half the values are not ABNs"}]
    _script(monkeypatch, [
        _msg(calls=[("try_reader", {"reader": {"format": "delimited", "delimiter": ","}})]),
        _msg(calls=[("submit_mapping", {"config_json": _config([{"op": "abn"}])})]),
        _msg(calls=[("submit_mapping", {"config_json": json.dumps(v1)})]),
    ])
    st = ob.onboard(env)
    assert st["status"] == "PENDING_REVIEW"
    assert len(st["proposals"]) == 2
    assert any(i["code"] == "HIGH_ERROR_RATE" for i in st["proposals"][0]["holdout_issues"])


@pytest.mark.parametrize("exhaust_retry", [False, True])
def test_incomplete_critic_review_cannot_pass(env, monkeypatch, exhaust_retry):
    proposal = json.loads(_config([{"op": "abn"}]))
    proposal["fields"] = proposal["fields"][:1]
    incomplete = json.dumps({"fields": [], "missed": [], "summary": "ok"})
    _script(monkeypatch, [_msg(calls=[("submit_mapping", {"config_json": json.dumps(proposal)})])],
            critic_replies=[incomplete, "invalid JSON"] if exhaust_retry else [incomplete])

    state = ob.onboard(env)
    assert len(state["proposals"]) == 1
    critic = state["proposals"][0]["critic"]
    events = (ob.RUNS / env["source_id"] / state["run_id"] / "events.jsonl").read_text(encoding="utf-8")
    assert events.count('"kind": "critic_response_invalid"') == (2 if exhaust_retry else 1)
    if exhaust_retry:
        assert state["status"] == "NEEDS_ATTENTION"
        assert critic["error"] == "INVALID_CRITIC_RESPONSE"
    else:
        assert state["status"] == "PENDING_REVIEW"
        assert critic["fields"][0]["target"] == "entity.legal_name"


def test_discovery_and_holdout_never_overlap_and_are_deterministic(tmp_path):
    from firmable.agent.workspace import Workspace
    from firmable.mapping.schema import ReaderSpec
    f = tmp_path / "d.csv"
    rows = ["Name,Country"] + [f"Co {i},Australia" for i in range(3000)] + ["Odd Co,Singapore"]
    f.write_text("\n".join(rows))
    spec = ReaderSpec(format="delimited", delimiter=",")
    key = lambda r: (r["Name"], r["Country"])
    a, b = Workspace({"source_id": "d", "snapshot": {"path": str(f)}}), Workspace({"source_id": "d", "snapshot": {"path": str(f)}})
    da, ha, _, _ = a.pool(spec)
    db, hb, _, _ = b.pool(spec)
    assert [key(r) for r in da] == [key(r) for r in db] and [key(r) for r in ha] == [key(r) for r in hb]  # seeded
    assert not {key(r) for r in da} & {key(r) for r in ha}                                                 # disjoint
    rare = ha[:a.rare_holdout(spec)]
    assert all(key(r) not in {key(x) for x in da} for r in rare)
    # The single non-Australian row reaches validation (or the agent saw it directly) - never neither.
    assert any(r["Country"] == "Singapore" for r in da) or any(r["Country"] == "Singapore" for r in rare)


def test_rare_row_outside_the_sample_always_reaches_holdout(tmp_path):
    from firmable.agent import workspace as W
    from firmable.mapping.schema import ReaderSpec
    f = tmp_path / "r.csv"
    f.write_text("\n".join(["Name,Kind"] + [f"Co {i},A" for i in range(5000)] + ["Rare Co,Z"]))
    spec = ReaderSpec(format="delimited", delimiter=",")
    old = W.SAMPLE
    W.SAMPLE = 50   # tiny sample: the rare row is almost surely not drawn
    try:
        ws = W.Workspace({"source_id": "r", "snapshot": {"path": str(f)}})
        disc, hold, _, _ = ws.pool(spec)
    finally:
        W.SAMPLE = old
    assert any(r["Kind"] == "Z" for r in disc) or any(r["Kind"] == "Z" for r in hold[:ws.rare_holdout(spec)])


def test_wrong_json_reader_on_big_document_stays_fast(tmp_path):
    # Regression: record_path omitted -> whole document flattens into ONE record with ~100k columns;
    # rare-value stratification must not go quadratic on it.
    import time
    from firmable.agent.workspace import Workspace
    f = tmp_path / "api.json"
    f.write_text(json.dumps({"result": {"records": [{"a": i, "b": f"n{i}", "c": "x"} for i in range(30000)]}}))
    ws = Workspace({"source_id": "w", "snapshot": {"path": str(f)}})
    t0 = time.perf_counter()
    out = ws.tool_try_reader({"format": "json"})
    assert time.perf_counter() - t0 < 10
    assert out["ok"] and out["n_columns"] > 1000  # the agent sees the symptom and can fix record_path


def test_resume_after_crash_reevaluates_saved_proposal(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("simulated crash in validation")
    clean = json.loads(_config([{"op": "abn"}]))
    clean["fields"] = clean["fields"][:1]
    _script(monkeypatch, [_msg(calls=[("try_reader", {"reader": {"format": "delimited", "delimiter": ","}})]),
                          _msg(calls=[("submit_mapping", {"config_json": json.dumps(clean)})])])
    monkeypatch.setattr(ob, "holdout_issues", boom)
    with pytest.raises(RuntimeError):
        ob.onboard(env)
    run_dir = next((ob.RUNS / "t_src").iterdir())
    assert json.loads((run_dir / "state.json").read_text())["status"] == "PROPOSED_v0"
    from firmable.mapping.validate import holdout_issues
    monkeypatch.setattr(ob, "holdout_issues", holdout_issues)
    _script(monkeypatch, [])  # resume must not need new agent turns to evaluate the saved proposal
    st = ob.resume(env, run_dir.name)
    assert st["status"] == "PENDING_REVIEW"
    assert "holdout_report" in st["proposals"][0] and len(st["proposals"]) == 1  # evaluated, not re-proposed


@pytest.mark.parametrize("legacy_checkpoint", [False, True])
def test_resume_after_first_model_call_fails(env, monkeypatch, legacy_checkpoint):
    def fail(messages, **kwargs):
        raise RuntimeError("provider request failed")

    monkeypatch.setattr(ob.llm, "chat", fail)
    with pytest.raises(RuntimeError, match="provider request failed"):
        ob.onboard(env)
    run_dir = next((ob.RUNS / "t_src").iterdir())
    history = run_dir / "messages.json"
    assert [m["role"] for m in json.loads(history.read_text(encoding="utf-8"))] == ["system", "user"]
    if legacy_checkpoint:
        history.write_text("[]", encoding="utf-8")

    def stop_after_verifying_prompt(messages, **kwargs):
        assert [m["role"] for m in messages] == ["system", "user"]
        assert '"source_id": "t_src"' in messages[1]["content"]
        raise RuntimeError("verified prompt")

    monkeypatch.setattr(ob.llm, "chat", stop_after_verifying_prompt)
    with pytest.raises(RuntimeError, match="verified prompt"):
        ob.resume(env, run_dir.name)


def test_register_unseen_source_then_onboard_and_extract(tmp_path, monkeypatch):
    import hashlib

    from firmable import cli, extract
    from firmable.agent import review, workspace
    from firmable.sources import register, select

    monkeypatch.setattr(cli, "ensure_dirs", lambda: None)
    monkeypatch.setattr(register, "ROOT", tmp_path)
    monkeypatch.setattr(register, "REGISTRY", tmp_path / "data" / "registered")
    monkeypatch.setattr(select, "OUT_SOURCES", tmp_path / "sources")
    monkeypatch.setattr(workspace, "ROOT", tmp_path)
    monkeypatch.setattr(ob, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(ob, "OUT_MAPPINGS", tmp_path / "maps")
    monkeypatch.setattr(review, "RUNS", ob.RUNS)
    monkeypatch.setattr(review, "OUT_MAPPINGS", ob.OUT_MAPPINGS)
    monkeypatch.setattr(review, "OUT_REVIEWS", tmp_path / "reviews")
    monkeypatch.setattr(extract, "ROOT", tmp_path)
    monkeypatch.setattr(extract, "OUT_MAPPINGS", ob.OUT_MAPPINGS)
    monkeypatch.setattr(extract, "OUT_OBS", tmp_path / "obs")
    monkeypatch.setattr(extract, "reliability", lambda: {})

    file = tmp_path / "register.csv"
    file.write_text("\n".join(["Name,Id"] + [f"Co {i} Pty Ltd,{GOOD_ABN}" for i in range(200)]), encoding="utf-8")
    original_digest = hashlib.sha256(file.read_bytes()).hexdigest()
    args = ["register-source", "new_register", str(file), "--title", "New register", "--publisher", "Test publisher"]
    cli.main(args)
    source = select.load_manifest()["new_register"]
    assert source["licence"] == "unknown"
    assert source["snapshot"]["sha256"] == original_digest
    file.write_text("Publisher updated the resource", encoding="utf-8")
    with pytest.raises(SystemExit, match="source ID already registered"):
        cli.main(args)

    _script(monkeypatch, [
        _msg(calls=[("try_reader", {"reader": {"format": "delimited", "delimiter": ","}})]),
        _msg(calls=[("submit_mapping", {"config_json": _config([{"op": "abn"}])})]),
    ])
    cli.main(["onboard", "new_register"])
    report = (review.OUT_REVIEWS / "new_register.md").read_text(encoding="utf-8")
    assert "PENDING_REVIEW" in report and "New register" in report
    with pytest.raises(SystemExit, match="no eligible approval"):
        cli.main(["extract", "new_register"])
    observations = extract.OUT_OBS / "new_register.jsonl"
    assert not observations.exists()
    review.approve("new_register", "Test proxy", "ai_assistant_proxy")
    with pytest.raises(SystemExit, match="no eligible approval"):
        cli.main(["extract", "new_register"])
    cli.main(["extract", "new_register", "--allow-proxy-approvals", "--sample-size", "3"])
    assert observations.is_file()
    # An actual rejection becomes revision context even for the first source proposal.
    review.approve("new_register", "Test reviewer", "human", reject=True, comment="Trim the registered name")
    config = json.loads(_config([{"op": "abn"}]))
    config["fields"][0]["steps"] = [{"op": "trim"}]
    _script(monkeypatch, [_msg(calls=[("submit_mapping", {"config_json": json.dumps(config)})])])
    cli.main(["onboard", "new_register", "--only", "entity.legal_name"])
    revised = review.load_proposal("new_register")
    state = json.loads((ob.RUNS / "new_register" / revised["run_id"] / "state.json").read_text(encoding="utf-8"))
    assert state["human_feedback"] == "Trim the registered name"
    assert state["feedback_base_config"]["fields"][0]["steps"] == []
    with pytest.raises(SystemExit, match="no eligible approval"):
        cli.main(["extract", "new_register"])
    answers = iter(["approve", "Test reviewer", "Checked the revised mapping"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    cli.main(["review", "new_register", "--interactive"])
    assert review.current_approval("new_register")["snapshot_sha256"] == original_digest
    cli.main(["extract", "new_register", "--sample-size", "10"])
    records = [json.loads(line) for line in observations.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 20
    assert {record["source_id"] for record in records} == {"new_register"}
    assert {record["field"] for record in records} == {"entity.legal_name", "entity.abn"}
