"""Measure identifier-based overlap against the full ASIC register on independent raw samples."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

from .. import ids
from ..extract import load_config, reliability, verify_snapshot
from ..mapping.engine import Engine
from ..mapping.schema import MappingConfig
from ..paths import ROOT
from ..sources.readers import iter_records
from ..sources.select import load_manifest
from .resolve import EVIDENCE_POLICY, resolve

SOURCES = ("ato_tax_transparency", "acnc_charities", "qbcc_licensees")
SEED = 20261113


def _sample(rows, n):
    rng = random.Random(SEED)
    chosen = []
    scanned = 0
    for scanned, row in enumerate(rows, 1):
        if scanned <= n:
            chosen.append((scanned, row))
        else:
            slot = rng.randrange(scanned)
            if slot < n:
                chosen[slot] = (scanned, row)
    return sorted(chosen), scanned


def _identifier_keys(observations):
    return {(row["field"].split(".")[-1], row["value"]) for row in observations
            if row["field"] in {"entity.abn", "entity.acn"}}


def _raw_asic_identifiers(row):
    abn, acn = (ids.digits(row.get(column)) for column in ("ABN", "ACN"))
    return {("abn", abn), ("acn", acn)}


def _write(path, observations):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for claim in observations:
            stream.write(json.dumps(claim) + "\n")


def run(output: Path, mappings: Path | None = None, sample_size=150) -> dict:
    manifest = load_manifest()
    source_reliability = reliability()

    def engine(sid):
        source = manifest[sid]
        verify_snapshot(source)
        if mappings is None:
            cfg, doc = load_config(sid)
        else:
            doc = json.loads((mappings / f"{sid}.json").read_text(encoding="utf-8"))
            cfg = MappingConfig.model_validate(doc["config"])
            if cfg.digest() != doc["config_digest"]:
                raise ValueError(f"Mapping changed for {sid}")
        if doc["snapshot_sha256"] != source["snapshot"]["sha256"]:
            raise ValueError(f"Snapshot changed for {sid}")
        return Engine(cfg, source, source_reliability.get(sid, source_reliability["default"]))

    stats, sample_claims, sample_keys = {}, {}, defaultdict(set)
    for sid in SOURCES:
        extractor = engine(sid)
        rows, scanned = _sample(iter_records(ROOT / manifest[sid]["snapshot"]["path"], extractor.cfg.reader), sample_size)
        observations = []
        for ordinal, raw in rows:
            claims = extractor.process(raw)
            if claims:
                key = f"{sid}::{claims[0]['source_record_id']}"
                sample_keys[key] = _identifier_keys(claims)
                for claim in claims:
                    claim.update(sample_stratum="independent_raw_sample", source_row_ordinal=ordinal)
                observations.extend(claims)
        sample_claims[sid] = observations
        stats[sid] = {"snapshot_rows_scanned": scanned, "independent_rows_sampled": len(rows),
                      "sample_rows_with_ids": sum(bool(keys) for key, keys in sample_keys.items() if key.startswith(sid + "::"))}
        print(f"{sid}: sampled {len(rows)} independent rows from {scanned}", flush=True)

    lookup = set().union(*sample_keys.values())
    asic = engine("asic_companies")
    asic_claims, asic_keys = [], set()
    scanned, current = 0, 0
    for scanned, raw in enumerate(iter_records(ROOT / manifest["asic_companies"]["snapshot"]["path"], asic.cfg.reader), 1):
        if (raw.get("Current Name Indicator") or "").strip() != "Y":
            continue
        current += 1
        if not (_raw_asic_identifiers(raw) & lookup):
            continue
        claims = asic.process(raw)
        asic_claims.extend(claims)
        asic_keys.update(_identifier_keys(claims))
    with TemporaryDirectory(prefix="firmable-id-coverage-") as path:
        root = Path(path)
        _write(root / "asic_companies.jsonl", asic_claims)
        for sid, claims in sample_claims.items():
            _write(root / f"{sid}.jsonl", claims)
        matched = {key for key, keys in sample_keys.items() if keys & asic_keys}
        for sid in SOURCES:
            stats[sid]["rows_sharing_identifier_with_full_asic"] = sum(key.startswith(sid + "::") for key in matched)
        for policy in ("strict-v2", EVIDENCE_POLICY):
            result = resolve(policy=policy, observations=root)
            by_source = defaultdict(set)
            referrals = defaultdict(set)
            for pair in result["decisions"]:
                if not (pair["a"].startswith("asic_companies::") or pair["b"].startswith("asic_companies::")):
                    continue
                sample_key = pair["b"] if pair["a"].startswith("asic_companies::") else pair["a"]
                if sample_key not in matched:
                    continue
                if pair["decision"] in {"LINK", "REVIEW"}:
                    target = by_source if pair["decision"] == "LINK" else referrals
                    target[sample_key.split("::")[0]].add(sample_key)
            for sid in SOURCES:
                stats[sid][policy] = {"identifier_overlap_rows_linked": len(by_source[sid]),
                                      "identifier_overlap_rows_with_review_pairs": len(referrals[sid])}
    report = {"sample_kind": "seeded independent raw source rows, verified identifier overlap", "seed": SEED,
              "asic_rows_scanned": scanned, "asic_current_name_rows": current, "sources": stats}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mappings", type=Path)
    parser.add_argument("--sample-size", type=int, default=150)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.mappings, args.sample_size), indent=2))
