"""Offline comparison and human-review inventory for the grouped experiment."""
import copy
import csv
import gzip
import json
import tempfile
from collections import Counter
from pathlib import Path

from firmable.evolution.registry import Registry, write, bootstrap, propose
from firmable.evolution.schema import DynamicMapping, Inspection, Proposal, digest
from firmable.evolution.engine import extract, bind, validate_mapping
from firmable.evolution2.pipeline import ledger_rows, replay
from firmable.evolution2.quality import quality
from firmable.evolution2.review import ReviewMemory, review_items
from firmable.evolution2.questions import Question, evaluate_question, company_connected
from scripts.report_profile_enrichment import md_table

EXP = Path("outputs/experiments/grouped-ontology")
OLD = Path("outputs/experiments/profile-enrichment")
CASES = [("ACNC", "acnc_ais2024_new", "run"), ("WGEA", "wgea_employers_new", "wgea-retest"), ("IP party", "ip_party_activity_new", "ip-pilot")]


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def sample(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def usage(root, sid):
    rows = [r for r in ledger_rows(root / "usage.jsonl") if r["source_id"] == sid]
    return {"calls": len(rows), "input_tokens": sum(r.get("prompt_tokens", 0) for r in rows),
            "output_tokens": sum(r.get("completion_tokens", 0) for r in rows),
            "failed_requests": sum("error" in r for r in rows)}


def measure(root, sid):
    folder = root / sid
    result = read(folder / "result.json")
    if result is None:
        raise ValueError("Run is not finished: " + str(folder))
    mapping = read(folder / "mapping.json", {"fields": []})
    obs = lines(folder / "observations.jsonl")
    edges = lines(folder / "relationships.jsonl")
    connected = company_connected(obs, edges)
    groups = result.get("groups", [])
    return {"run": str(root), "source_id": sid, "status": result["status"],
        "groups": len(groups), "accepted_groups": sum(g["status"] == "AGENT_VALIDATED" for g in groups),
        "reused_groups": sum(bool(g.get("reused_from")) for g in groups),
        "rules": len(mapping["fields"]), "value_columns": len({p for f in mapping["fields"] for p in f["source_paths"]}),
        "concepts": result.get("new_concepts", 0), "observations": len(obs),
        "profile_visible_observations": sum(o.get("privacy") != "personal" for o in obs),
        "business_connected_observations": sum(o.get("privacy") != "personal" and o["entity_ref"] in connected for o in obs),
        "self_edges": sum(e["from_ref"] == e["to_ref"] for e in edges),
        "test_quality": result.get("test_quality"), "quality": result.get("quality"),
        **usage(root, sid)}


def question_specs(sid):
    if sid.startswith("acnc"):
        return [Question("charity_financials", "Reported gross income and assets, with currency, period and consolidation context?",
            (("total gross income",), ("total assets",)), ("business", "charity"), True, True,
            ("report consolidated with more than one entity",)),
            Question("charity_workforce", "Reported employee and volunteer counts?",
            (("total full time equivalent staff", "full time employees", "number of full time employees"),
             ("number of volunteers", "volunteers", "staff - volunteers")), ("business", "charity"))]
    if sid.startswith("wgea"):
        return [Question("workforce_band", "What employee size band and reporting period are supplied?",
            (("Employer size range (# employees)",),), ("business", "employer_reporting_unit"), True),
            Question("workforce_exact", "What is the exact employee headcount?", (("Exact employee count",),))]
    return [Question("ip_role", "What party role and role-validity dates are recorded?",
                (("party_role",),), ("party_activity", "ip_party_activity", "party_role", "ip_party_role", "party_involvement", "party"), True),
            Question("ip_status_description", "What application status and description are linked to the party record?",
                (("status",), ("description_value",)), ("ip_application", "application")),
            Question("ip_status", "What source-stated application status is available?", (("status",),), ("ip_application", "application")),
            Question("ip_ownership", "Who is the verified ultimate beneficial owner of the IP?", (("Verified ultimate beneficial owner",),))]


def review_and_questions(root, sid):
    folder = root / sid
    if not (folder / "mapping.json").exists():
        return [], []
    result = read(folder / "result.json")
    cfg = DynamicMapping.model_validate(read(folder / "mapping.json"))
    ontology = Registry(root / "registry").load(result["ontology_version"])
    header = read(folder / "header-contract.json")
    schema = {"columns": sorted(header["parsed_columns"]), "reader": cfg.reader.model_dump(), "header_context": header.get("header_context", [])}
    queue = ReviewMemory(EXP / "human-decisions.jsonl").queue(review_items(cfg, ontology, schema))
    observations, edges = lines(folder / "observations.jsonl"), lines(folder / "relationships.jsonl")
    count = read(folder / "sampling.json")["sample_rows"]
    questions = [evaluate_question(q, observations, edges, input_records=count) for q in question_specs(sid)]
    return queue, questions


def simulated_review(items):
    """Synthetic repeat/change demonstration; no real reviewer decisions persist."""
    # Independent source registries may propose different meanings under one path.
    # Do not treat those unresolved variants as simultaneously approved concepts.
    original_count = len(items)
    items = list({i["key"]: i for i in items}.values())
    with tempfile.TemporaryDirectory() as temp:
        memory = ReviewMemory(Path(temp) / "synthetic.jsonl")
        for item in items:
            memory.record(item, reviewer="synthetic fixture", reviewer_kind="synthetic_test", decision="approve", evidence_digest="test-only")
        repeat = memory.queue(items, test_mode=True)
        changed = copy.deepcopy(items)
        binding = next((i for i in changed if i["kind"] == "binding"), None)
        if binding:
            binding["contract"] = copy.deepcopy(binding["contract"])
            binding["contract"]["source_schema"]["synthetic_reporting_year_change"] = "next year"
            binding["fingerprint"] = digest(binding["contract"])
        delta = memory.queue(changed, test_mode=True)
        return {"synthetic_only": True, "items": len(items),
            "excluded_conflicting_key_variants": original_count - len(items),
            "unchanged_repeat": dict(Counter(i["review_state"] for i in repeat)),
            "one_changed_binding": dict(Counter(i["review_state"] for i in delta)),
            "real_approvals_from_synthetic_ledger": sum(i["review_state"] == "approved_unchanged" for i in memory.queue(items)),
            "measured_human_time_saved": None}


def controller_ablation():
    """No LLM calls: isolate the gate change on the last executed ACNC proposal."""
    folder = OLD / "run/acnc_ais2024_new"
    inspection = Inspection.model_validate(read(folder / "0-inspector.json")["response"])
    proposal = Proposal.model_validate(read(folder / "3-architect.json")["response"])
    cfg = DynamicMapping.model_validate(read(folder / "3-mapper.json")["response"])
    records = sample(folder / "records.jsonl.gz")
    columns = sorted({c for r in records if r["partition"] != "test" for c in bind(r["row"], inspection)[0]})
    candidate = propose(bootstrap(), proposal, columns)
    errors = validate_mapping(cfg, candidate, columns)
    if errors:
        raise ValueError("Original ablation mapping no longer validates: " + str(errors))
    source = next(s for s in read(Path("config/profile_enrichment_sources.json")) if s["source_id"] == "acnc_ais2024_new")
    _, _, _, report = extract(cfg, source, candidate, [r for r in records if r["partition"] == "validation"], inspection)
    saved = read(folder / "3-validation.json")["heldout"]
    if report != saved:
        raise ValueError("Ablation no longer reproduces original held-out extraction")
    obs, edges, _, all_rows = extract(cfg, source, candidate, records, inspection)
    _, _, _, test = extract(cfg, source, candidate, [r for r in records if r["partition"] == "test"], inspection)
    return {"source_id": source["source_id"], "mapping_digest": cfg.digest(), "model_calls": 0,
        "original_gate_error_rate": saved["error_rate"], "revised_validation_quality": quality(report),
        "revised_test_quality": quality(test), "all_records_quality": quality(all_rows), "rules": len(cfg.fields),
        "recorded_critic_verdict": read(folder / "3-critic.json")["response"]["verdict"],
        "questions": [evaluate_question(q, obs, edges, input_records=len(records)) for q in question_specs(source["source_id"])],
        "status": "POSTHOC_TECHNICAL_ABLATION_NOT_PROMOTED",
        "scope": "Same saved proposal/mapping and rows. Changes accounting only, not values or semantic definitions. Not a new autonomous ingestion or human approval."}


def main():
    baseline = read(OLD / "automation-evaluation.json")["sources"]
    rows, all_queues, questions, blocking = [], [], [], []
    for name, sid, old_run in CASES:
        original = next(s for s in baseline if s["source_id"] == sid)
        first, recovery = measure(EXP / "run", sid), measure(EXP / "recovery", sid)
        paired = sample(OLD / old_run / sid / "records.jsonl.gz") == sample(EXP / "run" / sid / "records.jsonl.gz")
        if not paired:
            raise ValueError("Paired source records/partitions differ for " + sid)
        recovery["cumulative_input_tokens"] = first["input_tokens"] + recovery["input_tokens"]
        recovery["cumulative_output_tokens"] = first["output_tokens"] + recovery["output_tokens"]
        rows.append({"name": name, "same_records_and_partitions": paired, "baseline": original, "first_grouped": first, "recovery": recovery})
        queue, qs = review_and_questions(EXP / "recovery", sid)
        all_queues.extend(queue); questions += [{"source_id": sid, **q} for q in qs]
        blocking += [{"source_id": sid, **g} for g in read(EXP / "recovery" / sid / "result.json").get("groups", []) if g["status"] != "AGENT_VALIDATED"]
    join_root = EXP / "ip-joined-recovery"
    joined = measure(join_root, "ip_joined_view")
    joined_first = measure(EXP / "ip-joined-run", "ip_joined_view")
    joined["first_pass"] = joined_first
    joined["cumulative_input_tokens"] = joined_first["input_tokens"] + joined["input_tokens"]
    joined["cumulative_output_tokens"] = joined_first["output_tokens"] + joined["output_tokens"]
    queue, qs = review_and_questions(join_root, "ip_joined_view")
    all_queues.extend(queue); questions += [{"source_id": "ip_joined_view", **q} for q in qs]
    blocking += [{"source_id": "ip_joined_view", **g} for g in read(join_root / "ip_joined_view/result.json").get("groups", []) if g["status"] != "AGENT_VALIDATED"]
    # Semantics can recur across feeds; distinct bindings stay separate.
    unique = {}
    for item in all_queues:
        key = item["key"] + ":" + item["fingerprint"]
        unique[key] = item
    all_queues = list(unique.values())
    simulation = simulated_review(all_queues)
    replay_results = {str(root): replay(root) for root in (EXP / "run", EXP / "recovery", EXP / "ip-joined-run", join_root)}
    review_counts = dict(Counter(i["kind"] for i in all_queues))
    variants = Counter(i["key"] for i in all_queues)
    result = {"scope": "Known-case engineering comparison; one stochastic run per condition, with documented interventions. No population accuracy claim.",
        "conflicting_contract_keys": {k: v for k, v in variants.items() if v > 1},
        "controller_only_ablation": controller_ablation(),
        "paired_sources": rows, "joined_source": joined, "joins": read(EXP / "ip-joins/join-results.json"),
        "join_planning_usage": usage(EXP / "ip-joins", "ip_join_view"),
        "questions": questions, "review_counts": review_counts, "blocked_groups": blocking,
        "review_simulation": simulation, "offline_replay": replay_results,
        "human_semantic_precision": None, "measured_human_review_minutes": None,
        "production_promoted": False}
    write(EXP / "evaluation.json", result)
    write(EXP / "review-queue.json", all_queues)
    write(EXP / "business-question-checks.json", questions)
    path = EXP / "human-review-inventory.csv"
    if path.exists():
        with path.open(encoding="utf-8", newline="") as stream:
            if any(r.get("human_verdict") or r.get("reviewer") or r.get("minutes") or r.get("notes") for r in csv.DictReader(stream)):
                raise ValueError("Existing human labels must not be overwritten")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["key", "kind", "fingerprint", "state", "human_verdict", "reviewer", "minutes", "notes"])
        writer.writeheader()
        for item in all_queues:
            writer.writerow({"key": item["key"], "kind": item["kind"], "fingerprint": item["fingerprint"], "state": item["review_state"]})
    report(result)
    print(json.dumps({"review_items": len(all_queues), "blocked_groups": len(blocking), "sources": [(r["name"], r["recovery"]["status"], r["recovery"]["observations"]) for r in rows], "joined": joined["status"]}))


def report(result):
    rows = result["paired_sources"]
    out = ["# Grouped ontology: implementation and evaluation", "",
        "The changes improve recoverability and add verified multi-table intake. They do not establish unattended ontology learning or measured semantic accuracy. All new ontology and source-binding decisions remain candidates awaiting human review; production profiles are unchanged.", "",
        "## Comparison on identical source records", "",
        "Each source uses the same 600 frozen records and discovery/validation/test assignments as its preserved baseline. The first grouped run makes fresh model calls. Recovery reuses the recorded plan and accepted groups, and retries failures after generic controller fixes. These are known development cases, not independent unseen-source tests. One run per condition cannot isolate model randomness from controller effects.", ""]
    out += md_table(["Source", "Original candidate observations", "First grouped", "After recovery", "Final groups accepted", "Status"], [
        [r["name"], r["baseline"]["accepted_observations"], r["first_grouped"]["observations"], r["recovery"]["observations"],
         f'{r["recovery"]["accepted_groups"]}/{r["recovery"]["groups"]}', r["recovery"]["status"]] for r in rows])
    out += ["", "Counts are retained candidate observations, not confirmed-correct facts. Zero can mean ingestion/reconciliation failed; it does not mean the source contains no useful information.", "", "## Token cost and recovery", ""]
    out += md_table(["Source", "Original tokens", "First grouped tokens", "Recovery tokens", "Grouped cumulative tokens", "Groups reused without model calls"], [
        [r["name"], r["baseline"]["input_tokens"] + r["baseline"]["output_tokens"], r["first_grouped"]["input_tokens"] + r["first_grouped"]["output_tokens"],
         r["recovery"]["input_tokens"] + r["recovery"]["output_tokens"], r["recovery"]["cumulative_input_tokens"] + r["recovery"]["cumulative_output_tokens"], r["recovery"]["reused_groups"]] for r in rows])
    out += ["", "Budgets are isolated by source and reserve an entire request before each schema retry. Smaller prompts are not automatically cheaper: multiple groups and critic calls can outweigh context savings. Cumulative totals include failed attempts. Model: deepseek-v4-flash through the authorised gateway. No credentials are stored in reports.", "", "## What changed", "",
        "1. Inspector → group planner → concept retrieval → group architect → semantic mapper → deterministic compiler → validator → critic → final reconciliation. Group failures retain explicit reasons. Repeated identical failures stop; incomplete groups do not silently become mapped.",
        "2. Missing qualifier context is counted separately from malformed values and remains withheld. The technical gate allows at most 5% malformed eligible values, requires output and no record errors. This is not a semantic-precision threshold.",
        "3. The mapper chooses an explicit claim period; the compiler attaches dates to the affected claim. Executor metadata cannot become a business concept. Draft revisions can explicitly retain earlier drafts without treating them as accepted registry concepts.",
        "4. Replay checks frozen rows, partitions, recorded agent intents/critic acceptance, compiled mappings, ontology versions and emitted observations/relationships/refusals. Sealed evidence is immutable. Recovery records its origin and revalidates accepted groups.",
        "5. Human decisions are bound to semantic and executable contracts. Unchanged decisions can be reused; changed meanings, bindings or relevant source context reopen review. No synthetic decision counts as human approval.", "", "## Failures exposed by the experiment", "",
        "The first grouped pass exposed three controller issues: revision responses reused unregistered drafts; WGEA mappings confused entity kinds with role names; and IP group-local omissions conflicted with columns accepted by other groups during final reconciliation. The recovery fixes preserve the failed evidence. Additional scope pruning keeps unrelated roles/edges out of group-level validation; this compiler fix is covered by regression checks and its live-run status is recorded by each run's implementation hashes.", ""]
    ab = result["controller_only_ablation"]
    out += [f'An offline ablation applies only the revised error accounting to the original last-executed ACNC mapping: {ab["rules"]} rules, {ab["all_records_quality"]["emitted_observations"]} emitted observations and {ab["all_records_quality"]["withheld_missing_context"]} withheld missing-context values across 600 records, with zero new model calls. The revised validation gate passes: {ab["revised_validation_quality"]["passes_technical_gate"]}; the original raw rejection rate was {ab["original_gate_error_rate"]:.6%}. This is post-hoc technical evidence, not a newly approved candidate. It shows that fixing the controller alone can be more valuable than splitting every source into many groups.', ""]
    out += md_table(["Source", "Remaining group", "Stop reason / feedback"], [[g["source_id"], g["group"],
        (g.get("feedback") or {}).get("stop_reason") or (g.get("feedback") or {}).get("error") or "See recorded critic/static findings"] for g in result["blocked_groups"]])
    out += ["", "## Separate multi-table IP experiment", "",
        "The publisher archive changed during acquisition. The join experiment therefore uses a fresh, internally consistent snapshot and is excluded from the identical-input comparison. The agent proposed both composite joins; the executor scanned complete application and description tables, checked cardinality and preserved original snapshot/row lineage. Ambiguous or missing keys are refused rather than multiplied or silently selected.", ""]
    out += md_table(["Right table", "Rows scanned", "Anchor rows matched", "Ambiguous keys in cohort", "Output per anchor maximum"], [[s["step"]["right_table"], s["measurement"]["right_rows_scanned"],
        f'{s["measurement"]["matched_left_rows"]}/{s["measurement"]["left_rows"]}', s["measurement"]["right_duplicate_keys_in_cohort"], s["measurement"]["materialized_rows_per_left_max"]] for s in result["joins"]["steps"]])
    j = result["joined_source"]
    out += ["", f'The joined mapping produced {j["observations"]} candidate observations from 600 sampled records; status: {j["status"]}. Join planning used {sum(result["join_planning_usage"][k] for k in ("input_tokens", "output_tokens"))} tokens; joined-source mapping used {j["cumulative_input_tokens"] + j["cumulative_output_tokens"]} cumulatively, including the initial {j["first_pass"]["input_tokens"] + j["first_pass"]["output_tokens"]}-token pass and targeted recovery. The 25,000-record anchor is a patent-prefix cohort. It is not representative of all IP rights. A valid join does not establish ownership, business identity or current enforceability.', "", "## Business-question acceptance", "",
        "These checks require source evidence, the intended owning entity, necessary period/currency context and a declared path to a business. Row co-occurrence alone never establishes identity. Supported means structurally available in this candidate; semantic truth still needs review. Exact headcount and beneficial ownership are deliberately unsupported where the source does not supply them.", ""]
    out += md_table(["Source", "Question", "Rows with values", "Meet evidence contract", "Connected to business", "Outcome"], [[q["source_id"], q["question"], q["rows_with_requested_values"], q["rows_meeting_evidence_contract"], q["rows_connected_to_business"], q["status"]] for q in result["questions"]])
    out += ["", "A charity/reporting-unit/party node is not automatically the business subject. Disconnected facts require an explicit, evidence-supported relationship or identity design before profile use. The question checks expose this gap even where the mapping critic accepted individual groups.", "", "## Human review required", ""]
    out += md_table(["Source", "Candidate observations", "Visible observations connected to business", "Self-edges requiring graph review"], [
        [r["name"], r["recovery"]["observations"], r["recovery"]["business_connected_observations"], r["recovery"]["self_edges"]] for r in rows] +
        [["IP joined", j["observations"], j["business_connected_observations"], j["self_edges"]]])
    out += ["", "These are graph-connectivity checks, not links into the existing 50 production profiles. Self-edges cannot express a separate description entity and need semantic reconciliation. Privacy-suppressed values do not count as profile-visible evidence.", ""]
    out += md_table(["Review unit", "Pending contracts"], list(result["review_counts"].items()))
    out += ["", f'{len(result["blocked_groups"])} unresolved groups require technical/semantic correction before sign-off. Review the proposed meaning and ownership first, then the source bindings (units, guards, periods, joins), then a stratified sample of emitted claims and abstentions. The CSV inventory leaves verdict, reviewer and time blank; no measured human precision or working-time saving is available.', "",
        f'{len(result["conflicting_contract_keys"])} contract keys have conflicting definitions across these independently run registries. Any conflicting variants would require reconciliation before combining registries. Review actions can select a specific fingerprint; no variant is automatically approved.', "",
        "The review-memory demonstration uses temporary synthetic decisions only, with one variant per key. It checks an unchanged repeat and one changed binding; it does not estimate real review effort or approve candidates.", ""]
    sim = result["review_simulation"]
    out += md_table(["Synthetic scenario", "Unchanged approvals reused", "Changed items reopened"], [
        ["Repeat same contracts", sim["unchanged_repeat"].get("approved_unchanged", 0), sim["unchanged_repeat"].get("changed_requires_review", 0)],
        ["Change one binding context", sim["one_changed_binding"].get("approved_unchanged", 0), sim["one_changed_binding"].get("changed_requires_review", 0)]])
    out += ["", "## Reproduce the evaluation", "",
        "Run `python -m scripts.evaluate_grouped_ontology` for offline metrics/replay. Use `python -m firmable.evolution2 replay --output outputs/experiments/grouped-ontology/recovery` to check recovery evidence. No API call is needed. Live commands and budget controls are documented in docs/ONTOLOGY_IMPROVEMENT_PLAN.md. Downloaded source files are ignored; recorded sample evidence supports replay.", "",
        "Detailed artifacts: evaluation.json; business-question-checks.json (including examples); review-queue.json; human-review-inventory.csv; per-run usage.jsonl and checkpoints; ip-joins/join-plan.json, join-results.json and view-lineage.jsonl. No production promotion, commit or push was performed.", ""]
    (EXP / "RESULTS.md").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
