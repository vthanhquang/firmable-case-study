# Mapping review: `ato_tax_transparency_2023_24`

- **Status:** PENDING_REVIEW  (run `20261112T205404-d08c5f`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** Corporate Tax Transparency - 2023-24 Report of Entity Tax Information — Australian Taxation Office
- **Resource:** ato_tax_transparency_2023_24.xlsx (XLSX), sha256 `6b47837efab92e1eb2b0cacc46945376a5b185c1b16814146c3282a1921b0c75`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 9 tool calls, 6 model calls, 43,103 prompt + 9,561 completion tokens, 162s model time

## Final proposal (v0, digest `25a340246ac8b541e3e920f6428f0c534e57597d8835c44cf6ae9de490c1ddc9`)

**Record grain:** `legal_entity` — Each record is a legal entity (identified by ABN) with its tax information for an income year. The business participant's legal name and ABN are mapped; the financial figures are outside the ontology.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": "Income tax details", "record_path": null}`

**Record id:** `content_hash` [] — Neither Name (526 distinct/527) nor ABN (524 distinct/527, 2 missing) is unique per record, so a content hash is the traceable record id.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Name | `entity.legal_name` | trim, collapse_whitespace | 0.95 | 1075 / 1075 |  | The ATO corporate tax transparency report lists entities by their registered legal name; names carry legal-form suffixes (PTY LTD, PTY LIMITED, LIMITED). |
| ABN | `entity.abn` | abn | 0.98 | 1069 / 1069 |  | ABN column is 11 digits and 100% checksum-valid across the discovery partition; 2 records legitimately have no ABN. |

**Deliberately unmapped:**
- `Total income $` — Financial figure (total income) not in the ontology.
- `Taxable income $` — Financial figure (taxable income) not in the ontology.
- `Tax payable $` — Financial figure (tax payable) not in the ontology.
- `Income year` — Tax income year the figures relate to; not an entity attribute, and not a statement of when the name/ABN claim was observed. Kept as an observation-level fact only.

**Held-out run:** 1075 records, 1075 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Both rules are sound. Names carry legal-form suffixes and match the report's nature as a listing of registered legal entities, so entity.legal_name is correctly sourced rather than a trading name; ABNs are emitted in native 11-digit form. No entity_type, status, address, or date targets are claimed, which is appropriate since the source has only name, ABN, financial figures, and income year. Unmapped financial columns and income year are correctly excluded; note the income year is not being used as an observation date, which is the right call but means no provenance date exists for these claims.

**Agent notes:** Mapped the main data sheet 'Income tax details'. The 'Information' sheet is front-matter with no tabular records; the 'PRRT details' sheet (16 records: Name, ABN, PRRT Payable $) is a separate supplementary table not covered by this config. Restricting to one sheet keeps one row = one legal entity; no publisher documentation was supplied, so semantics rest on the sheet headers and the report's published structure.

## Decision

Approve: `python -m firmable.cli approve ato_tax_transparency_2023_24 --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve ato_tax_transparency_2023_24 --reviewer "<name>" --reject --comment "why"`
