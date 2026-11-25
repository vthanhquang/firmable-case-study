"""Build a compact, read-only onboarding replay from recorded experiment evidence.

No model calls, new mappings, approvals or production writes. The standalone HTML
and the existing demo tab consume the same JSON and renderer.
"""
import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/experiments/grouped-ontology"
CASES = [
    ("ip", "IP Australia", "Roles, application status and multi-table joins", "ip_joined_view", "ip-joined-run", "ip-joined-recovery"),
    ("acnc", "ACNC charities", "Charity reporting, activities and missing financial context", "acnc_ais2024_new", "run", "recovery"),
    ("wgea", "WGEA employers", "Workforce reporting, repeated headers and mapping revisions", "wgea_employers_new", "run", "recovery"),
]


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def jsonlines(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def safe_row(row):
    """Withhold natural-person IP names and direct contact data from the demo."""
    kind = row.get("party_activity.party_type", row.get("party_type"))
    return {k: ("[withheld in demo]" if (kind not in (None, "organisation") and "party_name" in k)
            or any(token in k.lower() for token in ("email", "phone", "contact name")) else v) for k, v in row.items()}


def mapping_diff(previous, current):
    def index(value):
        return {json.dumps([f["source_paths"], f["target"]]): f for f in (value or {}).get("fields", [])}
    before, after = index(previous), index(current)
    out = []
    for key in sorted(before.keys() | after.keys()):
        a, b = before.get(key), after.get(key)
        if a == b:
            continue
        changed = [k for k in (a or {}).keys() | (b or {}).keys() if (a or {}).get(k) != (b or {}).get(k)]
        rule = b or a
        out.append({"target": rule["target"], "source_paths": rule["source_paths"],
                    "kind": "added" if a is None else "removed" if b is None else "changed",
                    "changes": {k: {"before": (a or {}).get(k), "after": (b or {}).get(k)} for k in sorted(changed)}})
    return out


def history(first, last, sid, plan):
    ledger = {name: list(jsonlines(EXP / name / "usage.jsonl")) for name in (first, last)}
    groups = []
    for group in plan["groups"]:
        attempts, previous = [], None
        for run in (first, last):
            folder = EXP / run / sid
            for number in range(3):
                step = f'{group["name"]}-{number}'
                paths = {role: folder / f"{step}-{role}.json" for role in ("group_architect", "group_mapper", "group_critic")}
                saved = {role: read(path) for role, path in paths.items() if path.exists()}
                validation = read(folder / f"{step}-validation.json", {})
                if not saved and not validation:
                    continue
                mapper = saved.get("group_mapper", {}).get("response")
                critic = saved.get("group_critic", {}).get("response", validation.get("critic"))
                usage = [r for r in ledger[run] if r["source_id"] == sid and r["run_id"] == step]
                invalid = [read(p).get("schema_error", "Schema rejected") for p in folder.glob(f"{step}-*-invalid-*.json")]
                attempts.append({"id": f"{run}:{step}", "pass": "First pass" if run == first else "Recovery",
                    "attempt": number + 1, "roles": list(saved), "critic": critic,
                    "quality": validation.get("quality"), "findings": validation.get("findings", []),
                    "error": validation.get("error"), "schema_errors": invalid,
                    "mapping": mapper, "diff": mapping_diff(previous, mapper) if mapper and previous else [],
                    "has_previous_mapping": bool(previous),
                    "input_tokens": sum(r.get("prompt_tokens", 0) for r in usage),
                    "output_tokens": sum(r.get("completion_tokens", 0) for r in usage),
                    "calls": len(usage), "evidence": [p.relative_to(ROOT).as_posix() for p in paths.values() if p.exists()]})
                if mapper:
                    previous = mapper
        groups.append({**group, "attempts": attempts})
    return groups


def source_case(case, evaluation, profiles):
    key, name, subtitle, sid, first, last = case
    root, folder = EXP / last, EXP / last / sid
    source = next(s for s in read(root / "sources.json") if s["source_id"] == sid)
    result = read(folder / "result.json")
    plan, mapping = read(folder / "group-plan.json"), read(folder / "mapping.json")
    ontology = read(root / "registry/versions" / (result["ontology_version"] + ".json"))
    base = read(root / "registry/versions" / (result["parent_version"] + ".json"))
    proposal = read(folder / "ontology-proposal.json")
    inspection = read(folder / "inspection.json")
    with gzip.open(folder / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream]
    obs = list(jsonlines(folder / "observations.jsonl"))
    edges = list(jsonlines(folder / "relationships.jsonl"))
    by_record = defaultdict(list)
    for o in obs:
        by_record[o["source_record_id"]].append(o)
    profile_index = {str(p["fields"]["entity.abn"]["value"]): p for p in profiles if p.get("fields", {}).get("entity.abn")}
    ordered = []
    for r in records:
        row = r["row"]
        abn = str(row.get("abn") or row.get("Employer ABN") or row.get("party_activity.abn") or "").replace(" ", "")
        matched = profile_index.get(abn)
        claims = [o for o in by_record[r["record_id"]] if o.get("privacy") != "personal"]
        if not claims:
            continue
        label = row.get("charity name") or row.get("Employer name")
        if not label and row.get("party_activity.party_type") == "organisation":
            label = row.get("party_activity.party_name")
        ordered.append({"record_id": r["record_id"], "ordinal": r["ordinal"], "partition": r["partition"],
            "label": label or f'Source record {r["ordinal"]}', "source_row": safe_row(row),
            "existing_profile": {"id": matched["entity_key"], "name": matched["fields"]["entity.legal_name"]["value"],
                "fields": {k: v.get("value") for k, v in matched["fields"].items() if k in ("entity.legal_name", "entity.abn", "entity.status")}} if matched else None,
            "claims": [{k: o.get(k) for k in ("observation_id", "field", "value", "raw_value", "source_fields", "entity_role", "entity_kind", "entity_ref", "qualifiers", "valid_from", "valid_to", "confidence", "source_row_ordinal", "snapshot_sha256", "source_record_id", "review_state", "canonical_definition")} for o in claims],
            "suppressed_claims": len(by_record[r["record_id"]]) - len(claims)})
    ordered.sort(key=lambda r: (not bool(r["existing_profile"]), -len(r["claims"]), r["ordinal"]))
    examples = ordered[:6]
    join = None
    if key == "ip":
        join = read(EXP / "ip-joins/join-results.json")
        join["steps"] = [{"step": s["step"], "measurement": {k: v for k, v in s["measurement"].items() if k != "refusals"}} for s in join["steps"]]
        wanted = {r["record_id"] for r in examples}
        for line in jsonlines(EXP / "ip-joins/view-lineage.jsonl"):
            if line["view_record_id"] in wanted:
                next(e for e in examples if e["record_id"] == line["view_record_id"])["join_lineage"] = line["sources"]
    metrics = evaluation["joined_source"] if key == "ip" else next(r["recovery"] for r in evaluation["paired_sources"] if r["recovery"]["source_id"] == sid)
    calls = [r for run in (first, last) for r in jsonlines(EXP / run / "usage.jsonl") if r["source_id"] == sid]
    used = {f["target"] for f in mapping["fields"]}
    concepts = [{**c, "state": "proposed", "used": c["path"] in used} for c in proposal["concepts"]]
    concepts += [{**base["concepts"][path], "state": "reused", "used": True} for path in sorted(used & base["concepts"].keys())]
    available = [{**base["concepts"][path], "state": "existing", "used": False} for path in ("entity.abn", "entity.legal_name") if path not in used]
    if key == "acnc":
        takeaway = "The grouped run preserves accepted work, but four financial groups remain unfinished. The original mapping with corrected abstention accounting recovers more information without a new model call."
    elif key == "wgea":
        takeaway = "The earlier whole-source mapping retains more observations at lower cost. Grouping exposes useful revision evidence, but is not the stronger result for this source."
    else:
        takeaway = "The joins are complete for this prefix cohort. Application-status mapping recovers during revision; description mapping and a verified business connection remain unresolved."
    return {"key": key, "name": name, "subtitle": subtitle, "takeaway": takeaway, "source_id": sid,
        "source": {k: source.get(k) for k in ("title", "publisher", "url", "documentation_url", "licence", "licence_detail", "retrieved_at", "snapshot_sha256", "snapshot_bytes", "notes")},
        "run": {"first": first, "latest": last, "status": result["status"], "model": calls[0]["model"] if calls else None,
            "input_tokens": sum(c.get("prompt_tokens", 0) for c in calls), "output_tokens": sum(c.get("completion_tokens", 0) for c in calls),
            "calls": len(calls), "recorded_from": min((c["ts"] for c in calls), default=None), "recorded_to": max((c["ts"] for c in calls), default=None)},
        "metrics": metrics, "sampling": read(folder / "sampling.json"), "inspection": inspection,
        "headers": read(folder / "header-contract.json"),
        "preview": [{"ordinal": r["ordinal"], "partition": r["partition"], "row": safe_row(r["row"])} for r in records[:50]],
        "plan": plan, "groups": result["groups"], "history": history(first, last, sid, plan),
        "concepts": concepts, "available_concepts": available, "base_concept_count": len(base["concepts"]),
        "mapping": mapping, "quality": result["quality"], "test_quality": result["test_quality"],
        "test_fields": result["test"]["fields"], "review_queue": read(folder / "review-queue.json"),
        "questions": [q for q in evaluation["questions"] if q["source_id"] == sid],
        "join": join, "examples": examples, "self_edges": sum(e["from_ref"] == e["to_ref"] for e in edges),
        "evidence": {"result": (folder / "result.json").relative_to(ROOT).as_posix(),
            "mapping": (folder / "mapping.json").relative_to(ROOT).as_posix(), "ontology_version": result["ontology_version"],
            "manifest_sha256": hashlib.sha256((root / "evidence-manifest.json").read_bytes()).hexdigest()},
        "human_verification": {"status": "Not measured", "production_merged": 0,
            "note": "Recorded candidates await human review. Neither agent acceptance nor technical validation is a human verdict."}}


def main():
    evaluation = read(EXP / "evaluation.json")
    profiles = read(ROOT / "frontend/data/raw-profiles.json")["profiles"]
    data = {"version": 1, "mode": "Recorded execution", "sources": [source_case(c, evaluation, profiles) for c in CASES],
        "comparison": [{"name": r["name"], "baseline_observations": r["baseline"]["accepted_observations"],
            "new_observations": r["recovery"]["observations"],
            "baseline_tokens": r["baseline"]["input_tokens"] + r["baseline"]["output_tokens"],
            "new_tokens": r["recovery"]["cumulative_input_tokens"] + r["recovery"]["cumulative_output_tokens"]} for r in evaluation["paired_sources"]],
        "ablation": evaluation["controller_only_ablation"], "review_simulation": evaluation["review_simulation"],
        "scope": "Recorded engineering experiments on known development sources. No live API calls, new approvals or production merges occur in this replay."}
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    target = ROOT / "frontend/data/onboarding.json"
    target.write_text(payload + "\n", encoding="utf-8")
    css = (ROOT / "frontend/public/style.css").read_text(encoding="utf-8") + "\n" + (ROOT / "frontend/public/onboarding.css").read_text(encoding="utf-8")
    # One renderer for both pages; all source strings enter the DOM as text nodes.
    js = (ROOT / "frontend/public/onboarding.js").read_text(encoding="utf-8").replace("export function mountOnboarding", "function mountOnboarding")
    embedded = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    css = css.replace('url("/inter.woff2")', 'local("Inter")')
    page = '''<!doctype html><html lang="en" data-type="software"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="page-type" content="software"><meta name="site-kind" content="software"><meta name="description" content="Replay recorded dataset onboarding, ontology changes, revisions and human-review requirements."><title>Dataset onboarding · Firmable</title><style>''' + css + '''</style></head><body>
<a class="skip-link" href="#main">Skip to content</a><header class="site-header"><div class="wrap masthead"><a class="brand" href="#main"><strong>Firmable</strong><span class="brand-context">Dataset onboarding</span></a><span class="ob-offline-label">Self-contained evidence replay</span></div></header>
<main class="wrap" id="main" tabindex="-1"><div id="onboarding"></div></main><footer class="wrap footer">Recorded experiments · No API key or connection required · Candidate evidence, not production changes</footer>
<script id="onboarding-data" type="application/json">''' + embedded + '''</script><script>''' + js.replace("</script", "<\\/script") + '''
mountOnboarding(JSON.parse(document.getElementById('onboarding-data').textContent), document.getElementById('onboarding'), {standalone:true});
</script></body></html>'''
    (ROOT / "reports/dataset-onboarding.html").write_text(page, encoding="utf-8")
    print(f"Built onboarding replay: {len(data['sources'])} datasets, {len(payload):,} JSON characters; standalone HTML and demo share one renderer.")


if __name__ == "__main__":
    main()
