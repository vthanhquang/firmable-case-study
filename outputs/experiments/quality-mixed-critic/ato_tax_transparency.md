# Mapping review: `ato_tax_transparency`

- **Status:** PENDING_REVIEW  (run `20261112T020521-4a20ec`, prompt `prompts-v7`, model `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency — Australian Taxation Office
- **Resource:** 2024-25 Report of Entity Tax Information (excel (.xlsx)), sha256 `7cccd963cd4aad31c305b21d33272d3d99ff9c36258641622a28cd0028d65c45`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 13 tool calls, 12 model calls, 115,196 prompt + 12,847 completion tokens, 212s model time

## Final proposal (v1, digest `1959e4cc83bcbd72eaf30aa1035d0e2900f0ad0d65bd22bd39df3b250f646126`)

**Record grain:** `legal_entity` — Each row of the 'Income tax details' sheet is one legal entity (identified by its ABN) for one income year of the ATO Corporate Tax Transparency report; the row reports the entity's total income, taxable income and tax payable. The financial figures are not business identifiers and are left unmapped. The PRRT details sheet is a separate licence/rent-resource table and is not part of this mapping.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Income tax details", "record_path": null}`

**Record id:** `content_hash` [] — ABN+Income year collides on 8 held-out rows (the same ABN appears for more than one income year / duplicate rows), so no column combination is reliably unique. A content hash over the full record is traceable and collision-safe.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Name | `entity.legal_name` | trim, collapse_whitespace | 0.72 | 1166 / 1166 |  | Header is 'Name' in an ATO statutory register extract keyed to ABN; values carry legal-form suffixes (PTY LTD, PTY LIMITED, LIMITED), i.e. registered legal persons. Header does not say 'legal name' explicitly and a few rows are misspelt ('LINITED'), hence moderate confidence. |
| ABN | `entity.abn` | abn | 0.97 | 1156 / 1156 |  | Header is 'ABN'; 11-digit shape on all present values with 100% checksum validity. |
| Name | `entity.entity_type` | trim, upper, regex_extract({"pattern": "(PTY\\.? ?LTD\|PTY\\.? ?LIMITED\|LIMITED\|LTD)\\.?$", "group": 1}), map_enum({"mapping": {"PTY LTD": "company", "PTY. LTD": "company", "PTY LIMITED": "company", "PTY. LIMITED": "company", "LIMITED": "company", "LTD": "company"}, "default": "unknown", "passthrough": false}) | 0.55 | 1142 / 1166 |  | Only rows whose name ends in an explicit company legal-form suffix (PTY LTD / PTY LIMITED / LIMITED / LTD) are mapped to 'company'; rows with no explicit business-form suffix are left unmapped (regex_extract yields nothing) so they default to 'unknown' rather than being guessed. Confidence kept moderate-low because a name suffix states the corporate form of the ATO registrant rather than a dedicated entity-type field. |

**Constants:**
- `address.country` = `AU` (conf 0.9): ATO statutory transparency register of Australian entities; all ABNs checksum-validate.

**Deliberately unmapped:**
- `Total income $` — Financial amount for the income year, not an entity attribute in the ontology.
- `Taxable income $` — Financial amount for the income year, not an entity attribute in the ontology.
- `Tax payable $` — Financial amount for the income year, not an entity attribute in the ontology.
- `Income year` — Income year of the financial figures (2024-25 etc.). It dates the tax return period, not the validity or observation time of any entity attribute, so it is deliberately not mapped to observation.observed_at (resource_last_modified is used instead) nor to valid_from/valid_to.
- `PRRT details sheet (Name, ABN, PRRT Payable $)` — Separate sheet of Petroleum Resource Rent Tax payers; not read by this config, which targets the 'Income tax details' sheet.
- `Information sheet` — Guidance/prose sheet with titles and links, no tabular entity records.

**Held-out run:** 1166 records, 1166 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is accurate and well-reasoned. Legal names and ABNs are correctly identified and validated. Entity type is safely derived from explicit legal form suffixes in the name, avoiding harmful guessing. Financial figures and income year are appropriately left unmapped as they do not fit the entity ontology. No missed mappings.

**Agent notes:** Reader targets the 'Income tax details' sheet (header row 1). entity_type is emitted only when the Name ends with an explicit company suffix (416 of 435 discovery rows); entities without such a suffix get no entity_type observation (defaults to unknown). No ACN, address, status or registration-date columns exist, so those targets are left unset deliberately. record_id uses content_hash because ABN+Income year is not unique across held-out rows. observed_at falls back to the resource last-modified timestamp rather than being derived from the income year.

## Self-correction trace
- v0 -> v1: triggered by validator errors ['RECORD_ID_NOT_UNIQUE'], critic 'wrong' none
    - + added `('Name',)` -> `entity.entity_type`
    - - removed `('Income year',)` -> `observation.observed_at`
    - ~ record_id columns -> content_hash []

## Decision

This experimental proposal is outside the approval queue.
