# Local correction review: `qbcc_licensees`

Status: PENDING_REVIEW; human sign-off is still required.
Run: `20261117T041637-local-e6ae0e56`; config digest: `e6ae0e5640fe0a52f4b662b3a69e7ecf0c14fe62c40a592a51b2be967e457f27`.
Original agent run: `20261112T205520-1addc3` (preserved).
Actor: Codex maintainer, at user request. Model calls: 0.

Retain published licence trade categories; withhold unreviewed industry inferences.

Validation: Frozen replay sample partition; not an unseen holdout. No new model critic was called.

## Regression findings

```json
[
  {
    "code": "SOME_ERRORS",
    "severity": "warning",
    "message": "2 values rejected: {'ABN_CHECKSUM': 2}",
    "target": "entity.abn",
    "source_paths": [
      "ABN"
    ],
    "examples": {
      "ABN_CHECKSUM": [
        "96 472 706 505",
        "61 601 987 687"
      ]
    }
  }
]
```

## Exact mapping changes

```diff
--- previous agent proposal
+++ local corrected proposal
@@ -1,7 +1,9 @@
 {
   "constants": [
     {
+      "claim_scope": null,
       "confidence": 0.8,
+      "entity": null,
       "rationale": "Queensland Building and Construction Commission register; every address carries a QLD state code and an AU 4-digit postcode. Inferred from the publisher and address format rather than a source column, so confidence is moderate and flagged for review.",
       "target": "address.country",
       "value": "AU"
@@ -378,50 +380,10 @@
       "valid_to_path": null,
       "validity_date_formats": null,
       "when": null
-    },
-    {
-      "claim_scope": null,
-      "confidence": 0.5,
-      "entity": "subject",
-      "join_with": " ",
-      "one_hot": null,
-      "qualifiers": {
-        "scheme": {
-          "source_path": null,
-          "steps": [],
-          "value": "anzsic2006"
-        }
-      },
-      "rationale": "Licensed trade class is a source-stated activity mapped to ANZSIC 2006 only through the qbcc licence-class crosswalk, whose keys are the whole raw Licence Class Type strings (508/508 discovery and 1101/1101 held-out matches, zero errors). Kept unsplit so the lookup matches. Critic verdict 'doubtful': the direction is right, but the table is a draft L2 judgement crosswalk (mixing 2- and 4-digit precision) and a licensed trade is the performed activity, weakest for supervisory/nominee grades (30/508). Left for human sign-off rather than self-coded or dropped.",
-      "source_paths": [
-        "Licence Class Type"
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
-          "args": {
-            "output": "code",
-            "table": "anzsic_qbcc_licence_class"
-          },
-          "op": "crosswalk"
-        }
-      ],
-      "target": "ext.entity.industry_code",
-      "valid_from_path": null,
-      "valid_to_path": null,
-      "validity_date_formats": null,
-      "when": null
     }
   ],
   "grain_rationale": "Each record is one QBCC licence held by a licensee (Licence Number + Licence Grade + Licence Class Type identify the licence; _id is the CKAN row id). The business participant is the licensee named in 'Licensee Name'. Licence-level attributes (grade, class, financial category) describe the licence, not the entity. The register is a flat export that never distinguishes a registered legal name from a trading name, so 'Licensee Name' is mapped only to entity.legal_name: for 'Company' rows it is the registered company name (corroborated by a checksum-valid ACN and PTY LTD suffixes), for 'Individual' rows it is the natural person who is the licensee. No trading name is claimed because the source provides none.",
-  "notes": "REVISION after review. Advertised as CSV but the resource is a CKAN datastore_search API JSON envelope (starts '{\"help\":'), so format=json with record_path 'result.records'. No date column exists in the records: observation.observed_at falls back to resource last-modified metadata and no valid_from/valid_to can be supplied. Fixes for the reviewer's verdicts: (1) entity.trading_name REMOVED ('wrong' verdict - a personal licensee name is not a trading name, and for companies it duplicated the legal name); (2) the suffix-based legal_name heuristic REMOVED - 'Licensee Name' is now mapped in full to entity.legal_name (coverage 100%, no suppression, no guessing), which also resolves the 'doubtful' over-suppression of individual licensees; (3) entity.entity_type now maps only 'C'->company and lets 'I' fall to the ontology default 'unknown', removing the rejected 'I'->sole_trader inference; (4) address.locality REMOVED as brittle ('doubtful'), so address output is full/state/postcode only, all of which the reviewer rated 'ok'. Retained deliberately: entity.abn and entity.acn (direct, checksum-validated source columns rated 'ok'; ABN keeps a reported ~1% checksum rejection rather than hiding it) and address.country 'AU' at reduced confidence 0.8 and flagged. Open coverage gaps for a human: entity.trading_name (no trading name exists in this source), entity.status (no status column - register membership implies current licensing but that is inferred), entity.industry_code (no ANZSIC; Licence Class Type is the nearest but non-conforming signal), address.locality (unparseable from the free-text address), and no date fields at all.\n\n[ext-v1] Critic and holdout revision. (1) ext.licence.class FIXED: no split - each whole cell is one observation, so compound QBCC classes ('Fire Detection, Alarm and Warning Systems - Occupational', 'Glass, Glazing and Aluminium') are never fragmented. It is carried on the singular licence target ext.licence.category (the multi-valued ext.licence.class target cannot hold a single compound value without tripping UNSPLIT_LIST_VALUES, and every split that clears that gate is the ', ' split the held-out critic proved wrong). The reviewer's P1 #2 requirement - the licensed trade in the publisher's wording, on the licence role - is fully met; only the ext path differs, and the reason is documented. (2) ext.financial.revenue_band REMOVED (critic 'wrong'): Financial Category CODE/DESC are unmapped because QBCC's financial category is a licence financial-requirement/contract-value tier, not a revenue band; nothing is emitted where the source does not state revenue. The 14-code qbcc_mfr coverage note therefore no longer applies to any emitted field. (3) ext.entity.industry_code KEPT, critic 'doubtful': unsplit raw class -> ANZSIC 2006 via reviewed crosswalk (scheme anzsic2006, 100% match, zero errors in both partitions); residual doubt is the table's draft L2 status and the licensed-trade-vs-business-industry association, left for human sign-off. (4) holder_kind, licence.number and licence.grade kept ('ok'). Approved rules 0-6 untouched and not resubmitted. Remaining known issue: the static UNSPLIT_LIST_VALUES heuristic complained about Licence Class Type, and the config no longer triggers it anywhere. entity.abn keeps its known ~1% ABN_CHECKSUM rejections (6/618 held-out) - the transform refuses to emit checksum-invalid ABNs rather than fabricating them, which is the approved, intended behaviour. No personal contact data appears in any emitted claim.",
+  "notes": "REVISION after review. Advertised as CSV but the resource is a CKAN datastore_search API JSON envelope (starts '{\"help\":'), so format=json with record_path 'result.records'. No date column exists in the records: observation.observed_at falls back to resource last-modified metadata and no valid_from/valid_to can be supplied. Fixes for the reviewer's verdicts: (1) entity.trading_name REMOVED ('wrong' verdict - a personal licensee name is not a trading name, and for companies it duplicated the legal name); (2) the suffix-based legal_name heuristic REMOVED - 'Licensee Name' is now mapped in full to entity.legal_name (coverage 100%, no suppression, no guessing), which also resolves the 'doubtful' over-suppression of individual licensees; (3) entity.entity_type now maps only 'C'->company and lets 'I' fall to the ontology default 'unknown', removing the rejected 'I'->sole_trader inference; (4) address.locality REMOVED as brittle ('doubtful'), so address output is full/state/postcode only, all of which the reviewer rated 'ok'. Retained deliberately: entity.abn and entity.acn (direct, checksum-validated source columns rated 'ok'; ABN keeps a reported ~1% checksum rejection rather than hiding it) and address.country 'AU' at reduced confidence 0.8 and flagged. Open coverage gaps for a human: entity.trading_name (no trading name exists in this source), entity.status (no status column - register membership implies current licensing but that is inferred), entity.industry_code (no ANZSIC; Licence Class Type is the nearest but non-conforming signal), address.locality (unparseable from the free-text address), and no date fields at all.\n\n[ext-v1] Critic and holdout revision. (1) ext.licence.class FIXED: no split - each whole cell is one observation, so compound QBCC classes ('Fire Detection, Alarm and Warning Systems - Occupational', 'Glass, Glazing and Aluminium') are never fragmented. It is carried on the singular licence target ext.licence.category (the multi-valued ext.licence.class target cannot hold a single compound value without tripping UNSPLIT_LIST_VALUES, and every split that clears that gate is the ', ' split the held-out critic proved wrong). The reviewer's P1 #2 requirement - the licensed trade in the publisher's wording, on the licence role - is fully met; only the ext path differs, and the reason is documented. (2) ext.financial.revenue_band REMOVED (critic 'wrong'): Financial Category CODE/DESC are unmapped because QBCC's financial category is a licence financial-requirement/contract-value tier, not a revenue band; nothing is emitted where the source does not state revenue. The 14-code qbcc_mfr coverage note therefore no longer applies to any emitted field. (3) ext.entity.industry_code KEPT, critic 'doubtful': unsplit raw class -> ANZSIC 2006 via reviewed crosswalk (scheme anzsic2006, 100% match, zero errors in both partitions); residual doubt is the table's draft L2 status and the licensed-trade-vs-business-industry association, left for human sign-off. (4) holder_kind, licence.number and licence.grade kept ('ok'). Approved rules 0-6 untouched and not resubmitted. Remaining known issue: the static UNSPLIT_LIST_VALUES heuristic complained about Licence Class Type, and the config no longer triggers it anywhere. entity.abn keeps its known ~1% ABN_CHECKSUM rejections (6/618 held-out) - the transform refuses to emit checksum-invalid ABNs rather than fabricating them, which is the approved, intended behaviour. No personal contact data appears in any emitted claim.\nLocal maintainer correction (no model API call): Retain published licence trade categories; withhold unreviewed industry inferences.",
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