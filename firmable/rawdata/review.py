"""Review pages and human decisions for agent-written EXTENSION mappings.

The page answers what the reviewer is approving: which rules the agent added or changed relative to the
approved mapping, how they behaved on held-out rows, what the critic said, which reviewed crosswalk tables
they rely on (and those tables' own review status), and which columns are still unmapped and why.
Decisions are append-only and bound to the proposal's config digest and snapshot hash. Only a human
reviewer can approve; nothing in this package writes an approval on anyone's behalf.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .. import crosswalk, llm, ontology
from ..mapping.schema import MappingConfig
from ..paths import RUNS
from . import OUT_RD_MAPPINGS, OUT_RD_REVIEWS


def _fmt_steps(steps) -> str:
    out = []
    for s in steps:
        args = s.get("args") or {}
        if s["op"] == "crosswalk":
            out.append(f"crosswalk({args.get('table')}, {args.get('output', 'code')})")
        elif s["op"] in ("flag", "split", "split_regex", "phone_au", "parse_date"):
            out.append(f"{s['op']}({', '.join(f'{k}={v}' for k, v in args.items())})")
        else:
            out.append(s["op"])
    return " -> ".join(out) or "(as is)"


def _cell(v) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def write_extension_report(sid: str, run_id: str, out_dir: Path | None = None) -> str:
    st = json.loads((RUNS / sid / run_id / "state.json").read_text(encoding="utf-8"))
    from ..sources.select import load_manifest
    src = load_manifest()[sid]
    if st.get("local_revision"):
        revision = st["local_revision"]
        proposal = st["proposals"][-1]
        parent = json.loads((RUNS / sid / run_id / "parent_mapping.json").read_text(encoding="utf-8"))
        import difflib
        diff = "\n".join(difflib.unified_diff(
            json.dumps(parent["config"], indent=2, sort_keys=True).splitlines(),
            json.dumps(proposal["config"], indent=2, sort_keys=True).splitlines(),
            fromfile="previous agent proposal", tofile="local corrected proposal", lineterm=""))
        return _write(sid, [f"# Local correction review: `{sid}`", "",
            f"Status: {st['status']}; human sign-off is still required.",
            f"Run: `{run_id}`; config digest: `{proposal['digest']}`.",
            f"Original agent run: `{revision['parent_run_id']}` (preserved).",
            f"Actor: {revision['actor']}. Model calls: 0.", "", revision["reason"], "",
            f"Validation: {revision['validation_scope']}. No new model critic was called.", "",
            "## Regression findings", "", "```json", json.dumps(proposal["holdout_issues"], indent=2), "```", "",
            "## Exact mapping changes", "", "```diff", diff, "```", "",
            "## Interpretation dependencies", "", "```json", json.dumps(revision["dependencies"], indent=2), "```"], out_dir)
    usage = llm.summarize().get((sid, run_id), {})
    base = MappingConfig.model_validate(st["extension_base"])
    L = [f"# Extension mapping review: `{sid}`", "",
         f"- **Status:** {st['status']} - awaiting a human decision (run `{run_id}`, prompt `{st['prompt_version']}`, "
         f"model `{st['model']}`, critic `{st.get('critic_model')}`)",
         f"- **Dataset:** {src['title']} - {src['publisher']}; snapshot sha256 `{st['snapshot_sha256']}`",
         f"- **Extends approved mapping:** run `{st.get('extension_base_run_id')}`, digest "
         f"`{st['extension_base_digest'][:16]}`; registry `ext-v1` (draft concept definitions)",
         f"- **Agent effort:** {len(st['proposals'])} proposal(s), {st['tool_calls']} tool calls, "
         f"{usage.get('calls', 0)} model calls, {usage.get('prompt_tokens', 0):,} prompt + "
         f"{usage.get('completion_tokens', 0):,} completion tokens, {usage.get('latency_ms', 0) / 1000:.0f}s model time", ""]
    if not st["proposals"]:
        L.append("**The agent did not submit a draft.** See events.jsonl.")
        return _write(sid, L, out_dir)
    p = st["proposals"][-1]
    cfg = MappingConfig.model_validate(p["config"])
    L.append(f"- **Proposal digest:** `{p['digest']}` (round {p['round']})")
    if st.get("human_feedback"):
        L.append(f"- **Revision after reviewer feedback** ({st.get('feedback_source') or 'reviewer'}): "
                 f"{_cell(st['human_feedback'])[:600]}")
    for a in st.get("auto_submitted") or []:
        L.append(f"- **Auto-submitted by the controller** (round {a['round']}): {a['reason']}. The draft is the "
                 "agent's own last clean dry run, unchanged; it went through the same gates and critic.")
    if st.get("budget_exhausted"):
        L.append(f"- **Token budget exhausted** in round {st['budget_exhausted']['round']}: the run stopped and kept "
                 "its last evaluated proposal.")
    L.append("")
    findings = st.get("ext_base_findings") or []
    if findings:
        L += ["## Gate failures on the approved mapping (found by today's gates)", ""]
        for i in findings:
            L.append(f"- `{i['code']}` on `{i.get('target')}`: {_cell(i['message'])[:300]}")
        L.append("")
    logs = st.get("ext_change_logs") or []
    last = next((x for x in reversed(logs) if x["round"] == p["round"]), logs[-1] if logs else None)
    L += ["## What changes relative to the approved mapping", ""]
    if last:
        for c in last["changes"]:
            if c["change"] == "added":
                continue
            L.append(f"- {c['change']} rule #{c.get('index')} `{c['target']}`"
                     + (f" -> `{c['new_target']}`" if c.get("new_target") else "")
                     + "".join(f", {k}=`{c[k]}`" for k in ("entity", "claim_scope", "valid_from_path", "valid_to_path")
                               if c.get(k)) + f" - {_cell(c.get('reason', ''))}")
        added = [c for c in last["changes"] if c["change"] == "added"]
        L.append(f"- {len(added)} rule(s) added (table below)")
        for d in last.get("discarded") or []:
            L.append(f"- **discarded by the controller:** {_cell(d)}")
    L.append("")
    if cfg.entities or cfg.relationships:
        L += ["## Record roles and relationships", ""]
        for role, b in (cfg.entities or {}).items():
            L.append(f"- role `{role}`: {b.kind}, key {b.key_paths or '(row-scoped)'} - {_cell(b.rationale)}")
        for r in cfg.relationships or []:
            L.append(f"- `{r.type}`: {r.from_role} -> {r.to_role} - {_cell(r.rationale)}")
        L.append("")
    base_rules = {r.model_dump_json() for r in base.fields}
    hold = {i: f for i, f in enumerate(p.get("holdout_report", {}).get("fields", []))}
    onto = ontology.load(None, "ext-v1")
    L += ["## Added and changed rules", "",
          "| # | target | role | source columns | transform | qualifiers | conf. | held-out present / emitted / errors / dropped | rationale |",
          "|---|---|---|---|---|---|---|---|---|"]
    tables_used = set()
    for i, rule in enumerate(cfg.fields):
        if rule.model_dump_json() in base_rules:
            continue
        d = rule.model_dump()
        tables_used.update(s["args"].get("table") for s in d["steps"] if s["op"] == "crosswalk")
        h = hold.get(i, {})
        quals = ", ".join(f"{k}={q['value'] if q.get('value') is not None else 'col:' + q['source_path']}"
                          for k, q in (d.get("qualifiers") or {}).items())
        when = f" when {rule.when.source_path} {rule.when.op} {rule.when.values}" if rule.when else ""
        when += "".join(f"; {k}={getattr(rule, k)}" for k in ("valid_from_path", "valid_to_path", "claim_scope")
                        if getattr(rule, k))
        L.append(f"| {i} | `{rule.target}` | {rule.entity or 'subject'} | {_cell(', '.join(rule.source_paths))}{_cell(when)} | "
                 f"{_cell(_fmt_steps(d['steps']))} | {_cell(quals)} | {rule.confidence} | "
                 f"{h.get('source_present', '?')} / {h.get('emitted', '?')} / {sum((h.get('errors') or {}).values())} / "
                 f"{sum((h.get('dropped') or {}).values())} | {_cell(rule.rationale)[:160]} |")
    L.append("")
    issues = p.get("holdout_issues") or []
    scoped = [i for i in issues if not i.get("target") or i["target"] in
              {r.target for r in cfg.fields if r.model_dump_json() not in base_rules}]
    L += ["## Held-out validation (rules in this review)", ""]
    L += [f"- **{i['severity']}** `{i['code']}` {('on `' + i['target'] + '`') if i.get('target') else ''}: "
          f"{_cell(i['message'])[:300]}" for i in scoped] or ["- no issues"]
    rel = p.get("holdout_report", {}).get("relationships")
    if rel:
        L.append(f"- relationship edges on held-out rows: {rel}")
    L.append("")
    crit = p.get("critic") or {}
    L += ["## Critic", "", f"> {_cell(crit.get('summary', 'no critic verdict'))}", ""]
    for f in crit.get("fields", []):
        if f["verdict"] != "ok":
            L.append(f"- **{f['verdict']}** `{f.get('target')}` ({', '.join(f.get('source_paths') or [])}): {_cell(f['reason'])}")
    for m in crit.get("missed", []):
        L.append(f"- missed? `{m['source_path']}` -> `{m['suggested_target']}`: {_cell(m['reason'])}")
    L.append("")
    if tables_used - {None}:
        L += ["## Crosswalk tables this mapping relies on", "",
              "Each table is a separate human-reviewed artefact; approving the mapping does not approve the table.", ""]
        for t in sorted(tables_used - {None}):
            table = crosswalk.load(t)
            L.append(f"- `{t}` ({table['kind']}, {table.get('derivation_level', 'L1')}): {table.get('review_status')}")
        L.append("")
    personal = [r.target for r in cfg.fields if r.target in onto.fields and onto.fields[r.target].personal_data != "never"]
    if personal:
        L += ["## Personal data handling", "",
              f"- concepts that can hold personal data: {sorted(set(personal))}. Mobiles are flagged "
              "`privacy: personal`; personal mailboxes are dropped by the transform (counted above).", ""]
    L += ["## Still unmapped", ""] + [f"- `{u.source_path}`: {_cell(u.reason)}" for u in cfg.unmapped] + [""]
    L += ["## Decide", "",
          "```", f"python -m firmable.cli raw-approve {sid} --reviewer \"<your name>\"",
          f"python -m firmable.cli raw-approve {sid} --reviewer \"<your name>\" --reject --comment \"why\"", "```", ""]
    return _write(sid, L, out_dir)


def _write(sid: str, lines: list[str], out_dir) -> str:
    OUT_RD_REVIEWS.mkdir(parents=True, exist_ok=True)
    path = OUT_RD_REVIEWS / f"{sid}.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return str(path)


# ---- decisions --------------------------------------------------------------------------------------
def load_proposal(sid: str) -> dict:
    return json.loads((OUT_RD_MAPPINGS / f"{sid}.json").read_text(encoding="utf-8"))


def decide(sid: str, reviewer: str, reject: bool = False, comment: str = "", reviewer_kind: str = "human") -> dict:
    """Record a decision on the current extension proposal (append-only, digest-bound). Only a named human
    can approve; an AI assistant may only reject with a comment, which sends the proposal back to the agent."""
    if not reviewer.strip():
        raise ValueError("A named reviewer is required")
    if reviewer_kind != "human" and not reject:
        raise ValueError("Only a human reviewer can approve an extension mapping")
    doc = load_proposal(sid)
    from .maintenance import verify_dependencies
    verify_dependencies(doc)
    rec = {"source_id": sid, "decision": "rejected" if reject else "approved", "reviewer": reviewer,
           "reviewer_kind": reviewer_kind, "comment": comment, "run_id": doc["run_id"],
           "config_digest": doc["config_digest"], "snapshot_sha256": doc["snapshot_sha256"],
           "decided_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    if doc.get("local_revision"):
        rec["interpretation_dependencies"] = doc["local_revision"]["dependencies"]
    with open(OUT_RD_MAPPINGS / f"{sid}.approvals.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def approval_state(sid: str) -> str:
    """'approved' only when the latest human decision names the current proposal's digest."""
    doc = load_proposal(sid)
    from .maintenance import verify_dependencies
    verify_dependencies(doc)
    log = OUT_RD_MAPPINGS / f"{sid}.approvals.jsonl"
    if not log.exists():
        return "pending_human_review"
    for line in reversed(log.read_text(encoding="utf-8").splitlines()):
        rec = json.loads(line)
        if rec["config_digest"] == doc["config_digest"] and rec["snapshot_sha256"] == doc["snapshot_sha256"]:
            if doc.get("local_revision") and rec.get("interpretation_dependencies") != doc["local_revision"]["dependencies"]:
                continue
            return rec["decision"]
    return "pending_human_review"
