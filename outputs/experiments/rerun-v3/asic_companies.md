# Mapping review: `asic_companies`

- **Status:** PENDING_REVIEW  (run `20261110T045414-496498`, prompt `prompts-v3`, model `deepseek-v4-flash`)
- **Dataset:** ASIC - Company Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Company Dataset - Current (ZIP), sha256 `bb7935a163292c6d…`
- **Licence:** cc-by
- **Agent effort:** 2 proposal(s), 12 tool calls, 12 model calls, 151,589 prompt + 12,903 completion tokens, 80s model time

## Final proposal (v1, digest `8178406992aeffc2`)

**Record grain:** `legal_entity` — Each row is one ASIC company registration (one ACN). Name history appears as extra rows per ACN: the row carrying Current Name Indicator='Y' holds the current registered name in 'Company Name'; other rows for that ACN hold former names in 'Company Name' and repeat the current name in 'Current Name'. ACN is the business participant identifier.

**Reader:** `{"format": "delimited", "archive_member": "COMPANY_202611.csv", "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `columns` ['ACN', 'Company Name'] — ACN alone is not unique (471 distinct in 473 discovery rows) because name-history rows repeat the ACN; ACN+Company Name is unique per row.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Company Name *when Current Name Indicator present []* | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.9 | 727 / 727 |  | Flagged row (Current Name Indicator='Y') holds the current registered name in Company Name; guarded so former names in unflagged rows are never emitted as legal |
| Current Name *when Current Name Indicator absent []* | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": [""]}) | 0.8 | 424 / 424 |  | Unflagged rows carry the current registered name in Current Name (e.g. BNP PARIBAS for BANQUE NATIONALE DE PARIS); empty -> null instead of falling back to a fo |
| ACN | `entity.acn` | acn | 0.98 | 1151 / 1151 |  | 9-digit zero-padded ACN, 100% checksum-valid on discovery and holdout. |
| ABN | `entity.abn` | null_if({"values": ["0", "00000000000"]}), abn | 0.95 | 836 / 1151 |  | 11-digit checksum-valid ABNs; sentinel '0' means no ABN. |
| Status | `entity.status` | map_enum({"mapping": {"REGD": "active", "DRGD": "deregistered", "SOFF": "deregistered", "EXAD": "in_liquidation"}, "defa | 0.85 | 1151 / 1151 |  | ASIC status codes: REGD=registered (active), DRGD=deregistered, SOFF=struck off (registration ended -> deregistered), EXAD=external administration -> in_liquida |
| Type | `entity.entity_type` | map_enum({"mapping": {"APTY": "company", "APUB": "company", "FNOS": "other", "RACN": "incorporated_association", "RNON": | 0.78 | 1151 / 1151 |  | Explicit ASIC Type codes: APTY/APUB -> company; RACN/RNON/NOAC (registrable Australian body/association) -> incorporated_association; FNOS/ARBN (foreign) -> oth |
| Date of Registration | `entity.date_registered` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.95 | 1151 / 1151 |  | dd/mm/yyyy confirmed by held-out values (30/04/1907). |
| Date of Deregistration | `observation.valid_to` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.75 | 36 / 36 |  | Deregistration date ends validity of the registration; blank -> null (still current). |

**Constants:**
- `address.country` = `AU` (conf 0.6): ASIC Australian register; most registrations are Australian, though FNOS rows may be foreign-resident - moderate confidence only.

**Deliberately unmapped:**
- `Class` — ASIC class code (LMSH=limited by shares, LMGT=limited by guarantee) describes legal form/share structure; entity_type is already driven by the explicit Type column and Class alone cannot produce one allowed value reliably.
- `Sub Class` — Fine-grained ASIC sub-class (PROP, PSTC, ULSN, LISN...); no ontology target and not a reliable entity_type signal.
- `State Registration number` — Historical state registry number, not an ABN/ACN/NZBN; no ontology target.
- `Previous State of Registration` — Prior registration jurisdiction, not the entity's current address; mapping it to address.state would present a former jurisdiction as a current address attribute.
- `Modified since last report` — Empty in discovery; operational delta flag, not an entity attribute.
- `Current Name Indicator` — Row-level flag used only in 'when' conditions to distinguish current-name rows from former-name rows.
- `Current Name` — Not a trading/display name - repeats the current registered name on name-history rows; mapped conditionally to legal_name.
- `Current Name Start Date` — Tried as observation.valid_from guarded to current-name rows; the engine requires the source present on the envelope field, so it evaluated every row as absent and emitted 0 observations. Dropped rather than mapped unreliably - it is a name-claim start date, not the entity registration's validity start.

**Held-out run:** 1151 records, 1151 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** Core identifiers (ACN, ABN with checksum, dates) are correctly mapped. Legal_name mapping is fragile: it depends on a hidden Current Name Indicator 'when' guard that isn't expressed in the mapping and is only rescued by successful per-ACN grouping of Name/Current Name columns — any row failing the guard would emit a former name as legal_name (as the held-out row literally contains). entity_type enum assignments (RACN/RNON/NOAC -> incorporated_association, FNOS -> other) are guesses beyond the explicit Type codes. address.country constant 'AU' is wrong for foreign (FNOS) registrations. No clear unmapped columns besides Class, which could strengthen entity_type.
- doubtful: `entity.legal_name` <- ['Company Name'] — Advertised as guarded to Current Name Indicator='Y' rows, but the guard isn't evidenced; in held-out records 'Company Name' holds former names (BANQUE NATIONALE DE PARIS, SEAMET LTD, THE GOVERNING BODY OF THE HOTEL LOXTON, BAILLIEU HARDIE GORMAN PTY LTD, RICHFORD PTY. LIMITED) on the very rows where the current name is in 'Current Name'. The mapping couples two sources on the same target and relies on reading either column conditionally, and the guard condition is not expressed in the mapping (only ACN row grouping disambiguates).
- doubtful: `entity.entity_type` <- ['Type'] — Uses explicit Type codes, but the enum assignment for FNOS is questionable: FNOS is a 'foreign company' and the held-out BANQUE NATIONALE DE PARIS (FNOS) is a bank, not 'other' generically — yet 'other' vs 'company' is a judgement call. More concerning, RACN/RNON/NOAC are all mapped to incorporated_association even though these ASIC codes include registrable Australian bodies (e.g. cooperatives, associations) that aren't always incorporated_association. Held-out RACN row (THE AUSTRALIAN VOLUNTEER COAST GUARD ASSOCIATION INCORPORATED) is plausible, but the blanket mapping for RNON/NOAC is a guess.
- doubtful: `address.country` <- [] — Constant 'AU' for every row, but FNOS Type (foreign company, e.g. BANQUE NATIONALE DE PARIS) is foreign-resident and the config only flags it as 'moderate confidence'; assigning AU to a foreign-registered entity contradicts the stated semantics of a business-country field.
- missed? `Class` -> `entity.entity_type` — Class codes (LMSH, LMGT, NLIA, NONE) are the definitive legal-form signal and could disambiguate company vs incorporated_association (LMGT limited-by-guarantee associations are frequently not 'company'). It was dismissed on the grounds entity_type is already Type-driven, but Class is a strong cross-check.
- missed? `State Registration number` -> `entity.acn` — While not the ACN itself, this is an historical state identifier — mapping it as a supplementary identifier with the state prefix is inappropriate for entity.acn, but the unmapped rationale is acceptable. Not a real miss.

**Agent notes:** Tab-delimited CSV inside a ZIP (tab count 14/line vs 0-2 commas). Name history = multiple rows per ACN; legal_name is guarded in both branches so former names are never emitted as current. Status SOFF->deregistered, EXAD->in_liquidation; Type FNOS/ARBN->other, RACN->incorporated_association. 'Previous State of Registration' dropped (prior jurisdiction, not address). Current Name Start Date unmapped after the engine emitted 0 rows for it as valid_from.

## Self-correction trace
- v0 -> v1: triggered by validator errors none, critic 'wrong' ['entity.status', 'address.state']
    - - removed `('Previous State of Registration',)` -> `address.state`
    - ~ changed `('Current Name',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Type',)` -> `entity.entity_type` (steps/confidence)
    - ~ changed `('Company Name',)` -> `entity.legal_name` (steps/confidence)
    - ~ changed `('Status',)` -> `entity.status` (steps/confidence)
    - ~ record_id columns -> columns ['ACN', 'Company Name']

## Decision

Approve: `python -m firmable.cli approve asic_companies --reviewer "<name>"`  
Reject:  `python -m firmable.cli approve asic_companies --reviewer "<name>" --reject --comment "why"`
