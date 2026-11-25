"""Generic, config-driven record readers. No source-specific code lives here.

Every reader yields flat dict records: nested JSON/XML is flattened to dotted keys,
XML attributes become `tag@attr`. A ZIP is opened and one member is read with the
inner format. Size caps protect against oversized files and zip bombs.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

from ..mapping.schema import ReaderSpec

MAX_MEMBER_BYTES = 2_000_000_000   # refuse to decompress beyond 2 GB
MAX_JSON_BYTES = 300_000_000       # whole-document JSON parse cap
csv.field_size_limit(10_000_000)


class ReaderError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def _open_bytes(path: Path, spec: ReaderSpec) -> io.BufferedIOBase:
    if zipfile.is_zipfile(path) and spec.format != "xlsx":
        zf = zipfile.ZipFile(path)
        names = [n for n in zf.namelist() if not n.endswith("/")]
        member = spec.archive_member
        if member is None:
            if len(names) != 1:
                raise ReaderError("ARCHIVE_MEMBER_REQUIRED", f"zip has {len(names)} members: {names[:20]}")
            member = names[0]
        if member not in names:
            raise ReaderError("ARCHIVE_MEMBER_MISSING", f"{member!r} not in {names[:20]}")
        info = zf.getinfo(member)
        if info.file_size > MAX_MEMBER_BYTES or (info.compress_size and info.file_size / info.compress_size > 200):
            raise ReaderError("ARCHIVE_TOO_LARGE", f"{member}: {info.file_size} bytes")
        return zf.open(member)
    return open(path, "rb")


def _clean_key(k) -> str:
    return " ".join(str(k).replace("﻿", "").split()) if k is not None else ""


def _unique_headers(cells) -> list[str]:
    """Preserve every column, including repeated labels and existing suffixes.

    Suffixes identify positions only; their business meaning (for example, a
    reporting year in a preceding row) still needs to be inferred from evidence.
    """
    names = [_clean_key(cell) or f"column_{i}" for i, cell in enumerate(cells)]
    reserved, used, result = set(names), set(), []
    for name in names:
        candidate, suffix = name, 2
        if name in used:
            while True:
                candidate = f"{name}_{suffix}"
                suffix += 1
                if candidate not in reserved and candidate not in used:
                    break
        result.append(candidate)
        used.add(candidate)
    return result


def _flatten(obj, prefix="", out=None) -> dict:
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            out[prefix] = "; ".join("" if x is None else str(x) for x in obj)
        else:
            for i, x in enumerate(obj):
                _flatten(x, f"{prefix}[{i}]", out)
    else:
        out[prefix] = obj
    return out


def _read_delimited(fh, spec: ReaderSpec) -> Iterator[dict]:
    text = io.TextIOWrapper(fh, encoding=spec.encoding, errors="replace", newline="")
    for _ in range(spec.skip_rows):
        text.readline()
    reader = csv.reader(text, delimiter=spec.delimiter or ",")
    header = next(reader, None)
    if not header:
        raise ReaderError("EMPTY_FILE", "no header row")
    header = _unique_headers(header)
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        rec = {h: (row[i] if i < len(row) else None) for i, h in enumerate(header)}
        if len(row) > len(header):
            rec["__extra_cells__"] = "|".join(row[len(header):])
        yield rec


def _read_xlsx(path: Path, spec: ReaderSpec) -> Iterator[dict]:
    import openpyxl
    with open(path, "rb") as fh:  # file object: openpyxl would otherwise insist on an .xlsx extension
        wb = openpyxl.load_workbook(fh, read_only=True, data_only=True)
        if spec.sheet and spec.sheet not in wb.sheetnames:
            raise ReaderError("SHEET_MISSING", f"{spec.sheet!r} not in {wb.sheetnames}")
        ws = wb[spec.sheet] if spec.sheet else wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        for _ in range(spec.skip_rows):
            next(rows, None)
        header = next(rows, None)
        if not header:
            raise ReaderError("EMPTY_SHEET", ws.title)
        header = _unique_headers(header)
        for row in rows:
            if row is None or all(c is None or str(c).strip() == "" for c in row):
                continue
            yield {h: (None if c is None else (c.isoformat() if hasattr(c, "isoformat") else str(c)))
                   for h, c in zip(header, row)}


def _dig(obj, path: str | None):
    if not path:
        return obj
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def _read_json(fh, spec: ReaderSpec) -> Iterator[dict]:
    data = fh.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise ReaderError("JSON_TOO_LARGE", "document exceeds cap")
    doc = json.loads(data.decode(spec.encoding, errors="replace"))
    recs = _dig(doc, spec.record_path)
    if isinstance(recs, dict):  # dict of id -> record
        recs = [dict(v, __key__=k) if isinstance(v, dict) else {"__key__": k, "value": v} for k, v in recs.items()]
    if not isinstance(recs, list):
        raise ReaderError("INVALID_RECORD_SELECTOR", f"record_path {spec.record_path!r} is not a list")
    for r in recs:
        yield _flatten(r) if isinstance(r, (dict, list)) else {"value": r}


def _read_jsonl(fh, spec: ReaderSpec) -> Iterator[dict]:
    for line in io.TextIOWrapper(fh, encoding=spec.encoding, errors="replace"):
        line = line.strip()
        if line:
            try:
                yield _flatten(json.loads(line))
            except json.JSONDecodeError:
                yield {"__malformed_line__": line[:500]}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_record(el) -> dict:
    out = {}

    def walk(e, prefix):
        for k, v in e.attrib.items():
            out[f"{prefix}@{_local(k)}" if prefix else f"@{_local(k)}"] = v
        children = list(e)
        if not children:
            if e.text and e.text.strip():
                key = prefix or _local(e.tag)
                out[key] = (out[key] + "; " + e.text.strip()) if key in out else e.text.strip()
            return
        counts = {}
        for c in children:
            name = _local(c.tag)
            counts[name] = counts.get(name, 0) + 1
        seen = {}
        for c in children:
            name = _local(c.tag)
            seen[name] = seen.get(name, 0) + 1
            key = name if counts[name] == 1 else f"{name}[{seen[name] - 1}]"
            walk(c, f"{prefix}.{key}" if prefix else key)

    walk(el, "")
    return out


def _read_xml(fh, spec: ReaderSpec) -> Iterator[dict]:
    if not spec.record_path:
        raise ReaderError("INVALID_RECORD_SELECTOR", "xml needs record_path = record element tag")
    target = spec.record_path
    for event, el in ET.iterparse(fh, events=("end",)):
        if _local(el.tag) == target:
            yield _xml_record(el)
            el.clear()


def iter_records(path: Path, spec: ReaderSpec) -> Iterator[dict]:
    """Yield flat records from `path` according to `spec`. Errors are typed ReaderErrors."""
    try:
        if spec.format == "xlsx":
            yield from _read_xlsx(path, spec)
            return
        with _open_bytes(path, spec) as fh:
            if spec.format == "delimited":
                yield from _read_delimited(fh, spec)
            elif spec.format == "json":
                yield from _read_json(fh, spec)
            elif spec.format == "jsonl":
                yield from _read_jsonl(fh, spec)
            elif spec.format == "xml":
                yield from _read_xml(fh, spec)
    except ReaderError:
        raise
    except (UnicodeError, csv.Error, json.JSONDecodeError, ET.ParseError, KeyError, zipfile.BadZipFile) as e:
        raise ReaderError("PARSER_ERROR", f"{type(e).__name__}: {e}"[:300])
    except Exception as e:  # openpyxl and friends raise assorted types; keep them typed for the agent
        raise ReaderError("PARSER_ERROR", f"{type(e).__name__}: {e}"[:300])


def head(path: Path, spec: ReaderSpec, n: int) -> list[dict]:
    out = []
    for r in iter_records(path, spec):
        out.append(r)
        if len(out) >= n:
            break
    return out
