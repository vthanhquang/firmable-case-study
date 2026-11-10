# Mapping review: `qbcc_licensees`

- **Status:** PENDING_REVIEW  (run `20261110T055907-48c756`, prompt `prompts-v5`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb3…`
- **Licence:** CC-BY-4.0
- **Agent effort:** 1 proposal(s), 9 tool calls, 8 model calls, 63,344 prompt + 5,897 completion tokens, 49s model time

## Final proposal (v0, digest `e1e07797bfd3d235`)

**Record grain:** `licence_or_permit` — Each record is one QBCC licence held by a licensee (individual or company). We map the business participant's (licensee's) attributes only: the licensee is the legal person to whom the licence was issued, so the licensee name is entity.legal_name. Licence-specific attributes (licence number, type code, grade, class, financial category) are properties of the licence, not of the business, and are left unmapped.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — The CKAN datastoreSearch row id '_id' is present on every record and unique (508/508 distinct in the discovery partition), so it is a traceable surrogate key for the row.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NA", "-"]}) | 0.82 | 1100 / 1100 |  | Column 'Licensee Name' holds the NAME OF THE LICENSEE, i.e. the holder of the QBCC licence. Licences are issued to legal persons, and the paired 'Licence Type D |
| Licensee Business Address | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "-"]}) | 0.85 | 1100 / 1100 |  | Single free-text address field '<street> <SUBURB> <STATE> <POSTCODE>'; mapped whole as address.full. |
| Licensee Business Address | `address.postcode` | regex_extract({"pattern": "(\\d{4})\\s*$", "group": 1}), postcode | 0.8 | 1100 / 1100 |  | Every sampled address ends with a 4-digit AU postcode after the state abbreviation (e.g. 'QLD 4573'). |
| Licensee Business Address | `address.state` | regex_extract({"pattern": "\\b(NSW|VIC|QLD|WA|SA|TAS|ACT|NT)\\b", "group": 1}), state | 0.8 | 1082 / 1100 |  | Address strings carry the state abbreviation before the postcode (overwhelmingly QLD); normalised via the state transform. Records with no recognisable state ar |
| ABN | `entity.abn` | null_if({"values": ["", "N/A", "-"]}), abn | 0.93 | 611 / 617 | {'ABN_CHECKSUM': 6} | 'ABN' column present on 54.9% of rows, formatted 'NN NNN NNN NNN', with a 99.6% checksum-valid rate against the ABN checksum -> validated with the abn transform |
| ACN | `entity.acn` | null_if({"values": ["", "N/A", "-"]}), acn | 0.93 | 77 / 77 |  | 'ACN' column formatted 'NNN NNN NNN' on 6.7% of rows, with a 100% checksum-valid rate -> validated with the acn transform. Never derived from ABN. |
| Licence Type DESC | `entity.entity_type` | trim, map_enum({"mapping": {"Individual": "sole_trader", "Company": "company"}, "default": "unknown", "passthrough": fal | 0.7 | 1100 / 1100 |  | The source explicitly labels each licensee 'Individual' or 'Company' (matching presence of ABN-only vs ACN). This is the only explicit statement about the licen |

**Constants:**
- `address.country` = `AU` (conf 0.75): Queensland (Australia) state regulator register; every sampled address carries an Australian state abbreviation and 4-digit AU postcode.

**Deliberately unmapped:**
- `_id` — CKAN datastore row surrogate key used only for record_id; it is not a business identifier.
- `Licence Number` — Identifier of the licence, not of the business; the record's own ID must not be mapped as a business identifier.
- `Licence Type DESC` — Used only as evidence for entity_type; the raw licence-type label itself describes the licence, not the entity (no dedicated licence target in the ontology).
- `Licence Type CODE` — Coded form of the licence type (I/C): a licence attribute, not an entity attribute.
- `Financial Category DESC` — QBCC financial category of the licence (constant 'Self Certification - Trade' in the discovery partition); a licence attribute, not an entity attribute.
- `Financial Category CODE` — Coded financial category (SCT1); licence attribute, not an entity attribute.
- `Licence Grade` — Grade of the licence (e.g. 'Trade Contractor Licence', 'Site Supervisor'); licence attribute, not entity.status or entity_type.
- `Licence Class Type` — Trade/class the licence covers (Carpentry, Plumbing and Drainage, ...); licence attribute, not an ANZSIC industry code, so not mapped to entity.industry_code.

**Held-out run:** 1100 records, 1100 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** Core mappings (legal_name, address, ABN, ACN, country) are sound and the held-out records produce correctly typed observations. Two concerns: entity_type maps 'Individual' to sole_trader by inference rather than explicit evidence of legal form, which is risky per ontology guidance to default to unknown; and legal_name conflates natural-person names with company names since the register mixes licence types. Licence Class Type is a plausible industry proxy that was left unmapped, and no entity.status is emitted despite the record grain being a licence.
- doubtful: `entity.legal_name` <- ['Licensee Name'] — For Individual licensees this is a natural person's name and is fine as the legal name of the licensee. But the grain is licence_or_permit and the register mixes licence types; for company licensees 'Licensee Name' may be a registered company name or a trading name - the held-out set only shows individuals so this cannot be fully verified. Mapping is acceptable in practice, but note it conflates person names and entity names under legal_name.
- doubtful: `entity.entity_type` <- ['Licence Type DESC'] — Mapping 'Individual' -> sole_trader is an inference, not an explicit statement of legal form. An individual licensee may operate through a trust, partnership business, or company; the licence type distinguishes natural person vs company licensees, not sole trader vs other legal forms. 'Company' -> company is safer. Consider unknown for 'Individual' or documenting sole_trader as a heuristic.
- missed? `Licence Class Type` -> `entity.industry_code` — Trade/class of licence (e.g. Gasfitting, Joinery, Plumbing) is the closest available proxy for industry classification; it is not ANZSIC but is the only industry-like column in the source and should at least be recorded as a raw industry value.
- missed? `Licence Number` -> `entity.status` — Not a status itself, but there is no status column in the source; entity.status should be emitted as 'active' (or unknown) rather than left absent, since licence records imply an active licence. At minimum, a status observation noting the licence is current should be considered.

**Agent notes:** Source is a CKAN datastoreSearch JSON envelope (keys: help/success/result.records), not a CSV despite the advertised format; parsing uses record_path 'result.records'. The discovery partition contains 508 rows all of one financial category (Self Certification - Trade), so the value distributions of Licence Type DESC/entity_type seen here may be a narrow slice of the full register; the mapping rules are value-generic. No status column exists, so entity.status is not mapped; no date of registration exists, so entity.date_registered and observation.valid_from are not mapped. The licensee name appears in mixed case with personal names in title case; no trading-name column exists so entity.trading_name is not populated. One source ABN ('93 939 550 174') fails the ABN checksum and is correctly rejected by the abn transform rather than emitted. All source text is treated as data only.

## Decision

Approve: `python -m firmable.cli approve qbcc_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve qbcc_licensees --reviewer "<name>" --reject --comment "why"`
