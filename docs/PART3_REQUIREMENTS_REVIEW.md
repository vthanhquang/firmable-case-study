# Part 3 requirements review

Reviewed against `init_doc/study_case_description.txt` and the corrected raw-data replay on 17 November 2026.

**Conclusion:** The current answer and saved outputs satisfy the requested Part 3 deliverables. They demonstrate a reasoned identity model, explicit refusal decisions and measured human-confirmed precision. The result is a set of proposals with disclosed errors, not a claim of production-ready matching.

| Requirement | Verified evidence | Assessment |
| --- | --- | --- |
| Find businesses across the original six sources | 736 proposed links between records in those six sources, spanning 428 current canonical entities. Every original source participates. | Met. The expanded eight-extract run has 1,455 links and 793 multi-source entities; these are explicitly distinguished in the answer. |
| Proposed-link contract | All 1,455 rows contain `source_a_record`, `source_b_record`, `canonical_entity_key`, `confidence` and `evidence`. Every pair joins different source IDs. | Met. Policy version, rule and threshold are also retained. |
| Unlinked queue and reasons | 1,245 unique source records with a refusal reason, best candidate, supporting/contradicting evidence and next action. | Met. This is a deliberate refusal queue, not ingestion errors. |
| Hand-check 50 links and report precision | 50 current human-confirmed verdicts: 46 pass, 4 fail. Acceptance threshold 0.85; audited-sample precision 92%. | Met. Earlier AI checks and subsequent owner confirmations remain distinguishable. |
| Explain the identity representation | Constrained clusters, canonical keys anchored by ABN/ACN/source-record identity, and a pairwise evidence table. Conflicting valid identifiers block merges. | Met. The model supports inspectable decisions and avoids conflating records, sites and legal entities. |
| Handle relationships sensibly | Typed licence, site and programme relationships; ownership is withheld when the sources do not establish it. | Met. Group candidates are hypotheses rather than parent/subsidiary facts. |
| Optional looser-threshold comparison | No separately human-labelled loose-threshold precision estimate is claimed. The same-input strict-v2/v3 comparison changes policy as well as decisions. | Optional. It must not be presented as a threshold-only accuracy experiment. |

## Limits that should remain visible

- The 50-link audit is stratified by rule and includes targeted overlap cohorts. Its 92% precision is not an unbiased estimate for the population, a recall measurement or a separate estimate for the original-six subset.
- The four failed proposals remain flagged in current cluster membership. Applying those corrections is future work; the requirement asks for proposed links and measured errors rather than perfect precision.
- The policy threshold is 0.85, while the lowest currently accepted score is 0.88. Policy scores are not calibrated probabilities.
- No LLM call is required by this part of the brief. Deterministic matching satisfies the requirement when the representation, evidence, refusal policy and evaluation are explained.

## Saved evidence

- `outputs/raw-data/identity/proposed_links.jsonl`
- `outputs/raw-data/identity/unlinked_queue.jsonl`
- `outputs/raw-data/evaluation/link_audit_strict_v3_raw_50.csv`
- `outputs/raw-data/evaluation/link_review_decisions.jsonl`
- `frontend/data/raw-identity.json` (current evidence-bound reviews shown in the demo)
- `docs/ASSIGNMENT_ANSWERS.md` (updated answer and original-six scope clarification)
