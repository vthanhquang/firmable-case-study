# Dataset onboarding replay — implementation review

The demo follows one selected dataset through seven stages. It replays saved executions for IP Australia, ACNC and WGEA; it does not upload a new dataset or start a live model run. Each stage identifies its responsible component and exposes its input and output. Agent acceptance, technical validation, human approval and production integration remain separate.

## Deliverables and verification

| Requirement | Implementation and evidence |
| --- | --- |
| Existing website and portable HTML | `/?part=onboarding` and `reports/dataset-onboarding.html`; the build copies the latter unchanged into `frontend/dist/`. Both use one renderer and dataset export. All five local routes returned HTTP 200. |
| Three real source examples | Dataset selection for IP Australia, ACNC and WGEA. Export tests compare saved samples, test measurements, groups, review contracts and model usage with the experiment artifacts. |
| Source inspection | Metadata, licence links, 50 frozen sample records, column-group selector, ten-row pagination, row grain, preserved headers and evidence partitions. These are sampled rows, not necessarily consecutive publisher rows. |
| Join evidence | IP join keys, constraints, scanned/matched counts and original table lineage. ACNC/WGEA explicitly state that no multi-table join ran. |
| Planning and ontology | Clickable entity topology, recorded role rationale, concept owner/search filters, reuse/proposal states, definitions, qualifiers and explicit omissions. |
| Revision evidence | 52 saved attempts across the three examples, with execution findings, critic responses, token usage, mapping downloads and rule-level before/after changes. |
| Evaluation and human review | Withheld-test measurements, business-question checks, unresolved groups, review contracts and downloadable CSVs with blank human verdict/reviewer/timing fields. Synthetic review-memory tests are labelled as synthetic. |
| Profile impact | Six source-record examples per dataset, 504 inspectable claims, field provenance and existing-profile comparison where a source ABN actually overlaps. No overlap is presented as an approved identity merge. |
| Read-only operation | No API requests or review writes in the renderer. Production additions remain zero. Standalone execution is tested without a fetch API or a writable history API. |
| Navigation and interaction | DOM checks exercise all 21 dataset/stage combinations, dataset changes, next/previous/restart, preview pagination, ontology filters, all saved attempts, review filters, provenance buttons and six evidence/review downloads. |
| Responsive presentation | Browser screenshots inspected at 1440, 1024, 768 and 390 pixels. The added navigation originally overflowed at 768; wrapping the header fixed it, and the repeated screenshot reported no sideways page scroll. Wide data tables and graphs retain their own scroll regions. |
| Credentials and repository state | Repository secret scan passed for 4,755 files. No credentials were added, and no commit or push was performed. |

## Repeat the checks

From the repository root, with the project's Python dependencies installed:

```bash
python scripts/build_onboarding_demo.py
python -m pytest tests/test_onboarding_demo.py -q
npm --prefix frontend run check
npm --prefix frontend run build
```

The five Python tests check evidence fidelity, profile provenance, revision diffs, contact redaction, and standalone data/renderer integrity. They passed. JavaScript syntax checks and the static build passed.

Optional interaction checks use a DOM implementation installed only under ignored scratch space; the demo itself has no new npm dependency:

```bash
npm install --prefix tmp/onboarding-ui-test --no-save --package-lock=false linkedom@0.18.15
node tests/onboarding_ui.mjs
```

The interaction test passed: 21 stage renders, 52 attempts, 504 claims and six downloads. It also executes the standalone HTML script with a `file:` URL and restricted history. Linkedom lacks a native writable select implementation and layout; the harness supplies selection behavior and does not claim to replace a real browser. Browser screenshots independently cover layout.

## Scope and limits

This is a recorded experiment explorer. There is no live-ingestion progress simulation, automatic ontology approval, production merge, new human precision measurement or estimated human review time. Full historical samples and candidate outputs remain available in the experiment folders. The standalone page embeds its data and scripts and loads no remote assets; publisher links open only when selected.

The existing paper/green palette and Inter/system-font stack were retained. This is an evidence dashboard with navigable stages and scrollable tables, rather than a marketing landing page with full-screen sections, photography or animation scenes. No illustrative company facts, coined brands, stock photographs, contact forms or assumed business metrics were introduced.

The automated design-gate results are recorded below separately from functional and evidence verification.

## Automated design gate

GATE: OPEN 36 (rounds used up). Three rounds completed. No waivers were submitted. This is not a design-gate pass.

The generic checker treats the interactive dashboard as a marketing hero. Its full-screen section, limited-action, heading-size, card-edge and photographic/motion requirements do not match the requested existing dashboard. Its table cut/overlap warnings refer to offscreen cells in bounded scroll regions; the inspected screenshots show the regions containing them. Privacy/sample labels are deliberate evidence disclosures. The genuine SVG focus-outline issue was fixed, as was the tablet navigation overflow found by screenshot checking.

Every remaining gate finding is preserved below; no finding was hidden from the checker.

| Check | Location | Finding |
| --- | --- | --- |
| sample-label | article#ob-stage-content > section.ob-block:nth-of-type(2) > p.ob-note "Natural-person IP names and direct conta" | a note that the page's names or figures are examples ("names and direct contact details are withheld in t"): it reads as an apology and undercuts every claim |
| cut-text | table.ob-table > tbody > tr:nth-of-type(9) > td:nth-of-type(1) "9" | runs past the edge of its box article#ob-stage-content > section.ob-block:nth-of-type(2) > div > div.ob-table-scroll (and 7 more like it: "patent", "2016219949", "o318204", "—", ...) |
| cut-text | table.ob-table > tbody > tr:nth-of-type(9) > td:nth-of-type(9) "the feinstein institute for medical rese" | 1 of 2 lines hidden by the overflow of article#ob-stage-content > section.ob-block:nth-of-type(2) > div > div.ob-table-scroll |
| no-visual | div#onboarding "Dataset onboarding" | no picture, effect or mock in this section; a feature section needs a visual |
| copy-actions | section.ob-block:nth-of-type(2) > div > div.ob-pager > button.ob-button.ob-secondary:nth-of-type(2) "Next rows" | 5 actions in the hero ("Download evidence", "Previous rows", "Next rows", "Open review stage", "Download review queue"); at most 2 |
| heading-scale | article#ob-stage-content > div.ob-stage-heading > div > h2 "Dataset arrives" | h2 headings in 2 sizes, 18px ("Human review requirement") to 25px (x1.39) |
| heading-scale | div.ob-shell > div.ob-summary > div.ob-stat:nth-of-type(1) > strong "11,592" | the figure "11,592" is set at 32px, larger than the section headings (h2 25px); 2 more like it |
| off-grid | article#ob-stage-content > details.ob-disclosure > summary "Step input and output" | left edge at 84.5px, 12.5px off the page margin at 72px (26 elements, like p.ob-agent); 1 more in this section off the grid too (p.ob-note at 571px) |
| moment-none | (the page) | a software page (--type) deals no moment: every kind carries one, two on a long page (moments.md) |
| hero-screen | div#onboarding "Research extension · Recorded executionD" | the hero ends at 1983px on a 900px screen, 1083px below the fold: it ends at the fold, 1px either way (SR-1) |
| section-height | footer.wrap.footer "Recorded experiments · No API key or con" | the section is 63px tall (0.1 screens), 837px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2) |
| section-height | div#onboarding "Research extension · Recorded executionD" | the section starts at 73px, 73px below the screen grid (0 x 900px): sections start on whole screens (SR-2) |
| one-section | footer.wrap.footer "Recorded experiments · No API key or con" | the screen at scroll 1146px (the top of section 2) shows 63px of section 2 beside section 1: a screen shows one section (another may peek 8px, 24px WARN) (SR-4) |
| one-section | div#onboarding "Research extension · Recorded executionD" | a <div> sits directly in <main>: every part of <main> is a <section> (SR-4) |
| one-heading | article#ob-stage-content > div.ob-stage-heading > div > h2 "Dataset arrives" | the hero holds an h2 (2): its heading is the h1, and an h2 opens the next section (SR-5) |
| container-edges | a.skip-link "Skip to content" | a <a> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6) |
| container-edges | header.site-header "FirmableDataset onboardingSelf-contained" | a <header> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6) |
| container-edges | footer.wrap.footer "Recorded experiments · No API key or con" | a <footer> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (and 2 more like it: "Research extension · Rec", "Recorded experiments · N") (SR-6) |
| container-edges | div.ob-shell > div.ob-summary > div.ob-stat:nth-of-type(1) > p.ob-note:nth-of-type(1) "Extracted observations" | 3 text blocks start on a left line at x 93, 21px from the container's left: text starts on the container's left, or on one split line (x 622, 732, 842) (also "11,592", "Recorded candidate output") (SR-6) |
| container-edges | article#ob-stage-content > details.ob-disclosure "Step input and outputInputPublisher meta" | a box over half the container wide runs 72-1076px, not on the container's lines at 72-1368px (SR-6) |
| container-edges | article#ob-stage-content > section.ob-block:nth-of-type(2) > label.ob-select > select "Identity previewparty identityparty role" | a box over half the container wide runs 72-1076px, not on the container's lines at 72-1368px (SR-6) |
| container-edges | article#ob-stage-content > section.ob-block:nth-of-type(2) > div > div.ob-table-scroll "Frozen source row previewSource rowparty" | a box over half the container wide runs 72-1076px, not on the container's lines at 72-1368px (and 1 more like it: "← Previous stage1 / 7Nex") (SR-6) |
| row-lines | article#ob-stage-content > section.ob-block:nth-of-type(1) > dl.ob-facts "PublisherIP AustraliaRetrieved2026-11-23" | a row of 2 items: its last item ends at 1076px, the container's right line at 1368px (2px either way) (SR-7) |
| overlap-text | article#ob-stage-content > section.ob-block:nth-of-type(2) > p.ob-note "Natural-person IP names and direct conta" | lies over the text "patent" (tr:nth-of-type(8) > td:nth-of-type(2)) (and 1 more like it: "REVIEW DESK Human review") |
| edge-left | #onboarding p.ob-note "IP Australia · Roles, applicatio" | starts at x 183.9; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "Extracted observations" | starts at x 93; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "Recorded candidate output" | starts at x 93; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "Business-connected" | starts at x 417.5; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "Visible facts with a declared bu" | starts at x 417.5; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "Human-verified" | starts at x 741; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "No human verdict inferred from a" | starts at x 741; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "Groups accepted" | starts at x 1064.5; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "1 unresolved · 470,541 tokens ac" | starts at x 1064.5; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "Sample 1–10 of 50 · 8 columns" | starts at x 510.2; the lines are 72 and the column starts |
| edge-left | #onboarding p.ob-note "1 / 7" | starts at x 571.1; the lines are 72 and the column starts |
| bleed-one-side | #onboarding table.ob-table "Frozen source row previewSource " | runs from x 17 out to the right viewport edge; the left side stays at 16 |

### Non-blocking checker warnings

These warnings are retained because the UI uses data summaries, navigation, evidence controls and scroll containers. They are not claims that those checks passed.

| Check | Location | Finding |
| --- | --- | --- |
| fold-card | div#onboarding > div.ob-shell > div.ob-workspace > aside.ob-sidebar "REVIEW DESK Human review requirements Co" | the 264x978 card starts on the first screen and runs 690px past its bottom (inside a held section or scroll scene, whose motion --quick does not check) |
| pinned | div#onboarding > div.ob-shell > div.ob-workspace > aside.ob-sidebar "REVIEW DESK Human review requirements Co" | held on screen for 0.4 screens of scroll (position: sticky) while the page moves on (a narrow sticky column) |
| copy-buttons | section.ob-block:nth-of-type(2) > div > div.ob-pager > button.ob-button.ob-secondary:nth-of-type(1) "Previous rows" | "Previous rows" does not start with a verb (book, buy, try, start, get, see...) (and 3 more like it: "Next rows", "← Previous stage", "Next stage →") |
| heading-scale | div.ob-shell > div.ob-summary > div.ob-stat:nth-of-type(3) > strong "Not measured" | 1 line of plain text set larger than the section headings (32px against h2 21.5px) |
| stranded-action | section.ob-block:nth-of-type(2) > div > div.ob-pager > button.ob-button.ob-secondary:nth-of-type(1) "Previous rows" | stands 333px across from the nearest text of its block ("Sample 1–10 of 50 · 8 columns") (and 1 more like it: "Next rows") |
| copy-length | div#onboarding "Dataset onboarding" | 1 section over 90 words a screen outside the UI mocks ("Dataset onboarding" 233); 233 words a screen across the page (490 words in 2.1 screens): a tech page says it in about 80 or fewer |
| fold-action | section.ob-block:nth-of-type(2) > div > div.ob-pager > button.ob-button.ob-secondary:nth-of-type(1) | the hero's second button "Previous rows" starts 879px below the first screen (900px tall): it is not seen on load |
| fold-action | section.ob-block:nth-of-type(2) > div > div.ob-pager > button.ob-button.ob-secondary:nth-of-type(2) | the hero's second button "Next rows" starts 879px below the first screen (900px tall): it is not seen on load |
| fold-action | div.ob-shell > div.ob-workspace > aside.ob-sidebar > button.ob-button.ob-secondary:nth-of-type(1) | the hero's second button "Open review stage" starts 52px below the first screen (900px tall): it is not seen on load |
| fold-action | div.ob-shell > div.ob-workspace > aside.ob-sidebar > button.ob-button.ob-secondary:nth-of-type(2) | the hero's second button "Download review queue" starts 106px below the first screen (900px tall): it is not seen on load |
| font-load | div#onboarding > div.ob-header > div.page-intro.ob-intro > h1 "Inter" | "Inter" is asked for by the h1, the h2s and the body text but never loaded (no font link or @font-face loads it): it shows in its fallback |
| share-meta | head | the head lacks og:title, og:description, og:image, twitter:card, an icon, theme-color: a shared link shows no picture or title of its own |
| container-edges | div.ob-shell > div.ob-workspace > aside.ob-sidebar > h2 "Human review requirements" | the h2 starts 1053px right of the container's left: every h1 and h2 starts on it, 2px either way (it sits in a part held on screen as the page scrolls: told as a WARN) (SR-6) |
| heading-scale | article#ob-stage-content > div.ob-stage-heading > div > h2 "Dataset arrives" | h2 headings in 2 sizes, 18px ("Human review requirement") to 23px (x1.28) |
| heading-scale | article#ob-stage-content > section.ob-block:nth-of-type(1) > h3 "IP RAPID role-scoped joined application " | h3 headings in 2 sizes, 13px ("Current limitation") to 16px (x1.23) |
| off-grid | article#ob-stage-content > nav.ob-stage-controls > p.ob-note "1 / 7" | left edge at 192px, 10px off a common edge of its section at 202px (4 elements, none of them near it) |

## Performance check

The skill performance checker ran three loads per viewport at 1440 and 390 pixels against the standalone HTML: **PASS — 0 FAIL, 0 WARN**, including no broken requests. These are local CPU-browser measurements, not field performance. The self-contained report is 2,214,000 bytes uncompressed; its embedded data requires no separate API or asset requests.
