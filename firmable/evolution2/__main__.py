import argparse
import json
from pathlib import Path

from .pipeline import Controller, replay, seal


def main():
    p = argparse.ArgumentParser(description="Experimental grouped ontology onboarding")
    p.add_argument("action", choices=["run", "replay", "seal"])
    p.add_argument("--sources", type=Path, default=Path("config/profile_enrichment_sources.json"))
    p.add_argument("--output", type=Path, default=Path("outputs/experiments/grouped-ontology/run"))
    p.add_argument("--live", action="store_true")
    p.add_argument("--independent-sources", action="store_true", help="Use the same starting ontology for paired source comparisons")
    p.add_argument("--source-budget", type=int, default=350000)
    p.add_argument("--total-budget", type=int, default=1200000)
    p.add_argument("--resume-from", type=Path)
    p.add_argument("--review-memory", type=Path)
    args = p.parse_args()
    if args.action == "run":
        Controller(args.output, live=args.live, per_source_budget=args.source_budget, total_budget=args.total_budget, resume_from=args.resume_from, review_memory=args.review_memory).run(
            json.loads(args.sources.read_text(encoding="utf-8")), independent_sources=args.independent_sources)
        print(json.dumps(seal(args.output)))
    else:
        print(json.dumps(seal(args.output) if args.action == "seal" else replay(args.output)))


if __name__ == "__main__":
    main()
