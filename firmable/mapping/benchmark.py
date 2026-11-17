"""Paired semantic checks on raw rows excluded from onboarding and critic samples."""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from itertools import islice
from pathlib import Path

from .. import ids
from ..agent.review import current_approval
from ..agent.workspace import Workspace, _digest
from ..paths import OUT_MAPPINGS, ROOT
from ..sources.readers import iter_records
from ..sources.select import load_manifest
from .engine import Engine
from .schema import MappingConfig
from .validate import static_issues

SEED = 20261112
BENCHMARK_ROWS = 240

# These checks are evaluation references. The agent never reads them.
NAMES = {
    "acnc_charities": ("Charity_Legal_Name", "entity.legal_name"),
    "asic_credit_licensees": ("CRED_LIC_NAME", "entity.legal_name"),
    "ato_tax_transparency": ("Name", "entity.legal_name"),
    "dewr_employment_providers": ("SITE_NAME", "entity.trading_name"),
    "qbcc_licensees": ("Licensee Name", "entity.legal_name"),
    "vic_liquor": ("Licensee", "entity.legal_name"),
    "qld_suitable_operators": ("Customer Name", "entity.legal_name"),
}
IDENTIFIERS = {
    "asic_companies": {"abn": "ABN", "acn": "ACN"},
    "asic_credit_licensees": {"abn": "CRED_LIC_ABN_ACN", "acn": "CRED_LIC_ABN_ACN"},
    "acnc_charities": {"abn": "ABN"}, "ato_tax_transparency": {"abn": "ABN"},
    "qbcc_licensees": {"abn": "ABN", "acn": "ACN"},
    "qld_suitable_operators": {"abn": "Business Number", "acn": "Business Number"},
}
ABSENT = {"", "none", "nil", "n/a", "na", "not applicable", "-", "null", "unknown", "0"}


def _text(value) -> str | None:
    clean = " ".join(str(value or "").split()).casefold()
    return clean if clean not in ABSENT else None


def _date(value) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _identifier(kind, raw) -> str | None:
    value = ids.digits(raw)
    if kind == "acn" and 0 < len(value) < 9 and str(raw).strip().isdigit():
        value = value.zfill(9)
    check = ids.is_valid_acn if kind == "acn" else ids.is_valid_abn
    return value if check(value) else None


def _expected(source_id: str, raw: dict) -> dict:
    expected = {f"entity.{kind}": _identifier(kind, raw.get(column))
                for kind, column in IDENTIFIERS.get(source_id, {}).items()}
    if source_id == "asic_companies":
        current = _text(raw.get("Current Name Indicator")) == "y"
        expected.update({"entity.legal_name": _text(raw.get("Company Name" if current else "Current Name")),
                         "entity.date_registered": _date(raw.get("Date of Registration")),
                         "entity.status": {"regd": "active", "drgd": "deregistered"}.get(_text(raw.get("Status"))),
                         "address.state": None})
    else:
        column, target = NAMES[source_id]
        expected[target] = _text(raw.get(column))
    if source_id == "acnc_charities":
        expected.update({"entity.trading_name": None, "entity.date_registered": _date(raw.get("Registration_Date"))})
    if source_id in {"qbcc_licensees", "asic_credit_licensees", "vic_liquor", "qld_suitable_operators",
                     "dewr_employment_providers"}:
        expected.update({"entity.status": None, "entity.date_registered": None})
    if source_id == "qld_suitable_operators":
        declared = re.match(r"\s*(ABN|ACN|ARBN)\b", str(raw.get("Business Number") or ""), re.I)
        scheme = declared.group(1).lower() if declared else None
        for kind in ("abn", "acn"):
            if kind != scheme:
                expected[f"entity.{kind}"] = None
        role = _text(raw.get("Entity Type")) or ""
        if role.startswith("corporation"):
            expected["entity.entity_type"] = "company"
        elif "individual" in role:
            expected["entity.entity_type"] = None
            expected["entity.acn"] = None
    return expected


def _scope_errors(source_id, raw, obs):
    scope = obs.get("claim_scope")
    field = obs["field"]
    if source_id == "asic_companies" and scope == "former_legal_name" and obs.get("valid_to"):
        yield "former_name_end_unsupported"
    if source_id == "asic_companies" and field == "entity.status" and obs["value"] == "deregistered":
        if _text(raw.get("Status")) != "drgd":
            yield "deregistered_without_matching_code"
        if obs.get("valid_to"):
            yield "terminal_status_valid_to"
    if field == "entity.date_registered" and source_id in {"asic_companies", "acnc_charities"}:
        expected = "company_registration" if source_id == "asic_companies" else "charity_registration"
        if scope != expected:
            yield "registration_scope_missing_or_wrong"
    if source_id == "qld_suitable_operators" and field == "entity.entity_type" and obs["value"] == "sole_trader":
        if "individual" in (_text(raw.get("Entity Type")) or ""):
            yield "individual_or_sole_trader_guess"


def _sample(source, reference, proposals, seed: int, earlier: set[str]) -> tuple[list[dict], set[str], dict]:
    workspace = Workspace(source)
    excluded, reader_matches = set(), {}
    path = ROOT / source["snapshot"]["path"]
    head = [_digest(r) for r in islice(iter_records(path, reference.reader), 24)]
    for label, cfg in proposals.items():
        preview = [_digest(r) for r in islice(iter_records(path, cfg.reader), 24)]
        reader_matches[label] = bool(head) and preview == head
        if not reader_matches[label]:
            continue
        discovery, holdout, _, _ = workspace.pool(cfg.reader)
        excluded.update(_digest(r) for r in discovery + holdout)
    rng = random.Random(seed)
    rows, eligible = [], 0
    for raw in islice(iter_records(path, reference.reader), 32, 50_000):
        if (fingerprint := _digest(raw)) in excluded or fingerprint in earlier:
            continue
        eligible += 1
        if len(rows) < BENCHMARK_ROWS:
            rows.append(raw)
        else:
            replacement = rng.randrange(eligible)
            if replacement < BENCHMARK_ROWS:
                rows[replacement] = raw
    return rows, excluded, reader_matches


def _score(source, rows, cfg) -> dict:
    engine = Engine(cfg, source, ingested_at="benchmark")
    by_field = defaultdict(Counter)
    scope = Counter()
    holder_names = defaultdict(Counter)
    total_obs = 0
    for row in rows:
        obs = engine.process(row)
        total_obs += len(obs)
        observed = defaultdict(set)
        for claim in obs:
            scope.update(_scope_errors(cfg.source_id, row, claim))
            if claim.get("claim_scope") != "former_legal_name" and (value := _text(claim["value"])):
                observed[claim["field"]].add(value)
        if cfg.source_id == "qld_suitable_operators":
            raw_role = _text(row.get("Entity Type")) or "unrecorded"
            role = "individual_or_sole_trader" if "individual" in raw_role else raw_role
            holder_names[role]["rows"] += 1
            holder_names[role]["names_mapped"] += bool(observed["entity.legal_name"])
        for field, value in _expected(cfg.source_id, row).items():
            expected = {value} if value is not None else set()
            actual = observed[field]
            stats = by_field[field]
            stats["rows"] += 1
            stats["exact"] += actual == expected
            stats["expected_claims"] += len(expected)
            stats["matched_claims"] += len(actual & expected)
            stats["unexpected_claims"] += len(actual - expected)
    totals = sum(by_field.values(), Counter())
    tp, expected, extra = (totals[key] for key in ("matched_claims", "expected_claims", "unexpected_claims"))
    return {"rows": len(rows), "checked_rows_and_fields": totals["rows"], "exact": totals["exact"],
            "matched_claims": tp, "expected_claims": expected, "unexpected_claims": extra,
            "tested_claim_precision": round(tp / (tp + extra), 4) if tp + extra else None,
            "tested_claim_recall": round(tp / expected, 4) if expected else None,
            "canonical_observations": total_obs, "scope_issues": dict(scope), "fields": dict(by_field),
            **({"holder_name_coverage_by_source_role": dict(holder_names)} if holder_names else {})}


def run(experiments: list[Path], output: Path, *, seed=SEED, exclude_report: Path | None = None,
        source_ids: list[str] | None = None) -> dict:
    manifests = load_manifest()
    earlier = json.loads(exclude_report.read_text(encoding="utf-8"))["sources"] if exclude_report else {}
    results = {"protocol": "paired publisher-informed semantic checks on unseen raw rows", "seed": seed, "sources": {}}
    for sid, source in manifests.items():
        if source_ids and sid not in source_ids:
            continue
        if sid not in NAMES and sid != "asic_companies":
            continue
        variants, docs = {}, {}
        for label, path in [("approved_baseline", OUT_MAPPINGS)] + [(folder.name, folder) for folder in experiments]:
            file = path / f"{sid}.json"
            if not file.is_file():
                continue
            doc = json.loads(file.read_text(encoding="utf-8"))
            if doc.get("snapshot_sha256") != source["snapshot"]["sha256"]:
                continue
            cfg = MappingConfig.model_validate(doc["config"])
            if label == "approved_baseline" and not current_approval(sid, doc):
                raise ValueError(f"No eligible frozen approval for {sid}")
            if label != "approved_baseline" and cfg.digest() != doc.get("config_digest"):
                raise ValueError(f"Mapping digest mismatch for {label}/{sid}")
            variants[label], docs[label] = cfg, doc
        if not variants:
            continue
        reference = next(iter(variants.values()))
        prior_hashes = set(earlier.get(sid, {}).get("validation_row_sha256", []))
        rows, excluded, reader_matches = _sample(source, reference, variants, seed, prior_hashes)
        source_result = {"snapshot_sha256": source["snapshot"]["sha256"], "excluded_onboarding_rows": len(excluded),
                         "validation_rows": len(rows), "excluded_previous_evaluation_rows": len(prior_hashes),
                         "validation_row_sha256": sorted({_digest(row) for row in rows}),
                         "reference_reader": reference.reader.model_dump(), "versions": {}}
        headers = {key for row in rows for key in row}
        for label, cfg in variants.items():
            info = {"run_id": docs[label]["run_id"], "status": docs[label]["status"],
                    "config_digest": cfg.digest(), "recorded_config_digest": docs[label].get("config_digest"),
                    "reference_reader_rows_match": reader_matches[label]}
            if reader_matches[label]:
                info.update(_score(source, rows, cfg))
                info["semantic_gate_errors"] = sorted({issue["code"] for issue in static_issues(cfg, headers)
                                                       if issue["severity"] == "error"})
            source_result["versions"][label] = info
        results["sources"][sid] = source_result
        print(f"{sid}: compared {len(variants)} mapping(s) on {len(rows)} unseen rows", flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("experiments", nargs="*", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--exclude-report", type=Path, help="keep previously scored rows out of this split")
    parser.add_argument("--source", action="append", help="evaluate only the specified source IDs")
    args = parser.parse_args()
    run(args.experiments, args.output, seed=args.seed, exclude_report=args.exclude_report, source_ids=args.source)
