"""Part 3 end to end on tiny synthetic observations: output contract, refusal on conflict, queue, relationships."""
import json

import pytest

from firmable.identity import resolve as R

A_ABN, B_ABN = "51824753556", "53004085616"   # two different checksum-valid ABNs


def _write(path, source, rows, grain="legal_entity"):
    with open(path / f"{source}.jsonl", "w", encoding="utf-8") as fh:
        for rid, fields in rows.items():
            for field, value in fields:
                fh.write(json.dumps({"source_id": source, "source_record_id": rid, "record_grain": grain,
                                     "field": field, "value": value, "sample_stratum": "random"}) + "\n")


@pytest.fixture
def out(tmp_path, monkeypatch):
    obs, ident = tmp_path / "obs", tmp_path / "identity"
    obs.mkdir()
    monkeypatch.setattr(R, "OUT_OBS", obs)
    monkeypatch.setattr(R, "OUT_IDENTITY", ident)
    _write(obs, "reg", {"r1": [("entity.legal_name", "ACME PTY LTD"), ("entity.abn", A_ABN)],
                        "r2": [("entity.legal_name", "SAMENAME HOLDINGS PTY LTD"), ("entity.abn", B_ABN)]})
    _write(obs, "tax", {"t1": [("entity.legal_name", "Acme Pty Ltd"), ("entity.abn", A_ABN)]})
    _write(obs, "lic", {"l1": [("entity.legal_name", "SAMENAME HOLDINGS PTY LTD"), ("entity.abn", A_ABN)],
                        "l2": [("entity.legal_name", "JOHN CITIZEN"), ("address.postcode", "3000")]},
           grain="licence_or_permit")
    R.run()
    return ident


def _jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def test_link_output_contract(out):
    links = _jsonl(out / "proposed_links.jsonl")
    assert links, "expected at least the reg/tax ABN link"
    for l in links:
        for k in ("source_a_record", "source_b_record", "canonical_entity_key", "confidence", "evidence"):
            assert k in l
    pairs = {frozenset((l["source_a_record"], l["source_b_record"])) for l in links}
    assert frozenset(("reg::r1", "tax::t1")) in pairs


def test_same_name_different_abn_is_refused_queued_and_flagged(out):
    links = _jsonl(out / "proposed_links.jsonl")
    assert not any({"reg::r2", "lic::l1"} == {l["source_a_record"], l["source_b_record"]} for l in links)
    queue = {q["source_record"]: q for q in _jsonl(out / "unlinked_queue.jsonl")}
    assert queue["reg::r2"]["reason"] == "CONFLICTING_VALID_IDENTIFIER"
    rel = _jsonl(out / "relationships.jsonl")
    assert any(r["type"] == "SAME_NAME_DIFFERENT_IDENTIFIER" for r in rel)


def test_every_decision_is_kept_for_replay(out):
    dec = _jsonl(out / "link_decisions.jsonl")
    assert {d["decision"] for d in dec} >= {"LINK", "REJECT"}
    assert all(d["policy_version"] == R.POLICY_VERSION for d in dec)
