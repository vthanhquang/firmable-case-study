"""Part 4 profile assembly: winners, losers, variants, absence and per-field confidence parts."""
from firmable.profiles.build import build_profile


def _obs(src, rec, field, value, fc=0.9, rel=0.9, at="2026-01-01T00:00:00+00:00"):
    return {"observation_id": f"{src}-{rec}-{field}-{value}", "source_id": src, "source_record_id": rec, "field": field,
            "value": value, "confidence": {"field_confidence": fc, "source_reliability": rel}, "observed_at": at,
            "source_fields": ["x"], "derivation_level": "L0", "extractor_version": "t"}


def _profile(obs, link=0.97):
    idx = {}
    for o in obs:
        idx.setdefault(f"{o['source_id']}::{o['source_record_id']}", []).append(o)
    return build_profile("fe_x", list(idx), idx, {k: link for k in idx})


def test_cross_source_disagreement_is_a_visible_conflict():
    p = _profile([_obs("asic", "1", "entity.legal_name", "NEW NAME PTY LTD", rel=0.97),
                  _obs("ato", "a", "entity.legal_name", "OLD NAME PTY LTD", rel=0.9)])
    f = p["fields"]["entity.legal_name"]
    assert f["value"] == "NEW NAME PTY LTD"
    assert f["resolution"]["losing_values"][0]["value"] == "OLD NAME PTY LTD"
    assert p["conflicts"] and p["conflicts"][0]["field"] == "entity.legal_name"


def test_same_source_premises_are_variants_not_conflicts():
    p = _profile([_obs("ato", "a", "entity.abn", "51824753556"),
                  _obs("vic", "l1", "address.full", "1 MAIN ST"), _obs("vic", "l2", "address.full", "9 HIGH ST")])
    f = p["fields"]["address.full"]
    assert "resolution" not in f and len(f["same_source_variants"]) == 1
    assert p["conflicts"] == []


def test_agreement_raises_confidence_and_parts_are_kept_apart():
    one = _profile([_obs("asic", "1", "entity.abn", "51824753556")])["fields"]["entity.abn"]
    two = _profile([_obs("asic", "1", "entity.abn", "51824753556"), _obs("ato", "a", "entity.abn", "51824753556")])["fields"]["entity.abn"]
    assert two["value_confidence"] > one["value_confidence"]
    assert set(two["confidence_parts"]) >= {"field_confidence", "source_reliability", "link_confidence", "agreeing_sources"}


def test_missing_fields_are_absent_not_blank():
    p = _profile([_obs("asic", "1", "entity.abn", "51824753556")])
    assert set(p["fields"]) == {"entity.abn"}
