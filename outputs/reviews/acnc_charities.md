# Mapping review: `acnc_charities`

- **Revising after human rejection:** Fix address.country only: 'Australia.' (trailing full stop) must become 'AU', and 'WA 6105' (state+postcode typed into Country) must not be emitted as a country. Other letter-only country names (e.g. ARUBA, SINGAPORE) must pass through unchanged (map_enum passthrough true) - do not drop or guess them.
- **Latest review decision:** rejected by claude-code (AI assistant acting for the candidate) (ai_assistant_proxy) at 2026-11-10T01:51:10+00:00 - *for a different config digest; this proposal is not yet decided*
- **Status:** PENDING_REVIEW  (run `20261110T090701-e6e3cc`, prompt `prompts-v5`, model `deepseek-v4-flash`)
- **Dataset:** ACNC Registered Charities — Australian Charities and Not-for-profits Commission (ACNC)
- **Resource:** ACNC Register of Australian charities (XLSX), sha256 `69be72862e8728bf…`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 12 tool calls, 11 model calls, 154,370 prompt + 15,688 completion tokens, 205s model time

## Final proposal (v0, digest `f1d943df55f301f8`)

**Record grain:** `legal_entity` — One row per ACNC-registered charity; the record describes the registered legal entity and its registered business address. ABN is not guaranteed unique (duplicates/blanks occur), so record identity is content-derived.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Sheet1", "record_path": null}`

**Record id:** `content_hash` [] — ABN is blank in ~0.6% of rows and repeats for some entities, so it is not a reliable unique key; hash the full record content instead.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Charity_Legal_Name | `entity.legal_name` | trim, collapse_whitespace | 0.93 | 1178 / 1178 |  | Column explicitly named Charity_Legal_Name on the ACNC register = registered legal name. |
| Other_Organisation_Names | `entity.trading_name` | trim, collapse_whitespace | 0.6 | 131 / 131 |  | Other names the charity is known by (trading/display names), explicitly separate from the legal name column. |
| ABN | `entity.abn` | abn | 0.98 | 1173 / 1173 |  | ABN column; 100% checksum-valid in discovery profile (11-digit shape). |
| Charity_Website | `entity.website` | trim, website | 0.88 | 815 / 816 | {'WEBSITE_INVALID': 1} | Charity_Website holds domains or http(s) URLs. |
| Registration_Date | `entity.date_registered` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1179 / 1179 |  | ACNC registration date; all values match DD/MM/YYYY shape. |
| Address_Line_1, Address_Line_2, Address_Line_3 | `address.full` | trim, null_if({"values": [""]}), collapse_whitespace | 0.68 | 1061 / 1061 |  | Street address lines combined; Address_Type is uniformly 'Business' and some values are PO boxes, so this is a business/contact address. |
| Town_City | `address.locality` | trim, collapse_whitespace | 0.92 | 1061 / 1061 |  | Town/city (suburb) field. |
| State | `address.state` | state | 0.95 | 1061 / 1061 |  | Australian state abbreviations; state transform normalises and maps unknown to OTHER. |
| Postcode | `address.postcode` | postcode | 0.9 | 1056 / 1058 | {'POSTCODE_INVALID': 2} | 4-digit Australian postcodes; one 6-digit source defect fails validation by design. |
| Country | `address.country` | trim, collapse_whitespace, upper, regex_extract({"pattern": "^(.*?)[.\\s]*$", "group": 1}), map_enum({"mapping": {"AUSTR | 0.85 | 1056 / 1058 |  | Reviewer-directed fix. trim/collapse/upper, then strip trailing periods and spaces with regex_extract '^(.*?)[.\s]*$' so 'Australia.' structurally reduces to 'A |

**Deliberately unmapped:**
- `Address_Type` — Single constant value 'Business' on all rows; address contact type, no ontology target.
- `Date_Organisation_Established` — When the organisation was founded, not when ACNC registration became true; not a substitute for date_registered.
- `Charity_Size` — ACNC revenue-size band (Small/Medium/Large); no ontology target.
- `Number_of_Responsible_Persons` — Governance headcount; no ontology target.
- `Financial_Year_End` — Reporting period fit (e.g. 30-Jun); not a valid_from/valid_to date.
- `Operates_in_ACT` — State operation flag; address.state comes from the registered address, not operation footprint.
- `Operates_in_NSW` — State operation flag; not a canonical field.
- `Operates_in_NT` — State operation flag; not a canonical field.
- `Operates_in_QLD` — State operation flag; not a canonical field.
- `Operates_in_SA` — State operation flag; not a canonical field.
- `Operates_in_TAS` — State operation flag; not a canonical field.
- `Operates_in_VIC` — State operation flag; not a canonical field.
- `Operates_in_WA` — State operation flag; not a canonical field.
- `Operating_Countries` — ISO3 country list of operation; no ontology target (address.country is the registered address).
- `PBI` — Tax concession flag; no ontology target.
- `HPC` — Tax concession flag; no ontology target.
- `Preventing_or_relieving_suffering_of_animals` — Charitable purpose Y/N indicator; no ontology target.
- `Advancing_Culture` — Charitable purpose Y/N indicator; no ontology target.
- `Advancing_Education` — Charitable purpose Y/N indicator; no ontology target.
- `Advancing_Health` — Charitable purpose Y/N indicator; no ontology target.
- `Promote_or_oppose_a_change_to_law__government_poll_or_prac` — Charitable purpose Y/N indicator; no ontology target.
- `Advancing_natual_environment` — Charitable purpose Y/N indicator; no ontology target.
- `Promoting_or_protecting_human_rights` — Charitable purpose Y/N indicator; no ontology target.
- `Purposes_beneficial_to_ther_general_public_and_other_analogous` — Charitable purpose Y/N indicator; no ontology target.
- `Promoting_reconciliation__mutual_respect_and_tolerance` — Charitable purpose Y/N indicator; no ontology target.
- `Advancing_Religion` — Charitable purpose Y/N indicator; no ontology target.
- `Advancing_social_or_public_welfare` — Charitable purpose Y/N indicator; no ontology target.
- `Advancing_security_or_safety_of_Australia_or_Australian_public` — Charitable purpose Y/N indicator; no ontology target.
- `Aboriginal_or_TSI` — Beneficiary-type Y/N indicator; no ontology target.
- `Adults` — Beneficiary-type Y/N indicator; no ontology target.
- `Aged_Persons` — Beneficiary-type Y/N indicator; no ontology target.
- `Children` — Beneficiary-type Y/N indicator; no ontology target.
- `Communities_Overseas` — Beneficiary-type Y/N indicator; no ontology target.
- `Early_Childhood` — Beneficiary-type Y/N indicator; no ontology target.
- `Ethnic_Groups` — Beneficiary-type Y/N indicator; no ontology target.
- `Families` — Beneficiary-type Y/N indicator; no ontology target.
- `Females` — Beneficiary-type Y/N indicator; no ontology target.
- `Financially_Disadvantaged` — Beneficiary-type Y/N indicator; no ontology target.
- `LGBTIQA+` — Beneficiary-type Y/N indicator; no ontology target.
- `General_Community_in_Australia` — Beneficiary-type Y/N indicator; no ontology target.
- `Males` — Beneficiary-type Y/N indicator; no ontology target.
- `Migrants_Refugees_or_Asylum_Seekers` — Beneficiary-type Y/N indicator; no ontology target.
- `Other_Beneficiaries` — Beneficiary-type Y/N indicator; no ontology target.
- `Other_Charities` — Beneficiary-type Y/N indicator; no ontology target.
- `People_at_risk_of_homelessness` — Beneficiary-type Y/N indicator; no ontology target.
- `People_with_Chronic_Illness` — Beneficiary-type Y/N indicator; no ontology target.
- `People_with_Disabilities` — Beneficiary-type Y/N indicator; no ontology target.
- `Pre_Post_Release_Offenders` — Beneficiary-type Y/N indicator; no ontology target.
- `Rural_Regional_Remote_Communities` — Beneficiary-type Y/N indicator; no ontology target.
- `Unemployed_Person` — Beneficiary-type Y/N indicator; no ontology target.
- `Veterans_or_their_families` — Beneficiary-type Y/N indicator; no ontology target.
- `Victims_of_crime` — Beneficiary-type Y/N indicator; no ontology target.
- `Victims_of_Disasters` — Beneficiary-type Y/N indicator; no ontology target.
- `Youth` — Beneficiary-type Y/N indicator; no ontology target.
- `animals` — Beneficiary-type Y/N indicator; no ontology target.
- `environment` — Beneficiary-type Y/N indicator; no ontology target.
- `other_gender_identities` — Beneficiary-type Y/N indicator; no ontology target.

**Held-out run:** 1182 records, 1180 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 1 values rejected: {'WEBSITE_INVALID': 1} (`entity.website`)
- [warning] SOME_ERRORS: 2 values rejected: {'POSTCODE_INVALID': 2} (`address.postcode`)

**Critic:** 

**Agent notes:** Reviewer feedback addressed: address.country now uses map_enum with passthrough=true (no '__PASSTHROUGH__' sentinel); listed Australian spellings -> 'AU', other countries preserved as uppercase text. entity.status is NOT mapped: no per-row status column and the extract may include revoked charities, so asserting 'active' would be guesswork. entity_type not mapped: suffixes (Incorporated/Ltd/Trust) are name text, not a structured type field. Columns 29-69 are charitable-purpose/beneficiary Y/N flags with no ontology target. Some Other_Organisation_Names values are person-like (e.g. 'Shannon Schedlich'); trading_name confidence kept moderate for that reason. No per-row observation date; fallback to resource last-modified. Address is a business/contact address (Address_Type uniformly 'Business'), so address.full confidence is moderate. One 6-digit Postcode source defect fails validation by design.

## Scope enforced by the controller: only ['address.country'] may change
- round 0: discarded out-of-scope changes: none

## Second opinion (independent agent run)
- `rerun-v3`: 10/10 rules agree.

## Decision

Approve: `python -m firmable.cli approve acnc_charities --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve acnc_charities --reviewer "<name>" --reject --comment "why"`
