## Review findings and next engineering priorities

**Overall assessment: partial generalisation, not reliable unattended onboarding.** One source passed after a reusable reader correction. The other two exposed controller limitations. This test does not establish a successful three-source ontology chain or human-measured mapping precision.

| Finding | Evidence | Consequence / next correction |
| --- | --- | --- |
| Repeated spreadsheet columns lost data | WGEA's 24 columns became 20; 0.244 in the current year was overwritten by a blank prior-year cell | Fixed in the shared CSV/XLSX reader. Keep the independent workbook comparison as a regression check. |
| Abstention and malformed values share one acceptance denominator | ACNC validation withheld 728 financial claims across 26 of 140 validation records because the reporting-period field was blank; error rate remained 728/8,870 = 8.2074% | Separate withheld claims from malformed values and report both. Keep unknown-period claims withheld; do not fill periods merely to pass the gate. |
| Revision feedback did not resolve a repeated invalid proposal | IP submitted observation.valid_from / observation.valid_to as field targets; rounds 2–4 repeated the same mapping response digest | Return exact offending field indices and supported alternatives, then detect unchanged proposals and stop early. No IP mapping was manually repaired. |
| One source can exhaust the shared allowance | ACNC completed four evaluations and began a fifth round; the experiment's pre-call soft budget stopped further calls at 1,076,093 reported tokens | Add per-source spending shares and a no-progress exit. WGEA and IP were not attempted in that original process; separate bounded processes supplied their actual tests. |
| Some critic statements are unreliable | An early ACNC critic treated missing-period refusals as incorrect mapping and claimed source-field provenance ambiguity despite source_fields being retained. A later critic accepted the abstentions. | Keep deterministic evidence and independent review; an accepting or rejecting critic is not ground truth. |
| Source coverage and model-sample coverage differ | Full-source ABN overlap is 19 ACNC and 21 WGEA profiles; the patent-only IP prefix matches none of the existing 50 | Do not describe sample links as full coverage. Expand IP sampling and support application/party/description joins before claiming comprehensive IP enrichment. |

### WGEA validation and demonstration

- Repaired-reader run: 600 sampled records; 10 new concepts; 13,948 observations; two proposal/mapping rounds; 0/2,556 rejected present values in 109 sealed-test records.
- Independent original-workbook check: 20 seeded test records, 468 emitted claims, zero value mismatches and zero pay-gap-year mismatches. This is automated validation, not a human audit or semantic precision estimate.
- Same agent-authored mapping applied to a targeted cohort: 21 existing company ABNs, 500 observations. No additional model calls or modifications to the original 50 profiles.
- Workbook scope is narrower than the WGEA dashboard: this experiment does not ingest board composition or workplace policies. Corporate-group worksheets were not joined. Size-band reporting-year context is retained in source metadata, rather than a per-field period qualifier.
- All claims remain candidates with human review pending. Source provenance, period/currency qualifiers and separate confidence components remain available.

### Verification

The shared-reader correction passed the full Python suite: 189 tests. It includes new repeated-header and suffix-collision regressions. The accepted WGEA run is sealed and replays offline; the failed runs retain their checkpoints and reasons. No production promotion, commit or push was performed.
