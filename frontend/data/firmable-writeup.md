# Assignment answers — Parts 1–5

Results from the corrected replay, including subsequent work beyond the original six-hour exercise.

## Part 1 — Discovery and triage

Ranked 50 datasets from 1,509 deduplicated CKAN records. Outputs retain IDs, titles, publishers, formats, scores and reasons. The 100-point rubric uses business evidence (45), valid identifiers (20), corporate-name patterns (10), business names (10), identifier–name agreement (10) and catalogue category (5); it is not a probability.

Agentic triage assesses actual file previews instead of relying on potentially ambiguous descriptions. Human review confirmed all 20 sampled resources: 0/20 false positives (0% in this sample). The demo shows up to 50 rows per audited resource.

## Part 2 — Schema inference and mapping

Six sources provide complementary identity, purpose, financial, service and regulatory data across ZIP/TSV, XLSX, CSV and JSON. ASIC Credit and another ATO year extend coverage to eight extracts/seven families:

- **ASIC Companies:** Identifiers, current/former names, registration, legal form and status.

- **ACNC:** Charitable purpose, beneficiaries, size bands, websites, contact addresses and operating regions.

- **ATO, two years:** Total income, taxable income and tax payable, with reporting periods.

- **DEWR:** Employment-service programmes, provider sites, addresses and contacts.

- **QBCC:** Contractor identity, licence categories, grades and addresses.

- **Victorian Liquor:** Licensees, permits, licensed premises and capacity.

- **ASIC Credit:** Credit-licence status, dates, permissions and conditions.

One extractor read 116/168 columns: 85,446 observations from 7,744 saved rows. Roles separate company facts, contact addresses, sites and licences; unsupported fields remain unmapped. Eight mappings are human-verified, including seven maintainer-corrected configurations: an exception to fully agent-authored mapping.

## Part 3 — Entity identification

Threshold 0.85 yields 1,455 links across 793 multi-source entities (736 links within the original six sources). Each link retains both source-record IDs, canonical key, confidence and evidence. The 1,245-record unlinked queue explains refusals: weak evidence, ambiguity or conflicting identifiers.

Constrained clusters use ABN, then ACN, then source-record identity as their key anchor; conflicting valid identifiers block merges. Separate licence, site and programme edges preserve one-to-many relationships. Parent/subsidiary ownership is withheld without direct evidence.

Human-confirmed review found 46/50 links correct (92%). This rule-stratified, overlap-enriched sample is not a population estimate. Four failures remain flagged in the proposed output; confidence scores are policy scores, not calibrated probabilities.

## Part 4 — Company profiles

Fifty profiles combine identity, activities, locations, licences and period-specific finances. Linked-source examples:

### Examples from the saved profiles

- **The Personnel Group Ltd:** ACNC size and operating regions plus 11 DEWR establishment records reveal its documented service footprint.

- **WGA Group Holdings Pty Ltd:** ASIC identity plus two ATO years show total income rising from AUD 138.65m to 145.31m; these are tax measures, not profit.

- **Chinese Association of Victoria Inc:** Charitable purpose combines with a licensed-premises record and BYO permit.

Core/financial claims retain confidence, provenance, alternatives and selection reasons. Reliability-weighted evidence, bounded corroboration and recency determine winners; unsupported facts are absent. Nested site/licence fields retain observation references but still lack complete merged-confidence objects.

Removing ASIC changes 26/50 profiles: 210 field entries disappear, 10 values change and 20 profiles lose multi-source support. Confidence-only changes are excluded. All 25 financially populated profiles depend on ATO; uncorroborated source errors can survive.

## Part 5 — Engineering decisions

### 1. Cost

Model: **deepseek-v4-flash**. Off-peak prices in USD per 1M tokens; input assumes cache miss.

| Period | Input price | Output price |
| --- | ---: | ---: |
| Off-peak | $0.15 | $0.60 |

| Assignment part | Input tokens | Output tokens | Estimated cost (USD) |
| --- | ---: | ---: | ---: |
| Part 1 — Discovery and triage | 353,092 | 20,531 | $0.07 |
| Part 2 — Schema inference and mapping | 12,284,135 | 913,885 | $2.39 |
| Part 3 — Entity identification | 0 | 0 | $0.00 |
| Part 4 — Company profiles | 0 | 0 | $0.00 |
| **Total** | **12,637,227** | **934,416** | **$2.46** |

Estimates include logged experiments and retries. Parts 3–4 make no model calls. Chat assistance is excluded; actual billing is unknown.

[Model pricing reference](https://api-docs.deepseek.com/quick_start/pricing/).

One ASIC onboarding run took 15m 25s and used 282,603 input / 30,424 output tokens: US$0.0606 estimated, included above. Subsequent per-record model cost is zero; compute/storage costs were not measured.

### 2. Agent design

Inspect files, test readers, profile samples, propose mappings, validate held-out rows, critique semantics, revise, then seek human approval. This separates format, execution and interpretation errors. Provider errors retry; exhausted runs checkpoint. Humans see rules, samples, confidence, unmapped fields and validation/critic findings. Semantics is weakest: seven executable mappings needed corrections, including contact addresses treated as sites.

### 3. The hard one

ASIC supplied a ZIP with tab-separated .csv data and historical-name rows. Reader settings and conditional mappings handle both. Use a custom reader only when the shared configuration cannot represent a format reliably; preserve the canonical output contract.

### 4. Scale

Acquisition fails first: three of nine initial attempts hit HTTP errors or bot challenges; QBCC's fallback was a biased 32k-row prefix. At 500 sources, add publisher queues, pagination, caching, retry limits and schema/freshness checks. Review needs prioritisation; matching needs persistent candidate indexes and incremental processing.

### 5. Change

Preserve immutable snapshots/observations, mapping/model/policy versions, candidate evidence, scores, refusals, memberships and human decisions. Run both matchers on identical evidence; compare changed links and cluster splits/merges. Evaluate frozen human labels, review high-impact differences and promote gradually. Rebuild affected profiles, retain old memberships for rollback and publish key aliases/tombstones. Reuse human decisions only while evidence remains applicable.

The implemented comparison retains 1,205 links, adds 250 and removes 363. Evidence-bound review journals exist; automatic corrections, persistent membership history and production rollback remain future work.

### 6. Next

Week 1: regressions for four failed links and reviewed cluster corrections. Week 2: reliable fetching, schema-drift detection and review/resume controls. Week 3: nested-field confidence, financial-corruption testing and matcher migration with rollback. Correct known errors before scaling.
