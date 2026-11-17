# Local correction review: `dewr_employment_providers`

Status: PENDING_REVIEW; human sign-off is still required.
Run: `20261117T041637-local-69d5c4f1`; config digest: `69d5c4f153ea76f9d4c7c7b6575d60fb7c3746423896e00abf5e16c163ad5166`.
Original agent run: `20261112T205520-8b2f15` (preserved).
Actor: Codex maintainer, at user request. Model calls: 0.

Place country on the establishment address, consistent with all other site fields.

Validation: Frozen replay sample partition; not an unseen holdout. No new model critic was called.

## Regression findings

```json
[
  {
    "code": "VALUES_DROPPED",
    "severity": "warning",
    "message": "486 values deliberately discarded: {'PERSONAL_MAILBOX_DROPPED': 486}",
    "target": "ext.contact.role_email",
    "source_paths": [
      "SITE_EMAIL_ADDRESS"
    ]
  },
  {
    "code": "VALUES_DROPPED",
    "severity": "warning",
    "message": "89 values deliberately discarded: {'PHONE_INCOMPLETE': 89}",
    "target": "ext.contact.phone",
    "source_paths": [
      "SITE_CONTACT_PHONE",
      "SITE_STATE_CD"
    ]
  },
  {
    "code": "VALUES_DROPPED",
    "severity": "warning",
    "message": "71 values deliberately discarded: {'PHONE_INCOMPLETE': 71}",
    "target": "ext.contact.phone",
    "source_paths": [
      "PHONE_NUMBER",
      "SITE_STATE_CD"
    ]
  },
  {
    "code": "VALUES_DROPPED",
    "severity": "warning",
    "message": "38 values deliberately discarded: {'PHONE_INCOMPLETE': 38}",
    "target": "ext.contact.phone",
    "source_paths": [
      "AGENT_FREECALL_NUM",
      "SITE_STATE_CD"
    ]
  }
]
```

## Exact mapping changes

```diff
--- previous agent proposal
+++ local corrected proposal
@@ -1,8 +1,10 @@
 {
   "constants": [
     {
+      "claim_scope": "establishment_address",
       "confidence": 0.85,
-      "rationale": "Australian Government employment services provider register; all states are AU codes and all postcodes are AU.",
+      "entity": "establishment",
+      "rationale": "Metadata default for the evidenced Australian site/premises only, never the subject company or correspondence address.",
       "target": "address.country",
       "value": "AU"
     }
@@ -23,6 +25,7 @@
       "confidence": 0.72,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "SITE_NAME holds the provider's operating/brand name as delivered at this site (196 distinct values, e.g. 'MAX Employment', 'Advanced Personnel Management (APM)', 'Job Centre Australia'), not a registered legal name; trading_name is the safe target. Placeholders treated as missing.",
       "source_paths": [
@@ -65,6 +68,7 @@
       "confidence": 0.8,
       "entity": null,
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Provider website; 57.6% present, values are domains/URLs (www.*, http://*).",
       "source_paths": [
@@ -107,6 +111,7 @@
       "confidence": 0.85,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Street address line of the site (e.g. '2nd Floor 22 East Row'); locality is a separate column. Placeholder strings (TBA/TBC/N/A/-/.) are treated as missing per reviewer feedback.",
       "source_paths": [
@@ -150,6 +155,7 @@
       "confidence": 0.9,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Suburb/locality name (412 distinct AU localities, e.g. WOY WOY, CHATSWOOD). Placeholders treated as missing.",
       "source_paths": [
@@ -193,6 +199,7 @@
       "confidence": 0.95,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Explicit 8-value AU state code column (NSW/VIC/QLD/SA/WA/TAS/ACT/NT), all 2-letter abbreviations, 100% present.",
       "source_paths": [
@@ -236,6 +243,7 @@
       "confidence": 0.9,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "4-digit AU postcodes plus 13 three-digit values (NT-style, e.g. 0822 stored as 822) which the postcode transform re-pads.",
       "source_paths": [
@@ -279,6 +287,7 @@
       "confidence": 0.95,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Publisher-assigned site code; stable key for the establishment across snapshots.",
       "source_paths": [
@@ -314,6 +323,7 @@
       "confidence": 0.95,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "DEWR employment-services contract/programme code delivered at this site (DESB, EPS5, DESA, TTW5, RJCP, NEI5, SPP5, HLS5). A site attribute, not a business identifier.",
       "source_paths": [
@@ -345,6 +355,7 @@
       "confidence": 0.9,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "ESA_CD_1 is the Employment Services Area code of the contract (142 distinct, e.g. 5SYN, 5ACT); the ontology names 'employment services area' as an example of a publisher region for an establishment.",
       "source_paths": [
@@ -376,6 +387,7 @@
       "confidence": 0.95,
       "entity": "establishment",
       "join_with": ",",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Published decimal latitude/longitude of the site; the literal NULL (7 rows) is handled as missing by geo_point.",
       "source_paths": [
@@ -399,6 +411,7 @@
       "confidence": 0.85,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Domain of the published site contact email. Only the domain is kept, so the personal local part is never stored.",
       "source_paths": [
@@ -434,6 +447,7 @@
       "confidence": 0.8,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Role mailboxes published for the site (enquiries@, info@); the transform drops personal mailboxes. Held-out data confirms role mailboxes do occur (100 emitted of 814 present).",
       "source_paths": [
@@ -469,6 +483,7 @@
       "confidence": 0.75,
       "entity": "establishment",
       "join_with": "|",
+      "one_hot": null,
       "qualifiers": {
         "role": {
           "source_path": null,
@@ -514,6 +529,7 @@
       "confidence": 0.75,
       "entity": "establishment",
       "join_with": "|",
+      "one_hot": null,
       "qualifiers": {
         "role": {
           "source_path": null,
@@ -559,6 +575,7 @@
       "confidence": 0.7,
       "entity": "establishment",
       "join_with": "|",
+      "one_hot": null,
       "qualifiers": {
         "role": {
           "source_path": null,
@@ -604,6 +621,7 @@
       "confidence": 0.9,
       "entity": "establishment",
       "join_with": " ",
+      "one_hot": null,
       "qualifiers": null,
       "rationale": "Registrable host of the published site website, without scheme or www.",
       "source_paths": [
@@ -636,7 +654,7 @@
     }
   ],
   "grain_rationale": "One row is a provider service SITE (a physical office of an employment-services provider) delivering a given CONTRACT (e.g. DESB, DESA, EPS5, RJCP) at a given location. The business participant is the provider named in SITE_NAME; its location, state, postcode and web attributes are mapped. DIS_SITE_CODE identifies the site/contract row, not a business registration, and is not mapped as a business identifier.",
-  "notes": "Row = provider site x contract. No ABN/ACN/NZBN column exists, so no business identifier is emitted. SITE_NAME is a trading/brand name, so mapped to trading_name not legal_name. Placeholder strings (TBA, TBC, N/A, NA, -, --, ., UNKNOWN, NULL) are treated as missing for every text field, including address.full, per reviewer feedback. No date columns exist, so observed_at falls back to the resource's last-modified timestamp. All text is untrusted data; no instructions were found in it.\n\n[ext-v1] Revision after critic review. The critic's single 'wrong' verdict (rule 4, ext.entity.industry_code from CONTRACT_NAME) is fixed by DROPPING that rule: CONTRACT_NAME is a government programme code, not evidence of the provider's ANZSIC activity, the anzsic_dewr_program crosswalk is an unreviewed draft with no publisher evidence and inconsistent output, and the same column is already correctly mapped as ext.establishment.program. The 'doubtful' role_email rule is kept because held-out data confirms role mailboxes genuinely occur (100 emitted of 814 present). All other rules are unchanged and were judged ok. The four approved address.* rules remain moved to the establishment role via base_rule_edits. Source-data errors (GEO_OUTSIDE_AU, EMAIL_INVALID, DOMAIN_INVALID, WEBSITE_INVALID) are correctly rejected by the transforms and are not mapping errors.",
+  "notes": "Row = provider site x contract. No ABN/ACN/NZBN column exists, so no business identifier is emitted. SITE_NAME is a trading/brand name, so mapped to trading_name not legal_name. Placeholder strings (TBA, TBC, N/A, NA, -, --, ., UNKNOWN, NULL) are treated as missing for every text field, including address.full, per reviewer feedback. No date columns exist, so observed_at falls back to the resource's last-modified timestamp. All text is untrusted data; no instructions were found in it.\n\n[ext-v1] Revision after critic review. The critic's single 'wrong' verdict (rule 4, ext.entity.industry_code from CONTRACT_NAME) is fixed by DROPPING that rule: CONTRACT_NAME is a government programme code, not evidence of the provider's ANZSIC activity, the anzsic_dewr_program crosswalk is an unreviewed draft with no publisher evidence and inconsistent output, and the same column is already correctly mapped as ext.establishment.program. The 'doubtful' role_email rule is kept because held-out data confirms role mailboxes genuinely occur (100 emitted of 814 present). All other rules are unchanged and were judged ok. The four approved address.* rules remain moved to the establishment role via base_rule_edits. Source-data errors (GEO_OUTSIDE_AU, EMAIL_INVALID, DOMAIN_INVALID, WEBSITE_INVALID) are correctly rejected by the transforms and are not mapping errors.\nLocal maintainer correction (no model API call): Place country on the establishment address, consistent with all other site fields.",
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