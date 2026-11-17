"""Controller for onboarding one source: the agent proposes, the controller tests, the agent revises,
a human approves. The controller (not the model) owns state, stop conditions, the held-out split and
approval. State is checkpointed after every stage so a crash resumes from the last completed stage.

Stages: INSPECTED -> PROPOSED_v{n} -> VALIDATED_v{n} -> CRITIQUED_v{n} -> (REVISING -> PROPOSED_v{n+1})*
        -> PENDING_REVIEW | NEEDS_ATTENTION      (approval is a separate human command)
"""
from __future__ import annotations

import datetime as dt
import json
import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .. import llm, ontology
from ..mapping.schema import MappingConfig
from ..mapping.validate import holdout_issues, run_engine
from ..paths import OUT_MAPPINGS, RUNS
from .prompts import (AGENT_SYSTEM, CRITIC_PROMPT_VERSION, CRITIC_SYSTEM, EXT_CRITIC_ADDENDUM, EXT_PROMPT_VERSION,
                      EXTENSION_SYSTEM, PROFILE_CONTEXT_SYSTEM, PROMPT_VERSION)
from .workspace import Workspace, _short

MAX_TOOL_TURNS = 18      # per proposal round
MAX_EXT_TOOL_TURNS = 24  # extension runs profile more columns (ACNC has 57 unmapped)
MAX_REVISIONS = 2

TOOLS = [
    {"type": "function", "function": {"name": "inspect_resource", "description": "Raw-byte inspection of the resource (already shown; call again only if needed).",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "try_reader", "description": "Parse the resource with reader settings. Returns columns and 3 sample records, or a typed parse error. The last successful reader is used by profile_columns.",
                                      "parameters": {"type": "object", "properties": {"reader": {"type": "object", "description": "ReaderSpec: format, archive_member, encoding, delimiter, skip_rows, sheet, record_path"}}, "required": ["reader"]}}},
    {"type": "function", "function": {"name": "profile_columns", "description": "Statistics for up to 25 columns over the discovery partition: present rate, distinct count, top values, examples, value shapes, ABN/ACN checksum-valid rates.",
                                      "parameters": {"type": "object", "properties": {"columns": {"type": "array", "items": {"type": "string"}}}, "required": ["columns"]}}},
    {"type": "function", "function": {"name": "get_ontology", "description": "The canonical target paths, types, enum values and notes. This is the contract.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_transforms", "description": "Allowed transform ops and their args.",
                                      "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "dry_run", "description": "Validate a MappingConfig (JSON string) and run it over the discovery partition. Returns static issues, per-field coverage/errors and example observations.",
                                      "parameters": {"type": "object", "properties": {"config_json": {"type": "string"}}, "required": ["config_json"]}}},
    {"type": "function", "function": {"name": "submit_mapping", "description": "Submit the final MappingConfig (JSON string) for held-out validation and review. Rejected if it has static errors.",
                                      "parameters": {"type": "object", "properties": {"config_json": {"type": "string"}}, "required": ["config_json"]}}},
]
EXT_TOOLS = TOOLS + [
    {"type": "function", "function": {"name": "list_crosswalks", "description": "Human-reviewed lookup tables (raw code -> ANZSIC code, legal form, status label, revenue band) that rules can reference with the crosswalk transform.",
                                      "parameters": {"type": "object", "properties": {}}}},
]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Run:
    def __init__(self, source: dict, run_id: str | None = None):
        self.source = source
        self.sid = source["source_id"]
        self.run_id = run_id or f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.dir = RUNS / self.sid / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        context_base = source.get("profile_context_base")
        ext_base = source.get("extension_base")
        self.state = {"run_id": self.run_id, "source_id": self.sid, "status": "STARTED", "started_at": _now(),
                      "prompt_version": (EXT_PROMPT_VERSION if ext_base else
                                         f"{PROMPT_VERSION}-profile-context-v1" if context_base else PROMPT_VERSION),
                      "model": llm.DEFAULT_MODEL, "critic_model": llm.CRITIC_MODEL,
                      "ontology_sha256": ontology.load("v1" if context_base else None,
                                                       "ext-v1" if ext_base else None).sha256,
                      "snapshot_sha256": source["snapshot"]["sha256"],
                      "proposals": [], "tool_calls": 0, "stages": []}
        if context_base:
            self.state["profile_context_base"] = context_base
        if ext_base:
            self.state["extension_base"] = ext_base
            self.state["extension_base_digest"] = MappingConfig.model_validate(ext_base).digest()
            self.state["output_dir"] = source.get("extension_output_dir")
        if source.get("publisher_evidence"):
            self.state["publisher_evidence"] = source["publisher_evidence"]
        self.messages: list[dict] = []

    # ---- persistence ----------------------------------------------------------------------------
    def event(self, kind: str, **data):
        with open(self.dir / "events.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": _now(), "kind": kind, **data}, default=str) + "\n")

    def save(self):
        (self.dir / "state.json").write_text(json.dumps(self.state, indent=2, default=str), encoding="utf-8")
        (self.dir / "messages.json").write_text(json.dumps(self.messages, indent=1, default=str), encoding="utf-8")

    def checkpoint(self, stage: str):
        self.state["status"] = stage
        self.state["stages"].append({"stage": stage, "at": _now()})
        self.save()

    @classmethod
    def load(cls, source: dict, run_id: str) -> "Run":
        run = cls(source, run_id)
        run.state = json.loads((run.dir / "state.json").read_text(encoding="utf-8"))
        run.messages = json.loads((run.dir / "messages.json").read_text(encoding="utf-8"))
        # Drop a trailing assistant turn whose tool calls never got results (crash mid-turn).
        while run.messages and run.messages[-1]["role"] == "assistant" and run.messages[-1].get("tool_calls"):
            run.messages.pop()
        return run


def _assistant_dict(m) -> dict:
    d = {"role": "assistant", "content": m.content or ""}
    if m.tool_calls:
        d["tool_calls"] = [{"id": t.id, "type": "function",
                            "function": {"name": t.function.name, "arguments": t.function.arguments}}
                           for t in m.tool_calls]
    rc = getattr(m, "reasoning_content", None)
    if rc:
        d["reasoning_content"] = rc
    return d


def _dispatch(ws: Workspace, name: str, args: dict):
    if name == "inspect_resource":
        return ws.tool_inspect_resource()
    if name == "try_reader":
        return ws.tool_try_reader(args.get("reader") or {})
    if name == "profile_columns":
        return ws.tool_profile_columns(args.get("columns") or [])
    if name == "get_ontology":
        return ws.tool_get_ontology()
    if name == "list_transforms":
        return ws.tool_list_transforms()
    if name == "dry_run":
        return ws.tool_dry_run(args.get("config_json") or "")
    if name == "list_crosswalks" and ws.ext_base:
        return ws.tool_list_crosswalks()
    raise ValueError(f"unknown tool {name}")


AUTO_SUBMIT_AFTER_TURNS = 2   # turns without a submission after a clean dry run


def _draft_size(ws: Workspace, config_json) -> int:
    cfg, _ = ws.parse_config(config_json or "")
    return len(cfg.fields) + len(cfg.entities or {}) + len(cfg.relationships or []) if cfg is not None else 0


def largest_clean_draft(sid: str, run_id: str, ws: Workspace, round_no: int | None = None) -> dict | None:
    """The agent's clean dry run with the most rules in its transcript (optionally only after the last
    proposal of `round_no`). Used to re-evaluate a run whose auto-submission picked a partial probe."""
    run_dir = RUNS / sid / run_id
    msgs = json.loads((run_dir / "messages.json").read_text(encoding="utf-8"))
    results = {m.get("tool_call_id"): m.get("content") or "" for m in msgs if m["role"] == "tool"}
    best, turn = None, 0
    for m in msgs:
        if m["role"] != "assistant":
            continue
        turn += 1
        for tc in m.get("tool_calls") or []:
            if tc["function"]["name"] != "dry_run":
                continue
            try:
                res = json.loads(results.get(tc["id"], "") or "{}")
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                continue
            if res.get("ok") and not any(i.get("severity") == "error" for i in res.get("issues", [])):
                size = _draft_size(ws, args.get("config_json"))
                if best is None or size >= best["rules"]:
                    best = {"config_json": args.get("config_json"), "transcript_turn": turn, "rules": size}
    return best


def evaluate_recorded_draft(source: dict, base_doc: dict, output_dir, prior_run_id: str, draft: dict,
                            note: str) -> dict:
    """A new run whose only proposal is an agent-authored draft taken from an earlier run's transcript.
    No agent turns: held-out gates and the critic only, then a human decides. Provenance is recorded."""
    source = source | {"extension_base": base_doc["config"], "extension_output_dir": str(output_dir)}
    run = Run(source)
    run.state.update(experiment="raw-data", extension_base_run_id=base_doc.get("run_id"),
                     draft_source={"run_id": prior_run_id, "transcript_turn": draft.get("transcript_turn"),
                                   "rules": draft.get("rules"), "note": note})
    ws = Workspace(source)
    run.state["ext_base_findings"] = ws.ext_base_findings
    run.state["ext_editable"] = sorted(ws.ext_editable)
    cfg, issues = ws.parse_config(draft["config_json"])
    if cfg is None or any(i["severity"] == "error" for i in issues):
        raise ValueError(f"recorded draft no longer passes the static gate: {issues[:3]}")
    run.state.setdefault("ext_change_logs", []).append({"round": MAX_REVISIONS, "changes": ws.ext_last_changes,
                                                        "discarded": ws.ext_last_discarded})
    run.checkpoint("INSPECTED")
    run.event("stage", stage="RECORDED_DRAFT_EVALUATION", prior_run_id=prior_run_id)
    return _drive(run, ws, source, MAX_REVISIONS, cfg)


def auto_submit(run: Run, ws: Workspace, round_no: int, reason: str) -> MappingConfig | None:
    """Submit the agent's own last clean draft on its behalf. Measured on three ACNC extension runs: clean dry runs
    and no submission until the budget ran out, losing the work. The draft is the agent's, unchanged; it still
    goes through the held-out gates and the critic, and the review page says it was auto-submitted."""
    draft = run.state.get("last_clean_draft")
    if not draft:
        return None
    cfg, issues = ws.parse_config(draft["config_json"])
    if cfg is None or any(i["severity"] == "error" for i in issues):
        return None
    if ws.ext_base and not ws.ext_scope(cfg):
        # Measured (ACNC run 20261112T220306-c7ac80): the only clean dry run was an empty draft. Never submit one.
        run.event("stage", stage="AUTO_SUBMIT_REFUSED_EMPTY_DRAFT", round=round_no)
        return None
    run.state.setdefault("auto_submitted", []).append({"round": round_no, "reason": reason,
                                                        "draft_from_turn": draft.get("turn")})
    if ws.ext_base:
        run.state.setdefault("ext_change_logs", []).append(
            {"round": round_no, "changes": ws.ext_last_changes, "discarded": ws.ext_last_discarded})
    run.event("stage", stage="AUTO_SUBMITTED_LAST_CLEAN_DRAFT", round=round_no, reason=reason)
    run.state.pop("last_clean_draft", None)
    run.save()
    return cfg


def recover_clean_draft(sid: str, run_id: str) -> dict | None:
    """For a run that predates the auto-submit policy: find the agent's last clean dry run in its own transcript
    and record it, with the number of turns it then took without submitting. A resume applies the policy."""
    run_dir = RUNS / sid / run_id
    msgs = json.loads((run_dir / "messages.json").read_text(encoding="utf-8"))
    st = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    results = {m.get("tool_call_id"): m.get("content") or "" for m in msgs if m["role"] == "tool"}
    found, turns_after = None, 0
    for m in msgs:
        if m["role"] != "assistant":
            continue
        if found is not None:
            turns_after += 1
        for tc in m.get("tool_calls") or []:
            if tc["function"]["name"] == "submit_mapping":
                found = None
            if tc["function"]["name"] != "dry_run":
                continue
            try:
                res = json.loads(results.get(tc["id"], "") or "{}")
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                continue
            if res.get("ok") and not any(i.get("severity") == "error" for i in res.get("issues", [])):
                found, turns_after = args.get("config_json"), 0
    if not found:
        return None
    st["last_clean_draft"] = {"config_json": found, "turn": "recovered from transcript"}
    st["turns_since_clean"] = turns_after
    st["recovered_clean_draft"] = {"turns_without_submission": turns_after}
    if st.get("status") == "FAILED":
        st["status"] = "INTERRUPTED"      # resumable: the failure was the lost draft, now recovered
    (run_dir / "state.json").write_text(json.dumps(st, indent=2, default=str), encoding="utf-8")
    return {"turns_without_submission": turns_after}


def agent_round(run: Run, ws: Workspace, round_no: int) -> MappingConfig | None:
    """Let the model work with tools until it submits a statically valid config (or runs out of turns).
    The controller keeps the agent's last clean draft; if the agent stops submitting, the draft is not lost."""
    tools = EXT_TOOLS if ws.ext_base else TOOLS
    available_tools = tools
    for turn in range(MAX_EXT_TOOL_TURNS if ws.ext_base else MAX_TOOL_TURNS):
        pending = run.state.get("last_clean_draft")
        if pending and run.state.get("turns_since_clean", 0) >= AUTO_SUBMIT_AFTER_TURNS:
            cfg = auto_submit(run, ws, round_no, "no submission within two turns of a clean dry run")
            if cfg is not None:
                return cfg
        try:
            m = llm.chat(run.messages, stage=f"propose_r{round_no}", source_id=run.sid, run_id=run.run_id,
                         tools=available_tools,
                         # Measured: an ACNC extension draft (57 columns) hit the 6,000-token cap mid tool call.
                         max_tokens=16000 if ws.ext_base else 6000)
        except llm.BudgetExceeded:
            cfg = auto_submit(run, ws, round_no, "token budget reached after a clean dry run")
            if cfg is not None:
                return cfg
            raise
        available_tools = tools
        if run.state.get("last_clean_draft"):
            run.state["turns_since_clean"] = run.state.get("turns_since_clean", 0) + 1
        run.messages.append(_assistant_dict(m))
        if not m.tool_calls:
            run.messages.append({"role": "user", "content": "Continue using the tools. Finish by calling submit_mapping."})
            continue
        for tc in m.tool_calls:
            run.state["tool_calls"] += 1
            t0 = time.perf_counter()
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as e:
                args, result = {}, {"ok": False, "error": "ARGUMENTS_NOT_JSON", "detail": str(e)}
            else:
                if tc.function.name == "submit_mapping":
                    cfg, issues = ws.parse_config(args.get("config_json") or "")
                    errors = [i for i in issues if i["severity"] == "error"]
                    if cfg is not None and not errors:
                        run.state.pop("last_clean_draft", None)
                        run.state["turns_since_clean"] = 0
                        run.event("tool", round=round_no, name="submit_mapping", accepted=True, issues=issues)
                        accepted = {"accepted": True, "warnings": issues}
                        if ws.ext_base:
                            accepted["change_log"] = ws.ext_last_changes
                            run.state.setdefault("ext_change_logs", []).append(
                                {"round": round_no, "changes": ws.ext_last_changes,
                                 "discarded": ws.ext_last_discarded})
                        run.messages.append({"role": "tool", "tool_call_id": tc.id,
                                             "content": json.dumps(accepted, default=str)})
                        return cfg
                    result = {"accepted": False, "issues": issues}
                else:
                    try:
                        result = _dispatch(ws, tc.function.name, args)
                        # Measured (ACNC extension run 20261112T211007-25ec66): eleven clean dry runs in a row and
                        # no submission. After a clean dry run the controller asks for the submission.
                        clean = result.get("ok") and not any(i.get("severity") == "error" for i in result.get("issues", []))
                        if (ws.context_base or ws.ext_base) and tc.function.name == "dry_run" and clean:
                            result["next_action"] = "Submit this exact draft using submit_mapping."
                            available_tools = [tool for tool in TOOLS if tool["function"]["name"] == "submit_mapping"]
                            # Keep the LARGEST clean draft of the round, not the last: agents also dry-run small
                            # probes (measured on ACNC run 20261112T212142-d68338, round 1).
                            size = _draft_size(ws, args.get("config_json"))
                            best = run.state.get("last_clean_draft")
                            if best is None or best.get("round") != round_no or size >= best.get("rules", 0):
                                run.state["last_clean_draft"] = {"config_json": args.get("config_json"), "turn": turn,
                                                                 "round": round_no, "rules": size}
                            run.state["turns_since_clean"] = 0
                    except Exception as e:  # a failing tool is information for the model, not a crash
                        result = {"ok": False, "error": type(e).__name__, "detail": str(e)[:500]}
            content = json.dumps(result, default=str)
            if len(content) > 24000:
                content = content[:24000] + "...[truncated]"
            run.event("tool", round=round_no, name=tc.function.name, args=_short(json.dumps(args), 400),
                      ms=round((time.perf_counter() - t0) * 1000), result_head=content[:300])
            run.messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            if ws.reader is not None:
                run.state["reader"] = ws.reader.model_dump()
        run.save()  # every completed turn is durable: a crash loses at most the turn in flight
    return auto_submit(run, ws, round_no, "turn limit reached after a clean dry run")


def critic_sample(holdout: list[dict], n_rare: int, k: int = 6) -> list[dict]:
    """k rare-value records (spread across columns) + k random held-out records."""
    rare, rnd = holdout[:n_rare], holdout[n_rare:]
    step = max(1, len(rare) // k)
    return rare[::step][:k] + rnd[:k]


class RuleVerdict(BaseModel):
    rule_index: int = Field(ge=0, strict=True)
    verdict: Literal["ok", "wrong", "doubtful"]
    reason: str = Field(min_length=1)


class MissedField(BaseModel):
    source_path: str
    suggested_target: str
    reason: str


class CriticResponse(BaseModel):
    fields: list[RuleVerdict]
    missed: list[MissedField]
    summary: str = Field(min_length=1)


def critic(run: Run, cfg: MappingConfig, sample: list[dict], round_no: int, scope: set[int] | None = None) -> dict:
    """`scope` (extension runs): judge only these rule indices - the added/edited rules - against raw columns
    they read plus the record's name columns for context."""
    onto = ontology.load(cfg.profile_context, cfg.extensions)
    _, obs = run_engine(cfg, sample, run.source)
    if scope is not None:
        scoped = [cfg.fields[i] for i in sorted(scope)]
        name_cols = {p for f in cfg.fields if f.target in ("entity.legal_name", "entity.trading_name")
                     for p in f.source_paths}
        context_fields = scoped
        context_columns = {p for f in scoped for p in f.source_paths + [q.source_path for q in (f.qualifiers or {}).values()
                                                                        if q.source_path]} | name_cols
        targets_in_scope = {f.target for f in scoped}
        obs = [o for o in obs if o["field"] in targets_in_scope]
    else:
        context_fields = [f for f in cfg.fields if f.target.startswith("context.")]
        context_columns = {path for f in context_fields for path in f.source_paths}
    if cfg.profile_context:
        obs = [item for item in obs if item["field"].startswith("context.")]
    by_rec = {}
    for o in obs:
        claim = {"field": o["field"], "value": _short(o["value"], 220 if (cfg.profile_context or scope) else 70)}
        claim.update({key: o[key] for key in ("valid_from", "valid_to") if o[key] is not None})
        claim.update({key: o[key] for key in ("entity_role", "qualifiers", "claim_scope") if o.get(key)})
        by_rec.setdefault(o["source_record_id"], []).append(claim)
    # Re-derive record ids in order so raw records line up with their observations.
    from ..mapping.engine import record_id
    from collections import Counter
    seen = Counter()
    shown = []
    for r in sample:
        rid = record_id(r, cfg, seen) if r else None
        raw = {k: _short(v, 220) for k, v in r.items() if k in context_columns} if (cfg.profile_context or scope) else {
            k: _short(v, 70) for k, v in list(r.items())[:45]}
        shown.append({"raw": raw,
                      "observations": by_rec.get(rid, [])})
    active_fields = context_fields if (cfg.profile_context or scope is not None) else cfg.fields
    constants = [] if (cfg.profile_context or scope is not None) else cfg.constants
    targets = {f.target for f in active_fields} | {c.target for c in constants}
    mapping_fields = {"target", "source_paths", "steps", "when", "rationale", "valid_from_path", "valid_to_path",
                      "validity_date_formats", "claim_scope", "entity", "qualifiers", "join_with"}
    mapping = [f.model_dump(include=mapping_fields, exclude_none=True) for f in active_fields]
    mapping.extend({"target": c.target, "source_paths": [], "constant": c.value, "rationale": c.rationale}
                   for c in constants)
    for index, rule in enumerate(mapping):
        rule["rule_index"] = index
    payload = {
        "dataset": {"title": run.source["title"], "publisher": run.source["publisher"],
                    "record_grain_claimed": cfg.record_grain, "grain_rationale": cfg.grain_rationale,
                    "publisher_evidence": run.state.get("publisher_evidence", [])},
        "ontology": [d for d in onto.describe() if d["path"] in targets or
                     (not cfg.profile_context and d["path"].startswith("entity."))],
        "mapping": mapping,
        "unmapped": [u.model_dump() for u in cfg.unmapped],
        **({"approved_rules_kept_unchanged (already human-approved; not under review)": [
                {"target": f.target, "source_paths": f.source_paths} for i, f in enumerate(cfg.fields)
                if i not in scope]} if scope is not None else {}),
        **({"entities": {k: v.model_dump() for k, v in (cfg.entities or {}).items()},
            "relationships": [r.model_dump() for r in cfg.relationships or []],
            "crosswalks_used": _crosswalk_summaries(active_fields)} if cfg.extensions else {}),
        "heldout_records_note": "The first records were chosen for RARE values of some column; check that unusual "
                                "values still produce meaningful, correctly-typed observations.",
        "heldout_records": shown,
    }
    if cfg.profile_context:
        payload["heldout_records_note"] += (" Raw and mapped values are shortened for this display at the same "
                                             "length. Display shortening alone is not evidence of transform loss.")
    messages = [{"role": "system", "content": CRITIC_SYSTEM + (EXT_CRITIC_ADDENDUM if cfg.extensions else "")},
                {"role": "user", "content": json.dumps(payload, default=str)}]
    for attempt in range(2):
        m = llm.chat(messages, stage=f"critic_r{round_no}", source_id=run.sid, run_id=run.run_id,
                     model=llm.CRITIC_MODEL, json_mode=True,
                     # Measured on the first extension run: the reasoning model spent all 4,000 tokens before
                     # answering (finish_reason=length) twice. Extension critiques get more room.
                     max_tokens=12000 if cfg.extensions else 4000)
        try:
            response = CriticResponse.model_validate_json(m.content or "")
        except ValidationError:
            reason = "Response did not match the critic JSON schema."
        else:
            if sorted(field.rule_index for field in response.fields) == list(range(len(mapping))):
                verdict = response.model_dump() | {"prompt_version": CRITIC_PROMPT_VERSION}
                for field in verdict["fields"]:
                    rule = mapping[field["rule_index"]]
                    field.update(target=rule["target"], source_paths=rule["source_paths"])
                return verdict
            reason = "Response did not include exactly one verdict per mapping rule."
        run.event("critic_response_invalid", round=round_no, attempt=attempt + 1, reason=reason)
        messages = [*messages[:2], {"role": "user", "content": f"{reason} Return a fresh, complete response."}]
    return {"fields": [], "missed": [], "summary": f"Critic validation failed after two attempts. {reason}",
            "error": "INVALID_CRITIC_RESPONSE", "prompt_version": CRITIC_PROMPT_VERSION}


def _crosswalk_summaries(rules) -> list[dict]:
    from .. import crosswalk
    used = sorted({s.args.get("table") for r in rules for s in r.steps if s.op == "crosswalk"} - {None})
    return [d for d in crosswalk.describe() if d["table"] in used]


FINAL_STATES = ("PENDING_REVIEW", "NEEDS_ATTENTION", "FAILED")


def resume(source: dict, run_id: str) -> dict:
    """Continue a crashed/interrupted run from its last checkpoint instead of starting over."""
    run = Run.load(source, run_id)
    if run.state["snapshot_sha256"] != source["snapshot"]["sha256"]:
        raise ValueError("The snapshot changed since this run started. Start a new onboarding run.")
    if run.state["status"] in FINAL_STATES:
        return run.state
    if run.state.get("profile_context_base"):
        source = source | {"profile_context_base": run.state["profile_context_base"]}
        run.source = source
    if run.state.get("extension_base"):
        source = source | {"extension_base": run.state["extension_base"],
                           "extension_output_dir": run.state.get("output_dir")}
        run.source = source
    ws = Workspace(source)
    if not run.messages:
        run.messages = initial_messages(run, ws)
        run.save()
    if run.state.get("reader"):
        from ..mapping.schema import ReaderSpec
        ws.reader = ReaderSpec.model_validate(run.state["reader"])
    props = run.state["proposals"]
    pending = None
    if props and "critic" not in props[-1]:
        # Crashed between proposal and evaluation: re-evaluate the saved proposal, no new agent work.
        pending = MappingConfig.model_validate(props[-1]["config"])
        start = props[-1]["round"]
        props.pop()
    else:
        start = len(props)
    run.event("stage", stage="RESUMED", from_status=run.state["status"], start_round=start)
    return _drive(run, ws, source, start, pending)


def onboard(source: dict, human_feedback: str | None = None, experiment: str | None = None,
            only_targets: list[str] | None = None) -> dict:
    from .review import current_review, last_approved_config, load_proposal

    sid = source["source_id"]
    decision = current_review(sid) if human_feedback or not experiment else None
    revision_requested = (decision and decision["decision"] in {"rejected", "needs_evidence"}
                          and decision["snapshot_sha256"] == source["snapshot"]["sha256"])
    if human_feedback is None and revision_requested and decision["reviewer_kind"] == "human":
        human_feedback = decision["comment"] or None
    base = last_approved_config(sid) if human_feedback or only_targets else None
    if base is None and revision_requested and human_feedback:
        draft = load_proposal(sid)
        if current_review(sid, draft) == decision:
            base = draft["config"]
    if only_targets and base is None:
        raise ValueError("A scoped revision requires an approved mapping or a draft with review feedback")
    run = Run(source)
    run.state["experiment"] = experiment
    run.state["only_targets"] = only_targets
    ws = Workspace(source)
    run.state["inspection"] = ws.inspection
    run.state["human_feedback"] = human_feedback
    if human_feedback or only_targets:
        run.state["feedback_base_config"] = base
    run.messages = initial_messages(run, ws)
    run.checkpoint("INSPECTED")
    run.event("stage", stage="INSPECTED")
    return _drive(run, ws, source, 0, None)


def initial_messages(run: Run, ws: Workspace) -> list[dict]:
    source = run.source
    intro = {
        "source_id": source["source_id"], "title": source["title"], "publisher": source["publisher"],
        "licence": source["licence"], "advertised_format": source["advertised_format"],
        "resource_name": source["resource_name"], "inspection": ws.inspection,
        "publisher_evidence": run.state.get("publisher_evidence", []),
    }
    if ws.ext_base:
        base = ws.ext_base
        intro.pop("inspection")
        intro["record_grain"] = base.record_grain
        intro["grain_rationale"] = base.grain_rationale
        intro["reader"] = base.reader.model_dump(exclude_none=True)
        intro["approved_rules"] = [{"index": i, "target": r.target, "source_paths": r.source_paths,
                                    "ops": [s.op for s in r.steps], **({"when": r.when.model_dump()} if r.when else {}),
                                    **({"claim_scope": r.claim_scope} if r.claim_scope else {}),
                                    "editable": i in ws.ext_editable}
                                   for i, r in enumerate(base.fields)]
        intro["approved_constants"] = [{"target": c.target, "value": c.value} for c in base.constants]
        intro["previously_unmapped"] = [u.model_dump() for u in base.unmapped]
        intro["current_gate_failures_on_approved_rules"] = [
            {k: i.get(k) for k in ("code", "message", "target", "source_paths", "examples") if i.get(k)}
            for i in ws.ext_base_findings]
        if run.state.get("human_feedback"):
            intro["reviewer_rejected_previous_draft"] = {
                "reviewer_feedback": run.state["human_feedback"],
                "previous_draft": run.state.get("previous_draft"),
                "instruction": "Revise the previous draft to address the feedback. Keep its rules unless the "
                               "feedback or the data says otherwise. Verify every change with profile_columns "
                               "and dry_run; do not map a column the data does not support."}
        return [{"role": "system", "content": EXTENSION_SYSTEM},
                {"role": "user", "content": json.dumps(intro, default=str)[:24000]}]
    if ws.context_base:
        base = ws.context_base
        intro["record_grain"] = base.record_grain
        intro["reader"] = base.reader.model_dump()
        intro["previously_unmapped"] = [u.source_path for u in base.unmapped]
        return [{"role": "system", "content": PROFILE_CONTEXT_SYSTEM},
                {"role": "user", "content": json.dumps(intro, default=str)[:20000]}]
    human_feedback = run.state.get("human_feedback")
    if human_feedback:
        base = run.state.get("feedback_base_config")
        intro["mapping_revision"] = {
            "reviewer_feedback": human_feedback,
            "base_config": base,
            "instruction": ("Start from base_config and address the reviewer feedback. Preserve unrelated rules."
                            if base else "Use the reviewer feedback when proposing the new mapping.")}
    return [{"role": "system", "content": AGENT_SYSTEM},
            {"role": "user", "content": "Onboard this source. Metadata and raw inspection:\n"
                                       + json.dumps(intro, default=str)[:20000]}]


def scope_to_targets(base: dict, proposal: MappingConfig, only: list[str]) -> tuple[MappingConfig, list[str]]:
    """Controller-enforced narrow edit: take the proposal's rules/constants for `only` targets, keep EVERYTHING
    else from the last approved config. Returns the merged config and the out-of-scope changes discarded.
    (Measured need: asked in words to change one rule, the agent rewrote several others.)"""
    p = proposal.model_dump()
    merged = dict(base)
    merged["fields"] = [f for f in base["fields"] if f["target"] not in only] + \
                       [f for f in p["fields"] if f["target"] in only]
    merged["constants"] = [c for c in base["constants"] if c["target"] not in only] + \
                          [c for c in p["constants"] if c["target"] in only]
    # Out-of-scope rules that differ in any way (added, removed or edited) are discarded and reported.
    from ..mapping.schema import FieldRule
    # Normalise through the schema first: configs approved before newer optional DSL fields existed
    # must not look "changed" merely because those keys are absent.
    norm = lambda f: json.dumps(FieldRule.model_validate(f).model_dump(exclude_none=True), sort_keys=True)
    exact = lambda fs: {norm(f): f for f in fs if f["target"] not in only}
    a, b = exact(base["fields"]), exact(p["fields"])
    discarded = sorted(f"{f['target']} <- {f['source_paths']}" for k, f in {**a, **b}.items() if (k in a) != (k in b))
    for k in ("reader", "record_id", "observed_at", "record_grain", "grain_rationale"):
        if p[k] != base[k]:
            discarded.append(f"{k} (kept approved)")
    return MappingConfig.model_validate(merged), discarded


def _drive(run: Run, ws: Workspace, source: dict, start_round: int, pending: MappingConfig | None) -> dict:
    final_cfg = MappingConfig.model_validate(run.state["proposals"][-1]["config"]) if run.state["proposals"] else None
    passed = False
    for round_no in range(start_round, MAX_REVISIONS + 1):
        was_pending = pending is not None
        try:
            cfg, pending = (pending, None) if pending is not None else (agent_round(run, ws, round_no), None)
        except llm.BudgetExceeded as e:
            # Degrade, don't crash: the last evaluated proposal (if any) is kept as NEEDS_ATTENTION.
            run.event("stage", stage="BUDGET_EXHAUSTED", round=round_no, detail=str(e))
            run.state["budget_exhausted"] = {"round": round_no, "detail": str(e)}
            break
        if cfg is None:
            run.event("stage", stage="NO_SUBMISSION", round=round_no)
            break
        only = run.state.get("only_targets")
        if only and not was_pending:
            from .review import last_approved_config
            base = run.state.get("feedback_base_config") or last_approved_config(run.sid)
            cfg, discarded = scope_to_targets(base, cfg, only)
            run.state.setdefault("scope_discarded", []).append({"round": round_no, "discarded": discarded})
            run.event("stage", stage="SCOPE_ENFORCED", round=round_no, only=only, discarded=discarded)
        final_cfg = cfg
        run.state["proposals"].append({"round": round_no, "digest": cfg.digest(), "config": cfg.model_dump()})
        run.checkpoint(f"PROPOSED_v{round_no}")

        disc, hold, cols, _ = ws.pool(cfg.reader)
        h_issues, h_report = holdout_issues(cfg, disc, hold, source)
        run.state["proposals"][-1].update(holdout_issues=h_issues, holdout_report=h_report)
        run.checkpoint(f"VALIDATED_v{round_no}")

        scope = ws.ext_scope(cfg) if ws.ext_base else None
        try:
            verdict = critic(run, cfg, critic_sample(hold, ws.rare_holdout(cfg.reader)), round_no, scope=scope)
        except llm.BudgetExceeded as e:
            run.event("stage", stage="BUDGET_EXHAUSTED", round=round_no, detail=str(e))
            run.state["budget_exhausted"] = {"round": round_no, "detail": str(e)}
            verdict = {"fields": [], "missed": [], "summary": "Critic not run: token budget exhausted.",
                       "error": "BUDGET_EXHAUSTED", "prompt_version": CRITIC_PROMPT_VERSION}
        run.state["proposals"][-1]["critic"] = verdict
        run.checkpoint(f"CRITIQUED_v{round_no}")

        evaluated = [i for i in h_issues if i.get("target", "").startswith("context.")] if cfg.profile_context else h_issues
        if scope is not None:
            in_scope = {cfg.fields[i].target for i in scope}
            evaluated = [i for i in h_issues if not i.get("target") or i["target"] in in_scope]
        errors = [i for i in evaluated if i["severity"] == "error"]
        if scope is not None:
            # An extension run answers for its CHANGES. A rule whose transform the run left exactly as approved
            # (only its role / scope / validity moved) cannot be fixed here; a "wrong" verdict about it is shown
            # to the reviewer but does not block the proposal (measured deadlock: ACNC run 20261112T212142-d68338).
            approved_steps = {(r.target, tuple(r.source_paths), json.dumps([s.model_dump() for s in r.steps]))
                              for r in ws.ext_base.fields}
            scoped_rules = [cfg.fields[i] for i in sorted(scope)]
            for f in verdict.get("fields", []):
                rule = scoped_rules[f["rule_index"]] if f.get("rule_index", -1) < len(scoped_rules) else None
                if (f.get("verdict") == "wrong" and rule is not None and
                        (rule.target, tuple(rule.source_paths), json.dumps([s.model_dump() for s in rule.steps]))
                        in approved_steps):
                    f["verdict"] = "doubtful"
                    f["approved_behaviour"] = True
                    f["reason"] = "[concerns approved behaviour this run cannot change] " + f["reason"]
        wrong = [f for f in verdict.get("fields", []) if f.get("verdict") == "wrong"]
        doubtful = [f for f in verdict.get("fields", []) if f.get("verdict") == "doubtful"]
        run.event("stage", stage="EVALUATED", round=round_no, holdout_errors=len(errors),
                  critic_wrong=len(wrong), critic_doubtful=len(doubtful), critic_error=verdict.get("error"))
        if verdict.get("error"):
            break
        if not errors and not wrong:
            passed = True
            break
        if round_no == MAX_REVISIONS:
            break
        feedback = {
            "instruction": "Your config was run on HELD-OUT records you have not seen, then reviewed by a critic. "
                           "Fix every error and every 'wrong' verdict (re-profile columns if needed), consider the "
                           "'doubtful' ones and 'missed' suggestions, dry_run, then submit_mapping again. If a field "
                           "cannot be made reliable, move it to unmapped with the reason. Do not hide errors.",
            "holdout_issues": evaluated,
            "holdout_field_report": [{k: f[k] for k in ("target", "source_paths", "source_present", "emitted",
                                                        "error_rate_of_present", "errors", "error_examples")}
                                     for f in h_report["fields"]
                                     if not cfg.profile_context or f["target"].startswith("context.")],
            "critic": verdict,
        }
        run.messages.append({"role": "user", "content": json.dumps(feedback, default=str)[:30000]})
        run.checkpoint(f"REVISING_v{round_no + 1}")

    run.state["finished_at"] = _now()
    status = "PENDING_REVIEW" if passed else "NEEDS_ATTENTION" if final_cfg else "FAILED"
    run.state["final_digest"] = final_cfg.digest() if final_cfg else None
    run.checkpoint(status)
    exp = run.state.get("experiment")
    out_dir = OUT_MAPPINGS.parent / "experiments" / exp if exp else OUT_MAPPINGS
    if run.state.get("output_dir"):
        from pathlib import Path
        out_dir, exp = Path(run.state["output_dir"]), exp or "extension"
    if final_cfg:
        out_dir.mkdir(parents=True, exist_ok=True)
        prev = out_dir / f"{run.sid}.json"
        if prev.exists() and run.state.get("output_dir"):   # extension proposals keep their history too
            old = json.loads(prev.read_text(encoding="utf-8"))
            (out_dir / "superseded").mkdir(exist_ok=True)
            prev.replace(out_dir / "superseded" / f"{run.sid}.{old['run_id']}.json")
        if prev.exists() and not exp:  # keep superseded proposals; history is never overwritten
            old = json.loads(prev.read_text(encoding="utf-8"))
            (OUT_MAPPINGS / "superseded").mkdir(exist_ok=True)
            prev.rename(OUT_MAPPINGS / "superseded" / f"{run.sid}.{old['run_id']}.json")
        doc = {"status": status, "run_id": run.run_id, "prompt_version": run.state["prompt_version"], "model": llm.DEFAULT_MODEL,
               "ontology_sha256": run.state["ontology_sha256"], "snapshot_sha256": run.state["snapshot_sha256"],
               "config_digest": final_cfg.digest(), "config": final_cfg.model_dump()}
        (out_dir / f"{run.sid}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    if run.state.get("extension_base"):
        from ..rawdata.review import write_extension_report
        write_extension_report(run.sid, run.run_id, out_dir)
        return run.state
    from .review import write_report
    write_report(run.sid, run.run_id, out_dir=out_dir if exp else None)
    return run.state


def previous_draft(base: dict, proposal: dict) -> dict:
    """Re-express a merged extension proposal as the ExtensionDraft the agent would submit (for revisions)."""
    kept = {json.dumps(r, sort_keys=True) for r in base["fields"]}
    return {"entities": proposal.get("entities"), "relationships": proposal.get("relationships"),
            "new_rules": [{k: v for k, v in r.items() if v is not None}
                          for r in proposal["fields"] if json.dumps(r, sort_keys=True) not in kept],
            "unmapped": proposal.get("unmapped", [])}


def onboard_extension(source: dict, base_doc: dict, output_dir, *, feedback: str | None = None,
                      feedback_source: str | None = None, previous: dict | None = None) -> dict:
    """Extend an APPROVED mapping with ext-v1 concepts, roles and relationships (review 5.2-5.4).
    The agent proposes additions; the controller merges them into the approved config, gates the result on
    held-out rows, runs the critic on the changed rules, and leaves the proposal PENDING_REVIEW for a human.
    With `feedback` (a reviewer's rejection comment) the agent revises its previous draft."""
    source = source | {"extension_base": base_doc["config"], "extension_output_dir": str(output_dir)}
    run = Run(source)
    run.state["experiment"] = "raw-data"
    run.state["extension_base_run_id"] = base_doc.get("run_id")
    if feedback:
        run.state["human_feedback"] = feedback
        run.state["feedback_source"] = feedback_source
        run.state["previous_extension_run_id"] = (previous or {}).get("run_id")
        run.state["previous_draft"] = previous_draft(base_doc["config"], previous["config"]) if previous else None
    ws = Workspace(source)
    run.state["inspection"] = ws.inspection
    run.state["ext_base_findings"] = ws.ext_base_findings
    run.state["ext_editable"] = sorted(ws.ext_editable)
    run.messages = initial_messages(run, ws)
    run.checkpoint("INSPECTED")
    run.event("stage", stage="INSPECTED", ext_base_findings=len(ws.ext_base_findings))
    return _drive(run, ws, source, 0, None)
