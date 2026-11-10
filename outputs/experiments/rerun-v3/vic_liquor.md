# Mapping review: `vic_liquor`

- **Status:** PENDING_REVIEW  (run `20261110T051011-49ae0f`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** Victorian liquor licences by location — Liquor Control Victoria
- **Resource:** August 2026 (XLSX), sha256 `b0a00e0846f430dc…`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 12 tool calls, 12 model calls, 136,378 prompt + 9,514 completion tokens, 67s model time

## Final proposal (v1, digest `60e0f30553e61fde`)

**Record grain:** `licence_or_permit` — One record = one current Victorian liquor licence held by a licensee at a licensed premises. The business participant's registered-holder name ('Licensee') and the licensed premises locality/postcode are mapped; the licence number is a licence identifier, not a business identifier.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 4, "sheet": null, "record_path": null}`

**Record id:** `columns` ['Licence Number'] — Licence Number is present on every record and fully distinct (465/465) in discovery; it identifies the licence record. Holdout showed no duplicate-key errors.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [".", "-", "", "n/a"]}) | 0.6 | 1160 / 1160 |  | Revising previous round: 'Licensee' is the registered holder/legal name recorded by the regulator ('LIQUORLAND (AUSTRALIA) PTY LTD', 'ENDEAVOUR GROUP LIMITED',  |
| Trading As | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": [".", "-", "", "n/a"]}) | 0.85 | 1150 / 1152 |  | 'Trading As' is explicitly the trading/display name of the premises ('ALDI STORES', 'JKB BREWING', 'THE MAIN EMPORIUM'). Holdout placeholder '.' now nulled. |
| Suburb | `address.locality` | trim, collapse_whitespace, null_if({"values": [".", "-", ""]}) | 0.85 | 1114 / 1114 |  | Premises suburb; values are clean suburb names (MELBOURNE, EPPING, BAIRNSDALE). |
| Postcode | `address.postcode` | trim, null_if({"values": ["0", "0000", "", "n/a", "-"]}), postcode | 0.8 | 1102 / 1115 |  | Four-digit AU postcode; placeholder '0' rows treated as missing. |

**Constants:**
- `address.state` = `VIC` (conf 0.95): Victorian liquor licence register; licensed premises are in Victoria.
- `address.country` = `AU` (conf 0.95): Australian (Victorian) regulator dataset.

**Deliberately unmapped:**
- `Licence Number` — Licence identifier, not a business identifier; used only as record_id.
- `Street Address` — Street-address fragment without locality ('SUNSET DVE', 'PURCHES STREET') and sometimes just '-'/'', so it is not a complete address; emitting it as address.full overstates completeness (critic verdict: doubtful). Premises locality and postcode are mapped; state/country are constant VIC/AU.
- `Licence Category` — Licence type (General Licence, BYO Permit, ...); no ontology target for licence class.
- `Trading Hours` — Licence trading condition; no ontology target.
- `Patron Capacity (if applicable)` — Premises capacity; no ontology target.
- `Council` — Local government area of premises; no ontology target.
- `Region` — Regulator administrative region; no ontology target.
- `Metro/Regional` — Classification of location; no ontology target.
- `Latitude` — Geocoordinate; no ontology target.
- `Longitude` — Geocoordinate; no ontology target.
- `Postal Address` — Licensee postal address is a secondary address distinct from the licensed premises; the ontology address.* block has no address-type discriminator, so emitting it would conflict with the premises address. Critic suggested modelling it as a secondary address, but the contract offers no way to label it - left unmapped deliberately.
- `Postal Suburb` — Secondary (postal) suburb; cannot be distinguished from premises locality in the ontology address block.
- `Postal Postcode` — Secondary (postal) postcode; cannot be distinguished from premises postcode in the ontology address block.
- `column_7` — Empty spacer column in the spreadsheet.
- `column_8` — Empty spacer column in the spreadsheet.
- `column_13` — Empty spacer column in the spreadsheet.
- `column_14` — Empty spacer column in the spreadsheet.

**Held-out run:** 1160 records, 1160 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Address fields and trading_name are sound. The main risk is entity.legal_name: 'Licensee' mostly holds registered-holder names but also sole-trader personal names and role placeholders ('THE SECRETARY'), so it is a doubtful legal_name rather than a clean fit. Street/premises sub-address and postal address are deliberately unmapped, which is defensible given the ontology's single undiscriminated address block. The key gap remains: no entity_type is derivable, so entity_type is rightly left unmapped (not guessed), and no ABN/ACN exists in source. Dataset grain (licence_or_permit) and licence number treatment as licence ID are reasonable.
- doubtful: `entity.legal_name` <- ['Licensee'] — 'Licensee' is generally the registered holder and fits legal_name for companies (LIQUORLAND (AUSTRALIA) PTY LTD, HYLAND WINES PTY LTD), but heldout shows it also carries non-legal-name values: sole traders (ARNOLD BRUCE) and role placeholders like 'THE SECRETARY' (Cowes Yacht Club). Mapping a contact/role holder name as legal_name is a known failure mode; the caveat acknowledges this but the mapping still emits it unconditionally as legal_name.

**Agent notes:** Reader: xlsx, skip_rows=4 (3 title/blank rows above the header row); 21 columns including 4 empty spacer columns. No ABN/ACN/NZBN published (Licence Number is 8-digit; 0% ABN checksum), so no business identifier is claimed. No column explicitly states entity_type or status, so both are left unmapped (entity_type defaults to unknown rather than being inferred from ' PTY LTD' suffixes, which also occur inside trading names such as 'MORIAC PTY LTD', and many holders are bare personal names). observed_at: the 'as of 31/08/2026' statement lives in a title row, not a data column, so the envelope falls back to resource_last_modified. Licensee and Trading As are frequently identical, producing parallel legal_name/trading_name observations.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['PLACEHOLDER_VALUE_EMITTED(entity.trading_name)', 'PLACEHOLDER_VALUE_EMITTED(address.full)'], critic 'wrong' ['entity.trading_name']
    - + added `('Licensee',)` -> `entity.legal_name`
    - - removed `('Licensee',)` -> `entity.trading_name`
    - - removed `('Street Address',)` -> `address.full`
    - ~ changed `('Postcode',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('Suburb',)` -> `address.locality` (steps/confidence)
    - ~ changed `('Trading As',)` -> `entity.trading_name` (steps/confidence)
    - ~ record_id columns -> columns ['Licence Number']

## Decision

Approve: `python -m firmable.cli approve vic_liquor --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve vic_liquor --reviewer "<name>" --reject --comment "why"`
