# Architecture and two-page write-up validation

GATE: FAIL 31 (round 2 of 3). No waivers were applied.

The existing minimal case-study dashboard was preserved. The remaining automated findings concern marketing-page hero heights, sales calls to action, decorative motion/imagery, section sizing, and intentional inset padding inside diagram steps. They are recorded below; this is not a claim that the marketing design gate passed.

## Completed checks

- Part 3: all 1,455 proposals contain the required fields and join different source IDs; 1,245 unique unlinked records retain refusal reasons.
- Current human reviews bind to the saved proposal evidence: 46 pass and 4 fail across 50 audited links at threshold 0.85.
- Website JavaScript syntax checks and production build pass. New PDF, LaTeX, SVG, module and JSON routes return HTTP 200 with the expected content types.
- Desktop (1440 px) and mobile (390 px) architecture screenshots were inspected. A crossing diagram label was relocated. SVG keyboard focus and mobile human-step text contrast were corrected; these findings no longer appear in the second gate result.
- LaTeX compiled with Tectonic 0.17.0. An overfull line was corrected. The final PDF has exactly two A4 pages at 11-point body size; both rendered pages were inspected.
- PDF text includes all six Part 5 answers and the entity-relationship model. Website PDF/LaTeX copies match the final artifacts.
- No model API calls were needed.

## Design context

Software review dashboard; existing Inter typography, cream background and dark-green palette. The infographic uses green for AI, amber for human review and blue-grey for saved artifacts. Copy describes actual processing steps and measured results. No photographs, invented business facts, or placeholder assets were added.

## Remaining automated findings

| Check | Widths | Finding |
| --- | --- | --- |
| hero-fill | 1440 | the next section shows on the first screen: it starts at 417px on a 900px screen (the hero ends at 417px) |
| flush | 1440 | its last line sits 0px above the rule on top of the footer |
| no-visual | 1440, 390 | no picture, effect or mock in this section; a feature section needs a visual |
| cta | 1440, 390 | the hero has no button (the nav's does not count) |
| cta | 1440 | the last section before the footer ends with no button |
| copy-headline | 1440 | "From source records to company profiles" does not name what is sold (case study review dashboard, case, study, review, from flags) |
| copy-fact | 1440 | the first screen holds no number, price, date, place, platform or genre |
| moment-none | 1440 | a software page (--type) deals no moment: every kind carries one, two on a long page (moments.md) |
| hero-screen | 1440 | the hero ends at 1835px on a 900px screen, 935px below the fold: it ends at the fold, 1px either way (SR-1) |
| section-height | 1440 | the section is 63px tall (0.1 screens), 837px short of one screen (900px): every section after the hero is one screen or two, 2px either way (SR-2) |
| section-height | 1440 | the section starts at 73px, 73px below the screen grid (0 x 900px): sections start on whole screens (SR-2) |
| one-section | 1440 | the screen at scroll 1034px (the top of section 2) shows 63px of section 2 beside section 1: a screen shows one section (another may peek 8px, 24px WARN) (SR-4) |
| one-section | 1440 | a <div> sits directly in <main>: every part of <main> is a <section> (SR-4) |
| container-edges | 1440 | a <a> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6) |
| container-edges | 1440 | a <header> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (SR-6) |
| container-edges | 1440 | a <footer> at the top of the page, outside header.nav, main, footer.closing and nav.actionbar (and 2 more like it: "System architectureFrom ", "Firmable Case Study") (SR-6) |
| hero-fill | 390 | the next section shows on the first screen: it starts at 510px on a 844px screen (the hero ends at 481px) |
| nav | 390 | the nav has no bar, and its pieces sit past the content's edges (-31-394px against 16-374px) |
| no-visual | 390 | no picture, effect or mock in this section; a feature section needs a visual |
| no-visual | 390 | no picture, effect or mock in this section; a feature section needs a visual |
| no-visual | 390 | no picture, effect or mock in this section; a feature section needs a visual |
| no-visual | 390 | no picture, effect or mock in this section; a feature section needs a visual |
| card-visual | 390 | 5 cards hold only text: no picture, icon, UI fragment or effect in any of them |
| card-visual | 390 | 5 cards hold only text: no picture, icon, UI fragment or effect in any of them |
| card-visual | 390 | 5 cards hold only text: no picture, icon, UI fragment or effect in any of them |
| card-visual | 390 | 5 cards hold only text: no picture, icon, UI fragment or effect in any of them |
| cta | 390 | the last section before the footer ends with no button |
| off-grid | 390 | left edge at 33px, 17px off the page margin at 16px (35 elements, like p.eyebrow) |
| off-grid | 390 | left edge at 33px, 17px off the page margin at 16px (35 elements, like li.architecture-step.store); 1 more in this section off the grid too (p.architecture-branch-note:nth-of-type(3) at 33px) |
| off-grid | 390 | left edge at 33px, 17px off the page margin at 16px (35 elements, like li.architecture-step.human); 2 more in this section off the grid too (p.architecture-branch-note:nth-of-type(3) at 33px, p.architecture-branch-note:nth-of-type(4) at 33px) |
| off-grid | 390 | left edge at 33px, 17px off the page margin at 16px (35 elements, like span:nth-of-type(1)) |

Non-blocking warnings: copy-actions, share-meta, fold-cut and copy-eyebrows. The page uses download/navigation links, existing metadata and an intentionally continuous mobile process flow.

Published source: `2fe2647a19d0b72b5e85ba577ba371497529ddd2`.
