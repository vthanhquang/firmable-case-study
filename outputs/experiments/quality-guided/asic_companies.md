# Mapping review: `asic_companies`

- **Status:** PENDING_REVIEW  (run `20261112T014654-0456a0`, prompt `prompts-v8`, model `deepseek-v4-flash`)
- **Dataset:** ASIC - Company Dataset — Australian Securities and Investments Commission (ASIC)
- **Resource:** Company Dataset - Current (ZIP), sha256 `bb7935a163292c6d195bd2d5788863164f191198b3f29257fb332785f998bcea`
- **Licence:** cc-by
- **Agent effort:** 1 proposal(s), 10 tool calls, 10 model calls, 121,136 prompt + 15,610 completion tokens, 401s model time

## Final proposal (v0, digest `c22b623648ac17cafbdcb51488ae11248566022297dc002bf794f6cd84e34118`)

**Record grain:** `legal_entity` — Each row is one name record for an ASIC-registered company. Companies with a former name get two rows: a history row (Current Name Indicator blank, holding the former name in 'Company Name' and the present name in 'Current Name') and a current row (indicator Y, holding the current name in 'Company Name'). All rows sharing an ACN describe the same legal entity; the file is the company register extract itself, so the record's subject is the legal entity, not a licence, site or contract.

**Reader:** `{"format": "delimited", "archive_member": "COMPANY_202611.csv", "encoding": "utf-8-sig", "delimiter": "\t", "skip_rows": 0, "sheet": null, "record_path": null}`

**Record id:** `content_hash` ['ACN', 'Company Name', 'Current Name Indicator'] — ACN alone is not unique per row (471 distinct ACNs over 473 discovery rows) because former-name history rows repeat it. Hashing ACN + the row's own name + the current-name flag separates a history row from its current row while keeping the record traceable to the register entry.

**observed_at:** `{"source_path": null, "steps": [], "fallback": "resource_last_modified"}`

| source column(s) | canonical target | transforms | conf. | held-out emitted / present | errors | rationale |
|---|---|---|---|---|---|---|
| Company Name *when Current Name Indicator equals ['Y']* | `entity.legal_name` | trim, collapse_whitespace | 0.93 | 732 / 732 |  | Publisher help file: Company Name is the current name when Current Name Indicator is Y. Registered names are padded to a fixed width with trailing spaces; trim/collapse_whitespace cleans the 100-char padding seen in the sample. |
| Company Name *when Current Name Indicator absent []* | `entity.legal_name` | trim, collapse_whitespace | 0.8 | 431 / 431 |  | On history rows (indicator blank) Company Name is a former registered name, evidenced by the paired indicator-Y row whose 'Current Name' column repeats it (e.g. LOVINI HOLDINGS PTY LTD / MONAKA PTY LTD, ACN 000000019). No dates attached: the Current Name Start Date on these rows dates the CURRENT name, and the publisher states the extract does not establish when each former name stopped being valid. |
| Current Name *when Current Name Indicator absent []* | `entity.legal_name` | trim, collapse_whitespace, valid_from from Current Name Start Date | 0.85 | 431 / 431 |  | Publisher help file: on a history row the separate Current Name column contains the current name, and Current Name Start Date dates that current name. This row is the only place a dated current-name claim exists, so it carries the valid_from; the value duplicates (does not contradict) the indicator-Y row's current name. |
| ACN | `entity.acn` | acn | 0.97 | 1163 / 1163 |  | ACN column is 9 digits on 100% of rows with an acn checksum-valid rate of 1.0 over the discovery partition. |
| ABN | `entity.abn` | null_if({"values": ["0", "00000000000"]}), abn | 0.9 | 844 / 1163 |  | ABN is 11 digits with a 0.693 checksum-valid rate; every one of the 145 invalid values is the literal '0', which the publisher documents as a missing value. null_if removes the sentinel before the checksum-validating abn transform, leaving 328 of 473 rows with a real ABN. |
| Type | `entity.entity_type` | map_enum({"mapping": {"APTY": "company", "APUB": "company"}, "default": "unknown", "passthrough": false}) | 0.75 | 1163 / 1163 |  | Only two type codes occur in discovery: APTY (Australian proprietary company, 458 rows) and APUB (Australian public company, 15 rows) — both explicitly companies, so the source states the business form. Rare codes elsewhere in the file are left to the default 'unknown' rather than guessed. |
| Status | `entity.status` | map_enum({"mapping": {"REGD": "active", "DRGD": "deregistered", "SOFF": "active"}, "default": "unknown", "passthrough": false}) | 0.68 | 1163 / 1163 |  | Publisher: REGD = registered, DRGD = deregistered, SOFF = strike-off action in progress, EXAD covers both receivership and liquidation. REGD->active and DRGD->deregistered are unambiguous. SOFF->active because a company under strike-off action is still registered until struck off. EXAD is deliberately NOT mapped: the code pools receivership with liquidation, so no single canonical value is defensible for every EXAD record, and the publisher warns a coarse status must hold for all records bearing a code. It falls to 'unknown' (6/473 discovery rows). |
| Date of Registration | `entity.date_registered` | parse_date({"formats": ["%d/%m/%Y"]}) | 0.9 | 1163 / 1163 |  | All 473 discovery values match dd/mm/yyyy; publisher confirms day-first company registration event dates. claim_scope is company_registration because this is ASIC's company registration event, not any other registration. |
| Previous State of Registration | `address.state` | trim, state | 0.4 | 1161 / 1161 |  | Values are standard AU state abbreviations (NSW/VIC/WA/QLD/SA/TAS/ACT/NT plus a few padded). Caveat: this column is the jurisdiction of the company's earlier state-level registration, not a current street, office or contact address, so it is mapped as a coarse jurisdiction only, with low confidence; no locality/postcode/street data exists in this extract. |

**Constants:**
- `address.country` = `AU` (conf 0.6): ASIC is Australia's national companies register, so every record is an Australian-jurisdiction registration; moderate rather than high confidence because the full file also carries foreign registrations (Type FNOS).

**Deliberately unmapped:**
- `Class` — ASIC class code (LMSH = limited by shares, LMGT = limited by guarantee, NONE). The ontology has no company-class target and this is not entity.entity_type.
- `Sub Class` — ASIC sub-class code (PROP, PSTC, ULSN, LISN ...). No ontology target; a raw code table rather than a business attribute.
- `Date of Deregistration` — A company event date with no ontology target (entity.status already conveys the deregistered state, and the guidance forbids attaching a valid_to to a deregistered status). Present on only 4% of rows.
- `State Registration number` — Historical state-registry number (mixed alphanumeric with padding, e.g. C0268163E). Not an ABN, ACN or NZBN, and the ontology accepts identifier targets only for those checksummed schemes.
- `Modified since last report` — Completely empty in discovery (present_rate 0.0); an extract-diff flag, not a data claim.
- `Current Name Indicator` — Row-role flag used in the 'when' conditions that separate former from current name rows; not an entity attribute itself.
- `Current Name Start Date` — Consumed as valid_from on the dated current-name rule rather than emitted as a standalone entity field.

**Held-out run:** 1163 records, 1163 produced observations; record errors {}

**Open issues (held-out validator):**
- none

**Critic:** The mapping is largely faithful. Current versus former names are separated correctly using the Current Name Indicator, and the former name is not dated, which is right. ACN and ABN handling, including the '0' missing-value sentinel and checksum validation, is correct. The Type-to-entity_type mapping and the Status mapping, including the decision to leave EXAD unmapped, are defensible. The date order for Date of Registration is correct. The concerns are: (1) Previous State of Registration is a historical registration jurisdiction, not a premises or entity address, yet it is emitted as address.state without qualification (doubtful); (2) the constant address.country AU is asserted unconditionally despite the acknowledged possibility of foreign-aspect entity types (doubtful); and (3) the Current Name rule emits a dated current-name claim that duplicates the indicator-Y current-name row, so it needs deduplication and must not be read as bounding the former name (doubtful). No trading-name, contact-name, or licence-number mis-typing was found in these held-out records.
- doubtful: `entity.legal_name` <- ['Current Name'] — The Current Name column on a history row indeed holds the current name, and Current Name Start Date is defensible as its valid_from, since the publisher states the date dates the current name. But this rule emits a second current-name claim for the same entity that duplicates the indicator-Y row, so downstream deduplication is needed. Worse, the same Current Name Start Date cannot also bound the former name, and the row's own Company Name is a former name. The dated current-name claim is arguably better sourced from the Y row plus this date; as written the rule is only tenable if the duplication is consciously deduplicated. So the verdict is doubtful rather than wrong.
- doubtful: `address.state` <- ['Previous State of Registration'] — The values are valid AU state codes, and the rationale admits the caveat, but Previous State of Registration is the company's earlier state-level registration jurisdiction, not an entity address. Mapping it to address.state without any evidence that the entity's address is in that state is an agency-jurisdiction-to-record-address confusion. It is defensible only if claim_scope or provenance marks it as historical jurisdiction rather than a current address; as emitted it looks like a premises/entity address claim.
- doubtful: `address.country` <- [] — A constant AU country is reasonable for an ASIC company extract, but the rationale itself concedes the full file carries foreign registrations such as Type FNOS. Emitting address.country AU unconditionally would then be wrong for those records.
- missed? `Date of Deregistration` -> `entity.status (supporting evidence), or a deregistration event date if the ontology allowed one` — The value exists on DRGD rows (e.g. COMMONWEALTH PORTLAND CEMENT, 13/03/2026) and corroborates the deregistered status. It correctly must not be used as valid_to on a deregistered status, but the mapping offers no date-bearing target even where the ontology might want an event date.
- missed? `Class` -> `none available (entity_type is a business-form enum; LMSH/LMGT are liability classes)` — Correctly left unmapped, since the ontology lacks a company-class target; noting it only to confirm no precision loss for entity_type.
- missed? `State Registration number` -> `none (no ontology identifier target for state registration numbers)` — Correctly left unmapped: it is a legacy state-registry number, not an ABN or ACN, and the ontology accepts no other identifier scheme.

**Agent notes:** Reader settings come from evidence: the ZIP's single member is tab-delimited (14 tabs per line, 0-2 commas per line from commas inside company names), utf-8-sig, header on line 1, no title rows. Names arrive padded to ~100 characters, so trim+collapse_whitespace is applied everywhere a name is emitted. Two-row name structure means an ACN appears twice for renamed companies; content_hash keeps the history and current rows distinct and traceable. ABN '0' is a documented missing sentinel. Status: EXAD is left unknown on purpose (pooled receivership/liquidation code). address.state reflects a historical registration jurisdiction, not a contact address — there is no street/locality/postcode data in this extract. observed_at falls back to resource last-modified because no statement date column exists.

## Decision

This experimental proposal is outside the approval queue.
