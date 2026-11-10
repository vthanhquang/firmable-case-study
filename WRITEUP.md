# WRITEUP — Part 5

*Numbers come from `outputs/evaluation/run_metrics.json`; model is `deepseek-v4-flash` via MiraiAPI. The hand-checks were made by the AI
assistant that built this and are provisional until the candidate confirms them (see README).*

**Headline:** 1,509 catalogue records → 50 ranked (triage false positives 7/18 decided = 39%). Seven sources were onboarded by the agent,
including one it had never seen, with no code change. 38,032 observations. 649 links at threshold 0.85, **precision 48/50 = 96%**
(Wilson 95% interval 86–99%); a looser band scored 0/25. 50 profiles, 9 with conflicts. **≈ $0.12 to onboard a typical source; ≈ $9.20 in total (under the $10 budget, mostly experiments and revisions).**

## 1. Cost
- **The price is measured.** The provider's billing counter vs my token ledger gives **$1.57 per 1M tokens** over 2.6M tokens
  (individual windows ranged 1.57–1.67; input and output cost the same).
- **One-time cost per source:** 54k–261k tokens, **median 75k ≈ $0.12**. That's $0.09 for ATO (accepted first time) up to $0.41 for QBCC
  (a revision, 16 calls). Median wall clock is 51 s, with 5 logical stages (9 when revised). 92% of tokens are prompt tokens: the tool loop re-sends history, plus ~2k proxy overhead per call.
- **Per-record model cost is $0.** Extraction, matching and profiles are deterministic. The whole downstream pipeline,
  including two passes over the 4.46M-row ASIC file, runs in about 2 minutes on a laptop (4 minutes with downloads).
- **Whole project ≈ $9.20 (5.83M tokens).** Unscoped one-rule revisions were the most wasteful part (long contexts, repeated rounds);
  `--only` scoping fixed that. That includes development, every rejection-driven revision, a 7-source stability re-run (≈ $1.83)
  and the follow-up experiments. The production-relevant number is the per-source one above.

## 2. Agent design
- **Steps.** The controller owns state; the model acts only through tools scoped to one snapshot:
  1. Byte inspection.
  2. A tool loop on a discovery split (`try_reader`, `profile_columns`, `get_ontology`, `list_transforms`, `dry_run`, `submit_mapping`).
     Every submission passes a static gate first: real ontology paths and columns, checksum transforms on identifiers, no guessed enum defaults.
  3. **Held-out validation:** the engine runs on rows the agent never saw. Gates: ≤5% errors per field, coverage, key uniqueness, no placeholder values.
     The held-out set includes one row per value of every low-cardinality column.
  4. **Critic:** a separate call reads held-out raw rows next to the output and judges *meaning*, e.g. legal vs trading name, a person used as a business, a licence number used as an identifier.
  5. Up to 2 revisions, then a review page and a human decision; a rejection comment is fed back to the agent.
- **Self-correction happened.** ASIC: the critic flagged `Current Name`→trading_name and registration state→address; both were removed.
  QBCC: a person mapped as trading_name was removed. ACNC: a non-unique key became a content hash. The unseen credit source: a mixed
  ABN/ACN column was split by length and checksum. Each case is shown on its `outputs/reviews/*.md` page.
- **What the human sees:** one page per source. It shows licence and hash, reader settings and grain; per field, the transforms, confidence and held-out counts and errors;
  every unmapped column with a reason; the critic's doubts; the v0→vN diff with its trigger; and a **second opinion**, the rules an independent run
  disagreed with. Approval is append-only and bound to the config digest, and extraction refuses any digest without one.
- **Failure handling.** Every stage and every agent turn is checkpointed, and `--resume` continues from the last one. It was used for real
  when a re-run hung on a tool (a quadratic bug, since fixed and tested). Sources are isolated, tool errors go back to the model as typed results,
  and quota stops end a run cleanly. **Prompt injection:** on a register with planted instructions in a header and in cells, the live agent followed
  none of them and said so (`prompt_injection_test.json`). Approval isn't a model tool in any case.
- **The weakest step is semantic judgement at the edges, and it's measured.**
  - (a) While revising, the agent invented `map_enum default:"__PASSTHROUGH__"`. Every held-out row was Australian, so nothing exposed it; the reviewer
    caught it. After the fixes (unknown arguments rejected, rare-value rows added), the critic flags that config *wrong* on a real `"Australia."` row.
  - (b) Re-validating the approved configs under the new gates, plus spot-checking outputs, found 3 more placeholder escapes ("TBA", ".",
    "[NOT APPLICABLE] -"). Each was revised by the agent. Asked for a one-rule fix, the agent repeatedly **expanded scope unasked** (postal addresses into
    premises fields; a country default that erased foreign countries). So narrow edits are now enforced by the controller (`--only <targets>`), not
    requested in the prompt. After every round the links were byte-identical.
  - (c) **Repeatability:** an independent re-run of all 7 sources gave readers 7/7 and **ABN/ACN rules 7/7** identical. But QBCC moved company names to
    trading_name, and the credit source mapped licence status onto entity status, with the critic only "doubtful". General prompt rules (a holder's name is a
    legal name; licence status isn't entity status), re-measured twice: QBCC identical 2/2, status mapping 0/2. One run then guessed entity_type
    from name suffixes, which now fails a deterministic gate taken from the ontology ("default to unknown"). Structure is reliable; semantics need the human,
    which is why each review page lists second-opinion disagreements.

## 3. The hard one
- **ASIC Company Dataset.** The format traps were easy (a ZIP whose `.csv` member is tab-delimited, padded names, `0` meaning no ABN). The *shape*
  resisted: it's a name-**history** file. `Company Name` is the current name only when `Current Name Indicator = Y`; otherwise the current name is in
  `Current Name`. The agent's v1 said plainly that "the engine has no row filter or conditional target", which was true of my DSL.
- **How I decide between DSL and custom code.** A general shape gets a DSL feature, because row-conditional meaning appears in every history-style file.
  One publisher's quirk that config can't express gets custom code. So I added `when` conditions, and the same agent, with no hints, wrote complementary
  current-name rules. Former names were still dropped, so I added per-rule validity columns. In an experiment the agent used them unprompted:
  +424 dated historical names on held-out rows (`outputs/experiments/history-v4/`). This isn't promoted, since it would change the audited extraction, and it still has a flaw:
  the current name's `valid_from` is the registration date.
- **Runner-up: QBCC.** It's behind a bot challenge, and the API fallback stopped at 32k of its 195k rows: a biased prefix with ACNs on 7% of rows vs 23% overall.
  Paging fixed access, and the approved config ran **unchanged** on all 195k rows (15 s, gates pass). QBCC also produces the only linking errors.

## 4. Scale: 6 → 500 sources
- **Access fails first.** 3 of 9 Part-2 resources and 9 of 20 triage-audit resources were unreachable (403, 404, bot challenge). A column-reading
  triage ranker could read only 38 of 150 headers and showed no measurable gain (6/18 vs 7/18 false positives). Build the access layer first:
  API fallbacks, pagination, politeness, a queue of blocked sources, and atomic, hash-verified downloads. A transient failure here once
  left an empty file that crashed extraction downstream; it now fails loudly at `fetch`.
- **Then human review.** The agent costs about $0.12 and a minute per source; a reviewer needs 5–10 minutes. Order the queue by risk (identifiers, enums,
  second-opinion disagreements) and auto-pass unchanged digests. The model bill isn't the problem: 500 × $0.12 ≈ $60.
- **Then the DSL's long tail** (every new shape exposed a gap: `when`, passthrough, validity dates) and **throughput**: all approved configs ran over their
  full resources (~4.6M rows, worst field error 0.9%, no gate failures) at ~10k rows/s serially. Two-phase partitioned extraction (parallel base keys, in-order
  duplicate numbering, parallel emission) reproduced all 29.5M ASIC observations **identically** in 108 s instead of 464 s (`parallel_extraction_equivalence.json`).
- **Then identity.** In-memory exact-key blocking (blocks over 50 records skipped) moves to an index with incremental candidates.

## 5. Change: a better matcher, millions of old links
- **What must already be recorded (this repo records it):** every *decision*, not just links. `link_decisions.jsonl` holds
  LINK/REVIEW/ABSTAIN/REJECT/NON_MATCH with evidence, rule, score and `policy_version`. Every observation carries `extractor_version`
  (engine + config digest). Membership is derived from decisions, with keys anchored on ABN/ACN and unique per cluster.
- **I ran the procedure.** Precision by rule was ABN-equal 31/33 and registered-name 17/17: the "strongest" evidence held both errors,
  because they're about record grain (a person holding a company's ABN). **strict-v2** sends that pattern to REVIEW. A shadow run over all
  3,025 stored pairs changed **5 decisions** and split **5 clusters**, so only those need review; I checked all 5 and every one was right. It also exposed
  a bug, now fixed: a split-off record inherited the company's key. Promotion means switching `policy_version` (rollback is a pointer flip), and only
  affected profiles are rebuilt: measured at **5 of 478**. Human overrides are their own policy version. In a split, the side with the anchor keeps the key and the other gets a new key plus an alias.

## 6. Next (three weeks)
1. A labelled gold set (mapping fields and entity pairs), so confidence is calibrated rather than asserted.
2. The access layer, which is the first thing to fail.
3. Turn critic verdicts into deterministic gates where possible; run gate re-validation on a schedule; require a second opinion on contested rules.
4. Drift: a schema fingerprint per snapshot, with re-validation only when the shape is unchanged.
5. Promote strict-v2. Split `date_registered` by registrar: 7 of the 9 profile conflicts are ASIC vs ACNC registration (2012-12-03 is when the ACNC started), which are different facts.

## Entity relationships (Part 3 model)
- **Assumption tested:** name-only links assume a registered company name is unique. Over all 4.0M current ASIC names, 0.1% are held by
  more than one ACN. No current link uses one of those, and strict-v2 refuses name-only links on them (`config/ambiguous_company_names.json`).
- **Identity is a log of decisions; entities are derived.** The stored fact is a pairwise decision between source records. Clusters form from accepted
  decisions under one hard rule: no cluster may hold two different valid ABNs or ACNs, so chains of weak links can't merge registered entities.
  Not ABN-only keys, because licence and site records often lack an ABN, and keys must survive a matcher change.
- **Relationships between businesses are typed edges that never merge:** `SAME_NAME_DIFFERENT_IDENTIFIER`, `HOLDS_LICENCE` and
  `OPERATES_ESTABLISHMENT`. **I left parent/subsidiary alone:** no source states it, and inferring it from names is the guessed link the brief warns against.
