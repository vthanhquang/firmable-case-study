# Mapping review: `asic_credit_licensees`

- **Status:** PENDING_REVIEW  (run `20261112T014819-93ea82`, prompt `prompts-v7`, model `deepseek-v4-flash`)
- **Dataset:** ASIC – Credit Licensee Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Credit Licence Dataset - Current (TSV), sha256 `74fc2f5f73e64331dd36538e1fee47ed474c33c161f7c9bf990efe7aa5f8a218`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 9 tool calls, 9 model calls, 175,145 prompt + 15,353 completion tokens, 160s model time

## Final proposal (v1, digest `2c8f414c2e416149335e51e056f55bd5f61bcf180ae777b95824c9c2eda302f0`)

**Record grain:** `licence_or_permit` — One record is one current Australian credit licence issued by ASIC to one licensee. The business participant is the licensee named in CRED_LIC_NAME, whose attributes (ABN/ACN, locality/state/postcode) are carried on the same row. The record's own identity is the licence number (CRED_LIC_NUM), not a business identifier, so it is not mapped to any entity field.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['CRED_LIC_NUM'] — CRED_LIC_NUM is present on 100% of rows and distinct on all 464 discovery rows (464/464), matching the 6-digit credit licence number shape. Unique per licence, hence per record.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| CRED_LIC_NAME | `entity.legal_name` | trim, collapse_whitespace | 0.85 | 1174 / 1174 |  | ASIC issues credit licences to legal persons; this column names the licensee (the holder), which is the registered legal name. Values are all-caps with legal-form suffixes (PTY LTD, LIMITED, PTY. LTD.), consistent with a register of legal names. Some holders are natural persons (e.g. 'TSIALTAS, ARGIRIOS HARRY'); the raw name is preserved because that is how the register records the licensee. |
| CRED_LIC_BN | `entity.trading_name` | null_if({"values": ["", "0", "-"]}), trim, collapse_whitespace | 0.8 | 380 / 380 |  | CRED_LIC_BN is the registered business name under which the licensee trades, distinct from the legal name (e.g. LUNAWAVE PTY. LIMITED trades as DISCOVERY FINANCIAL MANAGEMENT). Present on 34.5% of discovery rows, blank elsewhere. Explicitly a business name, so trading_name not legal_name. |
| CRED_LIC_ABN_ACN | `entity.abn` | trim, null_if({"values": ["", "0"]}), regex_extract({"pattern": "^\\d{11}$", "group": 0}), abn | 0.85 | 1057 / 1174 |  | One combined ABN/ACN column. 90.5% of 11-digit discovery values pass the ABN checksum; 13 rows hold '0' as a placeholder for 'no identifier'. The regex_extract step gates the rule to 11-digit values only, so rows holding a 9-digit ACN (or a 7-8 digit short value) are skipped here rather than raising ABN_LENGTH errors - this removed the 8.7% holdout error rate. The abn transform then enforces checksum validity. |
| CRED_LIC_ABN_ACN | `entity.acn` | trim, null_if({"values": ["", "0"]}), regex_extract({"pattern": "^\\d{7,9}$", "group": 0}), acn | 0.7 | 102 / 1174 |  | 27 discovery rows carry 9-digit values in the combined column, i.e. an ACN rather than an ABN; a few further rows have 7-8 digits which the acn transform zero-pads. The regex_extract step gates the rule to 7-9 digit values only, so the 11-digit ABN rows are skipped rather than raising ACN_LENGTH errors - this removed the 90.0% holdout error rate. ACN is never derived by truncating an 11-digit ABN. The acn transform enforces the checksum. |
| CRED_LIC_LOCALITY | `address.locality` | trim, collapse_whitespace | 0.9 | 1174 / 1174 |  | Suburb/locality of the licensee's address; 100% present, 314 distinct on discovery, values match AU suburb names (SYDNEY, MELBOURNE, PARRAMATTA, LEONGATHA). |
| CRED_LIC_STATE | `address.state` | trim, state | 0.95 | 1174 / 1174 |  | 2-3 letter Australian state abbreviations, 8 distinct, fully within the state enum (NSW/VIC/QLD/WA/SA/TAS/ACT/NT). |
| CRED_LIC_PCODE | `address.postcode` | trim, postcode | 0.9 | 1174 / 1174 |  | All 464 discovery values are 4-digit shapes matching AU postcodes. |

**Constants:**
- `address.country` = `AU` (conf 0.95): ASIC Australian credit licence register; all state values are Australian jurisdictions and all postcodes are AU. Evident from metadata plus the state and postcode columns.

**Deliberately unmapped:**
- `REGISTER_NAME` — Constant label 'Credit Licence' on every row (1 distinct value); identifies the register, not the entity or its industry. Carries no ANZSIC code, so it cannot populate entity.industry_code.
- `CRED_LIC_NUM` — The credit licence number - the identifier of the record/licence itself, not a business identifier. Used only as record_id.
- `CRED_LIC_START_DT` — The date the CREDIT LICENCE commenced (dd/mm/yyyy, 100% present), not the date the legal entity was registered or incorporated. Mapping a licence effective date to entity.date_registered conflates two distinct concepts and would assert a fact the source does not state, so it is left unmapped. The ontology has no licence-start target.
- `CRED_LIC_END_DT` — Empty on 100% of discovery rows. It is the licence end date, which dates the licence claim, not the entity's name, form or address.
- `CRED_LIC_STATUS` — Status of the LICENCE (APPR = approved), not of the legal entity. A licence status must not become entity.status, so it is left unmapped rather than mapped as 'active'.
- `CRED_LIC_STATUS_HISTORY` — Free-text licence enforcement/history narrative (present on 0.2% of rows, e.g. 'Licensee contravenes a licence condition ...'). Licence event prose, not a structured entity field.
- `CRED_LIC_ABN_ACN` — The column itself is mapped twice (to entity.abn and entity.acn) via mutually exclusive regex shape gates; it is listed here only to record that '0' on 13 discovery rows is a placeholder for 'no identifier' and yields no observation.
- `CRED_LIC_AFSL_NUM` — Australian Financial Services licence number; '0' on 425/464 discovery rows. Another licence identifier, not an entity attribute; the ontology has no field for it.
- `CRED_LIC_LAT` — Latitude of the licence address. The ontology has no coordinate target; concatenating it into address.full would corrupt the address.
- `CRED_LIC_LNG` — Longitude of the licence address. No coordinate target in the ontology; see CRED_LIC_LAT.
- `CRED_LIC_EDRS` — External dispute resolution scheme memberships (AFCA/COSL/FOS, '~'-separated). A licence attribute with no ontology target.
- `CRED_LIC_AUTHORISATIONS` — Free-text prose describing what the licence authorises ('This licence authorises the licensee to:~...'), identical in structure across rows with only 7 distinct values. A licence attribute, not a structured entity field.
- `CRED_LIC_NAME` — Also considered for entity.entity_type. Declined: the register states no business form, so the suffix heuristic (PTY LTD -> company, a comma-separated personal name -> sole_trader) would be inference rather than a stated fact, and 'sole trader' in particular is not established by a name alone (the person could operate through a company or trust). entity_type is left unmapped so it stays 'unknown' rather than being guessed.

**Held-out run:** 1174 records, 1174 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All mapping rules are semantically correct and align with ontology definitions. The mapper correctly distinguishes licence-level attributes (status, dates, licence numbers) from entity-level attributes, avoiding common pitfalls like mapping licence status to entity.status or licence start date to entity.date_registered. ABN/ACN separation via regex gating is robust. Entity type is correctly left unmapped rather than guessed from name suffixes. No important source columns were missed; all unmapped fields are either licence-specific identifiers, free-text narratives, coordinates without ontology targets, or constants that do not represent entity attributes.

**Agent notes:** Held-out fix: the two identifier rules previously both fired on every non-empty CRED_LIC_ABN_ACN value, so each reported the other shape as a length error (ABN_LENGTH 8.7%, ACN_LENGTH 90.0%). Both rules now begin with a regex_extract shape gate (^\d{11}$ for ABN, ^\d{7,9}$ for ACN) that returns null instead of raising, making the rules mutually exclusive. On discovery this took both error rates to 0.0% with unchanged emission counts (420 ABN, 31 ACN); no identifier is silently dropped, and ACN is never obtained by truncating an ABN. Also moved CRED_LIC_START_DT (licence commencement) off entity.date_registered per critic. observed_at uses resource_last_modified because the file carries no stated-as-of date. Values in the file are all-caps as published; case is not altered.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['HIGH_ERROR_RATE(entity.abn)', 'HIGH_ERROR_RATE(entity.acn)'], critic 'wrong' none
    - - removed `('CRED_LIC_START_DT',)` -> `entity.date_registered`
    - ~ changed `('CRED_LIC_ABN_ACN',)` -> `entity.abn` (steps/confidence)
    - ~ changed `('CRED_LIC_ABN_ACN',)` -> `entity.acn` (steps/confidence)

## Decision

This experimental proposal is outside the approval queue.
