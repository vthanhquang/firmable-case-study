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


class TransformDrop(TransformError):
    """A value the config deliberately discards (a truncated phone, a personal mailbox). It is counted
    and shown to the reviewer as `dropped`, separately from errors, and never emitted."""


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


def op_parse_integer(v, **_):
    v = _str(v)
    if v is None or not v.strip():
        return None
    s = v.strip()
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.0+)?", s):
        raise TransformError("INTEGER_UNPARSEABLE", repr(s))
    return int(s.partition(".")[0].replace(",", ""))


def op_split_regex(v, pattern: str = ";", **_):
    """Split on a regular expression (e.g. ',\\s*|;\\s*'). Produces a list."""
    v = _str(v)
    if v is None:
        return None
    if len(pattern) > 100:
        raise TransformError("REGEX_TOO_LONG", "")
    parts = [p.strip() for p in re.split(pattern, v[:5000])]
    return [p for p in parts if p] or None


TRUTHY = ("Y", "YES", "TRUE", "1", "T")


def op_flag(v, value: str = "", truthy: list[str] | None = None, **_):
    """A Y/blank flag column -> `value` when the flag is set, else nothing. Used for one-column-per-tag sources."""
    v = _str(v)
    if v is None or not value:
        return None
    return value if v.strip().upper() in {t.upper() for t in (truthy or TRUTHY)} else None


def op_crosswalk(v, table: str = "", output: str = "code", **_):
    """Look a raw code up in a human-reviewed crosswalk table (config/crosswalks/<table>.yaml)."""
    from .. import crosswalk
    v = _str(v)
    if v is None or not v.strip():
        return None
    if output not in ("code", "label", "key_label"):
        raise TransformError("CROSSWALK_OUTPUT_INVALID", output)
    try:
        values, matched = crosswalk.lookup(table, v, output)
    except crosswalk.CrosswalkMissing as e:
        raise TransformError("CROSSWALK_MISSING", str(e))
    if not matched:
        if crosswalk.load(table).get("unlisted", "error") == "null":
            raise TransformDrop("CROSSWALK_UNLISTED", repr(v[:80]))
        raise TransformError("CROSSWALK_UNLISTED", repr(v[:80]))
    if not values:
        raise TransformDrop("CROSSWALK_NO_INFERENCE", repr(v[:80]))
    return values if len(values) > 1 else values[0]


def op_parse_decimal(v, **_):
    """Parse an amount: '$1,234.50', '115,090,768', '(1,200)' (negative). Whole numbers come back as int."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    s = v.strip().replace("$", "").replace(" ", "")
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?", s):
        raise TransformError("DECIMAL_UNPARSEABLE", repr(v))
    n = float(s.replace(",", ""))
    n = -n if negative else n
    return int(n) if n.is_integer() and "." not in s.rstrip("0").rstrip(".") else n


_AREA = {"NSW": "2", "ACT": "2", "VIC": "3", "TAS": "3", "QLD": "7", "SA": "8", "WA": "8", "NT": "8"}


def op_phone_au(v, area_from_state: bool = False, on_incomplete: str = "error", **_):
    """Australian phone -> E.164 (+61...). Input may be 'number|STATE' (two columns joined with '|'):
    an 8-digit local number then takes the state's area code when area_from_state=true.
    Numbers that cannot be completed (under 8 digits, or 8 digits without a state) raise
    PHONE_INCOMPLETE, or are dropped and counted when on_incomplete='drop'."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    number, _, state = v.partition("|")
    d = ids.digits(number)
    if not d:
        return None
    if d.startswith("61") and len(d) in (11, 12):
        d = "0" + d[2:] if not d[2:].startswith(("13", "18")) else d[2:]
    out = None
    if len(d) == 10 and d.startswith("0"):
        out = "+61" + d[1:]
    elif len(d) == 10 and d.startswith(("1300", "1800")):
        out = "+61" + d
    elif len(d) == 9 and d.startswith("4"):
        out = "+61" + d
    elif len(d) == 8 and area_from_state and state.strip().upper() in _AREA:
        out = "+61" + _AREA[state.strip().upper()] + d
    if out is None:
        exc = TransformDrop if on_incomplete == "drop" else TransformError
        raise exc("PHONE_INCOMPLETE", f"{len(d)} digits")
    return out


_EMAIL = re.compile(r"^\s*([A-Za-z0-9._%+'-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\s*$")
ROLE_MAILBOXES = {"info", "enquiries", "enquiry", "admin", "administration", "reception", "contact", "contactus",
                  "hello", "office", "mail", "accounts", "sales", "support", "service", "services", "employment",
                  "jobs", "careers", "recruitment", "bookings", "general", "team", "help", "helpdesk", "connect"}


def op_email_domain(v, **_):
    """The domain of an email address, lower-cased. The local part (often a person's name) is discarded."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    m = _EMAIL.match(v)
    if not m:
        raise TransformError("EMAIL_INVALID", "unparseable address")   # never echo the value: it may be personal
    return m.group(2).lower()


def op_role_email(v, **_):
    """Keep the whole address only for a role mailbox (info@, enquiries@ ...); personal mailboxes are dropped."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    m = _EMAIL.match(v)
    if not m:
        raise TransformError("EMAIL_INVALID", "unparseable address")
    local = m.group(1).lower()
    if local not in ROLE_MAILBOXES:
        raise TransformDrop("PERSONAL_MAILBOX_DROPPED", "")
    return f"{local}@{m.group(2).lower()}"


def op_url_domain(v, **_):
    """Host of a URL or bare domain, lower-cased, without scheme, path, port or a leading 'www.'."""
    v = _str(v)
    if v is None or not v.strip():
        return None
    s = v.strip().lower()
    s = re.sub(r"^[a-z]+://", "", s).split("/")[0].split("?")[0].split(":")[0]
    if s.startswith("www."):
        s = s[4:]
    if "@" in s or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", s):
        raise TransformError("DOMAIN_INVALID", repr(v[:80]))
    return s


# Australia including its external territories (Christmas Island 105.6E, Cocos 96.8E, Norfolk 167.9E):
# a DEWR site on Christmas Island is Australian. Mainland-only boxes misreport them as foreign.
AU_BBOX = {"lat": (-55.0, -9.0), "lon": (96.0, 168.5)}


def op_geo_point(v, **_):
    """'lat,lon' (two columns joined with ',') -> 'lat,lon' rounded to 6 dp, inside Australia's bounding box.
    A literal NULL / blank part is missing, not an error."""
    v = _str(v)
    if v is None:
        return None
    parts = [p.strip() for p in v.split(",")]
    if len(parts) != 2 or any(p.upper() in ("", "NULL", "NONE", "NAN", "0") for p in parts):
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        raise TransformError("GEO_UNPARSEABLE", repr(v[:60]))
    if not (AU_BBOX["lat"][0] <= lat <= AU_BBOX["lat"][1] and AU_BBOX["lon"][0] <= lon <= AU_BBOX["lon"][1]):
        raise TransformError("GEO_OUTSIDE_AU", f"{lat},{lon}")
    return f"{lat:.6f},{lon:.6f}"


def op_country_with_region(v, aliases: dict[str, str] | None = None):
    """Normalize an explicitly stated country, rejecting conflicts with an AU state.

    Input is country|state. Missing and unrecognised countries are never guessed from the state.
    The config supplies any additional verified ISO country aliases it wants to support.
    """
    if v is None:
        return None
    parts = str(v).split("|")
    # The generic gatherer omits empty columns; a lone state supplies no country evidence.
    au_regions = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT", "NEW SOUTH WALES", "VICTORIA",
                  "QUEENSLAND", "SOUTH AUSTRALIA", "WESTERN AUSTRALIA", "TASMANIA", "NORTHERN TERRITORY", "AUSTRALIAN CAPITAL TERRITORY"}
    if len(parts) == 1:
        if parts[0].strip().upper().rstrip(".") in au_regions:
            return None
        parts.append("")
    if len(parts) != 2:
        raise TransformError("COUNTRY_INPUT_INVALID", "Expected country|state")
    country, region = (part.strip().upper().rstrip(".") for part in parts)
    if not country or country in {"NULL", "NONE", "N/A"}:
        return None
    mapping = {"AU": "AU", "AUS": "AU", "AUSTRALIA": "AU", "NZ": "NZ", "NZL": "NZ", "NEW ZEALAND": "NZ"}
    mapping.update({key.upper(): value.upper() for key, value in (aliases or {}).items()})
    code = mapping.get(country)
    if code is None or not re.fullmatch(r"[A-Z]{2}", code):
        raise TransformError("COUNTRY_UNMAPPED", "Unrecognised country retained only in source evidence")
    if code != "AU" and region in au_regions:
        raise TransformError("COUNTRY_REGION_CONFLICT", "Stated country contradicts the Australian state")
    return code


OPS = {
    "country_with_region": (op_country_with_region, "Country and state joined by '|'; normalize explicit country aliases and reject contradictory AU state evidence."),
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
    "parse_integer": (op_parse_integer, "Parse a whole integer, retaining zero and signs. Accepts comma grouping."),
    "split_regex": (op_split_regex, "args {pattern: regex} - split one cell into many values on a pattern."),
    "flag": (op_flag, "args {value: str, truthy: [str]} - a Y/blank flag column -> `value` when set, else nothing."),
    "crosswalk": (op_crosswalk, "args {table: name, output: code|label|key_label} - look the raw value up in a "
                                "human-reviewed table (see list_crosswalks). Unlisted raw values are errors."),
    "parse_decimal": (op_parse_decimal, "Parse an amount ('$1,234.50', '(1,200)' negative). Whole numbers -> int."),
    "phone_au": (op_phone_au, "args {area_from_state: bool, on_incomplete: error|drop} - AU phone -> E.164. Join the "
                              "number with a state column using join_with '|' to complete 8-digit local numbers."),
    "email_domain": (op_email_domain, "Email address -> its domain. The personal local part is discarded."),
    "role_email": (op_role_email, "Keep a role mailbox (info@, enquiries@ ...); personal mailboxes are dropped."),
    "url_domain": (op_url_domain, "URL or bare domain -> host without scheme/path/www."),
    "geo_point": (op_geo_point, "Two columns joined with ',' (lat,lon) -> 'lat,lon' inside Australia; NULL -> missing."),
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
