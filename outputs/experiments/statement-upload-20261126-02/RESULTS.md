# Dataset ingestion results

**Completed: AGENT_VALIDATED_STATEMENT_CANDIDATE.** All four final critic batches accepted the output with no blocking findings. Exact replay passed in a separate process. Token-budget limits were disabled at both the controller and API-client layers using `--no-token-budget`.

| Measurement | Result |
|---|---:|
| Source rows / statement records | 941 / 941 |
| Source columns retained | 15 |
| Company profile candidates | 1,019 |
| New candidates / existing-profile matches | 1,017 / 2 |
| Business–statement relationships | 1,566 |
| Review items | 162 |
| Compound-name heuristic flags | 0 |
| Profiles without a confidently bound name | 49 |
| Statements without a business link | 60 |
| Recorded input / output tokens | 143,264 / 56,541 |

## What the dataset contributes

The agents inferred the column contract from the CSV. Valid ABNs identify business candidates; explicit identifiers in ReportingEntities and IncludedEntities establish their respective statement relationships. Repeated ABNs are deduplicated, while distinct ABNs remain separate business identities. Names are retained only where their binding is sufficiently clear; ambiguous spans stay in review.

Profiles retain statement history, source-reported names and roles, reporting periods, country and industry context, revenue bands, statement types, compliance labels and provenance. Revenue, country, industry and compliance facts remain statement/group-scoped; they are not asserted as exact company revenue or independently verified legal compliance. ACN/ARBN values are preserved without inventing their individual-company bindings.

For example, the candidate for **COMMERCIAL PROPERTY CLEANING PTY. LTD.**, ABN **72069158710**, is linked as an included entity to statement **2026-2165**, covering **2025-07-01 to 2026-06-30**, with a source-reported **Transparency Disclosure** label and its register URL.

## Review and verification

The inspector sampled 600 rows: 360 discovery, 127 validation and 113 test. Critic evidence included both early validation examples and structurally complex joint statements. The first review round raised a concern about missing reporting-entity information. The agent retained the same executable column contract, and all four batches accepted on recheck. Missing reporting facts were not inferred to manufacture a relationship.

All 941 full original rows were checked against the CSV, every candidate ABN passed checksum validation, and profile ABNs were unique. The sealed evidence manifest and all four accepting critic records were verified. Zero compound-name flags is a structural result, not a measured 100% precision claim. Human-labelled semantic precision remains unmeasured.

The 162 review items comprise **158 unresolved name-text entries and four invalid ABN occurrences**. Some profile candidates therefore have identifier evidence but no confidently bound name; some statements remain unlinked. Agent acceptance does not remove these limitations or constitute human approval.

## Execution notes

The run used Qwen through the authorized gateway. After repeated gateway timeouts on the final review batch, execution resumed from the saved steps with DeepSeek v4.1 Flash for that batch. Completed steps were reused during this fallback. Earlier responses and errors remain recorded. The usage ledger contains 17 entries, including four error entries; token totals cover entries with reported usage.

No token reservation stopped this run. Usage logging, schema checks, critic acceptance and bounded repair attempts remained active. No code changes were made for this upload.

## Outputs and replay

- `evaluation.json`: measured results and structural audit.
- `input-profile.json`: input counts and byte checksum.
- `run/statement_upload_20261126_02/company_profiles.jsonl`: profile candidates.
- `run/statement_upload_20261126_02/statements.jsonl`: statement facts and original rows.
- `run/statement_upload_20261126_02/relationships.jsonl`: reporting/included/association links.
- `run/statement_upload_20261126_02/review_queue.jsonl`: unresolved evidence.
- `run/`: inferred plan, agent decisions, usage ledger and sealed manifest.

```powershell
python -m firmable.evolution2 replay --output outputs/experiments/statement-upload-20261126-02/run
python -m scripts.audit_statement_run outputs/experiments/statement-upload-20261126-02/run
```

The original CSV and local registered snapshot are unchanged. Export reuse terms remain unverified, and the results remain local candidates pending human review. No website update, production promotion, commit or push was performed.
