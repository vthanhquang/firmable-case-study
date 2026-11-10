# Mapping review: `qbcc_licensees`

- **Status:** PENDING_REVIEW  (run `20261110T045803-d51345`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb3…`
- **Licence:** CC-BY-4.0
- **Agent effort:** 3 proposal(s), 22 tool calls, 24 model calls, 383,035 prompt + 20,973 completion tokens, 161s model time

## Final proposal (v2, digest `f2b91ed0fd33deeb`)

**Record grain:** `licence_or_permit` — One record is one QBCC licence held by a licensee (Licence Number is the licence identity; '_id' is the data.gov.au datastore row id). Business/entity attributes describe the licensee participant, not the licence. Most records are Individual licensees, where 'Licensee Name' is a natural person's name (including nominee supervisors who act for a company and are not the business); such person names are not mapped at all. Only for Company licensees, where the name is a business name, is it emitted, and only as trading_name because the register never asserts an ASIC-registered legal name.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — _id is the data.gov.au datastore row id and is distinct across all 508 discovery records, so it uniquely and traceably identifies the record.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name *when Licence Type CODE equals ['C']* | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.6 | 77 / 77 |  | Only for 'Company' licensees is this column a business name as used on the licence (e.g. 'FLASH AIR CONDITIONING AND ELECTRICAL PTY LTD'). It is plausibly the r |
| ACN | `entity.acn` | acn | 0.97 | 77 / 77 |  | ACN column formatted '999 999 999'; 100% of present values pass the ACN checksum (34/34 discovery, 77/77 held-out present). |
| ABN | `entity.abn` | abn | 0.96 | 611 / 617 | {'ABN_CHECKSUM': 6} | ABN column formatted '99 999 999 999'; 99.6% of discovery and 99.0% of held-out present values pass the ABN checksum; the few failures are surfaced as errors ra |
| Licensee Business Address | `address.full` | trim, collapse_whitespace | 0.9 | 1100 / 1100 |  | Single free-text address field labelled 'Licensee Business Address' ('street locality STATE postcode'); kept whole as the full address. |
| Licensee Business Address | `address.state` | regex_extract({"pattern": "\\b(QLD|NSW|VIC|WA|SA|TAS|ACT|NT|NZ)\\b\\s+\\d{3,4}\\s*$", "group": 1}), state | 0.9 | 1082 / 1100 |  | Address ends with a state abbreviation before the postcode (99% of held-out rows). |
| Licensee Business Address | `address.postcode` | regex_extract({"pattern": "(\\d{4})\\s*$", "group": 1}), postcode | 0.9 | 1100 / 1100 |  | Trailing 4-digit postcode in every sampled value. |

**Constants:**
- `address.country` = `AU` (conf 0.7): Queensland (QBCC) state register; business addresses carry QLD/other AU state abbreviations, so the licensee's address country is Australia.

**Deliberately unmapped:**
- `_id` — Datastore row id, not a business identifier; used only as record_id.
- `Licence Number` — Identifier of the licence/permit record, not of the business; must not be mapped to an entity identifier. Not used as record_id either because 2 values are duplicated across different datastore rows.
- `Licensee Name` — Emitted only as entity.trading_name and only for Company licensees. For Individual licensees (the large majority of records, incl. nominee supervisors) the value is a natural person's name, not a business name, so it is deliberately not mapped. Not mapped to legal_name for any row because the register never asserts an ASIC-registered legal name.
- `Licence Type DESC` — Describes the form of the licence holder (Individual/Company). 'Individual' covers sole traders and employee nominee supervisors alike, so it does not state an entity type; entity_type is left as the ontology default 'unknown' per guidance against guessing.
- `Licence Type CODE` — Coded form of Licence Type DESC (I/C); used only as the row condition restricting name mapping to Company licensees. Not a legal-form code.
- `Financial Category DESC` — Licence financial category (classification of the licence), not a business attribute. Single value 'Self Certification - Trade' in discovery.
- `Financial Category CODE` — Coded form of Financial Category DESC; licence classification, not a business attribute.
- `Licence Grade` — Grade of the licence (Trade Contractor Licence, Site Supervisor, Nominee Supervisor, etc.); describes the permit, not the business, and is not a status. No suitable ontology target; this extract carries no licence status column, so entity.status is left unset rather than inferred.
- `Licence Class Type` — Licensed trade specialisation (Carpentry, Plumbing and Drainage, Gasfitting, ...), a licence classification rather than an ANZSIC industry code, and some values arrive truncated from the source; stuffing it into entity.industry_code would conflate a licence class with an industry code and propagate source truncation, so it is left unmapped.
- `Licensee Business Address` — Used for address.full/state/postcode/country. Locality is NOT mapped: the address is a single free-text field and no split that fits the engine's regex limits is reliable and consistent (street-type lists miss 'Esplanade', 'Bvd', 'Court', 'Cr', and streets without a type token), so guessing would produce inconsistent partial values.

**Held-out run:** 1100 records, 1100 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** Address parsing (full/state/postcode/country) and ABN/ACN checksummed extraction are correct and verified on held-out rows; the conservative decision not to map natural-person names or to guess entity_type/status is appropriate. The only item warranting scrutiny is entity.trading_name from 'Licensee Name': the Company-only, trading_name-not-legal_name choice is defensible but untested in the held-out sample (all Individual). Licence Class Type as industry_code is a plausible but argued-against omission.
- doubtful: `entity.trading_name` <- ['Licensee Name'] — The rationale (only Company licensees; never legal_name because ASIC registration is not asserted) is sound and the held-out rows are all Individual so no trading_name was emitted — consistent. But since the register's Company-name value is plausibly the registered Pty Ltd name and the mapping entirely suppresses name for Individuals, this is a conservative choice that is defensible; without a Company row shown here the emit-only-for-Company condition can't be fully verified. Directionally acceptable but conditional/untested in held-out sample.
- missed? `Licence Class Type` -> `entity.industry_code` — The mapping explicitly declines it, arguing a licensed trade class is not ANZSIC. That is defensible, but the ontology says to record the raw source value for industry_code where available; if treated as a raw licence-trade classification it could be recorded. Verdict depends on strictness — flagged as a possible but likely-intentional omission (truncation issue noted).
- missed? `Licence Grade` -> `entity.status` — No status column exists in this extract; the mapping correctly leaves entity.status unset rather than inferring. Not actually a missed target — no suitable status source present.

**Agent notes:** Source is a data.gov.au datastore_search API JSON wrapper (top-level keys include help/success/result); records live at result.records and the advertised 'CSV' metadata is inaccurate. No dates (registration/renewal/lapse) are present, so observed_at falls back to resource last-modified and valid_from/valid_to are empty. Revision history: entity_type removed (licence-holder form is not an explicit legal-form statement; 'Individual' includes nominee supervisors); names mapped to trading_name only for Company licensees after a review flagged person-as-trading-name; address.locality and Licence Class Type moved to unmapped as unreliable / not an industry code. Expected shape downstream: Company records carry trading_name + ACN (+ ABN where present); Individual records carry address only, plus ABN where the licensee supplied one. Licence grade/class and licence number remain available in the source for consumers needing permit-level detail. ABN values failing the checksum (~1% of present) are surfaced as errors, not coerced or suppressed.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.entity_type']
    - + added `('Licensee Name',)` -> `entity.trading_name`
    - + added `('Licence Class Type',)` -> `entity.industry_code`
    - - removed `('Licensee Name',)` -> `entity.legal_name`
    - - removed `('Licence Type DESC',)` -> `entity.entity_type`
    - - removed `('Licensee Business Address',)` -> `address.locality`
    - ~ changed `('ABN',)` -> `entity.abn` (steps/confidence)
    - ~ record_id columns -> columns ['_id']
- v1 -> v2: triggered by validator errors none, critic 'wrong' ['entity.trading_name']
    - - removed `('Licence Class Type',)` -> `entity.industry_code`
    - ~ changed `('Licensee Name',)` -> `entity.trading_name` (steps/confidence)
    - ~ record_id columns -> columns ['_id']

## Decision

Approve: `python -m firmable.cli approve qbcc_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve qbcc_licensees --reviewer "<name>" --reject --comment "why"`
