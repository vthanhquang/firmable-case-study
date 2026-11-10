# Mapping review: `asic_credit_licensees`

- **Status:** PENDING_REVIEW  (run `20261110T051227-ef1d89`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** ASIC – Credit Licensee Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Credit Licence Dataset - Current (TSV), sha256 `74fc2f5f73e64331…`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 8 tool calls, 7 model calls, 71,181 prompt + 4,993 completion tokens, 37s model time

## Final proposal (v0, digest `55f2aceacac37936`)

**Record grain:** `licence_or_permit` — One record = one current Australian credit licence (CRED_LIC_NUM) held by a business licensee; the business's attributes (name, ABN/ACN, address) are those of the licensee.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['CRED_LIC_NUM'] — CRED_LIC_NUM is present on 100% of records and distinct on 100% of the discovery partition (464/464) - one row per licence.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| CRED_LIC_NAME | `entity.legal_name` | trim, collapse_whitespace | 0.55 | 1161 / 1161 |  | ASIC licensee register name; predominantly registered company names (PTY LTD / LIMITED), but some rows carry individual licensee names like 'TAN, JINTANG' (sole |
| CRED_LIC_BN | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.7 | 375 / 375 |  | CRED_LIC_BN is the business name of the licensee (present on 34.5% of rows, distinct, not a legal-name form). Business name -> trading_name. |
| CRED_LIC_ABN_ACN | `entity.abn` | regex_extract({"pattern": "^\\s*(\\d{11})\\s*$", "group": 1}), abn | 0.85 | 1045 / 1161 |  | ABN_ACN field holds an 11-digit ABN for 420/464 rows; profile shows abn checksum-valid rate 0.905 over all rows. Regex restricts to exactly the 11-digit shape s |
| CRED_LIC_ABN_ACN | `entity.acn` | regex_extract({"pattern": "^\\s*(\\d{9})\\s*$", "group": 1}), acn | 0.7 | 92 / 1161 |  | 27 rows in the discovery partition carry a 9-digit value in ABN_ACN - the ACN shape. Validated with the acn checksum transform; non-conforming values yield no o |
| CRED_LIC_STATUS | `entity.status` | trim, map_enum({"mapping": {"APPR": "active", "AP": "active", "APPROVED": "active", "SUSP": "suspended", "SUSPENDED": "s | 0.7 | 1161 / 1161 |  | Dataset is 'Current' licensees; every discovery row is APPR. Unlisted codes fall back to unknown. |
| CRED_LIC_LOCALITY | `address.locality` | trim, collapse_whitespace | 0.9 | 1161 / 1161 |  | Locality/suburb of the licensee's registered address. |
| CRED_LIC_STATE | `address.state` | trim, state | 0.9 | 1161 / 1161 |  | All values are already AU state abbreviations (NSW/VIC/QLD/WA/SA/ACT/TAS/NT). |
| CRED_LIC_PCODE | `address.postcode` | trim, postcode | 0.9 | 1161 / 1161 |  | 4-digit AU postcodes on 100% of rows. |
| CRED_LIC_START_DT | `observation.valid_from` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.85 | 1161 / 1161 |  | All values match dd/mm/yyyy (day-first, ASIC convention); this is when the licence took effect. |
| CRED_LIC_END_DT | `observation.valid_to` | trim, null_if({"values": [""]}), parse_date({"formats": ["%d/%m/%Y"]}) | 0.85 | 0 / 0 |  | Empty for all current licences; same dd/mm/yyyy format. Null means still current. |

**Constants:**
- `address.country` = `AU` (conf 0.8): Australian credit licensing regime administered by ASIC; all states are AU and licensing is domestic. No country column present.

**Deliberately unmapped:**
- `REGISTER_NAME` — Constant 'Credit Licence' for all rows - describes the register, adds no entity attribute.
- `CRED_LIC_NUM` — The licence's own identifier, not a business identifier. Used only as record_id.
- `CRED_LIC_AFSL_NUM` — Australian Financial Services licence number - a related-licence identifier, not an entity field; equals the credit licence number where present and '0' for 425/464 rows.
- `CRED_LIC_STATUS_HISTORY` — Free-text status/condition history present on 0.2% of rows; no ontology target and too sparse/irregular to parse.
- `CRED_LIC_EDRS` — External dispute resolution scheme memberships (AFCA/COSL/FOS, '~'-separated) - no ontology target.
- `CRED_LIC_LAT` — Latitude of the locality, not of a street address; address.full is not available and no geo target exists in the ontology.
- `CRED_LIC_LNG` — Longitude of the locality; no geo target exists in the ontology.
- `CRED_LIC_AUTHORISATIONS` — Free-text licence authorisations/conditions - licence scope, not an entity attribute.

**Held-out run:** 1161 records, 1161 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Most field mappings align with ontology semantics: legal_name from CRED_LIC_NAME, trading_name from CRED_LIC_BN, ABN/ACN split by digit length and checksum, address components, and dates in dd/mm/yyyy. Two soft concerns: (1) the status='active' assertion for records whose history records suspensions ignores evidence (TSIALTAS 2016-17, LEASEPLUS 2020-21) — arguably the licence status today is active post-suspension so may be acceptable, but the semantics of 'active' versus the history should be documented; (2) the ABN/ACN extraction from a mixed column relies on a simplistic digits-length heuristic (7-digit '7276075' in sample is neither ABN nor ACN, correctly dropped, but its source could be a truncated ACN that should be flagged). entity_type left as absent is defensible given no explicit type column; note that names containing PTY LTD/LIMITED could support a 'company' inference but guessing is contraindicated by the ontology. No clear source-to-target missed mappings beyond the status-history nuance.
- doubtful: `entity.abn` <- ['CRED_LIC_ABN_ACN'] — Field mixes ABNs, ACNs and '0' placeholders; the 11-digit regex plus ABN checksum is reasonable, but some held-out values look questionable (e.g. short 7-digit '7276075' correctly suppressed, but no confidence the 11-digit branch is always an ABN vs padded ACN). Worth verifying checksum coverage explicitly. Behavior in samples looks correct.
- doubtful: `entity.status` <- ['CRED_LIC_STATUS'] — APPR -> active is plausible for a 'current licensees' extract, but two held-out records (TSIALTAS, LEASEPLUS) show status_history of 'Suspended at the request of Licensee' and are still emitted as active. The enum mapping ignores the status history that says the licence was suspended during a period.
- missed? `CRED_LIC_AFSL_NUM` -> `observation.valid_to` — Not a fit for any ontology target directly; correctly left out. Not a missed mapping.
- missed? `CRED_LIC_STATUS_HISTORY` -> `entity.status` — Free-text suspension history on two held-out rows indicates the licence was suspended for a period; used solely to sanity-check status enum. Currently unmapped and the mapping emits active without acknowledging suspensions.

**Agent notes:** Grain is licence-level but each licence maps 1:1 to a licensee business. CRED_LIC_NAME is the licensee's registered name: mostly companies, occasionally individuals (sole traders) - mapped to legal_name with moderate confidence since the register itself uses this as the legal licensee name; no separate trading-name column ambiguity. ABN_ACN mixes ABN (11d), ACN (9d), and the placeholder '0'; each is routed by digit-length regex to the checksummed transform. entity_type left unmapped (names suggest companies but the source does not state a type field).

## Decision

Approve: `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>" --reject --comment "why"`
