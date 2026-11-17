"""Raw-data extension pipeline (review "Getting More Out of the Raw Source Files").

Everything here runs BESIDE the audited case-study pipeline and writes under outputs/raw-data/:
  store.py     raw row store keyed by (source_id, snapshot_sha256, source_record_id)        (review 5.1)
  review.py    review pages + human decisions for agent-written extension mappings          (review 5.4)
  extract.py   extension extraction: observations, roles, edges, extension cohort sample   (review 5.3)
  match.py     challenger matcher with the new matching evidence                            (review 4.1)
  profiles.py  profile-v3: firmographics, establishments, licences, contact points           (review 4.2, 4.4)
  changes.py   snapshot / period diffing into an event table                                (review 4.3)
  metrics.py   measurement for each phase                                                   (review 8)
Nothing is promoted into the audited outputs until a human approves it.
"""
from ..paths import OUT

OUT_RAWDATA = OUT / "raw-data"
OUT_RD_MAPPINGS = OUT_RAWDATA / "mappings"
OUT_RD_REVIEWS = OUT_RAWDATA / "reviews"
OUT_RD_OBS = OUT_RAWDATA / "observations"
OUT_RD_IDENTITY = OUT_RAWDATA / "identity"
OUT_RD_PROFILES = OUT_RAWDATA / "profiles"
OUT_RD_EVAL = OUT_RAWDATA / "evaluation"
