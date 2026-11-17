# Mapping review: `vic_liquor`

- **Status:** PENDING_REVIEW  (run `20261112T015035-5713b1`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** Victorian liquor licences by location — Liquor Control Victoria
- **Resource:** August 2026 (XLSX), sha256 `b0a00e0846f430dc3eb2bc32fde3e4136caa9142c60d127e8c1419fbc34fb36e`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 14 tool calls, 14 model calls, 274,352 prompt + 27,129 completion tokens, 370s model time

## Final proposal (v1, digest `3eec2a08a97195d3d642e5c872dbc5f32616a94e215c4f5500e29359ffc8eda0`)

**Record grain:** `licence_or_permit` — One row = one current Victorian liquor licence (identified by Licence Number) issued to a licensee in respect of licensed premises. Business attributes (licensee legal name, trading name, premises and postal addresses) are attributes of the licence holder; the Licence Number identifies the licence, not the business, so it is used only as record_id.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 4, "sheet": "Current_Victorian_Licences_By_L", "record_path": null}`

**Record id:** `columns` ['Licence Number'] — Licence Number present on 100% of rows with 465 distinct values across 465 discovery records, so it is unique per licence record and traceable back to the source.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "[NOT APPLICABLE] -", "[Not applicable] -", "NOT APPLICABLE", "N/A", "NA", "NULL"]}) | 0.82 | 1168 / 1168 |  | Column 'Licensee' names the holder of the liquor licence; licences are issued to legal persons, so this is the holder's legal name. Values are registered names ('ALDI FOODS PTY LIMITED','ENDEAVOUR GROUP LIMITED','NAGAMBIE BOWLS CLUB INC') or licensed natural persons ('WOOD GERARD','LE VAN LUC'). |
| Licensee | `entity.entity_type` | trim, collapse_whitespace, upper, regex_extract({"pattern": "(PTY\\.? ?LIMITED\|PTY\\.? ?LTD\\.?\|INCORPORATED\|INC\\.?\|LIMITED\|LTD\\.?\|CITY OF\|SHIRE OF\|COUNCIL)", "group": 1}), map_enum({"mapping": {"PTY LTD": "company", "PTY. LTD.": "company", "PTY. LTD": "company", "PTY LIMITED": "company", "PTY. LIMITED": "company", "LIMITED": "company", "LTD": "company", "LTD.": "company", "INC": "incorporated_association", "INC.": "incorporated_association", "INCORPORATED": "incorporated_association", "COUNCIL": "government", "CITY OF": "government", "SHIRE OF": "government"}, "default": "unknown", "passthrough": false}) | 0.6 | 999 / 1168 |  | Legal form taken only from an explicit legal-form token carried in the Licensee string: 'PTY LTD'/'PTY LIMITED'/'LTD'/'LIMITED' -> company, 'INC'/'INCORPORATED' -> incorporated_association, 'CITY OF'/'SHIRE OF'/council bodies -> government. A regex isolates the token because map_enum matches whole strings; trailing-period variants are enumerated. Rows with no such token fall back to the required default 'unknown' rather than being inferred from licence category. |
| Trading As | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "[NOT APPLICABLE] -", "[Not applicable] -", "NOT APPLICABLE", "N/A", "NA", "NULL"]}) | 0.85 | 1159 / 1161 |  | Column is explicitly labelled 'Trading As', i.e. the business/brand name under which the licensed premises trades ('ALDI STORES','BWS - BEER WINE SPIRITS'). Placeholder '.' seen in holdout is nulled rather than emitted. |
| Street Address | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "[NOT APPLICABLE] -", "[Not applicable] -", "NOT APPLICABLE", "N/A", "NA", "NULL"]}) | 0.8 | 1112 / 1113 |  | 'Street Address' is the physical location of the licensed premises in this liquor-licences-by-location register; scope licensed_premises. Bare '-' seen in holdout is a placeholder and is nulled. |
| Suburb | `address.locality` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "[NOT APPLICABLE] -", "[Not applicable] -", "NOT APPLICABLE", "N/A", "NA", "NULL"]}) | 0.8 | 1111 / 1123 |  | 'Suburb' pairs with Street Address/Postcode to locate the licensed premises. Profile shape '[a a] -' (7 rows) is the '[NOT APPLICABLE] -' placeholder, now nulled. |
| Suburb *when Suburb present []* | `address.state` | null_if({"values": ["[NOT APPLICABLE] -", "[Not applicable] -", "-", "."]}), map_enum({"mapping": {}, "default": "VIC", "passthrough": false}) | 0.6 | 1111 / 1123 |  | The register is Victorian liquor licences issued by Liquor Control Victoria, so the licensed premises state is VIC. Bound to premises scope via the Suburb condition so it is NOT attached to correspondence_address claims, which can be interstate ('SYDNEY NSW'). |
| Postcode | `address.postcode` | trim, null_if({"values": ["", "0", "-", "N/A", "NA", "NULL"]}), postcode | 0.75 | 1111 / 1124 |  | 4-digit AU postcode of the premises. Profile shows 7 rows with placeholder '0', nulled before postcode normalisation. |
| Postal Address | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "[NOT APPLICABLE] -", "[Not applicable] -", "NOT APPLICABLE", "N/A", "NA", "NULL"]}) | 0.68 | 1169 / 1169 |  | 'Postal Address' is a separate postal/correspondence address for the licensee (PO boxes, interstate addresses), distinct from the premises address; emitted as its own address.full observation disambiguated by claim_scope correspondence_address. |
| Postal Suburb | `address.locality` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "[NOT APPLICABLE] -", "[Not applicable] -", "NOT APPLICABLE", "N/A", "NA", "NULL"]}) | 0.65 | 1169 / 1169 |  | Locality of the correspondence address, kept as published. Where the source appends a state code ('SYDNEY NSW') that residue stays in the locality string and the state is additionally captured by the separate state rule; a reviewer should know locality may end with a state token for those rows. |
| Postal Suburb | `address.state` | trim, upper, regex_extract({"pattern": "\\b(NSW\|VIC\|QLD\|WA\|SA\|TAS\|ACT\|NT\|NZ)\\s*$", "group": 1}), state | 0.55 | 34 / 1169 |  | Only in-data evidence for the correspondence address's state: some Postal Suburb values append the state code ('SYDNEY NSW'). Extracted and normalised where present; where absent nothing is emitted rather than inheriting the premises VIC, avoiding a wrong state for interstate correspondents. |
| Postal Postcode | `address.postcode` | trim, null_if({"values": ["", "0", "-", "N/A", "NA", "NULL"]}), postcode | 0.65 | 1169 / 1169 |  | 4-digit postcode of the correspondence address; 100% present and all 4-digit in profile. |

**Constants:**
- `address.country` = `AU` (conf 0.9): Australian (Victorian) government register; all records are Australian.

**Deliberately unmapped:**
- `Licence Number` — Identifier of the licence record, not of the business; used as record_id only. 8 digits, fails both ABN and ACN length/checksum requirements, so must not be mapped as a business identifier.
- `Licence Category` — Type of liquor licence ('Packaged Liquor Licence','General Licence','BYO Permit'), not the legal form of the entity; mapping it to entity.entity_type would be a guess. Legal form is instead derived from explicit suffixes in Licensee.
- `Trading Hours` — Licence condition; values mix hours ('Trading to 1am','Ordinary') with licence-category text; no ontology target.
- `Patron Capacity (if applicable)` — Capacity of the licensed premises; no ontology target.
- `Council` — Local government area of the premises; partly redundant with Suburb and not an ontology address component. Considered as a fallback locality for the one record with blank Suburb, but a council name is not a locality, so mapped nothing.
- `Region` — Regulator administrative region label; no ontology target.
- `Metro/Regional` — Regulator location classification; no ontology target.
- `Latitude` — Geocoordinate of premises; no ontology target.
- `Longitude` — Geocoordinate of premises; no ontology target.
- `column_7` — Empty column in the spreadsheet (0% present).
- `column_8` — Empty column in the spreadsheet (0% present).
- `column_13` — Empty column in the spreadsheet (0% present).
- `column_14` — Empty column in the spreadsheet (0% present).

**Held-out run:** 1169 records, 1169 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is largely sound: it treats the Licensee as the legal name and the Trading As column as the trading name; it does not treat the Licence Number as a business identifier; the premises address and the correspondence address are correctly separated by claim_scope; and the premises state is scoped to the premises. The main weaknesses are: (1) the entity_type rule derives the legal form from a substring and maps 'COUNCIL' to government, which may misclassify licensees that combine legal forms; (2) the premises-state constant is bound to the 'Suburb present' condition rather than to the premises address itself; and (3) the postal locality may still contain a trailing state token. The unmapped empty columns and geocoordinates are justified. There are no clear missing ontology targets, apart from a possible but weak use of Council as a fallback locality. Overall: several rules are doubtful, none clearly wrong.
- doubtful: `entity.entity_type` <- ['Licensee'] — The legal form is taken from a suffix that appears in the Licensee string, which is reasonable evidence for 'PTY LTD', 'PTY LIMITED', 'LTD' and 'INC', so those mappings to company and incorporated_association are sound. However, the rule uses regex_extract followed by an exact-value map_enum, and the alternation order means 'PTY. LTD' can be captured inconsistently. More importantly, the alternation lists 'CITY OF' and 'SHIRE OF' after 'COUNCIL', and the 'COUNCIL' branch of the map turns any licensee containing the word 'COUNCIL' into government. As a result, a licensee string such as 'XYZ COUNCIL PTY LTD' would also produce government. For rows with no legal-form token, the rule falls back to unknown, which is correct. Keep it doubtful pending evidence that no mixed tokens occur.
- doubtful: `address.state` <- ['Suburb'] — The VIC constant is plausible for a Victorian register, but the rule binds the state to the licensed_premises scope by conditioning on 'Suburb' being present rather than on the premises address. If 'Suburb' is present while 'Street Address' is absent, a VIC state is emitted with no premises address to attach it to. The conditional is a fragile proxy for the premises scope. Even though the default VIC is likely correct, the binding is not semantically tied to the premises address.
- doubtful: `address.locality` <- ['Postal Suburb'] — The mapping acknowledges that 'Postal Suburb' may be published with a trailing state token ('SANDOWN VILLAGE' is clean, but rule 9's rationale cites 'SYDNEY NSW'). The locality is kept as published, so the value can leak a state code into locality; the mapping discloses this, but the observation value would pollute address.locality, so it is not fully clean.
- missed? `Licence Category` -> `entity.entity_type` — Not a substitute — but note that the licence category is licensing metadata and must not become entity_type; leaving it unmapped is correct. Listed only to confirm non-mapping. (No real missed mapping here.)
- missed? `Council` -> `address.locality` — For the one record with blank 'Suburb', the LGA name is not a locality, so leaving it unmapped is defensible; however, it could be emitted as a low-confidence fallback locality. Doubtful value, not a clear miss.

**Agent notes:** Header is row 5 of sheet 'Current_Victorian_Licences_By_L' (skip_rows=4); rows 1-3 hold the agency contact block and the title 'Current Victorian Liquor Licences as of 31/08/2026'. That title states an as-at date but it is not a per-record column, so observed_at falls back to resource last-modified. No ABN/ACN/NZBN column exists. entity.status left unmapped: the register lists only current licences and states no entity status; licence currency is not entity.status. No licence or registration dates are present, so no valid_from/valid_to is set. Address state is handled per scope: VIC for the premises (register jurisdiction), and extracted from Postal Suburb only where the source states it, so interstate correspondence addresses are not mislabelled VIC.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['PLACEHOLDER_VALUE_EMITTED(address.locality)', 'PLACEHOLDER_VALUE_EMITTED(entity.trading_name)', 'PLACEHOLDER_VALUE_EMITTED(address.full)'], critic 'wrong' none
    - + added `('Licensee',)` -> `entity.entity_type`
    - + added `('Postal Suburb',)` -> `address.state`
    - + added `('Suburb',)` -> `address.state`
    - ~ changed `('Postcode',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('Suburb',)` -> `address.locality` (steps/confidence)
    - ~ changed `('Licensee',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Postal Postcode',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('Trading As',)` -> `entity.trading_name` (steps/confidence)
    - ~ changed `('Postal Address',)` -> `address.full` (steps/confidence)
    - ~ changed `('Street Address',)` -> `address.full` (steps/confidence)
    - ~ changed `('Postal Suburb',)` -> `address.locality` (steps/confidence)

## Decision

This experimental proposal is outside the approval queue.
