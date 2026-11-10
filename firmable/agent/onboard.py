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

from .. import llm, ontology
from ..mapping.schema import MappingConfig
from ..mapping.validate import holdout_issues, run_engine
from ..paths import OUT_MAPPINGS, RUNS
from .prompts import AGENT_SYSTEM, CRITIC_SYSTEM, PROMPT_VERSION
from .workspace import Workspace, _short

MAX_TOOL_TURNS = 18      # per proposal round
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


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Run:
    def __init__(self, source: dict, run_id: str | None = None):
        self.source = source
        self.sid = source["source_id"]
        self.run_id = run_id or f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.dir = RUNS / self.sid / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state = {"run_id": self.run_id, "source_id": self.sid, "status": "STARTED", "started_at": _now(),
                      "prompt_version": PROMPT_VERSION, "model": llm.DEFAULT_MODEL, "critic_model": llm.CRITIC_MODEL,
                      "ontology_sha256": ontology.load().sha256, "snapshot_sha256": source["snapshot"]["sha256"],
                      "proposals": [], "tool_calls": 0, "stages": []}
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
    raise ValueError(f"unknown tool {name}")


def agent_round(run: Run, ws: Workspace, round_no: int) -> MappingConfig | None:
    """Let the model work with tools until it submits a statically valid config (or runs out of turns)."""
    for turn in range(MAX_TOOL_TURNS):
        m = llm.chat(run.messages, stage=f"propose_r{round_no}", source_id=run.sid, run_id=run.run_id, tools=TOOLS)
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
                        run.event("tool", round=round_no, name="submit_mapping", accepted=True, issues=issues)
                        run.messages.append({"role": "tool", "tool_call_id": tc.id,
                                             "content": json.dumps({"accepted": True, "warnings": issues})})
                        return cfg
                    result = {"accepted": False, "issues": issues}
                else:
                    try:
                        result = _dispatch(ws, tc.function.name, args)
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
    return None


def critic_sample(holdout: list[dict], n_rare: int, k: int = 6) -> list[dict]:
    """k rare-value records (spread across columns) + k random held-out records."""
    rare, rnd = holdout[:n_rare], holdout[n_rare:]
    step = max(1, len(rare) // k)
    return rare[::step][:k] + rnd[:k]


def critic(run: Run, cfg: MappingConfig, sample: list[dict], round_no: int) -> dict:
    onto = ontology.load()
    _, obs = run_engine(cfg, sample, run.source)
    by_rec = {}
    for o in obs:
        by_rec.setdefault(o["source_record_id"], []).append({"field": o["field"], "value": _short(o["value"], 70)})
    # Re-derive record ids in order so raw records line up with their observations.
    from ..mapping.engine import record_id
    from collections import Counter
    seen = Counter()
    shown = []
    for r in sample:
        rid = record_id(r, cfg, seen) if r else None
        shown.append({"raw": {k: _short(v, 70) for k, v in list(r.items())[:45]},
                      "observations": by_rec.get(rid, [])})
    targets = {f.target for f in cfg.fields} | {c.target for c in cfg.constants}
    payload = {
        "dataset": {"title": run.source["title"], "publisher": run.source["publisher"],
                    "record_grain_claimed": cfg.record_grain, "grain_rationale": cfg.grain_rationale},
        "ontology": [d for d in onto.describe() if d["path"] in targets or d["path"].startswith("entity.")],
        "mapping": [{"target": f.target, "source_paths": f.source_paths, "steps": [s.model_dump() for s in f.steps],
                     "rationale": f.rationale} for f in cfg.fields]
                   + [{"target": c.target, "constant": c.value, "rationale": c.rationale} for c in cfg.constants],
        "unmapped": [u.model_dump() for u in cfg.unmapped],
        "heldout_records_note": "The first records were chosen for RARE values of some column; check that unusual "
                                "values still produce meaningful, correctly-typed observations.",
        "heldout_records": shown,
    }
    m = llm.chat([{"role": "system", "content": CRITIC_SYSTEM},
                  {"role": "user", "content": json.dumps(payload, default=str)}],
                 stage=f"critic_r{round_no}", source_id=run.sid, run_id=run.run_id, model=llm.CRITIC_MODEL,
                 json_mode=True, max_tokens=4000)
    try:
        return json.loads(m.content or "{}")
    except json.JSONDecodeError:
        return {"fields": [], "missed": [], "summary": "critic output was not JSON", "raw": (m.content or "")[:500]}


FINAL_STATES = ("PENDING_REVIEW", "NEEDS_ATTENTION", "FAILED")


def resume(source: dict, run_id: str) -> dict:
    """Continue a crashed/interrupted run from its last checkpoint instead of starting over."""
    run = Run.load(source, run_id)
    if run.state["status"] in FINAL_STATES:
        return run.state
    ws = Workspace(source)
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
    run = Run(source)
    run.state["experiment"] = experiment
    run.state["only_targets"] = only_targets
    ws = Workspace(source)
    run.state["inspection"] = ws.inspection
    run.state["human_feedback"] = human_feedback
    run.checkpoint("INSPECTED")
    run.event("stage", stage="INSPECTED")

    intro = {
        "source_id": source["source_id"], "title": source["title"], "publisher": source["publisher"],
        "licence": source["licence"], "advertised_format": source["advertised_format"],
        "resource_name": source["resource_name"], "inspection": ws.inspection,
    }
    if human_feedback:
        # A reviewer rejected a proposal: the agent revises the last APPROVED config (not its own rejected
        # draft, which would carry the rejected changes forward), plus the reviewer's comment.
        from .review import last_approved_config
        intro["previous_proposal_rejected_by_human"] = {
            "reviewer_feedback": human_feedback,
            "last_approved_config": last_approved_config(source["source_id"]),
            "instruction": "Start from last_approved_config. Change only what the reviewer asks; keep everything else identical."}
    run.messages = [{"role": "system", "content": AGENT_SYSTEM},
                    {"role": "user", "content": "Onboard this source. Metadata and raw inspection:\n"
                                                + json.dumps(intro, default=str)[:20000]}]
    return _drive(run, ws, source, 0, None)


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
        cfg, pending = (pending, None) if pending is not None else (agent_round(run, ws, round_no), None)
        if cfg is None:
            run.event("stage", stage="NO_SUBMISSION", round=round_no)
            break
        only = run.state.get("only_targets")
        if only and pending is None:
            from .review import last_approved_config
            cfg, discarded = scope_to_targets(last_approved_config(run.sid), cfg, only)
            run.state.setdefault("scope_discarded", []).append({"round": round_no, "discarded": discarded})
            run.event("stage", stage="SCOPE_ENFORCED", round=round_no, only=only, discarded=discarded)
        final_cfg = cfg
        run.state["proposals"].append({"round": round_no, "digest": cfg.digest(), "config": cfg.model_dump()})
        run.checkpoint(f"PROPOSED_v{round_no}")

        disc, hold, cols, _ = ws.pool(cfg.reader)
        h_issues, h_report = holdout_issues(cfg, disc, hold, source)
        run.state["proposals"][-1].update(holdout_issues=h_issues, holdout_report=h_report)
        run.checkpoint(f"VALIDATED_v{round_no}")

        verdict = critic(run, cfg, critic_sample(hold, ws.rare_holdout(cfg.reader)), round_no)
        run.state["proposals"][-1]["critic"] = verdict
        run.checkpoint(f"CRITIQUED_v{round_no}")

        errors = [i for i in h_issues if i["severity"] == "error"]
        wrong = [f for f in verdict.get("fields", []) if f.get("verdict") == "wrong"]
        doubtful = [f for f in verdict.get("fields", []) if f.get("verdict") == "doubtful"]
        run.event("stage", stage="EVALUATED", round=round_no, holdout_errors=len(errors),
                  critic_wrong=len(wrong), critic_doubtful=len(doubtful))
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
            "holdout_issues": h_issues,
            "holdout_field_report": [{k: f[k] for k in ("target", "source_paths", "source_present", "emitted",
                                                        "error_rate_of_present", "errors", "error_examples")}
                                     for f in h_report["fields"]],
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
    if final_cfg:
        out_dir.mkdir(parents=True, exist_ok=True)
        prev = out_dir / f"{run.sid}.json"
        if prev.exists() and not exp:  # keep superseded proposals; history is never overwritten
            old = json.loads(prev.read_text(encoding="utf-8"))
            (OUT_MAPPINGS / "superseded").mkdir(exist_ok=True)
            prev.rename(OUT_MAPPINGS / "superseded" / f"{run.sid}.{old['run_id']}.json")
        doc = {"status": status, "run_id": run.run_id, "prompt_version": PROMPT_VERSION, "model": llm.DEFAULT_MODEL,
               "ontology_sha256": run.state["ontology_sha256"], "snapshot_sha256": run.state["snapshot_sha256"],
               "config_digest": final_cfg.digest(), "config": final_cfg.model_dump()}
        (out_dir / f"{run.sid}.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    from .review import write_report
    write_report(run.sid, run.run_id, out_dir=out_dir if exp else None)
    return run.state
