# Mapping review: `acnc_charities`

- **Status:** PENDING_REVIEW  (run `20261112T014653-883226`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** ACNC Registered Charities — Australian Charities and Not-for-profits Commission (ACNC)
- **Resource:** ACNC Register of Australian charities (XLSX), sha256 `69be72862e8728bfda782fc8438d8f6b16bf00f2ef99089e9c4dc2d85a8f6833`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 10 tool calls, 10 model calls, 226,842 prompt + 26,533 completion tokens, 319s model time

## Final proposal (v1, digest `b1e793864dbfa84aefdb44b27a512ab6a51918d5acc7c838cca3b2a44e08536d`)

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

**Deliberately unmapped:**
- `Other_Organisation_Names` — The critic suggested a filtered emission to entity.trading_name, and some holdout values do look like public names ('Donnybrook Men's Shed Inc.', 'Walker Close Community Centre'). I am still leaving it unmapped. Publisher evidence states this column is the names the charity is publicly known by and explicitly does NOT classify every alternate name as a trading name, so emitting trading_name would assert a trading use the source does not establish. The column is also irreducibly heterogeneous: person names ('Shannon Schedlich'), fragments ('Admin', 'NSP'), legal-form-tweaked duplicates of the legal name itself ('Donnybrook Men's Shed Inc.' vs 'Donnybrook Mens Shed Incorporated' - a spelling variant, not a trading name), and trust-entity wrappers. A filter cannot separate spelling variants from genuine trading names without guesswork. If this is wanted downstream it should be modelled as an alias/other-name field, not entity.trading_name.
- `Address_Type` — Constant 'Business' on 480/480 rows; describes the category of the address record, not a canonical entity attribute. Address semantics are already carried by the address.* mappings, and mapping it to entity_type would be a guess.
- `Date_Organisation_Established` — Publisher evidence explicitly distinguishes the original establishment/incorporation date from the effective ACNC registration date, and the ontology has only entity.date_registered, so mapping this there would be wrong (the critic agrees). Flagged by the critic as an ontology gap: if entity.date_established is added it should map there. It is also not a validity start for the legal name.
- `Charity_Size` — ACNC size classification (Small/Medium/Large) is a regulatory reporting category, not an ontology field; there is no entity.size target and it is not entity_type.
- `Number_of_Responsible_Persons` — Count of the charity's responsible persons (officers); an attribute of governance, not of the entity's identity, form or status. No ontology target.
- `Financial_Year_End` — Accounting period end (e.g. '30-Jun') is a reporting convention, not a date of the entity or of a claim in the ontology.
- `Operates_in_ACT` — Presence flag for operating in a state. The ontology has address.state as the entity's address, which is a different assertion; mapping an operating-in-jurisdiction flag to address.state would falsely claim the charity is located there. No ontology target for operational footprint.
- `Operates_in_NSW` — Operational footprint flag; would falsely assert the entity's address/location if mapped to address.state. No target.
- `Operates_in_NT` — Operational footprint flag; same reasoning as Operates_in_ACT.
- `Operates_in_QLD` — Operational footprint flag; same reasoning as Operates_in_ACT.
- `Operates_in_SA` — Operational footprint flag; same reasoning as Operates_in_ACT.
- `Operates_in_TAS` — Operational footprint flag; same reasoning as Operates_in_ACT.
- `Operates_in_VIC` — Operational footprint flag; same reasoning as Operates_in_ACT.
- `Operates_in_WA` — Operational footprint flag; same reasoning as Operates_in_ACT.
- `Operating_Countries` — Comma-separated ISO country codes of countries where the charity operates, not where it is located. address.country is the entity's own address country, so mapping this would be a false location claim. No ontology target for operational reach.
- `PBI` — Private Benevolent Institution tax concession flag; a tax status of the charity, not entity.status (which is registration/liquidation state) and not entity_type.
- `HPC` — Health Promotion Charity tax concession flag; same reasoning as PBI.
- `Preventing_or_relieving_suffering_of_animals` — Charitable purpose/subtype flag. No ontology target for charitable purposes; entity.industry_code is ANZSIC and these flags are not ANZSIC codes.
- `Advancing_Culture` — Charitable purpose flag; no ontology target.
- `Advancing_Education` — Charitable purpose flag; no ontology target.
- `Advancing_Health` — Charitable purpose flag; no ontology target.
- `Promote_or_oppose_a_change_to_law__government_poll_or_prac` — Charitable purpose flag; no ontology target.
- `Advancing_natual_environment` — Charitable purpose flag (source misspells 'natural'); no ontology target.
- `Promoting_or_protecting_human_rights` — Charitable purpose flag; no ontology target.
- `Purposes_beneficial_to_ther_general_public_and_other_analogous` — Charitable purpose flag (source misspells 'the'); no ontology target.
- `Promoting_reconciliation__mutual_respect_and_tolerance` — Charitable purpose flag; no ontology target.
- `Advancing_Religion` — Charitable purpose flag; no ontology target.
- `Advancing_social_or_public_welfare` — Charitable purpose flag; no ontology target.
- `Advancing_security_or_safety_of_Australia_or_Australian_public` — Charitable purpose flag; no ontology target.
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

**Held-out run:** 1182 records, 1180 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 1 values rejected: {'WEBSITE_INVALID': 1} (`entity.website`)
- [warning] SOME_ERRORS: 2 values rejected: {'POSTCODE_INVALID': 2} (`address.postcode`)
- [warning] SOME_ERRORS: 18 values rejected: {'ENUM_UNMAPPED': 18} (`address.country`)

**Critic:** 9 条规则全部检查通过：ABN 及其校验和、名称、注册日期读取顺序（dd/mm/yyyy，并由 2012 年 12 月的日期确认）、网址清洗、address.full 合并并带有诚实的联系地址范围说明、locality、state、postcode 拒绝，以及现在被正确禁用的 country 透传（在 'Austria' 上尤其重要）。与规范对比没有发现语义误映射：没有把 trading name 当作 legal_name，没有把许可证号当作标识符，没有在有效期上乱挂日期，也没有猜测 entity_type/status。遗留缺口是 Other_Organisation_Names（一个别名/其他名称字段，不是 trading_name）和成立日期（一个本体缺口，需要新的目标）。
- missed? `Other_Organisation_Names` -> `entity.trading_name` — 发布方说明这是“公众已知的名称”列表，而留出记录中含有看起来像公开名称的值（'Walker Close Community Centre'、'Donnybrook Men's Shed Inc.'）。由于本体没有 alias/other_name 目标，这里将其保留为未映射，与声称的粒度一致，但它是实体命名字段中最接近未映射的一项；如果下游需要，应该增加一个 alias 目标，而不是强制映射到 trading_name。
- missed? `Date_Organisation_Established` -> `entity.date_registered` — 这是本体缺口，不是错误映射项；它不能成为 date_registered（发布方区分了注册生效日期和成立日期），如果以后增加 entity.date_established，就应该映射到那里。
- missed? `Address_Type` -> `unknown` — 没有合适的目标；它只是地址行的类别标签（所有记录都是 'Business'），映射到 entity_type 或 address.* 都会成为猜测。

**Agent notes:** REVISION after holdout review. Changes: (1) record_id switched from columns[ABN] to content_hash - the error was real, 6 holdout rows collide on ABN because the register contains related/sub-entity rows and rows lacking an ABN. (2) address.country passthrough disabled - the previous passthrough emitted a typo ('Austria' on an Altona North VIC address) as an asserted canonical country; now only explicitly recognised values emit (AU, and SG for the Singapore rows actually present). (3) Rejected WEBSITE_INVALID and POSTCODE_INVALID values are intentional rejections of malformed prose / locality-names-in-postcode, not parser bugs; documented in their rationales. (4) address.full confidence lowered to 0.72 and its rationale now warns that the first line is often a venue/premises or PO box descriptor rather than a street address. (5) Other_Organisation_Names remains unmapped despite the critic's 'missed' suggestion: publisher evidence warns alternate names are not attested trading names, and the column mixes spelling variants of the legal name with person names and fragments, so a filter would require guesswork; the correct model is an alias field. (6) Date_Organisation_Established is a genuine ontology gap (no entity.date_established). No entity.status or entity.entity_type mapping was added: the register has no deregistered/in-liquidation or business-form column, so both stay unasserted rather than guessed.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' none
    - ~ changed `('Postcode',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('Country',)` -> `address.country` (steps/confidence)
    - ~ changed `('Address_Line_1', 'Address_Line_2', 'Address_Line_3')` -> `address.full` (steps/confidence)
    - ~ record_id columns -> content_hash []

## Decision

This experimental proposal is outside the approval queue.
