"""Prepare, verify and scan the Git submission without credentials or model calls.

Run from any directory: python scripts/submission.py prepare|verify|scan|freeze
`freeze` is a maintainer command requiring the original local replay inputs.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "fixtures/replay"
MANIFEST = FIXTURES / "manifest.json"
SOURCES = ("asic_companies", "acnc_charities", "ato_tax_transparency",
           "qbcc_licensees", "vic_liquor", "dewr_employment_providers",
           "asic_credit_licensees", "ato_tax_transparency_2023_24")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def safe_path(base, relative):
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Path escapes submission directory")
    return path


def freeze():
    from firmable.sources.select import load_manifest
    from firmable.licences import detail
    sources = load_manifest()
    paths = []
    for sid in SOURCES:
        paths.extend(sorted((ROOT / "data/rawstore" / sid).glob("*")))
    paths += [ROOT / "data/registered/ato_tax_transparency_2023_24/source.json",
              ROOT / "data/raw/qbcc_licensees_live_20261112"]
    entries = []
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        name = relative.removeprefix("data/") + (".gz" if path.suffix != ".gz" else "")
        target = safe_path(FIXTURES, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        compressed = path.suffix != ".gz"
        if compressed:
            with path.open("rb") as source, target.open("wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as output:
                    shutil.copyfileobj(source, output)
        else:
            shutil.copyfile(path, target)
        entries.append({"file": name, "restore_to": relative, "gzip": compressed,
                        "sha256": digest(target), "restored_sha256": digest(path),
                        "restored_bytes": path.stat().st_size})
    doc = {"description": "Frozen sampled publisher rows plus the second QBCC snapshot for change detection; not the full eight source resources.",
           "files": entries, "sources": {sid: {"metadata": sources[sid], "licence": detail(sources[sid])} for sid in SOURCES}}
    MANIFEST.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Froze {len(entries)} inputs; {sum((FIXTURES / e['file']).stat().st_size for e in entries):,} bytes")


def prepare():
    for entry in read(MANIFEST)["files"]:
        source = safe_path(FIXTURES, entry["file"])
        destination = safe_path(ROOT / "data", str(Path(entry["restore_to"]).relative_to("data")))
        if digest(source) != entry["sha256"]:
            raise ValueError("Fixture checksum mismatch: " + entry["file"])
        if destination.exists():
            if digest(destination) != entry["restored_sha256"]:
                raise ValueError("Existing input differs; move it aside before preparing: " + entry["restore_to"])
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".prepare.tmp")
        opener = gzip.open if entry["gzip"] else open
        try:
            with opener(source, "rb") as stream, temporary.open("wb") as output:
                shutil.copyfileobj(stream, output)
            if digest(temporary) != entry["restored_sha256"]:
                raise ValueError("Restored checksum mismatch: " + entry["restore_to"])
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    print("Frozen inputs prepared and SHA-256 verified. No downloads or API calls.")


def verify():
    from firmable.mapping.schema import MappingConfig
    from firmable.rawdata.maintenance import verify_dependencies
    from firmable.rawdata.review import approval_state
    from firmable.rawdata.audit import load_reviews
    raw = ROOT / "outputs/raw-data"
    for required in ("README.md", "WRITEUP.md", "docs/ASSIGNMENT_ANSWERS.md",
                     "reports/assignment-report.html", "output/pdf/firmable-writeup.pdf",
                     "output/pdf/firmable-writeup.tex", "frontend/public/system-architecture.svg"):
        if not (ROOT / required).is_file():
            raise ValueError("Missing deliverable: " + required)
    for sid in SOURCES:
        doc = read(raw / "mappings" / (sid + ".json"))
        if MappingConfig.model_validate(doc["config"]).digest() != doc["config_digest"]:
            raise ValueError("Mapping digest mismatch: " + sid)
        verify_dependencies(doc)
        if approval_state(sid) != "approved":
            raise ValueError("Mapping approval missing or stale: " + sid)
        if not (ROOT / "runs" / sid / doc["run_id"] / "state.json").is_file():
            raise ValueError("Missing mapping trace: " + sid)
    with (ROOT / "outputs/discovery/category_ranked/shortlist.csv").open(encoding="utf-8-sig", newline="") as f:
        shortlist = list(csv.DictReader(f))
    links = rows(raw / "identity/proposed_links.jsonl")
    queue = rows(raw / "identity/unlinked_queue.jsonl")
    profiles = rows(raw / "profiles/company_profiles_v3_50.jsonl")
    observations = [row for sid in SOURCES for row in rows(raw / "observations" / (sid + ".jsonl"))]
    for link in links:
        if not {"source_a_record", "source_b_record", "canonical_entity_key", "confidence", "evidence"} <= link.keys():
            raise ValueError("Proposed link misses a required field")
    with (raw / "evaluation/link_audit_strict_v3_raw_50.csv").open(encoding="utf-8-sig", newline="") as f:
        audit = list(csv.DictReader(f))
    reviews = load_reviews(raw / "evaluation/link_review_decisions.jsonl", {r["link_id"]: r for r in links})
    pairs = {(r["source_a_record"], r["source_b_record"]): r["link_id"] for r in links}
    human = [reviews.get(pairs[(row["record_a"], row["record_b"])], {}).get("human", {}) for row in audit]
    if sum(row.get("verdict") == "pass" for row in human) != 46 or sum(row.get("verdict") == "fail" for row in human) != 4:
        raise ValueError("Expected 46 pass / 4 fail evidence-bound human link decisions")
    discovery_audit = read(ROOT / "outputs/discovery/category_ranked/audit/metrics.json")
    if digest(ROOT / "outputs/discovery/category_ranked/shortlist.jsonl") != discovery_audit["shortlist_sha256"]:
        raise ValueError("Shortlist bytes differ from the reviewed version")
    if discovery_audit["human_review"]["reviewed"] != 20 or discovery_audit["human_review"]["no"] != 0:
        raise ValueError("Discovery human audit differs from the frozen report")
    counts = {"shortlist": len(shortlist), "sources": len(SOURCES), "observations": len(observations),
              "links": len(links), "unlinked": len(queue), "profiles": len(profiles), "audit": len(audit)}
    expected = {"shortlist": 50, "sources": 8, "observations": 85446, "links": 1455,
                "unlinked": 1245, "profiles": 50, "audit": 50}
    if counts != expected:
        raise ValueError("Frozen result counts differ: " + json.dumps(counts))
    if not all(row.get("licence_detail", {}).get("known") for row in observations):
        raise ValueError("Observation lacks a known licence")
    # Evidence binding and human decisions are also checked by the demo exporter.
    print(json.dumps(counts, indent=2))
    print("Deliverables, mapping approvals, dependencies, provenance licences and counts verified.")
    print("Human precision: 46/50 (92%) at threshold 0.85; discovery false positives: 0/20.")


SECRET = re.compile(rb"(?:(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def candidate_files():
    result = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                            cwd=ROOT, capture_output=True, check=True)
    names = sorted(set(result.stdout.decode("utf-8").split("\0")) - {""})
    return [name for name in names if (ROOT / name).is_file()]


def scan():
    names = candidate_files()
    bad = []
    for name in names:
        path = ROOT / name
        if path.is_symlink() or path.name.startswith(".env") and path.name != ".env.example":
            bad.append(name)
            continue
        data = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        if SECRET.search(data):
            bad.append(name)
    if bad:
        raise ValueError("Sensitive material detected; values withheld. Files: " + ", ".join(bad))
    print(f"Scanned {len(names)} repository files: no API-key/private-key patterns or credential files found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "verify", "scan", "freeze"])
    args = parser.parse_args()
    globals()[args.action]()
