# Auto-ontology evaluation and human review

## What the experiments establish

The pipeline automates proposal writing, executable mapping generation, validation, evidence capture and candidate replay. It is not yet a reliable unattended onboarding system. The latest trial accepted 1 of 3 sources (33.3%) after external assistance. This is a small, selected experiment outcome, not an estimated production success rate or semantic accuracy.

| Source | Sample | New concepts | Mapping rules | Mapper attempts | Executed evaluations | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| ACNC AIS | 600 | 63 | 91 | 4 | 4 | INGESTION_FAILED_REVIEW_REQUIRED |
| WGEA | 600 | 10 | 24 | 2 | 2 | AGENT_VALIDATED_CANDIDATE |
| IP Australia | 600 | 13 | 15 | 5 | 0 | NEEDS_REVIEW |

All 130 latest mapping rules and 86 proposed concepts were model-authored. This is an authorship count, not proof that they are correct or that 100% of onboarding work is automated. Only WGEA's 10 concepts/24 rules reached an accepted candidate; ACNC's 63 and IP's 13 concepts remain draft proposals. The latest ACNC fifth-round proposal was not mapped before the budget stopped; its last evaluated mapping is from the fourth round.

The original three-source process exhausted its shared budget on ACNC before trying WGEA or IP. WGEA and IP therefore use their separate processes here; the skipped attempts are not counted as extra source failures. The WGEA process used a shared-reader repair. No untouched three-source autonomy rate can be estimated from this run.

Historical context: AusTender, Brisbane grants and NPI eventually produced three accepted candidates after generic controller fixes and explicit resumes (8, 6 and 7 total numbered rounds respectively). Across the six distinct sources, 4/6 eventually reached candidates with supervision; that 66.7% must not be advertised as autonomous success. Accepted sources total 47 new concepts and 32,464 observations. Their 0/6,172 sealed-test rejected values measures types/constraints only, not semantic precision.

## Where automation works and where it stops

| Stage | Measured evidence | Human or engineering role |
| --- | --- | --- |
| Source discovery/intake | 3 sources researched and registered externally; not autonomous discovery | Confirm usefulness, licence, scope and entity granularity |
| Reader and sample | 3/3 created 600-record samples; WGEA originally lost 4/24 columns | Schema-fidelity checks; one external shared-reader repair |
| Ontology/mapping proposals | 3/3 produced drafts: 86 concepts, 130 rules, 2 entity types, 1 relationship type | Assess meaning, reuse, ownership, units, periods and unsupported assumptions |
| Static gates | IP blocked in all 5 mapping rounds | Engineer improves exact-field feedback and repeated-proposal stop; do not ask reviewers to approve invalid mappings |
| Extraction and critic | ACNC and WGEA reached validation; IP did not | Review abstention policy and spot-check critic findings |
| Sealed test / replay | Only WGEA reached test: 0/2,556 rejected values; offline replay succeeds | Check semantics and sampled evidence before approval |
| Production promotion | 0 promoted; no recorded human semantic verdicts | Explicit approval of the exact candidate version |

## The two unresolved technical blocks

ACNC's last validation emitted 8,158 observations from 140 records. It withheld 728 present financial values because 26/140 records (18.6%) lacked reporting periods. The same omission affects 28 rules per affected record: 26 × 28 = 728. The controller rejected an 8.2074% rejection rate against its 5% threshold, although the critic accepted the latest mapping. These are correlated missing-data conditions, not 728 separate manual-review tasks or 728 demonstrated wrong emitted claims. A reviewer should decide the period/abstention policy once, supported by representative examples; an engineer must separate abstentions from malformed values without fabricating dates.

IP repeated a mapping targeting observation.valid_from and observation.valid_to, which the controller forbids as ordinary field targets. Its last three mapping responses were identical. It never reached extraction or the critic, so zero accepted IP observations does not establish that its dataset is unusable. Improve actionable field-level feedback and loop-stagnation detection before semantic sign-off. Agent-versus-applicant roles and activity-versus-enforceability dates still need domain review after a valid mapping exists.

## How much human review is needed

The inventory CSV contains 242 review entries: 86 concept definitions, 23 reuse decisions (including repeated provenance concepts), 130 mapping rules, two entity types and one relationship type. These entries overlap and are not 242 independent tasks. WGEA has 40 entries ready for domain review; the other 202 are draft inventory behind technical blocks. Do not review every superseded proposal or every generated observation.

For WGEA now: review 10 concepts and their 24 mapping rules together, including the reused ABN/provenance semantics; check a 20-record sample with both reporting years, missing values, negative gaps and extreme sizes; then approve or reject its immutable candidate. The existing 468 comparisons across 20 records were automated and cannot be counted as human labels. The targeted 21-profile/500-observation demonstration likewise remains unpromoted.

For ACNC/IP: resolve the technical blocks first, rerun evaluation, and review the final concept/rule bundles. Add focused checks for consolidated financial scope and missing periods (ACNC), and individuals versus organisations, patent agents versus applicants, and historical versus current roles (IP).

### Illustrative effort scenario — not measured working time

Assumptions: source scope 10–15 minutes; each new concept/entity/relationship 2–4 minutes; each mapping rule 0.5–1 minute; 20 record checks at 1–2 minutes each; sign-off 5–10 minutes. Reuse is checked within the mapping review. Complex cases may take longer; reviewing rules with concepts may reduce overlap.

| Source | Calculated reviewer minutes | When |
| --- | --- | --- |
| ACNC AIS | 206.5–408 | After technical blockers are fixed; includes 20 record checks, excludes engineering and new audit findings. |
| WGEA | 67–129 | After technical blockers are fixed; includes 20 record checks, excludes engineering and new audit findings. |
| IP Australia | 74.5–144 | After technical blockers are fixed; includes 20 record checks, excludes engineering and new audit findings. |

Total scenario: 348–681 reviewer minutes (5.8–11.3 hours) for all three after technical repair. Engineering time, source acquisition, further corrections and statistical precision auditing are excluded. These are planning assumptions, not measured savings or a commitment.

## Measurements to add to the next trial

Freeze the engine and preregister new sources before starting. Measure separately: candidate acceptance without intervention; external interventions per source; new-concept accept/modify/reject rates; mapping-rule accept/modify/reject rates; stratified record/claim audit precision; abstention counts and reasons; unsupported-claim errors; ontology reuse/duplication; and elapsed versus active human minutes. Record reviewer verdicts against immutable concept/mapping versions. Label mixed purposive/random samples explicitly; do not treat every field in a record as an independent accuracy trial.

Human time saved requires a comparable manual baseline: (manual active minutes − assisted active minutes) / manual active minutes. Neither baseline minutes nor assisted human minutes were collected, so no 80–90% automation or time-saving claim is supported. The estimated review times above should be replaced with observed timings from the inventory.

## Recorded model usage

| Source | Calls | Input tokens | Output tokens | Cumulative request seconds |
| --- | --- | --- | --- | --- |
| ACNC AIS | 14 | 954928 | 121165 | 652.2 |
| WGEA | 7 | 161932 | 17927 | 194.5 |
| IP Australia | 11 | 228057 | 28634 | 214.2 |

Request times are cumulative model latency, not end-to-end or human working time; some runs overlapped. No new model calls were made for this evaluation. No mapping, approval, production state, commit or push was changed.
