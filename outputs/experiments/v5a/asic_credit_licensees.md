# Mapping review: `asic_credit_licensees`

- **Status:** PENDING_REVIEW  (run `20261110T055958-8cdaad`, prompt `prompts-v5`, model `deepseek-v4-flash`)
- **Dataset:** ASIC – Credit Licensee Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Credit Licence Dataset - Current (TSV), sha256 `74fc2f5f73e64331…`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 14 tool calls, 14 model calls, 212,250 prompt + 13,139 completion tokens, 92s model time

## Final proposal (v1, digest `b3ecc71f55ec27a7`)

**Record grain:** `licence_or_permit` — One record = one current ASIC credit licence (CRED_LIC_NUM) issued to a licensee legal person. Only the holder's business attributes (legal name, business/trading name, ABN or ACN, locality/state/postcode) are mapped to the entity; licence-level attributes (status, EDRS schemes, authorisations, AFSL number, coordinates) are not entity fields. Licence start/end dates are used as the record's validity envelope.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['CRED_LIC_NUM'] — CRED_LIC_NUM is the ASIC credit licence number and is unique per row (464/464 distinct in discovery), giving a traceable, stable record id; it is a licence id, not a business identifier.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| CRED_LIC_NAME | `entity.legal_name` | trim, collapse_whitespace | 0.92 | 1161 / 1161 |  | CRED_LIC_NAME names the licensee, the holder of the credit licence. Licences are issued to legal persons, so this is the registered legal name (e.g. 'RELI CAPIT |
| CRED_LIC_BN | `entity.trading_name` | trim, collapse_whitespace | 0.85 | 375 / 375 |  | CRED_LIC_BN is ASIC's registered business name of the licensee (34.5% present, e.g. 'PLANNING PARTNERS', 'DISCOVERY FINANCIAL MANAGEMENT'); business names are t |
| CRED_LIC_ABN_ACN *when CRED_LIC_ABN_ACN not_in ['0']* | `entity.abn` | trim, regex_extract({"pattern": "^\\d{11}$", "group": 0}), abn | 0.85 | 1045 / 1147 |  | Mixed identifier column: 420/464 discovery values are 11-digit ABNs and 90.5% pass the ABN checksum. The regex_extract step passes only 11-digit values (others  |
| CRED_LIC_ABN_ACN *when CRED_LIC_ABN_ACN not_in ['0']* | `entity.acn` | trim, regex_extract({"pattern": "^\\d{7,9}$", "group": 0}), acn | 0.7 | 102 / 1147 |  | The same column also carries ACN-only values (discovery: 27 nine-digit, 2 seven/eight-digit; 31 rows emit a checksum-valid ACN, with the acn transform zero-padd |
| CRED_LIC_START_DT | `observation.valid_from` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1161 / 1161 |  | Licence start date; all values match dd/mm/yyyy and values such as 21/12/2010 confirm day-first ordering. |
| CRED_LIC_END_DT | `observation.valid_to` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.8 | 0 / 0 |  | Licence end date, day-first; empty throughout discovery (current licences) so null = still current. |
| CRED_LIC_LOCALITY | `address.locality` | trim, collapse_whitespace | 0.9 | 1161 / 1161 |  | Suburb/locality of the licensee's address (e.g. MELBOURNE, PARRAMATTA). |
| CRED_LIC_STATE | `address.state` | state | 0.95 | 1161 / 1161 |  | Two/three-letter AU state abbreviations (NSW, VIC, QLD, WA, SA, ACT, NT, TAS) normalise directly to the state enum. |
| CRED_LIC_PCODE | `address.postcode` | postcode | 0.95 | 1161 / 1161 |  | All 464 discovery values are 4-digit Australian postcodes (e.g. 3000, 2000, 6005). |

**Constants:**
- `address.country` = `AU` (conf 0.85): Metadata states this is ASIC's Australian credit licensee register and every address uses AU states and 4-digit AU postcodes; country is not stated per row.

**Deliberately unmapped:**
- `REGISTER_NAME` — Constant register label ('Credit Licence'); not an entity attribute.
- `CRED_LIC_STATUS` — Status of the licence (APPR = approved; single value in discovery), not the status of the legal entity. Per mapping rules licence status is not entity.status; deliberately left unmapped rather than used as a proxy for active/deregistered.
- `CRED_LIC_STATUS_HISTORY` — Free-text licence status history (1 of 464 discovery rows, describing a licence-condition contravention with dates). It records licence actions, not the legal entity's registered status, so it is deliberately not mapped to entity.status.
- `CRED_LIC_AFSL_NUM` — Australian Financial Services Licence number held by the licensee ('0' in 425/464 rows); it is not an ABN/ACN and no ontology target exists for a second licence number.
- `CRED_LIC_LAT` — Latitude of the licensee address; no ontology target for coordinates.
- `CRED_LIC_LNG` — Longitude of the licensee address; no ontology target for coordinates.
- `CRED_LIC_EDRS` — External dispute resolution scheme memberships (AFCA/COSL/FOS, '~'-separated); licence-level attribute with no ontology target.
- `CRED_LIC_AUTHORISATIONS` — Free-text description of what the licence authorises; licence-level, no ontology target.
- `CRED_LIC_NUM` — The record's own licence id, used only as record_id; not a business identifier.

**Held-out run:** 1161 records, 1161 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Core name/address fields are correctly mapped and day-first dates are right. Trading-name vs legal-name distinction is properly handled (LUNAWAVE / DISCOVERY). The main concerns are (1) the mixed ABN/ACN column: zero-padding 7-8 digit values to ACN is fabrication and 9-digit-as-ACN is an unverified assumption; (2) entity.status and entity.entity_type are left entirely unmapped despite CRED_LIC_STATUS_HISTORY containing explicit suspension evidence, and legal-name suffixes being a usable entity_type signal.
- doubtful: `entity.abn` <- ['CRED_LIC_ABN_ACN'] — The column is mixed ABN/ACN and the mapping applies only a length regex (11 digits) plus checksum; the held-out example 80005443292 and 86090021462 look like ABNs but the design routes 11-digit values to ABN without confirming it isn't an ACN-derived value. The 0 placeholder is skipped, which is correct, but correctness depends on the checksum truly filtering; also note some 11-digit values may be ACN-padded. Acceptable but worth noting reliance on checksum alone.
- doubtful: `entity.acn` <- ['CRED_LIC_ABN_ACN'] — 9-digit values are treated as ACN, but 9-digit values can also be short ABNs or other identifiers; the transform zero-pads 7-8 digit values (e.g. '7276075' -> '007276075'). Zero-padding to fabricate a checksum-valid ACN is risky and may create a false ACN rather than a real one. Also '601283201' as ACN vs 9-digit ABN ambiguity unresolved.
- missed? `CRED_LIC_STATUS_HISTORY` -> `entity.status` — Contains explicit suspension wording and dates (e.g. 'Suspended at the request of Licensee/Registrant 19/09/2016 31/01/2017'), which is evidence for entity.status = suspended. Mapping leaves entity.status unmapped entirely, losing a status signal the ontology explicitly supports.
- missed? `CRED_LIC_BN` -> `entity.entity_type` — Legal-name suffix patterns ('LTD', 'PTY LTD', 'LIMITED', 'PTY. LIMITED', sole-trader comma format like 'LATASH, EDDIE') could support entity_type; currently entity_type is entirely unmapped, leaving default unknown with no source column used. Not strictly required but an explicit source-derived signal exists in CRED_LIC_NAME and is unused.

**Agent notes:** REVISION after held-out review. entity.abn and entity.acn previously errored on 10.0% and 91.2% of present values because the shared CRED_LIC_ABN_ACN column mixes identifier shapes (11-digit ABNs, 7-9 digit ACNs, '0'). Fixed by adding regex_extract gates ('^[0-9]{11}$' for ABN, '^[0-9]{7,9}$' for ACN) so each checksum transform only receives values of its own shape, plus a not_in '0' condition to skip the placeholder; verified 0 errors for both on discovery while keeping 90.5% ABN coverage. ACN coverage is only ~6.7% of rows, which is the honest count of ACN-shaped values in this column. entity.entity_type stays unmapped (name suffixes are not an explicit entity-type statement). entity.status stays unmapped as a deliberate decision: only licence status is published, and per the mapping rules licence/permit status is not entity.status, so populating it would be a guess. observed_at is not in the data, so resource last-modified is used.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['HIGH_ERROR_RATE(entity.abn)', 'HIGH_ERROR_RATE(entity.acn)'], critic 'wrong' none
    - ~ changed `('CRED_LIC_ABN_ACN',)` -> `entity.acn` (steps/confidence)
    - ~ changed `('CRED_LIC_ABN_ACN',)` -> `entity.abn` (steps/confidence)
    - ~ record_id columns -> columns ['CRED_LIC_NUM']

## Decision

Approve: `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>" --reject --comment "why"`
