# Part 5 — Write-up

Results from the corrected replay, including subsequent work beyond the original six-hour exercise.

## 1. Cost

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

## 2. Agent design

Inspect files, test readers, profile samples, propose mappings, validate held-out rows, critique semantics, revise, then seek human approval. This separates format, execution and interpretation errors. Provider errors retry; exhausted runs checkpoint. Humans see rules, samples, confidence, unmapped fields and validation/critic findings. Semantics is weakest: seven executable mappings needed corrections, including contact addresses treated as sites.

## 3. The hard one

ASIC supplied a ZIP with tab-separated .csv data and historical-name rows. Reader settings and conditional mappings handle both. Use a custom reader only when the shared configuration cannot represent a format reliably; preserve the canonical output contract.

## 4. Scale

Acquisition fails first: three of nine initial attempts hit HTTP errors or bot challenges; QBCC's fallback was a biased 32k-row prefix. At 500 sources, add publisher queues, pagination, caching, retry limits and schema/freshness checks. Review needs prioritisation; matching needs persistent candidate indexes and incremental processing.

## 5. Change

Preserve immutable snapshots/observations, mapping/model/policy versions, candidate evidence, scores, refusals, memberships and human decisions. Run both matchers on identical evidence; compare changed links and cluster splits/merges. Evaluate frozen human labels, review high-impact differences and promote gradually. Rebuild affected profiles, retain old memberships for rollback and publish key aliases/tombstones. Reuse human decisions only while evidence remains applicable.

The implemented comparison retains 1,205 links, adds 250 and removes 363. Evidence-bound review journals exist; automatic corrections, persistent membership history and production rollback remain future work.

## 6. Next

Week 1: regressions for four failed links and reviewed cluster corrections. Week 2: reliable fetching, schema-drift detection and review/resume controls. Week 3: nested-field confidence, financial-corruption testing and matcher migration with rollback. Correct known errors before scaling.

[Parts 1–4 and supporting evidence](docs/ASSIGNMENT_ANSWERS.md).

## Entity relationships

Identity uses constrained clusters with canonical keys; licence/site/programme relationships are separate. Conflicting valid identifiers block merges, and unsupported parent/subsidiary ownership is withheld.
