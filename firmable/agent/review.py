"""What a human sees before approving, and the approval record itself.

The report is generated from the run's checkpointed state. Approval binds a reviewer to the exact
config digest: any later edit to the config invalidates the approval, and extraction refuses it.
"""
from __future__ import annotations

import datetime as dt
import json

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
        mine = bool(st["proposals"]) and _digest({"config": st["proposals"][-1]["config"]}) == last["config_digest"]
        fb.append(f"- **Latest review decision:** {last['decision']} by {last['reviewer']} ({last['reviewer_kind']}) at "
                  f"{last['decided_at']}" + ("" if mine else " - *for a different config digest; this proposal is not yet decided*"))
    L = [f"# Mapping review: `{sid}`", ""] + fb + [
         f"- **Status:** {st['status']}  (run `{run_id}`, prompt `{st['prompt_version']}`, model `{st['model']}`)",
         f"- **Dataset:** {src['title']} — {src['publisher']}",
         f"- **Resource:** {src['resource_name']} ({src['advertised_format']}), sha256 `{st['snapshot_sha256'][:16]}…`",
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
        L += [f"## Final proposal (v{p['round']}, digest `{p['digest'][:16]}`)", "",
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
            L.append(f"| {', '.join(f['source_paths'])}{cond} | `{f['target']}` | {steps[:120]} | {f['confidence']} | "
                     f"{r.get('emitted', '?')} / {r.get('source_present', '?')} | {r.get('errors', {}) or ''} | "
                     f"{f['rationale'][:160]} |")
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
    L += ["", "## Decision", "",
          f"Approve: `python -m firmable.cli approve {sid} --reviewer \"<name>\"`  ",
          f"Reject:  `python -m firmable.cli approve {sid} --reviewer \"<name>\" --reject --comment \"why\"`", ""]
    target = out_dir or OUT_REVIEWS
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{sid}.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return str(path)


def _digest(doc: dict) -> str:
    # Recomputed from the config itself, never trusted from the stored field.
    from ..mapping.schema import MappingConfig
    return MappingConfig.model_validate(doc["config"]).digest()


def approve(sid: str, reviewer: str, reviewer_kind: str, reject: bool = False, comment: str = "") -> dict:
    doc = json.loads((OUT_MAPPINGS / f"{sid}.json").read_text(encoding="utf-8"))
    rec = {"source_id": sid, "decision": "rejected" if reject else "approved", "reviewer": reviewer,
           "reviewer_kind": reviewer_kind, "config_digest": _digest(doc), "run_id": doc["run_id"],
           "proposal_status_at_review": doc["status"], "comment": comment,
           "decided_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    with open(OUT_MAPPINGS / f"{sid}.approvals.jsonl", "a", encoding="utf-8") as fh:  # append-only
        fh.write(json.dumps(rec) + "\n")
    return rec


def last_approved_config(sid: str) -> dict | None:
    """The most recently approved config for a source (searching current and superseded proposals by digest)."""
    log = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
    if not log.exists():
        return None
    approved = [json.loads(l)["config_digest"] for l in log.read_text(encoding="utf-8").splitlines()
                if json.loads(l)["decision"] == "approved"]
    if not approved:
        return None
    candidates = [OUT_MAPPINGS / f"{sid}.json"] + sorted((OUT_MAPPINGS / "superseded").glob(f"{sid}.*.json"))
    for p in candidates:
        if p.exists():
            doc = json.loads(p.read_text(encoding="utf-8"))
            if _digest(doc) == approved[-1]:
                return doc["config"]
    return None


def restore_last_approved(sid: str) -> str | None:
    """Make the last approved config current again (the rejected one moves to superseded). Returns its run_id."""
    log = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
    approved = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if json.loads(l)["decision"] == "approved"]
    target = approved[-1]["config_digest"]
    cur = OUT_MAPPINGS / f"{sid}.json"
    for p in sorted((OUT_MAPPINGS / "superseded").glob(f"{sid}.*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if _digest(doc) == target:
            old = json.loads(cur.read_text(encoding="utf-8"))
            cur.rename(OUT_MAPPINGS / "superseded" / f"{sid}.{old['run_id']}.json")
            p.rename(cur)
            return doc["run_id"]
    return None


def current_approval(sid: str) -> dict | None:
    """Latest decision, valid only if it is an approval of the current config digest."""
    p = OUT_MAPPINGS / f"{sid}.approvals.jsonl"
    if not p.exists():
        return None
    doc = json.loads((OUT_MAPPINGS / f"{sid}.json").read_text(encoding="utf-8"))
    last = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])
    if last["decision"] == "approved" and last["config_digest"] == _digest(doc):
        return last
    return None
