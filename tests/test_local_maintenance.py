"""Regression checks for the post-review corrections and offline replay safety."""
import json
from pathlib import Path

import pytest

from firmable import llm
from firmable.mapping.engine import Engine
from firmable.mapping.schema import MappingConfig
from firmable.mapping.transforms import op_country_with_region, TransformError
from firmable.rawdata import maintenance

ROOT = Path(__file__).resolve().parents[1]
META = {"source_id": "src", "licence": "cc-by", "publisher": "Test", "title": "Test",
        "resource_last_modified": "2026-11-01T00:00:00+00:00"}


def test_country_requires_explicit_evidence_and_rejects_conflicting_state():
    assert op_country_with_region("Australia|VIC") == "AU"
    assert op_country_with_region("Australia") == "AU"
    assert op_country_with_region("VIC") is None
    assert op_country_with_region("|VIC") is None
    assert op_country_with_region("New Zealand|") == "NZ"
    with pytest.raises(TransformError, match="COUNTRY_REGION_CONFLICT"):
        op_country_with_region("Aruba|VIC", {"ARUBA": "AW"})
    with pytest.raises(TransformError, match="COUNTRY_UNMAPPED"):
        op_country_with_region("Unknown|VIC")


def site_config():
    return {"source_id": "src", "extensions": "ext-v1", "record_grain": "establishment",
        "grain_rationale": "one operating site per row", "reader": {"format": "delimited"},
        "record_id": {"strategy": "content_hash"},
        "entities": {"site": {"kind": "establishment", "key_paths": ["Street"], "rationale": "site address"}},
        "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": .9, "rationale": "operator name"},
                   {"source_paths": ["Street"], "target": "address.full", "entity": "site", "confidence": .9,
                    "claim_scope": "establishment_address", "rationale": "site street"}],
        "constants": [{"target": "address.country", "value": "AU", "entity": "site", "confidence": .9,
                       "claim_scope": "establishment_address", "rationale": "Australian sites register"}]}


def test_constant_follows_role_and_cannot_create_empty_site():
    engine = Engine(MappingConfig.model_validate(site_config()), META)
    output = engine.process({"Name": "Acme", "Street": "1 Main St"}, rid="one")
    country = next(o for o in output if o["field"] == "address.country")
    assert country["entity_role"] == "site" and country["claim_scope"] == "establishment_address"
    assert country["derivation_level"] == "L3"
    absent = engine.process({"Name": "Acme", "Street": ""}, rid="two")
    assert not any(o["entity_role"] == "site" for o in absent)
    broken = site_config()
    broken["constants"][0]["entity"] = "undeclared"
    with pytest.raises(ValueError):
        MappingConfig.model_validate(broken)


def test_offline_blocks_even_previously_cached_api_client(monkeypatch):
    monkeypatch.setenv("FIRMABLE_OFFLINE", "1")
    monkeypatch.setattr(llm, "_client", object())
    with pytest.raises(RuntimeError, match="disabled"):
        llm.client()


def test_changed_interpretation_dependency_requires_revalidation(monkeypatch):
    monkeypatch.setattr(maintenance, "dependencies", lambda cfg: {"engine": "new"})
    with pytest.raises(ValueError, match="dependencies changed"):
        maintenance.verify_dependencies({"config": {}, "local_revision": {"dependencies": {"engine": "old"}}})


def test_windows_dependency_paths_verify_on_any_platform(monkeypatch):
    monkeypatch.setattr(maintenance, "dependencies", lambda cfg: {"firmable/mapping/engine.py": "same"})
    maintenance.verify_dependencies({"config": {}, "local_revision": {
        "dependencies": {"firmable\\mapping\\engine.py": "same"}}})


def test_correction_bundle_preserves_permissions_and_scopes():
    bundle = json.loads((ROOT / "config/maintenance/mapping-corrections-20261117.json").read_text())
    configs = {r["source_id"]: r["config"] for r in bundle["revisions"]}
    credit = MappingConfig.model_validate(configs["asic_credit_licensees"])
    permission = next(r for r in credit.fields if r.target == "ext.licence.authorisation_text")
    date = next(r for r in credit.fields if r.target == "ext.licence.start_date")
    raw = {permission.source_paths[0]: "Permission heading~by providing services~where the service meets conditions",
           date.source_paths[0]: "03/04/2020"}
    out = Engine(credit, META).process(raw, rid="one")
    auth = [o for o in out if o["field"] == permission.target]
    assert len(auth) == 1 and auth[0]["value"] == raw[permission.source_paths[0]]
    assert next(o for o in out if o["field"] == date.target)["value"] == "2020-04-03"
    assert not any(o.get("valid_from") for o in out)
    for sid in ("asic_companies", "ato_tax_transparency"):
        assert not any(c["target"].startswith("address.") for c in configs[sid]["constants"])
    assert not any(r["target"] == "ext.entity.industry_code" for r in configs["qbcc_licensees"]["fields"])
    acnc = configs["acnc_charities"]
    assert not acnc["relationships"]
    assert all(r["claim_scope"] == "entity_contact_address" and not r["entity"]
               for r in acnc["fields"] if r["target"].startswith("address."))


def test_replay_stops_before_later_stages_and_records_failure(tmp_path, monkeypatch):
    from firmable.rawdata import extract, match
    monkeypatch.setattr(maintenance, "OUT_RD_EVAL", tmp_path)
    monkeypatch.setattr(maintenance, "RUNS", tmp_path)
    monkeypatch.setattr(maintenance, "OUT_RAWDATA", tmp_path)
    def fail():
        raise ValueError("invalid mapping")
    monkeypatch.setattr(extract, "run", fail)
    monkeypatch.setattr(match, "run", lambda: pytest.fail("must not resolve incomplete extraction"))
    with pytest.raises(ValueError, match="invalid mapping"):
        maintenance.replay()
    report = json.loads((tmp_path / "local_replay.json").read_text())
    assert report["status"] == "failed" and report["stages"] == []
    assert report["usage_ledgers_unchanged"]
