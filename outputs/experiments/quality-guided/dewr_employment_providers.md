# Mapping review: `dewr_employment_providers`

- **Status:** PENDING_REVIEW  (run `20261112T015916-1299ca`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** Employment Services Provider Locations and Contacts — Department of Employment and Workplace Relations
- **Resource:** Employment Services Provider Locations and Contacts (CSV), sha256 `0034e176b580405064272e688c7bf51230f051880263cdeeb5107ac00bd7a979`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 12 tool calls, 12 model calls, 162,916 prompt + 11,964 completion tokens, 264s model time

## Final proposal (v1, digest `fcd1badfb6e4c2df5f7a62c8b77332ec51a84d28d7cd30ce75a0543ff96bf9b8`)

**Record grain:** `establishment` — One record is a single employment-services provider SITE (a physical service-delivery location) contracted under a DEWR program; the site's operator is a business participant, so SITE_NAME is mapped to entity.trading_name (a business/brand name, not a registered legal name). DIS_SITE_CODE identifies the site, not the business, so it is not used as a business identifier.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": ",", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` [] — DIS_SITE_CODE is not unique per record (489 distinct across 505 discovery rows; repeated rows carry different CONTRACT_NAME/ESA_CD_1 values, and some codes are non-geographic placeholders such as EFTZ). No other candidate key is unique, so a content hash over the row is the only traceable identifier.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| SITE_NAME | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.6 | 1106 / 1106 |  | SITE_NAME holds the provider's public brand/trading names (MAX Employment, Advanced Personnel Management, Job Centre Australia, CoAct/Community Solutions) as used on site listings. No evidence it is the registered legal name, so trading_name is the safe target. |
| SITE_URL | `entity.website` | trim, null_if({"values": ["", "NULL", "N/A", "NA", "TBA", "-"]}), regex_extract({"pattern": "(?i)^(?:https?://)?(?:www\\.)?([a-z0-9][a-z0-9-]*(?:\\.[a-z0-9-]+)*\\.(?:com\\.au\|net\\.au\|org\\.au\|edu\\.au\|gov\\.au\|asn\\.au\|id\\.au\|au\|com\|net\|org\|edu\|gov\|info\|biz))", "group": 0}), website | 0.65 | 647 / 650 |  | SITE_URL holds the operator's website (www.apm.net.au, orsgroup.com.au, wiseemployment.com.au), present in 57.6% of rows. Holdout rows include phone numbers and 'TTY: 03 96143062' in this column, so a TLD-anchored regex_extract is applied: it keeps every genuine domain in discovery (all 88 distinct values are domain-shaped) while rejecting numeric/code values that would otherwise be emitted as websites. |
| SITE_ADDRESS_LN | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "TBA", "TBC", "N/A", "NA", "NULL", "UNKNOWN", "-"]}) | 0.7 | 1101 / 1104 |  | Street address line of the service-delivery site; scope is the contracted premises, not a registered office. Values are truncated at about 45 chars in the source but remain usable address lines. Holdout contained a literal 'TBA' placeholder, now excluded via null_if. |
| SITE_LOCALITY_NAME | `address.locality` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.8 | 1106 / 1106 |  | Suburb/town of the site; matches LOCATION_NAME almost exactly (412 distinct each). |
| SITE_STATE_CD | `address.state` | trim, state | 0.92 | 1106 / 1106 |  | Two/three-letter AU state abbreviations only (NSW, VIC, QLD, SA, WA, TAS, ACT, NT; 8 distinct values, no overseas entries). |
| SITE_POSTCODE | `address.postcode` | trim, null_if({"values": [""]}), postcode | 0.85 | 1106 / 1106 |  | 4-digit AU postcodes present 97% (492/505); 13 three-digit values are NT codes such as 822/850 which the postcode transform re-pads to 0822/0850. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Australian Government (DEWR) employment services register; all records carry AU state codes and AU postcodes, with no NZ or other jurisdiction evidence.

**Deliberately unmapped:**
- `DIS_SITE_CODE` — Site identifier for a contracted service location, not a business identifier; also not unique per row and contains non-geographic placeholders (EFTZ).
- `CONTRACT_NAME` — DEWR programme/contract code (DESA, DESB, EPS5, TTW5, RJCP, NEI5, HLS5) naming the funding contract under which the site operates. It is not an ANZSIC industry code, so mapping to entity.industry_code would be wrong, and the ontology has no programme attribute; retained as unmapped rather than mis-typed.
- `LOCATION_NAME` — Duplicates SITE_LOCALITY_NAME (412 distinct each); no added value over address.locality.
- `SITE_CONTACT_PHONE` — Site contact phone number; the ontology has no telephone target.
- `PHONE_NUMBER` — Site phone number, largely identical to SITE_CONTACT_PHONE; no telephone target in the ontology.
- `AGENT_FREECALL_NUM` — Freecall/13-number of the provider's call centre (27% present); contact detail, no telephone target.
- `SITE_EMAIL_ADDRESS` — Site mailbox, often a named individual (kal.perera@visionaustralia.org) or generic enquiries; a person/contact detail, not an entity field, and the ontology has no email target.
- `ESA_CD_1` — Employment Services Area geography code (e.g. 5ACT, 4SOE, 5MRV) denoting the service region of the site, not an ANZSIC industry code and not an entity identifier.
- `ESA_CD_2` — Employment Services Area code, blank in 100% of discovery rows.
- `ESA_CD_3` — Employment Services Area code, blank in 100% of discovery rows.
- `LATITUDE` — Site geocode with 'NULL' placeholders; no coordinate target in the ontology.
- `LONGITUDE` — Site geocode with 'NULL' placeholders; no coordinate target in the ontology.
- `column_18` — Trailing empty field created by a trailing comma in the header; contains no data in any row.

**Held-out run:** 1106 records, 1106 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Address block (rules 2-6) is consistent with a site/establishment grain and correctly scoped; no registered-office confusion and no licence/contract number misused as a business identifier (DIS_SITE_CODE and CONTRACT_NAME correctly left unmapped). Trading name vs legal name is the main risk area: SITE_NAME is displayed brand text, so trading_name is defensible, but names with legal suffixes (OCTEC Limited) and site names are blend into one target without claim_scope; doubtful rather than wrong. Rule 5's 3-digit NT postcode padding is an inference not backed by evidence in the rationale. Website regex is sound. No validity dates are emitted so no validity-path defects; status/entity_type/ABN were not mapped, which is correct given no source columns.
- doubtful: `address.postcode` <- ['SITE_POSTCODE'] — The padding of a 3-digit NT value ('850' to '0850') is plausible, but the rationale gives no evidence that these codes are NT-numeric; the state transform is applied separately and might disagree. The origin of the padding (leading zeros) is assumed; this carries moderate risk, not clearly wrong.
- missed? `SITE_EMAIL_ADDRESS` -> `entity.website` — Not a valid website target, but the domains in site emails (novaemployment.com.au, iim.net.au, bec.net.au) could fill website gaps. This is lower priority: do not emit an email as a website.
- missed? `SITE_NAME` -> `entity.legal_name` — Rows such as 'OCTEC Limited' and 'The Salvation Army Employment Plus' contain legal-form tokens; without ABN or ACN support, however, legal_name_must_not_be guessed. It is better left unmapped; listed only for completeness.

**Agent notes:** Source is a site-level register: no ABN, ACN, legal entity name, entity type, status or registration date is present, so none of those is mapped. SITE_NAME is treated as trading_name only; the operator's registered legal name cannot be established from this file (some values such as 'OCTEC Limited' look legal but cannot be proven, so legal_name is not asserted). No date columns exist, so observation.observed_at falls back to resource last-modified and no validity dates are asserted. SITE_URL is guarded by a TLD-anchored regex because holdout rows carry phone numbers in that column; genuine domains are unchanged.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['PLACEHOLDER_VALUE_EMITTED(address.full)'], critic 'wrong' none
    - ~ changed `('SITE_URL',)` -> `entity.website` (steps/confidence)
    - ~ changed `('SITE_ADDRESS_LN',)` -> `address.full` (steps/confidence)
    - ~ record_id content_hash -> content_hash []

## Decision

This experimental proposal is outside the approval queue.
