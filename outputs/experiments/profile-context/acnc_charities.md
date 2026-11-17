# Mapping review: `acnc_charities`

- **Status:** PENDING_REVIEW  (run `20261112T155030-e879bc`, prompt `prompts-v9-profile-context-v1`, model `deepseek-v4-flash`)
- **Dataset:** ACNC Registered Charities — Australian Charities and Not-for-profits Commission (ACNC)
- **Resource:** ACNC Register of Australian charities (XLSX), sha256 `69be72862e8728bfda782fc8438d8f6b16bf00f2ef99089e9c4dc2d85a8f6833`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 8 tool calls, 7 model calls, 82,418 prompt + 10,583 completion tokens, 228s model time

## Final proposal (v0, digest `1b4bededad961f02a7f08293b8187e4e2d4ed246906b7daf283dcea30f60f567`)

**Record grain:** `legal_entity` — One record is one charity as registered with the ACNC, i.e. one legal entity holding charity registration. The address columns are the charity's contact address, not a site or premises record, and the operational and purpose flag columns are attributes of that same registered entity. Record identity is therefore the entity.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Sheet1", "record_path": null}`

**Record id:** `content_hash` [] — ABN was tried first but the full register contains 6 holdout records that collide on ABN: the register includes related/sub-entity rows and rows with no ABN, so ABN is not a unique per-record key across the whole file even though it looked unique in discovery (477 of 477 distinct in 480 rows). content_hash is used instead so every distinct row gets a traceable, stable id without inventing uniqueness. ABN remains mapped as entity.abn where present.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| ABN | `entity.abn` | trim, abn | 0.97 | 1173 / 1173 |  | Column labelled ABN; 477/477 present values are 11 digits with a valid ABN checksum (abn_checksum_valid_rate 1.0), and 0 errors on holdout. Canonical Australian business identifier. Note the same ABN can appear on more than one row, so it is not used as the record id. |
| Charity_Legal_Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NA"]}) | 0.93 | 1178 / 1178 |  | Column is explicitly Charity_Legal_Name and the publisher states the register presents the formal legal name. Scope current_legal_name. Held-out values carry legal-form suffixes (Incorporated, 'The Trustee for ...', 'P&C Association'), consistent with registered names rather than display names. The source gives no start date for the name itself, so no valid_from_path; Registration_Date is deliberately not attached to the name. |
| Registration_Date | `entity.date_registered` | trim, parse_date({"formats": ["%d/%m/%Y"]}), valid_from from Registration_Date | 0.88 | 1179 / 1179 |  | Publisher evidence states the effective registration date is the date with ACNC, explicitly distinguished from the organisation's original establishment. 476/480 discovery values and 1179/1179 holdout values match dd/mm/yyyy (0 errors). The date is when ACNC charity registration became true, hence scope charity_registration and valid_from_path on this claim. |
| Charity_Website | `entity.website` | trim, null_if({"values": ["", "N/A", "nil"]}), website | 0.88 | 815 / 816 | {'WEBSITE_INVALID': 1} | Column is the charity's website; values are bare domains (www.x.org.au) or http(s) URLs. The website op rejects malformed values. One holdout value is prose containing two URLs and a parenthetical ('HTTPS://... AND WWW... (WWWW...)') rather than a single URL; rejecting that is the correct outcome, since coercing it would emit a broken URL as the entity's canonical website. |
| Address_Line_1, Address_Line_2, Address_Line_3 | `address.full` | collapse_whitespace, null_if({"values": ["", "N/A"]}) | 0.72 | 1061 / 1061 |  | Three free-text street lines of the charity's contact address, joined with a single space so multi-line addresses cannot concatenate without a separator; lines 2 and 3 are almost always null so the separator rarely appears. Publisher evidence says the address is contact information, hence scope entity_contact_address. Caveat a reviewer should know: Address_Line_1 often holds a venue/premises or building descriptor rather than a street line (e.g. 'Pembroke School', 'St Christopher's Pastoral Centre', 'Egan Park', 'Community Centre') alongside true street addresses, and some values are PO boxes. The source does not distinguish a licensed/operating premises address from the entity's contact address, so this is mapped as contact_address and not as a premises address; downstream users should not treat address.full as a verified street address. |
| Town_City | `address.locality` | trim, collapse_whitespace, null_if({"values": ["", "N/A"]}) | 0.9 | 1061 / 1061 |  | Town_City is the suburb/locality of the contact address; 362 distinct discovery values and all 1061 holdout values read as Australian localities ('Dubbo', 'Altona North', 'DONNYBROOK'), published case preserved as no canonical casing rule exists. |
| State | `address.state` | trim, state | 0.93 | 1061 / 1061 |  | State column holds AU state/territory abbreviations; holdout includes a trailing-whitespace value ('SA ') which trim then state resolves to SA. state sends anything unrecognised to OTHER rather than guessing. 0 errors on holdout. |
| Postcode | `address.postcode` | trim, postcode | 0.85 | 1056 / 1058 | {'POSTCODE_INVALID': 2} | Postcode is the contact address postcode; the postcode op validates 4-digit AU codes and re-pads 3-digit NT codes. The column is free text and carries occasional junk rather than just formatting noise: holdout rejects were '80571' (5 digits) and 'Cloverdale' (a locality name entered in the postcode field), plus one 6-digit value in discovery. Rejecting these is correct behaviour because coercing a locality name or a 5-digit string into address.postcode would assert a postcode the source never stated; the loss is a fraction of a percent of rows. |
| Country | `address.country` | trim, upper, map_enum({"mapping": {"AUSTRALIA": "AU", "AU": "AU", "SINGAPORE": "SG", "SG": "SG"}, "default": null, "passthrough": false}) | 0.8 | 1040 / 1058 | {'ENUM_UNMAPPED': 18} | Country of the contact address. Discovery shows only 'Australia' in mixed case plus one 'Singapore'. The previous passthrough behaviour asserted any unrecognised string as a canonical country, which turned a publisher typo ('Austria' on an Altona North VIC contact address) into a false country claim. passthrough is now false: only explicitly recognised values are emitted (Australian spellings -> AU, Singapore -> SG because the source genuinely states it) and anything else is left unmapped rather than asserted. Residual uncertainty: an unlisted genuine overseas country would be dropped rather than emitted. |
| Charity_Size | `context.charity.size` | trim, null_if({"values": ["", "NOT APPLICABLE"]}), map_enum({"mapping": {"Small": "Small", "Medium": "Medium", "Large": "Large"}, "default": null}) | 0.92 | 1055 / 1055 |  | Source-declared ACNC charity reporting-size class. |
| Date_Organisation_Established | `context.charity.established_on` | trim, null_if({"values": [""]}), parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1136 / 1136 |  | ACNC distinguishes original establishment date from registration date; format is DD/MM/YYYY. |
| Preventing_or_relieving_suffering_of_animals *when Preventing_or_relieving_suffering_of_animals equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Animal welfare"}, "default": null}) | 0.9 | 28 / 28 |  | Affirmative animal-suffering-relief purpose flag. |
| Advancing_Culture *when Advancing_Culture equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Culture"}, "default": null}) | 0.9 | 116 / 116 |  | Affirmative advancing-culture purpose flag. |
| Advancing_Education *when Advancing_Education equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Education"}, "default": null}) | 0.9 | 233 / 233 |  | Affirmative advancing-education purpose flag. |
| Advancing_Health *when Advancing_Health equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Health"}, "default": null}) | 0.9 | 113 / 113 |  | Affirmative advancing-health purpose flag. |
| Promote_or_oppose_a_change_to_law__government_poll_or_prac *when Promote_or_oppose_a_change_to_law__government_poll_or_prac equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Public policy and advocacy"}, "default": null}) | 0.85 | 14 / 14 |  | Affirmative flag for promoting or opposing change to law/policy. |
| Advancing_natual_environment *when Advancing_natual_environment equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Natural environment"}, "default": null}) | 0.9 | 50 / 50 |  | Affirmative advancing-natural-environment purpose flag. |
| Promoting_or_protecting_human_rights *when Promoting_or_protecting_human_rights equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Human rights"}, "default": null}) | 0.9 | 23 / 23 |  | Affirmative human-rights purpose flag. |
| Purposes_beneficial_to_ther_general_public_and_other_analogous *when Purposes_beneficial_to_ther_general_public_and_other_analogous equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "General public benefit"}, "default": null}) | 0.85 | 125 / 125 |  | Affirmative flag for other purposes beneficial to the public. |
| Promoting_reconciliation__mutual_respect_and_tolerance *when Promoting_reconciliation__mutual_respect_and_tolerance equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Reconciliation and tolerance"}, "default": null}) | 0.9 | 34 / 34 |  | Affirmative reconciliation and tolerance purpose flag. |
| Advancing_Religion *when Advancing_Religion equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Religion"}, "default": null}) | 0.9 | 328 / 328 |  | Affirmative advancing-religion purpose flag. |
| Advancing_social_or_public_welfare *when Advancing_social_or_public_welfare equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Social and public welfare"}, "default": null}) | 0.9 | 259 / 259 |  | Affirmative advancing-social-or-public-welfare purpose flag. |
| Advancing_security_or_safety_of_Australia_or_Australian_public *when Advancing_security_or_safety_of_Australia_or_Australian_public equals ['Y']* | `context.charity.purpose` | map_enum({"mapping": {"Y": "Public safety"}, "default": null}) | 0.9 | 20 / 20 |  | Affirmative public safety purpose flag. |
| Operates_in_ACT *when Operates_in_ACT equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "ACT"}, "default": null}) | 0.9 | 63 / 63 |  | Affirmative ACT operating flag. |
| Operates_in_NSW *when Operates_in_NSW equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "NSW"}, "default": null}) | 0.9 | 380 / 380 |  | Affirmative NSW operating flag. |
| Operates_in_NT *when Operates_in_NT equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "NT"}, "default": null}) | 0.9 | 52 / 52 |  | Affirmative NT operating flag. |
| Operates_in_QLD *when Operates_in_QLD equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "QLD"}, "default": null}) | 0.9 | 201 / 201 |  | Affirmative QLD operating flag. |
| Operates_in_SA *when Operates_in_SA equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "SA"}, "default": null}) | 0.9 | 106 / 106 |  | Affirmative SA operating flag. |
| Operates_in_TAS *when Operates_in_TAS equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "TAS"}, "default": null}) | 0.9 | 65 / 65 |  | Affirmative TAS operating flag. |
| Operates_in_VIC *when Operates_in_VIC equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "VIC"}, "default": null}) | 0.9 | 302 / 302 |  | Affirmative VIC operating flag. |
| Operates_in_WA *when Operates_in_WA equals ['Y']* | `context.charity.operating_region` | map_enum({"mapping": {"Y": "WA"}, "default": null}) | 0.9 | 143 / 143 |  | Affirmative WA operating flag. |

**Deliberately unmapped:**
- `Other_Organisation_Names` — The critic suggested a filtered emission to entity.trading_name, and some holdout values do look like public names ('Donnybrook Men's Shed Inc.', 'Walker Close Community Centre'). I am still leaving it unmapped. Publisher evidence states this column is the names the charity is publicly known by and explicitly does NOT classify every alternate name as a trading name, so emitting trading_name would assert a trading use the source does not establish. The column is also irreducibly heterogeneous: person names ('Shannon Schedlich'), fragments ('Admin', 'NSP'), legal-form-tweaked duplicates of the legal name itself ('Donnybrook Men's Shed Inc.' vs 'Donnybrook Mens Shed Incorporated' - a spelling variant, not a trading name), and trust-entity wrappers. A filter cannot separate spelling variants from genuine trading names without guesswork. If this is wanted downstream it should be modelled as an alias/other-name field, not entity.trading_name.
- `Address_Type` — Constant 'Business' on 480/480 rows; describes the category of the address record, not a canonical entity attribute. Address semantics are already carried by the address.* mappings, and mapping it to entity_type would be a guess.
- `Number_of_Responsible_Persons` — Count of the charity's responsible persons (officers); an attribute of governance, not of the entity's identity, form or status. No ontology target.
- `Financial_Year_End` — Accounting period end (e.g. '30-Jun') is a reporting convention, not a date of the entity or of a claim in the ontology.
- `Operating_Countries` — Comma-separated ISO country codes of countries where the charity operates, not where it is located. address.country is the entity's own address country, so mapping this would be a false location claim. No ontology target for operational reach.
- `PBI` — Private Benevolent Institution tax concession flag; a tax status of the charity, not entity.status (which is registration/liquidation state) and not entity_type.
- `HPC` — Health Promotion Charity tax concession flag; same reasoning as PBI.
- `Aboriginal_or_TSI` — Beneficiary-group flag; describes who the charity serves, not the entity's own attributes.
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

**Held-out run:** 1182 records, 1182 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 1 values rejected: {'WEBSITE_INVALID': 1} (`entity.website`)
- [warning] SOME_ERRORS: 2 values rejected: {'POSTCODE_INVALID': 2} (`address.postcode`)
- [warning] SOME_ERRORS: 18 values rejected: {'ENUM_UNMAPPED': 18} (`address.country`)

**Critic:** All 22 rules are acceptable. Size maps the source's own reporting-size class, and the date parse is verifiably day/month (31/12/1889, 13/11/2006), aligned with the publisher's distinction between establishment and registration. Every purpose flag maps to a semantically matching enum and emits only on affirmative values. Every operating-region flag maps to the corresponding jurisdiction as a service footprint rather than an address. Blank and negative flags correctly emit nothing, and each emitted value is correctly typed. Nothing material was left unmapped: unmapped columns are beneficiary-group flags, tax-concession flags, officer counts, accounting dates, operating-country reach, a constant address category, and the heterogeneous Other_Organisation_Names column; the mapping is right to withhold trading_name there, because publisher evidence says alternate names are not classified as trading names.

**Agent notes:** REVISION after holdout review. Changes: (1) record_id switched from columns[ABN] to content_hash - the error was real, 6 holdout rows collide on ABN because the register contains related/sub-entity rows and rows lacking an ABN. (2) address.country passthrough disabled - the previous passthrough emitted a typo ('Austria' on an Altona North VIC address) as an asserted canonical country; now only explicitly recognised values emit (AU, and SG for the Singapore rows actually present). (3) Rejected WEBSITE_INVALID and POSTCODE_INVALID values are intentional rejections of malformed prose / locality-names-in-postcode, not parser bugs; documented in their rationales. (4) address.full confidence lowered to 0.72 and its rationale now warns that the first line is often a venue/premises or PO box descriptor rather than a street address. (5) Other_Organisation_Names remains unmapped despite the critic's 'missed' suggestion: publisher evidence warns alternate names are not attested trading names, and the column mixes spelling variants of the legal name with person names and fragments, so a filter would require guesswork; the correct model is an alias field. (6) Date_Organisation_Established is a genuine ontology gap (no entity.date_established). No entity.status or entity.entity_type mapping was added: the register has no deregistered/in-liquidation or business-form column, so both stay unasserted rather than guessed.

## Decision

This experimental proposal is outside the approval queue.
