# Local correction review: `asic_credit_licensees`

Status: PENDING_REVIEW; human sign-off is still required.
Run: `20261117T041636-local-4b724c4f`; config digest: `4b724c4f9636b1e38c53a66d6ee0648966cfe9ddec99da7b44ae1e343bc36047`.
Original agent run: `20261112T205520-34807e` (preserved).
Actor: Codex maintainer, at user request. Model calls: 0.

Preserve complete authorisation text and licence dates; omit coordinates whose location precision is unverified.

Validation: Frozen replay sample partition; not an unseen holdout. No new model critic was called.

## Regression findings

```json
[]
```

## Exact mapping changes

```diff
--- previous agent proposal
+++ local corrected proposal
@@ -1,19 +1,25 @@
 {
   "constants": [
     {
+      "claim_scope": null,
       "confidence": 0.9,
+      "entity": null,
       "rationale": "ASIC Australian credit licence register; all localities/states are Australian.",
       "target": "address.country",
       "value": "AU"
     },
     {
+      "claim_scope": null,
       "confidence": 0.5,
+      "entity": null,
       "rationale": "The only status evidence is CRED_LIC_STATUS='APPR', a licence-approval code, not a company status (active/deregistered/liquidated/suspended). Conflating them would overstate knowledge, so entity.status is left unknown.",
       "target": "entity.status",
       "value": "unknown"
     },
     {
+      "claim_scope": null,
       "confidence": 0.3,
+      "entity": null,
       "rationale": "No explicit entity-type column; names suggest companies but many licensees are individuals/trusts, so left as unknown.",
       "target": "entity.entity_type",
       "value": "unknown"
@@ -257,19 +263,176 @@
     },
     {
       "claim_scope": null,
+      "confidence": 0.95,
+      "entity": "licence",
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "Publisher-assigned credit licence number, unique per row and stated on 100% of rows; identifies the licence across snapshots.",
+      "source_paths": [
+        "CRED_LIC_NUM"
+      ],
+      "steps": [
+        {
+          "args": {},
+          "op": "trim"
+        }
+      ],
+      "target": "ext.licence.number",
+      "valid_from_path": null,
+      "valid_to_path": null,
+      "validity_date_formats": null,
+      "when": null
+    },
+    {
+      "claim_scope": null,
       "confidence": 0.85,
-      "entity": null,
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Licence start date, all values DD/MM/YYYY (day-first; values like 21/12/2010 and 28/02/2011 confirm day-first).",
+      "entity": "licence",
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "CRED_LIC_STATUS is the licence approval status code (APPR on 464/464 discovery rows). It is licence status, not company status, so it must not go to entity.status. Kept as the raw publisher code because the only reviewed ASIC status table (asic_company_status) holds company codes, not credit-licence codes. No valid_from is attached: the publisher dates the licence start, not the status.",
+      "source_paths": [
+        "CRED_LIC_STATUS"
+      ],
+      "steps": [
+        {
+          "args": {},
+          "op": "trim"
+        }
+      ],
+      "target": "ext.licence.status",
+      "valid_from_path": null,
+      "valid_to_path": null,
+      "validity_date_formats": null,
+      "when": null
+    },
+    {
+      "claim_scope": null,
+      "confidence": 0.9,
+      "entity": "licence",
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "External dispute-resolution scheme membership published for the licence; single codes or tilde lists (AFCA, COSL, AFCA~COSL, FOS, AFCA~FOS, AFCA~COSL~FOS), so one scheme per observation.",
+      "source_paths": [
+        "CRED_LIC_EDRS"
+      ],
+      "steps": [
+        {
+          "args": {},
+          "op": "trim"
+        },
+        {
+          "args": {
+            "sep": "~"
+          },
+          "op": "split"
+        },
+        {
+          "args": {},
+          "op": "trim"
+        },
+        {
+          "args": {
+            "values": [
+              ""
+            ]
+          },
+          "op": "null_if"
+        }
+      ],
+      "target": "ext.licence.edr_scheme",
+      "valid_from_path": null,
+      "valid_to_path": null,
+      "validity_date_formats": null,
+      "when": null
+    },
+    {
+      "claim_scope": null,
+      "confidence": 0.6,
+      "entity": "licence",
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "Complete unparsed publisher permission text, preserving headings and conditions without asserting separate activities.",
+      "source_paths": [
+        "CRED_LIC_AUTHORISATIONS"
+      ],
+      "steps": [
+        {
+          "args": {},
+          "op": "trim"
+        }
+      ],
+      "target": "ext.licence.authorisation_text",
+      "valid_from_path": null,
+      "valid_to_path": null,
+      "validity_date_formats": null,
+      "when": null
+    },
+    {
+      "claim_scope": null,
+      "confidence": 0.4,
+      "entity": "licence",
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "Dated licence status-history entries (e.g. 'Licensee contravenes a licence condition 02/01/2013 ...', 'Suspended at the request of Licensee/Registrant 19/09/2016 31/01/2017') belong on the licence as status events, not on the business. Blank on most rows; the populated values are genuine dated licence events, kept as published.",
+      "source_paths": [
+        "CRED_LIC_STATUS_HISTORY"
+      ],
+      "steps": [
+        {
+          "args": {},
+          "op": "trim"
+        },
+        {
+          "args": {
+            "values": [
+              ""
+            ]
+          },
+          "op": "null_if"
+        },
+        {
+          "args": {
+            "sep": "~"
+          },
+          "op": "split"
+        },
+        {
+          "args": {},
+          "op": "trim"
+        }
+      ],
+      "target": "ext.licence.status_event",
+      "valid_from_path": null,
+      "valid_to_path": null,
+      "validity_date_formats": null,
+      "when": null
+    },
+    {
+      "claim_scope": null,
+      "confidence": 0.95,
+      "entity": "licence",
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "Explicit publisher licence date, not a company registration or lifetime date.",
       "source_paths": [
         "CRED_LIC_START_DT"
       ],
       "steps": [
         {
-          "args": {},
-          "op": "trim"
+          "args": {
+            "values": [
+              "",
+              "0",
+              "NULL"
+            ]
+          },
+          "op": "null_if"
         },
         {
           "args": {
@@ -280,33 +443,30 @@
           "op": "parse_date"
         }
       ],
-      "target": "observation.valid_from",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.7,
-      "entity": null,
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Licence end date in DD/MM/YYYY; empty on all discovery rows (current licences) so valid_to is null = still current.",
+      "target": "ext.licence.start_date",
+      "valid_from_path": null,
+      "valid_to_path": null,
+      "validity_date_formats": null,
+      "when": null
+    },
+    {
+      "claim_scope": null,
+      "confidence": 0.95,
+      "entity": "licence",
+      "join_with": " ",
+      "one_hot": null,
+      "qualifiers": null,
+      "rationale": "Explicit publisher licence date, not a company registration or lifetime date.",
       "source_paths": [
         "CRED_LIC_END_DT"
       ],
       "steps": [
-        {
-          "args": {},
-          "op": "trim"
-        },
         {
           "args": {
             "values": [
               "",
-              "0"
+              "0",
+              "NULL"
             ]
           },
           "op": "null_if"
@@ -320,224 +480,7 @@
           "op": "parse_date"
         }
       ],
-      "target": "observation.valid_to",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.95,
-      "entity": "licence",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Publisher-assigned credit licence number, unique per row and stated on 100% of rows; identifies the licence across snapshots.",
-      "source_paths": [
-        "CRED_LIC_NUM"
-      ],
-      "steps": [
-        {
-          "args": {},
-          "op": "trim"
-        }
-      ],
-      "target": "ext.licence.number",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.85,
-      "entity": "licence",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "CRED_LIC_STATUS is the licence approval status code (APPR on 464/464 discovery rows). It is licence status, not company status, so it must not go to entity.status. Kept as the raw publisher code because the only reviewed ASIC status table (asic_company_status) holds company codes, not credit-licence codes. No valid_from is attached: the publisher dates the licence start, not the status.",
-      "source_paths": [
-        "CRED_LIC_STATUS"
-      ],
-      "steps": [
-        {
-          "args": {},
-          "op": "trim"
-        }
-      ],
-      "target": "ext.licence.status",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.9,
-      "entity": "licence",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "External dispute-resolution scheme membership published for the licence; single codes or tilde lists (AFCA, COSL, AFCA~COSL, FOS, AFCA~FOS, AFCA~COSL~FOS), so one scheme per observation.",
-      "source_paths": [
-        "CRED_LIC_EDRS"
-      ],
-      "steps": [
-        {
-          "args": {},
-          "op": "trim"
-        },
-        {
-          "args": {
-            "sep": "~"
-          },
-          "op": "split"
-        },
-        {
-          "args": {},
-          "op": "trim"
-        },
-        {
-          "args": {
-            "values": [
-              ""
-            ]
-          },
-          "op": "null_if"
-        }
-      ],
-      "target": "ext.licence.edr_scheme",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.6,
-      "entity": "licence",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "The publisher's authorisation list: tilde-separated top-level items, each a lead-in heading followed by '; and/or'-separated activity clauses. Splitting on ';' (with optional and/or) plus the regex_extract requires the clause to end in a character other than ':', which drops every lead-in heading generically rather than a fixed list - this removes the headings the critic found on held-out rows 550376 / 381417 ('This licence authorises the licensee (either on the licensee's own behalf ...) to:', 'Engage in the credit activity of providing credit services limited only to acting as an intermediary ... where the licensee:', 'Engage in credit activities:', 'by providing debt management services.'). Bare conjunction fragments are nulled. ~7.7 activity observations per licence, 0 transform errors. Note: the reviewer asked for the publisher's top-level items; the top-level items are themselves headings, so the activities beneath them are what is emitted.",
-      "source_paths": [
-        "CRED_LIC_AUTHORISATIONS"
-      ],
-      "steps": [
-        {
-          "args": {},
-          "op": "trim"
-        },
-        {
-          "args": {
-            "sep": "~"
-          },
-          "op": "split"
-        },
-        {
-          "args": {},
-          "op": "trim"
-        },
-        {
-          "args": {
-            "pattern": ";\\s*(?:and/or|and|or)?\\s*"
-          },
-          "op": "split_regex"
-        },
-        {
-          "args": {},
-          "op": "trim"
-        },
-        {
-          "args": {},
-          "op": "collapse_whitespace"
-        },
-        {
-          "args": {
-            "group": 0,
-            "pattern": "^(.*[^:])$"
-          },
-          "op": "regex_extract"
-        },
-        {
-          "args": {
-            "values": [
-              "",
-              "and/or",
-              "and",
-              "or"
-            ]
-          },
-          "op": "null_if"
-        }
-      ],
-      "target": "ext.licence.authorisation",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.3,
-      "entity": null,
-      "join_with": ",",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Latitude/longitude carried alongside the licensee's own stated business address (the columns that feed the approved address.* rules), so this is the subject business's address point, latitude first. PRECISION CAVEAT: these are locality/suburb-centroid geocodes, not rooftop coordinates - only 315 distinct pairs across 464 rows, and the same point repeats for unrelated licensees in one suburb (e.g. -33.8698439,151.2082848 for several Sydney licensees; -37.83344,144.9570533 is a locality centroid). Confidence is set low (0.3) so consumers treat it as an approximate address point, not a precise site; it is not an establishment and no premises site is implied. geo_point drops coordinates outside Australia (3 held-out rows, US coordinates such as 48.8081114,-122.67575305) as errors, reported not hidden.",
-      "source_paths": [
-        "CRED_LIC_LAT",
-        "CRED_LIC_LNG"
-      ],
-      "steps": [
-        {
-          "args": {},
-          "op": "geo_point"
-        }
-      ],
-      "target": "ext.entity.address_point",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.4,
-      "entity": "licence",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": null,
-      "rationale": "Dated licence status-history entries (e.g. 'Licensee contravenes a licence condition 02/01/2013 ...', 'Suspended at the request of Licensee/Registrant 19/09/2016 31/01/2017') belong on the licence as status events, not on the business. Blank on most rows; the populated values are genuine dated licence events, kept as published.",
-      "source_paths": [
-        "CRED_LIC_STATUS_HISTORY"
-      ],
-      "steps": [
-        {
-          "args": {},
-          "op": "trim"
-        },
-        {
-          "args": {
-            "values": [
-              ""
-            ]
-          },
-          "op": "null_if"
-        },
-        {
-          "args": {
-            "sep": "~"
-          },
-          "op": "split"
-        },
-        {
-          "args": {},
-          "op": "trim"
-        }
-      ],
-      "target": "ext.licence.status_event",
+      "target": "ext.licence.end_date",
       "valid_from_path": null,
       "valid_to_path": null,
       "validity_date_formats": null,
@@ -545,7 +488,7 @@
     }
   ],
   "grain_rationale": "Each row is one ASIC credit licence (CRED_LIC_NUM) held by a licensee. The business participant is the licensee named in CRED_LIC_NAME; the licence number itself is the record identifier, not a business identifier.",
-  "notes": "Revision: CRED_LIC_ABN_ACN is a mixed ABN/ACN column. Shape filters (^\\d{11}$ -> entity.abn, ^\\d{9}$ -> entity.acn) send only the matching identifier type to its own checksum transform; 7-8 digit and '0' values are treated as missing. This removed all ABN_LENGTH errors (previously 8.8%) and recovers the ACNs that were being discarded. No ACN is ever derived from an ABN. entity.status changed to 'unknown' because CRED_LIC_STATUS is a licence-approval code, not a company status; the column is recorded in unmapped. No observed_at column exists, so resource_last_modified is used. TSV confirmed by 16 tabs per line in raw bytes.\n\n[ext-v1] Second revision, answering the holdout critic. (1) Rule 4 (industry_code) REMOVED: the critic is right - anzsic_credit_authorisation is a draft, all_matches, AI-prepared table over generic statutory wording, and it emits contradictory codes (6230 and 6419 for the same licence; 6419 for assistance-only licensees). CRED_LIC_AUTHORISATIONS is not a source-stated trade activity, so no reviewed crosswalk supports an ANZSIC code and none is claimed. (2) Rule 6 (related_licence_number) REMOVED and CRED_LIC_AFSL_NUM moved to unmapped: it echoed the record's own licence number as a separate AFS licence. (3) Rule 3 (authorisation) now uses a generic heading filter (a clause must not end in ':') instead of a fixed lead-in list, which removes the heading residue the critic saw on held-out records 550376/381417. (4) Rule 5 (address_point) kept with a low confidence of 0.3 and an explicit centroid-precision caveat: the values are locality-level geocodes, not rooftop coordinates; the 3 out-of-Australia coordinate pairs remain visible as reported GEO_OUTSIDE_AU errors rather than being suppressed. Licence number, status, EDR scheme and status-event rules are unchanged and were judged sound. Base rules untouched; CRED_LIC_END_DT stays with the approved (engine-ignored) observation.valid_to and is left alone because the source dates nothing from it (100% blank) so it cannot date a licence status.",
+  "notes": "Revision: CRED_LIC_ABN_ACN is a mixed ABN/ACN column. Shape filters (^\\d{11}$ -> entity.abn, ^\\d{9}$ -> entity.acn) send only the matching identifier type to its own checksum transform; 7-8 digit and '0' values are treated as missing. This removed all ABN_LENGTH errors (previously 8.8%) and recovers the ACNs that were being discarded. No ACN is ever derived from an ABN. entity.status changed to 'unknown' because CRED_LIC_STATUS is a licence-approval code, not a company status; the column is recorded in unmapped. No observed_at column exists, so resource_last_modified is used. TSV confirmed by 16 tabs per line in raw bytes.\n\n[ext-v1] Second revision, answering the holdout critic. (1) Rule 4 (industry_code) REMOVED: the critic is right - anzsic_credit_authorisation is a draft, all_matches, AI-prepared table over generic statutory wording, and it emits contradictory codes (6230 and 6419 for the same licence; 6419 for assistance-only licensees). CRED_LIC_AUTHORISATIONS is not a source-stated trade activity, so no reviewed crosswalk supports an ANZSIC code and none is claimed. (2) Rule 6 (related_licence_number) REMOVED and CRED_LIC_AFSL_NUM moved to unmapped: it echoed the record's own licence number as a separate AFS licence. (3) Rule 3 (authorisation) now uses a generic heading filter (a clause must not end in ':') instead of a fixed lead-in list, which removes the heading residue the critic saw on held-out records 550376/381417. (4) Rule 5 (address_point) kept with a low confidence of 0.3 and an explicit centroid-precision caveat: the values are locality-level geocodes, not rooftop coordinates; the 3 out-of-Australia coordinate pairs remain visible as reported GEO_OUTSIDE_AU errors rather than being suppressed. Licence number, status, EDR scheme and status-event rules are unchanged and were judged sound. Base rules untouched; CRED_LIC_END_DT stays with the approved (engine-ignored) observation.valid_to and is left alone because the source dates nothing from it (100% blank) so it cannot date a licence status.\nLocal maintainer correction (no model API call): Preserve complete authorisation text and licence dates; omit coordinates whose location precision is unverified.",
   "observed_at": {
     "fallback": "resource_last_modified",
     "source_path": null,
@@ -586,6 +529,14 @@
     {
       "reason": "Withdrawn per critic: this is not evidence of a separate related AFS licence. On held-out rows it frequently equals the row's own credit licence number (219612->219612, 223246->223246, 224543->224543, 225759->225759), i.e. the same licence echoed, so emitting it as ext.licence.related_licence_number creates a self-reference and a false related-licence fact. '0' (425/464) is a 'none' placeholder. The transform set offers no reliable way to drop only the equals-CRED_LIC_NUM case (a regex back-reference against a joined identifier column does not filter reliably), and a wrong fact is worse than a missing one, so the column is left unmapped.",
       "source_path": "CRED_LIC_AFSL_NUM"
+    },
+    {
+      "reason": "Coordinate precision is unverified; a locality centroid must not be asserted as an exact business address.",
+      "source_path": "CRED_LIC_LAT"
+    },
+    {
+      "reason": "Coordinate precision is unverified; a locality centroid must not be asserted as an exact business address.",
+      "source_path": "CRED_LIC_LNG"
     }
   ]
 }
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