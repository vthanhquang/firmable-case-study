"""Filesystem layout. Everything is relative to the repo root so a clean checkout works."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY = ROOT / "firmable_ontology.yaml"
DATA = ROOT / "data"            # raw downloads + http cache (gitignored)
RAW = DATA / "raw"
HTTP_CACHE = DATA / "http_cache"
RUNS = ROOT / "runs"            # agent checkpoints + event logs
OUT = ROOT / "outputs"
OUT_DISCOVERY = OUT / "discovery"
OUT_SOURCES = OUT / "sources"
OUT_MAPPINGS = OUT / "mappings"
OUT_REVIEWS = OUT / "reviews"
OUT_OBS = OUT / "observations"
OUT_IDENTITY = OUT / "identity"
OUT_PROFILES = OUT / "profiles"
OUT_EVAL = OUT / "evaluation"


def ensure_dirs():
    for p in (RAW, HTTP_CACHE, RUNS, OUT_DISCOVERY, OUT_SOURCES, OUT_MAPPINGS, OUT_REVIEWS,
              OUT_OBS, OUT_IDENTITY, OUT_PROFILES, OUT_EVAL):
        p.mkdir(parents=True, exist_ok=True)
