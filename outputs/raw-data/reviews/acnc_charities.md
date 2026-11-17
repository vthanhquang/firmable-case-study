# Local correction review: `acnc_charities`

Status: PENDING_REVIEW; human sign-off is still required.
Run: `20261117T041635-local-b7bddd8d`; config digest: `b7bddd8d303e91894a57c64492ff21696b9a360d0965b629d4178a51b6ea0a20`.
Original agent run: `20261112T222422-67b98b` (preserved).
Actor: Codex maintainer, at user request. Model calls: 0.

Keep register contact addresses on the company with explicit contact scope; reject country/state conflicts instead of creating establishments.

Validation: Frozen replay sample partition; not an unseen holdout. No new model critic was called.

## Regression findings

```json
[
  {
    "code": "SOME_ERRORS",
    "severity": "warning",
    "message": "3 values rejected: {'WEBSITE_INVALID': 3}",
    "target": "entity.website",
    "source_paths": [
      "Charity_Website"
    ],
    "examples": {
      "WEBSITE_INVALID": [
        "tielu124@gmail.com",
        "finaveukiso@gmail.com",
        "https://www.hollywoodprivate/Research Foundation/Research Foundation"
      ]
    }
  },
  {
    "code": "SOME_ERRORS",
    "severity": "warning",
    "message": "1 values rejected: {'POSTCODE_INVALID': 1}",
    "target": "address.postcode",
    "source_paths": [
      "Postcode"
    ],
    "examples": {
      "POSTCODE_INVALID": [
        "Cloverdale"
      ]
    }
  },
  {
    "code": "SOME_ERRORS",
    "severity": "warning",
    "message": "2 values rejected: {'COUNTRY_UNMAPPED': 1, 'COUNTRY_REGION_CONFLICT': 1}",
    "target": "address.country",
    "source_paths": [
      "Country",
      "State"
    ],
    "examples": {
      "COUNTRY_UNMAPPED": [
        "WA 6105"
      ],
      "COUNTRY_REGION_CONFLICT": [
        "Aruba|VIC"
      ]
    }
  }
]
```

## Exact mapping changes

```diff
--- previous agent proposal
+++ local corrected proposal
@@ -1,16 +1,6 @@
 {
   "constants": [],
-  "entities": {
-    "establishment": {
-      "key_paths": [
-        "ABN",
-        "Address_Line_1",
-        "Postcode"
-      ],
-      "kind": "establishment",
-      "rationale": "Address_Type is constant 'Business' on every row: these columns are the charity's registered business address, i.e. the premises it operates from, not the legal entity."
-    }
-  },
+  "entities": null,
   "extensions": "ext-v1",
   "fields": [
     {
@@ -131,7 +121,7 @@
       "when": null
     },
     {
-      "claim_scope": null,
+      "claim_scope": "charity_registration",
       "confidence": 0.9,
       "entity": null,
       "join_with": " ",
@@ -158,13 +148,13 @@
       "when": null
     },
     {
-      "claim_scope": null,
+      "claim_scope": "entity_contact_address",
       "confidence": 0.68,
-      "entity": "establishment",
+      "entity": null,
       "join_with": ", ",
       "one_hot": null,
       "qualifiers": null,
-      "rationale": "Street address lines combined; Address_Type is uniformly 'Business' and some values are PO boxes, so this is a business/contact address.",
+      "rationale": "ACNC register contact address; this does not establish operating premises.",
       "source_paths": [
         "Address_Line_1",
         "Address_Line_2",
@@ -195,13 +185,13 @@
       "when": null
     },
     {
-      "claim_scope": null,
+      "claim_scope": "entity_contact_address",
       "confidence": 0.92,
-      "entity": "establishment",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Town/city (suburb) field.",
+      "entity": null,
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "ACNC register contact address; this does not establish operating premises.",
       "source_paths": [
         "Town_City"
       ],
@@ -222,13 +212,13 @@
       "when": null
     },
     {
-      "claim_scope": null,
+      "claim_scope": "entity_contact_address",
       "confidence": 0.95,
-      "entity": "establishment",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Australian state abbreviations; state transform normalises and maps unknown to OTHER.",
+      "entity": null,
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "ACNC register contact address; this does not establish operating premises.",
       "source_paths": [
         "State"
       ],
@@ -245,13 +235,13 @@
       "when": null
     },
     {
-      "claim_scope": null,
+      "claim_scope": "entity_contact_address",
       "confidence": 0.9,
-      "entity": "establishment",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "4-digit Australian postcodes; one 6-digit source defect fails validation by design.",
+      "entity": null,
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "ACNC register contact address; this does not establish operating premises.",
       "source_paths": [
         "Postcode"
       ],
@@ -268,54 +258,27 @@
       "when": null
     },
     {
-      "claim_scope": null,
+      "claim_scope": "entity_contact_address",
       "confidence": 0.85,
-      "entity": "establishment",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Reviewer-directed fix. trim/collapse/upper, then strip trailing periods and spaces with regex_extract '^(.*?)[.\\s]*$' so 'Australia.' structurally reduces to 'AUSTRALIA' before lookup (general rule, not one hardcoded dotted key). map_enum(passthrough=true) maps 'AUSTRALIA'/'AU'/'AUS' -> 'AU' and passes any unlisted letter-only name (ARUBA, SINGAPORE) through unchanged as uppercase text, so genuine foreign countries are neither dropped nor guessed. A final regex_extract '^(\\D*)$' returns the value only when it contains no digits, so state+postcode mistypes such as 'WA 6105' become null instead of being emitted as a country; letter-only names are unaffected. 'default: null' is deliberately NOT used, since it would also null real foreign countries.",
-      "source_paths": [
-        "Country"
-      ],
-      "steps": [
-        {
-          "args": {},
-          "op": "trim"
-        },
-        {
-          "args": {},
-          "op": "collapse_whitespace"
-        },
-        {
-          "args": {},
-          "op": "upper"
-        },
-        {
-          "args": {
-            "group": 1,
-            "pattern": "^(.*?)[.\\s]*$"
-          },
-          "op": "regex_extract"
-        },
-        {
-          "args": {
-            "default": null,
-            "mapping": {
-              "AU": "AU",
-              "AUS": "AU",
-              "AUSTRALIA": "AU"
-            },
-            "passthrough": true
-          },
-          "op": "map_enum"
-        },
-        {
-          "args": {
-            "group": 1,
-            "pattern": "^(\\D*)$"
-          },
-          "op": "regex_extract"
+      "entity": null,
+      "join_with": "|",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "Normalize explicitly stated countries; reject a foreign country paired with an Australian state. Preserve rejected values in raw evidence.",
+      "source_paths": [
+        "Country",
+        "State"
+      ],
+      "steps": [
+        {
+          "args": {
+            "aliases": {
+              "ARUBA": "AW",
+              "AUSTRIA": "AT",
+              "SINGAPORE": "SG"
+            }
+          },
+          "op": "country_with_region"
         }
       ],
       "target": "address.country",
@@ -622,7 +585,7 @@
     }
   ],
   "grain_rationale": "One row per ACNC-registered charity; the record describes the registered legal entity and its registered business address. ABN is not guaranteed unique (duplicates/blanks occur), so record identity is content-derived.",
-  "notes": "Reviewer feedback addressed: address.country now uses map_enum with passthrough=true (no '__PASSTHROUGH__' sentinel); listed Australian spellings -> 'AU', other countries preserved as uppercase text. entity.status is NOT mapped: no per-row status column and the extract may include revoked charities, so asserting 'active' would be guesswork. entity_type not mapped: suffixes (Incorporated/Ltd/Trust) are name text, not a structured type field. Columns 29-69 are charitable-purpose/beneficiary Y/N flags with no ontology target. Some Other_Organisation_Names values are person-like (e.g. 'Shannon Schedlich'); trading_name confidence kept moderate for that reason. No per-row observation date; fallback to resource last-modified. Address is a business/contact address (Address_Type uniformly 'Business'), so address.full confidence is moderate. One 6-digit Postcode source defect fails validation by design.\n\n[ext-v1] Approved rules 5-9 (address.*) moved to the new establishment role because Address_Type is constant 'Business' (registered premises). ABN is not unique, so establishment key_paths include ABN plus address columns. entity.trading_name is dropped (editable rule 1) because the alias column mixes trading names with former legal names and cannot be classified by evidence; ext.entity.former_name is added in its place, emitting only the 'previously known as' segment. sector_tag uses map_enum over the publisher's purpose wording (scheme acnc_purpose): the acnc_purpose crosswalk op with one_hot produced only raw column names (key_label) or dropped all values (label), so it is not usable here; labels with internal commas were reworded with 'and' to avoid the delimiter lint false positive. Charity_Size has no per-row period, so revenue_band carries scheme only. Remaining forty beneficiary-type Y/N flag columns have no reviewed crosswalk table and are not asserted. Date_Organisation_Established is used only as date_established, never for registration status or validity.",
+  "notes": "Reviewer feedback addressed: address.country now uses map_enum with passthrough=true (no '__PASSTHROUGH__' sentinel); listed Australian spellings -> 'AU', other countries preserved as uppercase text. entity.status is NOT mapped: no per-row status column and the extract may include revoked charities, so asserting 'active' would be guesswork. entity_type not mapped: suffixes (Incorporated/Ltd/Trust) are name text, not a structured type field. Columns 29-69 are charitable-purpose/beneficiary Y/N flags with no ontology target. Some Other_Organisation_Names values are person-like (e.g. 'Shannon Schedlich'); trading_name confidence kept moderate for that reason. No per-row observation date; fallback to resource last-modified. Address is a business/contact address (Address_Type uniformly 'Business'), so address.full confidence is moderate. One 6-digit Postcode source defect fails validation by design.\n\n[ext-v1] Approved rules 5-9 (address.*) moved to the new establishment role because Address_Type is constant 'Business' (registered premises). ABN is not unique, so establishment key_paths include ABN plus address columns. entity.trading_name is dropped (editable rule 1) because the alias column mixes trading names with former legal names and cannot be classified by evidence; ext.entity.former_name is added in its place, emitting only the 'previously known as' segment. sector_tag uses map_enum over the publisher's purpose wording (scheme acnc_purpose): the acnc_purpose crosswalk op with one_hot produced only raw column names (key_label) or dropped all values (label), so it is not usable here; labels with internal commas were reworded with 'and' to avoid the delimiter lint false positive. Charity_Size has no per-row period, so revenue_band carries scheme only. Remaining forty beneficiary-type Y/N flag columns have no reviewed crosswalk table and are not asserted. Date_Organisation_Established is used only as date_established, never for registration status or validity.\nLocal maintainer correction (no model API call): Keep register contact addresses on the company with explicit contact scope; reject country/state conflicts instead of creating establishments.",
   "observed_at": {
     "fallback": "resource_last_modified",
     "source_path": null,
@@ -644,14 +607,7 @@
     "source_paths": [],
     "strategy": "content_hash"
   },
-  "relationships": [
-    {
-      "from_role": "subject",
-      "rationale": "The registered business address is a premises of the charity.",
-      "to_role": "establishment",
-      "type": "OPERATES_ESTABLISHMENT"
-    }
-  ],
+  "relationships": null,
   "source_id": "acnc_charities",
   "unmapped": [
     {
```

## Interpretation dependencies

```json
{
  "firmable_ontology.yaml": "639b80ea6333146c7ac714cd940fcdf6b2945f451e95333b0be21174bedee5da",
  "config\\ontology_extensions.yaml": "61598d10cb0feb8f2de0daeb403bd68722ae4ef6beec5d758bd5ca3d5ad8a061",
  "firmable\\mapping\\engine.py": "42402ccfbfb5a896ef14f2405be8f27ebf3d428030c9a2c2ec214b1a30d9056b",
  "firmable\\mapping\\transforms.py": "9f96be7568e9693dee9a8f89303471ac3883e3ed5bccd748f259a24227886c65",
  "firmable\\crosswalk.py": "ef1a7479dbe2ea3a5bc5ac86ed49dac849bc0990c36ddd3401107d862d0634cf",
  "config\\crosswalks\\acnc_size_2022.yaml": "0a2a3b7a1cea375dd681659b6d58817cf583315fa4aa95f6d4267f27667fd74b"
}
```