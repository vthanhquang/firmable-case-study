"""Human-reviewed lookup tables that configs reference by name (review section 5.4).

A crosswalk turns a raw source code into a canonical code, label or band. The table, not the
config, holds the judgement, so one reviewed table serves every config that cites it, and the
table's own derivation level (L1 official decode, L2 judgement) is stamped on each observation.

Table file: config/crosswalks/<name>.yaml
  kind:            code | band
  derivation_level L1 | L2
  entries:         {raw: {code, label, ...}}   exact match, case-insensitive; `code: null` = "no inference"
  patterns:        [{regex, code, label}]     applied in order when no entry matches
  all_matches:     every matching pattern yields a value (default: first match only)
  output_format:   used when an entry has no `code` (e.g. "{key}: {label}")
  unlisted:        error | null
"""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from .paths import ROOT

CROSSWALKS = ROOT / "config" / "crosswalks"
_NAME = re.compile(r"^[a-z0-9_]+$")


class CrosswalkMissing(KeyError):
    pass


@lru_cache(maxsize=64)
def load(name: str) -> dict:
    if not _NAME.match(name or ""):
        raise CrosswalkMissing(f"invalid crosswalk name {name!r}")
    path = CROSSWALKS / f"{name}.yaml"
    if not path.is_file():
        raise CrosswalkMissing(f"no crosswalk table {name!r}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["_index"] = {str(k).strip().casefold(): (str(k), v or {}) for k, v in (doc.get("entries") or {}).items()}
    doc["_patterns"] = [(re.compile(p["regex"]), p) for p in doc.get("patterns") or []]
    return doc


def names() -> list[str]:
    return sorted(p.stem for p in CROSSWALKS.glob("*.yaml"))


def describe() -> list[dict]:
    """Model-facing summary: what each table produces and the raw keys it knows."""
    out = []
    for n in names():
        t = load(n)
        out.append({"table": n, "kind": t["kind"], "target": t.get("target"), "scheme": t.get("scheme"),
                    "derivation_level": t.get("derivation_level", "L1"), "review_status": t.get("review_status"),
                    "keys": [k for k, _ in t["_index"].values()][:60],
                    "patterns": [p["regex"] for _, p in t["_patterns"]],
                    "all_matches": bool(t.get("all_matches"))})
    return out


def _render(table: dict, key: str, entry: dict, output: str):
    if "code" in entry and entry["code"] is None:
        return None                   # an explicit "no inference" entry emits nothing, whatever the output
    if output == "label":
        return entry.get("label")
    if output == "key_label":
        return f"{key}: {entry['label']}" if entry.get("label") else key
    if "code" in entry:
        return entry["code"]          # may be None: an explicit "no inference" entry
    fmt = table.get("output_format")
    return fmt.format(key=key, label=entry.get("label", "")) if fmt else key


def lookup(name: str, raw: str, output: str = "code"):
    """Return (values, matched). values is a list (possibly empty); matched=False means unlisted."""
    table = load(name)
    s = raw.strip()
    hit = table["_index"].get(s.casefold())
    if hit:
        value = _render(table, hit[0], hit[1], output)
        return ([value] if value is not None else []), True
    values, matched = [], False
    for rx, p in table["_patterns"]:
        if rx.search(s):
            matched = True
            value = _render(table, s, p, output)
            if value is not None and value not in values:
                values.append(value)
            if not table.get("all_matches"):
                break
    return values, matched


def band_labels(name: str) -> set[str]:
    table = load(name)
    if table.get("kind") != "band":
        return set()
    return {(v or {}).get("label", k) for k, v in (table.get("entries") or {}).items()
            if not ("code" in (v or {}) and (v or {})["code"] is None)}
