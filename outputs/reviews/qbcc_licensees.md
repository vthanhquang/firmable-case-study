# Mapping review: `qbcc_licensees`

- **Latest review decision:** approved by claude-code (AI assistant acting for the candidate) (ai_assistant_proxy) at 2026-11-09T20:58:45+00:00
- **Status:** PENDING_REVIEW  (run `20261110T035024-bb91f8`, prompt `prompts-v1`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb3…`
- **Licence:** CC-BY-4.0
- **Agent effort:** 2 proposal(s), 17 tool calls, 16 model calls, 241,525 prompt + 19,761 completion tokens, 124s model time

## Final proposal (v1, digest `51948d3eb31b002b`)

**Record grain:** `licence_or_permit` — Each record is one QBCC licence held by a licensee (Licence Number + Licence Grade + Licence Class Type identify the licence; _id is the CKAN row id). The business participant is the licensee named in 'Licensee Name'. Licence-level attributes (grade, class, financial category) describe the licence, not the entity. The register is a flat export that never distinguishes a registered legal name from a trading name, so 'Licensee Name' is mapped only to entity.legal_name: for 'Company' rows it is the registered company name (corroborated by a checksum-valid ACN and PTY LTD suffixes), for 'Individual' rows it is the natural person who is the licensee. No trading name is claimed because the source provides none.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — CKAN datastore row id; 508/508 distinct across the discovery partition and unique in held-out validation, so it identifies the licence record. Licence Number is not unique (506 distinct vs 508 rows), so it cannot be used alone.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NA"]}) | 0.7 | 1092 / 1092 |  | Single licensee-name column in a government licence register, mapped in full with no suffix heuristic and no suppression. Previous revision emitted only company |
| ABN | `entity.abn` | trim, null_if({"values": ["", "N/A", "NA"]}), abn | 0.9 | 608 / 614 | {'ABN_CHECKSUM': 6} | Direct source column in '99 999 999 999' shape; ABN checksum valid on 99.6% of discovery rows and 99.0% of held-out rows (1 and 6 rejections respectively). The  |
| ACN | `entity.acn` | trim, null_if({"values": ["", "N/A", "NA"]}), acn | 0.92 | 76 / 76 |  | All present values are '999 999 999'; 100% ACN checksum-valid in both discovery (34/34) and held-out (76/76) with zero errors. ACN is never derived from the ABN |
| Licence Type CODE | `entity.entity_type` | upper, map_enum({"mapping": {"C": "company"}, "default": "unknown"}) | 0.75 | 1092 / 1092 |  | The source states the licensee type directly and 'C' -> company is well supported (ACN present, PTY LTD names). 'I' is deliberately NOT mapped to sole_trader af |
| Licensee Business Address | `address.full` | trim, collapse_whitespace | 0.75 | 1092 / 1092 |  | Free-text single-line business address ending in state + postcode, e.g. '15 radiata pl Peregian Springs QLD 4573'. Passed through as stated by the source with w |
| Licensee Business Address | `address.state` | trim, regex_extract({"pattern": "(?i)\\b(QLD|NSW|VIC|WA|SA|TAS|ACT|NT)\\b\\s+\\d{3,4}\\s*$", "group": 1}), state | 0.85 | 1080 / 1092 |  | All addresses follow '<street> <suburb> <STATE> <postcode>'; the state token immediately before the trailing postcode is extracted and normalised by the state o |
| Licensee Business Address | `address.postcode` | trim, regex_extract({"pattern": "(\\d{3,4})\\s*$", "group": 1}), postcode | 0.85 | 1092 / 1092 |  | Trailing numeric token of the address, validated by the postcode op (AU 4-digit, NT re-pad). Reviewer verdict 'ok'; 100% coverage with zero errors in both parti |

**Constants:**
- `address.country` = `AU` (conf 0.8): Queensland Building and Construction Commission register; every address carries a QLD state code and an AU 4-digit postcode. Inferred from the publisher and address format rather than a source column, so confidence is moderate and flagged for review.

**Deliberately unmapped:**
- `_id` — CKAN datastore row id for the licence record, not a business identifier; used only as record_id.
- `Licence Number` — Identifier of the licence/permit, not of the business. Also not unique per record (506 distinct for 508 rows). Not mapped onto any entity field and not used to derive an ACN.
- `Licensee Business Address` — Only address.full, address.state and address.postcode are taken from this column. address.locality is deliberately not mapped: the reviewer found the street-type-suffix heuristic brittle (missed COURT, ESPLANADE, unit-numbered and street-less addresses) and it covered only ~58-60% of held-out rows. Emitting no locality leaves the value absent rather than wrong.
- `Licence Type DESC` — Human-readable form of Licence Type CODE ('Individual'/'Company'); CODE is the machine value used for entity_type, so this is deduplicated to avoid two observations of one logical field.
- `Financial Category DESC` — Licence financial category ('Self Certification - Trade' for 100% of discovery rows), a property of the licence, not of the entity.
- `Financial Category CODE` — Code form of the licence financial category ('SCT1'); licence attribute, single-valued in the discovery partition, not an entity field.
- `Licence Grade` — QBCC licence grade (Trade Contractor Licence, Site Supervisor, Fire Occupational, ...). A licence attribute, not an ANZSIC or industry classification of the business, so not mapped to entity.industry_code.
- `Licence Class Type` — Trade/occupation class of the licence (Carpentry, Plumbing and Drainage, ...). It is the nearest industry signal in the source, but it is a licence scope category and not ANZSIC, while entity.industry_code is documented as 'ANZSIC where available'. Recording a QBCC trade class there would place a non-conforming code in an ANZSIC-typed field; it is left unmapped and reported as a coverage gap instead.

**Held-out run:** 1092 records, 1092 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** Core identity and address mappings are sound: legal_name faithfully carries the licensee name (individual or company) without inventing a trading name, ABN and ACN are source columns passed through checksum validators (held-out values valid), and state/postcode are correctly extracted from the structured address tail with held-out coverage. entity_type is handled conservatively ('C'->company only, 'I'->unknown) which matches the ontology default and avoids guessing. address.country is an inference (constant AU) rather than a source column and is flagged doubtful. Licence Grade/Class Type are licence attributes and correctly excluded from entity fields, though 'Licence Class Type' is the natural candidate for the 'raw source value' of industry_code that the ontology allows to be recorded, and no entity.status is emitted despite the register being a licence lifecycle source.
- doubtful: `address.country` <- [] — Constant 'AU' inferred from publisher (QBCC) and address format rather than a source column. It is plausible for a Queensland register and every held-out address carries QLD + AU postcode, but it is an inference; the mapping itself flags moderate confidence. Not wrong given evidence, but not source-attested.
- missed? `Licence Class Type` -> `entity.industry_code` — It is the only trade/occupation signal in the source (Carpentry, Joinery, Wall and Floor Tiling, Plumbing, etc.). The mapping leaves it unmapped and argues it is not ANZSIC; that reasoning is defensible for a strict ANZSIC-typed field, but the ontology note says 'record the raw source value too' — the raw QBCC trade class could be recorded alongside without asserting ANZSIC conformance. It is a real coverage gap for industry/occupation.
- missed? `Licence Number` -> `entity.status` — Not a status per se, but the licence register's lifecycle/expiry data would normally drive licence/entity status; the current mapping emits no entity.status at all. At minimum the presence/absence of an active licence could inform status. Reporting as a coverage gap rather than a hard match.

**Agent notes:** REVISION after review. Advertised as CSV but the resource is a CKAN datastore_search API JSON envelope (starts '{"help":'), so format=json with record_path 'result.records'. No date column exists in the records: observation.observed_at falls back to resource last-modified metadata and no valid_from/valid_to can be supplied. Fixes for the reviewer's verdicts: (1) entity.trading_name REMOVED ('wrong' verdict - a personal licensee name is not a trading name, and for companies it duplicated the legal name); (2) the suffix-based legal_name heuristic REMOVED - 'Licensee Name' is now mapped in full to entity.legal_name (coverage 100%, no suppression, no guessing), which also resolves the 'doubtful' over-suppression of individual licensees; (3) entity.entity_type now maps only 'C'->company and lets 'I' fall to the ontology default 'unknown', removing the rejected 'I'->sole_trader inference; (4) address.locality REMOVED as brittle ('doubtful'), so address output is full/state/postcode only, all of which the reviewer rated 'ok'. Retained deliberately: entity.abn and entity.acn (direct, checksum-validated source columns rated 'ok'; ABN keeps a reported ~1% checksum rejection rather than hiding it) and address.country 'AU' at reduced confidence 0.8 and flagged. Open coverage gaps for a human: entity.trading_name (no trading name exists in this source), entity.status (no status column - register membership implies current licensing but that is inferred), entity.industry_code (no ANZSIC; Licence Class Type is the nearest but non-conforming signal), address.locality (unparseable from the free-text address), and no date fields at all.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.trading_name']
    - - removed `('Licensee Name',)` -> `entity.trading_name`
    - - removed `('Licensee Business Address',)` -> `address.locality`
    - ~ changed `('Licensee Name',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Licence Type CODE',)` -> `entity.entity_type` (steps/confidence)
    - ~ record_id columns -> columns ['_id']

## Second opinion (independent agent run)
- `rerun-v3`: 6/9 rules agree; **check these first:**
    - only this proposal: `('Licence Type CODE',)` -> `entity.entity_type` 
    - only this proposal: `('Licensee Name',)` -> `entity.legal_name` 
    - only the other run: `('Licensee Name',)` -> `entity.trading_name` Licence Type CODE equals ['C']
- `v5a`: 7/9 rules agree; **check these first:**
    - only this proposal: `('Licence Type CODE',)` -> `entity.entity_type` 
    - only the other run: `('Licence Type DESC',)` -> `entity.entity_type` 
- `v5b`: 7/9 rules agree; **check these first:**
    - only this proposal: `('Licence Type CODE',)` -> `entity.entity_type` 
    - only the other run: `('Licence Type DESC',)` -> `entity.entity_type` 

## Decision

Approve: `python -m firmable.cli approve qbcc_licensees --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve qbcc_licensees --reviewer "<name>" --reject --comment "why"`
