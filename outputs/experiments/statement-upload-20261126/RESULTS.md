# Dataset ingestion results

**Status: NEEDS_REVIEW. No profiles were accepted or promoted to production.**

The uploaded Modern Slavery Register CSV contains 941 statement rows and 15 columns. The inspector selected a 600-row sample (360 discovery, 127 validation, 113 test). The routing agent inferred the statement/business column contract without a supplied mapping configuration. It retained revenue, industry, country, reporting period and compliance labels as statement-level evidence, and used explicit ABNs to build company candidates and reporting/included relationships.

## Candidate preview

| Item | Count |
|---|---:|
| Statements | 941 |
| Profile candidates | 1,019 |
| New candidates / exact matches to existing profiles | 1,017 / 2 |
| Business–statement relationships | 1,566 |
| Unresolved name-text entries | 158 |
| Invalid ABN occurrences | 4 |
| Total review items | 162 |
| Profiles without a confidently bound name | 49 |

After the controller stopped, its recorded model-generated plan was executed offline to save these **unapproved** previews in `candidate-preview/`. This required no additional model calls. The mapping decision and existing-profile snapshot are retained there. Repeating candidate extraction produced identical outputs. All 941 full source rows were verified against the input CSV. This repeatability check is not semantic precision or final pipeline acceptance.

## Why the run stopped

One critic batch requested changes to how ambiguous name text is presented in the review queue: queue entries contain unresolved spans rather than the entire original entity-name cell. Full original cells are preserved in statement `raw_record` data, so inspection does not establish that source data was lost. The criticism concerns reviewer context and reconciliation between name claims, unresolved fragments and original cells. The recorded critique also questioned whether the parsed/unparsed split was complementary; that judgment remains unresolved rather than silently overridden.

The routing agent kept the same executable mapping in the revision round. Before all review batches could be accepted, the controller stopped because the next request could not fit its 200,000-token reservation budget. Recorded usage was **109,989 input tokens and 48,555 output tokens across 10 ledger calls**. Conservative reservation includes room for the next prompt and response, so stopping can occur before the nominal token ceiling is fully consumed.

The sealed controller result remains `NEEDS_REVIEW`. Its verification checks the integrity of that failed/incomplete outcome; it is not a successful accepted-profile replay. No human-labelled semantic precision was measured.

## Example

The source row for COMMERCIAL PROPERTY CLEANING PTY. LTD. explicitly binds ABN `72069158710` to the included-entity role in statement `2026-2165`, with reporting period `2025-07-01` to `2026-06-30` and a source-reported `Transparency Disclosure` label. Statement facts and provenance are retained with the profile candidate. That label is not treated as independently verified legal compliance. Different ABNs in joint statements remain separate business identities linked to the same statement.

## Files

- `input-profile.json`: input shape, counts and checksum.
- `evaluation.json`: controller status, candidate counts, usage and critic decisions.
- `run/`: sealed agent responses, generated plans, validation records and usage ledger.
- `candidate-preview/company_profiles.jsonl`: unapproved company candidates.
- `candidate-preview/statements.jsonl`: statement facts and complete raw rows.
- `candidate-preview/relationships.jsonl`: business-to-statement links.
- `candidate-preview/review_queue.jsonl`: unresolved names and identifiers.
- `candidate-preview/mapping-origin.json`: exact model decision used for the preview.

The original CSV is unchanged. Source export reuse terms remain unverified; the run is local. No website update, production promotion, commit or push was performed.
