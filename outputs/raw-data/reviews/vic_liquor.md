# Local correction review: `vic_liquor`

Status: PENDING_REVIEW; human sign-off is still required.
Run: `20261117T041638-local-45736cb6`; config digest: `45736cb670d75219d42759bf6e9d98722f58372a003624f6b1affaedb2a4024a`.
Original agent run: `20261112T210805-b6050a` (preserved).
Actor: Codex maintainer, at user request. Model calls: 0.

Place VIC/AU defaults on licensed premises, not the licensee correspondence address.

Validation: Frozen replay sample partition; not an unseen holdout. No new model critic was called.

## Regression findings

```json
[]
```

## Exact mapping changes

```diff
--- previous agent proposal
+++ local corrected proposal
@@ -1,14 +1,18 @@
 {
   "constants": [
     {
+      "claim_scope": "licensed_premises",
       "confidence": 0.9,
-      "rationale": "Victorian liquor licence register published by Liquor Control Victoria; licensed premises are in Victoria.",
+      "entity": "premises",
+      "rationale": "Metadata default for the evidenced Australian site/premises only, never the subject company or correspondence address.",
       "target": "address.state",
       "value": "VIC"
     },
     {
+      "claim_scope": "licensed_premises",
       "confidence": 0.9,
-      "rationale": "Australian (Victorian) register.",
+      "entity": "premises",
+      "rationale": "Metadata default for the evidenced Australian site/premises only, never the subject company or correspondence address.",
       "target": "address.country",
       "value": "AU"
     }
@@ -38,6 +42,7 @@
       "confidence": 0.6,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Column headed 'Licensee' = holder of the licence, mostly in legal-name form (PTY LTD / LIMITED / CITY OF X). Also carries officer/contact-role strings such as 'THE SECRETARY' and c/- address forms, which are gated out to null; corporate and sole-trader licensee names are kept. Confidence 0.6 reflects the mixed column.",
       "source_paths": [
@@ -104,6 +109,7 @@
       "confidence": 0.85,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "'Trading As' is explicitly the business/trading name, distinct from the licensee column (451 distinct of 465, 99.1% present). Placeholder strings nulled.",
       "source_paths": [
@@ -159,6 +165,7 @@
       "confidence": 0.85,
       "entity": "premises",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Street address of the licensed premises (present 94.2%). Premises address, not postal.",
       "source_paths": [
@@ -213,6 +220,7 @@
       "confidence": 0.85,
       "entity": "premises",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Suburb of the licensed premises (95.7% present). 7 records carry the placeholder '[Not applicable] -' (remote/pre-retail sellers without premises, shape '[a a] -'); after upper+trim the '[NOT APPLICABLE] -' gate nulls these so no bogus locality is emitted.",
       "source_paths": [
@@ -279,6 +287,7 @@
       "confidence": 0.85,
       "entity": "premises",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Premises postcode; 438 4-digit values plus 7 placeholder '0' values which are nulled. Postal postcodes are not used here (some are interstate, e.g. '2000').",
       "source_paths": [
@@ -325,6 +334,7 @@
       "confidence": 0.95,
       "entity": "licence",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Publisher-assigned licence number, unique per row (465/465 distinct, 8-digit).",
       "source_paths": [
@@ -342,6 +352,7 @@
       "confidence": 0.95,
       "entity": "licence",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "13 publisher licence categories kept in the publisher's wording on the licence role (Restaurant and cafe Licence 146, Limited Licence 75, General Licence 48, On-Premises 44, Packaged Liquor 36, Pre-retail 28, ...).",
       "source_paths": [
@@ -377,6 +388,7 @@
       "confidence": 0.85,
       "entity": "premises",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Published maximum patron count for the premises (60.2% present, all integer shapes 99/999/9999); blanks dropped.",
       "source_paths": [
@@ -415,6 +427,7 @@
       "confidence": 0.9,
       "entity": "premises",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Local government area of the licensed premises (74 distinct council names, 96.3% present).",
       "source_paths": [
@@ -455,6 +468,7 @@
       "confidence": 0.85,
       "entity": "premises",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Publisher's licensing region for the premises (11 values: Metro North/South/East/West, Barwon South-West, Hume, ...), 96.3% present.",
       "source_paths": [
@@ -493,6 +507,7 @@
       "confidence": 0.7,
       "entity": "premises",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Second publisher region label per site (Metro 286 / Regional 179); ext.establishment.region is multi-valued so this is one more value per observation.",
       "source_paths": [
@@ -527,6 +542,7 @@
       "confidence": 0.85,
       "entity": "premises",
       "join_with": ",",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Latitude first then longitude joined with ','; 94% present, remaining are missing coordinates.",
       "source_paths": [
@@ -554,6 +570,7 @@
       "confidence": 0.8,
       "entity": "subject",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "The licensee's postal mailing address is the subject's correspondence address; claim_scope keeps it separate from the establishment address so one record never claims two premises addresses.",
       "source_paths": [
@@ -589,6 +606,7 @@
       "confidence": 0.75,
       "entity": "subject",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Postal suburb of the correspondence address; 7 rows carry an interstate suffix (e.g. 'SYDNEY NSW') which the regex strips to the locality.",
       "source_paths": [
@@ -635,6 +653,7 @@
       "confidence": 0.8,
       "entity": "subject",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Postal postcode of the correspondence address, including interstate codes (e.g. 2000, 7 rows); all 465 values are 4 digits.",
       "source_paths": [
@@ -667,7 +686,7 @@
     }
   ],
   "grain_rationale": "Each row is one current Victorian liquor licence (Licence Number unique per row) held by a licensee at licensed premises. Entity fields describe the licensee business; address fields describe the licensed premises ONLY. The licensee's postal mailing address columns are left unmapped because they describe a different location than the premises and mixing them into the same address fields would make each record claim two different addresses.",
-  "notes": "XLSX: 4 title/branding rows precede the header (skip_rows=4); sheet 'Current_Victorian_Licences_By_L'; 465 data rows, 21 columns incl. two pairs of empty spacer columns. Sheet subtitle states 'Current Victorian Liquor Licences as of 31/08/2026' - a snapshot date, not per-record; observed_at falls back to dataset metadata. Nothing in the data changes per record over time, so address columns need no validity dates. No ABN/ACN column: Licence Number is 8-digit (ABN checksum 0%, ACN checksum 9.2% = chance) - deliberately unmapped. entity_type unmapped (no column states legal entity type). REVISION 3: adopts the reviewer's approved scope unchanged (premises address only; ALL postal columns unmapped) and adds ONLY the placeholder handling: '[Not applicable] -' in Suburb (7 rows, shape '[a a] -') is upper-cased and gated out at address.locality; the same '[NOT APPLICABLE] -' placeholder is nulled in address.full and the '0' postcodes in address.postcode so no placeholder value can be emitted.\n\n[ext-v1] Revision 2. Kept every rule from draft 1 that the data supports. No ext.entity.industry_code rule on Licence Category in this revision: the v2 anzsic_vic_liquor_category table's keys do cover all 13 categories in this file, and its 4 code-bearing groups (restaurant/cafe, packaged liquor, clubs, producers, late-night venues) are genuine activity evidence, but the table is still 'draft - L2 judgement crosswalk, needs a human reviewer' and 5 of the 13 categories (General, On-Premises, BYO, Remote Seller's, Pre-retail, Limited) would yield no code at all, so coverage is uneven. Recommend adding the rule with scheme anzsic2006 once a human signs the table off. Trading Hours stays unmapped because 136 of 465 values repeat the licence category; the rest are coarse trading bands. The three approved address rules were re-roled to premises (establishment), per the rule that a premises address describes the establishment.",
+  "notes": "XLSX: 4 title/branding rows precede the header (skip_rows=4); sheet 'Current_Victorian_Licences_By_L'; 465 data rows, 21 columns incl. two pairs of empty spacer columns. Sheet subtitle states 'Current Victorian Liquor Licences as of 31/08/2026' - a snapshot date, not per-record; observed_at falls back to dataset metadata. Nothing in the data changes per record over time, so address columns need no validity dates. No ABN/ACN column: Licence Number is 8-digit (ABN checksum 0%, ACN checksum 9.2% = chance) - deliberately unmapped. entity_type unmapped (no column states legal entity type). REVISION 3: adopts the reviewer's approved scope unchanged (premises address only; ALL postal columns unmapped) and adds ONLY the placeholder handling: '[Not applicable] -' in Suburb (7 rows, shape '[a a] -') is upper-cased and gated out at address.locality; the same '[NOT APPLICABLE] -' placeholder is nulled in address.full and the '0' postcodes in address.postcode so no placeholder value can be emitted.\n\n[ext-v1] Revision 2. Kept every rule from draft 1 that the data supports. No ext.entity.industry_code rule on Licence Category in this revision: the v2 anzsic_vic_liquor_category table's keys do cover all 13 categories in this file, and its 4 code-bearing groups (restaurant/cafe, packaged liquor, clubs, producers, late-night venues) are genuine activity evidence, but the table is still 'draft - L2 judgement crosswalk, needs a human reviewer' and 5 of the 13 categories (General, On-Premises, BYO, Remote Seller's, Pre-retail, Limited) would yield no code at all, so coverage is uneven. Recommend adding the rule with scheme anzsic2006 once a human signs the table off. Trading Hours stays unmapped because 136 of 465 values repeat the licence category; the rest are coarse trading bands. The three approved address rules were re-roled to premises (establishment), per the rule that a premises address describes the establishment.\nLocal maintainer correction (no model API call): Place VIC/AU defaults on licensed premises, not the licensee correspondence address.",
   "observed_at": {
     "fallback": "dataset_metadata_modified",
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