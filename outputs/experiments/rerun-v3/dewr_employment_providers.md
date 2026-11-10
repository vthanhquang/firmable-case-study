# Mapping review: `dewr_employment_providers`

- **Status:** PENDING_REVIEW  (run `20261110T051127-5871b9`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** Employment Services Provider Locations and Contacts — Department of Employment and Workplace Relations
- **Resource:** Employment Services Provider Locations and Contacts (CSV), sha256 `0034e176b5804050…`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 9 tool calls, 9 model calls, 99,423 prompt + 8,959 completion tokens, 60s model time

## Final proposal (v1, digest `0de7b51ee0b46e53`)

**Record grain:** `establishment` — Each row is one employment-services SITE (office/premises) operated by a provider under a specific employment services contract (CONTRACT_NAME, e.g. DESA/DESB/EPS5). The business participant is the provider organisation named in SITE_NAME; the row describes that provider's SITE PREMISES address (street address), plus website and phone contacts. DIS_SITE_CODE is the site identifier, not a business identifier, so it is not mapped to the entity.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": ",", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` [] — DIS_SITE_CODE is not unique per record (489 distinct over 505 discovery rows) because the same site appears once per contract code. No other column or combination is guaranteed unique, so a content hash over all mapped source fields is used for traceability.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| SITE_NAME | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["", "NULL", "N/A", "NA", "TBA", "TBC", "-"]}) | 0.62 | 1104 / 1104 |  | SITE_NAME holds the provider's operating/brand name (e.g. 'MAX Employment', 'Advanced Personnel Management', 'CoAct/Community Solutions', 'Job Centre Australia' |
| SITE_URL | `entity.website` | trim, null_if({"values": ["", "NULL", "NA", "N/A", "TBA", "TBC", "-"]}), regex_extract({"pattern": "(?i)(?:https?://)?(? | 0.75 | 646 / 649 |  | SITE_URL contains provider domains such as 'www.apm.net.au' or 'http://maxsolutions.com.au/'; present in ~58% of rows. Held-out data showed some non-URL junk in |
| SITE_ADDRESS_LN | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "NULL", "NA", "N/A", "TBA", "TBC", "-", "UNKNOWN"]}) | 0.8 | 1099 / 1102 |  | SITE_ADDRESS_LN is the site's PREMISES street address (e.g. '2nd Floor 22 East Row', 'Shop 6 & 7 The HUB Wynyard Street'), which is what address.full represents |
| SITE_LOCALITY_NAME | `address.locality` | trim, collapse_whitespace, upper, null_if({"values": ["", "NULL", "TBA", "TBC"]}) | 0.9 | 1104 / 1104 |  | Suburb/town of the site, e.g. 'CANBERRA', 'WOY WOY'; same value domain as LOCATION_NAME (412 distinct each in discovery). |
| SITE_STATE_CD | `address.state` | trim, upper, state | 0.95 | 1104 / 1104 |  | Two/three letter AU state abbreviation (8 distinct discovery values: NSW,VIC,QLD,SA,WA,TAS,NT,ACT). |
| SITE_POSTCODE | `address.postcode` | trim, postcode | 0.9 | 1104 / 1104 |  | 4-digit AU postcodes; 13 of 505 discovery rows are 3-digit (NT codes such as 822) which the postcode transform re-pads. |

**Constants:**
- `address.country` = `AU` (conf 0.9): Australian government register of Australian employment-services sites; all states are AU state codes and postcodes are AU format.

**Deliberately unmapped:**
- `DIS_SITE_CODE` — Short site code (e.g. A230, V352) with no checksum; not unique per record (same site repeats across contract codes). The record's own site ID, not a business identifier.
- `CONTRACT_NAME` — Employment-services contract type (DESB, DESA, EPS5, TTW5, RJCP...) describing the program under which the site is contracted, not an attribute of the business entity.
- `LOCATION_NAME` — Duplicates SITE_LOCALITY_NAME (same 412 distinct value domain) - the site's town; already captured via address.locality.
- `SITE_CONTACT_PHONE` — Site contact phone number; phone is not a target in the canonical ontology.
- `SITE_EMAIL_ADDRESS` — Contact email only; there is no email target in the ontology and it is not a website (critic concurred). Some values are personal staff addresses (e.g. kal.perera@...), which are not entity fields.
- `ESA_CD_1` — Employment Services Area code (e.g. 5ACT, 4SOE) - a program administrative region, not an ANZSIC industry code and not a business identifier.
- `ESA_CD_2` — Blank in 100% of discovery rows (wrapped second ESA code).
- `ESA_CD_3` — Blank in 100% of discovery rows (wrapped third ESA code).
- `AGENT_FREECALL_NUM` — 13/1800 freecall number for the agent; phone is not an ontology target.
- `PHONE_NUMBER` — Site phone number; phone is not a target in the canonical ontology.
- `LATITUDE` — Site geocoordinate; no geo target in the canonical ontology (and 7 discovery rows contain the literal 'NULL').
- `LONGITUDE` — Site geocoordinate; no geo target in the canonical ontology (and 7 discovery rows contain the literal 'NULL').
- `column_18` — Empty trailing column created by trailing delimiter in header; 0% present.

**Held-out run:** 1104 records, 1104 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All mapped fields are semantically correct for their canonical targets given the ontology. SITE_NAME is properly treated as trading_name (conservative, since legal names are not evidenced). Website regex correctly gates out junk phone-like values seen in discovery. Address fields map premises street address, locality, state, and AU postcode with correct zero-padding of NT 3-digit codes. The unmapped columns (DIS_SITE_CODE, CONTRACT_NAME, ESA codes, phones, LAT/LONG, email) are appropriately excluded because the ontology has no corresponding targets or they are duplicates/administrative codes, not business identifiers. No wrong enum guesses, no entity_type/legal_name/ABN fabrications were made. No genuine missed source columns.
- missed? `CONTRACT_NAME` -> `entity.industry_code` — Not appropriate: CONTRACT_NAME (DESB/DESA/EPS5/TTW5/RJCP/HLS5/SPP5/NEI5) is an employment-services programme code, not ANZSIC. Correctly left unmapped; no ANZSIC source present. Not a genuine miss.
- missed? `SITE_EMAIL_ADDRESS` -> `entity.website` — No — emails are not websites; some are personal staff addresses. Correctly excluded; ontology has no email target.
- missed? `LATITUDE / LONGITUDE` -> `address.full` — Not applicable: ontology has no geo target and geocoordinates are not an address string. Correctly unmapped.
- missed? `LOCATION_NAME` -> `address.locality` — Duplicate of SITE_LOCALITY_NAME; already captured. Correctly unmapped to avoid duplicate observations.

**Agent notes:** No ABN/ACN/NZBN column exists in this extract (checksum-valid rates on numeric columns are ~0%), so no business identifier can be mapped. entity_type is left out because no column states a legal structure. SITE_NAME is trading_name, not legal_name: values are brand names with inconsistent variants. address.full is explicitly the PREMISES (street) address of the site, not a postal address. Held-out fixes: placeholder 'TBA' now nulled in address fields and SITE_NAME; SITE_URL gated by a domain-shaped regex so junk values (bare phone numbers, 'TTY: ...') are dropped instead of erroring.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['PLACEHOLDER_VALUE_EMITTED(address.full)'], critic 'wrong' none
    - ~ changed `('SITE_URL',)` -> `entity.website` (steps/confidence)
    - ~ changed `('SITE_LOCALITY_NAME',)` -> `address.locality` (steps/confidence)
    - ~ changed `('SITE_ADDRESS_LN',)` -> `address.full` (steps/confidence)
    - ~ changed `('SITE_NAME',)` -> `entity.trading_name` (steps/confidence)
    - ~ record_id content_hash -> content_hash []

## Decision

Approve: `python -m firmable.cli approve dewr_employment_providers --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve dewr_employment_providers --reviewer "<name>" --reject --comment "why"`
