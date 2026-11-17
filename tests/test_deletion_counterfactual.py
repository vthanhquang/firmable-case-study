"""Part 4 'what if a source is deleted': re-resolve without it and diff each profile against its survivors."""
import json

import pytest

ABN = "51824753556"


def _obs(src, rec, field, value):
    return {"observation_id": f"{src}{rec}{field}", "source_id": src, "source_record_id": rec, "record_grain": "legal_entity",
            "field": field, "value": value, "confidence": {"field_confidence": 0.9, "source_reliability": 0.9},
            "observed_at": "2026-01-01T00:00:00+00:00", "source_fields": ["x"], "derivation_level": "L0",
            "extractor_version": "t", "sample_stratum": "random"}


@pytest.fixture
def impact(tmp_path, monkeypatch):
    import firmable.identity.resolve as R
    import firmable.profiles.build as B
    obs = tmp_path / "obs"
    obs.mkdir()
    monkeypatch.setattr(R, "OUT_OBS", obs)
    monkeypatch.setattr(B, "OUT_OBS", obs)
    monkeypatch.setattr(R, "OUT_IDENTITY", tmp_path / "identity")
    monkeypatch.setattr(B, "OUT_PROFILES", tmp_path / "profiles")
    monkeypatch.setattr(B, "OUT_EVAL", tmp_path / "eval")
    rows = {"reg": [("r1", "entity.legal_name", "ACME PTY LTD"), ("r1", "entity.abn", ABN), ("r1", "entity.date_registered", "2001-01-01")],
            "tax": [("t1", "entity.legal_name", "ACME PTY LTD"), ("t1", "entity.abn", ABN)],
            "lic": [("l1", "entity.legal_name", "ACME PTY LTD"), ("l1", "address.postcode", "3000")]}
    for src, rs in rows.items():
        with open(obs / f"{src}.jsonl", "w", encoding="utf-8") as fh:
            for rec, field, value in rs:
                fh.write(json.dumps(_obs(src, rec, field, value)) + "\n")
    summary = B.run(count=50)
    assert summary["profiles_written"] == 1
    return json.loads((tmp_path / "eval" / "source_deletion_impact.json").read_text())


def test_deleting_the_only_source_of_a_field_removes_it(impact):
    assert impact["reg"]["fields_removed"] == 1          # date_registered came only from 'reg'
    assert impact["lic"]["fields_removed"] == 1          # postcode came only from 'lic'


def test_deleting_a_corroborating_source_changes_no_values(impact):
    t = impact["tax"]
    assert t["fields_removed"] == 0 and t["fields_value_changed"] == 0 and t["no_longer_multi_source"] == 0
    assert t["fields_confidence_changed"] > 0 and t["fields_provenance_changed"] > 0


def test_corruption_can_change_value_even_with_a_visible_conflict():
    from firmable.profiles.build import build_profile, corruption_check

    a = _obs("asic", "r", "entity.date_registered", "2020-01-01")
    b = _obs("other", "s", "entity.date_registered", "2020-01-01")
    idx = {"asic::r": [a], "other::s": [b]}
    links = {"asic::r": 0.97, "other::s": 0.9}
    profiles = {"e": build_profile("e", list(idx), idx, links)}
    impact = corruption_check(profiles, idx, links, "asic")
    assert impact["profiles_value_changed"] == impact["profiles_confidence_changed"] == 1
    assert impact["profiles_provenance_changed"] == impact["profiles_showing_date_conflict"] == 1
    assert a["value"] == "2020-01-01"
