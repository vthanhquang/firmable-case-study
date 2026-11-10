"""Allowlisted transform operations for the mapping DSL.

Configs reference these by name with JSON arguments. Nothing here evaluates code
from a config; an unknown op is a validation error, never executed.
Each op takes a value (str | list[str] | None) and returns the same shape or None.
A transform that cannot handle a value raises TransformError (counted, never swallowed).
"""
from __future__ import annotations

import datetime as dt
import re

from .. import ids


class TransformError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code


_STATES = {
    "NSW": "NSW", "NEW SOUTH WALES": "NSW", "VIC": "VIC", "VICTORIA": "VIC", "QLD": "QLD",
    "QUEENSLAND": "QLD", "WA": "WA", "WESTERN AUSTRALIA": "WA", "SA": "SA", "SOUTH AUSTRALIA": "SA",
    "TAS": "TAS", "TASMANIA": "TAS", "ACT": "ACT", "AUSTRALIAN CAPITAL TERRITORY": "ACT",
    "NT": "NT", "NORTHERN TERRITORY": "NT", "NZ": "NZ", "NEW ZEALAND": "NZ",
}


def _str(v):
    return v if isinstance(v, str) or v is None else str(v)


def op_trim(v, **_):
    v = _str(v)
    return v.strip() if v is not None else None


def op_collapse_whitespace(v, **_):
    v = _str(v)
    return " ".join(v.split()) if v is not None else None


def op_upper(v, **_):
    v = _str(v)
    return v.upper() if v is not None else None


def op_null_if(v, values: list[str] | None = None, **_):
    """Treat placeholder strings ('', 'N/A', '-', 'NULL' ...) as missing."""
    vals = {s.strip().casefold() for s in (values or [])} | {""}
    v = _str(v)
    return None if v is None or v.strip().casefold() in vals else v


def _ident(v, n: int, check, code: str):
    v = _str(v)
    if v is None or not v.strip():
        return None
    d = ids.digits(v)
    if len(d) != n:
        raise TransformError(code + "_LENGTH", f"{v!r} has {len(d)} digits")
    if not check(d):
        raise TransformError(code + "_CHECKSUM", repr(v))
    return d


def op_abn(v, **_):
    """Digits only, then require a checksum-valid 11-digit ABN."""
    return _ident(v, 11, ids.is_valid_abn, "ABN")


def op_acn(v, **_):
    """Digits only (left-padded to 9 if 7-8 digits, as some sources drop leading zeros), checksum-valid ACN."""
    v = _str(v)
    if v is not None:
        d = ids.digits(v)
        if 7 <= len(d) < 9:
            v = d.zfill(9)
    return _ident(v, 9, ids.is_valid_acn, "ACN")


def op_nzbn(v, **_):
    return _ident(v, 13, ids.is_valid_nzbn, "NZBN")


def op_parse_date(v, formats: list[str] | None = None, **_):
    """Parse with the given strptime formats in order; output ISO yyyy-mm-dd.
    Ambiguous day/month order must be decided by the config author via `formats`."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    s = v.strip()
    for f in formats or ["%Y-%m-%d"]:
        try:
            return dt.datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    # Tolerate an ISO timestamp when ISO date was asked for.
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        raise TransformError("DATE_UNPARSEABLE", repr(s))


def op_map_enum(v, mapping: dict[str, str] | None = None, default: str | None = None, passthrough: bool = False):
    """Case-insensitive lookup table raw -> canonical value. Unlisted values -> `default` (use 'unknown'
    where the ontology has it), or unchanged if passthrough=true (free-text targets only), else an error."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    table = {k.strip().casefold(): val for k, val in (mapping or {}).items()}
    key = v.strip().casefold()
    if key in table:
        return table[key]
    if passthrough:
        return v.strip()
    if default is not None:
        return default
    raise TransformError("ENUM_UNMAPPED", repr(v))


def op_state(v, **_):
    """Normalise Australian state names/abbreviations to the ontology enum; others -> OTHER."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    key = " ".join(v.upper().replace(".", "").split())
    return _STATES.get(key, "OTHER")


def op_postcode(v, **_):
    v = _str(v)
    if v is None or not v.strip():
        return None
    d = ids.digits(v)
    if len(d) == 3:  # NT postcodes lose their leading zero in spreadsheets
        d = "0" + d
    if len(d) != 4:
        raise TransformError("POSTCODE_INVALID", repr(v))
    return d


def op_split(v, sep: str = ";", **_):
    """Split one cell into many values (e.g. several trading names). Produces a list."""
    v = _str(v)
    if v is None:
        return None
    parts = [p.strip() for p in v.split(sep)]
    return [p for p in parts if p] or None


def op_regex_extract(v, pattern: str = "", group: int = 0, **_):
    v = _str(v)
    if v is None:
        return None
    if len(pattern) > 200:
        raise TransformError("REGEX_TOO_LONG", "")
    m = re.search(pattern, v[:2000])
    return m.group(group) if m else None


def op_website(v, **_):
    v = _str(v)
    if v is None or not v.strip():
        return None
    s = v.strip()
    if " " in s or "." not in s or "@" in s:
        raise TransformError("WEBSITE_INVALID", repr(s))
    return s


OPS = {
    "trim": (op_trim, "Strip leading/trailing whitespace."),
    "collapse_whitespace": (op_collapse_whitespace, "Collapse internal runs of whitespace."),
    "upper": (op_upper, "Uppercase."),
    "null_if": (op_null_if, "args {values: [str]} - treat these placeholder strings as missing."),
    "abn": (op_abn, "Strip non-digits; require 11-digit checksum-valid ABN (error otherwise)."),
    "acn": (op_acn, "Strip non-digits (zero-pad 7-8 digits); require checksum-valid ACN."),
    "nzbn": (op_nzbn, "Strip non-digits; require 13-digit check-digit-valid NZBN."),
    "parse_date": (op_parse_date, "args {formats: [strptime formats]} - output ISO date. e.g. ['%d/%m/%Y']."),
    "map_enum": (op_map_enum, "args {mapping: {raw: canonical}, default: str|null, passthrough: bool} - case-insensitive "
                              "lookup; unlisted -> default, or unchanged if passthrough (string targets only)."),
    "state": (op_state, "Normalise AU state names/abbreviations to the state enum; unknown -> OTHER."),
    "postcode": (op_postcode, "4-digit AU postcode (re-pads 3-digit NT codes)."),
    "split": (op_split, "args {sep: str} - one cell -> many values (one observation each)."),
    "regex_extract": (op_regex_extract, "args {pattern: str, group: int} - first match or null."),
    "website": (op_website, "Basic sanity check for a URL/domain."),
}


def apply(steps, value):
    """Apply a chain of steps. Lists fan out element-wise after a `split`."""
    for step in steps:
        fn = OPS[step.op][0]
        if isinstance(value, list):
            out = []
            for item in value:
                r = fn(item, **step.args)
                if isinstance(r, list):
                    out.extend(r)
                elif r is not None:
                    out.append(r)
            value = out or None
        else:
            value = fn(value, **step.args)
        if value is None:
            return None
    return value


def describe() -> list[dict]:
    return [{"op": k, "doc": doc} for k, (_, doc) in OPS.items()]
