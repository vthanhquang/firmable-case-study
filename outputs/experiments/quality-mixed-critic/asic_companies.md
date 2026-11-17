# Mapping review: `asic_companies`

- **Status:** PENDING_REVIEW  (run `20261112T012826-6a5558`, prompt `prompts-v7`, model `deepseek-v4-flash`)
- **Dataset:** ASIC - Company Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Company Dataset - Current (ZIP), sha256 `bb7935a163292c6d195bd2d5788863164f191198b3f29257fb332785f998bcea`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 14 tool calls, 14 model calls, 179,593 prompt + 15,336 completion tokens, 461s model time

## Final proposal (v1, digest `3949d516f49f79231112d22d9191a622d54cf6694566cd3b2e85798c41123353`)

**Record grain:** `legal_entity` — One row = one name/registration entry in ASIC's company register for one registered legal person (identified by a checksum-valid 9-digit ACN). A company with former names has more than one row: the row flagged Current Name Indicator=Y carries the current registered name in 'Company Name', while the unflagged row carries a former name in 'Company Name' and the current registered name in 'Current Name'. No licence, permit or contract is involved.

**Reader:** `{"format": "delimited", "archive_member": "COMPANY_202611.csv", "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` ['ACN', 'Company Name', 'Current Name Indicator'] — ACN is not unique per record (471 distinct over 473 discovery rows: name-history rows repeat the ACN), so hash the ACN together with the row's own name and the current-name flag to get a traceable, unique row key.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| ACN | `entity.acn` | acn | 0.97 | 1163 / 1163 |  | 'ACN' is 9 digits on every row (shape 999999999) with acn_checksum_valid_rate 1.0; validated by the acn transform. |
| ABN | `entity.abn` | null_if({"values": ["0", "00000000000", ""]}), abn | 0.9 | 844 / 1163 |  | 'ABN' is 11 digits where populated and checksum-valid; '0' (145/473 discovery rows) is ASIC's placeholder for 'no ABN' and is nulled before validation. |
| Company Name *when Current Name Indicator equals ['Y']* | `entity.legal_name` | trim, collapse_whitespace, valid_from from Current Name Start Date | 0.85 | 732 / 732 |  | Header is ASIC's registered company-name field and values carry legal-form suffixes (PTY LTD, PTY. LIMITED). Rows flagged Current Name Indicator=Y carry the current registered name; Current Name Start Date is the date that name took effect (usually blank on these rows, in which case no valid_from is emitted). Padding spaces are stripped. |
| Company Name *when Current Name Indicator absent []* | `entity.legal_name` | trim, collapse_whitespace, valid_to from Current Name Start Date | 0.75 | 431 / 431 |  | Unflagged rows with a populated 'Current Name' are ASIC's former-name history: this name was registered until 'Current Name Start Date', which is exactly the date the claim stopped being true, so it is used as valid_to. No valid_from is known for a former name, so none is set. |
| Current Name *when Current Name Indicator absent []* | `entity.legal_name` | trim, collapse_whitespace, valid_from from Current Name Start Date | 0.8 | 431 / 431 |  | On former-name rows 'Current Name' holds the entity's actual current registered name (e.g. Company Name 'MONAKA PTY LTD' appears with Current Name 'LOVINI HOLDINGS PTY LTD' in the reverse pairing), and 'Current Name Start Date' is the date that current name took effect, used as valid_from. |
| Status | `entity.status` | map_enum({"mapping": {"REGD": "active", "DRGD": "deregistered", "SOFF": "suspended"}, "default": "unknown", "passthrough": false}) | 0.8 | 1163 / 1163 |  | ASIC company status codes describe the company itself: REGD registered (active), DRGD deregistered, SOFF strike-off in progress (suspended). EXAD (externally administered) is deliberately left to the 'unknown' default rather than guessed as deregistered or in liquidation. |
| Type | `entity.entity_type` | map_enum({"mapping": {"APTY": "company", "APUB": "company"}, "default": "unknown", "passthrough": false}) | 0.7 | 1163 / 1163 |  | ASIC 'Type' codes here distinguish Australian proprietary (APTY) and Australian public (APUB) companies; both are companies. Any other code falls back to unknown. |
| Date of Registration | `entity.date_registered` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1163 / 1163 |  | Day-first DD/MM/YYYY on 100% of rows (shape 99/99/9999), confirmed by values such as 31/12/1886. |

**Constants:**
- `address.country` = `AU` (conf 0.9): ASIC is the Australian corporate regulator and the register covers Australian-registered companies; the file has no country column.

**Deliberately unmapped:**
- `Class` — ASIC internal class code (LMSH limited by shares, LMGT limited by guarantee); it refines legal form but the entity_type enum is too coarse to express it safely, so left unmapped rather than forced.
- `Sub Class` — ASIC internal sub-class codes (PROP, PSTC, ULSN, LISN...); meaning undocumented in the file and no ontology target.
- `State Registration number` — State-issued historical registration number (mixed alphanumeric, padded); not an ACN/ABN/NZBN and no ontology target.
- `Modified since last report` — Empty on every sampled row; a change-tracking flag about the row, not a business attribute.
- `Current Name Indicator` — Row-level flag used as a 'when' condition to split current from former names; not a business attribute itself.
- `Current Name Start Date` — Used as valid_from/valid_to on the specific name claims it dates; not a standalone entity field.
- `Previous State of Registration` — Jurisdiction where the company was originally/formerly registered, not a premises or postal address; mapping it to address.state would conflate registration jurisdiction with physical location, so it is left unmapped.
- `Date of Deregistration` — Deregistration date is only populated for deregistered rows (4%) and is already reflected through entity.status; a record-level observation.valid_to would wrongly apply to every claim on the row (and the engine ignores legacy record-level validity), so it is left unmapped.

**Held-out run:** 1163 records, 1163 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All mapping rules are correct. The mapping accurately distinguishes between current and former legal names using the Current Name Indicator, applies validity dates only to the specific name claims they belong to, correctly nulls placeholder ABNs, parses day-first dates, maps status and entity type enums safely without guessing, and avoids attaching a valid_to to deregistered statuses. No important source columns were left unmapped that could be safely mapped to the provided ontology targets.

**Agent notes:** Tab-delimited despite the .csv member name (14 tabs/line, 0-2 commas) inside a ZIP; utf-8-sig, header on line 1 so skip_rows 0. Names are space-padded to fixed width and are trimmed/collapsed. Name history handling: former-name rows emit BOTH the former name (valid_to = Current Name Start Date) and the current registered name from 'Current Name' (valid_from = Current Name Start Date); company attribute observations repeat across the two rows of the same ACN, so downstream dedupe on ACN is expected. 145/473 discovery rows use '0' as an ABN placeholder and correctly emit no ABN.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.legal_name', 'observation.valid_to']
    - + added `('Current Name',)` -> `entity.legal_name`
    - - removed `('Previous State of Registration',)` -> `address.state`
    - - removed `('Date of Deregistration',)` -> `observation.valid_to`
    - ~ changed `('Company Name',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Status',)` -> `entity.status` (steps/confidence)
    - ~ record_id content_hash -> content_hash ['ACN', 'Company Name', 'Current Name Indicator']

## Decision

This experimental proposal is outside the approval queue.
