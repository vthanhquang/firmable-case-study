# Mapping review: `qbcc_licensees`

- **Status:** PENDING_REVIEW  (run `20261112T014653-d3b6fb`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb39510b79a8056568dd532843d75b711d3d44c193ff0d84447`
- **Licence:** CC-BY-4.0
- **Agent effort:** 1 proposal(s), 18 tool calls, 15 model calls, 196,619 prompt + 9,263 completion tokens, 215s model time

## Final proposal (v0, digest `f1b8e598fda1accf8d2704a5ee10d6bb1bfcfe5c24dcadc9124967286b5db371`)

**Record grain:** `licence_or_permit` — Each record is one QBCC licence held by a licensee (individual or company). Business attributes of the licence holder (name, ABN, ACN, business address) are mapped onto the entity; licence-specific attributes (number, grade, class, financial category) are not entity fields and are left unmapped.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — '_id' is the CKAN datastore row id and is 508/508 distinct in the discovery sample; 'Licence Number' had only 506 distinct out of 508 rows (duplicate licence numbers), so it is not unique per record.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name | `entity.legal_name` | trim, collapse_whitespace | 0.72 | 1101 / 1101 |  | Column is the licensee name; publisher evidence states a licence is issued to an individual or company (legal persons) and the name is the entity as named on the licence. Values are personal/company registered names (e.g. 'JUSTIN WILLIAM PAGE', 'FLASH AIR CONDITIONING AND ELECTRICAL PTY LTD'), so legal_name rather than trading_name. |
| ABN *when ABN present []* | `entity.abn` | trim, null_if({"values": ["", "-", "N/A"]}), abn | 0.95 | 612 / 618 | {'ABN_CHECKSUM': 6} | ABN column of shape '99 999 999 999' with 99.6% checksum validity in profiling; the abn transform strips spaces and validates checksum. |
| ACN *when ACN present []* | `entity.acn` | trim, null_if({"values": ["", "-", "N/A"]}), acn | 0.95 | 77 / 77 |  | ACN column of shape '999 999 999' with 100% checksum validity in profiling; acn transform strips spaces and validates checksum. |
| Licensee Business Address | `address.full` | trim, collapse_whitespace | 0.8 | 1101 / 1101 |  | Publisher evidence: the company application collects the licensee's business address and it is published in the register. Values are a combined street/locality/'QLD'/postcode string; no reliable separate locality/postcode columns, so only the full address is mapped. |
| Licensee Business Address | `address.state` | trim, regex_extract({"pattern": "\\b(NSW\|VIC\|QLD\|WA\|SA\|TAS\|ACT\|NT)\\b", "group": 1}), state | 0.7 | 1083 / 1101 |  | State abbreviation (e.g. 'QLD') is embedded in the address string; extracted by regex then normalised via the state transform. Sample is a QLD register so nearly all will be QLD. |

**Constants:**
- `address.country` = `AU` (conf 0.9): Queensland Building and Construction Commission register; all addresses in profiling carry an Australian state (QLD).

**Deliberately unmapped:**
- `_id` — CKAN internal datastore row id; used only for record_id, not a business identifier.
- `Licence Number` — Identifies the licence, not the business; also not unique per record (506 distinct / 508 rows). Mapping a licence ID as a business identifier would be wrong.
- `Licence Type DESC` — Describes whether the licence is held by an individual or company. Publisher evidence states a licence category does not by itself establish the holder's legal form, so this is ambiguous for entity_type; left unmapped to avoid a wrong enum.
- `Licence Type CODE` — Coded form (I/C) of Licence Type DESC; same ambiguity for entity_type.
- `Financial Category DESC` — Financial category of the licence (e.g. 'Self Certification - Trade'); a licence attribute, not an entity field.
- `Financial Category CODE` — Coded form of the licence financial category; not an entity field.
- `Licence Grade` — Grade of the licence (Trade Contractor, Site Supervisor, etc.); a licence attribute, not an entity field.
- `Licence Class Type` — Class/occupational category of the licence (Carpentry, Plumbing, etc.); a licence attribute, not an entity field.

**Held-out run:** 1101 records, 1101 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** ABN and state extraction are sound; the address is the holder's own business address, so claim_scope is fine, though full-address claims rest on unstructured strings. The real gap is entity_type: the source's 'Licence Type DESC/CODE' explicitly distinguishes Individual vs Company and should be used (at least conditionally for 'Company') rather than discarded. No incorrect dates, no legacy record-level validity, no licence/contract number misused as a business identifier, and no trading-name-as-legal-name error was observed. Note the grain claim is licence-level while entity fields are holder-level, so repeated holders across licence rows will duplicate entity observations — that is a grain concern, not a per-rule mapping error.
- doubtful: `address.full` <- ['Licensee Business Address'] — Mapped to address.full with claim_scope licence_holder_address. Publisher evidence says the business address is published and is the licensee's business address, so it is the entity's own address and not a licensed premises address — acceptable. However, the values are free-text strings that mix street, locality, state and postcode, and some (e.g. '51,107 Stanworth Rd Boondall QLD 4034') contain ambiguous unit/lot fragments; a full-address claim is reasonable but the lack of any structure makes it only partially verifiable.
- missed? `Licence Type DESC` -> `entity.entity_type` — Values 'Individual'/'Company' are the register's own statement of whether the licence holder is a natural person or a company. The config leaves this unmapped citing ambiguity, but for the value 'Company' (and 'Individual' paired with an ACN/ABN-to-ACN match) it is strong evidence for entity_type. At minimum a conditional rule company-only would be safe; note a bare 'Individual' does not establish sole_trader.
- missed? `Licence Type CODE` -> `entity.entity_type` — Coded I/C form of Licence Type DESC; the 'C' code supports entity_type=company with the same conditional logic. Leaving it fully unmapped forfeits the only explicit entity-form evidence in the source.

**Agent notes:** Advertised as CSV but the resource is a CKAN datastore_search JSON response: records live under result.records (record_path), with an outer help/success envelope. Individual licence holders appear as personal names in Licensee Name (legal_name for natural persons is acceptable here since the licensee is the legal person holding the licence; entity_type intentionally left unknown because Licence Type individual/company is a licence category, per publisher evidence). Business addresses are single combined strings with an embedded state; only address.full and address.state mapped, locality/postcode not reliably separable. No date columns present, so no entity.date_registered or observation.valid_* set. One ABN in the sample fails checksum and is correctly rejected by the abn transform.

## Decision

This experimental proposal is outside the approval queue.
