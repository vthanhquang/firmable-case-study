# Mapping review: `asic_companies`

- **Latest review decision:** approved by claude-code (AI assistant acting for the candidate) (ai_assistant_proxy) at 2026-11-09T20:58:45+00:00
- **Status:** PENDING_REVIEW  (run `20261110T035442-7cd099`, prompt `prompts-v2`, model `deepseek-v4-flash`)
- **Dataset:** ASIC - Company Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Company Dataset - Current (ZIP), sha256 `bb7935a163292c6d195bd2d5788863164f191198b3f29257fb332785f998bcea`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 11 tool calls, 11 model calls, 143,624 prompt + 15,837 completion tokens, 103s model time

**Current extraction:** Legacy record-level validity rules below have no effect on
claims. Check each claim's validity paths before approving.

## Final proposal (v1, digest `ccd07371fbc95e2ef95c6cc3a5b59cc6066b5252e036359089686fb5fdcb604c`)

**Record grain:** `business_name` — One row is one registered company name held by a company. Companies with previous names appear on multiple rows sharing the same ACN; on exactly one row per company 'Current Name Indicator' = 'Y' and 'Company Name' holds the current registered name, while on the other rows 'Company Name' holds a former registered name and 'Current Name' holds the then-current name. Because 'Current Name' carries a value only on the former-name rows, the current registered name is recoverable from BOTH row types: Company Name (when Indicator='Y') or Current Name (when Indicator is not 'Y'). Each row therefore yields at most one legal_name observation for the company; former registered names are NOT emitted as trading names (they are superseded legal names, not declared business/trading names). Per-company attributes (ACN, ABN, type, status, registration date) are identical across a company's rows and are mapped from every row.

**Reader:** `{"format": "delimited", "archive_member": "COMPANY_202611.csv", "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['ACN', 'Company Name'] — ACN alone is not unique (471 distinct for 473 rows) because multiple name-history rows share it; ACN + Company Name gives 473 distinct values in the discovery partition, i.e. one row per company-name record and traceable back to the source.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Company Name *when Current Name Indicator equals ['Y']* | `entity.legal_name` | collapse_whitespace, trim, null_if({"values": ["", "NONE", "."]}) | 0.9 | 716 / 716 |  | On the current-name row (Current Name Indicator='Y', 301/473 rows) 'Company Name' is the registered company name and 'Current Name' is blank. Names are space-padded to ~100 chars, hence collapse_whitespace+trim. |
| Current Name *when Current Name Indicator not_equals ['Y']* | `entity.legal_name` | collapse_whitespace, trim, null_if({"values": ["", "NONE", "."]}) | 0.85 | 411 / 411 |  | On rows without the current-name indicator, 'Current Name' is populated (172/473) and holds the company's current registered name, e.g. BRITAX STEELCRAFT PTY. LTD. -> BRITAX CHILDCARE PTY LTD. Verified on the header sample: rows where Indicator='Y' always have Current Name blank, and rows where Indicator is blank always have Current Name populated. The two legal_name rules are complementary, so each row emits exactly one legal_name and a company's current name is still recoverable if its Indicator='Y' row were absent from an extract. |
| ACN | `entity.acn` | trim, acn | 0.97 | 1127 / 1127 |  | Column 'ACN' is 9 digits on 100% of rows and passes the ACN checksum on 473/473 discovery rows; uses the acn transform, never derived from ABN. |
| ABN | `entity.abn` | trim, null_if({"values": ["", "0", "NONE"]}), abn | 0.9 | 816 / 1127 |  | Column 'ABN' is 11 digits on 69.3% of rows and passes the ABN checksum at exactly the same 69.3% rate; the remaining values are the literal placeholder '0' (145/473) meaning no ABN recorded, null_if'd away so the checksum transform only sees real ABNs. |
| Type | `entity.entity_type` | trim, map_enum({"mapping": {"APTY": "company", "APUB": "company", "FNOS": "company", "NONC": "company"}, "default": "unknown"}) | 0.8 | 1127 / 1127 |  | Column 'Type' states the ASIC company type explicitly (APTY = Australian proprietary company 458, APUB = Australian public company 15 in discovery). APTY/APUB/FNOS/NONC are all bodies registered as companies under the Corporations Act -> 'company'. Any other code falls through to 'unknown' rather than being guessed. |
| Status | `entity.status` | trim, map_enum({"mapping": {"REGD": "active", "DRGD": "deregistered"}, "default": "unknown"}) | 0.9 | 1127 / 1127 |  | Only statuses with an unambiguous ontology equivalent are mapped: REGD = registered -> active (435/473), DRGD = deregistered -> deregistered (28/473). EXAD (external administration, which may be voluntary administration or receivership rather than liquidation) and SOFF (strike-off action in progress, company still registered) have no exact enum equivalent and are deliberately mapped to 'unknown' rather than guessed. |
| Date of Registration | `entity.date_registered` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.95 | 1127 / 1127 |  | All discovery values match shape 99/99/9999 and are day-first Australian dates (e.g. 22/12/1986); parse as %d/%m/%Y. |
| Current Name Start Date *when Current Name Start Date present []* | `observation.valid_from` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.85 | 408 / 408 |  | For renamed companies 'Current Name Start Date' is when the current registered name took effect, i.e. the valid_from of the legal_name claim as stated by the source (e.g. 23/09/2002 for BRITAX CHILDCARE PTY LTD). Same day-first format (shape 99/99/9999 on all populated values). |
| Date of Registration *when Current Name Start Date absent []* | `observation.valid_from` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 719 / 719 |  | Fallback when no name-change start date is recorded: the company's registration date is when the name/registration claim became true. Complementary to the Current Name Start Date rule, so exactly one valid_from is emitted per row. |
| Date of Deregistration | `observation.valid_to` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 35 / 35 |  | Deregistration date ends the claim; present on 4% of rows (19/473), all matching 99/99/9999 and paired with DRGD status, so blank means still current. Day-first %d/%m/%Y like the other dates. |

**Constants:**
- `address.country` = `AU` (conf 0.85): Australian register of companies incorporated under the Corporations Act (ASIC); all discovery rows are AU registrations. Asserted from metadata rather than a source column, hence moderate confidence.

**Deliberately unmapped:**
- `Current Name Indicator` — Row-level flag ('Y' on the current-name row) used only as a 'when' condition to route Company Name vs Current Name into legal_name; not itself an attribute of the entity.
- `Class` — ASIC internal classification code (LMSH = limited by shares, LMGT = limited by guarantee, NONE...). It is an ASIC schema code, not an ANZSIC industry code, and the entity_type enum cannot express limited-by-shares vs limited-by-guarantee; every value here is still 'company', so mapping adds nothing and risks guessing.
- `Sub Class` — ASIC internal sub-classification (PROP, PSTC, ULSN, LISN...). No canonical target for share-structure/subclass codes; mapping it to entity_type would be a guess.
- `State Registration number` — Legacy state-registry number for companies registered before the national scheme; not an ACN or ABN (ACN checksum passes on only 13.5% by coincidence) and has no canonical target.
- `Modified since last report` — Empty on 100% of discovery rows; no data to map.
- `Previous State of Registration` — This is the jurisdiction in which the company was incorporated/registered under the old state schemes (NSW/VIC/WA/QLD/SA/TAS/...), not a business address, and 'Previous' signals the value is historical and may no longer apply. The ontology has no jurisdiction-of-incorporation target, so mapping it to address.state (a current address field) would conflate two different facts and emit a possibly stale value. Left unmapped after critic review.

**Held-out run:** 1127 records, 1127 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** All mapped fields are semantically faithful: legal_name is the registered name (not trading), ACN/ABN come from dedicated checksummed columns, entity_type and status come from explicit source columns rather than guesses, and dates are parsed day-first correctly as evidenced by valid dates. The former-name handling for legal_name is sound: Current Name (not Company Name) is used on renamed rows, and former names are not spuriously emitted as trading names. No wrong mappings found. The only debatable omission is 'Previous State of Registration', which the config deliberately excluded; it is a jurisdiction field with no clean ontology target, so its exclusion is acceptable. Overall verdict: mapping passes.
- missed? `Previous State of Registration` -> `address.state` — Source column contains the incorporation/registration state (NSW/VIC/QLD...). Ontology has address.country but no explicit state; it is a jurisdiction field and arguably maps to an address. The mapping deliberately excluded it as 'historical'; reviewer should flag it as a candidate but the exclusion rationale (no jurisdiction target, possibly stale) is defensible—list as missed-but-debatable.
- missed? `Class` -> `entity.entity_type` — LMSH/LMSG (limited by shares vs guarantee) is still 'company' under the ontology enum, so no additional target; not a true miss. No action.

**Agent notes:** ZIP member COMPANY_202611.csv: UTF-8 with BOM, TAB-delimited (14 tabs/line), one header row, 15 columns. Names are space-padded to ~100 chars -> collapse_whitespace+trim. ABN uses '0' as a missing sentinel (145/473). Name-history structure: multiple rows per ACN; legal_name comes from Company Name when Current Name Indicator='Y' and from Current Name when the indicator is blank, so each row contributes exactly one current registered name and no superseded name is emitted as trading_name (entity.trading_name is intentionally not populated - this register holds no declared business/trading names). valid_from = Current Name Start Date where present, else Date of Registration. entity.status maps only REGD/DRGD; EXAD and SOFF -> unknown by design. observed_at is not stated in the file, so resource_last_modified is used. address.full/locality/postcode are not present in this source.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.trading_name']
    - + added `('Current Name',)` -> `entity.legal_name`
    - + added `('Current Name Start Date',)` -> `observation.valid_from`
    - - removed `('Previous State of Registration',)` -> `address.state`
    - - removed `('Company Name',)` -> `entity.trading_name`
    - ~ changed `('Status',)` -> `entity.status` (steps/confidence)
    - ~ record_id columns -> columns ['ACN', 'Company Name']

## Second opinion (independent agent run)
- `history-v4`: 8/13 rules agree; **check these first:**
    - only this proposal: `('Current Name Start Date',)` -> `observation.valid_from` Current Name Start Date present []
    - only this proposal: `('Date of Registration',)` -> `observation.valid_from` Current Name Start Date absent []
    - only this proposal: `('Date of Deregistration',)` -> `observation.valid_to` 
    - only the other run: `('Previous State of Registration',)` -> `address.state` 
    - only the other run: `('Company Name',)` -> `entity.legal_name` Current Name Indicator not_equals ['Y']
- `rerun-v3`: 7/13 rules agree; **check these first:**
    - only this proposal: `('Company Name',)` -> `entity.legal_name` Current Name Indicator equals ['Y']
    - only this proposal: `('Current Name',)` -> `entity.legal_name` Current Name Indicator not_equals ['Y']
    - only this proposal: `('Current Name Start Date',)` -> `observation.valid_from` Current Name Start Date present []
    - only this proposal: `('Date of Registration',)` -> `observation.valid_from` Current Name Start Date absent []
    - only the other run: `('Company Name',)` -> `entity.legal_name` Current Name Indicator present []
    - only the other run: `('Current Name',)` -> `entity.legal_name` Current Name Indicator absent []

## Decision

Approve: `python -m firmable.cli approve asic_companies --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve asic_companies --reviewer "<name>" --reject --comment "why"`
