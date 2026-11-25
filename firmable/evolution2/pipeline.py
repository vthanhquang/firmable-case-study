"""Bounded, grouped source onboarding with retained decisions and offline replay."""
import gzip
import hashlib
import json
import os
import shutil
import time
from collections import Counter
from pathlib import Path

from .. import llm
from ..mapping.transforms import describe as transforms_description
from ..evolution.pipeline import Controller as LegacyController, SYSTEM, EXECUTION_CONTRACT, parse_agent_json, critic_evidence, jsonlines, partition
from ..evolution.registry import Registry, bootstrap, propose, write
from ..evolution.schema import Inspection, Proposal, DynamicMapping, digest
from ..evolution.engine import bind, extract, project
from ..sources.inspect import inspect_file
from ..sources.readers import iter_records
from .contracts import GroupPlan, ConceptPatch, GroupIntent, GroupCritique, compile_mapping, whole_patch, resolve_patch
from .quality import quality, mapping_findings, ProgressGuard, select_concepts
from .review import ReviewMemory, review_items

PROMPTS = {
    "inspector": "Choose a shared reader from actual bytes and explain row grain, header groups and identifier cautions. Preserve sheet names exactly. Do not choose a documentation sheet. Bind only singleton nested objects. Explain contextual years and percentage storage when visible.",
    "group_planner": "Partition ALL observed source columns exactly once into coherent business groups of at most 24 columns. Prefer 4-8 groups for wide tables and 2-3 for narrow tables. Keep similar measures with their scope where possible. State record grain. Declare named entity roles/types only where needed; subject is the implicit business, never declare it. Individuals, IP applications, party involvement and businesses are distinct. Reuse existing entity kinds. Key paths must be actual columns; no legal identity inference from names. Each group can reference other columns as qualifiers/conditions later. Propose only source-evidenced relationships. Metadata/validity is not a business entity.",
    "group_architect": "Resolve ONLY this group's meanings. Reuse shortlisted concepts only when owner, meaning, units and temporal scope agree. Otherwise propose typed dyn.family.field concepts with real column evidence. Use shared concepts with qualifiers for analogous measures; avoid needless aliases. Date, currency and reporting-unit scope must be explicit. Money requires currency and time-varying financial measures require a period. Entity types and relationships were already planned; do not add them here. You may reuse concepts from earlier accepted groups. New concepts must be business-useful, not copies of executor provenance fields.",
    "group_mapper": "Map ONLY this group's owned value columns against the supplied ontology. Other observed columns may supply qualifiers, guards, key context or claim periods. Every owned column must be consumed as a value/context or explicitly declined. Return semantic fields and explicit omissions, not a whole source config. Metadata (observation.*, confidence.*) is produced by the executor: NEVER target it. To date a claim, attach claim_period with a meaning and its from/to columns to that field; the compiler sets validity. For an independently reported date, use an appropriate date concept. Do not invent dates/values to improve coverage. Only allowed transformations, roles and concepts. When source context is missing, retain required qualifiers so the executor withholds the claim. Maintain guards for mixed person/business populations; applicant/agent/owner roles are distinct. No new concepts in this stage.",
    "group_critic": "Challenge this group's emitted claims using actual held-out validation evidence. Check meaning, owner, units, dates, legal claims, provenance and repeated/missing data. Missing required source context is deliberate abstention, not an incorrect emitted value; do not demand invented fallback dates. Judge semantic correctness separately from coverage. Check field definitions for scope, including consolidated accounts and historical party roles. Accept honestly bounded partial coverage when emitted meanings are defensible. For blocking issues name exact fields and an executable correction, and set repair_scope to mapping, ontology or both; accept uses none. Do not require hypothetical features or nonexistent guards. Never label this human approval. An accepting verdict with blocking findings will be rejected.",
}


class SourceBudget(RuntimeError):
    pass


def ledger_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def header_contract(source, inspection):
    """Preserve positional header evidence before semantic reasoning."""
    path = Path(source["local_path"])
    reader = inspection.reader
    first = next(iter_records(path, reader))
    evidence = {"parsed_columns": list(first), "byte_inspection": inspect_file(path)}
    if reader.format == "xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[reader.sheet] if reader.sheet else wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        above = [next(rows) for _ in range(reader.skip_rows)]
        header = next(rows)
        evidence.update(raw_headers=[str(x) if x is not None else None for x in header],
                        header_context=[[str(x) if x is not None else None for x in r] for r in above],
                        physical_columns=len(header), parsed_column_count=len(first))
        wb.close()
        if len(header) != len(first):
            raise ValueError("Reader fidelity failure: physical and parsed column counts differ")
    return evidence


class Controller(LegacyController):
    def __init__(self, root, *, live=False, per_source_budget=350000, total_budget=1200000, resume_from=None, review_memory=None):
        super().__init__(root, live=live)
        self.per_source_budget, self.total_budget = per_source_budget, total_budget
        self.resume_from = Path(resume_from) if resume_from else None
        self.review_memory = ReviewMemory(review_memory or root / "human-decisions.jsonl")
        if self.resume_from:
            if not (self.resume_from / "evidence-manifest.json").exists():
                raise ValueError("Resume requires a sealed prior experiment")
            replay(self.resume_from)

    def agent(self, role, sid, step, payload, schema):
        request = {"role": role, "instructions": PROMPTS[role], "schema": schema.model_json_schema(), "evidence": payload}
        request_hash = digest(request)
        path = self.root / sid / f"{step}-{role}.json"
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved["request_sha256"] != request_hash:
                raise ValueError("Checkpoint inputs changed; create a new experiment: " + str(path))
            return schema.model_validate(saved["response"])
        if not self.live:
            raise RuntimeError("Missing recorded model response: " + str(path))
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(request, default=str)}]
        for attempt in range(3):
            # Reserve an entire request before each schema retry, not just the first call.
            entries = ledger_rows(self.root / "usage.jsonl")
            spent = lambda rows: sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in rows)
            reserve = len(json.dumps(messages, ensure_ascii=False).encode()) + 8000 + 2048
            if spent([r for r in entries if r["source_id"] == sid]) + reserve > self.per_source_budget:
                raise SourceBudget("Per-source request reservation exhausted; other sources retain their allowances")
            if spent(entries) + reserve > self.total_budget:
                raise SourceBudget("Experiment request reservation exhausted")
            start = time.perf_counter()
            message = llm.chat(messages, stage="evolution2." + role, source_id=sid, run_id=step,
                               max_tokens=8000, json_mode=True)
            try:
                response = schema.model_validate(parse_agent_json(message.content))
            except (ValueError, TypeError) as exc:
                write(path.with_name(f"{step}-{role}-invalid-{attempt}.json"), {"request_sha256": request_hash,
                      "schema_error": str(exc), "response_text": message.content})
                messages += [{"role": "assistant", "content": message.content or ""},
                             {"role": "user", "content": "Correct the exact schema/semantic compiler error: " + str(exc)[:3500]}]
                continue
            write(path, {"request_sha256": request_hash, "role": role, "model": llm.DEFAULT_MODEL,
                         "seconds": round(time.perf_counter() - start, 3), "response": response.model_dump()})
            self.event("AGENT_RESPONSE", source_id=sid, role=role, step=step, response_sha256=digest(response.model_dump()))
            return response
        raise ValueError("Structured response remained invalid after three bounded attempts")

    def run_source(self, source, base):
        sid = source["source_id"]
        folder = self.root / sid
        prior = self.resume_from / sid if self.resume_from else None
        if prior:
            old_source = next(s for s in json.loads((self.resume_from / "sources.json").read_text(encoding="utf-8")) if s["source_id"] == sid)
            if old_source != source or file_sha(Path(source["local_path"])) != source["snapshot_sha256"]:
                raise ValueError("Resume source changed; use a fresh experiment")
            inspection = Inspection.model_validate_json((prior / "inspection.json").read_text(encoding="utf-8"))
            with gzip.open(prior / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
                records = [json.loads(line) for line in stream]
            folder.mkdir(parents=True, exist_ok=True)
            for name in ("records.jsonl.gz", "sampling.json"):
                shutil.copyfile(prior / name, folder / name)
            write(folder / "resume-origin.json", {"root": str(self.resume_from), "manifest_sha256": file_sha(self.resume_from / "evidence-manifest.json"), "note": "Reuse prior accepted decisions; retry failed groups with new calls. Cumulative costs include the prior run."})
        else:
            inspection, records = self.inspect(source)
        header = header_contract(source, inspection)
        write(folder / "header-contract.json", header)
        write(folder / "inspection.json", inspection.model_dump())
        discovery = [r for r in records if r["partition"] == "discovery"]
        validation = [r for r in records if r["partition"] == "validation"]
        test = [r for r in records if r["partition"] == "test"]
        dev_rows = [row for r in discovery if (row := bind(r["row"], inspection)[0]) is not None]
        valid_rows = [row for r in validation if (row := bind(r["row"], inspection)[0]) is not None]
        columns = sorted(set().union(*(r.keys() for r in dev_rows + valid_rows)))
        profiles = {c: {"nonempty": sum(r.get(c) not in (None, "") for r in dev_rows),
                   "examples": list(dict.fromkeys(str(r[c])[:180] for r in dev_rows if r.get(c) not in (None, "")))[:4]} for c in columns}
        metadata = {k: v for k, v in source.items() if k not in ("acquisition",)}
        plan_payload = {"metadata": metadata, "inspection": inspection.model_dump(), "column_profile": profiles,
                        "existing_entity_types": base["entity_types"], "existing_relationships": base["relationships"],
                        "header_context": header.get("header_context", [])}
        plan = None
        for attempt in range(3):
            plan = (GroupPlan.model_validate_json((prior / "group-plan.json").read_text(encoding="utf-8")) if prior else
                    self.agent("group_planner", sid, f"plan-{attempt}", plan_payload, GroupPlan))
            try:
                plan.check_columns(columns)
                shared = propose(base, whole_patch(plan, []), columns)
                break
            except ValueError as exc:
                plan_payload["feedback"] = {"error": str(exc), "previous_plan": plan.model_dump()}
        else:
            raise ValueError("Group planning did not pass deterministic checks")
        write(folder / "group-plan.json", plan.model_dump())
        patches, intents, group_results = [], [], []
        for group in plan.groups:
            if prior and (prior / f"{group.name}-accepted-intent.json").exists():
                patch = ConceptPatch.model_validate_json((prior / f"{group.name}-accepted-patch.json").read_text(encoding="utf-8"))
                intent = GroupIntent.model_validate_json((prior / f"{group.name}-accepted-intent.json").read_text(encoding="utf-8"))
                candidate = propose(shared, Proposal(concepts=patch.concepts, reuse=patch.reuse), columns)
                cfg = compile_mapping(source, inspection, plan, [intent], outside_columns=sorted(set(columns)-set(group.columns)), scoped=True)
                if mapping_findings(cfg, candidate, columns):
                    raise ValueError("Previously accepted group fails current static validation")
                _, _, _, report = extract(cfg, source, candidate, validation, inspection)
                if not quality(report)["passes_technical_gate"]:
                    raise ValueError("Previously accepted group fails current extraction")
                patches.append(patch); intents.append(intent); shared = candidate
                for suffix in ("accepted-intent", "accepted-patch"):
                    shutil.copyfile(prior / f"{group.name}-{suffix}.json", folder / f"{group.name}-{suffix}.json")
                group_results.append({"group": group.name, "columns": group.columns, "status": "AGENT_VALIDATED", "attempts": 0, "reused_from": str(prior), "feedback": None})
                self.event("GROUP_REUSED", source_id=sid, group=group.name, origin=str(prior))
                continue
            progress = ProgressGuard()
            patch, intent, feedback, accepted = None, None, None, False
            context = {"metadata": metadata, "inspection": inspection.model_dump(), "group": group.model_dump(),
                       "column_profile": {c: profiles[c] for c in group.columns}, "available_source_paths": columns,
                       "context_columns": {c: profiles[c] for c in columns if any(k in c.lower() for k in ("date", "period", "year", "currency", "consolidat", "type", "from", " to"))},
                       "roles": {"subject": "business"} | {k: v.kind for k, v in plan.entities.items()},
                       "allowed_field_entity_values": ["subject", *plan.entities],
                       "role_rule": "field.entity is an exact KEY in roles, never the associated entity kind. Do not create aliases.",
                       "header_context": header.get("header_context", []), "execution_contract": EXECUTION_CONTRACT}
            repair_scope = "both"
            for attempt in range(3):
                step = f"{group.name}-{attempt}"
                try:
                    if patch is None or repair_scope in ("ontology", "both"):
                        shortlist = select_concepts(shared, group.columns, profiles, group.purpose)
                        write(folder / f"{step}-retrieval.json", shortlist)
                        revision = self.agent("group_architect", sid, step,
                            context | {"ontology_shortlist": shortlist, "feedback": feedback,
                                       "prior_draft": patch.model_dump() if patch else None,
                                       "revision_contract": "Return new/replacement definitions. Unchanged prior drafts may be explicitly listed in reuse; omitted drafts are dropped. Draft reuse does not constitute acceptance."}, ConceptPatch)
                        patch = resolve_patch(revision, patch, shared["concepts"])
                        write(folder / f"{step}-resolved-patch.json", patch.model_dump())
                    candidate = propose(shared, Proposal(concepts=patch.concepts, reuse=patch.reuse), columns)
                    used_ontology = {"concepts": {**select_concepts(shared, group.columns, profiles, group.purpose)["concepts"],
                                      **{c.path: c.model_dump() for c in patch.concepts},
                                      **{k: shared["concepts"][k] for k in patch.reuse}},
                                     "entity_types": candidate["entity_types"], "relationships": candidate["relationships"]}
                    intent = self.agent("group_mapper", sid, step, context | {"ontology": used_ontology,
                        "feedback": feedback, "transforms": transforms_description()}, GroupIntent)
                    cfg = compile_mapping(source, inspection, plan, [intent], outside_columns=sorted(set(columns)-set(group.columns)), scoped=True)
                    findings = mapping_findings(cfg, candidate, columns)
                    # Models cannot consume unrelated values to inflate this group's coverage.
                    foreign = {p for f in intent.fields for p in f.source_paths} - set(group.columns)
                    if foreign:
                        findings.append({"code": "FOREIGN_GROUP_VALUES", "columns": sorted(foreign), "correction": "Map only owned value columns; others may be context qualifiers/conditions."})
                    if findings:
                        feedback = {"findings": findings, "previous_intent": intent.model_dump(), "allowed_field_entity_values": ["subject", *plan.entities], "roles": context["roles"]}
                        write(folder / f"{step}-validation.json", feedback)
                        repair_scope = "mapping"
                        if progress.stagnant(patch.model_dump(), intent.model_dump(), findings):
                            feedback["stop_reason"] = "UNCHANGED_FAILED_PROPOSAL"
                            break
                        continue
                    obs, edges, refusals, raw_report = extract(cfg, source, candidate, validation, inspection)
                    measured = quality(raw_report)
                    critique = self.agent("group_critic", sid, step, {"metadata": metadata,
                        "group": group.model_dump(), "inspection": inspection.model_dump(), "roles": context["roles"],
                        "proposal": patch.model_dump(), "mapping": cfg.model_dump(exclude={"unmapped"}) | {"unmapped": [u.model_dump() for u in intent.unmapped]},
                        "ontology": {"concepts": {f.target: candidate["concepts"][f.target] for f in cfg.fields}},
                        "quality": measured, "validation_fields": raw_report["fields"],
                        "field_evidence": critic_evidence(obs, raw_report), "heldout_examples": validation[:2],
                        "execution_contract": EXECUTION_CONTRACT}, GroupCritique)
                    write(folder / f"{step}-validation.json", {"quality": measured, "raw_validation": raw_report,
                          "critic": critique.model_dump()})
                    self.event("GROUP_EVALUATED", source_id=sid, group=group.name, attempt=attempt,
                               critic=critique.verdict, quality=measured)
                    if critique.verdict == "accept" and not critique.blocking_findings and measured["passes_technical_gate"]:
                        accepted = True
                        break
                    feedback = {"critic": critique.model_dump(), "quality": measured,
                                "previous_intent": intent.model_dump(), "previous_patch": patch.model_dump()}
                    if progress.stagnant(patch.model_dump(), intent.model_dump(), {"quality": measured, "blockers": critique.blocking_findings and [f.model_dump() for f in critique.blocking_findings]}):
                        feedback["stop_reason"] = "UNCHANGED_FAILED_PROPOSAL"
                        break
                    repair_scope = critique.repair_scope if critique.repair_scope != "none" else "mapping"
                except SourceBudget as exc:
                    feedback = {"stop_reason": "SOURCE_BUDGET", "error": str(exc)}
                    break
                except ValueError as exc:
                    feedback = {"error": str(exc), "previous_patch": patch.model_dump() if patch else None,
                                "previous_intent": intent.model_dump() if intent else None}
                    repair_scope = "both"
                    write(folder / f"{step}-validation.json", feedback)
                    if progress.stagnant(feedback["previous_patch"], feedback["previous_intent"], str(exc)):
                        feedback["stop_reason"] = "UNCHANGED_FAILED_PROPOSAL"
                        break
            group_results.append({"group": group.name, "columns": group.columns, "status": "AGENT_VALIDATED" if accepted else "NEEDS_REVIEW",
                                  "attempts": attempt + 1, "feedback": None if accepted else feedback})
            write(folder / "groups.json", group_results)
            if accepted:
                patches.append(patch); intents.append(intent); shared = candidate
                write(folder / f"{group.name}-accepted-intent.json", intent.model_dump())
                write(folder / f"{group.name}-accepted-patch.json", patch.model_dump())
        if not intents:
            write(folder / "result.json", {"source_id": sid, "status": "NEEDS_REVIEW", "groups": group_results})
            return base
        declined = sorted({c for g in group_results if g["status"] != "AGENT_VALIDATED" for c in g["columns"]})
        cfg = compile_mapping(source, inspection, plan, intents, outside_columns=declined)
        # Rebuild the final ontology from one additive patch; group order is recorded separately.
        total_patch = whole_patch(plan, patches)
        # Reuse of a newly introduced concept is internal to this source, not a base reuse.
        total_patch.reuse = {k: v for k, v in total_patch.reuse.items() if k in base["concepts"]}
        final = propose(base, total_patch, columns)
        findings = mapping_findings(cfg, final, columns)
        if findings:
            write(folder / "result.json", {"source_id": sid, "status": "RECONCILIATION_FAILED", "groups": group_results, "findings": findings})
            return base
        _, _, _, test_report = extract(cfg, source, final, test, inspection)
        test_quality = quality(test_report)
        complete = all(g["status"] == "AGENT_VALIDATED" for g in group_results)
        status = "AGENT_VALIDATED_CANDIDATE" if complete and test_quality["passes_technical_gate"] else "PARTIAL_REVIEW_REQUIRED"
        obs, edges, refusals, report = extract(cfg, source, final, records, inspection, review_state="agent_candidate_pending_human_review")
        version = self.registry.save(final)
        write(folder / "mapping.json", cfg.model_dump()); write(folder / "ontology-proposal.json", total_patch.model_dump())
        jsonlines(folder / "observations.jsonl", obs); jsonlines(folder / "relationships.jsonl", edges)
        jsonlines(folder / "refusals.jsonl", refusals)
        items = review_items(cfg, final, {"columns": columns, "reader": inspection.reader.model_dump(), "header_context": header.get("header_context", [])})
        write(folder / "review-queue.json", self.review_memory.queue(items))
        write(folder / "result.json", {"source_id": sid, "status": status, "ontology_version": version,
              "parent_version": digest(base), "snapshot_sha256": source["snapshot_sha256"], "mapping_digest": cfg.digest(),
              "groups": group_results, "new_concepts": len(total_patch.concepts), "mapping_rules": len(cfg.fields),
              "unmapped_columns": [u.model_dump() for u in cfg.unmapped], "quality": quality(report), "raw_extraction": report,
              "test_quality": test_quality, "test": test_report, "human_review": "pending", "production_promoted": False})
        return final if status == "AGENT_VALIDATED_CANDIDATE" else base

    def run(self, sources, *, independent_sources=False):
        if (self.root / "evidence-manifest.json").exists():
            raise ValueError("Sealed experiments are immutable")
        write(self.root / "sources.json", sources)
        implementation = {str(p): file_sha(p) for p in sorted(Path("firmable/evolution2").glob("*.py"))}
        write(self.root / "implementation.json", {"files": implementation, "prompts_sha256": digest(PROMPTS)})
        for name in implementation:
            dest = self.root / "implementation" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(name, dest)
        write(self.root / "policy.json", {"per_source_budget": self.per_source_budget, "total_budget": self.total_budget,
              "independent_sources": independent_sources,
              "resume_from": str(self.resume_from) if self.resume_from else None,
              "max_group_attempts": 3, "abstentions": "Missing qualifier context is withheld and counted separately; no inferred fallback dates.",
              "production_promotion": "Not implemented in this experimental controller; human review remains pending."})
        base = bootstrap(); self.registry.save(base)
        for source in sources:
            print("Grouped onboarding " + source["source_id"], flush=True)
            try:
                base = self.run_source(source, base)
            except (ValueError, RuntimeError, llm.BudgetExceeded) as exc:
                write(self.root / source["source_id"] / "result.json", {"source_id": source["source_id"], "status": "NEEDS_REVIEW", "error": str(exc)})
                self.event("SOURCE_STOPPED", source_id=source["source_id"], error=str(exc))
            if independent_sources:
                base = bootstrap()
        return base


def replay(root):
    root = Path(root)
    manifest = root / "evidence-manifest.json"
    if manifest.exists():
        for name, expected in json.loads(manifest.read_text()).items():
            if file_sha(root / name) != expected:
                raise ValueError("Sealed evidence changed: " + name)
    registry = Registry(root / "registry")
    counts = {}
    for source in json.loads((root / "sources.json").read_text(encoding="utf-8")):
        folder = root / source["source_id"]
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        if "mapping_digest" not in result:
            counts[source["source_id"]] = {"status": result["status"], "observations": 0}
            continue
        cfg = DynamicMapping.model_validate_json((folder / "mapping.json").read_text(encoding="utf-8"))
        inspection = Inspection.model_validate_json((folder / "inspection.json").read_text(encoding="utf-8"))
        if cfg.digest() != result["mapping_digest"] or source["snapshot_sha256"] != result["snapshot_sha256"]:
            raise ValueError("Mapping or source changed")
        plan = GroupPlan.model_validate_json((folder / "group-plan.json").read_text(encoding="utf-8"))
        patches, intents = [], []
        for group in result["groups"]:
            if group["status"] != "AGENT_VALIDATED":
                continue
            name = group["group"]
            intent = GroupIntent.model_validate_json((folder / f"{name}-accepted-intent.json").read_text(encoding="utf-8"))
            patch = ConceptPatch.model_validate_json((folder / f"{name}-accepted-patch.json").read_text(encoding="utf-8"))
            if group.get("reused_from"):
                origin = Path(group["reused_from"])
                receipt = json.loads((folder / "resume-origin.json").read_text(encoding="utf-8"))
                if origin.parent.resolve() == root.resolve() or file_sha(origin.parent / "evidence-manifest.json") != receipt["manifest_sha256"]:
                    raise ValueError("Invalid reuse origin")
                origin_manifest = json.loads((origin.parent / "evidence-manifest.json").read_text(encoding="utf-8"))
                for suffix in ("accepted-intent", "accepted-patch"):
                    filename = f"{name}-{suffix}.json"
                    if file_sha(folder / filename) != origin_manifest[origin.name + "/" + filename]:
                        raise ValueError("Reused decision differs from sealed agent decision")
            else:
                step = f"{name}-{group['attempts'] - 1}"
                recorded = json.loads((folder / f"{step}-group_mapper.json").read_text(encoding="utf-8"))["response"]
                critic = json.loads((folder / f"{step}-group_critic.json").read_text(encoding="utf-8"))["response"]
                if intent.model_dump() != recorded or critic["verdict"] != "accept" or critic["blocking_findings"]:
                    raise ValueError("Accepted intent lacks matching model and critic evidence")
                # Replay every explicitly retained draft, not just a handwritten final patch.
                resolved = None
                registered = set(registry.load(result["parent_version"])["concepts"]) | {c.path for p in patches for c in p.concepts}
                for attempt in range(group["attempts"]):
                    raw = folder / f"{name}-{attempt}-group_architect.json"
                    if raw.exists():
                        revision = ConceptPatch.model_validate(json.loads(raw.read_text(encoding="utf-8"))["response"])
                        if (folder / f"{name}-{attempt}-resolved-patch.json").exists():
                            resolved = resolve_patch(revision, resolved, registered)
                        else:
                            resolved = revision
                if resolved != patch:
                    raise ValueError("Accepted patch differs from recorded architect decisions")
            patches.append(patch); intents.append(intent)
        declined = sorted({c for g in result["groups"] if g["status"] != "AGENT_VALIDATED" for c in g["columns"]})
        compiled = compile_mapping(source, inspection, plan, intents, outside_columns=declined)
        if compiled != cfg:
            raise ValueError("Final mapping differs from deterministic compilation of agent intents")
        parent = registry.load(result["parent_version"])
        combined = whole_patch(plan, patches)
        combined.reuse = {k: v for k, v in combined.reuse.items() if k in parent["concepts"]}
        if combined.model_dump() != json.loads((folder / "ontology-proposal.json").read_text(encoding="utf-8")):
            raise ValueError("Final ontology patch differs from recorded architect decisions")
        with gzip.open(folder / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
            records = [json.loads(line) for line in stream]
        if any(digest(r["row"]) != r["record_id"] or partition(r) != r["partition"] for r in records):
            raise ValueError("Frozen row or partition changed")
        ontology = registry.load(result["ontology_version"])
        columns = sorted({c for g in plan.groups for c in g.columns})
        if propose(parent, combined, columns) != ontology:
            raise ValueError("Final ontology differs from compiled proposal")
        obs, edges, refused, report = extract(cfg, source, ontology, records, inspection, review_state="agent_candidate_pending_human_review")
        expected = [json.loads(line) for line in (folder / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
        if obs != expected or quality(report) != result["quality"]:
            raise ValueError("Offline extraction differs")
        for filename, actual in (("relationships.jsonl", edges), ("refusals.jsonl", refused)):
            if actual != [json.loads(line) for line in (folder / filename).read_text(encoding="utf-8").splitlines()]:
                raise ValueError("Offline relationships/refusals differ")
        counts[source["source_id"]] = {"status": result["status"], "observations": len(obs)}
    return counts


def seal(root):
    root = Path(root)
    counts = replay(root)
    if not (root / "evidence-manifest.json").exists():
        write(root / "evidence-manifest.json", {p.relative_to(root).as_posix(): file_sha(p) for p in sorted(root.rglob("*")) if p.is_file()})
    return counts
