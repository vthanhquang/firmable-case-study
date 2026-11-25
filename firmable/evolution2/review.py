"""Evidence-bound review memory. Reusing meaning never approves new source bindings."""
import json
from datetime import datetime, timezone
from pathlib import Path

from ..evolution.schema import digest


def review_items(cfg, ontology, source_schema):
    """One semantic contract plus each distinct executable binding; no auto-verdicts."""
    items = []
    for target in sorted({f.target for f in cfg.fields}):
        spec = ontology["concepts"][target]
        meaning = {k: v for k, v in spec.items() if k not in ("source_paths", "why_not_existing")}
        items.append({"key": "concept:" + target, "kind": "concept", "contract": meaning,
                      "fingerprint": digest(meaning)})
    for field in cfg.fields:
        spec = ontology["concepts"][field.target]
        contract = {"rule": field.model_dump(), "source_schema": source_schema,
                    "concept": {k: v for k, v in spec.items() if k not in ("source_paths", "why_not_existing")},
                    "roles": {k: v.model_dump() for k, v in cfg.entities.items()}}
        key = "binding:" + digest({"target": field.target, "sources": field.source_paths,
                                    "role": field.entity, "source_id": cfg.source_id})
        items.append({"key": key, "kind": "binding", "contract": contract, "fingerprint": digest(contract)})
    for edge in cfg.relationships:
        contract = {"edge": edge.model_dump(), "definition": ontology["relationships"][edge.type],
                    "roles": {k: v.model_dump() for k, v in cfg.entities.items()}, "source_schema": source_schema}
        items.append({"key": "relationship:" + edge.type + ":" + cfg.source_id, "kind": "relationship",
                      "contract": contract, "fingerprint": digest(contract)})
    return items


class ReviewMemory:
    def __init__(self, path):
        self.path = Path(path)

    def decisions(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()] if self.path.exists() else []

    def record(self, item, *, reviewer, decision, evidence_digest, notes="", reviewer_kind="human"):
        """Call only on an explicit reviewer action; this never promotes a registry."""
        if decision not in ("approve", "reject") or reviewer_kind not in ("human", "synthetic_test"):
            raise ValueError("Invalid reviewer decision")
        if not reviewer.strip() or not evidence_digest.strip():
            raise ValueError("Reviewer and evaluated evidence digest are required")
        if digest(item["contract"]) != item["fingerprint"]:
            raise ValueError("Review item changed since display")
        row = {"key": item["key"], "kind": item["kind"], "fingerprint": item["fingerprint"],
               "contract": item["contract"], "decision": decision, "reviewer": reviewer,
               "reviewer_kind": reviewer_kind, "evidence_digest": evidence_digest, "notes": notes,
               "at": datetime.now(timezone.utc).isoformat()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def queue(self, items, *, test_mode=False):
        history = {}
        for row in self.decisions():
            if row["reviewer_kind"] == "human" or test_mode:
                history[row["key"]] = row
        result = []
        for item in items:
            if digest(item["contract"]) != item["fingerprint"]:
                raise ValueError("Invalid review fingerprint")
            previous = history.get(item["key"])
            if previous and previous["fingerprint"] == item["fingerprint"]:
                state = "approved_unchanged" if previous["decision"] == "approve" else "rejected_unchanged"
                changed = []
            else:
                state = "changed_requires_review" if previous else "new_requires_review"
                changed = sorted(k for k in set(item["contract"]) | set(previous["contract"] if previous else {})
                                 if not previous or item["contract"].get(k) != previous["contract"].get(k))
            result.append(item | {"review_state": state, "changed_contract_parts": changed,
                                  "previous_fingerprint": previous["fingerprint"] if previous else None,
                                  "test_only": test_mode})
        return result


def main():
    import argparse
    p = argparse.ArgumentParser(description="Record an explicit human review of one displayed contract; never promotes production")
    p.add_argument("items", type=Path)
    p.add_argument("--memory", type=Path, required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--fingerprint", help="Required when a queue has conflicting variants under the same key")
    p.add_argument("--reviewer", required=True)
    p.add_argument("--decision", choices=["approve", "reject"], required=True)
    p.add_argument("--evidence-digest", required=True)
    p.add_argument("--notes", default="")
    args = p.parse_args()
    matches = [i for i in json.loads(args.items.read_text(encoding="utf-8")) if i["key"] == args.key and (not args.fingerprint or i["fingerprint"] == args.fingerprint)]
    if len(matches) != 1:
        raise ValueError("Select exactly one review contract using key and fingerprint")
    item = matches[0]
    print(json.dumps(ReviewMemory(args.memory).record(item, reviewer=args.reviewer, decision=args.decision,
          evidence_digest=args.evidence_digest, notes=args.notes)))


if __name__ == "__main__":
    main()
