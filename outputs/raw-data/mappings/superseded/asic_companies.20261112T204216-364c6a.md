# Extension mapping review: `asic_companies`

- **Status:** PENDING_REVIEW - awaiting a human decision (run `20261112T204216-364c6a`, prompt `ext-prompts-v1`, model `deepseek-v4-flash`, critic `deepseek-v4-flash`)
- **Dataset:** ASIC - Company Dataset - Australian Securities and Investments Commission (ASIC); snapshot sha256 `bb7935a163292c6d195bd2d5788863164f191198b3f29257fb332785f998bcea`
- **Extends approved mapping:** run `20261110T035442-7cd099`, digest `ccd07371fbc95e2e`; registry `ext-v1` (draft concept definitions)
- **Agent effort:** 1 proposal(s), 12 tool calls, 11 model calls, 167,972 prompt + 13,689 completion tokens, 189s model time

- **Proposal digest:** `60de0d744d54486c93f32e9452ef5ef5a4f30e28b98ffe7091a3b0d42be9537f` (round 0)

## What changes relative to the approved mapping

- removed rule #7 `observation.valid_from` - Legacy observation.valid_from rule; the engine ignores it. Superseded by the dated former_name claim (valid_to from Current Name Start Date).
- removed rule #8 `observation.valid_from` - Legacy observation.valid_from rule; the engine ignores it.
- removed rule #9 `observation.valid_to` - Legacy observation.valid_to rule; the engine ignores it. The deregistration date is not record-level validity for a name row.
- 7 rule(s) added (table below)

## Added and changed rules

| # | target | role | source columns | transform | qualifiers | conf. | held-out present / emitted / errors / dropped | rationale |
|---|---|---|---|---|---|---|---|---|
| 7 | `ext.entity.former_name` | subject | Company Name when Current Name Indicator not_equals ['Y'] | collapse_whitespace -> trim |  | 0.9 | 431 / 431 / 0 / 0 | On rows where Current Name Indicator is blank, Company Name holds the superseded registered legal name and Current Name holds the name that replaced it; Current |
| 8 | `ext.entity.legal_form_detail` | subject | Class | trim -> crosswalk(asic_company_class, key_label) |  | 0.85 | 1163 / 1163 / 0 / 0 | ASIC company class code; every discovery value (LMSH, LMGT) is a key of asic_company_class. Emits 'CODE: label' as legal_form_detail. |
| 9 | `ext.entity.legal_form_detail` | subject | Sub Class | trim -> crosswalk(asic_company_subclass, key_label) |  | 0.8 | 1163 / 1163 / 0 / 0 | ASIC subclass code identifying share/structure detail (PROP, PSTC, ULSN, LISN, LIST, ULST...); keys match asic_company_subclass. legal_form_detail is multi so c |
| 10 | `ext.entity.status_detail` | subject | Status | trim -> crosswalk(asic_company_status, key_label) |  | 0.9 | 1163 / 1163 / 0 / 0 | Registrar's full status code (REGD, DRGD, EXAD, SOFF all present in discovery) decoded to 'CODE: label'; keeps distress detail the coarse entity.status enum fla |
| 11 | `ext.entity.legal_form` | subject | Type | trim -> crosswalk(asic_company_type, code) |  | 0.85 | 1163 / 1163 / 0 / 0 | ASIC company type (APTY, APUB in discovery) decoded through asic_company_type to the legal_form enum; crosswalk_required target. |
| 12 | `ext.entity.prior_registration_state` | subject | Previous State of Registration | trim |  | 0.85 | 1161 / 1161 / 0 / 0 | State of original incorporation before the national scheme; the extension registry has a dedicated non-address target, so this no longer conflates with address. |
| 13 | `ext.entity.prior_registration_number` | subject | State Registration number | collapse_whitespace -> trim |  | 0.8 | 1162 / 1162 / 0 / 0 | Legacy state-registry number (shapes like C0262066K, 09724136); the registry target exists for exactly this, and trim removes the trailing padding seen in disco |

## Held-out validation (rules in this review)

- no issues

## Critic

> All seven added rules are structurally correct in role and target, and none exhibits the classic failure modes: Company Name on former-name rows is legally a superseded registered name mapped to ext.entity.former_name (never trading_name) with the replacement date as valid_to rather than a stray licence/effective date; class/subclass/type are decoded from registrar code columns via L1 crosswalks into legal_form_detail (multi) and legal_form; status stays detail-level and no deregistered row carries a valid_to; the state and state-registration columns use the dedicated prior-registration extension targets instead of addresses or business identifiers. Residual doubt is concentrated in the rule 1 class crosswalk (draft, mostly unverified keys, overlapping with the subclass detail) and in the fact that the four approved-but-unchanged core rules (ACN, ABN, legal_name via Current Name, date_registered) are not evidenced in this held-out slice, so their continued presence or checksum validation cannot be confirmed here; those source columns are listed as missed/verify items.

- **doubtful** `ext.entity.legal_form_detail` (Class): The emittance is a per-row legal_form_detail, and the class labels (LMSH Limited by shares, LMGT Limited by guarantee) are legitimate. Doubtful because: (a) the class membership/detail overlaps with the Sub Class rule and its 'key_label' output depends on the asic_company_class crosswalk still being draft and unverified against ASIC's help file (only LMSH/LMGT are observed; LMSG, UNLM, NLIA, NONE are unverified guesses); and (b) a value of 'Class' that is not a key of the table would silently produce an out-of-range/unknown label rather than a controlled 'unknown', which for an enumeration-derived detail is a resolution risk. Acceptable shape, but the code table must be verified before it is trusted.
- missed? `ACN` -> `entity.acn`: ACN is the actual 9-digit ASIC company number and the correct identifier for this grain; it is only listed in the approved-rules-kept-unchanged section, not in the added mapping, so confirm it is still applied and checksum-validated (ACN has a weighted checksum), not just length-checked.
- missed? `ABN` -> `entity.abn`: ABN (11 digits) should be emitted with checksum validation per the ontology pattern; it appears only in the approved list. If the column is empty on these held-out rows (no ABN key is present in any raw record), it should be reported as a coverage gap rather than omitted silently.
- missed? `Date of Registration` -> `entity.date_registered`: Registration date drives entity status/lifetime evidence and must be date-parsed as dd/mm/YYYY; it is approved-only here and absent from every held-out raw record, so verify it is not being dropped as all-null.
- missed? `Current Name` -> `entity.legal_name`: On former-name rows Current Name is the only source of the company's current registered legal name, and here it is present on 5 of 12 rows; apart from the approved current-name-becoming-former-name derivation, there is also the edge the approved rule must resolve: the same company's rows supply the current name only via Current Name, so a null Current Name on an indicator='Y' row would leave legal_name unproduced. Confirm coverage.
- missed? `Modified since last report` -> `entity.status (validity/change evidence) or ingestion metadata`: Dropped as 0% populated in discovery, which is defensible for this held-out sample, but if it ever carries a change timestamp it would be the natural period/validity bound rather than an unused column; keep it flagged for re-check on a wider sample.

## Crosswalk tables this mapping relies on

Each table is a separate human-reviewed artefact; approving the mapping does not approve the table.

- `asic_company_class` (code, L1): draft - prepared by an AI assistant; verify against ASIC's help file
- `asic_company_status` (code, L1): draft - prepared by an AI assistant from ASIC's Company Dataset help file wording; verify each label
- `asic_company_subclass` (code, L1): draft - prepared by an AI assistant; entries marked verified false need ASIC's data dictionary
- `asic_company_type` (code, L1): draft - prepared by an AI assistant from ASIC's help file wording; verify

## Still unmapped

- `Modified since last report`: Present on 0% of discovery rows; no data to map.

## Decide

```
python -m firmable.cli raw-approve asic_companies --reviewer "<your name>"
python -m firmable.cli raw-approve asic_companies --reviewer "<your name>" --reject --comment "why"
```
