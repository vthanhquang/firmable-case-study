"""Evaluate agent-generated profile context on fresh rows from each frozen source."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from .. import ontology
from ..agent.workspace import _digest
from ..extract import reliability, verify_snapshot
from ..sources.select import load_manifest
from .benchmark import _date, _sample
from .engine import Engine
from .schema import MappingConfig, ProfileContextDraft
from .validate import PLACEHOLDER

SOURCES = {
    "ato_tax_transparency": {
        "Income year": "tax.income_year", "Total income $": "tax.total_income_aud",
        "Taxable income $": "tax.taxable_income_aud", "Tax payable $": "tax.tax_payable_aud",
    },
    "acnc_charities": {"Charity_Size": "charity.size", "Date_Organisation_Established": "charity.established_on"},
    "vic_liquor": {
        "Licence Number": "licence.number", "Licence Category": "licence.category", "Trading Hours": "licence.trading_hours",
        "Patron Capacity (if applicable)": "licence.patron_capacity", "Council": "licence.council", "Region": "licence.region",
    },
    "qbcc_licensees": {
        "Licence Number": "licence.number", "Financial Category DESC": "licence.category",
        "Licence Grade": "licence.grade", "Licence Class Type": "licence.class",
    },
    "dewr_employment_providers": {"DIS_SITE_CODE": "establishment.site_code", "CONTRACT_NAME": "establishment.program"},
    "asic_companies": {
        "Class": "company.share_class", "Sub Class": "company.share_subclass",
        "Previous State of Registration": "company.former_registration_jurisdiction",
        "Date of Deregistration": "company.deregistered_on",
    },
}
PURPOSES = {
    "Preventing_or_relieving_suffering_of_animals": "Animal welfare", "Advancing_Culture": "Culture",
    "Advancing_Education": "Education", "Advancing_Health": "Health",
    "Promote_or_oppose_a_change_to_law__government_poll_or_prac": "Public policy and advocacy",
    "Advancing_natual_environment": "Natural environment", "Promoting_or_protecting_human_rights": "Human rights",
    "Purposes_beneficial_to_ther_general_public_and_other_analogous": "General public benefit",
    "Promoting_reconciliation__mutual_respect_and_tolerance": "Reconciliation and tolerance",
    "Advancing_Religion": "Religion", "Advancing_social_or_public_welfare": "Social and public welfare",
    "Advancing_security_or_safety_of_Australia_or_Australian_public": "Public safety",
}


def publisher_text(value):
    return " ".join(str(value).split()) if value is not None else ""


def expected(source_id, row):
    """Independent publisher-column reference for the supported context fields."""
    onto = ontology.load("v1")
    result = set()
    for column, name in SOURCES[source_id].items():
        path = f"context.{name}"
        value = publisher_text(row.get(column))
        kind = onto.fields[path].type
        if not value or (kind != "integer" and PLACEHOLDER.match(value)):
            continue
        if kind == "date":
            value = _date(value)
        elif kind == "integer":
            if not re.fullmatch(r"[+-]?[0-9]+(?:,[0-9]{3})*(?:\.0+)?", value):
                continue
            value = int(Decimal(value.replace(",", "")))
        if onto.check_value(path, value) is None:
            result.add((path, value, (column,)))
    if source_id == "acnc_charities":
        result.update(("context.charity.purpose", label, (key,)) for key, label in PURPOSES.items()
                      if publisher_text(row.get(key)).upper() == "Y")
        result.update(("context.charity.operating_region", state, (f"Operates_in_{state}",))
                      for state in onto.fields["context.charity.operating_region"].values
                      if publisher_text(row.get(f"Operates_in_{state}")).upper() == "Y")
    return result


def load_context_config(base_doc, doc, source):
    base = MappingConfig.model_validate(base_doc["config"])
    cfg = MappingConfig.model_validate(doc["config"])
    added = [rule for rule in cfg.fields if rule.target.startswith("context.")]
    if (doc["status"] != "PENDING_REVIEW" or cfg.source_id != source["source_id"] or cfg.profile_context != "v1" or
            cfg.digest() != doc["config_digest"] or base.digest() != base_doc["config_digest"] or
            doc["ontology_sha256"] != ontology.load("v1").sha256 or
            doc["snapshot_sha256"] != source["snapshot"]["sha256"] or
            base_doc["snapshot_sha256"] != doc["snapshot_sha256"] or
            ProfileContextDraft(fields=added).extend(base) != cfg):
        raise ValueError(f"{source['source_id']}: context draft is unvalidated, stale, or changed the base mapping")
    return base, cfg


def run(base_dir: Path, drafts: Path, *, seed: int = 20261114):
    manifest = load_manifest()
    by_source = {}
    results = drafts / "observations"
    results.mkdir(parents=True, exist_ok=True)
    previous = [json.loads((base_dir.parent / f"evaluation/{name}.json").read_text(encoding="utf-8"))["sources"]
                for name in ("mapping-selection", "mapping-holdout")]
    rel = reliability()
    for sid in SOURCES:
        source = manifest[sid]
        verify_snapshot(source)
        base_doc = json.loads((base_dir / f"{sid}.json").read_text(encoding="utf-8"))
        doc = json.loads((drafts / f"{sid}.json").read_text(encoding="utf-8"))
        base, cfg = load_context_config(base_doc, doc, source)
        earlier = {digest for report in previous for digest in report[sid]["validation_row_sha256"]}
        rows, excluded, readers_match = _sample(source, base, {"context": cfg}, seed, earlier)
        if not readers_match["context"] or len(rows) != 240:
            raise ValueError(f"{sid}: expected 240 fresh rows under the same reader")
        eng = Engine(cfg, source, rel.get(sid, rel.get("default")), ingested_at=source["snapshot"]["downloaded_at"])
        counts, fields = Counter(), defaultdict(Counter)
        out = results / f"{sid}.jsonl"
        with out.open("w", encoding="utf-8", newline="\n") as stream:
            for raw in rows:
                obs = [o for o in eng.process(raw) if o["field"].startswith("context.")]
                for record in obs:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                truth = expected(sid, raw)
                actual = {(item["field"], publisher_text(item["value"]) if isinstance(item["value"], str)
                           else item["value"], tuple(item["source_fields"])) for item in obs}
                for label, claims in (("expected", truth), ("matched", truth & actual), ("unsupported", actual - truth)):
                    counts[label] += len(claims)
                    for field, _, _ in claims:
                        fields[field][label] += 1
        report = eng.report()
        rules = [item for item in report["fields"] if item["target"].startswith("context.")]
        by_source[sid] = {
            "runId": doc["run_id"], "configDigest": doc["config_digest"], "baseDigest": base_doc["config_digest"],
            "rows": len(rows), "expected": counts["expected"], "matched": counts["matched"],
            "unsupported": counts["unsupported"], "observations": counts["matched"] + counts["unsupported"],
            "fields": fields, "rules": rules, "excludedOnboardingRows": len(excluded), "excludedEarlierRows": len(earlier),
            "rowSha256": sorted({_digest(row) for row in rows}),
        }
        print(f"{sid}: {counts['matched']}/{counts['expected']} expected context claims; {counts['unsupported']} unsupported")
    report = {"seed": seed, "ontologySha256": ontology.load("v1").sha256, "sources": by_source}
    (drafts / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("drafts", type=Path)
    args = parser.parse_args()
    run(args.base, args.drafts)
