"""Registered company names that are NOT unique: current names held by more than one ACN in the full ASIC register.

The name-only link rule assumes a registered company name identifies one company. Measured on the full
register that holds for 99.9% of current names; the rest (old state-registered companies) are listed here so a
policy can refuse name-only links on them.  python -m firmable.identity.ambiguity
"""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache

from ..paths import ROOT
from ..sources.readers import iter_records
from .resolve import norm_name

PATH = ROOT / "config" / "ambiguous_company_names.json"


def build() -> dict:
    from ..extract import load_config
    from ..sources.select import load_manifest
    src = load_manifest()["asic_companies"]
    acns = defaultdict(set)
    spec = load_config("asic_companies")[0].reader  # the approved, agent-chosen reader settings
    for r in iter_records(ROOT / src["snapshot"]["path"], spec):
        if (r.get("Current Name Indicator") or "").strip() == "Y":
            acns[norm_name(r["Company Name"])].add(r["ACN"])
    amb = sorted(n for n, a in acns.items() if len(a) > 1)
    doc = {"source": "ASIC company register snapshot, current names, any status",
           "snapshot_sha256": src["snapshot"]["sha256"], "current_names": len(acns), "count": len(amb), "names": amb}
    PATH.write_text(json.dumps(doc), encoding="utf-8")
    return {k: v for k, v in doc.items() if k != "names"}


@lru_cache(maxsize=1)
def ambiguous_names() -> frozenset:
    return frozenset(json.loads(PATH.read_text(encoding="utf-8"))["names"]) if PATH.exists() else frozenset()


if __name__ == "__main__":
    print(build())
