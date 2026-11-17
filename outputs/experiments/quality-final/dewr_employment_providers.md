# Mapping review: `dewr_employment_providers`

- **Status:** PENDING_REVIEW  (run `20261112T023946-7cb0f3`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** Employment Services Provider Locations and Contacts — Department of Employment and Workplace Relations
- **Resource:** Employment Services Provider Locations and Contacts (CSV), sha256 `0034e176b580405064272e688c7bf51230f051880263cdeeb5107ac00bd7a979`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 13 tool calls, 12 model calls, 235,190 prompt + 14,015 completion tokens, 98s model time

## Final proposal (v1, digest `c3ab79de711e2257cd0982e981cb7ab0a89501e15cdd31b679bc03f3883aafb2`)

**Record grain:** `establishment` — One record is one contracted employment-services SITE (delivery location) at which a provider organisation delivers a particular contract program (DESA/DESB/EPS5/TTW5/RJCP/NEI5 etc.). The business participant is the provider organisation named in SITE_NAME; its attributes (trading name, website, site address) are mapped. DIS_SITE_CODE is the department-issued site/delivery-point identifier, not a business identifier, so it is not mapped as an entity field. CONTRACT_NAME is the program that the record's grain is defined by, but it is a contract attribute, not an entity field, so it stays unmapped.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": ",", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` [] — DIS_SITE_CODE is not unique per row (489 distinct over 505 discovery rows; the same site code repeats once per contract program, e.g. A230 DESB vs A290 DESB), and no other column is unique either, so a content hash over the whole row is the only traceable identifier.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| SITE_NAME | `entity.trading_name` | collapse_whitespace, trim, null_if({"values": ["", "NULL", "null", "TBA", "N/A", "NA", "-"]}) | 0.62 | 1106 / 1106 |  | SITE_NAME is the name the provider trades under at the delivery site, e.g. 'MAX Employment', 'Advanced Personnel Management (APM)', 'Job Centre Australia', 'ORS Employment Solutions'. These are service-delivery/brand names rather than registered legal names (the file contains no ACN/ABN and no legal-name column), so this is mapped to trading_name only. A few values carry legal-form suffixes ('OCTEC Limited', 'The Salvation Army Employment Plus'), but the register does not assert that these are the registered legal names and the same column also holds brand labels, so the whole column is kept as trading_name rather than splitting it by suffix guesswork. |
| SITE_ADDRESS_LN | `address.full` | collapse_whitespace, trim, null_if({"values": ["", "NULL", "null", "TBA", "TBC", "N/A", "NA", "-", "UNKNOWN"]}) | 0.72 | 1101 / 1104 |  | Street address line of the contracted delivery site. Scope is the site/premises at which employment services are delivered under the contract, not the organisation's registered office. Values sometimes embed suburb text because the source line is free text. Placeholder strings ('TBA' seen in held-out rows) are nulled rather than emitted as an address. |
| SITE_LOCALITY_NAME | `address.locality` | collapse_whitespace, trim, null_if({"values": ["", "NULL", "null", "TBA", "N/A", "NA", "-"]}) | 0.8 | 1106 / 1106 |  | Locality/suburb of the site; duplicates LOCATION_NAME exactly in the sample (412 distinct in both). |
| SITE_STATE_CD | `address.state` | trim, null_if({"values": ["", "NULL", "null", "TBA", "N/A", "NA", "-"]}), state | 0.9 | 1106 / 1106 |  | Two-letter AU state/territory code of the site; 8 distinct values, all standard abbreviations. |
| SITE_POSTCODE | `address.postcode` | trim, null_if({"values": ["", "NULL", "null", "TBA", "N/A", "NA", "-"]}), postcode | 0.9 | 1106 / 1106 |  | 4-digit AU postcode of the site; 13 rows have 3-digit values which are NT postcodes and need re-padding, which the postcode transform handles. |
| SITE_URL | `entity.website` | trim, null_if({"values": ["", "NULL", "null", "TBA", "N/A", "NA", "-"]}), regex_extract({"pattern": "(?:https?://)?(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\\.)+[A-Za-z]{2,}(?:/[^\\s]*)?", "group": 0}), regex_extract({"pattern": "^(?:https?://)?(.*?)/?$", "group": 1}), website | 0.6 | 647 / 650 |  | Provider website, often organisation-level and repeated across that provider's sites (www.apm.net.au x46). 57.6% present. Held-out rows show the column is dirty: some cells hold a bare phone number ('467027758') or 'TTY: 03 96143062'. A domain regex first extracts only a URL-shaped token (dropping 'TTY: 03 96143062' and digit-only cells to null), and the scheme/trailing slash are stripped so http://maxsolutions.com.au/ and www.apm.net.au emit in the same shape before the website check. |

**Constants:**
- `address.country` = `AU` (conf 0.9): Australian Government (DEWR) employment-services provider register; all site state codes are AU states/territories and postcodes are Australian.

**Deliberately unmapped:**
- `DIS_SITE_CODE` — Department-issued site/delivery-point identifier (shape a99/a999, repeats once per contract program). Record's own site ID, not a business identifier, and not unique per record.
- `CONTRACT_NAME` — Employment-services contract program code (DESA, DESB, EPS5, TTW5, RJCP, NEI5...). It is the discriminator that makes the record grain a contracted delivery programme, but it describes a government contract, not the legal entity: there is no contract/entity field for it in the ontology and it is not an ANZSIC code, so it cannot go to entity.industry_code or entity.entity_type.
- `LOCATION_NAME` — Site town label, duplicating SITE_LOCALITY_NAME; mapping both would emit duplicate address.locality observations.
- `SITE_CONTACT_PHONE` — Site contact phone number; the ontology has no telephone field.
- `PHONE_NUMBER` — Site phone number (mixed 4-10 digit values); no telephone target in the ontology.
- `AGENT_FREECALL_NUM` — Agent freecall/helpline number; telephone data, no ontology target. 72.7% blank.
- `SITE_EMAIL_ADDRESS` — Site contact email address; no email field in the ontology. Many are personal-name mailboxes, i.e. contact details rather than entity attributes.
- `ESA_CD_1` — Employment Services Area / contract region code (5SYW, 4CAL, 5ACT...). A departmental service-area classification, not an ANZSIC industry code, so it cannot map to entity.industry_code; it also does not cleanly decompose into a state value and is not mapped to address.state.
- `ESA_CD_2` — Entirely blank in discovery (present_rate 0.0).
- `ESA_CD_3` — Entirely blank in discovery (present_rate 0.0).
- `LATITUDE` — Geocoordinate of the site; 7 rows literally contain 'NULL' and the ontology has no coordinate target.
- `LONGITUDE` — Geocoordinate of the site; same rationale as LATITUDE.
- `column_18` — Empty column produced by a trailing comma in the header row; contains no data.

**Held-out run:** 1106 records, 1106 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is essentially sound: a site-grain register mapped to trading_name plus a site (licensed_premises) address, with country AU, correct NT postcode re-padding, and a website regex that handles dirty cells. No legal-name, ABN/ACN or entity_type guesses are made, and no record-level or licence-style validity is asserted anywhere (no validity paths used at all), so the failure modes around deregistered status, wrong date order and legacy validity targets do not arise. The one substantive concern is rule 0: SITE_NAME mixes brand labels with names carrying legal-form suffixes ('OCTEC Limited', 'The Salvation Army Employment Plus'), and those legal-form strings are asserted as trading_name unchanged; it is defensible and preferable to suffix-based splitting, but the column is not purely a trading name and the rationale's claim that these are all 'the name the provider trades under' overstates the evidence. Remaining source columns are contact/geo/contract fields with no ontology target, correctly left unmapped.
- doubtful: `entity.trading_name` <- ['SITE_NAME'] — SITE_NAME is a per-site delivery/brand label ('Vision Australia', 'Job Centre Australia', 'Sarina Russo Job Access', 'NOVA Employment') and trading_name is defrestricted enough, but the rule only nulls placeholders and never handles values that carry legal-form suffixes ('OCTEC Limited') or a program suffix ('The Salvation Army Employment Plus'). Those are emitted unchanged as trading names, and a handful of them are in fact the organisation's registered name, so the column mixes brand labels and legal names. Keeping it all as trading_name is defensible and safer than guessing, but the rule should record the impurity and at minimum be checked against a legal-name source; as stated it asserts 'trading name' for strings the source does not describe as such.
- missed? `DIS_SITE_CODE` -> `unmapped (agree) / no target` — Agree with leaving unmapped: it is a departmental delivery-point identifier, not an ABN/ACN, so it cannot be a business identifier.
- missed? `CONTRACT_NAME` -> `entity.industry_code (raw source value only, not ANZSIC)` — Correctly not mapped as entity_type/industry_code inference; programme codes are not industry codes, so leaving unmapped is right. No ontology target is missed.
- missed? `ESA_CD_1` -> `address.state (secondary evidence only)` — ESA_CD_1 encodes a service area whose leading digit/suffix (5ACT, NTKR, QCOK) tracks a state/region; it could be used as corroboration for address.state where SITE_STATE_CD is missing, though it must not be autonomously mapped to industry_code. Not a required miss, but worth noting.
- missed? `LATITUDE / LONGITUDE` -> `none in ontology` — No coordinate target exists; correctly left unmapped, though site coordinates would be the natural geocode for address.full.

**Agent notes:** Header is on line 1 (skip_rows=0). No ABN/ACN/NZBN column exists in the file, so no identifier is mapped. entity.legal_name is deliberately left unmapped: SITE_NAME carries trading/brand names ('MAX Employment', 'Advanced Personnel Management (APM)') and is not asserted to be the registered legal name, even where a few values happen to carry a legal suffix. entity.status left unmapped: the register lists currently contracted delivery sites and has no legal-entity registration status column. entity.entity_type left unmapped (defaults to unknown): no column states the provider's legal form. No publisher documentation was supplied, so code semantics for CONTRACT_NAME and ESA_CD_* are inferred from values and remain unvalidated. Revision after review: placeholder 'TBA' is now nulled in address fields, and SITE_URL is domain-extracted and scheme-normalised so phone/'TTY:' cells drop to null instead of being rejected as invalid websites; confidence on entity.website lowered to 0.6 because the column is mixed-purpose in the source.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['PLACEHOLDER_VALUE_EMITTED(address.full)'], critic 'wrong' none
    - ~ changed `('SITE_POSTCODE',)` -> `address.postcode` (steps/confidence)
    - ~ changed `('SITE_URL',)` -> `entity.website` (steps/confidence)
    - ~ changed `('SITE_STATE_CD',)` -> `address.state` (steps/confidence)
    - ~ changed `('SITE_LOCALITY_NAME',)` -> `address.locality` (steps/confidence)
    - ~ changed `('SITE_NAME',)` -> `entity.trading_name` (steps/confidence)
    - ~ changed `('SITE_ADDRESS_LN',)` -> `address.full` (steps/confidence)

## Decision

This experimental proposal is outside the approval queue.
