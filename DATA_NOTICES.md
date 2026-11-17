# Source attribution and data notices

The public data retains its publisher licence; it is not relicensed as project code. The table records the licence interpretation saved with this run. Canonical observations carry `licence_detail` (ID, title, URL and attribution). The complete source metadata, snapshot hashes and restore-file hashes are in [fixtures/replay/manifest.json](fixtures/replay/manifest.json).

| Source | Publisher / dataset | Recorded licence |
| --- | --- | --- |
| `asic_companies` | [Australian Securities and Investments Commission (ASIC) — ASIC - Company Dataset](https://data.gov.au/data/dataset/7b8656f9-606d-4337-af29-66b89b2eeefb/resource/d6d03876-71a4-4e82-8c77-2e4df5da4236/download/company_202611.zip) | [Creative Commons Attribution 3.0 Australia](http://creativecommons.org/licenses/by/3.0/au/) |
| `acnc_charities` | [Australian Charities and Not-for-profits Commission (ACNC) — ACNC Registered Charities](https://data.gov.au/data/dataset/b050b242-4487-4306-abf5-07ca073e5594/resource/eb1e6be4-5b13-4feb-b28e-388bf7c26f93/download/datadotgov_main.xlsx) | [Creative Commons Attribution 3.0 Australia](http://creativecommons.org/licenses/by/3.0/au/) |
| `ato_tax_transparency` | [Australian Taxation Office — Corporate Tax Transparency](https://data.gov.au/data/dataset/c2524c87-cea4-4636-acac-599a82048a26/resource/15bf4eaa-7a14-48e9-8a3f-092df32a644e/download/2024-25-corporate-report-of-entity-tax-information.xlsx) | [Creative Commons Attribution 3.0 Australia](http://creativecommons.org/licenses/by/3.0/au/) |
| `qbcc_licensees` | [Queensland Building and Construction Commission — QBCC Licensed Contractors Register](https://www.data.qld.gov.au/dataset/980b6499-c0b4-491b-ba9c-1c7506368a50/resource/25608781-b28c-44f8-8545-0ab18d84082f/download/20260923_qbcc_active_licencees_opendatain-2.csv) | [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) |
| `vic_liquor` | [Liquor Control Victoria — Victorian liquor licences by location](https://www.vic.gov.au/sites/default/files/2026-09/Current_Victorian_Licences_By_Location_31_August_2026.xlsx) | [Creative Commons Attribution 3.0 Australia](http://creativecommons.org/licenses/by/3.0/au/) |
| `dewr_employment_providers` | [Department of Employment and Workplace Relations — Employment Services Provider Locations and Contacts](https://data.gov.au/data/dataset/638f89d7-1c12-4db9-8342-abfcd7b49e95/resource/d9c69f98-f0af-4db8-b598-513e1da748ce/download/providerdetailsmay2016.csv) | [Creative Commons Attribution 3.0 Australia](http://creativecommons.org/licenses/by/3.0/au/) |
| `asic_credit_licensees` | [Australian Securities and Investments Commission (ASIC) — ASIC – Credit Licensee Dataset](https://data.gov.au/data/dataset/fa0b0d71-b8b8-4af8-bc59-0b000ce0d5e4/resource/3abf1383-c4e5-4c1a-8331-8434b17b6f10/download/credit_lic_202611.tsv) | [Creative Commons Attribution 3.0 Australia](http://creativecommons.org/licenses/by/3.0/au/) |
| `ato_tax_transparency_2023_24` | [Australian Taxation Office — Corporate Tax Transparency - 2023-24 Report of Entity Tax Information](https://data.gov.au/data/dataset/c2524c87-cea4-4636-acac-599a82048a26/resource/491b366b-aa6f-4b1c-b39d-cebaeeb6f874) | [Creative Commons Attribution 3.0 Australia](http://creativecommons.org/licenses/by/3.0/au/) |

## Included material

- `fixtures/replay/rawstore/` contains the 7,744 frozen sampled rows used in the final replay, with their original row ordinals and sample strata. It is not a copy of every full source register.
- The compressed second QBCC snapshot is included to reproduce the saved change-detection experiment. Its exact restored hash is recorded separately from the sampled baseline.
- Generated observations, mappings, joins, profiles and excerpts are adaptations. Values have been normalised, filtered, linked and sometimes derived; they are not publisher-endorsed company records. Per-field provenance records those changes.
- The generic `cc-by` catalogue identifier is interpreted as CC BY 3.0 Australia in the saved licence registry; QBCC uses the explicit CC-BY-4.0 identifier. Source metadata and the interpretation are retained for inspection. Unknown licences are surfaced rather than inferred.
- Preserve publisher attribution and licence links when redistributing the data. No publisher endorsement is implied. Public-register entries can concern natural persons; avoid treating source availability as permission for unrelated uses. Personal contact observations are withheld from final profiles, but the replay inputs retain public source rows.

## Reproduction scope

Full original downloads and private credentials are excluded. The fixture bundle restores only the inputs needed by `raw-replay`. Full-resource onboarding, alternate sampling or contemporary data require fetching the corresponding publisher resources and respecting their current terms.
