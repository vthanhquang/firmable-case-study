# Mapping review: `ato_tax_transparency`

- **Status:** PENDING_REVIEW  (run `20261110T045723-46f0b7`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency — Australian Taxation Office
- **Resource:** 2024-25 Report of Entity Tax Information (excel (.xlsx)), sha256 `7cccd963cd4aad31…`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 10 tool calls, 9 model calls, 67,809 prompt + 3,893 completion tokens, 40s model time

## Final proposal (v1, digest `1fd1627a10f78a08`)

**Record grain:** `legal_entity` — Each row in the 'Income tax details' sheet is one company's tax information for one income year (name, ABN, total income, taxable income, tax payable). The business participant is the entity identified by the row's Name and ABN.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Income tax details", "record_path": null}`

**Record id:** `content_hash` [] — No column set is reliably unique: ABN has fewer distinct values than rows (431 of 435 in discovery, and the holdout rejected an ABN+Income year key with 8 collisions), so duplicate rows can legitimately repeat ABN/name/year. A content hash over the full row is the only guaranteed-unique, traceable record identity.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Name | `entity.legal_name` | trim, collapse_whitespace | 0.75 | 1166 / 1166 |  | Sheet is a statutory tax-info report of entities; names are all-caps registered-style company names (PTY LTD / LIMITED). |
| ABN | `entity.abn` | abn | 0.98 | 1156 / 1156 |  | ABN column with 100% checksum-valid rate in discovery partition. |

**Deliberately unmapped:**
- `Total income $` — Financial figure, no ontology target.
- `Taxable income $` — Financial figure, no ontology target.
- `Tax payable $` — Financial figure, no ontology target.
- `Income year` — Income year is a fiscal period label (e.g. 2024-25), not a clean date; no ontology date target fits cleanly.

**Held-out run:** 1166 records, 1166 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The two mapped fields are largely sound: ABN is a clean, checksummed 11-digit identifier and is correctly mapped. legal_name is mapped from the ATO 'Name' column, which is a registered-style statutory reporting name (consistent with PTY LTD/LIMITED forms), so it is broadly acceptable, but since the ATO does not formally certify it equals the ASIC-registered legal name (and some values are generic address-derived names), it is flagged doubtful rather than wrong. No trading-name, licence-number, or person-as-business confusion occurred. The financial columns and Income year are correctly left unmapped (no ontology targets). The only potential missed opportunity is deriving entity_type='company' from the explicit PTY LTD/LIMITED suffixes in Name, which would be evidence-based rather than guessed.
- doubtful: `entity.legal_name` <- ['Name'] — The ATO Corporate Tax Transparency 'Name' column is the entity name as reported for tax purposes; it generally contains registered-style names (PTY LTD / LIMITED), and these held-out values are consistent with legal names. However, the ATO does not guarantee this is the ASIC-registered legal name — for groups it can be the reporting entity's trading/brand name. Values like '1 MENDS STREET PTY LTD', '1884 PTY LIMITED', '20 CASHEWS PTY LTD' are generic/address-derived names that could plausibly be registered names but are not verifiable from the source. Reasonable mapping but not fully safe; would be 'ok' if the publisher confirms Name is the registered name.
- missed? `Income year` -> `entity.date_registered` — No — this is a fiscal period, not a registration date; correctly left unmapped. Listed only to confirm it is NOT a missed date_registered; no action needed.
- missed? `Name` -> `entity.entity_type` — The 'PTY LTD' / 'LIMITED' suffixes present in the Name column are explicit source evidence of entity legal form, enabling a non-guessed assignment of 'company'. The ontology warns against guessing entity_type, but here it can be derived from an explicit suffix. Optional but a reasonable missed target.

**Agent notes:** Multi-sheet workbook; only 'Income tax details' mapped. PRRT details sheet holds a different tax (PRRT payable) for a subset of entities and has no income-year column, so it is excluded to keep grain consistent. Record ID uses content_hash because ABN is not unique across rows.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' none
    - ~ record_id columns -> content_hash []

## Decision

Approve: `python -m firmable.cli approve ato_tax_transparency --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve ato_tax_transparency --reviewer "<name>" --reject --comment "why"`
