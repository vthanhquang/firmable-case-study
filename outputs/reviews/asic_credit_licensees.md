# Mapping review: `asic_credit_licensees`

- **Latest review decision:** approved by claude-code (AI assistant acting for the candidate) (ai_assistant_proxy) at 2026-11-09T20:58:46+00:00
- **Status:** PENDING_REVIEW  (run `20261110T035350-5f82db`, prompt `prompts-v1`, model `deepseek-v4-flash`)
- **Dataset:** ASIC – Credit Licensee Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Credit Licence Dataset - Current (TSV), sha256 `74fc2f5f73e64331dd36538e1fee47ed474c33c161f7c9bf990efe7aa5f8a218`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 12 tool calls, 11 model calls, 150,259 prompt + 10,979 completion tokens, 79s model time

**Current extraction:** Legacy record-level validity rules below have no effect on
claims. Check each claim's validity paths before approving.

## Final proposal (v1, digest `93e42b99014c322d168ee0c545d44f1bf6f2d61aba6e01df63336e42ba1e7b45`)

**Record grain:** `licence_or_permit` — Each row is one ASIC credit licence (CRED_LIC_NUM) held by a licensee. The business participant is the licensee named in CRED_LIC_NAME; the licence number itself is the record identifier, not a business identifier.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['CRED_LIC_NUM'] — CRED_LIC_NUM is present on 100% of rows and has 464 distinct values over 464 discovery records - unique per record.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| CRED_LIC_NAME | `entity.legal_name` | trim, collapse_whitespace | 0.7 | 1136 / 1136 |  | ASIC register name of the licensee, presented as a registered-style name (mostly '... PTY LTD'/'... LIMITED'); some rows are individuals (e.g. 'TAN, JINTANG'), which are the licensee legal names of sole traders, not contact people. |
| CRED_LIC_BN | `entity.trading_name` | trim, collapse_whitespace | 0.6 | 370 / 370 |  | ASIC 'business name' column, free of tilde separators, present on 34.5% of rows and clearly a trading/display name (e.g. 'DISCOVERY FINANCIAL MANAGEMENT' under LUNAWAVE PTY. LIMITED), not the registered name. |
| CRED_LIC_ABN_ACN | `entity.abn` | trim, null_if({"values": ["0", ""]}), regex_extract({"pattern": "^\\d{11}$", "group": 0}), abn | 0.8 | 1023 / 1136 |  | Mixed ABN/ACN column. Only the 11-digit shape (420/464 discovery rows, 90.5% ABN-checksum-valid) is an ABN by definition; regex_extract restricts the transform to that shape so 9-digit ACNs and 7-8 digit values resolve to null instead of raising ABN_LENGTH errors. |
| CRED_LIC_ABN_ACN | `entity.acn` | trim, null_if({"values": ["0", ""]}), regex_extract({"pattern": "^\\d{9}$", "group": 0}), acn | 0.55 | 91 / 1136 |  | The 9-digit values (27/464 discovery rows, e.g. 601283201) in this combined ABN_ACN column are ACNs and pass the ACN checksum; passed through the checksum-validating acn transform. Taken from an explicit ACN value in the source, never derived from an ABN. |
| CRED_LIC_LOCALITY | `address.locality` | trim, collapse_whitespace | 0.9 | 1136 / 1136 |  | Suburb/locality column, 100% present, matches AU place names. |
| CRED_LIC_STATE | `address.state` | trim, upper, state | 0.95 | 1136 / 1136 |  | Two-letter AU state abbreviations, 8 distinct, all within the enum. |
| CRED_LIC_PCODE | `address.postcode` | trim, postcode | 0.9 | 1136 / 1136 |  | All values 4-digit AU postcode shape. |
| CRED_LIC_START_DT | `observation.valid_from` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.85 | 1136 / 1136 |  | Licence start date, all values DD/MM/YYYY (day-first; values like 21/12/2010 and 28/02/2011 confirm day-first). |
| CRED_LIC_END_DT | `observation.valid_to` | trim, null_if({"values": ["", "0"]}), parse_date({"formats": ["%d/%m/%Y"]}) | 0.7 | 0 / 0 |  | Licence end date in DD/MM/YYYY; empty on all discovery rows (current licences) so valid_to is null = still current. |

**Constants:**
- `address.country` = `AU` (conf 0.9): ASIC Australian credit licence register; all localities/states are Australian.
- `entity.status` = `unknown` (conf 0.5): The only status evidence is CRED_LIC_STATUS='APPR', a licence-approval code, not a company status (active/deregistered/liquidated/suspended). Conflating them would overstate knowledge, so entity.status is left unknown.
- `entity.entity_type` = `unknown` (conf 0.3): No explicit entity-type column; names suggest companies but many licensees are individuals/trusts, so left as unknown.

**Deliberately unmapped:**
- `REGISTER_NAME` — Constant 'Credit Licence' on every row; identifies the register, no entity attribute.
- `CRED_LIC_NUM` — Credit licence number - identifier of the licence (record), not a business identifier; used as record_id.
- `CRED_LIC_STATUS` — Licence approval status code ('APPR' on 100% of discovery rows). It is a licence-status code, not one of the entity.status enum values, and the licence is not the entity; mapping it to entity.status would conflate licence approval with company status. Left unmapped rather than guessed.
- `CRED_LIC_AFSL_NUM` — AFS licence number; frequently '0' (425/464) and duplicates the credit licence number when present; not an entity identifier in the ontology and not an ABN/ACN.
- `CRED_LIC_STATUS_HISTORY` — Free-text narrative of licence conditions/status changes for the licence; no ontology target and too sparse (0.2%) to be reliable.
- `CRED_LIC_LAT` — Latitude of the licensee address; no coordinate target in the ontology.
- `CRED_LIC_LNG` — Longitude of the licensee address; no coordinate target in the ontology.
- `CRED_LIC_EDRS` — External dispute resolution scheme membership (AFCA/FOS/COSL); no ontology target.
- `CRED_LIC_AUTHORISATIONS` — Long free-text description of the credit activities authorised by the licence; narrative, no ontology target.

**Held-out run:** 1136 records, 1136 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is sound for all held-out fields: legal vs trading names are correctly distinguished, ABN/ACN are correctly separated by shape and validated by checksum, address fields are correctly sourced, dates are parsed day-first, and entity.status/entity_type are left as unknown rather than guessed. No clear ontology target was left unmapped; CRED_LIC_EDRS and CRED_LIC_AUTHORISATIONS have no strong ontology match.
- missed? `CRED_LIC_AUTHORISATIONS` -> `entity.industry_code` — The free-text authorisations describe the credit activities (e.g. 'engage in credit activities'), which could support an ANZSIC or activity classification, though it is narrative rather than a code. Not a strong direct match, but it is the only source of activity/industry information.
- missed? `CRED_LIC_EDRS` -> `entity.industry_code` — External dispute resolution scheme membership is not an industry code; this is a weak/no match and is reasonably left unmapped.

**Agent notes:** Revision: CRED_LIC_ABN_ACN is a mixed ABN/ACN column. Shape filters (^\d{11}$ -> entity.abn, ^\d{9}$ -> entity.acn) send only the matching identifier type to its own checksum transform; 7-8 digit and '0' values are treated as missing. This removed all ABN_LENGTH errors (previously 8.8%) and recovers the ACNs that were being discarded. No ACN is ever derived from an ABN. entity.status changed to 'unknown' because CRED_LIC_STATUS is a licence-approval code, not a company status; the column is recorded in unmapped. No observed_at column exists, so resource_last_modified is used. TSV confirmed by 16 tabs per line in raw bytes.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['HIGH_ERROR_RATE(entity.abn)'], critic 'wrong' none
    - + added `('CRED_LIC_ABN_ACN',)` -> `entity.acn`
    - ~ changed `('CRED_LIC_ABN_ACN',)` -> `entity.abn` (steps/confidence)

## Second opinion (independent agent run)
- `rerun-v3`: 10/13 rules agree; **check these first:**
    - only this proposal: `('<constant:unknown>',)` -> `entity.entity_type` 
    - only this proposal: `('<constant:unknown>',)` -> `entity.status` 
    - only the other run: `('CRED_LIC_STATUS',)` -> `entity.status` 
- `v5a`: 8/14 rules agree; **check these first:**
    - only this proposal: `('CRED_LIC_ABN_ACN',)` -> `entity.abn` 
    - only this proposal: `('CRED_LIC_ABN_ACN',)` -> `entity.acn` 
    - only this proposal: `('<constant:unknown>',)` -> `entity.entity_type` 
    - only this proposal: `('<constant:unknown>',)` -> `entity.status` 
    - only the other run: `('CRED_LIC_ABN_ACN',)` -> `entity.abn` CRED_LIC_ABN_ACN not_in ['0']
    - only the other run: `('CRED_LIC_ABN_ACN',)` -> `entity.acn` CRED_LIC_ABN_ACN not_in ['0']
- `v5b`: 7/13 rules agree; **check these first:**
    - only this proposal: `('<constant:AU>',)` -> `address.country` 
    - only this proposal: `('<constant:unknown>',)` -> `entity.entity_type` 
    - only this proposal: `('<constant:unknown>',)` -> `entity.status` 
    - only this proposal: `('CRED_LIC_START_DT',)` -> `observation.valid_from` 
    - only this proposal: `('CRED_LIC_END_DT',)` -> `observation.valid_to` 
    - only the other run: `('CRED_LIC_NAME',)` -> `entity.entity_type` 

## Decision

Approve: `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve asic_credit_licensees --reviewer "<name>" --reject --comment "why"`
