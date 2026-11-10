# Mapping review: `asic_companies`

- **Status:** PENDING_REVIEW  (run `20261110T051809-73fedf`, prompt `prompts-v4`, model `deepseek-v4-flash`)
- **Dataset:** ASIC - Company Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Company Dataset - Current (ZIP), sha256 `bb7935a163292c6d…`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 8 tool calls, 7 model calls, 66,968 prompt + 8,379 completion tokens, 59s model time

## Final proposal (v0, digest `f81b01e9c570f8a4`)

**Record grain:** `business_name` — Each record is one registered (or former) company name of an ASIC-registered body, identified by its ACN. A company whose name has changed appears as its current record (Current Name Indicator = Y, Company Name = the current registered name) plus one or more former-name records (Current Name Indicator blank, Company Name = the former name, Current Name = the name it was changed to, Current Name Start Date = when the new name took effect). All records for an ACN therefore describe the same legal entity; the entity attribute mapped from Company Name is a name claim whose validity ends when the name was superseded.

**Reader:** `{"format": "delimited", "archive_member": "COMPANY_202611.csv", "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['ACN', 'Company Name'] — ACN alone repeats across name-history rows (471 distinct ACNs in 473 discovery records), so the ACN + the name on the row identifies one record uniquely; name columns are trimmed first.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Company Name *when Current Name Indicator equals ['Y']* | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.85 | 727 / 727 |  | ASIC's registered company name (the name on the ASIC register), flagged as the current name by Current Name Indicator=Y. Validity starts at the registration dat |
| Company Name *when Current Name Indicator not_equals ['Y']* | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.7 | 424 / 424 |  | Historical registered name: rows without the current-name flag carry a former name, and Current Name Start Date gives the date the successor name took effect, i |
| Current Name *when Current Name Indicator not_equals ['Y']* | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.7 | 424 / 424 |  | Current Name on a former-name row states the name the company adopted on Current Name Start Date; emitting it with valid_from = that date records the successor  |
| ACN | `entity.acn` | trim, acn | 0.95 | 1151 / 1151 |  | ASIC ACN column, 9 digits in all sampled rows and 100% checksum-valid on the discovery partition. |
| ABN | `entity.abn` | trim, null_if({"values": ["", "0"]}), abn | 0.9 | 836 / 1151 |  | ASIC ABN column; 11-digit checksum-valid for populated values, and the placeholder '0' (145 rows) means no ABN recorded, so it is nulled before the abn transfor |
| Type | `entity.entity_type` | trim, upper, map_enum({"mapping": {"APTY": "company", "APUB": "company", "FNOS": "other", "RACN": "incorporated_associat | 0.65 | 1151 / 1151 |  | Type states the ASIC body type explicitly: APTY = Australian proprietary company and APUB = Australian public company (both -> company), which are the only valu |
| Status | `entity.status` | trim, upper, map_enum({"mapping": {"REGD": "active", "DRGD": "deregistered", "EXAD": "in_liquidation", "SOFF": "deregist | 0.75 | 1151 / 1151 |  | ASIC status codes observed: REGD (registered -> active), DRGD (deregistered), EXAD (external administration -> nearest allowed value in_liquidation), SOFF (stru |
| Date of Registration | `entity.date_registered` | trim, parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1151 / 1151 |  | dd/mm/yyyy dates (day-first: e.g. 22/12/1986, 30/04/1907). |
| Previous State of Registration | `address.state` | trim, state | 0.55 | 1149 / 1149 |  | The state in which the body was registered (ASIC 'Previous State of Registration'); a jurisdiction attribute, not a current street address. Normalised through t |

**Constants:**
- `address.country` = `AU` (conf 0.8): Source is the ASIC Australian company register, so the registration jurisdiction is Australia. Low-moderate: the dataset also contains a few foreign-registered bodies (Type FNOS), for which AU is the registering country rather than the entity's home country.

**Deliberately unmapped:**
- `Class` — ASIC class code (LMSH limited by shares, LMGT limited by guarantee) has no ontology target; it is not needed to determine entity_type (Type is sufficient) so it is left unmapped rather than folded into a combined field.
- `Sub Class` — ASIC sub-class code (PROP proprietary, PSTC public non-listed, ULSN/ULST/LISN/LIST etc.) has no ontology target; it is not an ANZSIC industry code and not a clean sole_trader/trust signal.
- `State Registration number` — State-level registration number for the body; not an ABN/ACN/NZBN and has no ontology target (its digits partially pass the ACN checksum by chance only).
- `Date of Deregistration` — Would date the end of registration, but the ontology has no slot for registration end; deregistration status already flows to entity.status, and using it as record valid_to would wrongly terminate the legal_name/ACN claims. Left out to avoid over-claiming.
- `Modified since last report` — Empty in every discovery record; no information.
- `Current Name Indicator` — Row-level flag used as a condition to distinguish current from former names; not an entity attribute itself.
- `Current Name Start Date` — Used only as the validity date for the name claims (valid_from of Current Name / valid_to of Company Name); not an entity attribute.
- `Current Name` — Mapped (see fields) only under the former-name condition; it is a name claim of the same legal entity, not a trading name.

**Held-out run:** 1151 records, 1151 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Core identifier mappings (legal_name from Company Name and Current Name history, ACN, ABN with placeholder handling, date_registered day-first, status codes) are sound. Main concerns: entity_type collapses several heterogeneous non-company ASIC codes to 'other' by guess (doubtful, especially ARBN/ACNC/QLCS), address.state is really registration jurisdiction rather than a postal/premises address state (doubtful), and the constant address.country=AU is wrong for foreign bodies. Date of Deregistration was discarded though it is a strong explicit deregistration signal that should feed status.
- doubtful: `entity.entity_type` <- ['Type'] — APTY/APUB -> company and RACN -> incorporated_association are defensible explicit code mappings. But mapping multiple foreign/other codes (FNOS, ARBN, ITDN, NOAC, ACNC, QLCS, ADFA) all to 'other' by guess is risky; some (e.g. ACNC/QLCS are registered bodies, ARBN is a foreign company registration) may really be company/incorporated_association or unknown. Default-to-unknown is fine; the non-company codes should not be silently collapsed to 'other' without evidence.
- doubtful: `address.state` <- ['Previous State of Registration'] — This is the state of registration jurisdiction, not a current business/premises address state. Mapping it to address.state conflates registration jurisdiction with address; the rationale acknowledges it is not a street address but the target semantics (address.state) are still a stretch. Values (NSW, SA, VIC, QLD) normalise correctly though, and one row with empty value correctly emits nothing.
- doubtful: `address.country` <- [] — Constant AU is reasonable for an ASIC register but wrong for foreign-registered bodies (e.g. BANQUE NATIONALE DE PARIS, Type FNOS) where AU is the registration country not the entity's country. The mapping itself concedes this.
- missed? `Date of Deregistration` -> `entity.status` — Population of this column is a direct, explicit signal of deregistration and should override/strengthen status; the rationale's concern about valid_to is valid but the value should still feed status rather than being wholly discarded.
- missed? `Class` -> `entity.entity_type` — LMGT (limited by guarantee) vs LMSH (limited by shares) is a useful corroborating signal; NLIA on SEAMET LTD indicates no-liability company, which may warrant 'other'/company disambiguation rather than ignoring. At minimum it is evidence for entity_type.
- missed? `Status` -> `entity.status` — Already mapped, but EXAD could be surfaced with the raw code recorded rather than only approximated as in_liquidation.

**Agent notes:** Tab-delimited CSV inside the ZIP (COMPANY_202611.csv), utf-8-sig. Name columns are space-padded in the raw data, hence trim/collapse_whitespace. One legal entity usually appears as 1-2 rows (current name + former name(s)); dedupe downstream on ACN. Type codes beyond APTY/APUB/FNOS were not observed in the discovery partition and are best guesses; unrecognised types default to unknown.

## Decision

Approve: `python -m firmable.cli approve asic_companies --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve asic_companies --reviewer "<name>" --reject --comment "why"`
