"""python -m firmable.evolution run|replay|promote"""
import argparse
import json
from pathlib import Path

from ..paths import ROOT
from .pipeline import Controller, replay, seal
from .registry import Registry, bootstrap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "replay", "seal", "promote", "check-drift", "resume-source"])
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/experiments/autonomous-ontology/run")
    parser.add_argument("--sources", type=Path, default=ROOT / "config/evolution_sources.json")
    parser.add_argument("--live", action="store_true", help="allow billable configured model calls; omitted means checkpoint-only")
    parser.add_argument("--version")
    parser.add_argument("--reviewer")
    parser.add_argument("--expected-current")
    parser.add_argument("--source-id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--rounds", type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    if args.action == "run":
        sources = json.loads(args.sources.read_text(encoding="utf-8"))
        Controller(args.output, live=args.live).run(sources)
        replay(args.output, ROOT / "outputs/raw-data/observations")
        seal(args.output, ROOT / "outputs/raw-data/observations")
    elif args.action == "resume-source":
        if not args.source_id:
            parser.error("resume-source requires --source-id")
        if (args.output / "registry/production.json").exists() or (args.output / "evidence-manifest.json").exists():
            parser.error("Published or sealed experiments are immutable; start a new output directory")
        controller = Controller(args.output, live=args.live)
        sources = json.loads((args.output / "sources.json").read_text(encoding="utf-8"))
        source = next(s for s in sources if s["source_id"] == args.source_id)
        folder = args.output / args.source_id
        validations = sorted(folder.glob("*-validation.json"), key=lambda p: int(p.name.split("-")[0]))
        if not validations:
            parser.error("No validation checkpoint to resume")
        previous = validations[-1]
        step = int(previous.name.split("-")[0])
        feedback = json.loads(previous.read_text(encoding="utf-8"))
        if "critic" in feedback:
            feedback = {"critic": feedback["critic"], "validation": feedback["heldout"]}
        for role, key in (("architect", "previous_proposal"), ("mapper", "previous_mapping")):
            path = folder / f"{step}-{role}.json"
            if path.exists():
                feedback[key] = json.loads(path.read_text(encoding="utf-8"))["response"]
        pointer = args.output / "registry/candidate.json"
        base = controller.registry.load(json.loads(pointer.read_text())["version"]) if pointer.exists() else bootstrap()
        controller.event("EXPLICIT_SOURCE_RESUME", source_id=args.source_id, start_round=step + 1, allowance=args.rounds)
        controller.run_source(source, base, start_round=step + 1, max_rounds=args.rounds, initial_feedback=feedback)
    elif args.action == "seal":
        seal(args.output, ROOT / "outputs/raw-data/observations")
    elif args.action == "replay":
        views = replay(args.output, ROOT / "outputs/raw-data/observations")
        print(json.dumps({"entities": len(views["entities"]), "proposed_links": len(views["links_to_existing_sample"])}))
    elif args.action == "check-drift":
        from .engine import drift
        from .schema import Inspection
        from ..sources.readers import iter_records
        if not args.source_id or not args.input:
            parser.error("check-drift requires --source-id and --input")
        folder = args.output / args.source_id
        inspection = Inspection.model_validate_json((folder / "inspection.json").read_text(encoding="utf-8"))
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        try:
            records = [{"row": row} for row in iter_records(args.input, inspection.reader)]
            report = drift(result["drift_baseline"], records, inspection)
        except (ValueError, UnicodeError, OSError) as exc:
            report = {"requires_reinspection": True, "reader_error": str(exc)}
        print(json.dumps(report, indent=2))
    else:
        if not args.version or not args.reviewer:
            parser.error("promote requires --version and --reviewer; this records YOUR human approval")
        print(json.dumps(Registry(args.output / "registry").promote(args.version, args.reviewer, args.expected_current)))


if __name__ == "__main__":
    main()
