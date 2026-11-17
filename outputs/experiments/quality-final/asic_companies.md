# Mapping review: `asic_companies`

- **Status:** PENDING_REVIEW  (run `20261112T021259-c6bc15`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** ASIC - Company Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Company Dataset - Current (ZIP), sha256 `bb7935a163292c6d195bd2d5788863164f191198b3f29257fb332785f998bcea`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 11 tool calls, 18 model calls, 264,271 prompt + 28,712 completion tokens, 392s model time

## Final proposal (v1, digest `494843832d4ceabdaf94a82934a6a0c98df96abda0fa897de4e0ac93a00ba59b`)

**Record grain:** `legal_entity` — Each row is one name-history entry for one ASIC-registered company: the same ACN repeats across rows when a company has changed name (a current-name row with Current Name Indicator=Y and blank Current Name, plus former-name rows whose separate Current Name column holds the current legal name). Mapped targets are the business participant's attributes (legal name, ACN, ABN, status, type, registration date).

**Reader:** `{"format": "delimited", "archive_member": "COMPANY_202611.csv", "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` [] — ACN is not unique per record (471 distinct ACNs over 473 profiled rows; the same ACN repeats on current-name and former-name rows). No column identifies a row, so content_hash is used.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Company Name *when Current Name absent []* | `entity.legal_name` | collapse_whitespace, trim, valid_from from Current Name Start Date | 0.8 | 732 / 732 |  | Publisher help file: on the row that carries no separate Current Name (the current-name row, indicator=Y), Company Name is the company's current registered legal name. Current Name Start Date is attached as that claim's start where present (usually blank on these rows, giving a null valid_from rather than a guess). Values are right-padded, so collapse_whitespace then trim. |
| Current Name *when Current Name present []* | `entity.legal_name` | collapse_whitespace, trim, valid_from from Current Name Start Date | 0.82 | 431 / 431 |  | Help file: on a history row the Current Name column holds the company's current legal name and Current Name Start Date dates the start of that name (day-first, e.g. 28/01/2016). That start is the only validity bound the source states for the current name. |
| Company Name *when Current Name present []* | `entity.legal_name` | collapse_whitespace, trim | 0.72 | 431 / 431 |  | Help file: where a row carries a separate Current Name, the Company Name on that row is a former registered name, so scope former_legal_name with no validity bounds - the extract does not establish when a former name stopped being valid. The condition is a value test on the name columns rather than the fragile Y/blank indicator. |
| ACN | `entity.acn` | acn | 0.95 | 1163 / 1163 |  | Column named ACN, 9-digit shape on 473/473 profiled rows, checksum-valid on 100% of values; use the acn transform. |
| ABN | `entity.abn` | trim, null_if({"values": ["0", "00", ""]}), abn | 0.9 | 844 / 1163 |  | Help file: ABN '0' is a missing value (145/473 discovery rows). null_if runs before the checksum-validating abn transform; the remaining 11-digit values validate (69.3% of rows emitted). |
| Status | `entity.status` | map_enum({"mapping": {"REGD": "active", "DRGD": "deregistered", "EXAD": "unknown", "SOFF": "unknown"}, "default": "unknown", "passthrough": false}) | 0.65 | 1163 / 1163 |  | Help file: REGD registered, DRGD deregistered, EXAD covers BOTH receivership and liquidation, SOFF is strike-off action in progress. REGD->active and DRGD->deregistered are exact. EXAD is mapped explicitly to unknown rather than in_liquidation, because a receivership-only company is not in liquidation and the code cannot establish which applies. SOFF is mapped explicitly to unknown because the company is still registered while strike-off action is in progress and no canonical value fits. Both are stated explicitly rather than silently defaulted. |
| Type | `entity.entity_type` | map_enum({"mapping": {"APTY": "company", "APUB": "company"}, "default": "unknown", "passthrough": false}) | 0.75 | 1163 / 1163 |  | Type states the ASIC company type explicitly: APTY Australian proprietary company, APUB Australian public company (both profiled, including the LMGT/APUB rows). Both are companies; unlisted codes default to unknown. |
| Date of Registration | `entity.date_registered` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1163 / 1163 |  | Help file: company registration event with day-first dates; all 473 profiled values match 99/99/9999 and held-out values parsed correctly. |

**Constants:**
- `address.country` = `AU` (conf 0.85): ASIC is the Australian register; every record is an Australian-registered body. No address columns exist, so only the country is defensible.

**Deliberately unmapped:**
- `Current Name Indicator` — Row-level flag duplicating the name-column pattern (Y rows carry the current name in Company Name with Current Name blank); conditions are taken from the name columns themselves, so the flag is not an entity attribute.
- `Current Name Start Date` — Dates the current-name claim only; used as valid_from_path on both current-name rules, not a standalone entity date.
- `Class` — ASIC internal class code (LMSH limited by shares, LMGT limited by guarantee); no canonical target and no entity_type evidence beyond 'company'.
- `Sub Class` — ASIC sub-class code (PROP/PSTC/LISN/ULSN...); no canonical target.
- `Previous State of Registration` — Historical jurisdiction of registration, not the entity's current address; mapping it to address.state would assert a current location the register does not establish.
- `State Registration number` — State-level registration number (mixed alphanumeric, padded); not an ACN/ABN/NZBN and the ontology has no field for it.
- `Modified since last report` — Empty in every profiled row (present_rate 0.0); carries no information.
- `Date of Deregistration` — Dates the end of the company registration, not the validity of any name/type/address claim; using it as valid_to would wrongly end the row's name claim and the engine ignores legacy observation.valid_to for entity history. The deregistered fact is carried by entity.status.

**Held-out run:** 1163 records, 1163 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All nine rules map to the meanings of their canonical targets. Current name comes from Company Name on current rows or from Current Name on history rows, former names are scoped as former with no invented bounds, ACN and ABN are checksum-validated with ABN 0 treated as missing, status and entity_type use only exact or explicitly-unknown mappings, and Date of Registration is parsed day-first. The deregistered record correctly carries no valid_to. Unmapped columns (Class, Sub Class, Previous State of Registration, State Registration number, Date of Deregistration) have no defensible ontology target and are correctly excluded, so no important missed source columns.

**Agent notes:** Reader settings from evidence: zip member COMPANY_202611.csv, utf-8-sig (BOM), tab-delimited (14 tabs per line; commas occur only inside names), no title rows. Legal names are split per the publisher help file into three complementary rules so every row yields a name: Company Name is the current legal name when no Current Name is carried on the row; Current Name is the current legal name on history rows (dated by Current Name Start Date); and Company Name on those history rows is a former legal name with no validity bounds. Dry run: 473/473 records with output, zero field errors, and 100% of rows now produce a legal_name (636 current from Company Name, 364 current from Current Name, plus 364 former-name observations). entity.status: EXAD (receivership OR liquidation) and SOFF (strike-off in progress) are mapped explicitly to unknown rather than asserting a liquidation or deregistration the source cannot establish. No address columns exist beyond the AU country constant. Record grain is the row (company name-history entry), so record_id is a content hash rather than ACN.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.legal_name', 'entity.status']
    - ~ changed `('Company Name',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Current Name',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Status',)` -> `entity.status` (steps/confidence)

## Decision

This experimental proposal is outside the approval queue.
