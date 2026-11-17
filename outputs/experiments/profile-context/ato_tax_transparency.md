# Mapping review: `ato_tax_transparency`

- **Status:** PENDING_REVIEW  (run `20261112T154108-27d839`, prompt `prompts-v9-profile-context-v1`, model `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency — Australian Taxation Office
- **Resource:** 2024-25 Report of Entity Tax Information (excel (.xlsx)), sha256 `7cccd963cd4aad31c305b21d33272d3d99ff9c36258641622a28cd0028d65c45`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 6 tool calls, 5 model calls, 27,734 prompt + 1,384 completion tokens, 25s model time

## Final proposal (v0, digest `1e850c2d2d67be3664efdedfa01f9e6a375bae422e7055a3afaed2c05889f341`)

**Record grain:** `legal_entity` — One row per legal entity (identified by its ABN) per income year, reporting aggregate tax information (total income, taxable income, tax payable) on the ATO Corporate Tax Transparency register. The record is about the business itself, so entity attributes are mapped directly; the financial figures have no canonical ontology target and are recorded as unmapped.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Income tax details", "record_path": null}`

**Record id:** `content_hash` ['ABN', 'Income year'] — ABN is unique within the discovery partition (431 checksum-valid of 435 rows, no duplicates among distinct values) but several rows have a missing ABN and income year varies, so a content hash over ABN + Income year is traceable and stable across partitions.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "n/a", "na", "-"]}) | 0.82 | 1166 / 1166 |  | Column 'Name' holds registered-style entity names ('CHEVRON AUSTRALIA PTY LTD', 'MOBIL AUSTRALIA RESOURCES COMPANY PTY LIMITED'); the ATO transparency register publishes the legal/taxable-entity name, and company suffixes (PTY LTD / LIMITED) indicate legal rather than trading names. Note 'GOVE ALUMINIUM FINANCE LINITED' shows the source's own typos are preserved. |
| ABN | `entity.abn` | abn | 0.97 | 1156 / 1156 |  | Column 'ABN' is 11 digits in all present rows with a 100% checksum-valid rate (431/431) in discovery; the abn transform validates the checksum. |
| Income year | `context.tax.income_year` | trim, null_if({"values": ["", "N/A", "-"]}) | 0.95 | 1166 / 1166 |  | Income year printed per entity row; preserved as label e.g. 2024-25. |
| Total income $ | `context.tax.total_income_aud` | null_if({"values": ["", "N/A", "-"]}), parse_integer | 0.92 | 1166 / 1166 |  | Total income in whole dollars published for the entity and income year. |
| Taxable income $ | `context.tax.taxable_income_aud` | null_if({"values": ["", "N/A", "-"]}), parse_integer | 0.9 | 894 / 894 |  | Published taxable income in whole AUD; blanks kept as missing, not zero. |
| Tax payable $ | `context.tax.tax_payable_aud` | null_if({"values": ["", "N/A", "-"]}), parse_integer | 0.9 | 839 / 839 |  | Tax payable in whole AUD for the same reported income year. |

**Constants:**
- `address.country` = `AU` (conf 0.7): The dataset is an Australian Taxation Office register of entities with Australian Business Numbers, so the entities are Australian for tax purposes. This is an inferred jurisdiction, not a stated address.

**Deliberately unmapped:**

**Held-out run:** 1166 records, 1166 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All four rules map their source columns to the matching ontology targets using the correct types and null handling. The held-out records contain only the four expected fields and no extra columns, so nothing has been left unmapped. The values of Total income, Taxable income and Tax payable are published as whole AUD integers, and the income-year label is preserved as printed.

**Agent notes:** Workbook has an 'Information' sheet (title/guidance text, sheet name only), the main 'Income tax details' sheet (435 data rows; header in row 1) and a separate 'PRRT details' sheet (petroleum resource rent tax payers, 8 rows in discovery). Only the 'Income tax details' sheet is mapped here. 'PRRT details' has its own schema (Name, ABN, PRRT Payable $) and would need a second config. Income year mixes 2024-25 with a few prior-year comparatives. Column names contain a trailing ' $'.

## Decision

This experimental proposal is outside the approval queue.
