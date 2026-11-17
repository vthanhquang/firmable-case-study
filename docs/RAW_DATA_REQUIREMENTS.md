# Raw-data opportunities: requirements tracker

Source: the review *Getting More Out of the Raw Source Files* (12 Nov 2026, `RAW_DATA_OPPORTUNITIES.md`).
Each requirement cites the section it comes from. What was built is in
[RAW_DATA_IMPLEMENTATION.md](RAW_DATA_IMPLEMENTATION.md); measured numbers are in
`outputs/raw-data/evaluation/raw_data_metrics.json`.

The case study's rules hold throughout (review §1, §5):
- every value stays a claim from a source, with provenance;
- the **agent** writes the mapping configs and a **human** approves them. No AI approvals were added: every
  extension proposal is `PENDING_REVIEW`, and every extension observation says `approval_state: pending_human_review`;
- the audited baseline (approved configs, strict-v2 links, profile-v1/v2) is untouched. The new work runs as a
  separate pipeline under `outputs/raw-data/` until a human promotes it.

Status: **done** = built, tested and run on the real sources; **done (pending review)** = built and run, but the
mapping or crosswalk it relies on still needs a human decision; **partial** = see the note.

| # | Requirement | Review § | Status | Evidence / note |
|---|---|---|---|---|
| R1 | Raw row store keyed by `(source_id, snapshot_sha256, source_record_id)`; configs replay over stored rows | 5.1 | done | `firmable/rawdata/store.py`; `data/rawstore/` (gitignored, rebuilt by `raw-store`); extraction reads only stored rows |
| R2 | Extension registry beside the core ontology | 5.2 | done (pending review) | `config/ontology_extensions.yaml` (5 families, 41 concepts, typed, with qualifiers, crosswalk and personal-data flags); concept definitions are a draft for human approval |
| R3 | One row → several entities, with relationships | 5.3 | done | `entities` / `relationships` in the mapping DSL; the engine emits `entity_role`, a snapshot-stable `entity_ref` and edges. Used by the agent for VIC (licence + premises), QBCC and credit (licence), DEWR (site) |
| R4 | Human-reviewed crosswalk tables referenced by name | 5.4 | done (pending review) | 12 tables in `config/crosswalks/`, each `review_status: draft`. ASIC code lists are complete for the 4.46M-row file; the QBCC band table covers the 14 categories of the full 195k register. VIC table revised to v2 after the critic found errors |
| R5 | Gates for new concepts | 5.5, 2.2 | done | `extension_issues`, `list_issues`, extended `UNSUPPORTED_FORMER_NAME_END`; re-running today's gates over the approved configs flags exactly the ACNC trading-name problem (`outputs/evaluation/revalidation_current_gates.json`) |
| R6 | Agent re-maps every source against the registry | 1, 5.4 | done (pending review) | 8 proposals under `outputs/raw-data/mappings/`, review pages under `outputs/raw-data/reviews/`. Reviewer feedback (from this review) went through the reject → revise loop for QBCC, credit, DEWR, VIC and ACNC; where the critic disagreed with the feedback, the agent's critic-backed choice stands and is documented |
| R7 | ASIC: former names, status detail (distress), legal form, class / sub-class, deregistration date not as record validity | 2.2, 3.1 | done (pending review) | ASIC proposal; the legacy record-level validity rules are removed; former names carry no unsupported end date (new gate). The agent did not add a dated "deregistered" status rule |
| R8 | New matching evidence | 4.1 | done | `firmable/rawdata/match.py`: domain, phone, geo ≤ 100 m, former name (exact and suffix-stem), explicit holder kind; ambiguous domains/phones and register-reused former names never link |
| R9 | Challenger matcher compared with strict-v2; audit sample for human labels | 4.1, 8 | done (labels pending) | `outputs/raw-data/identity/summary.json` (comparison on identical observations), `outputs/raw-data/evaluation/link_audit_strict_v3_raw_50.csv` (blank labels) |
| R10 | Relationships | 4.4 | done | `outputs/raw-data/identity/relationships.jsonl`: HOLDS_LICENCE, OPERATES_ESTABLISHMENT, LICENCE_AT_ESTABLISHMENT, DELIVERS_PROGRAM_FOR, TRUSTEE_OF / TRUSTEE_NAMED, LICENSED_INDIVIDUAL_FOR, SAME_GROUP_CANDIDATE |
| R11 | Profile-v3 with firmographics, establishments, licences, contact points, three date fields | 4.2, 4.1 | done | `outputs/raw-data/profiles/company_profiles_v3_50.jsonl` (+ all multi-source); premises/site addresses are establishments, not the business address |
| R12 | Change signals | 4.3 | done | `firmable/rawdata/changes.py`; real second QBCC snapshot (live register, 12 Nov) diffed on licence numbers; revenue year-on-year from ATO 2023-24 vs 2024-25 |
| R13 | Privacy | 6 | done | personal mailboxes dropped in the transform, mobiles flagged and withheld, personal values masked in everything sent to the model, no profile for an individual licence holder |
| R14 | Licence title, URL and attribution on every observation | 6 | done | `config/licences.yaml` (from CKAN package_show), `licence_detail` on every observation the engine emits |
| R15 | Related datasets through the same agent | 7 | partial | ATO 2023-24 onboarded end to end (base mapping + extension, both pending review). ABN Bulk Extract, ACNC AIS, ASIC business names and AFS licensees are assessed in the implementation doc, not onboarded |
| R16 | Measurement | 8 | done | `outputs/raw-data/evaluation/raw_data_metrics.json`, `source_deletion_impact_v3.json`, `financial_corruption_v3.json`, `change_events_summary.json` |
| R17 | Documentation | — | done | this tracker, `RAW_DATA_IMPLEMENTATION.md`, README section, review pages |

## What still needs a human

1. Approve or reject each extension mapping: `python -m firmable.cli raw-approve <source> --reviewer "<name>"`.
2. Review the crosswalk tables (`config/crosswalks/*.yaml`); several entries are marked `verified: false`.
3. Approve the extension concept definitions (`config/ontology_extensions.yaml`).
4. Label the 50-link challenger audit (`outputs/raw-data/evaluation/link_audit_strict_v3_raw_50.csv`).
5. Approve the ATO 2023-24 base mapping (`outputs/reviews/ato_tax_transparency_2023_24.md`).
