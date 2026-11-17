# Requirements review — 16 November 2026

The core system meets the assignment's architectural intent: runtime agentic mapping, one configurable extractor, conservative matching, and claim-level evidence. The latest demo is a useful review preview, but it is not yet a complete, human-evaluated submission. The largest gaps are evaluation integrity, profile evidence presentation, and keeping the five answers aligned to one declared run.

Authority: `init_doc/study_case_description.txt` and `init_doc/firmable_ontology.yaml`. Reviewed the latest `outputs/raw-data/` artifacts, website data and rendering, relevant implementation, README, WRITEUP, and the raw-data requirements tracker. Treat additional enrichment as an extension to the original assignment; do not imply the brief requires every source column or every possible company attribute.

## Requirement-to-evidence assessment

| Requirement | Current evidence | Assessment |
|---|---|---|
| Part 1: retrieve at least 200 records programmatically; rank 50 | 1,509 catalogue candidates; 50 ranked datasets; IDs, publishers, formats, scores and reasons exported | Implemented |
| Part 1: hand-check a random sample of 20 and report false positives | Seeded sample has 20 AI-assisted positives, zero negatives, zero human verdicts | Human evaluation outstanding. The observed AI result is not human validation or a guarantee about the other 30. |
| Part 2: six diverse downloadable datasets from the shortlist, including non-CSV | All six original sources remain in the current shortlist. Latest demo has eight extracts, including the held-back credit register and a second ATO year. XLSX, JSON and ZIP/TSV are represented. | Implemented; explain original six versus additional extracts |
| Part 2: multi-step agent with validation, revision and human approval | Tool loop, held-out validation, critic, bounded revision, checkpoints, digest-bound CLI decisions, saved traces | Implemented. All eight extension drafts remain pending; recovered ACNC draft needs explicit interpretation. |
| Part 2: machine-readable rules, transforms, confidence, unmapped columns and generic extraction | Eight saved configs; 92,092 observations; all eight frontend config digests agree with their configs | Implemented; remaining semantic decisions are visible but unresolved |
| Part 2: step count, tokens, elapsed time, safe failure boundaries | Per-run checkpoints/tokens/time in source drawers; cumulative per-source cost in raw metrics; resume logic in backend | Partly presented. Final-run cost is not complete onboarding cost; failure/resume story needs a concise visible example. |
| Part 3: proposed links, canonical key, evidence and unlinked reasons | 1,455 links at 0.85; 793 multisource entities; 1,245 explicitly queued records | Implemented. Queue is a selected review set, not every unmatched record. |
| Part 3: 50 human-checked links and measured precision | Audit has 50 blank labels | Required result missing; policy score is not measured precision |
| Part 3: explain entity/relationship model | Constrained membership, typed relationships, recorded evidence; website shows aggregate source connections | Backend evidence exists; entity-level model and relationships are poorly explained in the latest default view |
| Part 4: 50 profiles, field-level confidence/provenance and conflict reasoning | 50 profiles; three contain core-field conflicts; core claims preserve confidence components and resolution metadata | Partial. Website hides conflict reasoning; some enriched profile structures discard claim metadata. |
| Part 4: source removal/error impact | Source-removal replay exists; financial vulnerability report exists | Partial. Removal comparison misses confidence/provenance-only changes; financial report is not the advertised corruption replay. |
| Part 5: six specified answers, relationships, two-page limit | Root WRITEUP addresses the six topics using older benchmark results. Default website Write-up summarizes the extension. | Answers exist across different places/runs; default tab does not answer the full brief |
| Submission: runnable repository, outputs, audit evidence, actual costs/time | 143 tests pass; frontend checks/build pass; detailed README and artifacts exist | Fresh-checkout replay under ten minutes not verified in this review. Complete billing and original build hours remain unrecorded. |

## Prioritized findings

### 1. Preserve human audit decisions before asking anyone to label the current sample — high priority

`firmable/rawdata/match.py:379` calls `audit_sample()` on every matcher replay. At line 424 the function opens the same audit CSV in write mode, then emits empty label/note/reviewer cells. An isolated temporary-directory reproduction confirmed that an existing `CORRECT` verdict and reviewer are replaced with empty strings. No real audit artifact was altered during this reproduction.

The existing workbook importer supports older audits (`firmable/review_workbook.py:16`), not the latest raw matcher audit. The frontend exporter (`frontend/scripts/sync-raw-demo.py:116`) accepts nonempty label strings and counts them, but does not establish valid human verdicts or calculate precision. The latest Write-up always says precision is pending.

Recommended completion: store decisions separately and append-only, bind them to pair IDs, policy and evidence digest, validate verdict/reviewer, preserve them through replay, and compute human precision with numerator/denominator and unresolved cases. Because the sample is stratified by rule, distinguish the simple audited-sample proportion from a population estimate. Add a small supported import/export workflow; a production authentication system is not necessary for this assignment.

### 2. The mandated human evaluations and mapping approvals are still incomplete — high priority

Part 1's 20/20 is explicitly AI-assisted in the artifact and page, with zero human verdicts. The latest Part 3 sample has zero of 50 human labels. All eight extension mappings and their draft crosswalks await review. This is honest disclosure, but it does not fulfil the brief's human measurement requirements.

The latest matcher has ten random-to-random links, while none of those ten is in its current 50-link rule-stratified audit. Every sampled link includes a targeted overlap-cohort record. That is not proof the sample is invalid, but it limits what an overall precision number could demonstrate about random intake. Report sampling strata explicitly and review the ten random-to-random links as an additional stratum if making generalisation claims.

Keep a prominent distinction between AI-assisted review and human review in the Part 1 KPI itself. A human must supply the final labels and approval decisions; another agent pass cannot fill this requirement.

Evidence: `outputs/discovery/category_ranked/audit/metrics.json`, `outputs/raw-data/evaluation/link_audit_strict_v3_raw_50.csv`, `frontend/data/raw-demo.json`.

### 3. The latest profile view omits required explanations; enriched structures also lose metadata — high priority

The latest renderer at `frontend/public/raw-demo.js:259` displays a value score and source, but not the stored mapping/source/link confidence breakdown. Its conflicts table at line 358 shows selected and alternative strings, without the selection reason, losing source records, or their evidence. The earlier benchmark renderer already exposes much of this (`frontend/public/parts.js:528`).

Concrete example: J G KING BUILDING GROUP PTY LTD has a legal-name value confidence of 0.6211. Its JSON records stronger reliability-weighted evidence as the reason for selecting the ASIC spelling, and records the two ATO alternatives' observation IDs. The current drawer does not show that explanation. Reuse the richer earlier claim presentation for the latest run.

There is also a data-structure gap. `firmable/rawdata/profiles.py:199` flattens establishment/licence fields to values and retains a shared observation-ID list. It does not give each field its own profile confidence/provenance object. This affects 164 establishment records and nine licence records in the displayed sample. The original observations retain their confidence, so this is repairable without remapping. Charity-purpose tags are reduced to strings at line 150; 18 sampled profiles have these tags without claim-level evidence in that profile structure.

Financial facts do retain value confidence and provenance in JSON, but the financial table omits their value-confidence values; its evidence disclosure shows mapping confidence only. Derived changes and registration events likewise need accessible claim confidence and supporting inputs. Show separate uncertainty components; explain that the derived value score is a ranking heuristic rather than a calibrated probability.

### 4. The displayed financial corruption experiment does not run a corruption replay — high priority

`firmable/rawdata/profiles.py:331` loads observations but never changes an income observation, invokes a rebuilt profile on corrupted data, or compares before/after winners. It counts profiles with financial facts and checks their existing conflicts. Yet `frontend/public/raw-demo.js:298` says the experiment multiplies reported income by ten.

The finding that these 18 sampled financial profiles lack a second independent financial publisher is useful. Label it a source-dependence assessment until an actual experiment runs. Alternatively, mutate a copied observation for a specified company/period, rebuild under fixed membership, and report changed value, confidence, conflicts and derived growth. Keep original artifacts intact.

### 5. Default Part 5 and the root write-up describe different answers and runs — high priority

`WRITEUP.md:17` describes six sources, 38,032 observations and 644 strict-v2 links. The default website describes eight extracts, 92,092 observations and 1,455 strict-v3-raw links. The run banners help, but there is no single final assignment narrative.

`frontend/public/raw-demo.js:366` omits explicit answers to the agent decomposition/weakest step, hardest source, first bottleneck at 500 sources, matcher migration, next three weeks, and relationship-model rationale. These subjects exist in the root write-up; bring them into the current-run presentation and update the evidence.

For the migration answer, show: frozen observations and input fingerprints → challenger replay → added/removed/split decisions → human override handling → affected profile rebuild → versioned promotion and rollback. Clearly mark what is implemented versus proposed. The brief asks for reasoning; it does not require building a production migration service.

The extension has 7,154,131 tokens and estimated US$11.23 spend. This is not a full-project billed total. Show measured billing separately from estimates and split original assignment work, extension experiments, successful runs, retries/revisions, and per-record replay. Do not sum overlapping ledgers without reconciling them. Record original build hours if known; do not invent them. The Markdown has about 1,053 whitespace-separated words; a rendered two-page limit has not been verified.

### 6. Source-removal counts understate changes to trust and evidence — medium priority

`firmable/rawdata/profiles.py:281` fingerprints core values and selected firmographic values. For establishments/licences it compares counts only. It omits confidence, provenance, contact details, sector-tag dictionaries, and detailed membership effects. Consequently, a profile with an unchanged value but reduced evidence can be labelled unchanged; replacing a location value while preserving the count is also invisible to this comparison.

Report value, confidence, provenance, membership and related-record changes separately. Give each measure a denominator of the fixed 50 sampled profiles. Surface this directly in Part 4 rather than only through the experiments drawer. The earlier benchmark already contains more detailed comparison logic that can inform this work.

### 7. Source graphs need semantic counts and an entity-level drill-down — medium priority

The new source graph correctly states that its line widths count proposed record links and that one company can contribute several. Desktop and phone renders are legible. Keep it.

However, ACNC–DEWR's 304 links represent only 45 distinct canonical businesses. ATO year-to-year contributes 498 of 1,455 links, which is temporal overlap from one publisher. These facts matter to interpretation and should be immediately visible beside the pair count. The existing graph should offer record-link and unique-business counts, and distinguish same-publisher reporting periods from independent-publisher connections.

Add one entity-level example: source records → canonical business → licence/site/program relationships, with scores and refusal reasons. Expose a review-queue view as well as proposed links and the selected unlinked queue. Latest metrics contain 501 candidate REVIEW decisions; those are a different population from 1,245 unlinked records.

### 8. Mapping volume and profile richness need coverage/context visualisations — medium priority

Part 2's source-column bars are accurate as input-utilisation measures, not mapping-accuracy measures: 118/168 includes fields used in rules, filters and identifiers. The page discloses this. Add a compact source-by-field-family matrix so a reviewer can see which source contributes identity, business address, establishments, industry, licences, contacts and financial periods, with core ontology fields distinguished from extensions. Pair coverage with emitted/invalid/dropped/unmapped counts and reasons; more columns is not automatically better.

Preserve visible semantic questions: ACNC business/register addresses are not necessarily operating establishments; ASIC current-name start/deregistration dates remain unread; Victorian trading hours remain unmapped. The ACNC review rationale acknowledges PO boxes but still emits an operating-establishment relationship. That is a concrete human review decision, not a chart problem.

Part 4 has no comparable overview visualisation. Add a field-coverage view with clearly separate denominators for the selected 50 profiles and all 793 multisource entities, plus conflict and source-dependence counts. Existing aggregate data already reports industry-code coverage of only 10/793 (1.3%) and financial-fact coverage of 672/793 (84.7%). Rich examples should not imply uniform completeness.

Location lists also need source date and scope. DEWR observations are dated 27 May 2016. Present those as historical source records rather than implying current offices, and keep register addresses separate from operating sites. Do not infer a unique active-office count from the current establishment-record count.

## Recommended page order

| Part | Global results | Primary visual | Evidence and decisions |
|---|---|---|---|
| 1 | Catalogue, shortlist, AI audit and human audit counts | Discovery stages and audit outcomes; show the 20 as an audited subset | Score breakdown, 50-row previews, seeded audit evidence |
| 2 | Extracts/publishers/formats, observations, validation and approval status | Source contribution matrix plus current column bars | Raw → mapped claim, confidence, transforms, unmapped reason, agent revisions, review instructions |
| 3 | Records, linked businesses, candidate outcomes, measured audit status | Source graph with pair/business toggle; selected entity graph | Link evidence, review/refusal queue, audit decisions and precision by stratum |
| 4 | 50 profiles, populated field families, three conflict-bearing profiles, source dependence | Coverage matrix and source-removal impact | Company claims, dated locations, separate confidence components, winner/loser explanation |
| 5 | Declared run and cost/time scope | Small migration flow and per-source cost table | Six brief questions in order, relationship rationale, reproduction and deliverable index |

Complete audit preservation and truthful measurement first. Then align the write-up and profile evidence, improve coverage/graph interpretation, and finally perform actual human reviews and regenerate results. Do not add more sources merely to increase the headline totals.

## Verification performed and limits

- `python -m pytest -q`: 143 passed in 29.34 seconds.
- `npm.cmd --prefix frontend run check`: passed.
- `npm.cmd --prefix frontend run build`: passed.
- All 92,092 observation records contain the six required provenance-envelope values; none lack field confidence or source reliability.
- The root ontology matches the original supplied ontology byte-for-byte; all eight exported mapping config digests validate.
- All six original selected datasets and the held-back credit source remain in the current 50-dataset shortlist.
- Local page/data/audit endpoints checked returned HTTP 200. Local server was restarted at port 4191 after finding it stopped.
- Visually inspected desktop Discovery, Mapping, Identity, a profile drawer and Write-up, plus the Identity page at 390px. Screenshots are under `outputs/requirements-review/`. This is sampled visual review, not exhaustive responsive/accessibility certification; screenshots of the profile show the drawer's initial viewport, with deeper-content findings verified in renderer/data.
- Demonstrated audit-label overwrite only in a temporary directory. Did not rerun the actual raw pipeline or change its labels.
- No new model calls, paid inference, publisher refetch, fresh-checkout replay, independent human audit, or hosted redeployment were performed. Tests passing does not resolve the measurement and semantic findings above.
