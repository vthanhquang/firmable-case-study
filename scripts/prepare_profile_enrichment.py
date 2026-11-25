"""Acquire publisher inputs for an isolated, unmapped ingestion experiment.

The IP pilot is a prefix cohort, not a representative sample of all IP rights.
Only transport/container decoding happens here; no ontology/mapping is supplied.
"""
import csv
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
DATA = ROOT / "data/profile-enrichment"
EVIDENCE = ROOT / "outputs/experiments/profile-enrichment"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ip_prefix(url, member="party_activity.csv", rows=25000):
    """Read a bounded CSV cohort via standard ZIP/DEFLATE and HTTP ranges."""
    dest = DATA / "ip_party_activity_prefix.csv"
    receipt = EVIDENCE / "ip-acquisition.json"
    if dest.exists() and receipt.exists():
        record = json.loads(receipt.read_text(encoding="utf-8"))
        if sha(dest) != record["cohort_sha256"]:
            raise ValueError("Existing IP cohort changed")
        return dest, record
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        tail = client.get(url, headers={"Range": "bytes=-65536"})
        tail.raise_for_status()
        if tail.status_code != 206:
            raise ValueError("Publisher must support byte ranges for this bounded pilot")
        start = int(tail.headers["content-range"].split()[1].split("-")[0])
        archive_size = int(tail.headers["content-range"].split("/")[1])
        info = zipfile.ZipFile(io.BytesIO(tail.content)).getinfo(member)
        offset = info.header_offset + start
        length = min(info.compress_size + 4096, 4 * 1024 * 1024)
        headers = {"Range": f"bytes={offset}-{offset + length - 1}"}
        if tail.headers.get("etag"):
            headers["If-Match"] = tail.headers["etag"]
        part = client.get(url, headers=headers)
        part.raise_for_status()
        if part.status_code != 206 or not part.headers.get("content-range", "").startswith(f"bytes {offset}-"):
            raise ValueError("Unexpected IP range response")
        header = struct.unpack("<4s5H3I2H", part.content[:30])
        if header[0] != b"PK\x03\x04" or header[3] != 8:
            raise ValueError("Expected a DEFLATE ZIP member")
        payload = part.content[30 + header[-2] + header[-1]:]
        raw = zlib.decompressobj(-15).decompress(payload, 64 * 1024 * 1024)
        # Strict CSV decoding and a large surplus prevent using the truncated final row.
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        selected = [next(reader) for _ in range(rows + 2)]
        if any(len(r) != len(selected[0]) for r in selected):
            raise ValueError("Unexpected CSV record width in IP prefix")
        with dest.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows(selected[:rows + 1])
        record = {"url": url, "member": member, "archive_bytes": archive_size,
                  "member_bytes": info.file_size, "archive_etag": tail.headers.get("etag"),
                  "content_range": part.headers["content-range"],
                  "compressed_range_sha256": hashlib.sha256(part.content).hexdigest(),
                  "cohort_sha256": sha(dest), "cohort_rows": rows,
                  "selection": "First 25000 CSV records, no filtering; headers and values preserved; CSV serialization normalized.",
                  "limitation": "Prefix-biased acquisition cohort; not full archive ingestion. Full-member CRC cannot be verified from a partial stream.",
                  "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        receipt.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return dest, record


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    manifest = ROOT / "config/profile_enrichment_sources.json"
    sources = json.loads(manifest.read_text(encoding="utf-8"))
    # The manifest supplies publisher URLs and hashes, never mapping rules.
    for source in sources:
        path = ROOT / source["local_path"]
        if source["source_id"] == "ip_party_activity_new":
            continue
        if not path.exists():
            with httpx.stream("GET", source["url"], timeout=120, follow_redirects=True) as response:
                response.raise_for_status()
                with path.open("wb") as stream:
                    for block in response.iter_bytes():
                        stream.write(block)
        if sha(path) != source["snapshot_sha256"]:
            raise ValueError("Publisher snapshot changed; register a new experiment: " + source["source_id"])
    meta = json.loads((EVIDENCE / "iprapid-catalogue.json").read_text(encoding="utf-8"))
    url = next(r["url"] for r in meta["resources"] if r["format"] == "ZIP")
    path, receipt = ip_prefix(url)
    previous = next((s for s in sources if s["source_id"] == "ip_party_activity_new"), None)
    if previous and sha(path) != previous["snapshot_sha256"]:
        raise ValueError("IP publisher cohort changed; register a new experiment instead of replacing evidence")
    if not any(s["source_id"] == "ip_party_activity_new" for s in sources):
        sources.append({"source_id": "ip_party_activity_new", "title": "IP RAPID party activity — 25000-record prefix pilot",
            "publisher": "IP Australia", "url": url,
            "documentation_url": "https://www.ipaustralia.gov.au/tools-and-research/professional-resources/data-research-and-reports/open-ip-data",
            "licence": meta["license_id"], "licence_detail": {"id": meta["license_id"],
                "title": meta["license_title"], "url": meta["license_url"], "known": True,
                "attribution": "IP Australia, IP RAPID; " + url},
            "local_path": path.relative_to(ROOT).as_posix(), "snapshot_sha256": sha(path),
            "snapshot_bytes": path.stat().st_size, "retrieved_at": receipt["retrieved_at"],
            "selection_rationale": "Party involvement in IP applications, with ABNs where supplied; deliberately includes different party types and roles.",
            "notes": "Prefix cohort of party_activity.csv, not the whole archive. No joins to application status, descriptions or classifications. Parties include organisations, individuals and agents; applicant, patentee and agent roles are distinct. A current party activity is not evidence the IP right is currently enforceable. Activity dates are not company incorporation dates. Do not infer legal company status from a name or ABN. " + meta.get("notes", "")[:3000],
            "acquisition": receipt})
        manifest.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    print("Prepared three unmapped publisher inputs; IP scope is a documented prefix pilot.")


if __name__ == "__main__":
    main()
