# Mapping review: `qld_suitable_operators`

- **Status:** PENDING_REVIEW  (run `20261112T024240-9486e6`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** Suitable Operator Register (SOR) for Environmentally Relevant Activities (ERAs) — Environment, Tourism, Science and Innovation
- **Resource:** qld_suitable_operators.xlsx (XLSX), sha256 `d89014bdfa9616779dd19e3076e563a631c0af92137e78178da1a285e2dfd4ba`
- **Licence:** CC-BY-4.0
- **Agent effort:** 2 proposal(s), 12 tool calls, 12 model calls, 181,478 prompt + 11,562 completion tokens, 217s model time

## Final proposal (v1, digest `97c4e375e35e338cff0011c5f6bb91a4b404a4fb09d41d5851c572c8fa3d75ba`)

**Record grain:** `licence_or_permit` — One record is one suitable-operator registration (identified by an RSO number) held by a corporation, government body, association or individual/sole trader. This is program participation, not the entity register itself; the holder's attributes (name, ACN/ABN, form, location) are mapped, while the registration status, RSO number and the program registration date are programme facts and stay unmapped.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "rso-register", "record_path": null}`

**Record id:** `columns` ['RSO Number'] — RSO Number is the department-issued suitable-operator reference; distinct 459/459 across the discovery partition, so unique per registration (one row per registration).

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Customer Name *when Entity Type in ['Corporation (Company)', 'Government Owned Corporation', 'Incorporated Association', 'State Government Department', 'Australian Registered (Foreign) Body', 'Local Government Authority']* | `entity.legal_name` | trim, collapse_whitespace | 0.85 | 641 / 641 |  | For explicit non-individual entity types the Customer Name is the registered style of the licence holder (e.g. '"OVER THE TOP" ROOF RESTORATIONS PTY. LTD'); licences are issued to legal persons, so this is the holder's legal name. Quote/asterisk characters retained as publisher text. |
| Business Number *when Business Number present []* | `entity.acn` | regex_extract({"pattern": "^ACN\\s*(\\d{9})$", "group": 1}), acn | 0.85 | 614 / 651 | {'ACN_CHECKSUM': 2} | Values are 'ACN nnnnnnnnn'; 237/249 present values are 9-digit ACNs and 96% of present values pass the ACN checksum. The prefix-anchored regex requires the literal 'ACN' prefix so 'ABN ...' and 'ARBN ...' values are not misparsed. Values failing the checksum are reported as errors, never repaired. |
| Business Number *when Business Number present []* | `entity.abn` | regex_extract({"pattern": "^ABN\\s*(\\d{11})$", "group": 1}), abn | 0.85 | 26 / 651 |  | A minority of Business Number values are prefixed 'ABN ' with 11 digits; the ABN checksum transform validates them. 'ACN' and 'ARBN' values are excluded by the prefix anchor, and no ACN is ever derived from an ABN. |
| Entity Type | `entity.entity_type` | trim, map_enum({"mapping": {"Corporation (Company)": "company", "Government Owned Corporation": "government", "Incorporated Association": "incorporated_association", "State Government Department": "government", "Local Government Authority": "government", "Australian Registered (Foreign) Body": "other"}, "default": "unknown", "passthrough": false}) | 0.8 | 1151 / 1151 |  | Entity Type explicitly states the business form. 'Local Government Authority' added as government (heldout showed Allconnex Water under this label). 'Government Owned Corporation' -> government, following the source's own 'Government' wording, though it is legally a company; low-stakes either way. 'An individual or Sole trader' is a combined label that cannot distinguish a person from a business form, so it falls to the default 'unknown' rather than a guessed sole_trader. |
| Location | `address.locality` | regex_extract({"pattern": "^\\s*([^,]+)\\s*,", "group": 1}), trim | 0.65 | 1150 / 1151 |  | Location is 'SUBURB, STATE, POSTCODE' (e.g. 'South Brisbane, QLD, 4101'); the first comma-delimited component is the suburb/locality. Scope is ambiguous (holder contact address vs licensed premises) and is flagged in notes. |
| Location | `address.state` | regex_extract({"pattern": ",\\s*([A-Za-z]{2,3})\\s*,", "group": 1}), state | 0.8 | 1144 / 1151 |  | Second comma-delimited component is the state abbreviation (QLD dominant, plus VIC/NSW/WA and NT/SA/TAS/ACT); normalised with the state transform. Rows whose separator shape defeats extraction stay null rather than being guessed. |
| Location | `address.postcode` | regex_extract({"pattern": ",\\s*(\\d{3,4})\\s*$", "group": 1}), postcode | 0.8 | 1144 / 1151 |  | Trailing comma-delimited component is the postcode; some raw values are 3/2/1 digits, and the postcode transform re-pads 3-digit NT codes. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Queensland environment department register; all locations are AU suburbs/states, with a minority of holders located interstate (VIC, NSW, WA).

**Deliberately unmapped:**
- `Registration Status` — Status of the suitable-operator registration (a permit), not of the legal entity; only value present is 'Registered'. Mapping it to entity.status would misstate the entity's status.
- `RSO Number` — Department-assigned suitable-operator reference for the registration; used as record_id. It identifies the permit, not the business.
- `Registration Date` — Per publisher documentation this is the date the holder was registered as a suitable operator (programme participation), not the entity's incorporation/company registration date, and the claim_scope catalogue has no programme-registration scope. Mapping it to entity.date_registered would assert a legal-entity registration date the source does not support.
- `Customer Name (Entity Type = 'An individual or Sole trader')` — For these rows Customer Name is a natural person's name (e.g. 'WILLIAM YOUNG'). Nothing in the source establishes it as a registered business/trading name, and the combined label cannot establish a business form; the ontology has no target for an individual's name, so it is not emitted.
- `Business Number values with 'ARBN' prefix` — 'ARBN nnnnnnnnn' is an Australian Registered Body Number, issued to a foreign registered body; it is neither an ACN nor an ABN, so those rows yield no entity.acn/abn and must not be mistaken for missing identifiers.

**Held-out run:** 1151 records, 1151 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 2 values rejected: {'ACN_CHECKSUM': 2} (`entity.acn`)

**Critic:** Most rules are sound: legal_name is restricted to explicit non-individual entity types, ACN and ABN are prefix-anchored and checksummed so they are not confused with each other, and the combined 'individual or sole trader' label is correctly refused a sole_trader enum rather than guessed. The programme-level columns (RSO number, registration date, registration status) are correctly kept out of entity.date_registered and entity.status. Weak points: entity_type has two inference-based values (foreign body -> other, government-owned corporation -> government) marked doubtful; the address rules carry real risk because Location has no evidence of being an entity address versus a licensed premises/site, and one held-out record shows address.state dropped when the state is spelled out ('Queensland'). Country constant AU is justified. Unmapped 'Registration Status' should state how deregistered/suspended values would be treated, since the programme status cannot transfer to entity.status.
- doubtful: `entity.entity_type` <- ['Entity Type'] — The mapping is generally defensible, but two choices sit on inference rather than an explicit source category. 'Australian Registered (Foreign) Body' -> other discards that the holder is a registered foreign body (arguably company-adjacent), and 'Government Owned Corporation' -> government overrides a label that literally says corporation; the rationale itself concedes it is legally a company. The deliberate refusal to map the combined 'An individual or Sole trader' label to sole_trader is correct and is correctly reflected in the held-out records (entity_type unknown).
- doubtful: `address.locality` <- ['Location'] — The positional extraction works on the held-out values, but the claim_scope is unestablished: Location carries no evidence of whether it is the holder's mailing/contact address or a licensed premises, and the reviewer must not accept an entity address without evidence. In one held-out record (Allconnex Water, BEENLEIGH) and in the ABC record placed in NSW for a Queensland EAA programme, the value looks like a business or site location rather than a verified entity address. The rule emits a bare locality with no scope flag, so a premise location would silently become the entity's locality. Emitting it as address.locality is acceptable only with an explicit 'source scope unverified' qualifier.
- doubtful: `address.state` <- ['Location'] — The state rule fails on a real value shape: 'Pinkenba, Queensland, 4008' spells the state out, and the held-out observations show address.state missing for that record (only locality and postcode emitted). The rule leaves the state null rather than resolving 'Queensland' -> QLD, so a Queensland record loses its state. Extraction is otherwise correct for the abbreviated form (QLD/NSW observed).
- missed? `Customer Name (Entity Type = 'An individual or Sole trader')` -> `entity.legal_name` — The mapping deliberately drops these, and the ontology has no natural-person name target, but the decision is conservative and defensible; if the ontology later gains a person-name target these values should be routed there rather than silently discarded. Listed for visibility only.
- missed? `Registration Status` -> `entity.status` — The current unmapped rationale correctly notes the only value seen is 'Registered' (programme status). However, if any deregistered/suspended values appear in the full set, the entity.status enum exists; the mapping should state explicitly how those values would be handled rather than leaving the column wholly unmapped with no guard. Not counted as a miss of a matching entity status, since the source status is permit-level.
- missed? `Location (state component, spelled-out form)` -> `address.state` — Values such as 'Queensland' defeat the two-letter-plus-comma regex, leaving held-out address.state absent. The state transform / an extra normalisation for full state names is needed to avoid losing QLD state on those rows.

**Agent notes:** Programme register: each row is a suitable-operator registration (RSO number) held by a corporation, government body, association or an individual/sole trader. Registration Status, RSO Number and Registration Date describe the registration, not the entity, so they are unmapped. Customer Name is asserted as legal name only for explicit non-individual entity types; natural-person names under the combined 'An individual or Sole trader' label are not emitted. Business Number mixes ACN-, ABN- and ARBN-prefixed values, handled by two prefix-anchored rules so neither a wrong-length ACN nor an ABN-derived ACN is produced; a few values genuinely fail the ACN checksum and are reported as errors. Location 'SUBURB, STATE, POSTCODE' is split into locality/state/postcode because it is the only geographic evidence; its scope (holder contact vs licensed premises) is ambiguous, so it is emitted without a specific address claim_scope.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.trading_name', 'entity.date_registered']
    - + added `('Location',)` -> `address.postcode`
    - + added `('Location',)` -> `address.locality`
    - + added `('Location',)` -> `address.state`
    - - removed `('Registration Date',)` -> `entity.date_registered`
    - - removed `('Customer Name',)` -> `entity.trading_name`
    - ~ changed `('Business Number',)` -> `entity.abn` (steps/confidence)
    - ~ changed `('Business Number',)` -> `entity.acn` (steps/confidence)
    - ~ changed `('Entity Type',)` -> `entity.entity_type` (steps/confidence)

## Decision

This experimental proposal is outside the approval queue.
