# Mapping review: `asic_credit_licensees`

- **Status:** PENDING_REVIEW  (run `20261112T024126-f27d6d`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** ASIC – Credit Licensee Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Credit Licence Dataset - Current (TSV), sha256 `74fc2f5f73e64331dd36538e1fee47ed474c33c161f7c9bf990efe7aa5f8a218`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 9 tool calls, 8 model calls, 106,539 prompt + 10,202 completion tokens, 73s model time

## Final proposal (v0, digest `5ef1ba97b49f040c0524f4386a6c21c7f3a01a7501a9a3fb29412f0fd5d8fda4`)

**Record grain:** `licence_or_permit` — One record is one current Australian credit licence, identified by CRED_LIC_NUM, held by a legal person named in CRED_LIC_NAME (ASIC issues credit licences to legal entities). The business attributes mapped are those of the licensee/holder; the licence number, licence start date and licence status are attributes of the licence, not of the entity, so they are not mapped as business identifiers or entity.status.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['CRED_LIC_NUM'] — CRED_LIC_NUM has present_rate 1.0 and 464 distinct values across 464 discovery records, i.e. unique per licence record; it is the natural traceable key for the licence grain.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| CRED_LIC_NAME | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "0", "N/A"]}) | 0.82 | 1174 / 1174 |  | Column is CRED_LIC_NAME on a credit licence register: the licence is issued to the named holder, and the publisher states licence names follow the business register. Values are registered-form names ('...PTY LTD', 'LIMITED'). Some holders are individuals (e.g. 'TAN, JINTANG'), expected for sole-trader licensees; the field remains the registered legal name of the licensee, not a trading name. |
| CRED_LIC_BN | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["", "0"]}) | 0.75 | 380 / 380 |  | CRED_LIC_BN is the licence's business name field, present on 34.5% of rows; values are short trading brands ('DISCOVERY FINANCIAL MANAGEMENT', 'STACKS FINANCE', 'PLANNING PARTNERS') distinct from the registered names in CRED_LIC_NAME. Business/brand names map to trading_name. |
| CRED_LIC_ABN_ACN | `entity.abn` | regex_extract({"pattern": "^(\\d{11})$", "group": 1}), abn | 0.85 | 1057 / 1174 |  | Combined ABN/ACN column: 420 of 464 discovery values are 11-digit checksum-valid ABNs. The regex_extract step restricts this rule to the 11-digit branch so the abn transform only ever sees ABN-shaped values; ACN-shaped, 7-8 digit and placeholder values produce no ABN observation instead of an error. |
| CRED_LIC_ABN_ACN | `entity.acn` | regex_extract({"pattern": "^(\\d{9})$", "group": 1}), acn | 0.6 | 92 / 1174 |  | 27 of 464 records carry a 9-digit ACN-shaped value in CRED_LIC_ABN_ACN; that branch is an ACN (the last 9 digits of an ABN are not always an ACN, so it is validated with the acn checksum, never derived). The regex_extract step selects only 9-digit values, so 11-digit ABNs, 7-8 digit values and the placeholder '0' are excluded from this field rather than erroring. |
| CRED_LIC_LOCALITY | `address.locality` | trim, collapse_whitespace, null_if({"values": ["", "0"]}) | 0.72 | 1174 / 1174 |  | ASIC credit licensee extracts carry the licensee's locality/state/postcode as a group with latitude/longitude, i.e. the holder's contact address on the licence record. |
| CRED_LIC_STATE | `address.state` | state | 0.85 | 1174 / 1174 |  | All 464 values are already 2-3 letter AU state abbreviations over 8 distinct values (NSW, VIC, QLD, WA, SA, ACT, ...), consistent with the state enum. |
| CRED_LIC_PCODE | `address.postcode` | trim, postcode | 0.8 | 1174 / 1174 |  | All 464 values have shape 9999 (4-digit AU postcodes, e.g. 2000, 3000, 6102); normalised with the postcode transform. |

**Constants:**
- `address.country` = `AU` (conf 0.9): ASIC Australian credit licence register covering Australian licensees; all observed states are AU jurisdictions.

**Deliberately unmapped:**
- `REGISTER_NAME` — Constant register label ('Credit Licence') for every row; carries no entity attribute.
- `CRED_LIC_NUM` — Identifier of the licence record, not of the business. Used only as record_id; the ontology has no licence field.
- `CRED_LIC_START_DT` — Date the credit licence started, not the entity's registration date (publisher evidence: grant/suspension/cancellation dates concern the licence). Mapping it to entity.date_registered would misstate company registration.
- `CRED_LIC_END_DT` — Dataset is 'Current' and the column is empty in every discovery row; also concerns licence end, not entity validity.
- `CRED_LIC_STATUS` — Status of the licence (single value 'APPR' = approved), not of the legal entity; licence status is not entity.status.
- `CRED_LIC_STATUS_HISTORY` — Free-text licence-condition contravention history (present on 0.2% of rows); describes the licence, not the entity.
- `CRED_LIC_AFSL_NUM` — Australian Financial Services licence number of the licensee, a licence identifier with no ontology target; 91.6% of values are the placeholder '0' anyway.
- `CRED_LIC_LAT` — Latitude coordinate with no ontology address field for coordinates.
- `CRED_LIC_LNG` — Longitude coordinate with no ontology address field for coordinates.
- `CRED_LIC_EDRS` — External dispute resolution scheme membership(s) of the licensee ('AFCA~FOS'); a compliance attribute, not an entity or address field.
- `CRED_LIC_AUTHORISATIONS` — Free-text description of what the licence authorises; describes licence scope, not the entity.

**Held-out run:** 1174 records, 1174 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is largely sound: legal_name, trading_name, ABN/ACN checksum branches, state, postcode and country all match their ontology targets, and placeholders ('0', ACN-shaped or 11-digit values in the wrong rule) are filtered correctly. The main substantive doubt is the address group: CRED_LIC_LOCALITY/STATE/PCODE are labelled claim_scope 'licence_holder_address' although the supplied publisher evidence says nothing about address kind, and ASIC extracts can carry premises addresses, so the scope is asserted rather than evidenced (rule 4 doubtful; rules 5-6 acceptable on data quality). The unmapped list is well justified: licence number, licence start/end dates, licence status and AFSL number are licence attributes, not entity identifiers, dates or status, and mapping CRED_LIC_START_DT to entity.date_registered was correctly avoided. The clearest gap is entity_type: the register's registered-name suffixes ('PTY LTD', 'LIMITED') and individual personal-name entries are direct evidence available but unused.
- doubtful: `address.locality` <- ['CRED_LIC_LOCALITY'] — CRED_LIC_LOCALITY is reasonably the licensee's address group (with state/postcode/lat/lng), but the mapping calls it licence_holder_address without publisher evidence: ASIC's credit licence extracts also contain licensed business/premises addresses, and the claim_scope asserts a specific address kind the supplied publisher evidence does not confirm. Values emitted (LEONGATHA, PENRITH, SYDNEY, BRUNSWICK, TEMPLESTOWE, WILEY PARK) are plausible, but the scope label is asserted rather than evidenced.
- missed? `CRED_LIC_NAME (registered-name form and suffix, e.g. 'PTY LTD', 'LIMITED', 'PTY. LIMITED', or 'SURNAME, GIVEN NAMES')` -> `entity.entity_type` — The dataset contains both company-style suffixes and individual licensee names, yet no entity_type observation is emitted. Deriving company from 'PTY LTD'/'LIMITED' suffixes and treating bare personal names cautiously (unknown or, at most, evidence-limited sole_trader) would use an actual source column; currently entity_type is simply absent. Note the rule must not guess: personal name alone is weak evidence, so 'unknown' is a safe output.
- missed? `CRED_LIC_STATUS` -> `entity.status` — Only value 'APPR' is observed, so mapping it is arguable; but if the mapping were to use status at all it should be a licence-level caveat. Since the mapping deliberately excludes it and no entity-status source exists, this is correctly omitted — listing only to note that a licence approval does not evidence entity active status, so no status observation should be invented.

**Agent notes:** Licence-grain register: record_id is the licence number, and licence dates/status are deliberately not mapped to entity fields. CRED_LIC_ABN_ACN is a mixed column - 420/464 are checksum-valid 11-digit ABNs, 27 are 9-digit ACN-shaped, 13 are the placeholder '0', and a few are 7-8 digits; each identifier rule is shape-guarded with regex_extract so the checksummed transforms only see values of the right length and invalid values yield no observation rather than an error. entity_type is left unmapped because no column states the business form explicitly (names ending in PTY LTD are not treated as a stated type). Address fields are the licensee's contact details on the licence record; the geography of the register does not by itself prove each record's location, but locality/state/postcode plus coordinates are presented as the licensee's address.

## Decision

This experimental proposal is outside the approval queue.
