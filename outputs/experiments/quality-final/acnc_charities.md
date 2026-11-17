# Mapping review: `acnc_charities`

- **Status:** PENDING_REVIEW  (run `20261112T022145-16f920`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** ACNC Registered Charities — Australian Charities and Not-for-profits Commission (ACNC)
- **Resource:** ACNC Register of Australian charities (XLSX), sha256 `69be72862e8728bfda782fc8438d8f6b16bf00f2ef99089e9c4dc2d85a8f6833`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 10 tool calls, 11 model calls, 182,997 prompt + 23,130 completion tokens, 270s model time

## Final proposal (v1, digest `d039c04d1ab6c98a06739da2ea867c7c42a8572a6596aac677f3cb45705f2a7f`)

**Record grain:** `legal_entity` — One record per ACNC register row for a registered charity: the registered legal entity identified by its ABN, with its registered legal name, contact address, ACNC registration date and website. Attribute flags (operating states/countries, charitable purposes, beneficiary classes, size, PBI/HPC concessions) describe the entity or its registration, not separate business records, so they are not mapped.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Sheet1", "record_path": null}`

**Record id:** `content_hash` [] — ABN is checksum-valid but NOT unique per record on held-out data: the holdout run reported 6 records sharing a key built from ['ABN'], i.e. the register carries repeated ABN rows. A non-unique key silently merges distinct records, so record identity comes from the full-row content hash, which is traceable to the exact source row. ABN remains mapped as a field.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| ABN | `entity.abn` | trim, abn | 0.97 | 1173 / 1173 |  | Column labelled ABN; 11 digits and 100% ABN checksum validity on discovery and holdout. |
| Charity_Legal_Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.94 | 1178 / 1178 |  | Publisher states the register presents the charity's formal legal name; column explicitly named Charity_Legal_Name and values carry legal suffixes (Incorporated, Ltd, Inc., 'The Trustee For ...'). |
| Charity_Website | `entity.website` | trim, null_if({"values": [""]}), website | 0.88 | 815 / 816 | {'WEBSITE_INVALID': 1} | Column named Charity_Website; values are bare domains or http(s) URLs, 70% present. The single junk holdout value combining three URLs and a parenthetical is rejected by the website sanity check; no automated rule can pick which URL is authoritative, so rejection is the correct outcome and is visible in the error report. |
| Registration_Date | `entity.date_registered` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.93 | 1179 / 1179 |  | All non-null discovery values are dd/mm/yyyy; publisher guidance distinguishes the effective ACNC registration date (this field) from the organisation's establishment date, and values such as 28/02/2024 confirm day-first. |
| Address_Line_1, Address_Line_2, Address_Line_3 | `address.full` | trim, null_if({"values": [""]}), collapse_whitespace | 0.85 | 1061 / 1061 |  | Street lines of the charity's registered contact address (Address_Line_1 present 90.6%, lines 2/3 sparse). Publisher notes the register address is contact information, hence entity_contact_address scope. |
| Town_City | `address.locality` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.9 | 1061 / 1061 |  | Town_City holds suburb/locality strings (Sydney, Melbourne, Engadine); 90% present. Inconsistent casing and typos in the source (e.g. 'DONNYBROOK', 'Goowa') are preserved as-is; that is a data-quality property of the register, not evidence for a wrong mapping. |
| State | `address.state` | trim, state | 0.93 | 1061 / 1061 |  | 10 distinct values dominated by NSW/VIC/QLD/WA/SA/TAS abbreviations (a holdout value 'SA ' with trailing whitespace resolves after trim); normalised to the state enum, unknown values to OTHER. |
| Postcode | `address.postcode` | trim, postcode | 0.88 | 1056 / 1058 | {'POSTCODE_INVALID': 2} | 436/480 discovery values are 4 digits; malformed outliers seen on discovery and holdout ('139658', '80571', and the literal text 'Cloverdale') are rejected by the postcode transform rather than emitted as bad postcodes. Rejection is preferred over guessing a nearby postcode. |
| Country | `address.country` | trim, collapse_whitespace, upper, map_enum({"mapping": {"AUSTRALIA": "AU", "AU": "AU", "AUS": "AU"}, "default": "OTHER", "passthrough": false}) | 0.8 | 1058 / 1058 |  | Country is present on 88.7% of discovery rows and is Australia/AUSTRALIA apart from one Singapore. The previous passthrough admitted a holdout value 'Austria' verbatim for a record whose street, city, state and postcode (Altona North, VIC 3025) are unambiguously Australian - a real geographic error caused by a free-text field holding mis-keyed or legacy country text. Passthrough is now disabled and unrecognised values collapse to OTHER, so a non-AU country is never asserted as fact against AU address evidence. A constant 'AU' was rejected because the source does carry genuine overseas values (Singapore). |

**Constants:**
- `entity.entity_type` = `unknown` (conf 0.6): No column declares the entity's business form; Incorporated/Ltd/Trust markers appear only inside name text, so the ontology default of unknown is used instead of guessing. Consequently entity.acn is NOT derived from the ABN, since the trailing-9-digits rule holds only for company-type entities and entity form is unknown.

**Deliberately unmapped:**
- `Other_Organisation_Names` — Publisher evidence says the register lists names the charity is publicly known by but does not classify every alternate name as a trading name. Discovery and holdout values mix genuine public-facing names with personal names ('Shannon Schedlich') and junk ('Admin'), there is no row-level flag distinguishing trading use, and the cell is a free-text list of unclear separator (11.5% present, 55 distinct in 480 rows). Emitting these as entity.trading_name would assert trading-name status the source does not establish, so the column is retained as reviewed alias candidates for a human rather than mapped automatically.
- `Address_Type` — Single constant value 'Business' describing the ACNC address record type; no ontology target.
- `Date_Organisation_Established` — Organisation establishment/incorporation date, distinct from ACNC registration; no establishment-date target and must not be conflated with entity.date_registered.
- `Charity_Size` — ACNC revenue-size class (Small/Medium/Large); no ontology target.
- `Number_of_Responsible_Persons` — Count of officers/responsible persons; not a business attribute in the ontology.
- `Financial_Year_End` — Reporting period end day/month; no ontology target.
- `Operates_in_ACT` — Operating-jurisdiction flag attribute; no ontology target (not an address fact).
- `Operates_in_NSW` — Operating-jurisdiction flag attribute; no ontology target.
- `Operates_in_NT` — Operating-jurisdiction flag attribute; no ontology target.
- `Operates_in_QLD` — Operating-jurisdiction flag attribute; no ontology target.
- `Operates_in_SA` — Operating-jurisdiction flag attribute; no ontology target.
- `Operates_in_TAS` — Operating-jurisdiction flag attribute; no ontology target.
- `Operates_in_VIC` — Operating-jurisdiction flag attribute; no ontology target.
- `Operates_in_WA` — Operating-jurisdiction flag attribute; no ontology target.
- `Operating_Countries` — ISO3 list of countries where the charity operates; not the holder's address and no ontology target.
- `PBI` — Income tax concession flag (public benevolent institution); no ontology target.
- `HPC` — Health promotion charity concession flag; no ontology target.
- `Preventing_or_relieving_suffering_of_animals` — Charitable-purpose flag; no ontology target.
- `Advancing_Culture` — Charitable-purpose flag; no ontology target.
- `Advancing_Education` — Charitable-purpose flag; no ontology target.
- `Advancing_Health` — Charitable-purpose flag; no ontology target.
- `Promote_or_oppose_a_change_to_law__government_poll_or_prac` — Charitable-purpose flag; no ontology target.
- `Advancing_natual_environment` — Charitable-purpose flag; no ontology target.
- `Promoting_or_protecting_human_rights` — Charitable-purpose flag; no ontology target.
- `Purposes_beneficial_to_ther_general_public_and_other_analogous` — Charitable-purpose flag; no ontology target.
- `Promoting_reconciliation__mutual_respect_and_tolerance` — Charitable-purpose flag; no ontology target.
- `Advancing_Religion` — Charitable-purpose flag; no ontology target.
- `Advancing_social_or_public_welfare` — Charitable-purpose flag; no ontology target.
- `Advancing_security_or_safety_of_Australia_or_Australian_public` — Charitable-purpose flag; no ontology target.
- `Aboriginal_or_TSI` — Beneficiary-class flag; no ontology target.
- `Adults` — Beneficiary-class flag; no ontology target.
- `Aged_Persons` — Beneficiary-class flag; no ontology target.
- `Children` — Beneficiary-class flag; no ontology target.
- `Communities_Overseas` — Beneficiary-class flag; no ontology target.
- `Early_Childhood` — Beneficiary-class flag; no ontology target.
- `Ethnic_Groups` — Beneficiary-class flag; no ontology target.
- `Families` — Beneficiary-class flag; no ontology target.
- `Females` — Beneficiary-class flag; no ontology target.
- `Financially_Disadvantaged` — Beneficiary-class flag; no ontology target.
- `LGBTIQA+` — Beneficiary-class flag; no ontology target.
- `General_Community_in_Australia` — Beneficiary-class flag; no ontology target.
- `Males` — Beneficiary-class flag; no ontology target.
- `Migrants_Refugees_or_Asylum_Seekers` — Beneficiary-class flag; no ontology target.
- `Other_Beneficiaries` — Beneficiary-class flag; no ontology target.
- `Other_Charities` — Beneficiary-class flag; no ontology target.
- `People_at_risk_of_homelessness` — Beneficiary-class flag; no ontology target.
- `People_with_Chronic_Illness` — Beneficiary-class flag; no ontology target.
- `People_with_Disabilities` — Beneficiary-class flag; no ontology target.
- `Pre_Post_Release_Offenders` — Beneficiary-class flag; no ontology target.
- `Rural_Regional_Remote_Communities` — Beneficiary-class flag; no ontology target.
- `Unemployed_Person` — Beneficiary-class flag; no ontology target.
- `Veterans_or_their_families` — Beneficiary-class flag; no ontology target.
- `Victims_of_crime` — Beneficiary-class flag; no ontology target.
- `Victims_of_Disasters` — Beneficiary-class flag; no ontology target.
- `Youth` — Beneficiary-class flag; no ontology target.
- `animals` — Beneficiary-class flag; no ontology target.
- `environment` — Beneficiary-class flag; no ontology target.
- `other_gender_identities` — Beneficiary-class flag; no ontology target.

**Held-out run:** 1182 records, 1180 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 1 values rejected: {'WEBSITE_INVALID': 1} (`entity.website`)
- [warning] SOME_ERRORS: 2 values rejected: {'POSTCODE_INVALID': 2} (`address.postcode`)

**Critic:** The mapping is largely sound: ABN is checksummed, legal name matches the register's formal name with current_legal_name scope, registration date is correctly day-first and scoped to the ACNC registration claim, and the contact-address fields carry entity_contact_address scope consistent with publisher evidence; entity_type defaults to unknown with no ACN guessed. The one substantive weakness is rule 8: for the 'Austria' holdout the pipeline emits address.country='OTHER', asserting a non-AU country for a record whose street, city, state, postcode and Operating_Countries all indicate Australia — suppression or AU derivation would be safer. The unmapped Other_Organisation_Names is arguably a missed trading_name/alias opportunity, but its heterogeneity (personal names, junk) justifies a cautious, human-reviewed treatment rather than strict error.
- doubtful: `address.country` <- ['Country'] — Collapsing an unrecognised country to OTHER rather than emitting it is defensible, but the holdout record with Country='Austria', Country evidence contradicts the AU street/state/postcode (Altona North VIC 3025) and Operating_Countries='AUS'. Emitting address.country='OTHER' asserts a non-AU country, which is itself a factual claim the source does not support; better would be to suppress the country observation (null) or derive AU from state/postcode evidence. The rationale acknowledges the record is unambiguously Australian yet still emits OTHER, so the emitted claim is misleading.
- missed? `Other_Organisation_Names` -> `entity.trading_name` — The publisher states the register lists names the charity is publicly known by, which is the closest available evidence for public alternate names; several holdout values are genuine public-facing names (e.g. 'Walker Close Community Centre', 'Donnybrook Men's Shed Inc.'). Leaving it entirely unmapped discards the only source evidence for trading_name; a conservative map with a public-name scope would be preferable to nothing, though human review of person-like values is warranted.
- missed? `Date_Organisation_Established` -> `entity.date_registered (no) / review` — Correctly not conflated with registration; no ontology establishment-date target exists, so leaving unmapped is acceptable — listed only to confirm the date-order reading must stay distinct from Registration_Date.
- missed? `Operating_Countries` -> `address.country (no)` — It is an operating-jurisdiction field and must not feed the record address; leaving unmapped is correct. Listed to confirm the country rule should not pull from it.

**Agent notes:** Revisions after holdout review: (1) record_id switched from columns=['ABN'] to content_hash because 6 holdout records shared an ABN key - the register contains repeated ABN rows, and a duplicate key is a correctness error that silently merges rows. (2) address.country passthrough disabled with default OTHER, because passthrough emitted the holdout value 'Austria' verbatim on an otherwise clearly Australian record (Altona North VIC 3025). The critic suggested gating on postcode/state agreement; that cross-check cannot be expressed with the available transforms inside a single field rule, so the safe equivalent is to stop asserting unrecognised free-text countries. (3) Other_Organisation_Names kept unmapped but explicitly documented as alias candidates rather than dropped silently. (4) entity.acn deliberately not derived from ABN because entity_type is unknown. (5) Rejected values remain visible in the error report: 1-2 invalid postcodes and 1 malformed website cell per partition; these are genuine source-data defects, not parse failures that a better rule could fix. entity.status is not mapped: the register lists currently registered charities and carries no entity status column (licence/concession flags such as PBI and HPC are not entity status).

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' ['address.country']
    - ~ changed `('Country',)` -> `address.country` (steps/confidence)
    - ~ changed `('Charity_Website',)` -> `entity.website` (steps/confidence)
    - ~ record_id columns -> content_hash []

## Decision

This experimental proposal is outside the approval queue.
