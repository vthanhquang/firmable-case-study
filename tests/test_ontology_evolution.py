import json
from pathlib import Path

import pytest

from firmable.evolution.schema import Inspection, DynamicMapping, Proposal, digest
from firmable.evolution.registry import bootstrap, propose, Registry, write
from firmable.evolution.engine import bind, extract, validate_mapping, drift, project, indexed_cardinality
from firmable.evolution.pipeline import Controller, partition, parse_agent_json, critic_evidence


def inspection(**kw):
    return Inspection.model_validate({"reader": {"format": "json", "record_path": "releases"},
        "bindings": [], "grain": "contract", "identity_cautions": [], "rationale": "test source", **kw})


def mapping():
    return DynamicMapping.model_validate({"source_id": "test", "record_grain": "contract_or_grant",
        "grain_rationale": "One contract per input record", "reader": {"format": "delimited"},
        "record_id": {"strategy": "columns", "source_paths": ["ID"]},
        "entities": {"contract": {"kind": "contract", "key_paths": ["ID"], "rationale": "Publisher contract ID"}},
        "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": .9, "rationale": "Supplier name column"},
                   {"source_paths": ["ABN"], "target": "entity.abn", "steps": [{"op": "abn"}], "confidence": .9, "rationale": "Supplier ABN column"},
                   {"source_paths": ["Amount"], "target": "dyn.contract.amount", "entity": "contract", "steps": [{"op": "parse_decimal"}],
                    "qualifiers": {"currency": {"source_path": "Currency"}}, "confidence": .9, "rationale": "Source contract value"}],
        "relationships": [{"type": "SUPPLIES_CONTRACT", "from_role": "subject", "to_role": "contract", "rationale": "Supplier of this contract"}]})


def proposal():
    return Proposal.model_validate({"entity_types": [{"name": "contract", "definition": "A specific procurement agreement, separate from its supplier."}],
        "concepts": [{"path": "dyn.contract.amount", "type": "decimal", "owner": "contract", "definition": "Published value of this procurement contract, not supplier income.",
            "required_qualifiers": ["currency"], "source_paths": ["Amount"], "why_not_existing": "Business income is a different measure with a different owner."}],
        "relationships": [{"name": "SUPPLIES_CONTRACT", "from_type": "business", "to_type": "contract", "definition": "The business supplies the named procurement contract."}],
        "reuse": {"entity.legal_name": "Supplier legal name"}})


def test_nested_binding_uses_role_not_array_position_and_refuses_ambiguity():
    spec = inspection(bindings=[{"name": "supplier", "collection": "parties", "filter_path": "roles", "filter_value": "supplier"}])
    row = {"parties[0].roles": "buyer", "parties[0].name": "Agency", "parties[1].roles": "supplier", "parties[1].name": "Business"}
    bound, trace = bind(row, spec)
    assert bound["supplier.name"] == "Business"
    assert trace["supplier.name"] == "parties[1].name"
    row["parties[0].roles"] = "supplier"
    bound, error = bind(row, spec)
    assert bound is None and error["matches"] == 2


def test_shared_engine_keeps_amount_on_contract_and_currency_required():
    cfg = mapping()
    row = {"ID": "C1", "Name": "Test Pty Ltd", "ABN": "53004085616", "Amount": "100.50", "Currency": "AUD"}
    registry = propose(bootstrap(), proposal(), row.keys())
    assert not validate_mapping(cfg, registry, row.keys())
    source = {"source_id": "test", "retrieved_at": "2026-11-23T00:00:00Z", "snapshot_sha256": "snapshot",
              "licence_detail": {"id": "cc-by", "known": True}}
    records = [{"ordinal": 1, "record_id": "r1", "row": row}]
    obs, edges, _, _ = extract(cfg, source, registry, records, inspection())
    amount = next(o for o in obs if o["field"] == "dyn.contract.amount")
    assert amount["entity_kind"] == "contract" and amount["qualifiers"] == {"currency": "AUD"}
    assert amount["value"] == 100.5 and edges[0]["type"] == "SUPPLIES_CONTRACT"
    assert amount["ontology_version"] == digest(registry)
    row["Currency"] = ""
    obs, _, _, report = extract(cfg, source, registry, records, inspection())
    assert not any(o["field"] == "dyn.contract.amount" for o in obs)
    assert report["value_errors"] == 1


def test_wrong_owner_and_unknown_columns_fail_static_gate():
    cfg = mapping()
    registry = propose(bootstrap(), proposal(), ["Amount"])
    cfg.fields[2].entity = None
    errors = validate_mapping(cfg, registry, ["ID", "Name", "ABN", "Amount", "Currency", "Unexplained"])
    assert any("Wrong owner" in e for e in errors)
    assert any("Unexplained" in e for e in errors)


def test_ontology_is_additive_and_requires_real_column_evidence():
    with pytest.raises(ValueError, match="source columns"):
        propose(bootstrap(), proposal(), [])
    current = propose(bootstrap(), proposal(), ["Amount"])
    with pytest.raises(ValueError, match="existing entity type"):
        propose(current, proposal(), ["Amount"])


def test_immutable_registry_detects_tampering_and_cannot_promote_unvalidated(tmp_path):
    store = Registry(tmp_path)
    version = store.save(bootstrap())
    with pytest.raises(ValueError, match="not passed"):
        store.promote(version, "human")
    path = tmp_path / "versions" / (version + ".json")
    doc = json.loads(path.read_text()); doc["entity_types"]["business"] = "changed"
    write(path, doc)
    with pytest.raises(ValueError, match="hash mismatch"):
        store.load(version)


def test_checkpoint_only_mode_never_invents_agent_output(tmp_path, monkeypatch):
    from firmable import llm
    monkeypatch.setattr(llm, "LEDGER", llm.LEDGER)
    controller = Controller(tmp_path, live=False)
    with pytest.raises(RuntimeError, match="No saved agent response"):
        controller.agent("inspector", "source", "0", {}, Inspection)


def test_drift_is_visible_and_name_only_entities_abstain():
    assert drift(["Name"], [{"row": {"Name": "x", "New": 1}}])["requires_reinspection"]
    result = project([{"field": "entity.legal_name", "value": "Same Name", "source_id": "new",
                       "entity_ref": "r1", "entity_kind": "business"}], [], [])
    assert not result["links_to_existing_sample"]
    assert result["unlinked_businesses"][0]["reason"] == "NO_VALID_ABN"


def test_identifier_checksum_cannot_be_omitted_or_transformed_after_validation():
    cfg = mapping()
    registry = propose(bootstrap(), proposal(), ["Amount"])
    cfg.fields[1].steps = []
    assert any("checksum" in e for e in validate_mapping(cfg, registry, ["ID", "Name", "ABN", "Amount", "Currency"]))


def test_promotion_checks_evidence_and_concurrent_pointer(tmp_path):
    import hashlib
    store = Registry(tmp_path / "registry")
    version = store.save(bootstrap())
    cfg = mapping()
    write(tmp_path / "test/mapping.json", cfg.model_dump())
    result = {"status": "AGENT_VALIDATED_CANDIDATE", "ontology_version": version, "mapping_digest": cfg.digest()}
    write(tmp_path / "test/result.json", result)
    manifest = {"test/result.json": hashlib.sha256((tmp_path / "test/result.json").read_bytes()).hexdigest()}
    write(tmp_path / "evidence-manifest.json", manifest)
    write(tmp_path / "registry/ready" / (version + ".json"), {"source_id": "test", "result_sha256": digest(result), "manifest_sha256": digest(manifest)})
    store.promote(version, "Test reviewer")
    with pytest.raises(ValueError, match="Production changed"):
        store.promote(version, "Test reviewer")
    store.promote(version, "Test reviewer", expected_current=version)
    result["status"] = "NEEDS_REVIEW"
    write(tmp_path / "test/result.json", result)
    with pytest.raises(ValueError, match="Evidence changed"):
        store.promote(version, "Test reviewer", expected_current=version)


def test_drift_compares_bound_columns_without_false_binding_alias_changes():
    spec = inspection(bindings=[{"name": "supplier", "collection": "parties", "filter_path": "roles", "filter_value": "supplier"}])
    row = {"parties[0].roles": "supplier", "parties[0].name": "Business"}
    expected = list(bind(row, spec)[0])
    assert not drift(expected, [{"row": row}], spec)["requires_reinspection"]


def test_sealed_test_membership_is_content_determined_and_preview_is_discovery():
    assert partition({"ordinal": 1, "record_id": "00000009"}) == "discovery"
    assert partition({"ordinal": 13, "record_id": "00000009"}) == "test"
    assert partition({"ordinal": 13, "record_id": "00000007"}) == "validation"


def test_json_fence_normalization_does_not_edit_semantics_or_accept_extra_prose():
    assert parse_agent_json('```json\n{"amount": 0}\n```') == {"amount": 0}
    with pytest.raises(ValueError):
        parse_agent_json('Here is the result: {"amount": 0}')


def test_observed_timestamp_is_a_consumed_column():
    cfg = mapping()
    cfg.observed_at.source_path = "Published"
    registry = propose(bootstrap(), proposal(), ["Amount"])
    assert not validate_mapping(cfg, registry, ["ID", "Name", "ABN", "Amount", "Currency", "Published"])


def test_repeated_contract_is_refused_instead_of_silently_taking_first():
    cfg = mapping()
    cfg.fields[2].source_paths = ["contracts[0].amount"]
    assert indexed_cardinality(cfg, {"contracts[0].amount": "100"}) is None
    assert indexed_cardinality(cfg, {"contracts[0].amount": "100", "contracts[1].amount": "200"})["members"] == 2


def test_critic_sees_each_field_and_executed_transform_evidence():
    evidence = critic_evidence([{"field": "name", "value": "A"}, {"field": "jurisdiction", "value": "COM"}], {})
    assert set(evidence["examples_by_field_and_role"]) == {"name@subject", "jurisdiction@subject"}
    assert evidence["executed_transform_probe"]["output"] == "A B"
