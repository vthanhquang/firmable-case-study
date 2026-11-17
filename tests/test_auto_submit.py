"""The controller's auto-submit policy: it may submit the agent's own clean draft, never an empty or failing one."""
import pytest

from firmable import llm
from firmable.agent import onboard as O
from firmable.mapping.schema import MappingConfig


def cfg(n_fields=1):
    return MappingConfig.model_validate({
        "source_id": "src", "record_grain": "licence_or_permit", "grain_rationale": "one licence per row",
        "reader": {"format": "delimited", "delimiter": ","},
        "record_id": {"strategy": "columns", "source_paths": ["Licence"]},
        "fields": [{"source_paths": [f"C{i}"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "legal name"}
                   for i in range(n_fields)],
        "unmapped": []})


class FakeRun:
    sid, run_id = "src", "test-run"

    def __init__(self, **state):
        self.state, self.events, self.messages, self.saved = dict(state), [], [], 0

    def event(self, kind, **kw):
        self.events.append(kw.get("stage"))

    def save(self):
        self.saved += 1


class FakeWorkspace:
    def __init__(self, parsed, issues=(), ext_base=None, scope=True):
        self.parsed, self.issues, self.ext_base, self.scope = parsed, list(issues), ext_base, scope
        self.ext_last_changes, self.ext_last_discarded = [{"change": "added", "target": "x"}], []

    def parse_config(self, config_json):
        return self.parsed, self.issues

    def ext_scope(self, c):
        return self.scope


def test_no_pending_draft_submits_nothing():
    assert O.auto_submit(FakeRun(), FakeWorkspace(cfg()), 0, "r") is None


def test_draft_failing_the_static_gate_is_not_submitted():
    run = FakeRun(last_clean_draft={"config_json": "{}", "turn": 3})
    ws = FakeWorkspace(cfg(), issues=[{"severity": "error", "code": "X"}])
    assert O.auto_submit(run, ws, 0, "r") is None
    assert "auto_submitted" not in run.state


def test_empty_extension_draft_is_refused():
    run = FakeRun(last_clean_draft={"config_json": "{}", "turn": 3})
    ws = FakeWorkspace(cfg(), ext_base={"fields": []}, scope=False)
    assert O.auto_submit(run, ws, 1, "r") is None
    assert "AUTO_SUBMIT_REFUSED_EMPTY_DRAFT" in run.events and "auto_submitted" not in run.state


def test_clean_draft_is_submitted_unchanged_and_recorded():
    c = cfg(2)
    run = FakeRun(last_clean_draft={"config_json": "{}", "turn": 5})
    ws = FakeWorkspace(c, ext_base={"fields": []})
    assert O.auto_submit(run, ws, 1, "turn limit") is c
    assert run.state["auto_submitted"] == [{"round": 1, "reason": "turn limit", "draft_from_turn": 5}]
    assert run.state["ext_change_logs"][-1]["changes"] == ws.ext_last_changes
    assert "last_clean_draft" not in run.state and run.saved == 1


def test_draft_size_counts_rules_and_unparseable_is_zero():
    assert O._draft_size(FakeWorkspace(cfg(3)), "{}") == 3
    assert O._draft_size(FakeWorkspace(None), "not json") == 0


def test_agent_round_auto_submits_after_two_idle_turns_without_calling_the_model(monkeypatch):
    def no_call(*a, **k):
        raise AssertionError("the model must not be called")
    monkeypatch.setattr(llm, "chat", no_call)
    c = cfg()
    run = FakeRun(last_clean_draft={"config_json": "{}", "turn": 1}, turns_since_clean=O.AUTO_SUBMIT_AFTER_TURNS)
    assert O.agent_round(run, FakeWorkspace(c), 0) is c


def test_agent_round_keeps_the_draft_when_the_budget_runs_out(monkeypatch):
    def broke(*a, **k):
        raise llm.BudgetExceeded("budget")
    monkeypatch.setattr(llm, "chat", broke)
    c = cfg()
    run = FakeRun(last_clean_draft={"config_json": "{}", "turn": 1}, turns_since_clean=0)
    assert O.agent_round(run, FakeWorkspace(c), 0) is c
    assert run.state["auto_submitted"][0]["reason"].startswith("token budget")
    # Without a clean draft the budget error still propagates.
    with pytest.raises(llm.BudgetExceeded):
        O.agent_round(FakeRun(), FakeWorkspace(c), 0)
