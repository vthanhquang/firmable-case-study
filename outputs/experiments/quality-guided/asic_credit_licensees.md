# Mapping review: `asic_credit_licensees`

- **Status:** PENDING_REVIEW  (run `20261112T014653-803650`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** ASIC – Credit Licensee Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Credit Licence Dataset - Current (TSV), sha256 `74fc2f5f73e64331dd36538e1fee47ed474c33c161f7c9bf990efe7aa5f8a218`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 13 tool calls, 12 model calls, 189,360 prompt + 14,971 completion tokens, 360s model time

## Final proposal (v1, digest `84baee2e41b1dd1400fd3e6985cc44429d22d2c7b640bee6e90c6fb5d2a5173c`)

**Record grain:** `licence_or_permit` — One record is one current Australian credit licence issued by ASIC to a licensee. The business participant is the licensee (the holder), so business attributes (legal name, ABN, address) are mapped from the licence-holder columns; the licence number is the record's own identifier, not a business identifier, and licence status/dates describe the licence, not the entity.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['CRED_LIC_NUM'] — CRED_LIC_NUM present on every row, 464 distinct among 464 records (100% unique), fixed 6-digit shape. It is the ASIC credit licence number and the stable traceable key.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| CRED_LIC_NAME | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "0", "-"]}) | 0.8 | 1174 / 1174 |  | Column names the licensee, the legal person to whom the credit licence is issued (publisher: licence name changes follow business register updates). Values are registered-style legal names ending PTY LTD / LIMITED; some rows are individual holders in surname-first form (e.g. 'TAN, JINTANG'), still the holder's legal name rather than a trading name. |
| CRED_LIC_BN | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["", "0", "-"]}) | 0.75 | 380 / 380 |  | CRED_LIC_BN is the licensee's business name, present on 34.5% of rows. Values are short trading-style names ('PLANNING PARTNERS', 'DEFENCE BANK', 'STACKS FINANCE') distinct from the legal-name column. |
| CRED_LIC_ABN_ACN | `entity.abn` | trim, null_if({"values": ["", "0", "-"]}), regex_extract({"pattern": "^\\d{11}$", "group": 0}), abn | 0.8 | 1057 / 1174 |  | Mixed ABN/ACN column: 420/464 values are 11 digits and 90.5% of those pass the ABN checksum, so the 11-digit population is an ABN population. The regex pre-filter keeps only 11-digit values so the checksummed abn transform is applied solely to genuine ABN candidates; shorter ACN-shaped values and the '0' placeholder (13 rows) are deliberately left unmapped rather than converted. |
| CRED_LIC_LOCALITY | `address.locality` | trim, collapse_whitespace, null_if({"values": ["", "0", "-"]}) | 0.8 | 1174 / 1174 |  | 100% present with 314 distinct AU suburb/locality values, paired with coherent state and postcode columns. |
| CRED_LIC_STATE | `address.state` | trim, state | 0.9 | 1174 / 1174 |  | All 464 values are 1-character AU state abbreviations across 8 distinct values, exactly the state enum vocabulary. |
| CRED_LIC_PCODE | `address.postcode` | trim, postcode | 0.9 | 1174 / 1174 |  | 100% present, 100% 4-digit numeric shape, 275 distinct values consistent with AU postcodes. |

**Constants:**
- `address.country` = `AU` (conf 0.85): ASIC Australian credit licensee register; all states are Australian and every postcode is a 4-digit AU postcode.

**Deliberately unmapped:**
- `REGISTER_NAME` — Constant 'Credit Licence' on all rows - register name, not a business attribute.
- `CRED_LIC_NUM` — The licence's own identifier; used for record_id only, not a business identifier.
- `CRED_LIC_START_DT` — Start date of the credit licence, not the entity's registration date; publisher evidence says grant/suspension/cancellation dates concern the licence. Mapping it to entity.date_registered would overstate the claim.
- `CRED_LIC_END_DT` — Licence end date, empty on all discovery rows; describes the licence, not the holder's entity claims.
- `CRED_LIC_STATUS` — Status of the LICENCE (APPR = approved) on every row, not the legal entity's status. Licence status must not become entity.status.
- `CRED_LIC_AFSL_NUM` — Australian Financial Services licence number - a different licence regime, not a business identifier in this ontology.
- `CRED_LIC_STATUS_HISTORY` — Free-text licence condition/enforcement history (present on 0.2% of rows); concerns the licence, not the legal entity's status.
- `CRED_LIC_LAT` — Latitude coordinate; no coordinate target in the ontology.
- `CRED_LIC_LNG` — Longitude coordinate; no coordinate target in the ontology.
- `CRED_LIC_EDRS` — External dispute resolution scheme membership (AFCA/COSL/FOS), a licence-condition attribute, not an entity or address field.
- `CRED_LIC_AUTHORISATIONS` — Long free-text description of what the licence authorises; describes the licence scope, not an entity attribute.

**Held-out run:** 1174 records, 1174 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All seven rules are acceptable in direction and meaning. legal_name comes from the licensee name column, not a trading name; trading_name comes from the distinct business-name column; ABN is filtered by regex plus checksum so only valid 11-digit ABNs are emitted and ACN shapes and the '0' placeholder are dropped; address locality/state/postcode are coherent AU values under a holder-address scope; the country constant is supported. Correctly excluded: licence number, licence status, dates, AFSL number, EDRS and coordinates. Main gaps are that entity_type and ACN are not mapped, even though name suffixes and the 9-digit values support deterministic conditional rules. Neither omission smuggles in a mis-typed claim, but they leave clear ontology targets unfilled.
- missed? `CRED_LIC_NAME` -> `entity.entity_type` — Only direct evidence for entity_type: names ending PTY LTD/LIMITED support company; comma-form individual names ('TSIALTAS, ARGIRIOS HARRY', 'LATASH, EDDIE') support sole_trader/individual. Leaving entity_type unmapped is safer than guessing, but the suffix pattern is a deterministic, non-guess signal worth a conditional rule (company when PTY LTD/LIMITED/Pty Ltd; individual when SURNAME, GIVEN form; otherwise unknown).
- missed? `CRED_LIC_ABN_ACN` -> `entity.acn` — 9-digit values in this mixed column are ACN-shaped (e.g. '102331359', '601283201'); the mapping deliberately drops them but they could be checksum-validated and emitted as entity.acn, which is a defined ontology target.

**Agent notes:** Tab-delimited UTF-8-BOM text despite the TSV label; 17 columns, header on row 0. CRED_LIC_ABN_ACN is a combined ABN/ACN column: only the 11-digit values are mapped, via an ^\d{11}$ pre-filter plus the checksummed abn transform. The 9-digit population (27 rows) was NOT mapped to entity.acn because no publisher evidence separates ABN from ACN in this column and the column-wide ACN checksum-valid rate is only 6.7%, so claiming those values are ACNs is unverified inference from shape alone - a wrong ABN/ACN mapping is worse than a missing one. entity.status intentionally emits nothing: CRED_LIC_STATUS describes the licence, not the legal entity, and rows with suspension history show licence status cannot establish holder status, so the ontology default of unknown applies. Licence-derived facts (start/end dates, status, authorisation text, EDR scheme, coordinates, AFSL number) are all left unmapped because the grain is the licence, not the entity. Held-out run was clean on every retained rule (0 errors).

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.status']
    - - removed `('CRED_LIC_ABN_ACN',)` -> `entity.acn`

## Decision

This experimental proposal is outside the approval queue.
