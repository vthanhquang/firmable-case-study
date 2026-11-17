# Submission review follow-up

This tracks the priorities in `SUBMISSION_REVIEW.md` against the benchmark requirements in `init_doc`.

| Priority | Current evidence | Remaining work |
|---|---|---|
| 1. Human review | The workbook contains seven mappings, 20 triage decisions and 50 active-policy links. Mapping approvals bind to the run, config and source snapshot. Import records named decisions, evidence and review minutes. Normal extraction requires human approval. | Complete the workbook and import it. The benchmark approvals are AI proxy decisions. |
| 2. QBCC identity errors | Strict-v2 sends the five company ABN and licence-holder mismatches to the review queue. The audit includes all five proposed random-to-random links and samples the remaining links by rule family. | Label the new sample for strict-v2 precision. The 48/50 result belongs to the historical strict-v1 proxy audit. |
| 3. Unfamiliar-source intake | `register-source` snapshots a local resource for the same onboarding workflow. The provider URL and per-run token budget are configurable. | Add direct URL and CKAN intake with agent resource selection. |
| 4. Metrics | The report counts recorded calls through the current approval. The write-up uses 9/20 triage false positives when uncertain counts as no, with 6/7 reader and 5/7 key-rule agreement. | Measure cost and review time through human approval. |
| 5. Source errors | Deletion reports value, confidence and provenance changes separately. The corruption experiment shifts one registration-date field and replays reconciliation. | Evaluate other corruption modes if they are relevant to the production rollout. |
| 6. Claim validity | Engine 0.2.0 uses claim-specific validity paths. The held-out gate rejects a deregistered status with an end date. | Review proposed date rules against source semantics, including the experimental ASIC name history. |
| 7. Trading names and confidence | The ACNC review page and README expose the unresolved former-name issue. | Add list and former-name gates, define the confidence floor, and revise affected mappings. |
| 8. Metadata defaults | Legacy constants carry derivation level L3, and profiles still count them as corroboration. | Move defaults out of source observations and apply ontology defaults during profile construction. |
| 9. Unlinked records | The queue covers unlinked sample records with positive evidence from a scored candidate, including conflicting candidates. Rows show the strongest candidate, reason and next action. | Broader recall depends on additional candidate generation. |
| 10. Matcher migration | The configured active policy is strict-v2. The comparison reports cluster changes relative to strict-v1. | Persist append-only pair decisions and input fingerprints, with versioned memberships for rollback. |
| 11. Submission claims | The write-up identifies the sample, observed relationships and proxy reviewer. The README records licence caveats and the QBCC prefix scope. | Confirm final two-page layout and supply the original build hours if available. |
| 12. Recall | The precision audit reports separate strata. Full-register QBCC validation and full ASIC extraction benchmarks are recorded. | Link against the full ASIC and ACNC registers and label a recall sample including DEWR. |
| 13. Critic independence | Critic model selection is configurable. Placeholder, ambiguous type and terminal-status failures have deterministic gates. | Verify a critic from a different family and evaluate on additional independent folds. |
| 14. Transform plugins | The mapping DSL supports the readers and transformations used by the benchmarks. | Design reviewed plugins for formats the DSL cannot express. |
| 15. Key registry | The matcher emits anchored keys, cluster membership and evidence for its decisions. | Add durable aliases, overrides and calibration on a human-labelled gold set. |

For the human pass, open each linked mapping review in the workbook, enter a decision and elapsed minutes, and add verdicts for both audits. Run `python -m firmable.cli review-import <workbook.xlsx> --dry-run` to validate the entries. Run it again without the flag to record decisions and refresh the metrics. Use the evidence note to record any ambiguity or reason for rejection.

The [quality replay](outputs/experiments/quality-final/QUALITY_RUN.md) adds a publisher-row shortlist, a separate semantic holdout, a mixed-model critic trial, evidence-based link scores, and scoped profile claims. Its review sheets identify proxy verdicts and provide fields for the human pass.
