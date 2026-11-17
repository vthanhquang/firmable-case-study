# Firmable Case Study website

The demo opens on the latest raw-data replay, with searchable human-reviewed mappings, proposed links, and company profiles. Each results tab links to the earlier benchmark. The Discovery tab shows the saved Part 1 audit, with a CKAN response and up to 50 publisher rows per sample.

Run from this directory with Node.js 22 or later.

```powershell
npm start
```

Open [the local site](http://127.0.0.1:4173). Run `npm run build` to generate the static site in `dist/`.

After a completed `raw-replay` run, regenerate the demo data with `npm run sync-demo`. The exporter verifies the saved mapping digests, run IDs, observation counts, link audit, and change totals before producing browser snapshots. It publishes aggregate contact counts and keeps direct contact values and coordinates out of the replay demo.

The snapshots in `data/` are enough to run and build the site. From the repository root, run `python frontend/scripts/capture-discovery.py` to refresh the saved publisher excerpts and replay the catalogue rules. Then run `npm --prefix frontend run sync-data` to build the site data from the latest discovery audit and the quality replay. The capture uses the project's Python dependencies, saved source snapshots, and public publisher URLs.

The earlier benchmark shows the agent's supplemental `context.*` rules and its original 50-company sample. Run `python frontend/scripts/sync-profile-context.py` from the repository root to rebuild that context before syncing the benchmark. Pass `--refresh-registry` to reopen ABN Lookup.

Replay the Part 1 category ranking and bind the archived audit to its new order from the repository root.

```powershell
python -m firmable.discovery.quality outputs/discovery/category_ranked --candidates 1509 --reuse-candidates outputs/discovery/evidence_ranked/candidates.jsonl
python -m firmable.discovery.quality_audit carry-forward outputs/discovery/category_ranked outputs/discovery/category_ranked/audit --previous outputs/discovery/evidence_ranked
```

The latest link audit displays evidence-bound decisions from `outputs/raw-data/evaluation/link_review_decisions.jsonl`. AI and human reviews are stored separately and identified in the UI and CSV export. These decisions survive regeneration of the blank audit sample; changed link evidence invalidates the previous decision. Run `python -m pytest -q tests/test_raw_audit_review.py` and `node --test frontend/tests/source-pairs.test.mjs` to check review persistence and graph counts.

Mapping assessments are separate from human approvals. Part 2 reads `outputs/raw-data/evaluation/mapping_review_decisions.jsonl`, showing findings and recommendations bound to the config, snapshot, observations, engine and crosswalk dependencies. Changed evidence invalidates an old assessment. The detailed review is in `docs/MAPPING_REVIEW_2026-11-17.md`; replay evidence can be regenerated with `python outputs/requirements-review/review_mapping_evidence.py`.

## Submission reports

The repository includes [Part 5](../WRITEUP.md), a [standalone HTML report](../reports/assignment-report.html), and the full [two-page PDF](../output/pdf/firmable-writeup.pdf) with [Overleaf source](../output/pdf/firmable-writeup.tex). The HTML opens directly without a server. Follow the root [README](../README.md) for the verified clean-checkout replay.
