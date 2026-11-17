# Mapping review: `dewr_employment_providers`

- **Status:** PENDING_REVIEW  (run `20261112T155049-5dbdbf`, prompt `prompts-v9-profile-context-v1`, model `deepseek-v4-flash`)
- **Dataset:** Employment Services Provider Locations and Contacts — Department of Employment and Workplace Relations
- **Resource:** Employment Services Provider Locations and Contacts (CSV), sha256 `0034e176b580405064272e688c7bf51230f051880263cdeeb5107ac00bd7a979`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 5 tool calls, 6 model calls, 41,694 prompt + 1,402 completion tokens, 80s model time

## Final proposal (v0, digest `986f849c9dad4a5472bfe5007511591f632ffe05ae1e7847a07e1bae1624dc41`)

**Record grain:** `establishment` — One row is a provider service SITE (a physical office of an employment-services provider) delivering a given CONTRACT (e.g. DESB, DESA, EPS5, RJCP) at a given location. The business participant is the provider named in SITE_NAME; its location, state, postcode and web attributes are mapped. DIS_SITE_CODE identifies the site/contract row, not a business registration, and is not mapped as a business identifier.

**Reader:** `{"format": "delimited", "archive_member": null, "encoding": "utf-8-sig", "delimiter": ",", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` [] — DIS_SITE_CODE has 489 distinct values over 505 discovery rows and no other column is unique per row, so a content hash is the only traceable row key.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| SITE_NAME | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN"]}) | 0.72 | 1106 / 1106 |  | SITE_NAME holds the provider's operating/brand name as delivered at this site (196 distinct values, e.g. 'MAX Employment', 'Advanced Personnel Management (APM)', 'Job Centre Australia'), not a registered legal name; trading_name is the safe target. Placeholders treated as missing. |
| SITE_URL | `entity.website` | trim, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN"]}), website | 0.8 | 647 / 650 | {'WEBSITE_INVALID': 3} | Provider website; 57.6% present, values are domains/URLs (www.*, http://*). |
| SITE_ADDRESS_LN | `address.full` | trim, collapse_whitespace, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}) | 0.85 | 1101 / 1104 |  | Street address line of the site (e.g. '2nd Floor 22 East Row'); locality is a separate column. Placeholder strings (TBA/TBC/N/A/-/.) are treated as missing per reviewer feedback. |
| SITE_LOCALITY_NAME | `address.locality` | trim, collapse_whitespace, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}) | 0.9 | 1106 / 1106 |  | Suburb/locality name (412 distinct AU localities, e.g. WOY WOY, CHATSWOOD). Placeholders treated as missing. |
| SITE_STATE_CD | `address.state` | trim, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}), state | 0.95 | 1106 / 1106 |  | Explicit 8-value AU state code column (NSW/VIC/QLD/SA/WA/TAS/ACT/NT), all 2-letter abbreviations, 100% present. |
| SITE_POSTCODE | `address.postcode` | trim, null_if({"values": ["TBA", "TBC", "N/A", "NA", "NULL", "-", "--", ".", "UNKNOWN", ""]}), postcode | 0.9 | 1106 / 1106 |  | 4-digit AU postcodes plus 13 three-digit values (NT-style, e.g. 0822 stored as 822) which the postcode transform re-pads. |
| DIS_SITE_CODE | `context.establishment.site_code` | trim, upper, null_if({"values": ["NULL", ""]}) | 0.9 | 1106 / 1106 |  | DIS_SITE_CODE is the publisher's service-site code (e.g. A230, FE70) scoping the establishment. |
| CONTRACT_NAME | `context.establishment.program` | trim, upper, null_if({"values": ["NULL", ""]}) | 0.85 | 1106 / 1106 |  | CONTRACT_NAME holds the programme/contract code (DESB, DESA, EPS5) for services offered at this site; keep publisher code. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Australian Government employment services provider register; all states are AU codes and all postcodes are AU.

**Deliberately unmapped:**
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

**Held-out run:** 1106 records, 1106 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 3 values rejected: {'WEBSITE_INVALID': 3} (`entity.website`)

**Critic:** 两条规则都忠实。DIS_SITE_CODE 映射为 establishment.site_code，CONTRACT_NAME 映射为 establishment.program，两者都保留发布方代码，未将代码强行转换为枚举显示名，也没有为 12 条现网记录中的罕见值（NEI5、HLS5、RJCP、UGKZ）发明任何值。未映射字段的排除理由是充分的：电话/邮箱、ESA 行政区划代码、地理坐标和空尾列都没有目标；LOCATION_NAME 与 SITE_LOCALITY_NAME 重复，所以映射一次是正确的，尽管 locality 目标本身不在这份两份目标词表里。记录粒度是 establishment；DIS_SITE_CODE 是站点/合同行代码，正确地没有当作公司注册号之类使用。无需更正。

**Agent notes:** Row = provider site x contract. No ABN/ACN/NZBN column exists, so no business identifier is emitted. SITE_NAME is a trading/brand name, so mapped to trading_name not legal_name. Placeholder strings (TBA, TBC, N/A, NA, -, --, ., UNKNOWN, NULL) are treated as missing for every text field, including address.full, per reviewer feedback. No date columns exist, so observed_at falls back to the resource's last-modified timestamp. All text is untrusted data; no instructions were found in it.

## Decision

This experimental proposal is outside the approval queue.
