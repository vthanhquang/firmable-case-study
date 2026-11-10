"""Deterministic first look at a raw resource: what kind of bytes is this, really?

The output is shown to the agent so it can choose reader settings from evidence
(e.g. a `.csv` that is actually tab-delimited) instead of from the file extension.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

SNIFF_BYTES = 64_000


def _decode(b: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return b.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1", errors="replace"), "latin-1"


def _text_view(b: bytes) -> dict:
    # Drop a possibly-truncated last line so delimiter counts are honest.
    text, enc = _decode(b[:SNIFF_BYTES])
    lines = text.splitlines()[:-1] if len(b) >= SNIFF_BYTES else text.splitlines()
    head = lines[:12]
    delim_counts = {}
    for name, d in (("comma", ","), ("tab", "\t"), ("pipe", "|"), ("semicolon", ";")):
        counts = [ln.count(d) for ln in lines[:30] if ln.strip()]
        if counts:
            delim_counts[name] = {"min": min(counts), "max": max(counts)}
    stripped = text.lstrip()
    kind = "xml" if stripped.startswith("<") else "json" if stripped[:1] in "[{" else "text"
    if kind == "json" and len(lines) > 1 and all(ln.strip().startswith("{") for ln in lines[:5] if ln.strip()):
        kind = "jsonl_probably"
    return {"looks_like": kind, "encoding_guess": enc,
            "delimiter_counts_per_line": delim_counts,
            "first_lines": [ln[:400] for ln in head]}


def inspect_file(path: Path) -> dict:
    size = path.stat().st_size
    with open(path, "rb") as fh:
        magic = fh.read(8)
    info = {"file_name": path.name, "size_bytes": size, "magic_hex": magic.hex()}
    if zipfile.is_zipfile(path):
        zf = zipfile.ZipFile(path)
        names = zf.namelist()
        if any(n.startswith("xl/") for n in names):
            import openpyxl
            wb = openpyxl.load_workbook(open(path, "rb"), read_only=True, data_only=True)  # file object: no extension check
            sheets = {}
            for ws in wb.worksheets[:6]:
                rows = []
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    rows.append([None if c is None else str(c)[:60] for c in row[:30]])
                    if i >= 7:
                        break
                sheets[ws.title] = rows
            info.update(container="xlsx", sheets_first_rows=sheets)
            return info
        members = [{"name": i.filename, "size": i.file_size} for i in zf.infolist() if not i.is_dir()]
        info.update(container="zip", members=members[:50])
        # Preview the largest member's leading bytes.
        big = max(zf.infolist(), key=lambda i: i.file_size)
        with zf.open(big) as m:
            info["largest_member_preview"] = {"name": big.filename, **_text_view(m.read(SNIFF_BYTES))}
        return info
    with open(path, "rb") as fh:
        info.update(container="plain", **_text_view(fh.read(SNIFF_BYTES)))
    return info
