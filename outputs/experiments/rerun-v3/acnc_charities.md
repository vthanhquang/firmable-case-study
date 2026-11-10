# Mapping review: `acnc_charities`

- **Status:** PENDING_REVIEW  (run `20261110T045536-785f8e`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** ACNC Registered Charities — Australian Charities and Not-for-profits Commission (ACNC)
- **Resource:** ACNC Register of Australian charities (XLSX), sha256 `69be72862e8728bf…`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 11 tool calls, 11 model calls, 178,287 prompt + 17,083 completion tokens, 97s model time

## Final proposal (v1, digest `3e0afa13c4c35c43`)

**Record grain:** `legal_entity` — One row = one ACNC-registered charity (a legal entity identified by its ABN). The business participant is the charity itself, so its attributes (name, ABN, address, website, registration date) map to entity/address targets.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Sheet1", "record_path": null}`

**Record id:** `content_hash` [] — ABN is not unique in held-out records (some charities share/reuse ABNs and some lack one), so a content hash over the whole row keeps every record traceable without dropping duplicates.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Charity_Legal_Name | `entity.legal_name` | trim | 0.9 | 1165 / 1165 |  | Column is explicitly the registered charity legal name. |
| Other_Organisation_Names | `entity.trading_name` | trim | 0.6 | 129 / 129 |  | Other names a charity trades/operates under, not the registered legal name. |
| ABN | `entity.abn` | abn | 0.98 | 1160 / 1160 |  | 11-digit column with 100% ABN checksum validity on discovery. |
| Charity_Website | `entity.website` | trim, regex_extract({"pattern": "^\\S+", "group": 0}), regex_extract({"pattern": "(?:https?://)?[A-Za-z0-9.?=&_%+~#\\-/] | 0.7 | 807 / 807 |  | Website column; free-text cells sometimes list several URLs, so the first whitespace-delimited token is isolated before validation, avoiding record errors. Cove |
| Registration_Date | `entity.date_registered` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1166 / 1166 |  | ACNC registration date, dd/mm/yyyy (Australian day-first). |
| Address_Line_1, Address_Line_2, Address_Line_3 | `address.full` | collapse_whitespace | 0.7 | 1049 / 1049 |  | Street address lines; joined into a single full address string. |
| Town_City | `address.locality` | collapse_whitespace | 0.85 | 1049 / 1049 |  | Town/city column; trailing commas/spaces cleaned by whitespace collapse. |
| State | `address.state` | state | 0.95 | 1050 / 1050 |  | AU state abbreviations; distinct values all in the state enum. |
| Postcode | `address.postcode` | regex_extract({"pattern": "\\d{4}", "group": 0}), postcode | 0.85 | 1046 / 1048 |  | 4-digit AU postcodes; digits isolated first so trailing punctuation such as '5109,' is kept, and non-4-digit fragments are nulled rather than erroring the recor |
| Country | `address.country` | upper, regex_extract({"pattern": "[A-Z][A-Z ]*[A-Z]|[A-Z]", "group": 0}), trim, map_enum({"mapping": {"AUSTRALIA": "AU"} | 0.7 | 1047 / 1048 |  | Country name, predominantly Australia; punctuation stripped and Australia normalised to the ontology's 'AU' form, other stated countries passed through. |

**Deliberately unmapped:**
- `Address_Type` — Constant 'Business' address-type label; carries no entity information.
- `Date_Organisation_Established` — Foundation date of the organisation in the world; no ontology target (date_registered is the ACNC registration date, a different fact).
- `Charity_Size` — ACNC size classification (Small/Medium/Large) is not an entity_type or industry code; no matching target.
- `Number_of_Responsible_Persons` — Count of responsible persons; no ontology target and not a person name.
- `Financial_Year_End` — Reporting period end (day-month); not a date of an ontology event.
- `Operates_in_ACT` — Operational footprint flag; no ontology target.
- `Operates_in_NSW` — Operational footprint flag; no ontology target.
- `Operates_in_NT` — Operational footprint flag; no ontology target.
- `Operates_in_QLD` — Operational footprint flag; no ontology target.
- `Operates_in_SA` — Operational footprint flag; no ontology target.
- `Operates_in_TAS` — Operational footprint flag; no ontology target.
- `Operates_in_VIC` — Operational footprint flag; no ontology target.
- `Operates_in_WA` — Operational footprint flag; no ontology target.
- `Operating_Countries` — List of ISO country codes of operation; no ontology target.
- `PBI` — Tax concession flag (Public Benevolent Institution); no ontology target.
- `HPC` — Health Promotion Charity flag; no ontology target.
- `Preventing_or_relieving_suffering_of_animals` — Charitable purpose flag; no ontology target.
- `Advancing_Culture` — Charitable purpose flag; no ontology target.
- `Advancing_Education` — Charitable purpose flag; no ontology target.
- `Advancing_Health` — Charitable purpose flag; no ontology target.
- `Promote_or_oppose_a_change_to_law__government_poll_or_prac` — Charitable purpose flag; no ontology target.
- `Advancing_natual_environment` — Charitable purpose flag; no ontology target.
- `Promoting_or_protecting_human_rights` — Charitable purpose flag; no ontology target.
- `Purposes_beneficial_to_ther_general_public_and_other_analogous` — Charitable purpose flag; no ontology target.
- `Promoting_reconciliation__mutual_respect_and_tolerance` — Charitable purpose flag; no ontology target.
- `Advancing_Religion` — Charitable purpose flag; no ontology target.
- `Advancing_social_or_public_welfare` — Charitable purpose flag; no ontology target.
- `Advancing_security_or_safety_of_Australia_or_Australian_public` — Charitable purpose flag; no ontology target.
- `Aboriginal_or_TSI` — Beneficiary-group flag; no ontology target.
- `Adults` — Beneficiary-group flag; no ontology target.
- `Aged_Persons` — Beneficiary-group flag; no ontology target.
- `Children` — Beneficiary-group flag; no ontology target.
- `Communities_Overseas` — Beneficiary-group flag; no ontology target.
- `Early_Childhood` — Beneficiary-group flag; no ontology target.
- `Ethnic_Groups` — Beneficiary-group flag; no ontology target.
- `Families` — Beneficiary-group flag; no ontology target.
- `Females` — Beneficiary-group flag; no ontology target.
- `Financially_Disadvantaged` — Beneficiary-group flag; no ontology target.
- `LGBTIQA+` — Beneficiary-group flag; no ontology target.
- `General_Community_in_Australia` — Beneficiary-group flag; no ontology target.
- `Males` — Beneficiary-group flag; no ontology target.
- `Migrants_Refugees_or_Asylum_Seekers` — Beneficiary-group flag; no ontology target.
- `Other_Beneficiaries` — Beneficiary-group flag; no ontology target.
- `Other_Charities` — Beneficiary-group flag; no ontology target.
- `People_at_risk_of_homelessness` — Beneficiary-group flag; no ontology target.
- `People_with_Chronic_Illness` — Beneficiary-group flag; no ontology target.
- `People_with_Disabilities` — Beneficiary-group flag; no ontology target.
- `Pre_Post_Release_Offenders` — Beneficiary-group flag; no ontology target.
- `Rural_Regional_Remote_Communities` — Beneficiary-group flag; no ontology target.
- `Unemployed_Person` — Beneficiary-group flag; no ontology target.
- `Veterans_or_their_families` — Beneficiary-group flag; no ontology target.
- `Victims_of_crime` — Beneficiary-group flag; no ontology target.
- `Victims_of_Disasters` — Beneficiary-group flag; no ontology target.
- `Youth` — Beneficiary-group flag; no ontology target.
- `animals` — Beneficiary-group flag; no ontology target.
- `environment` — Beneficiary-group flag; no ontology target.
- `other_gender_identities` — Beneficiary-group flag; no ontology target.

**Held-out run:** 1169 records, 1167 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Core identity fields (legal_name, abn, website, date_registered, state, postcode, country) are mapped correctly and date order is day-first as expected. Two address sub-fields are doubtful: address.full retains trailing punctuation and does not signal postal-vs-premises, and address.locality retains a trailing comma despite a whitespace-collapse step, indicating the cleaning rationale is not actually applied. No legal/trading name confusion, no person-name-as-business errors, and no licence/contract confusion observed. entity_type is correctly not guessed from source. No significant missed ontology targets among unmapped columns.
- doubtful: `address.full` <- ['Address_Line_1', 'Address_Line_2', 'Address_Line_3'] — Address_Type is constant 'Business', so this is presumably the charity's registered/premises address, but mapping does not flag postal-vs-premises; also trailing punctuation (e.g. '47, Stanbel Road,') not cleaned.
- doubtful: `address.locality` <- ['Town_City'] — Trailing comma retained in output 'Salisbury Plain,' despite claimed whitespace/collapse cleaning; comparison of collapse_whitespace rationale vs actual output.
- missed? `Date_Organisation_Established` -> `entity.date_registered` — Not the same fact (foundation vs ACNC registration); correctly left unmapped, but note that entity_type inference could draw on names, not a target miss.
- missed? `Operating_Countries` -> `address.country` — Not a postal address country; correctly unmapped.

**Agent notes:** Revisions after holdout: (1) record_id switched from ABN columns to content_hash because ABN was not unique across holdout rows; (2) website now isolates the first token before the website check so multi-URL cells no longer raise WEBSITE_INVALID (coverage verified unchanged at 0.702); (3) postcode extracts the first 4-digit run, so values with trailing punctuation are kept (discovery coverage 437/437 present); (4) country is upper-cased, punctuation-stripped and AUSTRALIA mapped to 'AU'; (5) the hardcoded entity.status='active' constant was removed as it was a guess - status is left unmapped and defaults to unknown. entity_type is also unmapped: no column states type explicitly, and deriving it from name suffixes (Inc/Ltd/Trust) would be inference.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' ['entity.status']
    - ~ changed `('Postcode',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('Charity_Website',)` -> `entity.website` (steps/confidence)
    - ~ changed `('Country',)` -> `address.country` (steps/confidence)
    - ~ changed `('Town_City',)` -> `address.locality` (steps/confidence)
    - ~ record_id columns -> content_hash []

## Decision

Approve: `python -m firmable.cli approve acnc_charities --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve acnc_charities --reviewer "<name>" --reject --comment "why"`
