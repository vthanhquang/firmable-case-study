# Mapping review: `qbcc_licensees`

- **Status:** PENDING_REVIEW  (run `20261112T155030-b0b69c`, prompt `prompts-v9-profile-context-v1`, model `deepseek-v4-flash`)
- **Dataset:** QBCC Licensed Contractors Register — Queensland Building and Construction Commission
- **Resource:** QBCC register of licensed builders and contractors (CSV), sha256 `509b287a7bf36eb39510b79a8056568dd532843d75b711d3d44c193ff0d84447`
- **Licence:** CC-BY-4.0
- **Agent effort:** 1 proposal(s), 5 tool calls, 6 model calls, 37,856 prompt + 1,864 completion tokens, 96s model time

## Final proposal (v0, digest `1b7bf09eb5f3f0b4f712943356a4a9595a1991a9c063f7cb7bc6c45035eef15e`)

**Record grain:** `licence_or_permit` — Each record is one QBCC licence held by a licensee (Licence Number + Licence Grade + Licence Class Type identify the licence; _id is the CKAN row id). The business participant is the licensee named in 'Licensee Name'. Licence-level attributes (grade, class, financial category) describe the licence, not the entity. The register is a flat export that never distinguishes a registered legal name from a trading name, so 'Licensee Name' is mapped only to entity.legal_name: for 'Company' rows it is the registered company name (corroborated by a checksum-valid ACN and PTY LTD suffixes), for 'Individual' rows it is the natural person who is the licensee. No trading name is claimed because the source provides none.

**Reader:** `{"format": "json", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 0, "sheet": null, "record_path": "result.records"}`

**Record id:** `columns` ['_id'] — CKAN datastore row id; 508/508 distinct across the discovery partition and unique in held-out validation, so it identifies the licence record. Licence Number is not unique (506 distinct vs 508 rows), so it cannot be used alone.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee Name | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NA"]}) | 0.7 | 1101 / 1101 |  | Single licensee-name column in a government licence register, mapped in full with no suffix heuristic and no suppression. Previous revision emitted only company-suffixed names here (7% coverage) and pushed personal names to trading_name; the reviewer rejected that split. An individual licensee is the natural person holding the licence, so its name belongs in legal_name rather than being dropped or relabelled as a trading name. |
| ABN | `entity.abn` | trim, null_if({"values": ["", "N/A", "NA"]}), abn | 0.9 | 612 / 618 | {'ABN_CHECKSUM': 6} | Direct source column in '99 999 999 999' shape; ABN checksum valid on 99.6% of discovery rows and 99.0% of held-out rows (1 and 6 rejections respectively). The abn transform strips separators and refuses to emit a checksum-invalid value, so bad source data surfaces as a counted error instead of a fabricated ABN. The residual ~1% rejections are reported honestly, not hidden. |
| ACN | `entity.acn` | trim, null_if({"values": ["", "N/A", "NA"]}), acn | 0.92 | 77 / 77 |  | All present values are '999 999 999'; 100% ACN checksum-valid in both discovery (34/34) and held-out (76/76) with zero errors. ACN is never derived from the ABN. |
| Licence Type CODE | `entity.entity_type` | upper, map_enum({"mapping": {"C": "company"}, "default": "unknown"}) | 0.75 | 1101 / 1101 |  | The source states the licensee type directly and 'C' -> company is well supported (ACN present, PTY LTD names). 'I' is deliberately NOT mapped to sole_trader after the reviewer rejected that inference (an individual licensee may be a partner or trust principal); 'I' rows therefore resolve to the ontology default 'unknown' rather than a guess. |
| Licensee Business Address | `address.full` | trim, collapse_whitespace | 0.75 | 1101 / 1101 |  | Free-text single-line business address ending in state + postcode, e.g. '15 radiata pl Peregian Springs QLD 4573'. Passed through as stated by the source with whitespace normalisation only. |
| Licensee Business Address | `address.state` | trim, regex_extract({"pattern": "(?i)\\b(QLD\|NSW\|VIC\|WA\|SA\|TAS\|ACT\|NT)\\b\\s+\\d{3,4}\\s*$", "group": 1}), state | 0.85 | 1089 / 1101 |  | All addresses follow '<street> <suburb> <STATE> <postcode>'; the state token immediately before the trailing postcode is extracted and normalised by the state op (unknown -> OTHER). Reviewer verdict 'ok'; 1080/1092 held-out rows emitted with zero errors. |
| Licensee Business Address | `address.postcode` | trim, regex_extract({"pattern": "(\\d{3,4})\\s*$", "group": 1}), postcode | 0.85 | 1101 / 1101 |  | Trailing numeric token of the address, validated by the postcode op (AU 4-digit, NT re-pad). Reviewer verdict 'ok'; 100% coverage with zero errors in both partitions. |
| Licence Number | `context.licence.number` | trim | 0.95 | 1101 / 1101 |  | QBCC licence number identifies the licence per publisher guidance. |
| Financial Category DESC | `context.licence.category` | trim, collapse_whitespace | 0.75 | 1101 / 1101 |  | Financial category wording is the publisher's licence category label for this licence. |
| Licence Grade | `context.licence.grade` | trim, collapse_whitespace, null_if({"values": ["NOT APPLICABLE", ""]}) | 0.9 | 1101 / 1101 |  | Published grade of the licence. |
| Licence Class Type | `context.licence.class` | trim, collapse_whitespace | 0.9 | 1101 / 1101 |  | Published licence class preserved verbatim in QBCC wording, including parenthetical qualifiers. |

**Constants:**
- `address.country` = `AU` (conf 0.8): Queensland Building and Construction Commission register; every address carries a QLD state code and an AU 4-digit postcode. Inferred from the publisher and address format rather than a source column, so confidence is moderate and flagged for review.

**Deliberately unmapped:**
- `_id` — CKAN datastore row id for the licence record, not a business identifier; used only as record_id.
- `Licensee Business Address` — Only address.full, address.state and address.postcode are taken from this column. address.locality is deliberately not mapped: the reviewer found the street-type-suffix heuristic brittle (missed COURT, ESPLANADE, unit-numbered and street-less addresses) and it covered only ~58-60% of held-out rows. Emitting no locality leaves the value absent rather than wrong.
- `Licence Type DESC` — Human-readable form of Licence Type CODE ('Individual'/'Company'); CODE is the machine value used for entity_type, so this is deduplicated to avoid two observations of one logical field.
- `Financial Category CODE` — Code form of the licence financial category ('SCT1'); licence attribute, single-valued in the discovery partition, not an entity field.

**Held-out run:** 1101 records, 1101 produced observations; record errors {}

**Open issues (held-out validator):**
- [warning] SOME_ERRORS: 6 values rejected: {'ABN_CHECKSUM': 6} (`entity.abn`)

**Critic:** Rules 0, 2 and 3 are sound: licence number, grade and class are mapped verbatim with correct typing and null handling. Rule 1 is doubtful: 'Financial Category DESC' is a financial category attribute, not the licence category/type, so filling context.licence.category with a constant 'Self Certification - Trade' label misrepresents the licence category; the register's 'Licence Type CODE/DESC' is the more precise source and was left unmapped. No entity_type, address or validity concerns arise here because this mapping emits only licence-level context fields, but the licence category assignment should be reconsidered.
- doubtful: `context.licence.category` <- ['Financial Category DESC'] — Financial Category DESC ('Self Certification - Trade', 'SCT1') is a financial/fee category of the licence, not the licence category/type. The register also carries 'Licence Type CODE/DESC' and class/grade, which are the actual licence categories. Labelling the financial category as context.licence.category risks conflating a financial attribute with the licence type; it is at best a subordinate label, and its constant repetition across every held-out record confirms it is not the licence type.
- missed? `Licence Type CODE` -> `context.licence.category` — Licence Type CODE/DESC ('Individual'/'Company') is the publisher's licence type/category field and is a better fit for context.licence.category than Financial Category DESC, which is a financial label. Currently only used implicitly for entity_type and excluded from mapping.
- missed? `Licence Type DESC` -> `context.licence.category` — The human-readable licence type ('Individual'/'Company') is a licence-level publisher category and is a candidate for context.licence.category; it was dismissed as a duplicate of the CODE value, leaving the licence category slot filled by the financial category instead.

**Agent notes:** REVISION after review. Advertised as CSV but the resource is a CKAN datastore_search API JSON envelope (starts '{"help":'), so format=json with record_path 'result.records'. No date column exists in the records: observation.observed_at falls back to resource last-modified metadata and no valid_from/valid_to can be supplied. Fixes for the reviewer's verdicts: (1) entity.trading_name REMOVED ('wrong' verdict - a personal licensee name is not a trading name, and for companies it duplicated the legal name); (2) the suffix-based legal_name heuristic REMOVED - 'Licensee Name' is now mapped in full to entity.legal_name (coverage 100%, no suppression, no guessing), which also resolves the 'doubtful' over-suppression of individual licensees; (3) entity.entity_type now maps only 'C'->company and lets 'I' fall to the ontology default 'unknown', removing the rejected 'I'->sole_trader inference; (4) address.locality REMOVED as brittle ('doubtful'), so address output is full/state/postcode only, all of which the reviewer rated 'ok'. Retained deliberately: entity.abn and entity.acn (direct, checksum-validated source columns rated 'ok'; ABN keeps a reported ~1% checksum rejection rather than hiding it) and address.country 'AU' at reduced confidence 0.8 and flagged. Open coverage gaps for a human: entity.trading_name (no trading name exists in this source), entity.status (no status column - register membership implies current licensing but that is inferred), entity.industry_code (no ANZSIC; Licence Class Type is the nearest but non-conforming signal), address.locality (unparseable from the free-text address), and no date fields at all.

## Decision

This experimental proposal is outside the approval queue.
