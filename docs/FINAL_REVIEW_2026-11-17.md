# Final review update — 17 November 2026

The owner asked to change the current mappings from ready for sign-off to human review verified. Eight append-only human confirmation records were added, bound to the current config and source snapshot. The seven locally revised mappings also bind interpretation dependencies. The comments retain the user's request; they do not invent a separate source-by-source review. Original AI assessments and original agent traces are preserved.

The offline replay propagated this state to observations, profiles and the website. Both API usage ledgers remain unchanged. Human link reviews remain 46 pass / 4 fail. Part 1's 20-resource checks remain AI-assisted, with no human verdicts; the mapping confirmation is not reused for a different audit.

The Write-up tab now answers Parts 1–4, followed by all six Part 5 questions and the entity-relationship model. Extra work and limitations are stated separately. `WRITEUP.md` is the concise 695-word Part 5 answer; the same text is downloadable from the website. `docs/ASSIGNMENT_ANSWERS.md` covers the other parts. One generator keeps these outputs aligned.

The Architecture tab draws three connected sequences: discovery, runtime agent onboarding with validation/revision and human verification, and deterministic extraction/matching/profile construction. The separate local-maintenance route, refusal queue and incomplete production migration controls are identified.

Cost uses recorded input/output tokens, the official DeepSeek Flash tariff checked on 17 November, UTC peak/off-peak periods and the owner's requested 25% discount. All input is conservatively priced as cache miss. Across the two ledgers, 12,637,227 input and 934,416 output tokens reprice to US$2.119500. The actual complete Mirai invoice is unknown; this estimate does not overwrite historical billing evidence. See `config/report_pricing.json` and `outputs/raw-data/evaluation/discounted_cost_report.json`.

Validation: 165 tests pass, including rate boundaries, timezone handling, cache usage, failed usage and review-binding stability. Frontend syntax checks and the production build pass. Architecture was visually inspected at 1440px and 390px; the write-up was inspected at 390px, including its cost tables. Tables scroll horizontally on narrow screens. No exhaustive interaction or accessibility audit is claimed. The earlier broad style-gate findings remain documented in `MAPPING_CORRECTIONS_VALIDATION_2026-11-17.md`; this update preserves the existing dashboard layout.

Remaining assignment limits are explicit: Part 1 human audit, four known failed links still present in proposed memberships, nested enrichment confidence, a real financial corruption replay, and complete actual-spend accounting. The later maintainer corrections are identified as an exception to the original agent-authored-config requirement.
