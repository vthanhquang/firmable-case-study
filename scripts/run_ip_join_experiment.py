"""Model-planned, cardinality-checked joins on a consistent IP RAPID snapshot.

This script supplies source files and a question, never mapping rules or join keys.
"""
import argparse
import csv
import json
from itertools import islice
from pathlib import Path

from firmable.evolution.registry import write
from firmable.evolution.pipeline import jsonlines
from firmable.evolution2.pipeline import Controller, PROMPTS, file_sha
from firmable.evolution2.joins import JoinPlan, materialize


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def run(root, live=False):
    data = Path("data/profile-enrichment/ip-join-new")
    paths = {"party_activity": data / "ip_party_activity_prefix.csv",
             "application": data / "application.csv", "application_description": data / "application_description.csv"}
    profiles = {}
    hashes = {}
    acquisition = json.loads(Path("outputs/experiments/grouped-ontology/ip-inputs/ip-acquisition.json").read_text(encoding="utf-8"))
    for name, path in paths.items():
        examples = list(islice(rows(path), 8))
        profiles[name] = {"columns": list(examples[0]), "examples": examples}
        hashes[name] = file_sha(path)
        if name != "party_activity":
            receipt = json.loads(path.with_suffix(".receipt.json").read_text(encoding="utf-8"))
            if receipt["sha256"] != hashes[name] or receipt["archive_etag"] != acquisition["archive_etag"]:
                raise ValueError("IP tables are from different snapshots or changed on disk")
        elif hashes[name] != acquisition["cohort_sha256"]:
            raise ValueError("Anchor cohort changed")
    headers = {name: profile["columns"] for name, profile in profiles.items()}
    controller = Controller(root, live=live, per_source_budget=100000, total_budget=100000)
    PROMPTS["join_planner"] = (
        "Propose a star equijoin view anchored on party_activity so analysts can see each reported party role "
        "with source-stated application status, dates and descriptions. Infer keys from supplied schemas and values. "
        "Use composite keys when application numbers are scoped by right type. Never equate a party role with "
        "ownership or current enforceability. Only many_to_one/one_to_one star joins are executable. Actual full "
        "right-table cardinality will be checked; duplicates are refused, not selected first. Explain limitations "
        "and unsupported questions; this is a patent-prefix pilot, not a representative sample of all rights."
    )
    feedback = None
    for attempt in range(3):
        plan = controller.agent("join_planner", "ip_join_view", str(attempt),
            {"tables": profiles, "feedback": feedback, "snapshot_hashes": hashes}, JoinPlan)
        try:
            plan.validate_tables(headers)
            break
        except ValueError as exc:
            feedback = {"error": str(exc), "previous_plan": plan.model_dump()}
    else:
        raise ValueError("No valid model-proposed join plan")
    write(root / "join-plan.json", plan.model_dump())
    anchor = list(rows(paths[plan.anchor]))
    print("Scanning full application tables for the anchor cohort", flush=True)
    view, lineage, reports = materialize(plan, anchor,
        {name: (lambda path=path: rows(path)) for name, path in paths.items()}, headers, hashes)
    output = data / "joined_view.csv"
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(view[0])); writer.writeheader(); writer.writerows(view)
    jsonlines(root / "view-lineage.jsonl", lineage)
    write(root / "join-results.json", {"source_fingerprints": hashes, "etag": acquisition["archive_etag"],
        "anchor_rows": len(anchor), "view_rows": len(view), "steps": reports,
        "view_path": str(output), "view_sha256": file_sha(output),
        "semantic_precision": None, "human_review": "pending"})
    original = next(s for s in json.loads(Path("config/profile_enrichment_sources.json").read_text(encoding="utf-8")) if s["source_id"] == "ip_party_activity_new")
    source = original | {"source_id": "ip_joined_view", "title": "IP RAPID role-scoped joined application view (prefix pilot)",
        "local_path": str(output), "snapshot_sha256": file_sha(output), "snapshot_bytes": output.stat().st_size,
        "notes": "One anchor party-activity record per row. Columns are prefixed with the original table name. "
                 "Model-proposed joins were checked on full right tables; missing/ambiguous matches are null. "
                 "Do not infer legal business identity, beneficial ownership or enforceability from party role. "
                 "This is a patent-prefix cohort, not a population sample. Original row/snapshot lineage is in the join experiment. "
                 "Application status, dates and descriptions apply to the application, not to the business.",
        "retrieved_at": acquisition["retrieved_at"],
        "acquisition": {"join_evidence": str(root), "snapshot_etag": acquisition["archive_etag"], "source_fingerprints": hashes}}
    write(root / "sources.json", [source])
    print(json.dumps({"view_rows": len(view), "matches": [r["measurement"]["matched_left_rows"] for r in reports]}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=Path("outputs/experiments/grouped-ontology/ip-joins"))
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    run(args.output, args.live)
