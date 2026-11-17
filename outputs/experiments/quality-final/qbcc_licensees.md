# Mapping review: `qbcc_licensees`

- **Status:** PENDING_REVIEW  (run `20261112T022859-48e454`, prompt `prompts-v9`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb39510b79a8056568dd532843d75b711d3d44c193ff0d84447`
- **Licence:** CC-BY-4.0
- **Agent effort:** 1 proposal(s), 10 tool calls, 8 model calls, 124,268 prompt + 9,627 completion tokens, 137s model time

## Final proposal (v0, digest `e396e02ccc172dcd2a69bcbaf54b7ef4f20712873772ea61e11d29583ee166d0`)

**Record grain:** `licence_or_permit` — One record is one QBCC licence (licence number, grade/class and financial category, held by a licensee). The business participant is the licensee, so the record's own Licence Number is the licence identifier and is not mapped as a business identifier. A licensee may hold several licences, so holder attributes repeat across records and record_id is the datastore row id, not the licence.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — Datastore _id is present on 100% of rows and 508/508 distinct in discovery. Licence Number has only 506 distinct over 508 rows, so it is not unique per record; _id is.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name | `entity.legal_name` | trim, collapse_whitespace | 0.85 | 1101 / 1101 |  | Header 'Licensee Name' = holder of the QBCC licence; licences are issued to legal persons, so this is the holder's legal name. Values are person names in caps or company names ending PTY LTD, consistent with registered names. |
| ABN | `entity.abn` | abn | 0.92 | 612 / 618 | {'ABN_CHECKSUM': 6} | Column labelled ABN, 54.9% present, checksum-valid rate 0.996. The abn transform rejects the one bad checksum rather than guessing. |
| ACN | `entity.acn` | acn | 0.92 | 77 / 77 |  | Column labelled ACN, 100% checksum-valid on the 6.7% of rows present; populated on exactly the 34 Company rows. Never derived from ABN. |
| Licence Type DESC | `entity.entity_type` | map_enum({"mapping": {"Company": "company"}, "default": "unknown", "passthrough": false}) | 0.6 | 1101 / 1101 |  | Only 'Company' reliably states legal form and agrees with ACN presence. 'Individual' maps to unknown because an individual licensee may be a sole trader, partner, or nominee for a company, and the publisher states a licence category does not establish legal form. |
| Licensee Business Address | `address.full` | trim, collapse_whitespace | 0.8 | 1101 / 1101 |  | Publisher: the licensee's business address is collected on the application and published in the register. Scope licence_holder_address, not registered office or licensed premises. |
| Licensee Business Address | `address.state` | regex_extract({"pattern": "\\b(NSW\|VIC\|QLD\|WA\|SA\|TAS\|ACT\|NT)\\b", "group": 1}), state | 0.82 | 1083 / 1101 |  | State abbreviation sits before the 4-digit postcode; extracted from its own evidence rather than assumed QLD. |
| Licensee Business Address | `address.postcode` | regex_extract({"pattern": "(\\d{4})\\s*$", "group": 1}), postcode | 0.8 | 1101 / 1101 |  | Address lines end with a 4-digit postcode; anchored at end of string so street numbers are not matched. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Queensland (Australia) licensing register; all sampled addresses carry an Australian state abbreviation and 4-digit postcode.

**Deliberately unmapped:**
- `_id` — Datastore row identifier used only as record_id; an API artefact, not a business identifier.
- `Licence Number` — Identifier of the licence, not of the business; the rules forbid mapping the record's own ID as a business identifier. Also non-unique (506/508).
- `Licence Type CODE` — Redundant coded form of Licence Type DESC ('I'/'C').
- `Financial Category DESC` — Financial category of the licence; a licence attribute, not entity.status. No ontology licence-status field.
- `Financial Category CODE` — Coded form of Financial Category DESC; licence attribute, no target.
- `Licence Grade` — Grade/type of the licence; a licence attribute, not the holder's business form, so it must not feed entity_type. No ontology field for licence grade.
- `Licence Class Type` — Licensed trade/class (e.g. Carpentry). Not an ANZSIC code, and entity.industry_code asks for ANZSIC where available, so mapping it would misstate the coded industry. Raw values remain in the source.
- `Licensee Business Address (locality)` — Tried deriving address.locality from this free-text line, but the street portion cannot be separated reliably: every attempt included the street name (e.g. 'radiata pl Peregian Springs'), which would emit a wrong locality. A wrong mapping is worse than a missing one, so locality is left unmapped. address.full preserves the complete address.

**Held-out run:** 1101 records, 1101 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** The mapping is sound overall. The licence number and row _id are correctly excluded as business identifiers; entity_type is conservatively derived only from the explicit 'Company' category and defaults to unknown for 'Individual', which matches the publisher's statement that licence category does not establish legal form; ABN/ACN are taken from their own labelled columns with checksums rather than inferred. Address parts are extracted from their own evidence with end-anchored postcode, and claim_scope correctly labels the address as the licence holder's business address, not a licensed premises. No validity paths are attached to any claim, so no cross-claim date bleed or legacy record-level validity problem arises. The only soft spot is the hard-coded country=AU constant, which is a reasonable but sampled inference rather than per-record evidence. No material missed ontology targets were found in the held-out data.
- doubtful: `address.country` <- [] — A constant AU with no source column is acceptable for an all-QLD register, but the supporting reason (all sampled addresses show an Australian state) is a sampled inference, not a guarantee; a small number of interstate/NZ licensee addresses could exist. Low risk but not evidence-backed per record, so doubtful rather than ok.
- missed? `Licensee Business Address (locality)` -> `address.locality` — No locality target exists in the supplied ontology, so this is not a lost ontology match — but note the ontology also has no locality field, so leaving it unmapped is defensible.
- missed? `Licence Class Type` -> `entity.industry_code` — Not a true miss: the ontology asks for ANZSIC where available and the classes are trade descriptions, so the mapping's refusal is correct; recorded here only to confirm the reviewer agrees rather than treating it as a gap.

**Agent notes:** Source is not a CSV as advertised: the file is a data.gov.au CKAN DataStore search JSON envelope, so record_path 'result.records' is required. Address locality deliberately omitted — the address is unstructured free text with inconsistent casing and no delimiter between street, suburb, state and postcode, and the dry_run showed locality values swallowed the street name. State and postcode are reliably extractable; locality is not. entity_type stays unknown for all 474 'Individual' rows: the register does not distinguish sole traders from individual nominees. No date columns exist, so observed_at falls back to resource_last_modified and no validity dates are emitted.

## Decision

This experimental proposal is outside the approval queue.
