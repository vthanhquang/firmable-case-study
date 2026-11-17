# Mapping review: `vic_liquor`

- **Status:** PENDING_REVIEW  (run `20261112T023328-32a675`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** Victorian liquor licences by location — Liquor Control Victoria
- **Resource:** August 2026 (XLSX), sha256 `b0a00e0846f430dc3eb2bc32fde3e4136caa9142c60d127e8c1419fbc34fb36e`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 14 tool calls, 13 model calls, 166,190 prompt + 17,776 completion tokens, 266s model time

## Final proposal (v1, digest `6721959762b3c3a5eb1def83afc08797539515f66228c67692399db706f4b8dd`)

**Record grain:** `licence_or_permit` — One row is one current Victorian liquor licence (Licence Number) issued to a licensee at licensed premises. Business attributes of the holder (legal name, trading name) and the premises address are mapped; the licence number itself is the record key, not a business identifier.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 4, "sheet": "Current_Victorian_Licences_By_L", "record_path": null}`

**Record id:** `columns` ['Licence Number'] — Licence Number is present on every row and distinct across the discovery records (465 distinct / 465 records); it uniquely identifies a licence record.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee | `entity.legal_name` | trim, collapse_whitespace | 0.72 | 1168 / 1168 |  | The 'Licensee' column names the holder of the liquor licence. Licences are issued to legal persons, so this is the holder's name as registered; values are mostly registered names ('ALDI FOODS PTY LIMITED', '... CLUB INC') but can be natural persons/sole traders (e.g. 'ARNOLD BRUCE'), so entity_type is left unknown rather than inferred. |
| Trading As | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["", ".", "-", "N/A", "NA", "NOT APPLICABLE", "[NOT APPLICABLE]", "[NOT APPLICABLE] -", "[Not applicable] -", "[Not Applicable] -", "NULL", "NIL"]}) | 0.9 | 1159 / 1161 |  | Column is explicitly a trading name ('Trading As'), e.g. 'ALDI STORES' for licensee 'ALDI FOODS PTY LIMITED'. Placeholder punctuation such as '.' is treated as missing. |
| Street Address | `address.full` | trim, collapse_whitespace, upper, null_if({"values": ["", "-", ".", "N/A", "NA", "NOT APPLICABLE", "[NOT APPLICABLE]", "[NOT APPLICABLE] -", "[Not applicable] -", "[Not Applicable] -", "NULL", "NIL"]}) | 0.8 | 1112 / 1113 |  | Street Address is the address of the licensed premises covered by the licence, not the licensee's registered office; mapped to generic address.full with explicit claim_scope licensed_premises. Placeholder '-' is treated as missing. |
| Suburb | `address.locality` | trim, collapse_whitespace, upper, null_if({"values": ["", "-", ".", "N/A", "NA", "NOT APPLICABLE", "[NOT APPLICABLE]", "[NOT APPLICABLE] -", "[Not applicable] -", "[Not Applicable] -", "NULL", "NIL"]}) | 0.84 | 1111 / 1123 |  | Suburb of the licensed premises, immediately following the street address. Uppercasing keeps the source's all-uppercase locality style and makes placeholder variants such as '[NOT APPLICABLE] -' detectable; those are treated as missing. |
| Postcode | `address.postcode` | trim, null_if({"values": ["", "0", "-", "."]}), postcode | 0.8 | 1111 / 1124 |  | Postcode of the licensed premises block; the source's '0' placeholders are nulled before postcode normalisation. |

**Constants:**
- `address.state` = `VIC` (conf 0.9): Register of Victorian liquor licences published by Liquor Control Victoria; the licensed premises are Victorian.
- `address.country` = `AU` (conf 0.95): Australian state register.

**Deliberately unmapped:**
- `Licence Number` — Identifier of the licence record, not a business identifier; also 8 digits and fails abn/acn checksums, so it must not feed those fields.
- `Licence Category` — Category of the licence, not the legal entity's type or status; no allowed enum value fits licence categories.
- `Trading Hours` — Licence condition, no ontology target.
- `Patron Capacity (if applicable)` — Premises capacity, no ontology target.
- `column_7` — Empty spacer column in the sheet.
- `column_8` — Empty spacer column in the sheet.
- `Council` — Local government area of the premises; the ontology has no council field.
- `Region` — Administrative region label, no ontology target.
- `column_13` — Empty spacer column.
- `column_14` — Empty spacer column.
- `Metro/Regional` — Location classification of the premises, no ontology target.
- `Latitude` — No ontology field for coordinates.
- `Longitude` — No ontology field for coordinates.
- `Postal Address` — Postal/correspondence address of the licensee, which may be a PO box or interstate (Postal Suburb includes 'SYDNEY NSW'); not established as the registered office or the licensed premises, so it is left unmapped rather than conflated with the premises address.
- `Postal Suburb` — Part of the licensee's postal/correspondence address; can be interstate (e.g. 'SYDNEY NSW'), so it cannot support the VIC premises-location constant and is left unmapped.
- `Postal Postcode` — Part of the licensee's postal/correspondence address; can be interstate (e.g. 2000), so it cannot support the VIC premises-location constant and is left unmapped.

**Held-out run:** 1169 records, 1169 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All seven rules are directionally sound: the licensee name is not a trading name, the Trading As column is a genuine trading name, the premises address block is distinguished from Postal Address, placeholder nulling is careful, entity_type is left unknown, and no licence number was passed into abn/acn. The one weakness is that the VIC/AU constants are emitted even when the premises street, locality, and postcode are all empty; this produces an address that consists only of state and country. A minor gap is that the licensee's postal address block is fully unmapped. It could be captured with a distinct claim_scope such as licensee_postal, but deliberately leaving it unmapped is defensible and avoids confusing it with the premises address.
- missed? `Licence Category` -> `entity.industry_code` — Not a true industry code, so this is a weak suggestion; the licence category describes the licensed activity ('Restaurant and cafe Licence', 'Producer's Licence') and could serve as a proxy when no ANZSIC value is available. Its omission is acceptable because it is not a genuine industry code.
- missed? `Postal Address` -> `address.full` — This is currently unmapped deliberately. It is the licensee's correspondence address, which could be treated as the registered/contact address where the premises block is empty, for example ORIENTAL VODKA PTY LTD. If it is mapped, it must carry a claim_scope such as licensee_postal to avoid confusing it with the premises address.
- missed? `Postal Suburb` -> `address.locality` — This is only needed together with Postal Address under the same licensee_postal claim_scope, because it can be interstate.
- missed? `Postal Postcode` -> `address.postcode` — This is only needed together with Postal Address under the same licensee_postal claim_scope, and it must not inherit the VIC constant.

**Agent notes:** Header row is row 5 of the sheet (contact/title rows above), hence skip_rows=4 with the named sheet. The sheet title says the list is current as of 31/08/2026; that is a snapshot date for the whole list, not a per-record observation, so observed_at falls back to resource_last_modified. No ABN/ACN column exists in this extract. Street Address/Suburb/Postcode are licensed-premises values and are emitted with claim_scope licensed_premises; the licensee's postal address is deliberately not mixed into those fields because it may be a PO box or interstate. Lat/Long, Council, Region and licence category are retained by the publisher but have no ontology target.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['PLACEHOLDER_VALUE_EMITTED(address.locality)', 'PLACEHOLDER_VALUE_EMITTED(entity.trading_name)', 'PLACEHOLDER_VALUE_EMITTED(address.full)'], critic 'wrong' none
    - ~ changed `('Postcode',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('Trading As',)` -> `entity.trading_name` (steps/confidence)
    - ~ changed `('Licensee',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Street Address',)` -> `address.full` (steps/confidence)
    - ~ changed `('Suburb',)` -> `address.locality` (steps/confidence)
    - ~ record_id columns -> columns ['Licence Number']

## Decision

This experimental proposal is outside the approval queue.
