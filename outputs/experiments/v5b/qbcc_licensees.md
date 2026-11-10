# Mapping review: `qbcc_licensees`

- **Status:** PENDING_REVIEW  (run `20261110T060131-742227`, prompt `prompts-v5`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb3…`
- **Licence:** CC-BY-4.0
- **Agent effort:** 1 proposal(s), 11 tool calls, 10 model calls, 94,943 prompt + 8,939 completion tokens, 61s model time

## Final proposal (v0, digest `c1e346bd4ffce355`)

**Record grain:** `licence_or_permit` — One record is one QBCC licence held by a licensee. The business participant is the licensee (the holder legal person); the licence number, licence grade, licence class and financial category describe the licence itself, not the business, so they are left unmapped.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — The CKAN datastore row id is unique per record in the discovery partition (508/508 distinct); Licence Number has duplicate rows (506/508). _id is the traceable record key, not a business identifier.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "dataset_metadata_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "-", "NOT STATED", "UNKNOWN"]}) | 0.85 | 1100 / 1100 |  | Column is 'Licensee Name' - a licence is issued to a legal person, so the licensee is the holder's legal name. Values are registered-style names (e.g. 'FLASH AI |
| Licence Type DESC | `entity.entity_type` | trim, map_enum({"mapping": {"Individual": "sole_trader", "Company": "company", "Partnership": "partnership", "Trust": "t | 0.8 | 1100 / 1100 |  | Licence Type DESC explicitly states the licensee's legal form: 'Individual' -> sole_trader, 'Company' -> company. Only these two values observed; everything els |
| ABN | `entity.abn` | null_if({"values": ["", "-"]}), abn | 0.9 | 611 / 617 | {'ABN_CHECKSUM': 6} | Column 'ABN', values shape '99 999 999 999', 99.6% checksum-valid over 279 populated values - genuine ABNs. Checksum transform rejects the remainder (1 invalid  |
| ACN | `entity.acn` | null_if({"values": ["", "-"]}), acn | 0.9 | 77 / 77 |  | Column 'ACN', values shape '999 999 999', 100% checksum-valid over 34 populated values. Mapped as its own column only; never derived from ABN. |
| Licensee Business Address | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "-"]}) | 0.85 | 1100 / 1100 |  | Full business address as stated in the one free-text address column. |
| Licensee Business Address | `address.state` | regex_extract({"pattern": "(QLD|NSW|VIC|WA|SA|TAS|ACT|NT)\\s*\\d{4}\\s*$", "group": 1}), state | 0.85 | 1082 / 1100 |  | Address strings consistently end with '<STATE> <POSTCODE>' (e.g. 'Toorbul QLD 4510'); the state token is extracted from that tail rather than assumed as a const |
| Licensee Business Address | `address.postcode` | regex_extract({"pattern": "(QLD|NSW|VIC|WA|SA|TAS|ACT|NT)\\s*(\\d{4})\\s*$", "group": 2}), postcode | 0.85 | 1082 / 1100 |  | 4-digit postcode is the trailing token of the address after the state abbreviation. |

**Constants:**
- `address.country` = `AU` (conf 0.8): Queensland Building and Construction Commission register of Australian licensees; all addresses carry Australian state abbreviations and 4-digit postcodes.

**Deliberately unmapped:**
- `_id` — CKAN datastore row identifier; used as record_id only, not a business identifier.
- `Licence Number` — Identifier of the licence, not of the business. Not mapped to any entity identifier.
- `Licence Type CODE` — Coded form ('I'/'C') of Licence Type DESC, which is already used for entity_type; redundant.
- `Licence Grade` — Describes the licence (e.g. Trade Contractor Licence, Site Supervisor), not the legal entity.
- `Licence Class Type` — Trade/occupational class of the licence (e.g. Carpentry, Gasfitting); not an ANZSIC industry code, so not entity.industry_code.
- `Financial Category DESC` — Financial category of the licence; constant in this partition and not an entity attribute.
- `Financial Category CODE` — Code form of Financial Category DESC; licence attribute, not an entity field.

**Held-out run:** 1100 records, 1100 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** All mapped fields are semantically defensible. legal_name is the licensee legal name (correct for a licence-holder register; sole-trader personal names are the legal name for individuals). entity_type is read directly from an explicit licence-type column rather than guessed. ABN/ACN use their own columns with checksums and no cross-derivation. Address fields are extracted from the one address column with an anchored state/postcode pattern, and country constant AU is justified. No clearly matching source columns were left unmapped: the licence number, grade, class and financial category are genuine licence attributes, not entity attributes, and are correctly excluded (Licence Class Type is not an ANZSIC code, so not industry_code). No material data-quality concerns in the heldout records.

**Agent notes:** Source is a CKAN datastore_search JSON envelope (help/value/result.records); records are read from result.records. No observation or validity dates are exposed by the source, so observed_at falls back to dataset metadata modified and no valid_from/valid_to is emitted. No trading-name column exists, so entity.trading_name is not populated. Licence status is not present in this file; entity.status is therefore left unmapped rather than inferred. address.state/postcode resolve for 503/508 records; the remaining 5 have non-standard address tails and are left unset rather than guessed.

## Decision

Approve: `python -m firmable.cli approve qbcc_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve qbcc_licensees --reviewer "<name>" --reject --comment "why"`
