# Mapping review: `vic_liquor`

- **Status:** PENDING_REVIEW  (run `20261112T155049-bcb246`, prompt `prompts-v9-profile-context-v1`, model `deepseek-v4-flash`)
- **Dataset:** Victorian liquor licences by location — Liquor Control Victoria
- **Resource:** August 2026 (XLSX), sha256 `b0a00e0846f430dc3eb2bc32fde3e4136caa9142c60d127e8c1419fbc34fb36e`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 5 tool calls, 9 model calls, 80,727 prompt + 5,869 completion tokens, 118s model time

## Final proposal (v0, digest `86278470175e7ba1ae974d3520e25bd19fbd579f18bdcc8d436a2e1263a98027`)

**Record grain:** `licence_or_permit` — One record is one current Victorian liquor licence (one licence number) held at one premises. The business participant is the licensee; its legal name, trading name and premises address are mapped as attributes of the licence holder, not of the licence itself. Licence Number is the licence's own ID, so it is not used as a business identifier.

**Reader:** `{"format": "xlsx", "archive_member": null, "encoding": "utf-8-sig", "delimiter": null, "skip_rows": 4, "sheet": "Current_Victorian_Licences_By_L", "record_path": null}`

**Record id:** `columns` ['Licence Number'] — Licence Number is present on 100% of rows and has 465 distinct values in 465 discovery records, so it is unique per record and traceable.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Licensee | `entity.legal_name` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "n/a", "na", "not applicable", "[not applicable] -"]}) | 0.82 | 1168 / 1168 |  | Column headed 'Licensee' - a licence is issued to a legal person, so this is the registered legal name of the holder. Values look like registered entity names (ALDI FOODS PTY LIMITED, ENDEAVOUR GROUP LIMITED, CITY OF DAREBIN), with some sole traders (WOOD GERARD). Placeholder nulls added defensively; none were observed here. |
| Trading As | `entity.trading_name` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "n/a", "na", "not applicable", "none", "nil"]}) | 0.9 | 1159 / 1161 |  | Explicitly a trading-as/business name column, distinct from the licensee (ALDI FOODS PTY LIMITED -> ALDI STORES). Held-out records contained a bare '.' placeholder, which is nulled rather than emitted. |
| Street Address | `address.full` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "n/a", "na", "not applicable"]}) | 0.85 | 1112 / 1113 |  | Street address of the licensed premises (not the postal address), paired with Suburb/Postcode columns. Held-out records contained a bare '-' placeholder, which is nulled rather than emitted. |
| Suburb | `address.locality` | trim, collapse_whitespace, null_if({"values": ["", "-", ".", "n/a", "na", "not applicable", "[not applicable] -", "[not applicable]-"]}) | 0.85 | 1111 / 1123 |  | Locality of the premises address row. The discovery profile showed 7 rows shaped '[a a] -' i.e. '[NOT APPLICABLE] -' markers (case varies in the source: '[Not applicable] -'); these are placeholders for licences with no fixed premises locality and are nulled. |
| Postcode | `address.postcode` | trim, null_if({"values": ["", "0", "-", ".", "n/a", "na", "not applicable"]}), postcode | 0.8 | 1111 / 1124 |  | 4-digit premises postcode. A handful of rows contain '0' (7 of 465) which is a placeholder, not a postcode, so it is nulled. |
| Licence Number | `context.licence.number` | trim, null_if({"values": ["", "N/A", "NOT APPLICABLE", "-"]}) | 0.95 | 1169 / 1169 |  | Publisher licence number, unique per licence record (465 distinct, 8-digit). |
| Licence Category | `context.licence.category` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NOT APPLICABLE"]}) | 0.92 | 1169 / 1169 |  | Licence category in Liquor Control Victoria's own terms; kept verbatim. |
| Trading Hours | `context.licence.trading_hours` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NOT APPLICABLE"]}) | 0.8 | 1169 / 1169 |  | Trading-hours condition stated for this licence, preserved as published. |
| Patron Capacity (if applicable) | `context.licence.patron_capacity` | null_if({"values": ["", "N/A", "NOT APPLICABLE", "-"]}), parse_integer | 0.88 | 643 / 643 |  | Numeric patron capacity; blank for ~40% of rows so missing stays distinct from zero. |
| Council | `context.licence.council` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NOT APPLICABLE", "-"]}) | 0.85 | 1114 / 1126 |  | Local council of the licensed premises, in publisher wording. |
| Region | `context.licence.region` | trim, collapse_whitespace, null_if({"values": ["", "N/A", "NOT APPLICABLE"]}) | 0.85 | 1126 / 1126 |  | Publisher's licensing region (11 values such as Metro North, Hume). |

**Constants:**
- `address.state` = `VIC` (conf 0.9): Victorian liquor licence register published by Liquor Control Victoria; every premises is in Victoria.
- `address.country` = `AU` (conf 0.9): Victorian (Australian) licensing register.

**Deliberately unmapped:**
- `Metro/Regional` — Geographic classifier for the licence area; no ontology target.
- `Latitude` — Coordinates; no ontology target.
- `Longitude` — Coordinates; no ontology target.
- `Postal Address` — Postal address of the licensee, not the premises address; mapping it too would conflict with the premises address claimed by address.full.
- `Postal Suburb` — Part of the postal (correspondence) address, not the premises locality.
- `Postal Postcode` — Part of the postal (correspondence) address, not the premises postcode; also contains interstate postcodes (e.g. 2000 NSW).
- `column_7` — Empty spacer column in the sheet.
- `column_8` — Empty spacer column in the sheet.
- `column_13` — Empty spacer column in the sheet.
- `column_14` — Empty spacer column in the sheet.

**Held-out run:** 1169 records, 1169 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is essentially sound: all six licence-scoped fields target appropriate ontology paths, values are preserved verbatim where the ontology asks for publisher terminology, blanks are nulled rather than emitted, and licence number is correctly treated as the licence's own ID. The one substantive weakness is rule 2: 'Trading Hours' is frequently just an echo of the licence category (BYO Permit, Producer's Licence, Pre-retail Licence, Limited Licence), so those rows carry a category name in a trading-hours field, which is misleading condition data. The postal address/suburb/postcode being left unmapped is defensible since the dataset distinguishes correspondence address from premises address. Metro/Regional, latitude/longitude, and spacer columns have no ontology target, so no important source columns were left unmapped.
- doubtful: `context.licence.trading_hours` <- ['Trading Hours'] — Trading Hours is a licence condition, but in many held-out rows it merely repeats the category ('BYO Permit', 'Producer's Licence', 'Pre-retail Licence', 'Limited Licence'), so it is not actually trading hours. Copying it into context.licence.trading_hours produces false condition data (a category name in a hours field) rather than a null. Valid for rows like 'Trading to 5am'/'Ordinary', but the rule should suppress the category-echo values.

**Agent notes:** Single sheet 'Current_Victorian_Licences_By_L'; rows 1-3 are publisher contact block, a title ('Current Victorian Liquor Licences as of 31/08/2026') and a blank line, so header is row 5 -> skip_rows 4. No ABN/ACN columns exist, so none are mapped (Licence Number is 8 digits and fails both checksums - it is not an ACN). The snapshot date 31/08/2026 appears only in the title text, not as a per-record column, so observed_at falls back to resource_last_modified. Status of the licence is not mapped to entity.status: the sheet lists current licences, which says nothing about the entity's registered status. Revision: null_if placeholder lists were widened on entity.legal_name, entity.trading_name, address.full, address.locality and address.postcode after held-out records emitted '.', '-', and '[NOT APPLICABLE] -' markers.

## Decision

This experimental proposal is outside the approval queue.
