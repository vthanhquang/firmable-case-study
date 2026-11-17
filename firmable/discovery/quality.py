"""Re-rank a frozen catalogue using bounded previews of the publisher's data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import islice
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import httpx
from openpyxl import load_workbook

from .. import ids
from ..mapping.schema import ReaderSpec
from ..paths import OUT_DISCOVERY, OUT_EVAL, OUT_SOURCES, ROOT
from ..sources.inspect import _decode
from ..sources.readers import head
from .triage import PORTAL, score_package

VERSION = "data-evidence-v6-catalogue-five"
PREVIEW_CACHE_VERSION = "data-evidence-v3"
PUBLISHER_WEIGHTS = {
    "business_evidence": 45,
    "valid_identifier": 20,
    "corporate_name": 10,
    "business_name": 10,
    "identifier_and_name": 10,
}
PUBLISHER_MAX_POINTS = sum(PUBLISHER_WEIGHTS.values())
CATALOGUE_POINTS = {"strong": 5, "corroborated": 3, "single": 1}
CATALOGUE_MAX_POINTS = max(CATALOGUE_POINTS.values())
RANKING_MAX_POINTS = PUBLISHER_MAX_POINTS + CATALOGUE_MAX_POINTS
FORMATS = {"CSV", "TSV", "XLSX", "JSON", "ZIP"}
SAMPLE_ROWS = 50
NAME_ROLE = re.compile(r"\b(?:business|company|legal|trading|entity|organisation|organization|supplier|vendor|"
                       r"contractor|provider|employer|operator|licensee|licence holder|charity|recipient|"
                       r"tenderer|registered|corporate|firm|agent)\b")
NON_ENTITY = re.compile(r"\b(?:contact|officer|inspector|street|road|sheet|file|suburb|park|region|facility|"
                        r"month|form|project|classification|program|role|position|first|given|last|family)\b")
AGGREGATE = re.compile(r"\b(?:count|total|number of|mean|median|percent|average|rate|summary|statistics)\b")
COMPANY = re.compile(r"\b(?:pty|limited|ltd|incorporated|inc|corporation|llc)\b", re.I)
PUBLIC_BODY_DIRECTORY = re.compile(
    r"(?:(?:australian|commonwealth|state|territory|local) )?"
    r"(?:government organi[sz]ations|public sector bodies) (?:register|directory|list)"
)
IDENTIFIERS = (
    (re.compile(r"\babn\b|australian business number"), ids.is_valid_abn),
    (re.compile(r"\bacn\b|australian company number"), ids.is_valid_acn),
    (re.compile(r"\bnzbn\b|new zealand business number"), ids.is_valid_nzbn),
    (re.compile(r"\bbusiness number\b"), lambda v: ids.is_valid_abn(v) or ids.is_valid_acn(v)),
)


def _words(value) -> str:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(value))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _format(resource) -> str:
    fmt = (resource.get("format") or "").upper().strip()
    if fmt == "XLSX" or "XLSX" in fmt or fmt in {"EXCEL", "EXCEL SPREADSHEET"}:
        return "XLSX"
    if fmt in FORMATS:
        return fmt
    return urlsplit(resource.get("url") or "").path.rpartition(".")[2].upper()


def _table_score(rows: list[dict]) -> dict:
    fields, valid_rows, named_rows, company_rows = [], set(), set(), set()
    keys = list(dict.fromkeys(str(key) for row in rows for key in row if key and key != "_id"))[:120]
    for key in keys:
        label = _words(key)
        if AGGREGATE.search(label) or NON_ENTITY.search(label):
            continue
        validator = next((check for pattern, check in IDENTIFIERS if pattern.search(label)), None)
        values = [(i, str(row[key]).strip()) for i, row in enumerate(rows) if row.get(key) is not None and
                  str(row[key]).strip().casefold() not in {"", "0", "n/a", "na", "nil", "none", "null", "-"}]
        if validator:
            valid = {i for i, value in values if validator(value)}
            if len(valid) >= 2 and len(valid) >= 0.5 * len(values):
                valid_rows.update(valid)
                fields.append({"field": key, "signal": "checksum_valid_identifier", "count": len(valid)})
        named = ("name" in label.split() or label in {"supplier", "contractor", "licensee", "licence holder", "charity"})
        if named or label in {"customer", "entity"}:
            names = {i: value for i, value in values if len(value) >= 3 and any(c.isalpha() for c in value)}
            corporate = {i for i, value in names.items() if COMPANY.search(value)}
            if len(corporate) >= 2:
                company_rows.update(corporate)
                fields.append({"field": key, "signal": "corporate_name_suffix", "count": len(corporate)})
            if named and NAME_ROLE.search(label) and len(set(names.values())) >= 2:
                named_rows.update(names)
                fields.append({"field": key, "signal": "named_business_role", "count": len(names)})
    n = len(rows)
    positive = valid_rows | named_rows | company_rows
    support = max(n, 10)
    # Evidence quality is a ranking score. Partial samples, generic names and
    # repeated schema synonyms cannot inflate it beyond the observed row counts.
    score = 0.0
    if positive:
        score = 0.58 + 0.22 * len(valid_rows) / support + 0.10 * len(company_rows) / support
        score += 0.07 * len(named_rows) / support + 0.025 * len(valid_rows & named_rows) / support
    return {"sampled_rows": n, "columns": len(keys), "fields": fields, "business_rows": len(positive),
            "row_score": round(score, 5), "row_signal_counts": {
                "valid_identifier": len(valid_rows), "corporate_name": len(company_rows),
                "business_name": len(named_rows), "identifier_and_name": len(valid_rows & named_rows),
            }}


def _header_rows(table) -> list[list[dict]]:
    first = list(islice(table, SAMPLE_ROWS + 12))
    results = []
    for start, row in enumerate(first[:10]):
        names = [str(cell).strip()[:120] if cell is not None else "" for cell in row[:120]]
        if sum(bool(cell) for cell in names) < 2 or len(set(filter(None, names))) < 2:
            continue
        body = [dict(zip(names, values)) for values in first[start + 1:] if any(v not in (None, "") for v in values)]
        if body:
            results.append(body[:SAMPLE_ROWS])
    return results


def _delimited(body: bytes, truncated=False) -> list[list[dict]]:
    text, _ = _decode(body)
    if truncated:
        text = text.rsplit("\n", 1)[0]
    if text.lstrip().startswith(("<", "{", "[")):
        return []
    results = []
    for delimiter in (",", "\t", ";", "|"):
        results.extend(_header_rows(csv.reader(io.StringIO(text), delimiter=delimiter)))
    return results


def _workbook(body: bytes) -> list[list[dict]]:
    book = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    try:
        return [rows for sheet in book.worksheets[:4]
                for rows in _header_rows(sheet.iter_rows(max_col=min(sheet.max_column or 120, 120), values_only=True))]
    finally:
        book.close()


def _records(body: bytes) -> list[list[dict]]:
    doc = json.loads(body)
    if isinstance(doc, dict):
        doc = doc.get("result", doc)
        doc = doc.get("records", doc.get("data", [])) if isinstance(doc, dict) else doc
    if not isinstance(doc, list):
        return []
    rows = [row for row in doc[:SAMPLE_ROWS] if isinstance(row, dict)]
    return [rows] if rows else []


def _fetch(client, url, cap) -> tuple[bytes, bool]:
    with client.stream("GET", url) as response:
        if response.status_code not in {200, 206}:
            raise ValueError(f"HTTP {response.status_code}")
        chunks = bytearray()
        for chunk in response.iter_bytes(chunk_size=16384):
            chunks.extend(chunk[:cap + 1 - len(chunks)])
            if len(chunks) > cap:
                break
    return bytes(chunks[:cap]), len(chunks) > cap


def _preview(client, resource, snapshots, *, prefer_datastore=False) -> tuple[list[list[dict]], str]:
    rid, url = resource["id"], resource.get("url") or ""
    if rid in snapshots:
        path, reader = snapshots[rid]
        return [head(path, reader, SAMPLE_ROWS)], "frozen_publisher_snapshot"
    if urlsplit(url).scheme not in {"https", "http"}:
        raise ValueError("public HTTP resource URL unavailable")
    fmt = _format(resource)
    if fmt in FORMATS and not prefer_datastore:
        cap = 8_000_000 if fmt in {"ZIP", "XLSX"} else 1_000_000 if fmt == "JSON" else 140_000
        try:
            body, clipped = _fetch(client, url, cap)
            if fmt in {"CSV", "TSV"}:
                results = _delimited(body, clipped)
            elif clipped:
                results = []
            elif fmt == "XLSX":
                results = _workbook(body)
            elif fmt == "ZIP":
                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                    files = [item for item in archive.infolist() if item.filename.lower().endswith((".csv", ".tsv"))]
                    results = []
                    for item in files[:3]:
                        with archive.open(item) as data:
                            results.extend(_delimited(data.read(140_000), item.file_size > 140_000))
            else:
                results = _records(body)
            if results:
                return results, "publisher_file_preview"
        except (httpx.HTTPError, ValueError, zipfile.BadZipFile, OSError, KeyError):
            pass
    host = urlsplit(url).hostname or ""
    portals = [f"https://{host}", PORTAL] if host in {"www.data.qld.gov.au", "data.qld.gov.au", "data.sa.gov.au"} else [PORTAL]
    for portal in portals:
        try:
            body, clipped = _fetch(client, f"{portal}/api/3/action/datastore_search?resource_id={rid}&limit={SAMPLE_ROWS}", 600_000)
            results = [] if clipped else _records(body)
            if results:
                return results, "public_datastore_records"
        except (httpx.HTTPError, ValueError, OSError):
            pass
    if prefer_datastore:
        return _preview(client, resource, snapshots)
    return [], "rows_unavailable"


def _catalogue_signals(pkg) -> tuple[float, list[str]]:
    resources = []
    for resource in pkg["resources"]:
        format_name = _format(resource)
        resources.append(resource | {"format": format_name} if format_name in FORMATS else resource)
    compact = {"title": pkg["title"], "organization": {"title": pkg.get("organisation")}, "resources": resources}
    return score_package(compact)


def _metadata(pkg) -> float:
    return _catalogue_signals(pkg)[0]


def _catalogue_category(reasons: list[str]) -> dict:
    signals = {reason.partition("(")[0] for reason in reasons}
    cautions = signals & {"aggregate_terms", "spatial_terms", "officials_terms"}
    explicit = signals & {"identifier_terms", "entity_name_terms"}
    context = signals & {"entity_title", "register_title", "contract_terms", "publisher_regulator"}
    if cautions:
        return {"label": "Mixed catalogue signals", "points": 0, "signals": sorted(cautions)}
    if "machine_readable" not in signals:
        return {"label": "No machine-readable format listed", "points": 0, "signals": sorted(signals & {"documents_only"})}
    if explicit:
        return {"label": "Explicit identifier or business name", "points": CATALOGUE_MAX_POINTS, "signals": sorted(explicit)}
    if "register_title" in context and context & {"entity_title", "publisher_regulator"}:
        return {"label": "Business register context", "points": CATALOGUE_MAX_POINTS, "signals": sorted(context)}
    if len(context) >= 2:
        return {"label": "Corroborated business context", "points": CATALOGUE_POINTS["corroborated"], "signals": sorted(context)}
    if context:
        return {"label": "Single business signal", "points": CATALOGUE_POINTS["single"], "signals": sorted(context)}
    return {"label": "Format only", "points": 0, "signals": []}


def _row_signal_counts(evidence: dict) -> dict[str, int]:
    if "row_signal_counts" in evidence:
        return evidence["row_signal_counts"]
    names = ("valid_identifier", "corporate_name", "business_name", "identifier_and_name")
    total = evidence.get("business_rows", 0)
    if not total:
        return dict.fromkeys(names, 0)

    # Older frozen previews retain per-column counts and the original row score.
    # Undo that score's rounding to recover its integer numerator, then accept
    # the per-row counts only when one tuple satisfies the recorded evidence.
    support = max(10, evidence["sampled_rows"])
    numerator = round((evidence["row_score"] - 0.58) * support * 200)

    def possible_totals(signal):
        counts = [field["count"] for field in evidence["fields"] if field["signal"] == signal]
        return range(max(counts, default=0), min(total, sum(counts)) + 1)

    matches = []
    for valid in possible_totals("checksum_valid_identifier"):
        for corporate in possible_totals("corporate_name_suffix"):
            for named in possible_totals("named_business_role"):
                shared, remainder = divmod(numerator - 44 * valid - 20 * corporate - 14 * named, 5)
                union = valid + named - shared
                if (not remainder and 0 <= shared <= min(valid, named) and
                        max(union, corporate) <= total <= union + corporate):
                    matches.append((valid, corporate, named, shared))
    if len(matches) != 1:
        raise ValueError(f"Reopen resource {evidence.get('resource_id')} to determine its row signal counts")
    return dict(zip(names, matches[0]))


def _rank_score(evidence: dict, reasons: list[str]) -> tuple[float, dict]:
    counts = _row_signal_counts(evidence)
    support = max(10, evidence.get("sampled_rows", 0))
    rubric = {"business_evidence": PUBLISHER_WEIGHTS["business_evidence"] if evidence.get("business_rows") else 0}
    for name, count in counts.items():
        rubric[name] = round(PUBLISHER_WEIGHTS[name] * count / support, 3)
    publisher_points = round(sum(rubric.values()), 3)
    category = _catalogue_category(reasons)
    ranking_points = round(publisher_points + category["points"], 3)
    return round(ranking_points / RANKING_MAX_POINTS, 6), {
        "publisher_points": publisher_points, "catalogue_category": category, "ranking_points": ranking_points,
        "publisher_breakdown": [
            {"rule": rule, "max_points": PUBLISHER_WEIGHTS[rule], "points": points,
             "matching_rows": evidence.get("business_rows", 0) if rule == "business_evidence" else counts[rule],
             "support": None if rule == "business_evidence" else support}
            for rule, points in rubric.items()
        ],
    }


def _inspect(pkg, client, snapshots, cache: Path, max_resources: int, previous=None) -> dict:
    resource_order = sorted(pkg["resources"], key=lambda resource: (
        resource["id"] in snapshots, _format(resource) in FORMATS,
        resource.get("last_modified") or "", _format(resource) in {"CSV", "TSV"},
    ), reverse=True)
    evidence = [previous["evidence"]] if previous and previous["evidence"] else []
    attempts = previous["attempts"] if previous else []
    inspected = {attempt["resource_id"] for attempt in attempts}
    for resource in resource_order[:max_resources]:
        if evidence and max(table["row_score"] for table in evidence) >= 0.85:
            break
        rid = resource["id"]
        if rid in inspected:
            continue
        try:
            previews, route = _preview(client, resource, snapshots)
            tables = [_table_score(rows) for rows in previews]
        except Exception as exc:
            tables, route = [], type(exc).__name__
        attempts.append({"resource_id": rid, "route": route})
        if tables:
            table = max(tables, key=lambda t: (t["row_score"], t["sampled_rows"], t["columns"]))
            evidence.append(table | {"resource_id": rid, "route": route, "url": resource.get("url")})
    best = max(evidence, key=lambda t: (t["row_score"], t["sampled_rows"], t["columns"]), default={})
    data = {"dataset_id": pkg["dataset_id"], "title": pkg["title"], "publisher": pkg.get("organisation"),
            "metadata_score": _metadata(pkg), "evidence": best, "attempts": attempts}
    cache.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def _snapshots() -> dict:
    sources = json.loads((OUT_SOURCES / "selected_sources.json").read_text(encoding="utf-8"))
    snapshots = {}
    for source in sources:
        if "snapshot" not in source:
            continue
        path = ROOT / source["snapshot"]["path"]
        mapping = ROOT / "outputs" / "mappings" / f"{source['source_id']}.json"
        if path.is_file() and mapping.is_file():
            spec = ReaderSpec.model_validate(json.loads(mapping.read_text(encoding="utf-8"))["config"]["reader"])
            snapshots[source["resource_id"]] = (path, spec)
    return snapshots


def run(output: Path, candidate_count=200, workers=10, max_resources=2, *, cache_root: Path | None = None,
        reuse_candidates: Path | None = None) -> dict:
    pool_path = OUT_DISCOVERY / "catalogue_pool.jsonl"
    pool = {row["dataset_id"]: row for line in pool_path.read_text(encoding="utf-8").splitlines()
            if (row := json.loads(line))}
    audits = []
    for name in ("triage_audit_20.csv", "triage_audit_v2_20.csv"):
        with (OUT_EVAL / name).open(encoding="utf-8", newline="") as stream:
            audits.append((name, list(csv.DictReader(stream))))
    ranked = sorted(pool.values(), key=lambda row: (-_metadata(row), row["dataset_id"]))
    # Evaluation candidates outside the retrieval pool are probed for scoring
    # coverage, but are never eligible for the shortlist on that basis.
    shortlist_ids = {p["dataset_id"] for p in ranked[:candidate_count]}
    audit_ids = {row["dataset_id"] for _, audit in audits for row in audit}
    ids_to_probe = shortlist_ids | audit_ids
    candidates = [pkg for pkg in ranked if pkg["dataset_id"] in ids_to_probe]
    output.mkdir(parents=True, exist_ok=True)
    if reuse_candidates:
        rows = [json.loads(line) for line in reuse_candidates.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(rows) != len(ids_to_probe) or {row["dataset_id"] for row in rows} != ids_to_probe:
            raise ValueError("The frozen candidate file must cover the exact probe population")
    else:
        cache = (cache_root or output / "evidence") / f"{PREVIEW_CACHE_VERSION}-r{max_resources}"
        cache.mkdir(parents=True, exist_ok=True)
        snapshots = _snapshots()
        with httpx.Client(timeout=10, follow_redirects=True, headers={"User-Agent": "firmable-case-study/0.2"}) as client:
            def inspect(pkg):
                path = cache / f"{pkg['dataset_id']}.json"
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8"))
                prior = cache.parent / f"{PREVIEW_CACHE_VERSION}-r{max_resources - 1}" / path.name
                previous = json.loads(prior.read_text(encoding="utf-8")) if prior.exists() else None
                return _inspect(pkg, client, snapshots, path, max_resources, previous)

            with ThreadPoolExecutor(max_workers=workers) as executor:
                rows = list(executor.map(inspect, candidates))

    by_id = {}
    for row in rows:
        pkg = pool[row["dataset_id"]]
        row["metadata_score"], reasons = _catalogue_signals(pkg)
        row["score"], row["score_components"] = _rank_score(row["evidence"], reasons)
        row["status"] = "KEEP" if row["evidence"].get("business_rows", 0) >= 2 else "REVIEW"
        row["resource_formats"] = "|".join(sorted({(res.get("format") or "?").upper() for res in pkg["resources"]}))
        row["url"] = f"{PORTAL}/dataset/{pkg['name']}"
        evidence = row["evidence"]
        signals = ", ".join(dict.fromkeys(field["field"] for field in evidence.get("fields", [])))
        row["reason"] = (f"{evidence['business_rows']}/{evidence['sampled_rows']} rows expose business signals in {signals}."
                         if signals else "No conclusive business identity in the available row previews.")
        if PUBLIC_BODY_DIRECTORY.fullmatch(_words(row["title"])):
            row.update(status="EXCLUDE", reason="The directory identifies public bodies.")
        by_id[row["dataset_id"]] = row
    rows.sort(key=lambda row: (-row["score_components"]["ranking_points"], row["dataset_id"]))
    selected, deferred, publishers, families, exports = [], [], Counter(), set(), set()
    for row in rows:
        if row["dataset_id"] not in shortlist_ids or row["status"] != "KEEP" or publishers[row["publisher"]] >= 4:
            continue
        title = re.sub(r"\b(?:19|20)\d{2}(?:[ /-]\d{2,4})?\b", "", row["title"])
        family = (row["publisher"], _words(title))
        url = urlsplit(row["evidence"]["url"])
        # A delimiter changes the representation of a CSV export, not its records.
        query = tuple(sorted((key, value) for key, value in parse_qsl(url.query, keep_blank_values=True)
                             if key != "delimiter"))
        export = (_words(row["title"]), url.netloc, url.path, query)
        if export in exports:
            continue
        exports.add(export)
        if family in families:
            deferred.append(row)
            continue
        families.add(family)
        publishers[row["publisher"]] += 1
        selected.append(row)
        if len(selected) == 50:
            break
    for row in deferred:
        if len(selected) == 50:
            break
        if publishers[row["publisher"]] < 4:
            publishers[row["publisher"]] += 1
            selected.append(row | {"repeat_series": True})
    selected = [{"rank": i, **row} for i, row in enumerate(selected, 1)]
    metrics = {"version": VERSION, "catalogue_sha256": hashlib.sha256(pool_path.read_bytes()).hexdigest(),
               "catalogue_candidates": len(pool), "retrieval_candidates": len(shortlist_ids), "probed": len(rows),
               "rows_read": sum(bool(row["evidence"]) for row in rows),
               "keep_candidates": sum(row["status"] == "KEEP" for row in rows), "shortlist": len(selected),
               "distinct_shortlist_scores": len({row["score"] for row in selected}), "proxy_audits": {},
               "publisher_max_points": PUBLISHER_MAX_POINTS, "ranking_max_points": RANKING_MAX_POINTS,
               "catalogue_category_points": CATALOGUE_POINTS}
    if reuse_candidates:
        metrics["frozen_candidates_sha256"] = hashlib.sha256(reuse_candidates.read_bytes()).hexdigest()
    for name, audit in audits:
        decisions = {status: Counter() for status in ("KEEP", "REVIEW", "EXCLUDE")}
        for row in audit:
            decision = by_id.get(row["dataset_id"], {}).get("status", "REVIEW")
            decisions[decision][row["label"] or "UNLABELLED"] += 1
        metrics["proxy_audits"][name] = decisions
    for name, values in (("shortlist.jsonl", selected), ("candidates.jsonl", rows)):
        (output / name).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in values), encoding="utf-8")
    fields = ("rank", "dataset_id", "title", "publisher", "resource_formats", "confidence",
              "ranking_points", "publisher_points", "catalogue_category", "catalogue_points",
              "reason", "url", "evidence_url")
    with (output / "shortlist.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in selected:
            components = row["score_components"]
            category = components["catalogue_category"]
            writer.writerow(row | {"confidence": row["score"], "evidence_url": row["evidence"]["url"],
                                   "ranking_points": components["ranking_points"],
                                   "publisher_points": components["publisher_points"],
                                   "catalogue_category": category["label"], "catalogue_points": category["points"]})
    review_input = []
    for row in rows:
        if row["status"] != "KEEP":
            continue
        evidence = row["evidence"]
        resource = next(res for res in pool[row["dataset_id"]]["resources"] if res["id"] == evidence["resource_id"])
        details = {key: evidence[key] for key in ("sampled_rows", "fields", "business_rows", "columns")}
        review_input.append({"rank": len(review_input) + 1, "dataset_id": row["dataset_id"], "title": row["title"],
                             "publisher": row["publisher"] or "Unknown",
                             "notes": "Evidence r1 summarizes the inspected publisher rows, including checksum verification.",
                             "resources": [{"id": "r1", "name": resource.get("name") or resource["id"],
                                            "format": _format(resource), "route": evidence["route"],
                                            "evidence": {"kind": "records", "evidence_id": "r1", **details}}]})
    (output / "review-input.json").write_text(json.dumps(review_input, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--candidates", type=int, default=200)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--resources", type=int, default=2)
    parser.add_argument("--cache", type=Path, help="reuse a previous run's evidence directory")
    parser.add_argument("--reuse-candidates", type=Path, help="rerank the exact frozen publisher evidence in candidates.jsonl")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.candidates, args.workers, args.resources, cache_root=args.cache,
                         reuse_candidates=args.reuse_candidates), indent=2))
