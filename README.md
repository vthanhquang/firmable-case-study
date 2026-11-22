# Firmable case study

An agentic ingestion pipeline for Australian business data: catalogue discovery → multi-step mapping agent → generic extraction → conservative entity linking → company profiles.

Start with the **[HTML report](reports/assignment-report.html)** (download/open locally), the **[two-page PDF](output/pdf/firmable-writeup.pdf)**, or [all answers in Markdown](docs/ASSIGNMENT_ANSWERS.md). The required **[WRITEUP.md](WRITEUP.md) contains Part 5**; the brief requires it as a separate file, so the README links to it rather than duplicating it. [LaTeX source](output/pdf/firmable-writeup.tex) is self-contained and compiles in Overleaf with pdfLaTeX. The HTML includes Parts 1–5 and the architecture diagram, with no server, JavaScript or external assets required.

## Run from a clean checkout in under 10 minutes

Prerequisites: **Python 3.11+**, and **Node.js 22+ only for the interactive website**. Run commands from the repository root. Dependency installation needs internet access; the frozen replay, tests and reports need **no API key, model calls or publisher downloads**.

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/submission.py prepare
.venv\Scripts\python.exe -m firmable.cli raw-replay --sync-demo
.venv\Scripts\python.exe scripts/submission.py verify
.venv\Scripts\python.exe -m pytest -q
```

macOS / Linux:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/submission.py prepare
.venv/bin/python -m firmable.cli raw-replay --sync-demo
.venv/bin/python scripts/submission.py verify
.venv/bin/python -m pytest -q
```

`prepare` restores hash-verified publisher samples into ignored `data/`, refusing to overwrite different files. `raw-replay` rebuilds observations, links, profiles, change events, metrics and website data. It disables model access and verifies that both historical token ledgers remain unchanged. It does **not** rerun inference. Ingestion timestamps change on replay; decisions remain bound to their source evidence. One optional full-resource parallel-extraction test skips without the original QBCC download.

Expected verification: **50 shortlisted datasets, 8 extracts, 85,446 observations, 1,455 proposed links, 1,245 unlinked records, 50 profiles and 50 audited links**. The audit has **46 correct / 50 = 92% at threshold 0.85**. The Part 1 human-confirmed audit has **0 / 20 false positives**. These are sample results, not population accuracy estimates.

Verified from a fresh checkout and Python 3.11 environment: **about 126 seconds after dependency installation; 169 tests passed, one optional test skipped**. Links, queue and profiles reproduced byte-for-byte. See [validation details](docs/SUBMISSION_VALIDATION.md). GitHub Actions also runs the offline workflow on Ubuntu.

### Interactive website

```bash
npm --prefix frontend start
```

Open **http://127.0.0.1:4173**. No npm dependencies or installation are needed. The site includes discovery previews, mapping coverage, source-link graphs, review evidence, searchable profiles, the write-up and architecture. Checked-in snapshots work before running the Python pipeline.

```bash
npm --prefix frontend run check
node --test frontend/tests/source-pairs.test.mjs
npm --prefix frontend run build
```

The static build is written to `frontend/dist/`. Use the Node server for the interactive site; opening its `index.html` directly cannot load JSON reliably. For a standalone file, use `reports/assignment-report.html` instead.

## Submission outputs

The final report and default website use **`outputs/raw-data/`**. The original six-source benchmark remains under `outputs/mappings/`, `outputs/observations/`, `outputs/identity/` and `outputs/profiles/`; it is historical evidence, not the final replay.

| Required item | Final artifact / evidence |
| --- | --- |
| Ranked shortlist of 50 from 1,509 catalogue records | [shortlist.csv](outputs/discovery/category_ranked/shortlist.csv); [catalogue pool](outputs/discovery/catalogue_pool.jsonl) |
| Part 1 random audit of 20 | [audit CSV](outputs/discovery/category_ranked/audit/audit_20.csv), [metrics](outputs/discovery/category_ranked/audit/metrics.json), [human confirmation](outputs/discovery/category_ranked/audit/human-review-confirmation.json) |
| Six mapping configs, plus two extensions | [final mappings and approval journals](outputs/raw-data/mappings/); [original agent configs](outputs/mappings/) |
| Canonical observations, one claim per row | [observations](outputs/raw-data/observations/) — one JSONL per source, plus sample metadata |
| Proposed links with records, canonical key, confidence and evidence | [proposed_links.jsonl](outputs/raw-data/identity/proposed_links.jsonl) |
| Deliberate refusals and reasons | [unlinked_queue.jsonl](outputs/raw-data/identity/unlinked_queue.jsonl) |
| 50 company profiles | [company_profiles_v3_50.jsonl](outputs/raw-data/profiles/company_profiles_v3_50.jsonl) |
| Precision hand-check material | [50-link sample](outputs/raw-data/evaluation/link_audit_strict_v3_raw_50.csv), [evidence-bound review journal](outputs/raw-data/evaluation/link_review_decisions.jsonl), [joined human labels and notes](frontend/data/raw-link-audit.csv) |
| Human mapping review | [review pages](outputs/raw-data/reviews/), [findings](docs/MAPPING_REVIEW_2026-11-17.md), [corrections](docs/MAPPING_CORRECTIONS_2026-11-17.md); each mapping has an `.approvals.jsonl` journal |
| Agent steps, validation, critic and revisions | [runs/](runs/) — per-source state, messages and events; [unseen-source pilot](outputs/experiments/live-sor-pilot/) |
| Source deletion / corruption analysis | [deletion impact](outputs/raw-data/evaluation/source_deletion_impact_v3.json), [financial corruption](outputs/raw-data/evaluation/financial_corruption_v3.json) |
| Part 5 write-up | [WRITEUP.md](WRITEUP.md) |
| Full report and diagram | [HTML](reports/assignment-report.html), [Markdown](docs/ASSIGNMENT_ANSWERS.md), [PDF](output/pdf/firmable-writeup.pdf), [LaTeX](output/pdf/firmable-writeup.tex), [architecture SVG](frontend/public/system-architecture.svg) |
| Offline inputs, hashes and attribution | [fixture manifest](fixtures/replay/manifest.json), [data notices](DATA_NOTICES.md) |

The original six sources are ASIC companies, ACNC charities, ATO corporate tax transparency, QBCC licensees, Victorian liquor licences and DEWR employment-service providers. They span ZIP/TSV, CSV, XLSX and JSON. ASIC credit licensees and an earlier ATO reporting year extend the final replay to eight extracts across seven dataset families. **736 of the 1,455 final links are between the original six sources.** The 50-link precision sample covers the extended replay; it is not a separate six-source precision estimate.

## What is agentic, and what is deterministic?

Part 2 uses one controller and one mapping contract. The agent inspects bytes, tries readers, profiles columns, consults the ontology, proposes mappings and dry-runs them. Static gates and held-out rows test the proposal, a critic checks semantics, and bounded revisions feed findings back to the model. Checkpoints retain proposals, validation, tool calls and failures. Human review shows the rules, transformations, confidence, samples, unmapped columns and critic findings before digest-bound approval.

Measured ASIC onboarding example: **9 recorded stage transitions, 15 tool calls, 2 proposals, 282,603 input / 30,424 output tokens and 15m 25s wall time** (about US$0.0606 at the declared estimate rates). Its trace is `runs/asic_companies/20261112T204647-23688e/`.

The same `firmable/mapping/engine.py` executes every source config. Reader settings and transformations are configuration, not separate source parsers. Parts 3–4 are deterministic over Part 2 observations: constrained clusters with canonical keys, evidence-based abstention, typed site/licence/programme relationships, then per-field merging with provenance and losing values. Mapping confidence, source reliability and link confidence remain distinct; they are policy scores, not calibrated probabilities. Unsupported ownership relationships are withheld.

**Mapping authorship exception:** initial configs and extension proposals were produced by the agent. Seven final extension configs were subsequently corrected locally without further model calls, at the project owner's request, then human-confirmed. This does not fully meet the brief's preference for exclusively agent-generated configs. Original proposals, exact correction bundles and lineage remain available; corrected mappings are not presented as untouched agent output.

## Run the agent on a new source (optional, paid)

The default client uses the **direct DeepSeek API**, `DEEPSEEK_API_KEY`, endpoint `https://api.deepseek.com`, model `deepseek-flash`. [DeepSeek's API documentation](https://api-docs.deepseek.com/) identifies this as the current model name; saved runs retain their historical requested name, `deepseek-v4-flash`. Thinking mode is disabled explicitly so ordinary tool-call transcripts can be replayed. Override endpoint, model and critic using `FIRMABLE_BASE_URL`, `FIRMABLE_MODEL` and `FIRMABLE_CRITIC_MODEL`.

Set your own key in the current terminal. **No credential is included.** `.env.example` documents settings; the CLI does not automatically load `.env` files.

```powershell
$env:DEEPSEEK_API_KEY="your-own-deepseek-key"
$env:FIRMABLE_USAGE_LEDGER="outputs/experiments/new-run/usage.jsonl"
$env:FIRMABLE_TOTAL_TOKEN_BUDGET="1000000"
```

On macOS/Linux use `export DEEPSEEK_API_KEY="your-own-deepseek-key"` and `export` for the same optional variables. Activate the virtual environment or substitute its Python path below.

```bash
python -m firmable.cli register-source new_register ./register.xlsx --title "Business register" --publisher "Publisher" --licence CC-BY-4.0
python -m firmable.cli onboard new_register
python -m firmable.cli review new_register --interactive
python -m firmable.cli extract new_register
```

Use the source's actual licence; the value above is an example. Extraction requires approval of the current mapping. Resume an interrupted run with `python -m firmable.cli onboard new_register --resume RUN_ID`. Revise after rejection with `python -m firmable.cli onboard new_register --feedback "review findings"`. Normal inference has a 350,000-token run budget; retries and resumes are logged. Live inference is not part of the ten-minute offline check and may exceed that time. The direct-client contract is tested with mocked HTTP; no new paid DeepSeek call was made for submission preparation.

To reconstruct the original downloaded benchmark, `python -m firmable.cli fetch` verifies snapshot hashes. Live publisher files can change or fail; this is why the submission includes frozen sampled rows. Original full resources are not all bundled, so full-resource re-inference needs downloads or a newly registered file.

## Follow-up: autonomous ontology experiment

The CSO follow-up adds **three previously unused government sources**: AusTender contract notices, Brisbane grant recipients and National Pollutant Inventory facilities. Four model roles inspect source bytes, propose ontology additions, generate mappings and critique validation results. The existing shared extractor executes their configs. Candidate ontologies are versioned; new profile facets are projected generically; production promotion requires explicit human review. The original assignment results remain separate.

The development run accepted all three after revisions/resumes: **37 new concepts, 18,516 observations and 12 proposed exact-ABN links**. Sealed tests had 0/3,616 type/constraint errors; four invalid NPI identifier values were rejected across the full sample. This is not human-measured semantic precision, and it was not three first-pass successes. Grant recipients remain unresolved as companies; production is not promoted.

- [System design, agent roles, source selection and limitations](docs/autonomous-ontology.md)
- [Standalone HTML experiment report](reports/autonomous-ontology.html) — download/open locally, or serve the repository with `python -m http.server 8000` and visit `/reports/autonomous-ontology.html`.
- [Measured experiment results](outputs/experiments/autonomous-ontology/RESULTS.md)
- [Recorded model responses, frozen samples, mappings and registry versions](outputs/experiments/autonomous-ontology/run/)

```bash
python -m firmable.evolution replay
python scripts/build_evolution_report.py
```

Replay needs no model key and makes no API calls. Live onboarding is optional and paid; follow the design document for download/registration and `run --live` commands. This experiment's type/constraint validation is not a new human-measured semantic precision result. Agent review is labelled as agent review.

## Known limitations

- **Four audited links are wrong and remain in the proposed output**, visibly labelled failed in the review material. They are not silently removed to inflate precision. Sampling is stratified and enriched for cross-source overlap; the 92% result does not estimate population precision or recall.
- Final mappings read **116 of 168 source columns**. Unsupported columns and draft semantic crosswalks remain explicit. There is no complete-coverage claim.
- Core and financial fields retain resolved confidence, provenance and alternatives. Nested establishment/licence fields retain observation references but do **not yet have complete merged field-confidence objects**.
- QBCC's original sample came from a biased first 32,000-row prefix; the full register check is retained separately. Source access encountered HTTP errors and bot challenges. The frozen replay avoids these dependencies, not their sampling limitations.
- All 25 financially populated profiles depend on ATO. Deleting ASIC affects 26/50 profiles; 210 field entries disappear, 10 values change and 20 profiles lose multi-source support. Confidence-only changes are excluded from those counts.
- Some historical configs fail gates introduced later. Use the final replay instructions above; old experiment reports and pending-review messages describe the state when written, while current approval journals determine final status.
- Direct-API inference may differ from historical outputs. Complete historical billing is unknown. The report's **US$2.46** is an estimate for 12,637,227 input and 934,416 output tokens at the declared off-peak rates, including logged experiments/retries; chat assistance and infrastructure costs are excluded.
- Frozen source files contain public-register information, including entries concerning natural persons. Personal contact observations are withheld from profiles; public availability does not remove licence or privacy obligations. See [DATA_NOTICES.md](DATA_NOTICES.md).

## Rebuild reports and check the Git submission

```bash
python frontend/scripts/build-assignment-writeup.py
python scripts/build_html_report.py
python frontend/scripts/build-writeup-latex.py
python scripts/submission.py scan
```

Compile `output/pdf/firmable-writeup.tex` with pdfLaTeX/Overleaf to refresh the PDF; LaTeX is not needed to run the pipeline. Reports and the two-page PDF are already included. `scan` checks tracked plus non-ignored files for API-key/private-key patterns and credential files. Submit this Git repository; no ZIP is required. Local credentials, full downloads, caches, build output and scratch backups are ignored. Agent and review evidence is committed.

## Code map

| Component | Entry points |
| --- | --- |
| Discovery and row-evidence scoring | `firmable/discovery/` |
| Agent controller, tools, review and checkpoints | `firmable/agent/` |
| Shared readers, mapping contract, transforms, validation | `firmable/sources/`, `firmable/mapping/` |
| Final extraction, matching, profiles and audits | `firmable/rawdata/` |
| Offline replay and correction lineage | `firmable/rawdata/maintenance.py` |
| Ontology, policies, crosswalks and publisher evidence | `firmable_ontology.yaml`, `config/` |
| CLI | `python -m firmable.cli --help` |
| Website and shared report prose | `frontend/` |
| Submission preparation, verification and secret scan | `scripts/submission.py` |
