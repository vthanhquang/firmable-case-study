# Mapping review - 17 November 2026

Reviewer: Codex (AI assistant). Advisory review only; no human approval was recorded.

Reviewed all eight complete configurations, saved validation and critic reports, raw sample rows, role/scope semantics and referenced crosswalks. Replayed 7,744 rows / 92,092 observations with zero differences. Replay agreement measures reproducibility, not independent accuracy.

**Outcome: 1 ready for human sign-off; 7 need changes.** Source configs and the saved replay remain unchanged. Findings below are recommendations for the agent revision loop, not hand-authored replacement mappings.

## acnc_charities - needs changes

Keep charity identity and purpose fields; correct address role and country contradictions before sign-off.

Evidence: 1,064 rows; 16,462 observations. Config `51544ecb3266ffaeec341599f31b85a2108462918d09ef9158437aaef0dc67cc`.

### P1 Register contact addresses are asserted as operating establishments

108 of 1,064 sampled rows contain a PO box or locked bag, yet the mapping emits an establishment and OPERATES_ESTABLISHMENT. Row 1873 is one example. ACNC describes these as contact details.

Correction: Have the agent use a business/contact-address scope. Do not assert operating premises from the register address alone.

### P1 Contradictory country values become canonical facts

Row 2785 supplies Country=Aruba alongside State=VIC and Postcode=3821; the mapping emits ARUBA. The earlier holdout also reported Austria against an Australian locality.

Correction: Retain the raw country as evidence and flag contradictions. Do not silently correct the country or pass contradictory names into canonical address fields.

- Identity, dates, operating regions and purpose flags reproduce correctly. Invalid websites and postcodes are rejected.
- Beneficiary columns have an available acnc_beneficiary concept. Leaving them unmapped is conservative, but the explanation that no target exists is inaccurate.
- The charity-size crosswalk remains a separate draft dependency; its thresholds should not be treated as period-specific revenue without a reporting year.

Reference: [ACNC: information published on the Charity Register](https://www.acnc.gov.au/charity/about-acnc-charity-register/information-charity-register)

## asic_companies - needs changes

Correct subclass crosswalk meanings and remove address-country inference from registration jurisdiction.

Evidence: 1,166 rows; 13,396 observations. Config `068a14bebaadb5fa5973a9ef3c662f4967578460df32b91a7d3b210bf6c9092c`.

### P1 Some subclass labels contradict ASIC documentation

The sample includes 6 LISN and 8 NLTD rows. The table describes LISN as listed non-profit and NLTD as no liability; ASIC instead uses these for companies allowed to omit Limited from their names. LISS is also mislabelled as listed.

Correction: Correct and separately review the crosswalk, then regenerate observations and affected profiles. Keep unverified rare codes unmapped rather than decoding them speculatively.

### P2 Registration jurisdiction is emitted as address country

All 1,166 sampled records receive address.country=AU from a constant, although this dataset has no address column and includes foreign-company registration types.

Correction: Remove the address-country constant or represent registration jurisdiction in the appropriate concept.

- Current and former names are separated correctly; zero ABNs are discarded and valid ACNs are retained.
- The earlier critic was wrong to question PSTC and ULSS merely from business names: ASIC explicitly supports those trustee meanings.
- All four ASIC crosswalks remain separately pending human review.

Reference: [ASIC EDGE specification, Appendix C, page 92](https://download.asic.gov.au/media/5982305/els-document-messages-specification-v500-20210218.pdf#page=97)

## asic_credit_licensees - needs changes

Preserve complete authorisation conditions and retain licence dates on licence claims.

Evidence: 512 rows; 10,362 observations. Config `e5c026d80cd981f19eaac2b698f2933e33c258ded02759f8efc2982048cfbfe3`.

### P1 Authorisation splitting detaches conditions from permissions

893 emitted fragments begin with where the service or by providing. For example, licence 230637 on row 25 emits a dependent condition as a standalone activity after its parent heading was dropped.

Correction: Preserve each complete permission block, including conditions, or leave the complex field as unparsed source evidence. Do not present dependent clauses as separate permissions.

### P2 Licence start dates are silently absent from output

All 512 sampled rows have CRED_LIC_START_DT, but the rule targets legacy observation.valid_from, which the engine validates and then ignores.

Correction: Map dates to supported licence-scoped facts or validity paths only on claims actually dated by the source; do not apply licence validity to the company itself.

- ABN and ACN are correctly distinguished by length and checksum. Licence status remains separate from company status.
- Repeated coordinates may be locality centroids. Verify precision before presenting ext.entity.address_point as an exact business location; the website currently omits coordinates.


## ato_tax_transparency - needs changes

Financial mapping is sound; remove the unsupported address-country default.

Evidence: 1,000 rows; 5,462 observations. Config `01b1bfad71c89e00a75160c6c95fb0f1bf44c6576feaf85e845aed5df40edbe6`.

### P2 An ABN does not establish an Australian address

The mapping emits address.country=AU for all 1,000 sampled rows even though the file contains only identity and tax data. ABR permits eligible non-residents to hold ABNs.

Correction: Remove the constant. Preserve known tax jurisdiction separately rather than filling an address field.

- All 2,473 financial claims retain their source income year and AUD qualifier. Blank tax amounts do not become zero.
- The earlier critic claimed identity was missing because it saw only extension rules. The complete config and replay contain legal name and ABN, so that warning is dismissed.

Reference: [ABR: ABNs for businesses outside Australia](https://www.abr.gov.au/business-super-funds-charities/applying-abn/abn-businesses-outside-australia)
Reference: [ATO: interpreting the published tax figures](https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/large-business/corporate-tax-transparency/report-of-entity-tax-information)

## ato_tax_transparency_2023_24 - ready

Ready for human sign-off: identity and financial facts are correctly scoped and no blocking issue was found.

Evidence: 1,000 rows; 4,504 observations. Config `244af1f30398ffc614cf5a08be2c16412071bacf19c7c9bdbaa62dece844736c`.

- Replayed all 1,000 sampled records and 2,510 financial claims with no output differences or financial qualifier gaps.
- Legal name and checksum-valid ABN identify the subject. Financial figures use the income year from each row and AUD; missing values remain absent.
- There is no inferred address-country constant. Blank spreadsheet columns remain explicitly unmapped.
- This is a review recommendation, not human approval or a claim that every row in the full source is correct.

Reference: [ATO: interpreting the published tax figures](https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/large-business/corporate-tax-transparency/report-of-entity-tax-information)

## dewr_employment_providers - needs changes

Site fields are mostly well scoped; move the country default to the establishment role before sign-off.

Evidence: 1,002 rows; 13,976 observations. Config `d3f0f2bfdf667a0b4008c82363141c1c2617aad587e58949fad2e74f5b0cb127`.

### P2 Country default is attached to the business rather than the site

Address, locality, state and postcode belong to establishment, but all 1,002 rows also emit address.country=AU on subject because generic constants always use subject.

Correction: Attach country to the same establishment address as the other fields, or omit it until role-aware constants are supported.

- SITE_NAME is a trading/display name, not promoted to a legal name. Site codes, programmes and addresses preserve establishment scope.
- 847 rows repeat the same phone under different source roles. This preserves column evidence; the profile builder already deduplicates contact values. It is not evidence of multiple distinct phone numbers.
- The current mapping conservatively omits the proposed industry-code inference. Separately, downstream programme labels still use a draft crosswalk and require review.


## qbcc_licensees - needs changes

Keep licence and holder identity; revise the activity-to-industry inference before sign-off.

Evidence: 1,000 rows; 11,605 observations. Config `9af5930b0631a87c0f70674fbfc39c71285a74107d6db01b74ef3be8036200c4`.

### P1 A draft trade crosswalk overstates business industry

14 sampled Cabinet Making rows are assigned ANZSIC 3242. ABS separates on-site carpentry from manufacturing prefabricated cabinets under 1492; the licence class alone does not resolve that distinction.

Correction: Retain the licence category as published. Review ambiguous crosswalk entries and omit or broaden unsupported industry claims; then obtain separate crosswalk sign-off.

- Individual versus organisation holder evidence is preserved without inferring sole-trader status. Licence number, grade and category stay on the licence role.
- Three bad ABNs in this saved sample are rejected by checksum. The source is a 32,000-row prefix, so this review does not establish coverage across every category in the full register.

Reference: [ABS: ANZSIC 3242 and its manufacturing exclusion](https://www.abs.gov.au/statistics/classifications/australian-and-new-zealand-standard-industrial-classification-anzsic/2006-revision-2-0/detailed-classification/e/32/324/3242)

## vic_liquor - needs changes

Premises and postal addresses are separated, but the VIC default is attached to the wrong role.

Evidence: 1,000 rows; 16,325 observations. Config `4a41b83076313583089c587a3986612bc3bc8716ba1e9a9fbb15d7e53544a2c1`.

### P1 Premises jurisdiction contaminates the licensee postal address

The VIC constant is emitted on subject, while the premises address is on premises. 44 of 1,000 sampled records have postal postcodes outside VIC ranges: row 25 has ALBURY 2640 and row 2453 has SYDNEY NSW 2000.

Correction: Move VIC and the associated country default to the premises role or omit them. Never combine the Victorian premises state with the licensee correspondence address.

- Licensee, trading name, licence and premises fields are separated; postal fields carry correspondence_address scope. A PO box is valid for that scope, so the earlier postal-address critic warning is not itself a blocker.
- The mapping avoids inferring an industry from broad liquor permissions. Opening hours, capacity and licence category remain source facts.
