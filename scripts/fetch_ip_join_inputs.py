"""Download complete IP ZIP members with CRC verification, without fetching the full archive.

Transport only: this script supplies no ontology or mapping rules. The original
party cohort and new members must come from the same publisher archive ETag.
"""
import hashlib
import io
import json
import struct
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def fetch_member(client, url, etag, info, offset, dest):
    receipt_path = dest.with_suffix(".receipt.json")
    if dest.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        with dest.open("rb") as stream:
            current = hashlib.file_digest(stream, "sha256").hexdigest()
        if receipt["archive_etag"] != etag or receipt["sha256"] != current:
            raise ValueError("Existing IP member does not match the requested snapshot")
        return receipt
    response = client.get(url, headers={"Range": f"bytes={offset}-{offset+4095}", "If-Match": etag})
    response.raise_for_status()
    if response.status_code != 206 or response.headers.get("etag") != etag:
        raise ValueError("Range support required")
    header = struct.unpack("<4s5H3I2H", response.content[:30])
    if header[0] != b"PK\x03\x04" or header[3] != 8:
        raise ValueError("Expected ZIP DEFLATE member")
    start = offset + 30 + header[-2] + header[-1]
    end = start + info.compress_size - 1
    decompressor = zlib.decompressobj(-15)
    crc, size, received = 0, 0, 0
    sha = hashlib.sha256()
    temp = dest.with_suffix(".partial")
    with client.stream("GET", url, headers={"Range": f"bytes={start}-{end}", "If-Match": etag}) as response:
        response.raise_for_status()
        if response.status_code != 206 or response.headers.get("etag") != etag or response.headers.get("content-range", "").split("/")[0] != f"bytes {start}-{end}":
            raise ValueError("Wrong compressed member range")
        with temp.open("wb") as stream:
            for block in response.iter_bytes(256 * 1024):
                received += len(block)
                raw = decompressor.decompress(block)
                size += len(raw)
                if size > info.file_size:
                    raise ValueError("ZIP member exceeded declared size")
                crc = zlib.crc32(raw, crc); sha.update(raw); stream.write(raw)
    if received != info.compress_size or size != info.file_size or crc != info.CRC or not decompressor.eof:
        raise ValueError("Incomplete or corrupt IP member")
    temp.replace(dest)
    receipt = {"archive_url": url, "archive_etag": etag, "member": info.filename,
               "size": size, "sha256": sha.hexdigest(), "crc32": crc, "crc_verified": True,
               "compressed_content_range": f"bytes={start}-{end}",
               "retrieved_at": datetime.now(timezone.utc).isoformat()}
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-snapshot", action="store_true", help="Acquire a fresh party cohort and matching complete members for a separate join experiment")
    args = parser.parse_args()
    source = json.loads((ROOT / "outputs/experiments/profile-enrichment/ip-acquisition.json").read_text())
    if args.new_snapshot:
        from scripts import prepare_profile_enrichment as intake
        intake.DATA = ROOT / "data/profile-enrichment/ip-join-new"
        intake.EVIDENCE = ROOT / "outputs/experiments/grouped-ontology/ip-inputs"
        intake.DATA.mkdir(parents=True, exist_ok=True); intake.EVIDENCE.mkdir(parents=True, exist_ok=True)
        _, source = intake.ip_prefix(source["url"])
    url, etag = source["url"], source["archive_etag"]
    folder = ROOT / ("data/profile-enrichment/ip-join-new" if args.new_snapshot else "data/profile-enrichment/ip-tables")
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=180, follow_redirects=True) as client:
        tail = client.get(url, headers={"Range": "bytes=-65536", "If-Match": etag})
        tail.raise_for_status()
        if tail.status_code != 206 or tail.headers.get("etag") != etag:
            raise ValueError("IP archive changed since the original cohort; do not mix snapshots")
        start = int(tail.headers["content-range"].split()[1].split("-")[0])
        archive = zipfile.ZipFile(io.BytesIO(tail.content))
        for member in ("application.csv", "application_description.csv"):
            info = archive.getinfo(member)
            print("Fetching " + member, flush=True)
            receipt = fetch_member(client, url, etag, info, info.header_offset + start, folder / member)
            print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
