# Local correction review: `asic_companies`

Status: PENDING_REVIEW; human sign-off is still required.
Run: `20261117T041636-local-04fe946b`; config digest: `04fe946b4bbb6c1a60fe0bbf5f74f22cdf0e53ae4c267f956513e1088b9fa213`.
Original agent run: `20261112T204647-23688e` (preserved).
Actor: Codex maintainer, at user request. Model calls: 0.

Use corrected official subclass labels, withhold unverifiable meanings, and remove unsupported address-country default.

Validation: Frozen replay sample partition; not an unseen holdout. No new model critic was called.

## Regression findings

```json
[
  {
    "code": "VALUES_DROPPED",
    "severity": "warning",
    "message": "6 values deliberately discarded: {'CROSSWALK_NO_INFERENCE': 6}",
    "target": "ext.entity.legal_form_detail",
    "source_paths": [
      "Class"
    ]
  },
  {
    "code": "VALUES_DROPPED",
    "severity": "warning",
    "message": "6 values deliberately discarded: {'CROSSWALK_NO_INFERENCE': 6}",
    "target": "ext.entity.legal_form_detail",
    "source_paths": [
      "Sub Class"
    ]
  }
]
```

## Exact mapping changes

```diff
--- previous agent proposal
+++ local corrected proposal
@@ -1,12 +1,5 @@
 {
-  "constants": [
-    {
-      "confidence": 0.85,
-      "rationale": "Australian register of companies incorporated under the Corporations Act (ASIC); all discovery rows are AU registrations. Asserted from metadata rather than a source column, hence moderate confidence.",
-      "target": "address.country",
-      "value": "AU"
-    }
-  ],
+  "constants": [],
   "entities": null,
   "extensions": "ext-v1",
   "fields": [
@@ -15,6 +8,7 @@
       "confidence": 0.9,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "On the current-name row (Current Name Indicator='Y', 301/473 rows) 'Company Name' is the registered company name and 'Current Name' is blank. Names are space-padded to ~100 chars, hence collapse_whitespace+trim.",
       "source_paths": [
@@ -57,6 +51,7 @@
       "confidence": 0.85,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "On rows without the current-name indicator, 'Current Name' is populated (172/473) and holds the company's current registered name, e.g. BRITAX STEELCRAFT PTY. LTD. -> BRITAX CHILDCARE PTY LTD. Verified on the header sample: rows where Indicator='Y' always have Current Name blank, and rows where Indicator is blank always have Current Name populated. The two legal_name rules are complementary, so each row emits exactly one legal_name and a company's current name is still recoverable if its Indicator='Y' row were absent from an extract.",
       "source_paths": [
@@ -99,6 +94,7 @@
       "confidence": 0.97,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Column 'ACN' is 9 digits on 100% of rows and passes the ACN checksum on 473/473 discovery rows; uses the acn transform, never derived from ABN.",
       "source_paths": [
@@ -125,6 +121,7 @@
       "confidence": 0.9,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Column 'ABN' is 11 digits on 69.3% of rows and passes the ABN checksum at exactly the same 69.3% rate; the remaining values are the literal placeholder '0' (145/473) meaning no ABN recorded, null_if'd away so the checksum transform only sees real ABNs.",
       "source_paths": [
@@ -161,6 +158,7 @@
       "confidence": 0.8,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Column 'Type' states the ASIC company type explicitly (APTY = Australian proprietary company 458, APUB = Australian public company 15 in discovery). APTY/APUB/FNOS/NONC are all bodies registered as companies under the Corporations Act -> 'company'. Any other code falls through to 'unknown' rather than being guessed.",
       "source_paths": [
@@ -195,6 +193,7 @@
       "confidence": 0.9,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Only statuses with an unambiguous ontology equivalent are mapped: REGD = registered -> active (435/473), DRGD = deregistered -> deregistered (28/473). EXAD (external administration, which may be voluntary administration or receivership rather than liquidation) and SOFF (strike-off action in progress, company still registered) have no exact enum equivalent and are deliberately mapped to 'unknown' rather than guessed.",
       "source_paths": [
@@ -227,6 +226,7 @@
       "confidence": 0.95,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "All discovery values match shape 99/99/9999 and are day-first Australian dates (e.g. 22/12/1986); parse as %d/%m/%Y.",
       "source_paths": [
@@ -257,6 +257,7 @@
       "confidence": 0.8,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "ASIC company type code (APTY=proprietary, APUB=public, FNOS=foreign, RACN=registrable Australian body, CCIV=corporate collective investment vehicle, NONC=no-liability). Profiled values are exactly keys of asic_company_type.",
       "source_paths": [
@@ -286,6 +287,7 @@
       "confidence": 0.75,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Class holds the share/guarantee structure (LMSH=limited by shares, LMGT=limited by guarantee) which entity_type flattens to 'company'. Keys match the source values; code retained in key_label.",
       "source_paths": [
@@ -315,6 +317,7 @@
       "confidence": 0.7,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Sub Class carries the finer ASIC structure (PROP, LIST, PSTC, LISN, ULST...). Crosswalk keys are this source's raw values; target is multi-valued so Class and Sub Class are separate observations. Labels are draft/AI-guessed; concept fit is accepted by the critic.",
       "source_paths": [
@@ -344,6 +347,7 @@
       "confidence": 0.85,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "entity.status is coarse and hides distress codes (EXAD external administration, SOFF strike-off). asic_company_status keys are exactly this column's values.",
       "source_paths": [
@@ -373,6 +377,7 @@
       "confidence": 0.8,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Column names the state register in which the company was originally registered; ext.entity.prior_registration_state is defined as exactly that and explicitly not an address.",
       "source_paths": [
@@ -403,6 +408,7 @@
       "confidence": 0.85,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Legacy state-registry number (shapes like C0268163E and 8-digit numerics; ACN checksum passes by chance on only 13.5%). Must not be parsed as an ACN.",
       "source_paths": [
@@ -433,6 +439,7 @@
       "confidence": 0.8,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "On a former-name row (Current Name Indicator != 'Y'), Company Name is the superseded registered name, not a trading name; legal_name comes from Company Name only on the 'Y' row, so there is no collision. Current Name Start Date dates the later name's commencement and cannot be assigned as this former name's valid_from or valid_to when a company has several former-name rows, so the claim is emitted without a validity path.",
       "source_paths": [
@@ -466,7 +473,7 @@
     }
   ],
   "grain_rationale": "One row is one registered company name held by a company. Companies with previous names appear on multiple rows sharing the same ACN; on exactly one row per company 'Current Name Indicator' = 'Y' and 'Company Name' holds the current registered name, while on the other rows 'Company Name' holds a former registered name and 'Current Name' holds the then-current name. Because 'Current Name' carries a value only on the former-name rows, the current registered name is recoverable from BOTH row types: Company Name (when Indicator='Y') or Current Name (when Indicator is not 'Y'). Each row therefore yields at most one legal_name observation for the company; former registered names are NOT emitted as trading names (they are superseded legal names, not declared business/trading names). Per-company attributes (ACN, ABN, type, status, registration date) are identical across a company's rows and are mapped from every row.",
-  "notes": "ZIP member COMPANY_202611.csv: UTF-8 with BOM, TAB-delimited (14 tabs/line), one header row, 15 columns. Names are space-padded to ~100 chars -> collapse_whitespace+trim. ABN uses '0' as a missing sentinel (145/473). Name-history structure: multiple rows per ACN; legal_name comes from Company Name when Current Name Indicator='Y' and from Current Name when the indicator is blank, so each row contributes exactly one current registered name and no superseded name is emitted as trading_name (entity.trading_name is intentionally not populated - this register holds no declared business/trading names). valid_from = Current Name Start Date where present, else Date of Registration. entity.status maps only REGD/DRGD; EXAD and SOFF -> unknown by design. observed_at is not stated in the file, so resource_last_modified is used. address.full/locality/postcode are not present in this source.\n\n[ext-v1] Adds ASIC's own schema detail to the extension registry (Type -> legal_form, Class + Sub Class -> legal_form_detail as two multi-valued observations, Status -> status_detail) plus the two prior-registration columns and former legal names. Fixes the critic's 'wrong' verdict: former name is Company Name on non-'Y' rows (never Current Name, which is the later name and would collide with legal_name), emitted without a validity path because Current Name Start Date dates a different claim. The record is a company (business role); no entities/relationships are declared. Base edits limited to removing the three ignored legacy observation.valid_* rules (7, 8, 9). All four crosswalk tables used are marked 'draft - prepared by an AI assistant'; the asic_company_subclass labels are AI-guessed (critic: doubtful) and need verification against ASIC's data dictionary before relying on finer sub-class detail.",
+  "notes": "ZIP member COMPANY_202611.csv: UTF-8 with BOM, TAB-delimited (14 tabs/line), one header row, 15 columns. Names are space-padded to ~100 chars -> collapse_whitespace+trim. ABN uses '0' as a missing sentinel (145/473). Name-history structure: multiple rows per ACN; legal_name comes from Company Name when Current Name Indicator='Y' and from Current Name when the indicator is blank, so each row contributes exactly one current registered name and no superseded name is emitted as trading_name (entity.trading_name is intentionally not populated - this register holds no declared business/trading names). valid_from = Current Name Start Date where present, else Date of Registration. entity.status maps only REGD/DRGD; EXAD and SOFF -> unknown by design. observed_at is not stated in the file, so resource_last_modified is used. address.full/locality/postcode are not present in this source.\n\n[ext-v1] Adds ASIC's own schema detail to the extension registry (Type -> legal_form, Class + Sub Class -> legal_form_detail as two multi-valued observations, Status -> status_detail) plus the two prior-registration columns and former legal names. Fixes the critic's 'wrong' verdict: former name is Company Name on non-'Y' rows (never Current Name, which is the later name and would collide with legal_name), emitted without a validity path because Current Name Start Date dates a different claim. The record is a company (business role); no entities/relationships are declared. Base edits limited to removing the three ignored legacy observation.valid_* rules (7, 8, 9). All four crosswalk tables used are marked 'draft - prepared by an AI assistant'; the asic_company_subclass labels are AI-guessed (critic: doubtful) and need verification against ASIC's data dictionary before relying on finer sub-class detail.\nLocal maintainer correction (no model API call): Use corrected official subclass labels, withhold unverifiable meanings, and remove unsupported address-country default.",
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
  "firmable\\crosswalk.py": "ef1a7479dbe2ea3a5bc5ac86ed49dac849bc0990c36ddd3401107d862d0634cf",
  "config\\crosswalks\\asic_company_class.yaml": "a81124796a88a9741e86afb103c6a954654403924c5e37427538a401bd8ce72a",
  "config\\crosswalks\\asic_company_status.yaml": "07d1d7a0a48933fc699da59eb6609611e4c52afbcf407f07fa3a465a141e701b",
  "config\\crosswalks\\asic_company_subclass.yaml": "0b7c580046b281c13fdf57696ddf49bcd8751a4aa71a3b2f7d69fc13a83d3fd1",
  "config\\crosswalks\\asic_company_type.yaml": "009afee3f0b56269097c5de492652da735f381f8f18008c6a2552ab38f464ddc"
}
```