# Mapping review: `qbcc_licensees`

- **Status:** PENDING_REVIEW  (run `20261112T015521-14ea42`, prompt `prompts-v7`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb39510b79a8056568dd532843d75b711d3d44c193ff0d84447`
- **Licence:** CC-BY-4.0
- **Agent effort:** 1 proposal(s), 9 tool calls, 8 model calls, 90,170 prompt + 8,890 completion tokens, 210s model time

## Final proposal (v0, digest `b9c407a5867c4ab2b0d8e822eacff43c612144e5eec7e3612d21064e5d23b0db`)

**Record grain:** `licence_or_permit` — One record is one Queensland Building and Construction Commission licence (Licence Number + Licence Grade + Licence Class Type) as held by a licensee. The business participant is the licensee (licence holder), whose name/ACN/ABN/business address are the entity attributes. Licence Number is not unique per row (506 distinct over 508 discovery rows) because a holding can span grade/class rows, so row identity, not the licence number, identifies the record.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — _id is the CKAN datastore row identifier, unique across the discovery partition (508 distinct of 508 present), so it is a traceable per-record key. Licence Number is not unique (506 distinct / 508).

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "-", "N/A", "NA"]}) | 0.85 | 1101 / 1101 |  | 'Licensee Name' names the holder of the licence, i.e. the legal person the licence is issued to (e.g. 'FLASH AIR CONDITIONING AND ELECTRICAL PTY LTD'; a natural person for an Individual licence). A licensee/holder column is the holder's legal name, not a trading name. |
| ABN | `entity.abn` | abn | 0.95 | 612 / 618 | {'ABN_CHECKSUM': 6} | Column is literally an ABN formatted '99 999 999 999', present in 54.9% of rows; 99.6% of non-null values pass the ABN checksum, so the abn transform validates rather than guesses. |
| ACN | `entity.acn` | acn | 0.95 | 77 / 77 |  | Column is literally an ACN in '999 999 999' format, present in 6.7% of rows (company licensees); 100% of non-null discovery values pass the ACN checksum. Taken straight from the source, never derived from the ABN. |
| Licensee Business Address | `address.full` | trim, collapse_whitespace | 0.85 | 1101 / 1101 |  | 'Licensee Business Address' is the licensee's business address as a single free-text line ('90 HENDERSON RD LOGAN RESERVE QLD 4133'); kept whole as address.full. |
| Licensee Business Address | `address.state` | regex_extract({"pattern": "(QLD\|NSW\|VIC\|WA\|SA\|TAS\|ACT\|NT)\\s+\\d{3,4}\\s*$", "group": 1}), state | 0.8 | 1083 / 1101 |  | The state token immediately before the trailing postcode is the only reliable position of the state; anchored to the end of the string so street-name text cannot be mistaken for a state code, then normalised through the state transform. 503/508 emit (the remainder have no state/postcode tail). |
| Licensee Business Address | `address.postcode` | regex_extract({"pattern": "(\\d{3,4})\\s*$", "group": 1}), postcode | 0.85 | 1101 / 1101 |  | Australian addresses in this source end with the postcode; the trailing 3-4 digit run is the postcode (postcode transform re-pads 3-digit NT codes). |
| Licence Type DESC | `entity.entity_type` | trim, map_enum({"mapping": {"individual": "sole_trader", "company": "company", "partnership": "partnership", "trust": "trust", "incorporated association": "incorporated_association", "government": "government"}, "default": "unknown", "passthrough": false}) | 0.6 | 1101 / 1101 |  | QBCC licence type states the licensee's legal form with mutually exclusive values ('Individual', 'Company' in the discovery partition; codes I and C). 'Individual' means the licence is held by a natural person, i.e. a sole trader. Unlisted or ambiguous values fall back to unknown rather than being guessed. |

**Constants:**
- `address.country` = `AU` (conf 0.9): Queensland (QBCC) state register of Australian licensees; every address example carries an Australian state abbreviation and a 4-digit AU postcode.

**Deliberately unmapped:**
- `_id` — CKAN datastore row id, used only as record_id; it is the record's own id, not a business identifier.
- `Licence Number` — Identifier of the licence/permit record itself, not of the business entity; not unique per row (506 distinct in 508) and has no ontology target.
- `Licence Type CODE` — Coded form of Licence Type DESC ('I'/'C'); redundant with the entity_type mapping and not a mappable ontology value.
- `Financial Category DESC` — Financial category of the licence (single value 'Self Certification - Trade' in discovery); a licence attribute, not an entity field.
- `Financial Category CODE` — Coded form of the financial category ('SCT1'); licence attribute, not an entity field.
- `Licence Grade` — Licence grade/permit class of the licence record; no ontology target (licences are not modelled as fields).
- `Licence Class Type` — Trade/occupational class covered by the licence (e.g. 'Carpentry', 'Plumbing and Drainage'); a licence attribute, and not an ANZSIC code, so it must not be forced into entity.industry_code.
- `Licensee Business Address -> locality` — address.locality could not be separated from the street line reliably: the address is one undelimited free-text string, so any locality regex would also capture street-name tokens. Full address is mapped; locality left unmapped to avoid a wrong value.

**Held-out run:** 1101 records, 1101 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** All mappings are largely correct and well-justified. Only rule_index 6 (entity.entity_type) is doubtful due to potential over-assumption that 'Individual' licence type always equals sole_trader, which may not hold if an individual operates under a different legal structure. No critical source columns appear unmapped that should have been included; Licence Class Type was correctly excluded from industry_code as it is occupational, not ANZSIC.
- doubtful: `entity.entity_type` <- ['Licence Type DESC'] — Mapping 'Individual' licence type to sole_trader assumes all individual licensees are sole traders, but individuals may operate under other structures (e.g., as trustees or partners) without explicit evidence. The ontology warns against guessing entity_type; while QBCC 'Individual' typically implies natural person, it does not definitively confirm sole_trader status without additional structural data.

**Agent notes:** Advertised format is CSV but the payload is a CKAN datastore_search JSON envelope (magic bytes 7b2268656c70223a = '{"help":'), so records are read from result.records with 12 flat fields each; reader format is json, not delimited. Grain is one licence row held by a licensee: entity attributes describe the licence holder, and licence-specific attributes (number, type code, financial category, grade, class) are deliberately unmapped. No date column exists in the source, so observed_at falls back to resource_last_modified and no valid_from/valid_to paths are set. One discovery ABN ('93 939 550 174') fails the ABN checksum and is rejected as a bad source value rather than coerced. 'Individual' -> sole_trader is an inference from the licence type stated by the register; hedge kept via default unknown for other values.

## Decision

This experimental proposal is outside the approval queue.
