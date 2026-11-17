"""Licence terms for an observation: id, title, URL and an attribution string (review section 6)."""
from __future__ import annotations

from functools import lru_cache

import yaml

from .paths import ROOT


@lru_cache(maxsize=1)
def _table() -> dict:
    return yaml.safe_load((ROOT / "config" / "licences.yaml").read_text(encoding="utf-8"))["licences"]


def detail(source_meta: dict) -> dict:
    """The licence block for one source. An unknown licence id is reported, never guessed."""
    lid = source_meta.get("licence") or "unknown"
    known = _table().get(lid)
    entry = known or _table()["unknown"]
    publisher = source_meta.get("publisher") or "unknown publisher"
    title = source_meta.get("title") or source_meta.get("source_id", "dataset")
    url = source_meta.get("catalogue_url") or source_meta.get("url")
    attribution = (f"Source: {publisher}, \"{title}\", via data.gov.au"
                   + (f" ({url})" if url else "") + f". Licensed under {entry['title']}.")
    return {"id": lid, "title": entry["title"], "url": entry.get("url"), "attribution": attribution,
            "known": known is not None}
