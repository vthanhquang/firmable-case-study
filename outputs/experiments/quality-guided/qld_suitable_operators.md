# Mapping review: `qld_suitable_operators`

- **Status:** PENDING_REVIEW  (run `20261112T015255-5846cd`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** Suitable Operator Register (SOR) for Environmentally Relevant Activities (ERAs) — Environment, Tourism, Science and Innovation
- **Resource:** qld_suitable_operators.xlsx (XLSX), sha256 `d89014bdfa9616779dd19e3076e563a631c0af92137e78178da1a285e2dfd4ba`
- **Licence:** CC-BY-4.0
- **Agent effort:** 2 proposal(s), 13 tool calls, 13 model calls, 215,720 prompt + 18,742 completion tokens, 393s model time

**Current extraction:** Legacy record-level validity rules below have no effect on
claims. Check each claim's validity paths before approving.

## Final proposal (v1, digest `2099e4d581b143ab5c3ec79e91b588dc23e2a67c2b7516c130ab4d056b71214b`)

**Record grain:** `licence_or_permit` — One record is a registration of a person or corporation as a 'suitable operator' (a prerequisite to applying for an environmental authority under the QLD Environmental Protection Act). The business participant is the registrant named in 'Customer Name'; the RSO Number and Registration Date describe program participation, not a business identifier or the entity's own company-registration date. There is no authority or premises in this record.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "rso-register", "record_path": null}`

**Record id:** `content_hash` [] — RSO Number is unique per record in the discovery partition (459/459 distinct) but it is the department's suitable-operator reference for program participation, not a business identifier and not resolvable to an entity key; content hash keeps rows traceable without implying it identifies a business.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Customer Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "null", "NULL", "N/A", "-", "."]}) | 0.6 | 1150 / 1150 |  | Suitable-operator registration is issued to a legal person, so the registrant's name is the holder's legal name; rows are either registered company names ('... PTY LTD') or individual person names. Label is only 'Customer Name', which is soft, so confidence is moderate. Natural-person rows are kept as legal_name because a sole trader registers under their own legal name. |
| Business Number *when Business Number present []* | `entity.acn` | regex_extract({"pattern": "^ACN\\s*(\\d{9})$", "group": 1}), acn | 0.85 | 614 / 651 | {'ACN_CHECKSUM': 2} | The cell is prefixed with its identifier scheme. The regex anchors on the literal 'ACN' prefix and captures exactly the 9 following digits, so ABN-prefixed, ARBN-prefixed, malformed-length and non-ACN values produce no match (null, nothing emitted) instead of being pushed through the acn transform and failing the checksum. One checksum-invalid ACN still errors out rather than being converted. |
| Business Number *when Business Number present []* | `entity.abn` | regex_extract({"pattern": "^ABN\\s*(\\d{11})$", "group": 1}), abn | 0.85 | 26 / 651 |  | A minority of rows carry 'ABN 99 999 999 999'. The regex anchors on the literal 'ABN' prefix and captures exactly 11 digits, so ACN-prefixed and ARBN-prefixed rows cannot reach the abn transform - this removes the previous 95.9% ABN_LENGTH error rate caused by routing every ACN cell into this rule. |
| Entity Type | `entity.entity_type` | trim, map_enum({"mapping": {"Corporation (Company)": "company", "Government Owned Corporation": "government", "Local Government Authority": "government", "State Government Department": "government", "Government Department": "government", "Incorporated Association": "incorporated_association", "Australian Registered (Foreign) Body": "other", "Foreign Company": "other", "Partnership": "partnership", "Trust": "trust", "An individual or Sole trader": "unknown"}, "default": "unknown", "passthrough": false}) | 0.72 | 1151 / 1151 |  | Column explicitly states business form. Added the missing 'Local Government Authority' -> government entry flagged on held-out data. 'Australian Registered (Foreign) Body' is now 'other' rather than 'company', since an ARBN body is a foreign registered body and collapsing it to company was a guess. 'An individual or Sole trader' stays unknown because the label conflates natural persons and sole traders. |
| Registration Date | `observation.valid_from` | parse_date({"formats": ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"]}) | 0.6 | 1151 / 1151 |  | Dates are ISO datetimes from the XLSX serial cells. Per publisher evidence this date is when the suitable-operator program registration was assigned: it is the start of the claim this record makes (program participation), and no entity.date_registered is produced from it. |
| Location | `address.locality` | trim, regex_extract({"pattern": "^\\s*([^,]+),", "group": 1}), collapse_whitespace, upper | 0.75 | 1150 / 1151 |  | Location is a 'SUBURB, STATE, POSTCODE' composite; the first comma segment is the locality. Claim scope corrected from licence_holder_address to entity_contact_address: this is the registrant's contact address on the suitable-operator program registration, and the record contains no environmental authority or premises. |
| Location | `address.state` | regex_extract({"pattern": ",\\s*([A-Za-z ]{2,20}?)\\s*,", "group": 1}), trim, state | 0.8 | 1149 / 1151 |  | Second comma-delimited segment is the state. The regex now matches full state names as well as abbreviations, because held-out record 10 carries 'Pinkenba, Queensland, 4008' which a 2-3 letter pattern missed entirely; the state transform normalises both forms. |
| Location | `address.postcode` | regex_extract({"pattern": "(\\d{3,4})\\s*$", "group": 1}), postcode | 0.75 | 1144 / 1151 |  | Trailing 3-4 digit segment is the postcode; 3-digit values are re-padded by the postcode transform. |
| Location | `address.full` | trim, collapse_whitespace | 0.7 | 1151 / 1151 |  | Raw 'suburb, state, postcode' string retained verbatim as the address as published. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Queensland state register of suitable operators; every location carries an Australian state name/abbreviation and Australian postcode.

**Deliberately unmapped:**
- `RSO Number` — Department-assigned suitable-operator reference for program participation (formats vary: 6-digit, RSO+6, 9-digit). It is the record's own ID, not a business identifier, and has no ontology target.
- `Registration Status` — Only value is 'Registered', which is the status of the suitable-operator registration (a licence-like status), not the legal entity's own status; licence/permit status must not map to entity.status.
- `Business Number (prefix 'ARBN')` — An ARBN identifies an Australian Registered (Foreign) Body and is neither an ACN nor an ABN; the ontology has no ARBN target, so these values are deliberately left unrouted rather than mis-emitted as ACN. The row's entity_type is 'other', which carries the evidence.

**Held-out run:** 1151 records, 1151 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 2 values rejected: {'ACN_CHECKSUM': 2} (`entity.acn`)
- [warning] RECORD_VALIDITY_IGNORED: The engine ignores this legacy record-level date. Set a rule's validity path only when the source dates that claim. (`observation.valid_from`)

**Critic:** Strong mapping for a program register that carries no licence, premises, or company-registration data. The two identifier rules are prefix-anchored and checksummed, so ACN/ABN/ARBN cannot cross-contaminate; ARBN is deliberately left unrouted and entity_type 'other' carries the foreign-body evidence. entity_type is sourced from an explicit column, and the conflated 'individual or Sole trader' category is correctly reduced to unknown instead of guessed as sole_trader. Registration Date and RSO Number are properly withheld from entity.date_registered and any business identifier, consistent with the publisher evidence that they describe program participation. Address components are correctly scoped as the registrant's contact address, not premises; the state pattern and transform handle full names. The only residual doubts are soft: 'Customer Name' as legal_name for natural persons, the ABC being labelled a Government Owned Corporation in the source, and observation.valid_from not appearing in the observed output for rule 4 — none of which is a semantic mis-mapping of a target. No obviously matching source column was left unmapped.

**Agent notes:** Revised after held-out review. Business Number is scheme-prefixed (ACN / ABN / ARBN); routing is now done by anchoring the regex on the literal prefix and capturing exactly the mandated digit length, so ACN and ABN can no longer leak into each other's transform and ARBN values are not emitted as ACN. entity_type gained 'Local Government Authority' -> government and now maps foreign registered bodies to 'other'. Address claim_scope is entity_contact_address, not licence_holder_address, because this register records program registration, not an environmental authority or premises. The address.state regex now accepts full state names. 'An individual or Sole trader' remains entity_type unknown by design. Some rows have no Business Number (natural persons) and some have a blank Customer Name; those rows emit the facts they do have.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['HIGH_ERROR_RATE(entity.abn)'], critic 'wrong' ['entity.acn', 'entity.abn', 'entity.entity_type', 'address.state']
    - ~ changed `('Entity Type',)` -> `entity.entity_type` (steps/confidence)
    - ~ changed `('Location',)` -> `address.state` (steps/confidence)
    - ~ changed `('Customer Name',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Business Number',)` -> `entity.abn` (steps/confidence)
    - ~ changed `('Business Number',)` -> `entity.acn` (steps/confidence)

## Decision

This experimental proposal is outside the approval queue.
