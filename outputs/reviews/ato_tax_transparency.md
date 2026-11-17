# Mapping review: `ato_tax_transparency`

- **Latest review decision:** approved by claude-code (AI assistant acting for the candidate) (ai_assistant_proxy) at 2026-11-09T20:58:46+00:00
- **Status:** PENDING_REVIEW  (run `20261110T034703-b5fe14`, prompt `prompts-v1`, model `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency — Australian Taxation Office
- **Resource:** 2024-25 Report of Entity Tax Information (excel (.xlsx)), sha256 `7cccd963cd4aad31c305b21d33272d3d99ff9c36258641622a28cd0028d65c45`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 9 tool calls, 8 model calls, 51,437 prompt + 2,790 completion tokens, 38s model time

## Final proposal (v0, digest `78133ba75c7f0f4cfd321fc27b28ff75aaec21454ac96fbe43e84b214c77f85b`)

**Record grain:** `legal_entity` — One row per legal entity (identified by its ABN) per income year, reporting aggregate tax information (total income, taxable income, tax payable) on the ATO Corporate Tax Transparency register. The record is about the business itself, so entity attributes are mapped directly; the financial figures have no canonical ontology target and are recorded as unmapped.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Income tax details", "record_path": null}`

**Record id:** `content_hash` ['ABN', 'Income year'] — ABN is unique within the discovery partition (431 checksum-valid of 435 rows, no duplicates among distinct values) but several rows have a missing ABN and income year varies, so a content hash over ABN + Income year is traceable and stable across partitions.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "n/a", "na", "-"]}) | 0.82 | 1165 / 1165 |  | Column 'Name' holds registered-style entity names ('CHEVRON AUSTRALIA PTY LTD', 'MOBIL AUSTRALIA RESOURCES COMPANY PTY LIMITED'); the ATO transparency register publishes the legal/taxable-entity name, and company suffixes (PTY LTD / LIMITED) indicate legal rather than trading names. Note 'GOVE ALUMINIUM FINANCE LINITED' shows the source's own typos are preserved. |
| ABN | `entity.abn` | abn | 0.97 | 1155 / 1155 |  | Column 'ABN' is 11 digits in all present rows with a 100% checksum-valid rate (431/431) in discovery; the abn transform validates the checksum. |

**Constants:**
- `address.country` = `AU` (conf 0.7): The dataset is an Australian Taxation Office register of entities with Australian Business Numbers, so the entities are Australian for tax purposes. This is an inferred jurisdiction, not a stated address.

**Deliberately unmapped:**
- `Total income $` — Financial reporting figure (total income in AUD); no canonical ontology target for financial amounts.
- `Taxable income $` — Financial reporting figure (taxable income in AUD); no ontology target. Also null in ~24% of rows.
- `Tax payable $` — Financial reporting figure (tax payable in AUD); no ontology target.
- `Income year` — Income-year label (e.g. '2024-25'; 3 distinct values incl. 2023-24 and 2022-23 comparatives). It is used in record_id but does not itself state an entity attribute; not mapped to observation.valid_from because it is a fiscal-year label rather than a claim-effective date.

**Held-out run:** 1165 records, 1165 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is largely sound: 'Name' correctly yields legal_name (suffixed registered names, not trading names), and 'ABN' correctly yields a checksummed entity.abn. The only questionable mapping is the constant address.country='AU', which is an inference rather than an observed address, though the ontology permits an AU default. The income-year field is a reasonable non-mapping, though a future observation.valid_from target could use it. No trading-name, ACN, entity_type, or status columns exist in the source, so no enum guessing occurs.
- doubtful: `address.country` <- [] — Constant 'AU' is inferred from the ATO publisher and ABN presence, not from any source address column. Reasonable inference but it is a constant, not an observed address; the mapping itself acknowledges this. Acceptable as a default per ontology (default 'AU') but flag as inferred.
- missed? `Income year` -> `observation.valid_from` — Fiscal-year label (e.g. '2024-25') anchors each observation in time; while it does not state an entity attribute, it could set observation validity where the ontology supports it. The mapping's choice not to map is defensible but worth noting.
- missed? `Name` -> `entity.trading_name` — No trading name column exists; only legal name. No missed trading_name source. (No action needed.)

**Agent notes:** Workbook has an 'Information' sheet (title/guidance text, sheet name only), the main 'Income tax details' sheet (435 data rows; header in row 1) and a separate 'PRRT details' sheet (petroleum resource rent tax payers, 8 rows in discovery). Only the 'Income tax details' sheet is mapped here. 'PRRT details' has its own schema (Name, ABN, PRRT Payable $) and would need a second config. Income year mixes 2024-25 with a few prior-year comparatives. Column names contain a trailing ' $'.

## Second opinion (independent agent run)
- `rerun-v3`: 2/3 rules agree; **check these first:**
    - only this proposal: `('<constant:AU>',)` -> `address.country` 

## Decision

Approve: `python -m firmable.cli approve ato_tax_transparency --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve ato_tax_transparency --reviewer "<name>" --reject --comment "why"`
