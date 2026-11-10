# Mapping review: `asic_credit_licensees`

- **Status:** PENDING_REVIEW  (run `20261110T060234-40c96c`, prompt `prompts-v5`, model `deepseek-v4-flash`)
- **Dataset:** ASIC – Credit Licensee Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Credit Licence Dataset - Current (TSV), sha256 `74fc2f5f73e64331…`
- **Licence:** cc-by
- **Agent effort:** 3 proposal(s), 14 tool calls, 15 model calls, 252,611 prompt + 20,578 completion tokens, 132s model time

## Final proposal (v2, digest `af01f3499a16f459`)

**Record grain:** `licence_or_permit` — One record is one current Australian Credit Licence issued by ASIC to a licensee. The entity fields describe the licensee (the holder), whose legal name is in CRED_LIC_NAME and whose identifier is in CRED_LIC_ABN_ACN. The licence number itself is the record's own ID and is used only as record_id, not as a business identifier. Licence start/end dates are attributes of the licence and are not evidence of when the entity's own claims (name, ABN, address) became true, so they are not mapped to the observation envelope.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['CRED_LIC_NUM'] — CRED_LIC_NUM is the ASIC credit licence number, 6 digits, present on every row and distinct on all 464 discovery rows (and all 4313 rows scanned). Unique per record.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| CRED_LIC_NAME | `entity.legal_name` | trim, collapse_whitespace | 0.9 | 1161 / 1161 |  | Column holds the licensee's registered name; licences are issued to legal persons, so this is the legal name (values like 'PLANNING PARTNERS PTY. LTD.', 'RELI C |
| CRED_LIC_BN | `entity.trading_name` | trim, collapse_whitespace | 0.8 | 375 / 375 |  | CRED_LIC_BN is ASIC's business-name column: short brand-style values ('PLANNING PARTNERS', 'DISCOVERY FINANCIAL MANAGEMENT', 'STACKS FINANCE') that differ from  |
| CRED_LIC_ABN_ACN | `entity.abn` | trim, null_if({"values": ["0", "N/A", "NA"]}), regex_extract({"pattern": "^\\d{11}$", "group": 0}), abn | 0.85 | 1045 / 1161 |  | Combined ABN/ACN column. Discovery shapes are 11-digit (420), 9-digit (27), 1-digit '0' (13), 7/8-digit (4); 90.5% of values pass the ABN checksum. The regex ga |
| CRED_LIC_ABN_ACN | `entity.acn` | trim, null_if({"values": ["0", "N/A", "NA"]}), regex_extract({"pattern": "^\\d{9}$", "group": 0}), acn | 0.7 | 92 / 1161 |  | Same combined column; 27 of 464 discovery values are exactly 9 digits, the only shape that can be an ACN. The ^\d{9}$ gate is applied BEFORE the acn transform s |
| CRED_LIC_NAME | `entity.entity_type` | trim, upper, regex_extract({"pattern": "(PTY\\.? ?LTD\\.?|PTY\\.? ?LIMITED|LIMITED|LTD\\.?|NO LIABILITY|INCORPORATED|ASS | 0.6 | 1041 / 1161 |  | CRED_LIC_NAME carries an explicit company-type suffix ('PTY LTD', 'PTY. LIMITED', 'LIMITED') versus the comma-inverted natural-person form ASIC uses for individ |
| CRED_LIC_LOCALITY | `address.locality` | trim, collapse_whitespace | 0.85 | 1161 / 1161 |  | Suburb/locality of the licensee's address on the register (SYDNEY, MELBOURNE, WEST PERTH). |
| CRED_LIC_STATE | `address.state` | trim, state | 0.9 | 1161 / 1161 |  | Two/three-letter AU state abbreviations; all 8 distinct values (NSW VIC QLD WA SA ACT NT TAS) map to the state enum. |
| CRED_LIC_PCODE | `address.postcode` | trim, postcode | 0.9 | 1161 / 1161 |  | All values are 4-digit Australian postcodes (2000, 3000, 6102, ...). |

**Deliberately unmapped:**
- `REGISTER_NAME` — Constant literal 'Credit Licence' on every row - describes the register itself, not an entity attribute.
- `CRED_LIC_STATUS` — Status of the LICENCE (APPR = approved), not of the legal entity. entity.status must not carry licence status; the suggested derivation of entity.status from licence status is declined because a suspended or ceased licence does not deregister or liquidate the company that holds it.
- `CRED_LIC_STATUS_HISTORY` — Free-text licence condition/contravention/suspension history (~0.2% present, prose plus dates). It records the status of the LICENCE, so per the mapping rules it is not entity.status; and it is unparsed free text, so it cannot be reliably reduced to a single enum value. Left unmapped deliberately rather than guessed.
- `CRED_LIC_AFSL_NUM` — Related AFS licence number; not a business identifier target in the ontology and '0' placeholder on 92% of rows.
- `CRED_LIC_START_DT` — Licence start date - when this licence began. No ontology target for a licence's own start date, and using it as observation.valid_from would assert that the entity's name/ABN/address claim only became true on that date, which the source does not say (it is mostly a 2010-2011 scheme-transition date). Not mapped.
- `CRED_LIC_END_DT` — Licence end date - empty on every discovery and held-out row. Same scope problem as the start date, and no licence-validity target exists in the ontology.
- `CRED_LIC_LAT` — Latitude of the address; no latitude/longitude target in the ontology.
- `CRED_LIC_LNG` — Longitude of the address; no latitude/longitude target in the ontology.
- `CRED_LIC_EDRS` — External dispute resolution scheme membership codes (AFCA/COSL/FOS, tilde-delimited licence attributes). Not a business attribute; it is not a website.
- `CRED_LIC_AUTHORISATIONS` — Long free-text description of what the licence authorises - an attribute of the licence, not the entity.

**Held-out run:** 1161 records, 1161 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Mapping is largely sound: legal_name vs trading name are correctly separated (CRED_LIC_NAME vs CRED_LIC_BN), the combined ABN/ACN column is split by length gate with checksum validation, and the address fields map cleanly. The one soft spot is entity.entity_type, which is inferred from name suffixes rather than a source column; the ontology explicitly says to default to unknown, and the mapping instead defaults un-suffixed names to sole_trader, so it is flagged doubtful rather than wrong. Licence status, start/end dates, lat/lng, EDRS and authorisations are correctly left unmapped because they describe the licence, not the entity. No important source columns matching an ontology target were left unmapped.
- doubtful: `entity.entity_type` <- ['CRED_LIC_NAME'] — Inferred from name suffix. Two problems: (1) 'ENTITY_TYPE' has an explicit unknown default in the ontology, but the mapping's regex-with-default-sole_trader means any un-suffixed name becomes sole_trader by guess, not evidence; sole_trader is arguably ok for the inverted 'SURNAME, GIVEN' form, but 'HEAJAS PTY LTD'... actually has PTY LTD. The bigger issue is that LTD/LIMITED -> company is asserted without any entity-type column, and the ontology warns guessing causes harm. Observed outputs (company for 'LIMITED', no type for 'LATASH, EDDIE') look defensible per-case, so not clearly wrong, but it is name-derived inference rather than sourced truth.

**Agent notes:** Grain is licence, not entity: ASIC issues one credit licence per legal person here, so CRED_LIC_NUM is unique and used as record_id. CRED_LIC_ABN_ACN is a dual-purpose column; it is routed through digit-count gates (^\d{11}$ for ABN, ^\d{9}$ for ACN) BEFORE the checksum transforms, so no value is padded, truncated or derived into a passing checksum. Licence start/end dates were previously mapped to observation.valid_from/valid_to; per review they are licence-validity dates rather than entity-claim validity, so both are now unmapped and the observation envelope is dated by resource_last_modified instead. entity.status is intentionally null: this source states licence status, never the registered/deregistered/liquidation status of the legal entity. The address.country constant has been removed, since the ontology already defaults to AU and asserting it would be an unobserved claim. entity.entity_type is inferred from the legal-name suffix form at 0.6 confidence. Source text is untrusted data; nothing in it was treated as instruction.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['HIGH_ERROR_RATE(entity.abn)', 'HIGH_ERROR_RATE(entity.acn)'], critic 'wrong' none
    - ~ changed `('CRED_LIC_ABN_ACN',)` -> `entity.abn` (steps/confidence)
    - ~ changed `('CRED_LIC_ABN_ACN',)` -> `entity.acn` (steps/confidence)
- v1 -> v2: triggered by validator errors none, critic 'wrong' ['observation.valid_from']
    - + added `('CRED_LIC_NAME',)` -> `entity.entity_type`
    - - removed `('CRED_LIC_END_DT',)` -> `observation.valid_to`
    - - removed `('CRED_LIC_START_DT',)` -> `observation.valid_from`

## Decision

Approve: `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>" --reject --comment "why"`
