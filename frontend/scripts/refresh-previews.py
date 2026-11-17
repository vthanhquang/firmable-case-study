"""Build bounded public dataset previews for the Part 1 audit."""
import csv
import io
import json
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
from pathlib import Path

import httpx
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/triage-recheck"
ROW_LIMIT = 50
HIDE_COLUMN = re.compile(r"e.?mail|phone|fax|contact number|contact details", re.I)


def table(resource, source, rows, note=None):
    rows = iter(rows)
    headers = [str(value or "") for value in next(rows)]
    columns = [index for index, name in enumerate(headers) if name and not HIDE_COLUMN.search(name)]
    records = []
    for row in rows:
        if not any(cell is not None and str(cell).strip() for cell in row):
            continue
        records.append([str(row[index])[:280] if index < len(row) and row[index] is not None else "" for index in columns])
        if len(records) == ROW_LIMIT:
            break
    if not records or not columns:
        raise ValueError("empty table")
    return {"resource": resource, "source": source, "headers": [headers[index] for index in columns],
            "rows": records, "note": note or ("Direct contact columns omitted." if len(columns) < len(headers) else None)}


def csv_rows(stream, delimiter):
    return csv.reader(stream, delimiter=delimiter)


def workbook(file, url):
    with file.open("rb") as stream:
        book = load_workbook(stream, read_only=True, data_only=True)
        try:
            sheet = book.worksheets[0]
            return table(sheet.title, url, sheet.iter_rows(values_only=True))
        finally:
            book.close()


def asic(file, url):
    with zipfile.ZipFile(file) as archive, archive.open(archive.namelist()[0]) as compressed:
        with io.TextIOWrapper(compressed, encoding="utf-8-sig", errors="replace") as text:
            return table(archive.namelist()[0], url, csv_rows(text, "\t"))


def get_bytes(url, size=2_000_000, *, byte_range=False):
    headers = {"User-Agent": "firmable-case-study/0.1 (public dataset review)"}
    if byte_range:
        headers["Range"] = f"bytes=0-{size - 1}"
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=15) as response:
        response.raise_for_status()
        if response.status_code not in {200, 206}:
            raise ValueError(f"HTTP {response.status_code}")
        chunks, length = [], 0
        for chunk in response.iter_bytes():
            chunks.append(chunk[:size - length])
            length += len(chunk)
            if length >= size:
                break
    return b"".join(chunks)


def csv_preview(name, url):
    contents = get_bytes(url)
    if contents.lstrip().lower().startswith((b"<!doctype", b"<html")):
        raise ValueError("download returned a web page")
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = contents.decode("cp1252", errors="replace")
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    return table(name, url, csv_rows(io.StringIO(text), delimiter))


def bulk_xml(url):
    body = get_bytes(url, byte_range=True)
    header = struct.unpack("<4s5H3L2H", body[:30])
    if header[0] != b"PK\x03\x04" or header[3] != 8:
        raise ValueError("expected a ZIP deflate member")
    offset = 30 + header[-2] + header[-1]
    xml = zlib.decompressobj(-zlib.MAX_WBITS).decompress(body[offset:], 3_000_000)
    records = list(islice(re.finditer(rb"<ABR[\s>].*?</ABR>", xml, re.S), ROW_LIMIT))
    rows = [["ABN", "Entity type", "Organisation name", "ASIC number", "State", "Postcode"]]
    for record in records:
        node = ET.fromstring(record.group())
        rows.append([node.findtext(path) or "" for path in (
            "ABN", "./EntityType/EntityTypeText", "./MainEntity/NonIndividualName/NonIndividualNameText",
            "./MainEntity/ASICNumber", ".//BusinessAddress/AddressDetails/State",
            ".//BusinessAddress/AddressDetails/Postcode",
        )])
    return table(body[30:30 + header[-2]].decode("utf-8", errors="replace"), url, rows,
                 "Selected fields from the first XML records in the archive.")


def main():
    audit = json.loads((ROOT / "outputs/evaluation/triage_audit_evidence.json").read_text(encoding="utf-8"))
    audit_by_rank = {row["rank"]: row for row in audit}
    packages = {row["dataset_id"]: row for line in (ROOT / "outputs/discovery/catalogue_pool.jsonl")
                .read_text(encoding="utf-8").splitlines() if (row := json.loads(line))}

    def url(rank, prefix=None):
        row = audit_by_rank[rank]
        return next(r["url"] for r in packages[row["dataset_id"]]["resources"] if r["id"].startswith(prefix)) if prefix else row["resource_checked"]

    work = {
        1: lambda: workbook(RAW / "qld_suitable_operators.xlsx", url(1)),
        4: lambda: asic(RAW / "asic_companies__d6d03876", url(4, "d6d03876")),
        12: lambda: bulk_xml(url(12, "0ae4d427")),
        19: lambda: csv_preview("ASIC AFS Licensee Dataset", url(19)),
        21: lambda: workbook(RAW / "acnc_charities__eb1e6be4", url(21, "eb1e6be4")),
        24: lambda: csv_preview("Outdoor Dining Permits.csv", url(24)),
        26: lambda: csv_preview("APROSS 2019–20.csv", url(26)),
        38: lambda: csv_preview("Toiletmap.csv", url(38)),
        40: lambda: csv_preview("design-party-activity.csv", url(40, "51f6686d")),
    }
    previews = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        jobs = {rank: executor.submit(job) for rank, job in work.items()}
        for rank, job in jobs.items():
            try:
                previews[rank] = job.result()
                print(f"Rank {rank}: {len(previews[rank]['rows'])} rows")
            except (OSError, ValueError, StopIteration, httpx.HTTPError, zipfile.BadZipFile, ET.ParseError) as error:
                print(f"Rank {rank}: preview unavailable ({type(error).__name__})")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "site-previews.json").write_text(json.dumps(previews, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
