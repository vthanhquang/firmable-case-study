"""Command line entry point: python -m firmable.cli <command> ...

Pipeline order:
  discover -> select-sources -> onboard -> approve -> extract -> resolve -> profiles -> report
"""
from __future__ import annotations

import argparse
import json
import sys

from .paths import OUT_REVIEWS, ensure_dirs


def cmd_discover(a):
    from .discovery import triage
    print(triage.run(min_pool=a.min_pool, top=a.top))


def cmd_select(a):
    from .sources import select
    select.run()


def cmd_fetch(a):
    from .sources import select
    select.fetch_from_manifest()


def cmd_onboard(a):
    from .agent.onboard import onboard
    from .sources.select import load_manifest
    man = load_manifest()
    ids = list(man) if a.all else a.source_ids
    for sid in ids:
        if sid not in man:
            sys.exit(f"unknown source {sid}; known: {list(man)}")
        if a.all and sid == "asic_credit_licensees" and not (a.include_seventh or a.experiment):
            continue
        print(f"== onboarding {sid}", flush=True)
        if a.resume:
            from .agent.onboard import resume
            st = resume(man[sid], a.resume)
        else:
            st = onboard(man[sid], human_feedback=a.feedback, experiment=a.experiment,
                         only_targets=a.only.split(",") if a.only else None)
        report_dir = OUT_REVIEWS.parent / "experiments" / a.experiment if a.experiment else OUT_REVIEWS
        print(f"   -> {st['status']} after {len(st['proposals'])} proposal(s), {st['tool_calls']} tool calls; "
              f"report: {report_dir / (sid + '.md')}", flush=True)


def cmd_review(a):
    print((OUT_REVIEWS / f"{a.source_id}.md").read_text(encoding="utf-8"))
    if a.interactive:
        ans = input("approve / reject / skip? ").strip().lower()
        if ans in ("approve", "reject"):
            name = input("reviewer name: ").strip()
            comment = input("comment: ").strip()
            from .agent.review import approve
            print(approve(a.source_id, name, "human", reject=ans == "reject", comment=comment))


def cmd_approve(a):
    from .agent.review import approve
    print(json.dumps(approve(a.source_id, a.reviewer, a.reviewer_kind, reject=a.reject, comment=a.comment), indent=2))


def cmd_restore(a):
    from .agent.review import restore_last_approved
    rid = restore_last_approved(a.source_id)
    print(f"restored run {rid}; it needs a fresh approval: python -m firmable.cli approve {a.source_id} --reviewer <name>"
          if rid else "nothing to restore (no superseded config matches the last approval)")


def cmd_revalidate(a):
    from .revalidate import run
    out = run()
    if any(v["errors"] for v in out.values()):
        sys.exit(1)


def cmd_fullcheck(a):
    from . import fullcheck
    if a.parallel:
        print(json.dumps(fullcheck.parallel_stats(a.source_id, workers=a.parallel), indent=1))
    elif a.source_id:
        print(json.dumps(fullcheck.run(a.source_id, a.snapshot), indent=1))
    else:
        fullcheck.all_sources()


def cmd_stability(a):
    from .agent.stability import compare
    print(json.dumps({k: v for k, v in compare(a.experiment, a.baseline).items() if k != "per_source"}, indent=1))


def cmd_extract(a):
    from .extract import run_all
    run_all(sample_size=a.sample_size, sources=a.source_ids or None)


def cmd_resolve(a):
    from .identity import resolve
    print(json.dumps(resolve.run(), indent=2))


def cmd_compare(a):
    from .identity import compare
    print(json.dumps(compare.run(a.challenger), indent=2))


def cmd_profiles(a):
    from .profiles import build
    print(json.dumps(build.run(count=a.count), indent=2))


def cmd_report(a):
    from .report import run
    print(run())


def main(argv=None):
    ensure_dirs()
    p = argparse.ArgumentParser(prog="firmable")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("discover"); s.add_argument("--min-pool", type=int, default=200); s.add_argument("--top", type=int, default=50); s.set_defaults(fn=cmd_discover)
    s = sub.add_parser("select-sources"); s.set_defaults(fn=cmd_select)
    s = sub.add_parser("fetch", help="re-download the committed manifest's resources, verify sha256"); s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("onboard"); s.add_argument("source_ids", nargs="*"); s.add_argument("--all", action="store_true")
    s.add_argument("--include-seventh", action="store_true")
    s.add_argument("--feedback", default=None, help="reviewer's rejection reason; the agent revises the previous proposal")
    s.add_argument("--resume", default=None, metavar="RUN_ID", help="continue an interrupted run from its last checkpoint")
    s.add_argument("--experiment", default=None, help="write proposals to outputs/experiments/<name>/, never touching approved configs")
    s.add_argument("--only", default=None, help="comma-separated targets the revision may change; everything else is "
                                                 "kept from the last approved config by the controller")
    s.set_defaults(fn=cmd_onboard)
    s = sub.add_parser("review"); s.add_argument("source_id"); s.add_argument("--interactive", action="store_true"); s.set_defaults(fn=cmd_review)
    s = sub.add_parser("approve"); s.add_argument("source_id"); s.add_argument("--reviewer", required=True)
    s.add_argument("--reviewer-kind", default="human"); s.add_argument("--reject", action="store_true")
    s.add_argument("--comment", default=""); s.set_defaults(fn=cmd_approve)
    s = sub.add_parser("restore-approved", help="make the last approved config current again (after a bad revision)")
    s.add_argument("source_id"); s.set_defaults(fn=cmd_restore)
    s = sub.add_parser("revalidate", help="current deterministic gates over every approved config; exit 1 on any error")
    s.set_defaults(fn=cmd_revalidate)
    s = sub.add_parser("fullcheck", help="approved config(s) over whole resources; --parallel N for partitioned stats")
    s.add_argument("source_id", nargs="?"); s.add_argument("--snapshot", default=None)
    s.add_argument("--parallel", type=int, default=0); s.set_defaults(fn=cmd_fullcheck)
    s = sub.add_parser("stability", help="agreement of an experiment re-run with approved configs (or --baseline)")
    s.add_argument("experiment"); s.add_argument("--baseline", default=None); s.set_defaults(fn=cmd_stability)
    s = sub.add_parser("extract"); s.add_argument("source_ids", nargs="*"); s.add_argument("--sample-size", type=int, default=1000); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("resolve"); s.set_defaults(fn=cmd_resolve)
    s = sub.add_parser("compare-matchers"); s.add_argument("--challenger", default="strict-v2"); s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("profiles"); s.add_argument("--count", type=int, default=50); s.set_defaults(fn=cmd_profiles)
    s = sub.add_parser("report"); s.set_defaults(fn=cmd_report)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
