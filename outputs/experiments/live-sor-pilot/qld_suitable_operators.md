# Mapping review: `qld_suitable_operators`

- **Status:** PENDING_REVIEW  (run `20261111T180502-531bbd`, prompt `prompts-v5`, model `deepseek-v4-flash`)
- **Dataset:** Suitable Operator Register (SOR) for Environmentally Relevant Activities (ERAs) — Environment, Tourism, Science and Innovation
- **Resource:** qld_suitable_operators.xlsx (XLSX), sha256 `d89014bdfa961677…`
- **Licence:** CC-BY-4.0
- **Agent effort:** 2 proposal(s), 11 tool calls, 10 model calls, 168,937 prompt + 15,596 completion tokens, 120s model time

## Final proposal (v1, digest `cebb493408a3d982`)

**Record grain:** `licence_or_permit` — One row is one suitable-operator registration (RSO) held by an entity under the Environmental Protection Act ERAs scheme. The business participant is the holder named in 'Customer Name'; the register's own identifier (RSO Number) and the registration status are not business attributes.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "rso-register", "record_path": null}`

**Record id:** `columns` ['RSO Number'] — RSO Number is present in 100% of rows and distinct 459/459 in the discovery partition, so it uniquely identifies one registration.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Customer Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "-", "N/A", "Not applicable", "?"]}) | 0.8 | 1150 / 1150 |  | 'Customer Name' is the name of the RSO registration holder, i.e. the legal person the registration was issued to. Corporate values carry Pty Ltd etc. For 'An in |
| Entity Type | `entity.entity_type` | trim, map_enum({"mapping": {"Corporation (Company)": "company", "An individual or Sole trader": "sole_trader", "Governme | 0.85 | 1151 / 1151 |  | Column explicitly states the holder's legal form, so entity_type is stated, not guessed. Government forms (GOC, state department, local government authority) al |
| Business Number | `entity.acn` | trim, regex_extract({"pattern": "^(?:ACN\\s*)?(\\d{9})$", "group": 1}), acn | 0.8 | 614 / 651 | {'ACN_CHECKSUM': 2} | Business Number carries prefixed identifiers from several schemes. Nine-digit values are ACNs, published as 'ACN 123456789'; the optional-prefix regex also tole |
| Business Number | `entity.abn` | trim, regex_extract({"pattern": "^ABN\\s*(\\d{11})$", "group": 1}), abn | 0.8 | 26 / 651 |  | The column's 11-digit shapes are 'ABN 12345678901' values (e.g. ABN 61250757901, 80769308350, 52429278345). They are extracted and checksum-validated with the a |
| Location | `address.locality` | trim, regex_extract({"pattern": "^([^,]+)", "group": 1}), collapse_whitespace, upper | 0.85 | 1151 / 1151 |  | Location is 'LOCALITY, STATE, POSTCODE' (all discovery rows match that shape); the first comma-separated segment is the suburb/locality. |
| Location | `address.state` | trim, regex_extract({"pattern": ",\\s*([^,]+?)\\s*,\\s*\\d{3,4}\\s*$", "group": 1}), state | 0.85 | 1143 / 1151 |  | The segment between locality and postcode is the state/territory, sometimes abbreviated (QLD, VIC, NSW) and sometimes spelled out ('Queensland'). The regex capt |
| Location | `address.postcode` | trim, regex_extract({"pattern": ",\\s*(\\d{3,4})\\s*$", "group": 1}), postcode | 0.85 | 1144 / 1151 |  | Trailing segment is the Australian postcode; the profile shows a few 1-3 digit shapes which the postcode transform re-pads. |
| Registration Date | `observation.valid_from` | trim, null_if({"values": ["", "-"]}), parse_date({"formats": ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/ | 0.75 | 1151 / 1151 |  | Registration Date is the date the holder's RSO registration took effect, i.e. the date the 'X is a registered suitable operator' claim became true; used as the  |

**Constants:**
- `address.country` = `AU` (conf 0.9): Queensland (Australia) state register published by the QLD environment department; all Location values are Australian state/postcode pairs.

**Deliberately unmapped:**
- `RSO Number` — Identifier of the suitable-operator registration record itself, not of the business. Used only as record_id; formats vary (649054 / RSO001334 / 9-digit) so it is not a stable external business identifier.
- `Registration Status` — Status of the registration/licence (only value in the file is 'Registered'), not the status of the legal entity; mapping it to entity.status would falsely assert every holder is 'active'.
- `Location` — Emitted only for its parts (locality, state, postcode). The value is a locality/state/postcode triplet with no street number, street name or PO box, so it is not a full premises address and is deliberately NOT mapped to address.full.

**Held-out run:** 1151 records, 1151 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 2 values rejected: {'ACN_CHECKSUM': 2} (`entity.acn`)

**Critic:** All nine rules are correctly targeted. Notable correct calls: Customer Name is the registration holder's legal name (not a trading name); Entity Type is an explicit source column so entity_type is stated rather than guessed, with ARBN holders going to 'other' and GOC/state/local government to 'government'; the shared 'Business Number' column is split into an ABN rule and a checksum-validated ACN rule that cannot cross-fire, and the ARBN nine-digit value is correctly excluded from ACN; Registration Date is properly used as observation.valid_from rather than entity.date_registered; RSO Number and Registration Status are rightly left unmapped because they describe the registration, not the business entity. No important source column that matches an ontology target was left unmapped; Location is decomposed into locality/state/postcode and is not a full street/premises address, so declining address.full is correct. Minor residual risk: rows whose ACN fails checksum (e.g. the cited ACN 409225509 / 912679254) yield no ACN identifier at all, and postcode re-padding of 1-3 digit values should be confirmed against the full file, neither of which mis-targets a field.

**Agent notes:** Register of holders of suitable-operator registrations for ERAs. 'Business Number' is a multi-scheme identifier column: ACN-prefixed (and bare 9-digit) values go to entity.acn, ABN-prefixed 11-digit values go to entity.abn, and ARBN-prefixed values (e.g. ARBN 010937112) are neither, so no identifier is emitted and the holder's entity_type is 'other'. ARBN values are the only identifier shapes deliberately not emitted. A small number of ACN-prefixed values fail the ACN checksum in the source; these are reported as ACN_CHECKSUM errors rather than being emitted unvalidated. 'Customer Name' covers both companies and sole traders; for the latter the person's name is the legal name of the registration holder. Location is a postal/locality line only, so address.full is intentionally left unmapped.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.acn', 'address.full']
    - + added `('Business Number',)` -> `entity.abn`
    - - removed `('Location',)` -> `address.full`
    - ~ changed `('Business Number',)` -> `entity.acn` (steps/confidence)
    - ~ changed `('Registration Date',)` -> `observation.valid_from` (steps/confidence)
    - ~ changed `('Entity Type',)` -> `entity.entity_type` (steps/confidence)
    - ~ changed `('Location',)` -> `address.state` (steps/confidence)

## Decision

This experimental proposal is outside the approval queue.
