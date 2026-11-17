# Local mapping corrections — 17 November 2026

Seven findings corrected at the user's request without further model API calls. These are maintainer edits to preserved agent proposals; they are not represented as a new agent run or a human approval.

Replayed 7,744 frozen rows and verified 85,446 observations with zero differences. Both API usage logs and the human link-review journal are unchanged.

- **acnc_charities**: Contact-address scope corrected for all ACNC address claims, including 108 postal-box records; no operating-establishment edges remain. The conflicting Aruba/VIC country claim is withheld.
- **asic_companies**: ASIC subclass meanings corrected for LISN/LISS/NLTD, including all 14 affected saved records. Seven records with unverified PUBF/RACA codes now omit the subclass interpretation. Unsupported address-country defaults removed.
- **asic_credit_licensees**: All 512 complete permission texts are preserved without splitting conditions; all 512 licence start dates are now explicit licence facts. Unverified location coordinates omitted.
- **ato_tax_transparency**: Unsupported address-country defaults removed. All 2,473 financial claims retain reporting period and AUD qualifiers; blank amounts remain absent.
- **ato_tax_transparency_2023_24**: Unchanged mapping rechecked: all 2,510 financial claims retain reporting period and AUD qualifiers, with no address-country default.
- **dewr_employment_providers**: All 1,002 country defaults now describe the establishment, alongside its address. They no longer assert the business subject's country.
- **qbcc_licensees**: Ambiguous trade-to-industry inference removed. All 1000 published licence-category claims remain available with their licence and source evidence.
- **vic_liquor**: All 2,000 state/country defaults now describe licensed premises. Interstate correspondence addresses are kept separately without an invented Victorian state.

All eight mappings are ready for human sign-off on the saved sample. The original review remains in MAPPING_REVIEW_2026-11-17.md. The immutable before/ archive and parent_mapping.json in each new run preserve the exact originals.

Human link reviews still matching current evidence: {'pass': 46, 'fail': 4}. Changes to link evidence do not inherit a previous decision.

No new accuracy percentage is claimed. Source data errors, the known link-review failures, draft interpretation tables, and incomplete source coverage remain visible limitations.
