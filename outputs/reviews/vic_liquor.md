# Mapping review: `vic_liquor`

- **Revising after human rejection:** Rejected: the revision added Postal Address -> address.full and Postal Suburb -> address.locality. That was not requested and mixes the licensee's postal address with the licensed premises in the same fields, so every record would claim two different addresses. Keep the previous approved scope (premises address only; postal columns unmapped) and ONLY add the placeholder handling for '[NOT APPLICABLE] -' style values.
- **Latest review decision:** approved by claude-code (AI assistant acting for the candidate) (ai_assistant_proxy) at 2026-11-09T22:43:12+00:00
- **Status:** PENDING_REVIEW  (run `20261110T054156-0453b4`, prompt `prompts-v4`, model `deepseek-v4-flash`)
- **Dataset:** Victorian liquor licences by location — Liquor Control Victoria
- **Resource:** August 2026 (XLSX), sha256 `b0a00e0846f430dc…`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 7 tool calls, 6 model calls, 62,988 prompt + 5,267 completion tokens, 39s model time

## Final proposal (v0, digest `3974d55e7dff6033`)

**Record grain:** `licence_or_permit` — Each row is one current Victorian liquor licence (Licence Number unique per row) held by a licensee at licensed premises. Entity fields describe the licensee business; address fields describe the licensed premises ONLY. The licensee's postal mailing address columns are left unmapped because they describe a different location than the premises and mixing them into the same address fields would make each record claim two different addresses.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 4, "sheet": "Current_Victorian_Licences_By_L", "record_path": null}`

**Record id:** `columns` ['Licence Number'] — Licence Number: 465/465 present and 465 distinct (shape 99999999); identifies the licence record, not a business identifier.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "dataset_metadata_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee | `entity.legal_name` | trim, collapse_whitespace, regex_extract({"pattern": "^(?!THE SECRETARY$)(?!SECRETARY$)(?!THE TRUSTEE$)(?!THE OWNER$)(?! | 0.6 | 1159 / 1160 |  | Column headed 'Licensee' = holder of the licence, mostly in legal-name form (PTY LTD / LIMITED / CITY OF X). Also carries officer/contact-role strings such as ' |
| Trading As | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["", "-", "--", ".", "..", "...", "N/A", "NA", "N.A.", "N/A -", "TBA", "TB | 0.85 | 1150 / 1152 |  | 'Trading As' is explicitly the business/trading name, distinct from the licensee column (451 distinct of 465, 99.1% present). Placeholder strings nulled. |
| Street Address | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "-", "--", ".", "..", "...", "N/A", "NA", "N.A.", "N/A -", "TBA", "TB | 0.85 | 1103 / 1104 |  | Street address of the licensed premises (present 94.2%). Premises address, not postal. |
| Suburb | `address.locality` | trim, collapse_whitespace, upper, regex_extract({"pattern": "^(?!\\[?NOT APPLICABLE\\]?).*$", "group": 0}), null_if({"va | 0.85 | 1102 / 1114 |  | Suburb of the licensed premises (95.7% present). 7 records carry the placeholder '[Not applicable] -' (remote/pre-retail sellers without premises, shape '[a a]  |
| Postcode | `address.postcode` | trim, null_if({"values": ["", "0", "0000", "-", ".", "N/A", "NA", "N/A -", "NOT APPLICABLE", "NOT APPLICABLE -", "[NOT A | 0.85 | 1102 / 1115 |  | Premises postcode; 438 4-digit values plus 7 placeholder '0' values which are nulled. Postal postcodes are not used here (some are interstate, e.g. '2000'). |

**Constants:**
- `address.state` = `VIC` (conf 0.9): Victorian liquor licence register published by Liquor Control Victoria; licensed premises are in Victoria.
- `address.country` = `AU` (conf 0.9): Australian (Victorian) register.

**Deliberately unmapped:**
- `Licence Number` — Licence identifier, not a business identifier; used only as record_id.
- `Licence Category` — Licence type (General/On-Premises/Packaged Liquor/Producer's etc.); not an entity type or status in the ontology.
- `Trading Hours` — Licence condition text; no ontology target.
- `Patron Capacity (if applicable)` — Premises attribute; no ontology target.
- `Council` — Local government area of premises; no ontology target for LGA.
- `Region` — Administrative region; no ontology target.
- `Metro/Regional` — Administrative classification; no ontology target.
- `Latitude` — Coordinate; no ontology target.
- `Longitude` — Coordinate; no ontology target.
- `Postal Address` — Licensee's postal mailing address, per reviewer direction kept unmapped: it is a different location from the licensed premises and would make each record claim two addresses in address.full.
- `Postal Suburb` — Part of the licensee postal mailing address (some carry interstate suffixes e.g. 'SYDNEY NSW'); per reviewer direction kept unmapped to avoid mixing postal and premises addresses.
- `Postal Postcode` — Part of the licensee postal mailing address; some are interstate (e.g. 2000) and cannot be used under the VIC premises constant.
- `column_7` — Empty spacer column.
- `column_8` — Empty spacer column.
- `column_13` — Empty spacer column.
- `column_14` — Empty spacer column.

**Held-out run:** 1160 records, 1160 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Premises address mapping is coherent and postal columns are correctly excluded. The main doubts are entity.legal_name (mixed licensee column that can carry contact-role and sole-trader personal names) and the constant address.state=VIC, which assumes all licensed premises are in Victoria without a verifying source column. Trading name and premises address parts are sound.
- doubtful: `entity.legal_name` <- ['Licensee'] — Mostly legal-name form, but the column mixes role/officer strings (e.g. 'THE SECRETARY' correctly nulled) and sole-trader personal names ('ARNOLD BRUCE'). Personal name is not necessarily a legal_name as registered; and the role regex only covers a handful of patterns. Reasonable but not clean; a risk of person-name-as-business-name for sole traders.
- doubtful: `address.state` <- [] — Constant VIC is plausible for a Liquor Control Victoria register, but the source carries postal suburbs with interstate suffixes; the rationale assumes premises are all VIC. If any premises are outside VIC (or postal-only rows), this constant will mislabel. Constant assignment without a verifying column should be flagged.
- missed? `Patron Capacity (if applicable)` -> `none (premises attribute)` — Correctly unmapped; no ontology target for capacity.
- missed? `Licence Category` -> `entity.industry_code (possible, ANZSIC-adjacent)` — Could arguably inform industry classification but is a licence type, not ANZSIC; leaving unmapped is defensible.
- missed? `Postal Address / Postal Suburb / Postal Postcode` -> `none (or a separate licensee-address record)` — Correctly excluded to avoid mixing postal and premises addresses; no ontology target for a second address.

**Agent notes:** XLSX: 4 title/branding rows precede the header (skip_rows=4); sheet 'Current_Victorian_Licences_By_L'; 465 data rows, 21 columns incl. two pairs of empty spacer columns. Sheet subtitle states 'Current Victorian Liquor Licences as of 31/08/2026' - a snapshot date, not per-record; observed_at falls back to dataset metadata. Nothing in the data changes per record over time, so address columns need no validity dates. No ABN/ACN column: Licence Number is 8-digit (ABN checksum 0%, ACN checksum 9.2% = chance) - deliberately unmapped. entity_type unmapped (no column states legal entity type). REVISION 3: adopts the reviewer's approved scope unchanged (premises address only; ALL postal columns unmapped) and adds ONLY the placeholder handling: '[Not applicable] -' in Suburb (7 rows, shape '[a a] -') is upper-cased and gated out at address.locality; the same '[NOT APPLICABLE] -' placeholder is nulled in address.full and the '0' postcodes in address.postcode so no placeholder value can be emitted.

## Second opinion (independent agent run)
- `rerun-v3`: 6/7 rules agree; **check these first:**
    - only this proposal: `('Street Address',)` -> `address.full` 

## Decision

Approve: `python -m firmable.cli approve vic_liquor --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve vic_liquor --reviewer "<name>" --reject --comment "why"`
