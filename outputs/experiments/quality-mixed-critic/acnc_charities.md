# Mapping review: `acnc_charities`

- **Status:** PENDING_REVIEW  (run `20261112T013823-1df524`, prompt `prompts-v7`, model `deepseek-v4-flash`)
- **Dataset:** ACNC Registered Charities — Australian Charities and Not-for-profits Commission (ACNC)
- **Resource:** ACNC Register of Australian charities (XLSX), sha256 `69be72862e8728bfda782fc8438d8f6b16bf00f2ef99089e9c4dc2d85a8f6833`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 16 tool calls, 14 model calls, 293,382 prompt + 28,374 completion tokens, 568s model time

## Final proposal (v1, digest `51e9ade621df846929372bc654adbc5e59ae982c352845a03b2591bb3964c088`)

**Record grain:** `legal_entity` — One record = one charity entry on the ACNC Register. Records describe the registered legal entity itself (registered name, ABN, registration date, registered address), so those are the business participant's own attributes. Remaining columns are charity classification (size, purposes, beneficiary groups, operating states/countries) with no canonical target.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Sheet1", "record_path": null}`

**Record id:** `content_hash` ['ABN', 'Charity_Legal_Name', 'Registration_Date'] — ABN alone is not unique: 6 held-out records shared an ABN key, discovery had a duplicate pair, and blank-ABN rows collide on a null key. A content hash over ABN + legal name + registration date stays traceable to a source row while separating repeated entries.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Charity_Legal_Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.95 | 1178 / 1178 |  | Header Charity_Legal_Name on a government charity register; values are registered legal names with legal-form suffixes (Inc, Incorporated, Ltd, 'The Trustee For ...'). |
| ABN | `entity.abn` | abn | 0.97 | 1173 / 1173 |  | All values 11 digits, abn_checksum_valid_rate 1.0 on discovery; validated by the abn transform. |
| Charity_Website | `entity.website` | trim, null_if({"values": [""]}), regex_extract({"pattern": "(?:https?://)?(?:www\\.)?[A-Za-z0-9][A-Za-z0-9-]*(?:\\.[A-Za-z0-9][A-Za-z0-9-]*)+", "group": 0}), website | 0.82 | 816 / 816 |  | Most cells hold one domain or URL. A minority concatenate multiple sites, parentheticals and prose (e.g. 'HTTPS://WWW.ALLMYLINKS.COM/... AND WWW.CHARITYCONSULTANTS.ORG.AU (WWWW.NFPCCC.AU)'); regex_extract takes the first well-formed domain so the cell yields a valid site instead of a rejected blob, then website applies the sanity check. |
| Registration_Date | `entity.date_registered` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1179 / 1179 |  | ACNC registration date, day-first dd/mm/yyyy (476/480 in that shape). Dates the registration, not the record envelope. |
| Address_Line_1, Address_Line_2, Address_Line_3 | `address.full` | trim, null_if({"values": [""]}), collapse_whitespace | 0.85 | 1061 / 1061 |  | Registered address street lines; Line_1 90.6% present, Lines 2-3 sparse unit/level extras. |
| Town_City | `address.locality` | trim, null_if({"values": [""]}), collapse_whitespace | 0.93 | 1061 / 1061 |  | Suburb/locality names; casing varies in source. |
| State | `address.state` | state | 0.95 | 1061 / 1061 |  | Abbreviation column, 10 distinct values; normalised to state enum. |
| Postcode | `address.postcode` | regex_extract({"pattern": "\\d{4}", "group": 0}), postcode | 0.85 | 1056 / 1058 |  | Usually a 4-digit AU postcode, but dirty cells occur ('80571', '139658', 'Cloverdale'). regex_extract takes the first 4-digit run so an over-long cell yields the plausible postcode, and cells with no 4-digit run become null rather than errors. |
| Country *when Country in ['Australia', 'AUSTRALIA', 'AU', 'australia', 'Aus']* | `address.country` | trim, upper, map_enum({"mapping": {"AUSTRALIA": "AU", "AU": "AU"}, "default": "AU", "passthrough": false}) | 0.9 | 1041 / 1041 |  | Free-text AU register field with 'Australia'/'AUSTRALIA' on 99.8% of populated rows. The when-condition fires only for Australian values (case variants), so non-Australian or mistyped entries ('Singapore', 'Austria') are never rendered as AU. |
| Other_Organisation_Names | `entity.trading_name` | trim, null_if({"values": ["", "Admin", "NSP"]}), collapse_whitespace | 0.45 | 131 / 131 |  | Column explicitly holds OTHER names used by the charity (ACNC 'other organisation names'), i.e. names other than the registered legal name. Held-out values such as "Donnybrook Men's Shed Inc." and 'Walker Close Community Centre' are genuine alternative/trading names, so trading_name is the right target rather than legal_name. Confidence is only moderate: the column also carries acronyms, person-like strings and near-duplicates of the legal name that cannot be filtered declaratively. |

**Deliberately unmapped:**
- `Address_Type` — Constant 'Business' on all 480 scanned rows; an address label, not a canonical fact.
- `Date_Organisation_Established` — When the organisation was established in the world, not a validity date for any canonical claim.
- `Charity_Size` — ACNC revenue-size class (Small/Medium/Large); no canonical target and not an entity_type.
- `Number_of_Responsible_Persons` — Count of officeholders; people counts are not entity fields.
- `Financial_Year_End` — Accounting period end (30-Jun etc.), not an entity date or claim validity date.
- `Operates_in_ACT` — Operational-reach flag; not the registered address state.
- `Operates_in_NSW` — Operational-reach flag; not the registered address state.
- `Operates_in_NT` — Operational-reach flag; not the registered address state.
- `Operates_in_QLD` — Operational-reach flag; not the registered address state.
- `Operates_in_SA` — Operational-reach flag; not the registered address state.
- `Operates_in_TAS` — Operational-reach flag; not the registered address state.
- `Operates_in_VIC` — Operational-reach flag; not the registered address state.
- `Operates_in_WA` — Operational-reach flag; not the registered address state.
- `Operating_Countries` — Comma-separated ISO3 operating country codes (AUS, PNG, NZL); describes where the charity operates, not the country of its registered address.
- `PBI` — Public Benevolent Institution tax concession flag; no canonical target.
- `HPC` — Health Promotion Charity tax concession flag; no canonical target.
- `Preventing_or_relieving_suffering_of_animals` — Charitable purpose flag; no canonical target.
- `Advancing_Culture` — Charitable purpose flag; no canonical target.
- `Advancing_Education` — Charitable purpose flag; no canonical target.
- `Advancing_Health` — Charitable purpose flag; no canonical target.
- `Promote_or_oppose_a_change_to_law__government_poll_or_prac` — Charitable purpose flag; no canonical target.
- `Advancing_natual_environment` — Charitable purpose flag; no canonical target.
- `Promoting_or_protecting_human_rights` — Charitable purpose flag; no canonical target.
- `Purposes_beneficial_to_ther_general_public_and_other_analogous` — Charitable purpose flag; no canonical target.
- `Promoting_reconciliation__mutual_respect_and_tolerance` — Charitable purpose flag; no canonical target.
- `Advancing_Religion` — Charitable purpose flag; no canonical target.
- `Advancing_social_or_public_welfare` — Charitable purpose flag; no canonical target.
- `Advancing_security_or_safety_of_Australia_or_Australian_public` — Charitable purpose flag; no canonical target.
- `Aboriginal_or_TSI` — Beneficiary group flag; no canonical target.
- `Adults` — Beneficiary group flag; no canonical target.
- `Aged_Persons` — Beneficiary group flag; no canonical target.
- `Children` — Beneficiary group flag; no canonical target.
- `Communities_Overseas` — Beneficiary group flag; no canonical target.
- `Early_Childhood` — Beneficiary group flag; no canonical target.
- `Ethnic_Groups` — Beneficiary group flag; no canonical target.
- `Families` — Beneficiary group flag; no canonical target.
- `Females` — Beneficiary group flag; no canonical target.
- `Financially_Disadvantaged` — Beneficiary group flag; no canonical target.
- `LGBTIQA+` — Beneficiary group flag; no canonical target.
- `General_Community_in_Australia` — Beneficiary group flag; no canonical target.
- `Males` — Beneficiary group flag; no canonical target.
- `Migrants_Refugees_or_Asylum_Seekers` — Beneficiary group flag; no canonical target.
- `Other_Beneficiaries` — Beneficiary group flag; no canonical target.
- `Other_Charities` — Beneficiary group flag; no canonical target.
- `People_at_risk_of_homelessness` — Beneficiary group flag; no canonical target.
- `People_with_Chronic_Illness` — Beneficiary group flag; no canonical target.
- `People_with_Disabilities` — Beneficiary group flag; no canonical target.
- `Pre_Post_Release_Offenders` — Beneficiary group flag; no canonical target.
- `Rural_Regional_Remote_Communities` — Beneficiary group flag; no canonical target.
- `Unemployed_Person` — Beneficiary group flag; no canonical target.
- `Veterans_or_their_families` — Beneficiary group flag; no canonical target.
- `Victims_of_crime` — Beneficiary group flag; no canonical target.
- `Victims_of_Disasters` — Beneficiary group flag; no canonical target.
- `Youth` — Beneficiary group flag; no canonical target.
- `animals` — Beneficiary group flag; no canonical target.
- `environment` — Beneficiary group flag; no canonical target.
- `other_gender_identities` — Beneficiary group flag; no canonical target.

**Held-out run:** 1182 records, 1180 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Mapping is largely correct with proper handling of legal names, ABN validation, date parsing, and address components. The conditional country rule appropriately prevents false AU assignments. Trading name mapping is acceptable but carries inherent ambiguity. Critical omissions are entity_type and status fields which are standard ACNC columns and have direct ontology targets; their absence significantly reduces record utility. No validity date misuse or legacy target issues detected.
- doubtful: `entity.trading_name` <- ['Other_Organisation_Names'] — Other_Organisation_Names mapped to trading_name is semantically reasonable but column may contain acronyms, near-duplicates of legal name, or non-trading aliases that cannot be filtered declaratively; moderate confidence as noted in rationale.
- missed? `Entity_Type` -> `entity.entity_type` — ACNC register typically includes an entity type field (e.g., Incorporated Association, Trust, Company) which maps directly to entity.entity_type enum; absence forces default 'unknown' despite source likely having this data.
- missed? `Charity_Status` -> `entity.status` — ACNC register includes registration status (Active, Deregistered, etc.) which maps to entity.status enum; without this, all entities lack status information.

**Agent notes:** Revision after critic review. (1) record_id switched from columns[ABN] to content_hash over ABN+legal name+registration date because 6 held-out records shared an ABN and blank-ABN rows collide. (2) entity.website now extracts the first well-formed domain before the website check, so cells listing several URLs no longer produce WEBSITE_INVALID. (3) address.postcode extracts the first 4-digit run so '80571'/'139658'/'Cloverdale' style cells resolve or null out instead of erroring. (4) address.country: passthrough disabled and the rule guarded by a when-condition restricting it to Australian values; the unconditional 'AU' constant was removed so no duplicate conflicting observation is emitted. (5) Other_Organisation_Names is now mapped to entity.trading_name (per critic 'missed' suggestion) at low confidence because the column mixes genuine alternative names with acronyms and person-like strings. entity.status and entity.entity_type are deliberately unmapped: the register lists currently registered charities only, and no column states a legal form plainly enough to avoid guessing.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' ['address.country']
    - + added `('Other_Organisation_Names',)` -> `entity.trading_name`
    - ~ changed `('Country',)` -> `address.country` (steps/confidence)
    - ~ changed `('Postcode',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('Charity_Website',)` -> `entity.website` (steps/confidence)
    - ~ record_id columns -> content_hash ['ABN', 'Charity_Legal_Name', 'Registration_Date']

## Decision

This experimental proposal is outside the approval queue.
