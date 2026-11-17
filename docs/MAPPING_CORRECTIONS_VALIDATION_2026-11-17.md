# Validation — local mapping corrections, 17 November 2026

Backend: 156 tests passed. Targeted profile, audit and offline-replay checks also passed after the final profile assertion.

Frozen-data verification: 7,744 rows / 85,446 observations, zero replay mismatches. Seven corrected mappings and the unchanged eighth mapping are ready for human sign-off. Both model usage ledgers are unchanged. Model access was disabled during replay. All 50 human link reviews remain bound to matching evidence: 46 pass, 4 fail.

Frontend: JavaScript syntax checks and production build passed. Visually inspected the mapping drawer at 1440px and the profile drawer at 390px. Fixed the mobile drawer extending beyond the viewport. These screenshots cover the visible drawer viewport, not every expanded nested detail. The full-page screenshot tool cannot scroll the independently scrolling drawer and reported unreachable bottom rows; no claim of exhaustive visual coverage is made.

Published source commit: `380ee0c82e89a59cf4d9a464e3a110c80141588a`. Deployment succeeded with owner-only access preserved.

## Broader design gate

GATE: OPEN 40 (rounds used up), with 20 warnings and no waivers. Most findings enforce landing-page conventions on this existing data-review dashboard: full-screen sections, hero imagery/CTAs, and uniform split alignment. The report also flags visible search labeling. The existing dashboard structure was retained; the broad style gate is not claimed as passing. Per the skill stop rule, remaining findings are recorded here.

An initial gate invocation used the old saved localhost:4173 target and could not inspect the current page. The final run below targets localhost:4191/?part=mapping.

- **hero-fill** — div#part-content > section.analysis-section "What each source contributed": the next section shows on the first screen: it starts at 541px on a 900px screen (the hero ends at 543px)
- **flush** — div#part-content > section.analysis-section > div.analysis-card "Latest mapping Base mapping Source colum": its last line sits 0px above the lower edge of section.analysis-section, where the ground changes to section.overview-block:nth-of-type(1)
- **flush** — div.overview-grid > section.overview-block:nth-of-type(1) > a.source-link > span.external "â†’": section.overview-block:nth-of-type(1) and section.overview-block.pilot-block run together: -109px between their content, on one ground
- **no-visual** — div#part-content > section.overview.with-analysis "Schema inference & mapping": no picture, effect or mock in this section; a feature section needs a visual
- **no-visual** — div#part-content > section.analysis-section "What each source contributed": no picture, effect or mock in this section; a feature section needs a visual
- **text-only** — div#part-content > section.catalogue.results-catalogue "Explore the mappings": the closing section is only text: no picture, icon, mock or effect in it
- **cta** — div#part-content > section.overview.with-analysis: the hero has no button (the nav's does not count)
- **cta** — div#part-content > section.catalogue.results-catalogue "Explore the mappings": the last section before the footer ends with no button
- **heading-scale** — section.analysis-section > div.analysis-card > div.chart-inspector > h3 "ACNC": an h3 at 19px, as large as the smallest h2 (16px) or larger
- **heading-scale** — section.analysis-section > div.section-heading > div > h2 "What each source contributed": h2 headings in 2 sizes, 16px ("One row can describe sev") to 32px (x2.00)
- **heading-scale** — section.overview.with-analysis > div.summary > div.metric:nth-of-type(1) > strong.metric-value "8": the figure "8" is set at 38px, larger than the section headings (h2 32px); 3 more like it
- **field-label** — section.catalogue.results-catalogue:nth-of-type(3) > div.toolbar:nth-of-type(2) > label.search > input: a input[type=search] without a label you can see: its <label> is hidden
- **moment-none** — (the page): a software page (--type) deals no moment: every kind carries one, two on a long page (moments.md)
- **hero-screen** — div#part-content "Part 2 of 5Schema inference & mappingCom": the hero ends at 2138px on a 900px screen, 1238px below the fold: it ends at the fold, 1px either way (SR-1)
- **section-height** — footer.wrap.footer "Firmable Case Study": the section is 63px tall (0.1 screens), 837px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2)
- **section-height** — div#part-content "Part 2 of 5Schema inference & mappingCom": the section starts at 73px, 73px below the screen grid (0 x 900px): sections start on whole screens (SR-2)
- **one-section** — footer.wrap.footer "Firmable Case Study": the screen at scroll 1301px (the top of section 2) shows 63px of section 2 beside section 1: a screen shows one section (another may peek 8px, 24px WARN) (SR-4)
- **one-section** — div#part-content "Part 2 of 5Schema inference & mappingCom": a <div> sits directly in <main>: every part of <main> is a <section> (SR-4)
- **one-heading** — section.analysis-section > div.section-heading > div > h2 "What each source contributed": the hero holds an h2 (4): its heading is the h1, and an h2 opens the next section (SR-5)
- **container-edges** — a.skip-link "Skip to content": a <a> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6)
- **container-edges** — header.site-header "Firmable Case study Demo Discovery Mappi": a <header> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6)
- **container-edges** — footer.wrap.footer "Firmable Case Study": a <footer> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (and 2 more like it: "Part 2 of 5Schema infere", "Firmable Case Study") (SR-6)
- **container-edges** — div.overview-grid > section.overview-block.pilot-block > div.block-title > h2 "Mapping review findings": the h2 starts 765px right of the container's left: every h1 and h2 starts on it, 2px either way (SR-6)
- **container-edges** — section.overview.with-analysis > div.summary > div.metric:nth-of-type(1) > p.metric-label "Sources mapped": 5 text blocks start on a left line at x 94, 22px from the container's left: text starts on the container's left, or on one split line (x 622, 732, 842) (also "8", "Includes two ATO reporting years", "Column counts include inputs use") (SR-6)
- **container-edges** — div#part-content > section.overview.with-analysis > aside.run-banner > span "Latest raw-data replay Â· Review preview": 1 text block starts on a left line at x 85, 13px from the container's left: text starts on the container's left, or on one split line (x 622, 732, 842) (SR-6)
- **row-lines** — section.analysis-section > div.analysis-card > div.chart-main > div.column-axis "Source020406080Read / total": a row of 3 items: its first item starts at 102px, its column's left line at 94px; its last item ends at 876px, its column's right line at 884px (2px either way) (SR-7)
- **split-pair** — div#part-content > section.analysis-section > div.analysis-card "Latest mappingBase mappingSource columns": the two columns of the split start 20px apart at the top: a split's columns are top-aligned, 8px either way (SR-8)
- **split-pair** — div#part-content > div.overview-grid "One row can describe several thingsThe V": the split's columns are off the page's one pair of lines: its right column starts at x 805, the first split's at 905; its right column starts at x 805, on none of the split lines 622 (k=5), 732 (k=6), 842 (k=7) (SR-8)
- **no-visual** — div#part-content > section.catalogue.results-catalogue "Explore the mappings": no picture, effect or mock in this section; a feature section needs a visual
- **edge-left** — #part-content p.metric-label "Sources mapped": starts at x 94; the lines are 72 and the column starts
- **edge-left** — #part-content p.metric-note "Includes two ATO reporting years": starts at x 94; the lines are 72 and the column starts
- **edge-left** — #part-content p.metric-label "Source columns read": starts at x 418.5; the lines are 72 and the column starts
- **edge-left** — #part-content p.metric-note "54 in the base mappings": starts at x 418.5; the lines are 72 and the column starts
- **edge-left** — #part-content p.metric-label "Observations extracted": starts at x 742; the lines are 72 and the column starts
- **edge-left** — #part-content p.metric-note "Across all eight source extracts": starts at x 742; the lines are 72 and the column starts
- **edge-left** — #part-content p.metric-label "Mappings reviewed": starts at x 1065.5; the lines are 72 and the column starts
- **edge-left** — #part-content p.metric-note "8 ready Â· 0 need changes": starts at x 1065.5; the lines are 72 and the column starts
- **edge-left** — #part-content p.chart-note "Column counts include inputs use": starts at x 98; the lines are 72 and the column starts
- **edge-left** — #part-content h2 "Mapping review findings": starts at x 836.5; the lines are 72 and the column starts
- **edge-left** — #part-content p.pilot-result "8 mappings assessed. 8 still awa": starts at x 836.5; the lines are 72 and the column starts

Detailed machine report: `frontend/.taste-skill/gate.json`; consistency report: `frontend/.taste-skill/gate/consistency/report.json`.
Screenshots: `frontend/.taste-skill/corrections-mapping.png` and `frontend/.taste-skill/corrections-profile-mobile-fixed-top.png`.
