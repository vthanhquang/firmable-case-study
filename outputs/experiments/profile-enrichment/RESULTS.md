# Company intelligence: unseen-source experiment

This experiment tests the existing multi-step ontology/mapping system on ACNC Annual Information Statements, WGEA employer data and IP Australia party activity. All mappings and ontology proposals are recorded model outputs. Human semantic precision has not been measured; production has not been promoted.

**Conclusion: the system generalises partially, but is not yet reliable for unattended onboarding.** WGEA passed after a generic reader fix. ACNC stalled because safe abstentions counted against the acceptance threshold. IP exhausted its revision allowance on invalid date mappings. These failures are retained, not relabelled as successes.

## Scope and source availability

The engine samples up to 600 records per input, with discovery, validation and sealed test partitions. ACNC and WGEA use the complete downloaded CSV/workbook as sampling inputs. IP uses the first 25,000 party-activity records from its ZIP: this prefix contains patents only, not a representative sample of the full IP collection. It does not include joined application status, descriptions, trademarks or classifications.

| Input | Available records | ABNs also in the existing 50 profiles | Interpretation |
| --- | --- | --- | --- |
| ACNC AIS 2024 | 54233 | 19 | Financials, staffing and activities; charities only |
| WGEA employer sheet | 8617 | 21 | Workforce/pay measures; not all dashboard indicators |
| IP party-activity prefix | 25000 | 0 | Party roles in patent applications; not current enforceability |

These overlap counts describe raw source availability, not accepted enrichment, measured link precision or additions already made to the 50 production profiles.

## Original engine: first bounded pass

| Source | Agent/controller status | Sample | Rounds | New concepts | Observations | Test rejected/present values |
| --- | --- | --- | --- | --- | --- | --- |
| acnc_ais2024_new | INGESTION_FAILED_REVIEW_REQUIRED | 600 | — | — | — | not reached |
| wgea_employers_new | NOT ATTEMPTED — shared budget exhausted | — | — | — | — | not reached |
| ip_party_activity_new | NOT ATTEMPTED — shared budget exhausted | — | — | — | — | not reached |

Zero type/constraint errors do not establish correct meaning, scope or completeness. A controller acceptance is a candidate status, not permission to publish. The independent reader finding below overrides any WGEA baseline acceptance.

## Independent finding and repair

The original XLSX reader collapsed repeated column headings, silently replacing four current-year WGEA pay-gap columns with prior-year values. In the first employer row, a current-year value of 0.244 (24.4%) was replaced by a blank prior-year cell. The 24-column sheet became 20 parsed columns. A model critic cannot recover information already discarded by the reader.

A generic reader correction now assigns collision-safe suffixes to repeated headings in both CSV and XLSX. It preserves positions and values; it does not invent year labels or author mappings. The baseline process had already imported the original reader before this change. Its commit/file hashes and diagnostic example are retained separately. A fresh WGEA process tests the repaired reader against the same workbook.

WGEA retest status: **AGENT_VALIDATED_CANDIDATE**.

Retest: 2 rounds; 10 new concepts; 13,948 observations; sealed-test rejected/present values 0/2556.

## Concrete profile enrichment

The exact accepted WGEA mapping was applied, without further model calls, to all 21 ABN-matching employers in the existing 50 profiles. It produced 500 observations in a separate review artifact. This is a targeted demonstration, not a random precision sample or production merge.

| Existing company | ABN | Reported industry | Employee band | Women in workforce | Average total remuneration (AUD) |
| --- | --- | --- | --- | --- | --- |
| ADVANTA SEEDS PTY LTD | 87010933061 | Other Grain Growing | <250 | 37% | 117000 |
| AUSTRALIAN LEISURE AND HOSPITALITY GROUP PTY LIMITED | 37067391511 | Pubs, Taverns and Bars | 5000+ | 50% | 78000 |
| THE KITCHENARY PTY LTD | 82619485353 | Other Food Product Manufacturing n.e.c. | 250-499 | 50% | 83000 |

Workforce/pay figures are employer-reported for 2024-25; remuneration is not company revenue. Currency AUD is recorded as inferred. The size band remains a band, not an estimated exact headcount. Complete provenance, qualifiers and separate confidence components are in targeted-wgea-profiles.json.

## Independent IP pilot

A separate bounded process tests IP without waiting for ACNC's revision loop or inheriting ACNC's candidate ontology. It uses the repaired shared reader; its CSV headers are unique, so the reader correction does not change this input's columns.

IP pilot status: **NEEDS_REVIEW**.

## ACNC 2024 Annual Information Statement (AIS) Data — baseline

Publisher: Australian Charities and Not-for-profits Commission. [Dataset](https://data.gov.au/data/dataset/276ec1bc-4971-461c-88bc-be9f3c99a0f8/resource/710630ea-1202-4bbb-95f7-3973a972ddf8/download/datadotgov_ais24.csv) · [Documentation](https://www.acnc.gov.au/tools/guides/2024-annual-information-statement-guide) · [Licence](http://creativecommons.org/licenses/by/3.0/au/).

No accepted mapping was produced in this pass.

Experiment token budget exhausted; checkpoints saved


## Employer Gender Pay Gaps Spreadsheet 2024-25 — baseline

Publisher: Workplace Gender Equality Agency. [Dataset](https://www.wgea.gov.au/sites/default/files/documents/Employer-Gender-Pay-Gaps-Spreadsheet.xlsx) · [Documentation](https://www.wgea.gov.au/publications/employer-gender-pay-gaps-report) · [Licence](https://creativecommons.org/licenses/by/4.0/).

No accepted mapping was produced in this pass.

Experiment token budget exhausted; checkpoints saved


## IP RAPID party activity — 25000-record prefix pilot — baseline

Publisher: IP Australia. [Dataset](https://data.gov.au/data/dataset/423000b8-5735-4447-bcb9-792644bcd7ea/resource/c79b3af6-3720-44ac-9e39-6a68f5635924/download/iprapid.zip) · [Documentation](https://www.ipaustralia.gov.au/tools-and-research/professional-resources/data-research-and-reports/open-ip-data) · [Licence](http://creativecommons.org/licenses/by/4.0).

No accepted mapping was produced in this pass.

Experiment token budget exhausted; checkpoints saved


## Employer Gender Pay Gaps Spreadsheet 2024-25 — repaired reader

Publisher: Workplace Gender Equality Agency. [Dataset](https://www.wgea.gov.au/sites/default/files/documents/Employer-Gender-Pay-Gaps-Spreadsheet.xlsx) · [Documentation](https://www.wgea.gov.au/publications/employer-gender-pay-gaps-report) · [Licence](https://creativecommons.org/licenses/by/4.0/).

| New concept | Owner | Meaning |
| --- | --- | --- |
| dyn.workforce.employer_name | business | The employer/reporting-unit name as stated by the publisher for this row. This is a publisher-reported employer name, not a registrar-stated legal name; it is not unique and may coincide with a corporate group name. |
| dyn.workforce.employer_size_band | business | The employer size band stated by the publisher for the reporting employer, kept as the publisher's band label rather than an exact headcount. Values are the WGEA bands as written in the source. |
| dyn.workforce.sector_classification | business | The publisher's sector classification for the reporting employer (e.g. Private, Public). This is a WGEA sector classification, not a legal form and not an ANZSIC industry. |
| dyn.workforce.anzsic_division | business | The ANZSIC Division name stated by the publisher for the employer (e.g. Transport, Postal and Warehousing). Kept as the publisher's division label. Same ANZSIC 2006 scheme as dyn.workforce.anzsic_class, at the coarser division level; neither is crosswalked to a code. |
| dyn.workforce.anzsic_class | business | The ANZSIC Class name stated by the publisher for the employer (e.g. Computer System Design and Related Services). Kept as the publisher's class label. Same ANZSIC 2006 scheme as dyn.workforce.anzsic_division, at the finer class level; neither is crosswalked to a code. |
| dyn.workforce.total_workforce_women_share | business | Share of the employer's total workforce who are women, as a proportion (0-1) stated by the publisher for the reporting period. |
| dyn.workforce.quartile_women_share | business | Share of women (0-1) in a named pay quartile of the employer's workforce, as stated by the publisher for the reporting period. The quartile is identified by the quartile qualifier. |
| dyn.workforce.quartile_average_total_remuneration | business | Average total remuneration in dollars for a named pay quartile of the employer's workforce, as stated by the publisher for the reporting period. This is remuneration, not revenue or business income. Currency is inferred as AUD from the Australian federal publisher; the source header states only '($)'. |
| dyn.workforce.total_workforce_average_total_remuneration | business | Average total remuneration in dollars across the employer's total workforce, as stated by the publisher for the reporting period. Remuneration, not revenue or business income. Currency is inferred as AUD from the Australian federal publisher; the source header states only '($)'. |
| dyn.workforce.gender_pay_gap | business | Gender pay gap as a proportion (0-1, may be negative) stated by the publisher for the reporting period, identified by the remuneration basis (base salary or total remuneration) and the statistic (average or median) qualifiers. A derived gap measure, not a pay level. The publisher already expresses the gap as a proportion despite the '(%)' header (observed values like 0.044, 0.221); a future percent-formatted value would need a percent-to-proportion step. |

### Explicit omissions

| Source column | Reason |
| --- | --- |

### Candidate evidence examples

These are source-scoped extracted claims, not merged or human-approved company profiles.

| Field | Value | Qualifiers | Source columns |
| --- | --- | --- | --- |
| dyn.workforce.employer_name | 1-STOP CONNECTIONS PTY LIMITED | {} | Employer name |
| entity.abn | 58102573544 | {} | Employer ABN |
| dyn.workforce.employer_size_band | <250 | {"scheme": "wgea_employer_size_band"} | Employer size range (# employees) |
| dyn.workforce.sector_classification | Private | {"scheme": "wgea_sector"} | Sector |
| dyn.workforce.anzsic_division | Professional, Scientific and Technical Services | {"scheme": "anzsic2006"} | Industry (ANZSIC Division) |
| dyn.workforce.anzsic_class | Computer System Design and Related Services | {"scheme": "anzsic2006"} | Industry (ANZSIC Class) |
| dyn.workforce.total_workforce_women_share | 0.31 | {"period": "2024-25"} | Total workforce % women |
| dyn.workforce.quartile_women_share | 0.62 | {"quartile": "lower", "period": "2024-25"} | Lower quartile % women |
| dyn.workforce.quartile_women_share | 0.38 | {"quartile": "lower_middle", "period": "2024-25"} | Lower-middle quartile % women |
| dyn.workforce.quartile_women_share | 0.12 | {"quartile": "upper_middle", "period": "2024-25"} | Upper-middle quartile % women |
| dyn.workforce.quartile_women_share | 0.12 | {"quartile": "upper", "period": "2024-25"} | Upper quartile % women |
| dyn.workforce.quartile_average_total_remuneration | 95000 | {"quartile": "lower", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Lower quartile - average total remuneration ($) |
| dyn.workforce.quartile_average_total_remuneration | 154000 | {"quartile": "lower_middle", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Lower-middle quartile - average total remuneration ($) |
| dyn.workforce.quartile_average_total_remuneration | 176000 | {"quartile": "upper_middle", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Upper-middle quartile - average total remuneration ($) |
| dyn.workforce.quartile_average_total_remuneration | 227000 | {"quartile": "upper", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Upper quartile - average total remuneration ($) |
| dyn.workforce.total_workforce_average_total_remuneration | 162000 | {"currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Total workforce - average total remuneration ($)* |
| dyn.workforce.gender_pay_gap | 0.223 | {"remuneration_basis": "base_salary", "statistic": "average", "period": "2024-25"} | Average base salary GPG (%) |
| dyn.workforce.gender_pay_gap | 0.223 | {"remuneration_basis": "total_remuneration", "statistic": "average", "period": "2024-25"} | Average total remuneration GPG (%) |
| dyn.workforce.gender_pay_gap | 0.277 | {"remuneration_basis": "base_salary", "statistic": "median", "period": "2024-25"} | Median base salary GPG (%) |
| dyn.workforce.gender_pay_gap | 0.277 | {"remuneration_basis": "total_remuneration", "statistic": "median", "period": "2024-25"} | Median total remuneration GPG (%) |
| dyn.workforce.gender_pay_gap | 0.16 | {"remuneration_basis": "base_salary", "statistic": "average", "period": "2023-24"} | Average base salary GPG (%)_2 |
| dyn.workforce.gender_pay_gap | 0.16 | {"remuneration_basis": "total_remuneration", "statistic": "average", "period": "2023-24"} | Average total remuneration GPG (%)_2 |
| dyn.workforce.gender_pay_gap | 0.165 | {"remuneration_basis": "base_salary", "statistic": "median", "period": "2023-24"} | Median base salary GPG (%)_2 |
| dyn.workforce.gender_pay_gap | 0.165 | {"remuneration_basis": "total_remuneration", "statistic": "median", "period": "2023-24"} | Median total remuneration GPG (%)_2 |

| Field | Value | Qualifiers | Source columns |
| --- | --- | --- | --- |
| dyn.workforce.employer_name | 233 VICTORIA SQUARE HOTEL PTY LTD | {} | Employer name |
| entity.abn | 39655433711 | {} | Employer ABN |
| dyn.workforce.employer_size_band | 250-499 | {"scheme": "wgea_employer_size_band"} | Employer size range (# employees) |
| dyn.workforce.sector_classification | Private | {"scheme": "wgea_sector"} | Sector |
| dyn.workforce.anzsic_division | Accommodation and Food Services | {"scheme": "anzsic2006"} | Industry (ANZSIC Division) |
| dyn.workforce.anzsic_class | Accommodation | {"scheme": "anzsic2006"} | Industry (ANZSIC Class) |
| dyn.workforce.total_workforce_women_share | 0.51 | {"period": "2024-25"} | Total workforce % women |
| dyn.workforce.quartile_women_share | 0.55 | {"quartile": "lower", "period": "2024-25"} | Lower quartile % women |
| dyn.workforce.quartile_women_share | 0.62 | {"quartile": "lower_middle", "period": "2024-25"} | Lower-middle quartile % women |
| dyn.workforce.quartile_women_share | 0.48 | {"quartile": "upper_middle", "period": "2024-25"} | Upper-middle quartile % women |
| dyn.workforce.quartile_women_share | 0.38 | {"quartile": "upper", "period": "2024-25"} | Upper quartile % women |
| dyn.workforce.quartile_average_total_remuneration | 65000 | {"quartile": "lower", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Lower quartile - average total remuneration ($) |
| dyn.workforce.quartile_average_total_remuneration | 74000 | {"quartile": "lower_middle", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Lower-middle quartile - average total remuneration ($) |
| dyn.workforce.quartile_average_total_remuneration | 81000 | {"quartile": "upper_middle", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Upper-middle quartile - average total remuneration ($) |
| dyn.workforce.quartile_average_total_remuneration | 99000 | {"quartile": "upper", "currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Upper quartile - average total remuneration ($) |
| dyn.workforce.total_workforce_average_total_remuneration | 80000 | {"currency": "AUD", "currency_basis": "inferred", "period": "2024-25"} | Total workforce - average total remuneration ($)* |
| dyn.workforce.gender_pay_gap | 0.064 | {"remuneration_basis": "base_salary", "statistic": "average", "period": "2024-25"} | Average base salary GPG (%) |
| dyn.workforce.gender_pay_gap | 0.074 | {"remuneration_basis": "total_remuneration", "statistic": "average", "period": "2024-25"} | Average total remuneration GPG (%) |
| dyn.workforce.gender_pay_gap | 0.049 | {"remuneration_basis": "base_salary", "statistic": "median", "period": "2024-25"} | Median base salary GPG (%) |
| dyn.workforce.gender_pay_gap | 0.052 | {"remuneration_basis": "total_remuneration", "statistic": "median", "period": "2024-25"} | Median total remuneration GPG (%) |
| dyn.workforce.gender_pay_gap | 0.036 | {"remuneration_basis": "base_salary", "statistic": "average", "period": "2023-24"} | Average base salary GPG (%)_2 |
| dyn.workforce.gender_pay_gap | 0.039 | {"remuneration_basis": "total_remuneration", "statistic": "average", "period": "2023-24"} | Average total remuneration GPG (%)_2 |
| dyn.workforce.gender_pay_gap | 0.026 | {"remuneration_basis": "base_salary", "statistic": "median", "period": "2023-24"} | Median base salary GPG (%)_2 |
| dyn.workforce.gender_pay_gap | 0.045 | {"remuneration_basis": "total_remuneration", "statistic": "median", "period": "2023-24"} | Median total remuneration GPG (%)_2 |

## IP RAPID party activity — 25000-record prefix pilot — independent pilot

Publisher: IP Australia. [Dataset](https://data.gov.au/data/dataset/423000b8-5735-4447-bcb9-792644bcd7ea/resource/c79b3af6-3720-44ac-9e39-6a68f5635924/download/iprapid.zip) · [Documentation](https://www.ipaustralia.gov.au/tools-and-research/professional-resources/data-research-and-reports/open-ip-data) · [Licence](http://creativecommons.org/licenses/by/4.0).

No accepted mapping was produced in this pass.

['Use explicit per-claim validity, not record-wide validity rules', 'Use explicit per-claim validity, not record-wide validity rules']


## Recorded model usage

| Pass | Source | Completed calls | Failed requests | Input tokens | Output tokens |
| --- | --- | --- | --- | --- | --- |
| run | acnc_ais2024_new | 14 | 0 | 954928 | 121165 |
| wgea-retest | wgea_employers_new | 7 | 0 | 161932 | 17927 |
| ip-pilot | ip_party_activity_new | 11 | 0 | 228057 | 28634 |

Model: deepseek-v4-flash through the authorised gateway. Failed-request usage may be unknown. No secrets are included. No new human labels, production promotion, commit or push is performed.

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