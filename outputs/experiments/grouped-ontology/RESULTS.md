# Grouped ontology: implementation and evaluation

The changes improve recoverability and add verified multi-table intake. They do not establish unattended ontology learning or measured semantic accuracy. All new ontology and source-binding decisions remain candidates awaiting human review; production profiles are unchanged.

## Comparison on identical source records

Each source uses the same 600 frozen records and discovery/validation/test assignments as its preserved baseline. The first grouped run makes fresh model calls. Recovery reuses the recorded plan and accepted groups, and retries failures after generic controller fixes. These are known development cases, not independent unseen-source tests. One run per condition cannot isolate model randomness from controller effects.

| Source | Original candidate observations | First grouped | After recovery | Final groups accepted | Status |
| --- | --- | --- | --- | --- | --- |
| ACNC | 0 | 15125 | 20193 | 5/9 | PARTIAL_REVIEW_REQUIRED |
| WGEA | 13948 | 0 | 11996 | 4/5 | PARTIAL_REVIEW_REQUIRED |
| IP party | 0 | 0 | 7397 | 5/5 | AGENT_VALIDATED_CANDIDATE |

Counts are retained candidate observations, not confirmed-correct facts. Zero can mean ingestion/reconciliation failed; it does not mean the source contains no useful information.

## Token cost and recovery

| Source | Original tokens | First grouped tokens | Recovery tokens | Grouped cumulative tokens | Groups reused without model calls |
| --- | --- | --- | --- | --- | --- |
| ACNC | 1076093 | 308956 | 303601 | 612557 | 4 |
| WGEA | 179859 | 239871 | 298351 | 538222 | 0 |
| IP party | 256691 | 272090 | 0 | 272090 | 5 |

Budgets are isolated by source and reserve an entire request before each schema retry. Smaller prompts are not automatically cheaper: multiple groups and critic calls can outweigh context savings. Cumulative totals include failed attempts. Model: deepseek-v4-flash through the authorised gateway. No credentials are stored in reports.

## What changed

1. Inspector → group planner → concept retrieval → group architect → semantic mapper → deterministic compiler → validator → critic → final reconciliation. Group failures retain explicit reasons. Repeated identical failures stop; incomplete groups do not silently become mapped.
2. Missing qualifier context is counted separately from malformed values and remains withheld. The technical gate allows at most 5% malformed eligible values, requires output and no record errors. This is not a semantic-precision threshold.
3. The mapper chooses an explicit claim period; the compiler attaches dates to the affected claim. Executor metadata cannot become a business concept. Draft revisions can explicitly retain earlier drafts without treating them as accepted registry concepts.
4. Replay checks frozen rows, partitions, recorded agent intents/critic acceptance, compiled mappings, ontology versions and emitted observations/relationships/refusals. Sealed evidence is immutable. Recovery records its origin and revalidates accepted groups.
5. Human decisions are bound to semantic and executable contracts. Unchanged decisions can be reused; changed meanings, bindings or relevant source context reopen review. No synthetic decision counts as human approval.

## Failures exposed by the experiment

The first grouped pass exposed three controller issues: revision responses reused unregistered drafts; WGEA mappings confused entity kinds with role names; and IP group-local omissions conflicted with columns accepted by other groups during final reconciliation. The recovery fixes preserve the failed evidence. Additional scope pruning keeps unrelated roles/edges out of group-level validation; this compiler fix is covered by regression checks and its live-run status is recorded by each run's implementation hashes.

An offline ablation applies only the revised error accounting to the original last-executed ACNC mapping: 91 rules, 35344 emitted observations and 2744 withheld missing-context values across 600 records, with zero new model calls. The revised validation gate passes: True; the original raw rejection rate was 8.207441%. This is post-hoc technical evidence, not a newly approved candidate. It shows that fixing the controller alone can be more valuable than splitting every source into many groups.

| Source | Remaining group | Stop reason / feedback |
| --- | --- | --- |
| acnc_ais2024_new | income_and_revenue | SOURCE_BUDGET |
| acnc_ais2024_new | expenses_and_grants_made | SOURCE_BUDGET |
| acnc_ais2024_new | assets_and_liabilities | SOURCE_BUDGET |
| acnc_ais2024_new | key_management_and_related_parties | SOURCE_BUDGET |
| wgea_employers_new | prior_year_gender_pay_gaps_comparison | SOURCE_BUDGET |
| ip_joined_view | application_description | SOURCE_BUDGET |

## Separate multi-table IP experiment

The publisher archive changed during acquisition. The join experiment therefore uses a fresh, internally consistent snapshot and is excluded from the identical-input comparison. The agent proposed both composite joins; the executor scanned complete application and description tables, checked cardinality and preserved original snapshot/row lineage. Ambiguous or missing keys are refused rather than multiplied or silently selected.

| Right table | Rows scanned | Anchor rows matched | Ambiguous keys in cohort | Output per anchor maximum |
| --- | --- | --- | --- | --- |
| application | 4383361 | 25000/25000 | 0 | 1 |
| application_description | 7485828 | 25000/25000 | 0 | 1 |

The joined mapping produced 11592 candidate observations from 600 sampled records; status: PARTIAL_REVIEW_REQUIRED. Join planning used 6374 tokens; joined-source mapping used 470541 cumulatively, including the initial 312017-token pass and targeted recovery. The 25,000-record anchor is a patent-prefix cohort. It is not representative of all IP rights. A valid join does not establish ownership, business identity or current enforceability.

## Business-question acceptance

These checks require source evidence, the intended owning entity, necessary period/currency context and a declared path to a business. Row co-occurrence alone never establishes identity. Supported means structurally available in this candidate; semantic truth still needs review. Exact headcount and beneficial ownership are deliberately unsupported where the source does not supply them.

| Source | Question | Rows with values | Meet evidence contract | Connected to business | Outcome |
| --- | --- | --- | --- | --- | --- |
| acnc_ais2024_new | Reported gross income and assets, with currency, period and consolidation context? | 0 | 0 | 0 | UNSUPPORTED |
| acnc_ais2024_new | Reported employee and volunteer counts? | 502 | 502 | 0 | PARTIAL |
| wgea_employers_new | What employee size band and reporting period are supplied? | 600 | 0 | 0 | PARTIAL |
| wgea_employers_new | What is the exact employee headcount? | 0 | 0 | 0 | UNSUPPORTED |
| ip_party_activity_new | What party role and role-validity dates are recorded? | 600 | 0 | 0 | PARTIAL |
| ip_party_activity_new | What application status and description are linked to the party record? | 0 | 0 | 0 | UNSUPPORTED |
| ip_party_activity_new | What source-stated application status is available? | 0 | 0 | 0 | UNSUPPORTED |
| ip_party_activity_new | Who is the verified ultimate beneficial owner of the IP? | 0 | 0 | 0 | UNSUPPORTED |
| ip_joined_view | What party role and role-validity dates are recorded? | 596 | 0 | 0 | PARTIAL |
| ip_joined_view | What application status and description are linked to the party record? | 0 | 0 | 0 | UNSUPPORTED |
| ip_joined_view | What source-stated application status is available? | 598 | 598 | 0 | PARTIAL |
| ip_joined_view | Who is the verified ultimate beneficial owner of the IP? | 0 | 0 | 0 | UNSUPPORTED |

A charity/reporting-unit/party node is not automatically the business subject. Disconnected facts require an explicit, evidence-supported relationship or identity design before profile use. The question checks expose this gap even where the mapping critic accepted individual groups.

## Human review required

| Source | Candidate observations | Visible observations connected to business | Self-edges requiring graph review |
| --- | --- | --- | --- |
| ACNC | 20193 | 2021 | 0 |
| WGEA | 11996 | 0 | 0 |
| IP party | 7397 | 0 | 0 |
| IP joined | 11592 | 0 | 600 |

These are graph-connectivity checks, not links into the existing 50 production profiles. Self-edges cannot express a separate description entity and need semantic reconciliation. Privacy-suppressed values do not count as profile-visible evidence.

| Review unit | Pending contracts |
| --- | --- |
| concept | 91 |
| binding | 114 |
| relationship | 6 |

6 unresolved groups require technical/semantic correction before sign-off. Review the proposed meaning and ownership first, then the source bindings (units, guards, periods, joins), then a stratified sample of emitted claims and abstentions. The CSV inventory leaves verdict, reviewer and time blank; no measured human precision or working-time saving is available.

0 contract keys have conflicting definitions across these independently run registries. Any conflicting variants would require reconciliation before combining registries. Review actions can select a specific fingerprint; no variant is automatically approved.

The review-memory demonstration uses temporary synthetic decisions only, with one variant per key. It checks an unchanged repeat and one changed binding; it does not estimate real review effort or approve candidates.

| Synthetic scenario | Unchanged approvals reused | Changed items reopened |
| --- | --- | --- |
| Repeat same contracts | 211 | 0 |
| Change one binding context | 210 | 1 |

## Reproduce the evaluation

Run `python -m scripts.evaluate_grouped_ontology` for offline metrics/replay. Use `python -m firmable.evolution2 replay --output outputs/experiments/grouped-ontology/recovery` to check recovery evidence. No API call is needed. Live commands and budget controls are documented in docs/ONTOLOGY_IMPROVEMENT_PLAN.md. Downloaded source files are ignored; recorded sample evidence supports replay.

Detailed artifacts: evaluation.json; business-question-checks.json (including examples); review-queue.json; human-review-inventory.csv; per-run usage.jsonl and checkpoints; ip-joins/join-plan.json, join-results.json and view-lineage.jsonl. No production promotion, commit or push was performed.
