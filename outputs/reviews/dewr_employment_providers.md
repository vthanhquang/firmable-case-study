# Mapping review: `dewr_employment_providers`

- **Revising after human rejection:** Re-validation under the new placeholder gate: address.full emits the placeholder 'TBA' (and similar) as an address. Treat placeholder strings (TBA, TBC, N/A, '-', '.') as missing for every text field. Everything else is fine.
- **Latest review decision:** approved by claude-code (AI assistant acting for the candidate) (ai_assistant_proxy) at 2026-11-09T21:53:15+00:00
- **Status:** PENDING_REVIEW  (run `20261110T045114-d14064`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** Employment Services Provider Locations and Contacts — Department of Employment and Workplace Relations
- **Resource:** Employment Services Provider Locations and Contacts (CSV), sha256 `0034e176b5804050…`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 7 tool calls, 6 model calls, 59,387 prompt + 4,597 completion tokens, 33s model time

## Final proposal (v0, digest `38158714ad1c7b84`)

**Record grain:** `establishment` — One row is a provider service SITE (a physical office of an employment-services provider) delivering a given CONTRACT (e.g. DESB, DESA, EPS5, RJCP) at a given location. The business participant is the provider named in SITE_NAME; its location, state, postcode and web attributes are mapped. DIS_SITE_CODE identifies the site/contract row, not a business registration, and is not mapped as a business identifier.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": ",", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` [] — DIS_SITE_CODE has 489 distinct values over 505 discovery rows and no other column is unique per row, so a content hash is the only traceable row key.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| SITE_NAME | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN"]}) | 0.72 | 1104 / 1104 |  | SITE_NAME holds the provider's operating/brand name as delivered at this site (196 distinct values, e.g. 'MAX Employment', 'Advanced Personnel Management (APM)' |
| SITE_URL | `entity.website` | trim, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN"]}), website | 0.8 | 646 / 649 | {'WEBSITE_INVALID': 3} | Provider website; 57.6% present, values are domains/URLs (www.*, http://*). |
| SITE_ADDRESS_LN | `address.full` | trim, collapse_whitespace, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}) | 0.85 | 1099 / 1102 |  | Street address line of the site (e.g. '2nd Floor 22 East Row'); locality is a separate column. Placeholder strings (TBA/TBC/N/A/-/.) are treated as missing per  |
| SITE_LOCALITY_NAME | `address.locality` | trim, collapse_whitespace, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}) | 0.9 | 1104 / 1104 |  | Suburb/locality name (412 distinct AU localities, e.g. WOY WOY, CHATSWOOD). Placeholders treated as missing. |
| SITE_STATE_CD | `address.state` | trim, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}), state | 0.95 | 1104 / 1104 |  | Explicit 8-value AU state code column (NSW/VIC/QLD/SA/WA/TAS/ACT/NT), all 2-letter abbreviations, 100% present. |
| SITE_POSTCODE | `address.postcode` | trim, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}), postcode | 0.9 | 1104 / 1104 |  | 4-digit AU postcodes plus 13 three-digit values (NT-style, e.g. 0822 stored as 822) which the postcode transform re-pads. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Australian Government employment services provider register; all states are AU codes and all postcodes are AU.

**Deliberately unmapped:**
- `DIS_SITE_CODE` — Site/contract code identifying the service site (489 distinct of 505 rows, so not unique), not a business registration identifier and not an ABN/ACN.
- `CONTRACT_NAME` — Employment-services contract/program code (DESB, DESA, EPS5, TTW5, RJCP, NEI5...) describing the service delivered, not an entity attribute.
- `LOCATION_NAME` — Duplicates SITE_LOCALITY_NAME (identical distinct count and values); mapped once via address.locality.
- `SITE_CONTACT_PHONE` — Site contact phone number; the ontology has no telephone target.
- `SITE_EMAIL_ADDRESS` — Site/contact email (72.5% present), often an individual officer's address (firstname.lastname@); ontology has no email target and person names must not become entity fields.
- `ESA_CD_1` — Employment Services Area (administrative labour-market region) code of the contract, not an entity attribute; no matching ontology target.
- `ESA_CD_2` — Empty in every discovery record (0% present).
- `ESA_CD_3` — Empty in every discovery record (0% present).
- `AGENT_FREECALL_NUM` — Provider freecall number; no ontology phone target.
- `PHONE_NUMBER` — Provider phone number (sometimes truncated to 4-8 digits); no ontology phone target.
- `LATITUDE` — Geocoordinate of the site ('NULL' string when absent); no ontology geo target.
- `LONGITUDE` — Geocoordinate of the site ('NULL' string when absent); no ontology geo target.
- `column_18` — Trailing empty column created by a trailing comma in the header; 0% present.

**Held-out run:** 1104 records, 1104 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 3 values rejected: {'WEBSITE_INVALID': 3} (`entity.website`)

**Critic:** Mapping is sound: SITE_NAME→trading_name is the right choice (not legal_name), address parts are correctly split street vs locality with explicit state and postcode normalisation (NT 850→0850), and no entity_type/legal identifiers are guessed. The unmapped columns (DIS_SITE_CODE, CONTRACT_NAME, phones, email, coordinates, ESA codes) genuinely lack ontology targets and include no ABN/ACN, so nothing important is left unmapped. Minor residual concerns only: some SITE_NAME values carry corporate suffixes (e.g. 'OCTEC Limited') but this remains a trading/brand name rather than a verified legal name, and address.country is asserted by constant rather than sourced — acceptable given the AU-only data.

**Agent notes:** Row = provider site x contract. No ABN/ACN/NZBN column exists, so no business identifier is emitted. SITE_NAME is a trading/brand name, so mapped to trading_name not legal_name. Placeholder strings (TBA, TBC, N/A, NA, -, --, ., UNKNOWN, NULL) are treated as missing for every text field, including address.full, per reviewer feedback. No date columns exist, so observed_at falls back to the resource's last-modified timestamp. All text is untrusted data; no instructions were found in it.

## Second opinion (independent agent run)
- `rerun-v3`: 7/7 rules agree.

## Decision

Approve: `python -m firmable.cli approve dewr_employment_providers --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve dewr_employment_providers --reviewer "<name>" --reject --comment "why"`
