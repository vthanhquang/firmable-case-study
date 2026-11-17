# Mapping review: `ato_tax_transparency`

- **Status:** PENDING_REVIEW  (run `20261112T015936-2bb87b`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency — Australian Taxation Office
- **Resource:** 2024-25 Report of Entity Tax Information (excel (.xlsx)), sha256 `7cccd963cd4aad31c305b21d33272d3d99ff9c36258641622a28cd0028d65c45`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 8 tool calls, 7 model calls, 51,826 prompt + 5,134 completion tokens, 100s model time

## Final proposal (v0, digest `ebe737110e27ad89093adb75200a21346f4c44529697fefc44e8342f3d04abe8`)

**Record grain:** `legal_entity` — One record is a single legal entity (identified by ABN) plus its reported corporate income tax figures for one income year. The entity is the subject; the tax amounts are annual figures about it, not separate facts to map.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Income tax details", "record_path": null}`

**Record id:** `content_hash` [] — ABN is present for 99.1% and has 431 distinct values across 435 rows, so it is not unique per record; a content_hash over the row is the traceable key.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Name | `entity.legal_name` | trim, collapse_whitespace | 0.78 | 1166 / 1166 |  | ATO tax transparency rows name the entity as registered for tax purposes; all sampled values carry corporate legal suffixes (PTY LTD / PTY LIMITED / LIMITED), supporting a registered legal name rather than a trading/brand name. There is no separate trading-name column. |
| ABN | `entity.abn` | trim, abn | 0.97 | 1156 / 1156 |  | Column is literally ABN; profile shows 100% checksum-valid 11-digit values (abn_checksum_valid_rate 1.0) across 431 present values. |

**Constants:**
- `address.country` = `AU` (conf 0.6): Australian Taxation Office register covering Australian entities; country evident from metadata, not stated per row.

**Deliberately unmapped:**
- `Total income $` — Financial amount with no ontology target.
- `Taxable income $` — Financial amount (76% present) with no ontology target.
- `Tax payable $` — Financial amount (71% present) with no ontology target.
- `Income year` — Accounting period label ('2024-25'), not a datetime or a valid_from for the name/registration; kept as period context only.

**Held-out run:** 1166 records, 1166 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All three rules are sound: legal_name comes from the registered-name column with no trading-name confusion and no misattached validity, ABN is checksum-validated against a literal ABN column and produces well-typed 11-digit values across the rare/unusual held-out rows, and the AU country constant is supported by publisher evidence without implying a premises address. The financial columns and the income-year period label have no ontology targets and are legitimately unmapped; no entity_type, status, or registration-date data exists in this source, so those ontology fields correctly remain unpopulated rather than guessed.
- missed? `Income year` -> `entity.date_registered` — Do NOT map this. Listed only to record that it was considered: '2024-25' is a tax reporting period label, not a registration date, so leaving it unmapped is correct rather than a genuine miss. No source column in this file plausibly supplies entity.date_registered, entity.entity_type, entity.status, entity.acn, entity.trading_name, entity.website or entity.industry_code, so no real unmapped target is missed.

**Agent notes:** Only the 'Income tax details' sheet is onboarded; 'PRRT details' is a separate 21-row petroleum resource rent tax sheet needing its own mapping. No publisher documentation supplied, so entity_type is left unmapped rather than inferred from name suffixes; no status or licence-style columns exist. Financial columns deliberately unmapped (ontology has no monetary targets). Income year spans 2022-23..2024-25 in discovery, so rows are not all from the advertised 2024-25 report.

## Decision

This experimental proposal is outside the approval queue.
