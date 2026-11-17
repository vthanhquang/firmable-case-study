# Mapping review: `dewr_employment_providers`

- **Status:** PENDING_REVIEW  (run `20261112T020855-b3968c`, prompt `prompts-v7`, model `deepseek-v4-flash`)
- **Dataset:** Employment Services Provider Locations and Contacts — Department of Employment and Workplace Relations
- **Resource:** Employment Services Provider Locations and Contacts (CSV), sha256 `0034e176b580405064272e688c7bf51230f051880263cdeeb5107ac00bd7a979`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 11 tool calls, 11 model calls, 145,241 prompt + 14,849 completion tokens, 163s model time

## Final proposal (v1, digest `9bffaf5a2539d0ff754f369e7fd9b0d69652ab1b42f779ef2474b5aaffc4b702`)

**Record grain:** `establishment` — One record is a provider's service site (outlet): the location at which an employment-services provider delivers a named contract (DESA, DESB, EPS5, TTW5, NEI5, RJCP...). The same physical site recurs once per contract, and identical site/contract keys also repeat in the source, so record identity is taken from the full row content. Business attributes mapped here (name, website, address) are those of the provider operating that site; the file carries no ABN/ACN or registered legal name.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": ",", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` ['DIS_SITE_CODE', 'CONTRACT_NAME', 'LOCATION_NAME', 'SITE_NAME', 'SITE_CONTACT_PHONE', 'SITE_ADDRESS_LN', 'SITE_LOCALITY_NAME', 'SITE_STATE_CD', 'SITE_POSTCODE', 'SITE_URL', 'SITE_EMAIL_ADDRESS', 'ESA_CD_1', 'ESA_CD_2', 'ESA_CD_3', 'AGENT_FREECALL_NUM', 'PHONE_NUMBER', 'LATITUDE', 'LONGITUDE'] — DIS_SITE_CODE alone is not unique (489 distinct in 505 discovery rows) and the (DIS_SITE_CODE, CONTRACT_NAME) pair still collides on held-out records (7 duplicates), so no column key is unique per record; identity is hashed from the full row content instead.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| SITE_NAME | `entity.trading_name` | collapse_whitespace, trim, null_if({"values": ["", "NA", "N/A", "NULL"]}) | 0.62 | 1106 / 1106 |  | SITE_NAME holds the provider organisation's trading/brand name as published in the provider directory (e.g. 'MAX Employment', 'Advanced Personnel Management (APM)', 'Vision Australia', 'NOVA Employment'). These are business/display names, not registered legal names, and the source has no legal-name, ABN or ACN column, so trading_name is the correct target rather than legal_name. |
| SITE_URL | `entity.website` | trim, null_if({"values": ["", "NA", "N/A", "NULL"]}), regex_extract({"pattern": "(?:[A-Za-z][A-Za-z0-9+.-]*://)?(?:[A-Za-z0-9][A-Za-z0-9-]*\\.)+[A-Za-z]{2,}(?:/\\S*)?", "group": 0}), website | 0.82 | 647 / 650 |  | SITE_URL is the provider's web address (present on 57.6% of discovery rows, 88 distinct domains such as www.apm.net.au, www.sureway.com.au), mostly without scheme. A few cells contain phone numbers or 'TTY: ...' text instead of a domain; regex_extract keeps only the domain-shaped part so non-URL junk (e.g. '467027758', 'TTY: 03 96143062') yields no observation instead of a rejected value, and the website op then normalises the domain. Discovery coverage is unchanged (291/291 domain values still emitted) with zero errors. |
| SITE_ADDRESS_LN, SITE_LOCALITY_NAME, SITE_STATE_CD, SITE_POSTCODE | `address.full` | collapse_whitespace, trim, null_if({"values": ["", "NA", "N/A", "NULL"]}) | 0.72 | 1106 / 1106 |  | Composed full address of the provider site from the street address line, locality, state code and postcode; all four components are present on 100% of discovery and held-out rows. |
| SITE_LOCALITY_NAME | `address.locality` | collapse_whitespace, trim, null_if({"values": ["", "NA", "N/A", "NULL"]}) | 0.9 | 1106 / 1106 |  | SITE_LOCALITY_NAME is the suburb/locality of the site's street address (100% present, 412 distinct AU localities such as HEALESVILLE, IPSWICH). |
| SITE_STATE_CD | `address.state` | trim, state | 0.95 | 1106 / 1106 |  | SITE_STATE_CD is the site's Australian state/territory abbreviation (NSW, VIC, QLD, SA, WA, TAS, NT, ACT observed in discovery and held-out rows). |
| SITE_POSTCODE | `address.postcode` | trim, postcode | 0.95 | 1106 / 1106 |  | SITE_POSTCODE is the site's 4-digit Australian postcode; 13 discovery values are 3 digits and are NT postcodes missing the leading zero (postcode op re-pads, e.g. 850 -> 0850). |

**Constants:**
- `address.country` = `AU` (conf 0.9): Australian Government (DEWR) employment-services provider directory; every state code is an Australian state/territory.

**Deliberately unmapped:**
- `DIS_SITE_CODE` — Internal code for the provider's site/outlet; not an ABN/ACN and not unique per record (489 distinct in 505 discovery rows). Identifies a site under contract, not a business.
- `CONTRACT_NAME` — Code of the employment-services contract/programme the site delivers (DESB, DESA, EPS5, TTW5, NEI5, RJCP...). Describes the site's contract, not an attribute of the legal entity; the contract's status is not entity.status.
- `LOCATION_NAME` — Provider site location label; duplicates SITE_LOCALITY_NAME (same 412 distinct values) and adds no separate attribute.
- `SITE_CONTACT_PHONE` — Phone number of the site; no phone target in the ontology.
- `AGENT_FREECALL_NUM` — Agent free-call number; no phone target in the ontology.
- `PHONE_NUMBER` — Additional site phone number; no phone target in the ontology.
- `SITE_EMAIL_ADDRESS` — Site contact email (often a named individual's mailbox); no email target in the ontology.
- `ESA_CD_1` — Employment Service Area code for the first ESA the site serves; a geography/contract descriptor, not a business identifier or ANZSIC industry code.
- `ESA_CD_2` — Second Employment Service Area code; geography/contract descriptor, mostly blank.
- `ESA_CD_3` — Third Employment Service Area code; geography/contract descriptor, mostly blank.
- `LATITUDE` — Site geocode ('NULL' placeholders present); no coordinate target in the ontology.
- `LONGITUDE` — Site geocode ('NULL' placeholders present); no coordinate target in the ontology.
- `column_18` — Trailing empty column created by the header's final comma; 0% populated.

**Held-out run:** 1106 records, 1106 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All 7 mapping rules are correct. SITE_NAME is appropriately mapped to trading_name (not legal_name) given the source lacks registered names or ABN/ACN. Website extraction handles dirty data correctly. Address components are properly decomposed and normalized, including NT postcode zero-padding. The constant country value is justified. Unmapped columns are correctly excluded: DIS_SITE_CODE and CONTRACT_NAME are site/contract identifiers not business attributes; phone/email fields have no ontology targets; ESA codes are geographic descriptors not industry codes; coordinates lack ontology support. No missed mappings identified.

**Agent notes:** Header has a trailing comma, producing an empty 19th field (column_18) - ignored. No ABN/ACN/NZBN, legal-name, entity-type, entity-status or date columns exist, so no identifier, entity_type, status, date_registered or observation validity dates can be asserted. SITE_NAME appears truncated at 30 characters in places (e.g. 'Auctus Business Training and Consul', 'Campbell Page MORELAND/'), so trading names may be incomplete. Some SITE_URL cells hold phone numbers or text such as 'TTY: 03 96143062', which are dropped by the domain regex rather than emitted as websites. Held-out validation showed (DIS_SITE_CODE, CONTRACT_NAME) is not unique, so record_id now uses a content hash over all source columns.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' none
    - ~ changed `('SITE_URL',)` -> `entity.website` (steps/confidence)
    - ~ record_id columns -> content_hash ['DIS_SITE_CODE', 'CONTRACT_NAME', 'LOCATION_NAME', 'SITE_NAME', 'SITE_CONTACT_PHONE', 'SITE_ADDRESS_LN', 'SITE_LOCALITY_NAME', 'SITE_STATE_CD', 'SITE_POSTCODE', 'SITE_URL', 'SITE_EMAIL_ADDRESS', 'ESA_CD_1', 'ESA_CD_2', 'ESA_CD_3', 'AGENT_FREECALL_NUM', 'PHONE_NUMBER', 'LATITUDE', 'LONGITUDE']

## Decision

This experimental proposal is outside the approval queue.
