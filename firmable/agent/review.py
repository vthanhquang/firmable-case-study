"""What a human sees before approving, and the approval record itself.

The report is generated from the run's checkpointed state. Approval binds a reviewer to the exact
config digest: any later edit to the config invalidates the approval, and extraction refuses it.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

from .. import llm
from ..paths import OUT_MAPPINGS, OUT_REVIEWS, RUNS


def _diff(a: dict, b: dict) -> list[str]:
    fa = {(f["target"], tuple(f["source_paths"])): f for f in a["fields"]}
    fb = {(f["target"], tuple(f["source_paths"])): f for f in b["fields"]}
    out = []
    for k in fb.keys() - fa.keys():
        out.append(f"+ added `{k[1]}` -> `{k[0]}`")
    for k in fa.keys() - fb.keys():
        out.append(f"- removed `{k[1]}` -> `{k[0]}`")
    for k in fa.keys() & fb.keys():
        if fa[k]["steps"] != fb[k]["steps"] or fa[k]["confidence"] != fb[k]["confidence"]:
            out.append(f"~ changed `{k[1]}` -> `{k[0]}` (steps/confidence)")
    if a["reader"] != b["reader"]:
        out.append(f"~ reader {a['reader']} -> {b['reader']}")
    if a["record_id"] != b["record_id"]:
        out.append(f"~ record_id {a['record_id']['strategy']} -> {b['record_id']['strategy']} {b['record_id']['source_paths']}")
    return out


def _second_opinion(sid: str, st: dict) -> list[str]:
    """Rules on which an independent agent run disagrees: measured to be where the agent is unreliable,
    so this is where the reviewer should spend their minutes."""
    if not st["proposals"] or st.get("experiment"):
        return []
    from ..paths import OUT
    from .stability import _pairs
    mine = st["proposals"][-1]["config"]
    L = []
    for p in sorted((OUT / "experiments").glob(f"*/{sid}.json")):
        other = json.loads(p.read_text(encoding="utf-8"))["config"]
        a, b = _pairs(mine), _pairs(other)
        if not L:
            L = ["", "## Second opinion (independent agent run)"]
        L.append(f"- `{p.parent.name}`: {len(a & b)}/{len(a | b)} rules agree"
                 + ("." if a == b else "; **check these first:**"))
        L += [f"    - only this proposal: `{x[1]}` -> `{x[0]}` {x[2]}" for x in sorted(a - b)]
        L += [f"    - only the other run: `{x[1]}` -> `{x[0]}` {x[2]}" for x in sorted(b - a)]
    return L


def write_report(sid: str, run_id: str, out_dir=None) -> str:
    st = json.loads((RUNS / sid / run_id / "state.json").read_text(encoding="utf-8"))
    from ..sources.select import load_manifest
    src = load_manifest()[sid]
    usage = llm.summarize().get((sid, run_id), {})
    fb = [f"- **Revising after human rejection:** {st['human_feedback']}"] if st.get("human_feedback") else []
    log = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
    if log.exists() and not st.get("experiment"):
        last = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
        mine = bool(st["proposals"]) and _matches(last, {
            "config_digest": _digest({"config": st["proposals"][-1]["config"]}),
            "run_id": run_id, "snapshot_sha256": st["snapshot_sha256"]})
        fb.append(f"- **Latest review decision:** {last['decision']} by {last['reviewer']} ({last['reviewer_kind']}) at "
                  f"{last['decided_at']}" + ("" if mine else " (applies to an earlier proposal)"))
    L = [f"# Mapping review: `{sid}`", ""] + fb + [
         f"- **Status:** {st['status']}  (run `{run_id}`, prompt `{st['prompt_version']}`, model `{st['model']}`)",
         f"- **Dataset:** {src['title']} — {src['publisher']}",
         f"- **Resource:** {src['resource_name']} ({src['advertised_format']}), sha256 `{st['snapshot_sha256']}`",
         f"- **Licence:** {src['licence']}",
         f"- **Agent effort:** {len(st['proposals'])} proposal(s), {st['tool_calls']} tool calls, "
         f"{usage.get('calls', 0)} model calls, {usage.get('prompt_tokens', 0):,} prompt + "
         f"{usage.get('completion_tokens', 0):,} completion tokens, {usage.get('latency_ms', 0) / 1000:.0f}s model time", ""]
    if not st["proposals"]:
        L.append("**The agent did not submit a config.** See events.jsonl.")
    else:
        p = st["proposals"][-1]
        cfg = p["config"]
        rep = p["holdout_report"]["fields"]  # same order as cfg["fields"]
        if any(f["target"] in {"observation.valid_from", "observation.valid_to"} for f in cfg["fields"]):
            L += ["**Current extraction:** Legacy record-level validity rules below have no effect on",
                  "claims. Check each claim's validity paths before approving.", ""]
        L += [f"## Final proposal (v{p['round']}, digest `{_digest({'config': cfg})}`)", "",
              f"**Record grain:** `{cfg['record_grain']}` — {cfg['grain_rationale']}", "",
              f"**Reader:** `{json.dumps(cfg['reader'])}`", "",
              f"**Record id:** `{cfg['record_id']['strategy']}` {cfg['record_id']['source_paths']} — {cfg['record_id']['rationale']}", "",
              f"**observed_at:** `{json.dumps(cfg['observed_at'])}`", "",
              "| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |",
              "|---|---|---|---|---|---|---|"]
        for i, f in enumerate(cfg["fields"]):
            r = rep[i] if i < len(rep) else {}
            steps = ", ".join(s["op"] + (f"({json.dumps(s['args'])})" if s["args"] else "") for s in f["steps"])
            cond = f" *when {f['when']['source_path']} {f['when']['op']} {f['when']['values']}*" if f.get("when") else ""
            validity = ", ".join(f"{key.removesuffix('_path')} from {f[key]}"
                                 for key in ("valid_from_path", "valid_to_path") if f.get(key))
            cells = [f"{', '.join(f['source_paths'])}{cond}", f"`{f['target']}`",
                     ", ".join(part for part in (steps, validity) if part), str(f["confidence"]),
                     f"{r.get('emitted', '?')} / {r.get('source_present', '?')}", str(r.get('errors') or ''), f['rationale']]
            L.append("| " + " | ".join(value.replace("|", r"\|").replace("\n", "<br>") for value in cells) + " |")
        if cfg["constants"]:
            L += ["", "**Constants:**"] + [f"- `{c['target']}` = `{c['value']}` (conf {c['confidence']}): {c['rationale']}"
                                           for c in cfg["constants"]]
        L += ["", "**Deliberately unmapped:**"] + [f"- `{u['source_path']}` — {u['reason']}" for u in cfg["unmapped"]]
        L += ["", f"**Held-out run:** {p['holdout_report']['records_in']} records, "
                  f"{p['holdout_report']['records_with_output']} produced observations; record errors "
                  f"{p['holdout_report']['record_errors']}", ""]
        L += ["**Open issues (held-out validator):**"] + ([f"- [{i['severity']}] {i['code']}: {i['message']}"
                                                         + (f" (`{i.get('target')}`)" if i.get('target') else "")
                                                         for i in p["holdout_issues"]] or ["- none"])
        c = p.get("critic", {})
        L += ["", f"**Critic:** {c.get('summary', '')}"]
        L += [f"- {f.get('verdict')}: `{f.get('target')}` <- {f.get('source_paths')} — {f.get('reason')}"
              for f in c.get("fields", []) if f.get("verdict") != "ok"]
        L += [f"- missed? `{m.get('source_path')}` -> `{m.get('suggested_target')}` — {m.get('reason')}"
              for m in c.get("missed", [])]
        if cfg.get("notes"):
            L += ["", f"**Agent notes:** {cfg['notes']}"]
        if len(st["proposals"]) > 1:
            L += ["", "## Self-correction trace"]
            for prev, cur in zip(st["proposals"], st["proposals"][1:]):
                errs = [i["code"] + (f"({i.get('target')})" if i.get("target") else "")
                        for i in prev["holdout_issues"] if i["severity"] == "error"]
                wrong = [f"{f.get('target')}" for f in prev.get("critic", {}).get("fields", []) if f.get("verdict") == "wrong"]
                L.append(f"- v{prev['round']} -> v{cur['round']}: triggered by validator errors {errs or 'none'}, "
                         f"critic 'wrong' {wrong or 'none'}")
                L += [f"    - {d}" for d in _diff(prev["config"], cur["config"])] or ["    - (no structural change)"]
    if st.get("only_targets"):
        L += ["", f"## Scope enforced by the controller: only {st['only_targets']} may change"]
        for s in st.get("scope_discarded", []):
            L.append(f"- round {s['round']}: discarded out-of-scope changes: {s['discarded'] or 'none'}")
    L += _second_opinion(sid, st)
    L += ["", "## Decision", ""]
    if st.get("experiment"):
        L += ["This experimental proposal is outside the approval queue.", ""]
    else:
        L += [f"Approve: `python -m firmable.cli approve {sid} --reviewer \"<name>\"`  ",
              f"Reject:  `python -m firmable.cli approve {sid} --reviewer \"<name>\" --reject --comment \"why\"`", ""]
    target = out_dir or OUT_REVIEWS
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{sid}.md"
    path.write_text("\n".join(L), encoding="utf-8", newline="\n")
    return str(path)


def _digest(doc: dict) -> str:
    # Recomputed from the config itself, never trusted from the stored field.
    from ..mapping.schema import MappingConfig
    return MappingConfig.model_validate(doc["config"]).digest()


def load_proposal(sid: str) -> dict:
    return json.loads((OUT_MAPPINGS / f"{sid}.json").read_text(encoding="utf-8"))


def proposal_ref(doc: dict) -> dict:
    return {"config_digest": _digest(doc), "run_id": doc["run_id"],
            "snapshot_sha256": doc.get("snapshot_sha256")}


def _matches(record: dict, ref: dict) -> bool:
    return (record["config_digest"] == ref["config_digest"] and record["run_id"] == ref["run_id"]
            and record.get("snapshot_sha256", ref["snapshot_sha256"]) == ref["snapshot_sha256"])


def _check_review_evidence(sid: str, doc: dict, ref: dict) -> None:
    state = json.loads((RUNS / sid / ref["run_id"] / "state.json").read_text(encoding="utf-8"))
    saved = state["proposals"][-1]["config"] if state.get("proposals") else None
    if (state.get("experiment") or not saved or doc["config"].get("source_id") != sid
            or _digest({"config": saved}) != ref["config_digest"]
            or not ref["snapshot_sha256"] or state.get("snapshot_sha256") != ref["snapshot_sha256"]
            or state["status"] != doc["status"]):
        raise ValueError(f"{sid}: the current proposal differs from its review evidence")


def current_report(sid: str) -> tuple[str, dict]:
    doc = load_proposal(sid)
    ref = proposal_ref(doc)
    _check_review_evidence(sid, doc, ref)
    return Path(write_report(sid, ref["run_id"])).read_text(encoding="utf-8"), ref


def decision_proposal(sid: str, reviewer: str, reviewer_kind: str, reject: bool, expected: dict | None) -> tuple[dict, dict]:
    if not reviewer.strip() or reviewer_kind not in {"human", "ai_assistant_proxy"}:
        raise ValueError("A reviewer name and a supported reviewer kind are required")
    doc = load_proposal(sid)
    ref = proposal_ref(doc)
    if expected is not None and expected != ref:
        raise ValueError(f"{sid}: the proposal changed after the review was opened")
    if not reject and doc["status"] != "PENDING_REVIEW":
        raise ValueError(f"{sid}: approval requires a proposal that passed validation (current status {doc['status']})")
    _check_review_evidence(sid, doc, ref)
    return doc, ref


def approve(sid: str, reviewer: str, reviewer_kind: str, reject: bool = False, comment: str = "",
            *, expected: dict | None = None, review_minutes: float | None = None) -> dict:
    return record_decision(sid, reviewer, reviewer_kind, "rejected" if reject else "approved", comment,
                           expected=expected, review_minutes=review_minutes)


def record_decision(sid: str, reviewer: str, reviewer_kind: str, decision: str, comment: str = "",
                    *, expected: dict | None = None, review_minutes: float | None = None) -> dict:
    if decision not in {"approved", "rejected", "needs_evidence"}:
        raise ValueError(f"Unknown mapping decision {decision!r}")
    doc, ref = decision_proposal(sid, reviewer, reviewer_kind, decision != "approved", expected)
    if review_minutes is not None and (not math.isfinite(review_minutes) or review_minutes < 0):
        raise ValueError("Review minutes must be a non-negative finite number")
    rec = {"source_id": sid, "decision": decision, "reviewer": reviewer,
           "reviewer_kind": reviewer_kind, **ref,
           "proposal_status_at_review": doc["status"], "comment": comment,
           "decided_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if review_minutes is not None:
        rec["review_minutes"] = review_minutes
    with open(OUT_MAPPINGS / f"{sid}.approvals.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def last_approved_config(sid: str) -> dict | None:
    """The most recently approved config for a source (searching current and superseded proposals by digest)."""
    log = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
    if not log.exists():
        return None
    approved = [row for row in map(json.loads, log.read_text(encoding="utf-8").splitlines())
                if row["decision"] == "approved"]
    if not approved:
        return None
    candidates = [OUT_MAPPINGS / f"{sid}.json"] + sorted((OUT_MAPPINGS / "superseded").glob(f"{sid}.*.json"))
    for p in candidates:
        if p.exists():
            doc = json.loads(p.read_text(encoding="utf-8"))
            if _matches(approved[-1], proposal_ref(doc)):
                return doc["config"]
    return None


def restore_last_approved(sid: str) -> str | None:
    """Make the last approved config current again (the rejected one moves to superseded). Returns its run_id."""
    log = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
    if not log.exists():
        return None
    approved = [row for row in map(json.loads, log.read_text(encoding="utf-8").splitlines())
                if row["decision"] == "approved"]
    if not approved:
        return None
    cur = OUT_MAPPINGS / f"{sid}.json"
    for p in sorted((OUT_MAPPINGS / "superseded").glob(f"{sid}.*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if _matches(approved[-1], proposal_ref(doc)):
            old = json.loads(cur.read_text(encoding="utf-8"))
            cur.rename(OUT_MAPPINGS / "superseded" / f"{sid}.{old['run_id']}.json")
            p.rename(cur)
            return doc["run_id"]
    return None


def current_review(sid: str, doc: dict | None = None) -> dict | None:
    """Return the latest decision only when it applies to this exact proposal."""
    p = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
    if not p.exists() or (doc is None and not (OUT_MAPPINGS / f"{sid}.json").exists()):
        return None
    rows = p.read_text(encoding="utf-8").splitlines()
    if not rows:
        return None
    last = json.loads(rows[-1])
    if "snapshot_sha256" not in last:
        # The historical benchmark logs predate snapshot binding. Recover it from the recorded run.
        state_path = RUNS / sid / last["run_id"] / "state.json"
        if not state_path.is_file():
            return None
        last["snapshot_sha256"] = json.loads(state_path.read_text(encoding="utf-8")).get("snapshot_sha256")
    return last if _matches(last, proposal_ref(doc if doc is not None else load_proposal(sid))) else None


def current_approval(sid: str, doc: dict | None = None) -> dict | None:
    review = current_review(sid, doc)
    return review if review and review["decision"] == "approved" else None
