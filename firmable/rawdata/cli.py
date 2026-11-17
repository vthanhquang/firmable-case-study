"""CLI commands for the raw-data extension pipeline (python -m firmable.cli raw-...)."""
from __future__ import annotations

import json
import sys


def cmd_raw_onboard(a):
    from ..agent.onboard import onboard_extension
    from ..agent.review import current_approval
    from ..extract import load_config, verify_snapshot
    from ..sources.select import load_manifest
    from . import OUT_RD_MAPPINGS
    man = load_manifest()
    for sid in a.source_ids or [s for s in man if s != "qld_suitable_operators"]:
        if sid not in man:
            sys.exit(f"unknown source {sid}")
        verify_snapshot(man[sid])
        _, doc = load_config(sid)
        approval = current_approval(sid, doc)
        if not approval and not a.base_pending:
            sys.exit(f"{sid}: the current mapping has no approval to extend (use --base-pending for a new source "
                     "whose base mapping still awaits review; the result is labelled accordingly)")
        approval = approval or {"reviewer_kind": "none - base mapping pending review"}
        previous = None
        if a.feedback:
            from .review import decide, load_proposal
            previous = load_proposal(sid)
            # The rejection is recorded against the proposal it concerns, with who wrote the feedback.
            decide(sid, a.reviewer or "", reject=True, comment=a.feedback,
                   reviewer_kind=a.reviewer_kind)
        st = onboard_extension(man[sid], doc, OUT_RD_MAPPINGS, feedback=a.feedback,
                               feedback_source=a.feedback_source, previous=previous)
        print(json.dumps({"source_id": sid, "status": st["status"], "run_id": st["run_id"],
                          "proposals": len(st["proposals"]), "tool_calls": st["tool_calls"],
                          "base_reviewer_kind": approval["reviewer_kind"]}), flush=True)


def cmd_raw_approve(a):
    from .review import decide
    print(json.dumps(decide(a.source_id, a.reviewer, a.reject, a.comment or "")))


def cmd_raw_store(a):
    from .store import build_all
    print(json.dumps(build_all(a.source_ids or None, full=a.full), indent=1))


def cmd_raw_extract(a):
    from .extract import run
    print(json.dumps(run(a.source_ids or None), indent=1))


def cmd_raw_resolve(a):
    from .match import run
    print(json.dumps(run(), indent=1))


def cmd_raw_profiles(a):
    from .profiles import run
    print(json.dumps(run(), indent=1))


def cmd_raw_changes(a):
    from .changes import run
    print(json.dumps(run(), indent=1))


def cmd_raw_metrics(a):
    from .metrics import run
    print(json.dumps(run(), indent=1))


def cmd_raw_all(a):
    for fn in (cmd_raw_store, cmd_raw_extract, cmd_raw_resolve, cmd_raw_profiles, cmd_raw_changes, cmd_raw_metrics):
        fn(a)


def register(sub):
    s = sub.add_parser("raw-revise-local", help="validate and record an explicit maintainer correction bundle; no model calls")
    s.add_argument("bundle")
    def revise_local(a):
        from pathlib import Path
        from .maintenance import apply_bundle
        print(json.dumps(apply_bundle(Path(a.bundle)), indent=2))
    s.set_defaults(fn=revise_local)
    s = sub.add_parser("raw-replay", help="replay the frozen raw sample through profiles and metrics with model access disabled")
    s.add_argument("--sync-demo", action="store_true")
    def replay_local(a):
        from .maintenance import replay
        print(json.dumps(replay(a.sync_demo), indent=2))
    s.set_defaults(fn=replay_local)
    s = sub.add_parser("raw-onboard", help="agent extends approved mappings with ext-v1 concepts (needs a model key)")
    s.add_argument("source_ids", nargs="*")
    s.add_argument("--feedback", help="reject the current extension proposal with this comment; the agent revises")
    s.add_argument("--reviewer", help="who wrote the feedback")
    s.add_argument("--reviewer-kind", default="human", choices=["human", "ai_assistant_proxy"],
                   help="recorded with the rejection; ai_assistant_proxy rejections never count as approvals")
    s.add_argument("--feedback-source", help="where the feedback comes from (document and section)")
    s.add_argument("--base-pending", action="store_true", help="extend a base mapping that awaits review")
    s.set_defaults(fn=cmd_raw_onboard)
    s = sub.add_parser("raw-approve", help="record a HUMAN decision on an extension mapping")
    s.add_argument("source_id"); s.add_argument("--reviewer", required=True)
    s.add_argument("--reject", action="store_true"); s.add_argument("--comment"); s.set_defaults(fn=cmd_raw_approve)
    for name, fn, helptext in (("raw-store", cmd_raw_store, "raw row store for the sampled rows (no model)"),
                               ("raw-extract", cmd_raw_extract, "extension observations + edges (no model)"),
                               ("raw-resolve", cmd_raw_resolve, "challenger matcher with the new evidence"),
                               ("raw-profiles", cmd_raw_profiles, "profile-v3 with firmographics"),
                               ("raw-changes", cmd_raw_changes, "change-signal event table"),
                               ("raw-metrics", cmd_raw_metrics, "phase measurements"),
                               ("raw-all", cmd_raw_all, "store -> extract -> resolve -> profiles -> changes -> metrics")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("source_ids", nargs="*")
        s.add_argument("--full", action="store_true", help="raw-store: keep every row, not only sampled rows")
        s.set_defaults(fn=fn)
