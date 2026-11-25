# Ontology improvement experiment

Objective: implement and measure the proposed improvements without replacing the historical benchmark, approving machine output as human review, or committing/pushing changes.

## Completion evidence required

1. Controller: explicit abstention/error accounting, actionable field failures, repeated-proposal detection and per-source budget isolation. Verify with adversarial tests and recorded ACNC/IP reruns.
2. Grouped reasoning: model-authored groups, relevant concept retrieval, typed semantic intents compiled to the existing mapping DSL, targeted revisions and final reconciliation. Compare coverage, calls/tokens and outcomes on the same frozen source snapshots/partitions.
3. Review memory: evidence-bound reviewer decisions, reusable semantic contracts, invalidation on changed bindings/meaning, and a change-based review queue. Demonstrate with clearly synthetic test decisions; do not create real approvals.
4. Multi-table ingestion: model-proposed join plan, measured key coverage/cardinality/row multiplication, preserved source provenance and abstention on unsafe joins. Exercise on IP Australia application/party data, separately from the same-input benchmark.
5. Business-question checks: executable requirements for workforce size, dated charity financials and role-scoped IP information; report supported, partial and unsupported answers with evidence. Do not equate successful extraction with useful company intelligence.
6. Evaluation: offline replay, regression checks, preserved baselines, a reviewable report with measured before/after statistics and limitations. Human time savings and semantic precision remain unmeasured unless actual human labels/timings are supplied.

The existing development sources are regression experiments, not a new held-out population. Stage-level comparison must distinguish reused inspections, changed inputs, newly retrieved tables, cached responses and new model calls. A success on repaired known cases is not a fresh autonomous ingestion success rate.

Production promotion, commits and pushes remain out of scope pending the owner's review.

## Run and review

Use Python 3.11+ and the existing project installation (`pip install -e ".[dev]"`). From the repository root:

```bash
# Recorded evidence only; no key or complete downloads required.
python -m scripts.evaluate_grouped_ontology
python -m firmable.evolution2 replay --output outputs/experiments/grouped-ontology/recovery
python -m pytest -q

# Optional paid experiment. Configure DEEPSEEK_API_KEY and the desired model
# using the provider instructions in README; credentials are never CLI arguments.
# Restore inputs first. Existing snapshots must match their recorded hashes.
python -m firmable.evolution2 run --sources config/profile_enrichment_sources.json --output outputs/experiments/my-grouped-run --live --independent-sources --source-budget 350000 --total-budget 1200000

# Retry failed groups from a sealed run, retaining accepted agent decisions.
python -m firmable.evolution2 run --sources config/profile_enrichment_sources.json --output outputs/experiments/my-recovery --resume-from outputs/experiments/my-grouped-run --live --independent-sources --source-budget 350000 --total-budget 700000
```

Use new output directories when changing prompts, inputs or code. Sealed runs cannot be overwritten. The recorded runs used the previously authorised gateway; environment credentials are excluded. Model responses remain stochastic, so live reruns need not reproduce the recorded outcome. Full source downloads are ignored; offline replay reconstructs outputs from frozen samples.

For a new IP join experiment, `python -m scripts.fetch_ip_join_inputs --new-snapshot` acquires a fresh 25,000-record party prefix and complete application/description CSV members from one archive ETag. It downloads over 1 GB decompressed and verifies full-member CRCs for the two complete tables. The partial party stream cannot verify its full-member CRC. Do not mix it with the older benchmark prefix.

`python -m scripts.run_ip_join_experiment --live --output outputs/experiments/my-ip-joins` requests a typed join plan from the model and measures actual key/cardinality behaviour. Then pass its `sources.json` to `firmable.evolution2 run` with a fresh output directory. The executor supports one-to-one/many-to-one star joins only; other shapes require an explicit extension. Missing/duplicate keys are refused, original row hashes and snapshot hashes remain in `view-lineage.jsonl`.

## Human review memory

The evaluator writes `review-queue.json` and a blank CSV inventory. Inspect the specific concept/binding/relationship contract and its source evidence before recording a decision:

```bash
python -m firmable.evolution2.review outputs/experiments/grouped-ontology/review-queue.json --memory outputs/experiments/grouped-ontology/human-decisions.jsonl --key REVIEW_ITEM_KEY --fingerprint DISPLAYED_FINGERPRINT --reviewer YOUR_NAME --decision approve --evidence-digest REVIEWED_EVIDENCE_HASH --notes "Meaning, scope and evidence checked"
```

This is an explicit human action; the controller never invokes it. The command records a contract decision, not production promotion. A later run may take `--review-memory PATH`. Unchanged semantic approval does not approve a changed source binding, prove a new batch's accuracy, or resolve drift. Recheck batch values, abstentions and business-question coverage. Tests use temporary `synthetic_test` decisions, which the real queue excludes.

The evaluator refuses to overwrite a CSV containing review verdicts, names, notes or timings. Preserve those labels and make a separate evaluation version after human work begins.

## Interpretation of the recorded experiment

The [results](../outputs/experiments/grouped-ontology/RESULTS.md) support selective adoption: retain budget isolation, abstention accounting, typed compilation, explicit join checks and review invalidation. Keep the existing WGEA engine as the stronger measured result. Do not make the grouped controller the default based on this experiment. Global role/identity design, privacy-safe organisation bindings, unfinished groups and description self-edges still need reconciliation. No human semantic precision or measured review-time reduction is claimed.
