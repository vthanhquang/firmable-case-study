"""Command line entry point: python -m firmable.cli <command> ...

Pipeline order:
  discover -> select-sources -> onboard -> approve -> extract -> resolve -> profiles -> report
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .paths import OUT, OUT_REVIEWS, ensure_dirs


def cmd_discover(a):
    from .discovery import triage
    print(triage.run(min_pool=a.min_pool, top=a.top))


def cmd_select(a):
    from .sources import select
    select.run()


def cmd_register(a):
    from .sources.register import register

    try:
        source = register(a.source_id, a.file, title=a.title, publisher=a.publisher, licence=a.licence)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    print(json.dumps(source, indent=2))


def cmd_fetch(a):
    from .sources import select
    select.fetch_from_manifest()


def cmd_onboard(a):
    from .agent.onboard import onboard
    from .extract import verify_snapshot
    from .sources.select import load_manifest
    man = load_manifest()
    if a.profile_context_base and (not a.experiment or a.only or a.feedback or a.resume):
        sys.exit("--profile-context-base requires --experiment and starts a new additive run")
    evidence = json.loads(a.publisher_evidence.read_text(encoding="utf-8")) if a.publisher_evidence else {}
    ids = list(man) if a.all else a.source_ids
    for sid in ids:
        if sid not in man:
            sys.exit(f"unknown source {sid}; known: {list(man)}")
        if a.all and sid == "asic_credit_licensees" and not (a.include_seventh or a.experiment):
            continue
        source = man[sid]
        if sid in evidence:
            source = source | {"publisher_evidence": evidence[sid]}
        if a.profile_context_base:
            from .mapping.schema import MappingConfig
            base = json.loads((a.profile_context_base / f"{sid}.json").read_text(encoding="utf-8"))
            config = MappingConfig.model_validate(base["config"])
            if (config.source_id != sid or config.profile_context or config.digest() != base["config_digest"] or
                    base["snapshot_sha256"] != source["snapshot"]["sha256"]):
                sys.exit(f"{sid}: context base must match this source and snapshot")
            source = source | {"profile_context_base": config.model_dump()}
        verify_snapshot(source)
        print(f"== onboarding {sid}", flush=True)
        try:
            if a.resume:
                from .agent.onboard import resume
                st = resume(source, a.resume)
            else:
                st = onboard(source, human_feedback=a.feedback, experiment=a.experiment,
                             only_targets=a.only.split(",") if a.only else None)
        except ValueError as exc:
            sys.exit(str(exc))
        report_dir = OUT_REVIEWS.parent / "experiments" / a.experiment if a.experiment else OUT_REVIEWS
        print(f"   -> {st['status']} after {len(st['proposals'])} proposal(s), {st['tool_calls']} tool calls; "
              f"report: {report_dir / (sid + '.md')}", flush=True)


def cmd_review(a):
    from .agent.review import approve, current_report

    if not a.interactive:
        print((OUT_REVIEWS / f"{a.source_id}.md").read_text(encoding="utf-8"))
        return
    try:
        report, expected = current_report(a.source_id)
        started = time.perf_counter()
        print(report)
        ans = input("approve / reject / skip? ").strip().lower()
        if ans in ("approve", "reject"):
            name = input("reviewer name: ").strip()
            comment = input("comment: ").strip()
            print(approve(a.source_id, name, "human", reject=ans == "reject", comment=comment, expected=expected,
                          review_minutes=round((time.perf_counter() - started) / 60, 2)))
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))


def cmd_approve(a):
    from .agent.review import approve
    try:
        print(json.dumps(approve(a.source_id, a.reviewer, a.reviewer_kind, reject=a.reject, comment=a.comment,
                                 review_minutes=a.minutes), indent=2))
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))


def cmd_review_import(a):
    from .report import run
    from .review_workbook import import_reviews

    try:
        result = import_reviews(a.file, dry_run=a.dry_run)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
    if not a.dry_run:
        run()
    print(json.dumps(result, indent=2))


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
    run_all(sample_size=a.sample_size, sources=a.source_ids or None, allow_proxy_approvals=a.allow_proxy_approvals)


def cmd_resolve(a):
    from .identity import resolve
    options = {"policy": a.policy} if a.policy else {}
    if a.experiment:
        options["output"] = OUT / "experiments" / a.experiment / "identity"
    print(json.dumps(resolve.run(**options), indent=2))


def cmd_audit_links(a):
    from .identity.audit import build_active

    print(json.dumps(build_active(), indent=2))


def cmd_compare(a):
    from .identity import compare
    from .identity.resolve import POLICY_VERSION
    print(json.dumps(compare.run(a.challenger or POLICY_VERSION, a.baseline), indent=2))


def cmd_profiles(a):
    from .profiles import build
    options = {"policy": a.policy, "version": a.version} if a.policy or a.version != build.PROFILE_VERSION else {}
    if a.experiment:
        experiment = OUT / "experiments" / a.experiment
        options.update(output=experiment / "profiles", evaluation=experiment / "evaluation")
    print(json.dumps(build.run(count=a.count, **options), indent=2))


def cmd_report(a):
    from .report import run
    print(run())


def main(argv=None):
    ensure_dirs()
    p = argparse.ArgumentParser(prog="firmable")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("discover"); s.add_argument("--min-pool", type=int, default=200); s.add_argument("--top", type=int, default=50); s.set_defaults(fn=cmd_discover)
    s = sub.add_parser("select-sources"); s.set_defaults(fn=cmd_select)
    s = sub.add_parser("register-source", help="snapshot a local resource for onboarding without code changes")
    s.add_argument("source_id")
    s.add_argument("file", type=Path)
    s.add_argument("--title", required=True)
    s.add_argument("--publisher", required=True)
    s.add_argument("--licence", default="unknown")
    s.set_defaults(fn=cmd_register)
    s = sub.add_parser("fetch", help="re-download the committed manifest's resources, verify sha256"); s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("onboard"); s.add_argument("source_ids", nargs="*"); s.add_argument("--all", action="store_true")
    s.add_argument("--include-seventh", action="store_true")
    s.add_argument("--feedback", default=None, help="reviewer's rejection reason; the agent revises the previous proposal")
    s.add_argument("--resume", default=None, metavar="RUN_ID", help="continue an interrupted run from its last checkpoint")
    s.add_argument("--experiment", default=None, help="write proposals to outputs/experiments/<name>/, never touching approved configs")
    s.add_argument("--publisher-evidence", type=Path, help="JSON object keyed by source ID with publisher documentation")
    s.add_argument("--profile-context-base", type=Path, help="directory of frozen canonical mappings to extend")
    s.add_argument("--only", default=None, help="comma-separated targets the revision may change; everything else is "
                                                 "kept from the last approved config by the controller")
    s.set_defaults(fn=cmd_onboard)
    s = sub.add_parser("review"); s.add_argument("source_id"); s.add_argument("--interactive", action="store_true"); s.set_defaults(fn=cmd_review)
    s = sub.add_parser("review-import", help="record decisions from the human review workbook")
    s.add_argument("file", type=Path)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_review_import)
    s = sub.add_parser("approve"); s.add_argument("source_id"); s.add_argument("--reviewer", required=True)
    s.add_argument("--reviewer-kind", default="human"); s.add_argument("--reject", action="store_true")
    s.add_argument("--minutes", type=float, help="elapsed reviewer minutes")
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
    s.add_argument("--allow-proxy-approvals", action="store_true", help="replay the historical AI-proxy benchmark approvals")
    from .identity.resolve import POLICIES
    from .profiles.build import PROFILE_VERSION, PROFILE_VERSIONS

    s = sub.add_parser("resolve")
    s.add_argument("--policy", choices=POLICIES)
    s.add_argument("--experiment", help="write identity outputs under outputs/experiments/<name>/")
    s.set_defaults(fn=cmd_resolve)
    s = sub.add_parser("audit-links", help="sample proposed strict-v2 links for independent review"); s.set_defaults(fn=cmd_audit_links)
    s = sub.add_parser("compare-matchers"); s.add_argument("--baseline", default="strict-v1"); s.add_argument("--challenger"); s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("profiles")
    s.add_argument("--count", type=int, default=50)
    s.add_argument("--policy", choices=POLICIES)
    s.add_argument("--version", choices=PROFILE_VERSIONS, default=PROFILE_VERSION)
    s.add_argument("--experiment", help="write profiles and replay results under outputs/experiments/<name>/")
    s.set_defaults(fn=cmd_profiles)
    s = sub.add_parser("report"); s.set_defaults(fn=cmd_report)
    from .rawdata.cli import register as register_rawdata
    register_rawdata(sub)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
