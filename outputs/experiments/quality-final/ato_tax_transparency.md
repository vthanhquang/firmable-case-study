# Mapping review: `ato_tax_transparency`

- **Status:** PENDING_REVIEW  (run `20261112T023836-e79af7`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency — Australian Taxation Office
- **Resource:** 2024-25 Report of Entity Tax Information (excel (.xlsx)), sha256 `7cccd963cd4aad31c305b21d33272d3d99ff9c36258641622a28cd0028d65c45`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 13 tool calls, 13 model calls, 138,203 prompt + 5,968 completion tokens, 68s model time

## Final proposal (v1, digest `fb40b0bea5f3d729ae0810ed4df757897f3db8ba92f01d0e2678a99833074960`)

**Record grain:** `legal_entity` — One row is one entity's tax information for one income year (Name + ABN). The identifiers and name describe the business participant; the monetary amounts and income year are financial facts about that entity-year and have no ontology target.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Income tax details", "record_path": null}`

**Record id:** `content_hash` ['Name', 'ABN', 'Total income $', 'Taxable income $', 'Tax payable $', 'Income year'] — No column combination is a reliable unique key: ABN+Income year collided on the held-out partition (8 duplicate keys) because an ABN can be reported more than once for the same income year. Content hash over all six reported columns is used instead.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Name | `entity.legal_name` | trim, collapse_whitespace | 0.72 | 1166 / 1166 |  | Header is 'Name' in an ATO register of entities reporting tax; values are registered-style legal names ending in PTY LTD / PTY LIMITED / LIMITED. ATO publishes the registered entity name, not a trading name, so legal_name is appropriate. |
| ABN | `entity.abn` | trim, abn | 0.97 | 1156 / 1156 |  | Column 'ABN' holds 11-digit values with a 100% checksum-valid rate on the discovery partition; validated with the abn transform. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Australian Taxation Office register of Australian entities identified by ABN; all records are Australian.

**Deliberately unmapped:**
- `Total income $` — Monetary amount reported for the income year; no ontology target for financial figures.
- `Taxable income $` — Monetary amount reported for the income year; no ontology target.
- `Tax payable $` — Monetary amount reported for the income year; no ontology target.
- `Income year` — Reporting period label (e.g. 2024-25) used only for record identity, not a validity date of the name or registration; not a mappable observation date.

**Held-out run:** 1166 records, 1166 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All three rules are defensible: legal_name sourced from the ATO registered name column, ABN validated with a checksum transform, and a country constant warranted by the ATO/ABN context. No validity dates are emitted, so no date-order or licence-date-on-name misattribution, no legacy record-level validity target, and no status is asserted (so no deregistered/valid_to conflict). Financial amounts and the income year are correctly left unmapped. Main gap: entity_type is derivable with fair confidence from explicit legal-name suffixes in the same source column and was not captured; if it stays unmapped it should be recorded as 'unknown' by default rather than inferred elsewhere.
- missed? `Name` -> `entity.entity_type` — Legal-name suffixes (PTY LTD, PTY LIMITED, LIMITED, HOLDINGS, HOLDCO) are explicit in-source evidence that lets entity_type be set to 'company' (and 'unknown' otherwise) rather than left unmapped; the ontology warns specifically against guessing entity_type, so this precise source signal should be captured or the field explicitly justified as unknown.

**Agent notes:** Workbook has three sheets: 'Information' (documentation), 'Income tax details' (mapped here) and 'PRRT details' (Name, ABN, PRRT Payable) - the PRRT sheet was not mapped; it is a separate small table of petroleum resource rent tax payers. No dates in the data, so the record envelope uses resource_last_modified. ABN+Income year is not unique (an ABN can be reported more than once per income year; the held-out partition had 8 such collisions), so record identity uses content_hash over all six columns. ABN is missing in ~0.9% of rows, so such rows hash with an empty ABN and still emit legal_name.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' none
    - ~ record_id columns -> content_hash ['Name', 'ABN', 'Total income $', 'Taxable income $', 'Tax payable $', 'Income year']

## Decision

This experimental proposal is outside the approval queue.
