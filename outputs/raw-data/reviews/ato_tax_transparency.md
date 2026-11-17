# Local correction review: `ato_tax_transparency`

Status: PENDING_REVIEW; human sign-off is still required.
Run: `20261117T041636-local-015226f8`; config digest: `015226f840e046d67cee97aa355a30aceecd4aecf81c905879c1de88f28c6931`.
Original agent run: `20261112T204029-b6524b` (preserved).
Actor: Codex maintainer, at user request. Model calls: 0.

Remove address-country inference from ABN and tax jurisdiction; keep financial facts unchanged.

Validation: Frozen replay sample partition; not an unseen holdout. No new model critic was called.

## Regression findings

```json
[]
```

## Exact mapping changes

```diff
--- previous agent proposal
+++ local corrected proposal
@@ -1,12 +1,5 @@
 {
-  "constants": [
-    {
-      "confidence": 0.7,
-      "rationale": "The dataset is an Australian Taxation Office register of entities with Australian Business Numbers, so the entities are Australian for tax purposes. This is an inferred jurisdiction, not a stated address.",
-      "target": "address.country",
-      "value": "AU"
-    }
-  ],
+  "constants": [],
   "entities": null,
   "extensions": "ext-v1",
   "fields": [
@@ -15,6 +8,7 @@
       "confidence": 0.82,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Column 'Name' holds registered-style entity names ('CHEVRON AUSTRALIA PTY LTD', 'MOBIL AUSTRALIA RESOURCES COMPANY PTY LIMITED'); the ATO transparency register publishes the legal/taxable-entity name, and company suffixes (PTY LTD / LIMITED) indicate legal rather than trading names. Note 'GOVE ALUMINIUM FINANCE LINITED' shows the source's own typos are preserved.",
       "source_paths": [
@@ -52,6 +46,7 @@
       "confidence": 0.97,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Column 'ABN' is 11 digits in all present rows with a 100% checksum-valid rate (431/431) in discovery; the abn transform validates the checksum.",
       "source_paths": [
@@ -74,6 +69,7 @@
       "confidence": 0.95,
       "entity": null,
       "join_with": "",
+      "one_hot": null,
       "qualifiers": {
         "currency": {
           "source_path": null,
@@ -107,6 +103,7 @@
       "confidence": 0.95,
       "entity": null,
       "join_with": "",
+      "one_hot": null,
       "qualifiers": {
         "currency": {
           "source_path": null,
@@ -140,6 +137,7 @@
       "confidence": 0.95,
       "entity": null,
       "join_with": "",
+      "one_hot": null,
       "qualifiers": {
         "currency": {
           "source_path": null,
@@ -170,7 +168,7 @@
     }
   ],
   "grain_rationale": "One row per legal entity (identified by its ABN) per income year, reporting aggregate tax information (total income, taxable income, tax payable) on the ATO Corporate Tax Transparency register. The record is about the business itself, so entity attributes are mapped directly; the financial figures have no canonical ontology target and are recorded as unmapped.",
-  "notes": "Workbook has an 'Information' sheet (title/guidance text, sheet name only), the main 'Income tax details' sheet (435 data rows; header in row 1) and a separate 'PRRT details' sheet (petroleum resource rent tax payers, 8 rows in discovery). Only the 'Income tax details' sheet is mapped here. 'PRRT details' has its own schema (Name, ABN, PRRT Payable $) and would need a second config. Income year mixes 2024-25 with a few prior-year comparatives. Column names contain a trailing ' $'.\n\n[ext-v1] The sheet is narrow: only six columns, and the approved mapping already covered Name -> entity.legal_name and ABN -> entity.abn, so this extension recovers the three financial measures that the record grain rationale had left unmapped. No new record roles are needed: one row is one legal entity's aggregate tax position for one income year, and the financials attach to the subject business. Income year is deliberately left unmapped as an attribute (see unmapped reason) but is load-bearing as the period qualifier - the file contains 2023-24 and 2022-23 comparative rows alongside 2024-25, so without the qualifier the same ABN could appear to hold two conflicting income figures. No approved base rules were edited; both approved rules are non-editable and passed the gate. No crosswalk tables were used: the source states no status code, legal form, industry activity or revenue band, and deriving a revenue band from the dollar amounts would be inference rather than source-stated fact. The approved constant address.country = AU is left untouched - the file carries no address, but the entity is AU-registered by ABN, and removing an approved constant is outside this draft's remit.",
+  "notes": "Workbook has an 'Information' sheet (title/guidance text, sheet name only), the main 'Income tax details' sheet (435 data rows; header in row 1) and a separate 'PRRT details' sheet (petroleum resource rent tax payers, 8 rows in discovery). Only the 'Income tax details' sheet is mapped here. 'PRRT details' has its own schema (Name, ABN, PRRT Payable $) and would need a second config. Income year mixes 2024-25 with a few prior-year comparatives. Column names contain a trailing ' $'.\n\n[ext-v1] The sheet is narrow: only six columns, and the approved mapping already covered Name -> entity.legal_name and ABN -> entity.abn, so this extension recovers the three financial measures that the record grain rationale had left unmapped. No new record roles are needed: one row is one legal entity's aggregate tax position for one income year, and the financials attach to the subject business. Income year is deliberately left unmapped as an attribute (see unmapped reason) but is load-bearing as the period qualifier - the file contains 2023-24 and 2022-23 comparative rows alongside 2024-25, so without the qualifier the same ABN could appear to hold two conflicting income figures. No approved base rules were edited; both approved rules are non-editable and passed the gate. No crosswalk tables were used: the source states no status code, legal form, industry activity or revenue band, and deriving a revenue band from the dollar amounts would be inference rather than source-stated fact. The approved constant address.country = AU is left untouched - the file carries no address, but the entity is AU-registered by ABN, and removing an approved constant is outside this draft's remit.\nLocal maintainer correction (no model API call): Remove address-country inference from ABN and tax jurisdiction; keep financial facts unchanged.",
   "observed_at": {
     "fallback": "resource_last_modified",
     "source_path": null,
```

## Interpretation dependencies

```json
{
  "firmable_ontology.yaml": "639b80ea6333146c7ac714cd940fcdf6b2945f451e95333b0be21174bedee5da",
  "config\\ontology_extensions.yaml": "61598d10cb0feb8f2de0daeb403bd68722ae4ef6beec5d758bd5ca3d5ad8a061",
  "firmable\\mapping\\engine.py": "42402ccfbfb5a896ef14f2405be8f27ebf3d428030c9a2c2ec214b1a30d9056b",
  "firmable\\mapping\\transforms.py": "9f96be7568e9693dee9a8f89303471ac3883e3ed5bccd748f259a24227886c65",
  "firmable\\crosswalk.py": "ef1a7479dbe2ea3a5bc5ac86ed49dac849bc0990c36ddd3401107d862d0634cf"
}
```