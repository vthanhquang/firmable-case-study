"""Part 4 profile assembly: winners, losers, variants, absence and per-field confidence parts."""
from firmable.profiles.build import EVIDENCE_PROFILE, _membership_conf, build_profile


def _obs(src, rec, field, value, fc=0.9, rel=0.9, at="2026-01-01T00:00:00+00:00"):
    return {"observation_id": f"{src}-{rec}-{field}-{value}", "source_id": src, "source_record_id": rec, "field": field,
            "value": value, "confidence": {"field_confidence": fc, "source_reliability": rel}, "observed_at": at,
            "source_fields": ["x"], "derivation_level": "L0", "extractor_version": "t"}


def _profile(obs, link=0.97, **kwargs):
    idx = {}
    for o in obs:
        idx.setdefault(f"{o['source_id']}::{o['source_record_id']}", []).append(o)
    return build_profile("fe_x", list(idx), idx, {k: link for k in idx}, **kwargs)


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


def test_scoped_profiles_preserve_premises_charity_registration_and_former_names():
    p = _profile([
        _obs("asic_companies", "a", "entity.legal_name", "CURRENT PTY LTD") | {"claim_scope": "current_legal_name"},
        _obs("asic_companies", "a", "entity.legal_name", "FORMER PTY LTD", fc=1) | {"claim_scope": "former_legal_name"},
        _obs("asic_companies", "a", "entity.date_registered", "2000-01-01"),
        _obs("acnc_charities", "b", "entity.date_registered", "2014-02-01"),
        _obs("acnc_charities", "b", "address.locality", "Sydney"),
        _obs("vic_liquor", "c", "address.full", "1 HIGH ST"),
        _obs("vic_liquor", "c", "address.country", "AU") | {"derivation_level": "L3"},
    ], version=EVIDENCE_PROFILE)
    assert p["fields"]["entity.legal_name"]["value"] == "CURRENT PTY LTD"
    assert p["historical_names"][0]["value"] == "FORMER PTY LTD"
    assert p["fields"]["entity.date_registered"]["value"] == "2000-01-01"
    assert {r["scope"] for r in p["registration_events"]} == {"company_registration", "charity_registration"}
    assert p["primary_address_record"] == "acnc_charities::b"
    assert "address.full" not in p["fields"] and "address.country" not in p["fields"]
    assert p["locations"][1]["fields"]["address.full"]["value"] == "1 HIGH ST"
    assert p["mapping_defaults"]["address.country"][0]["value"] == "AU"
    assert p["conflicts"] == []


def test_transitive_membership_cannot_outrank_the_bridge_to_its_anchor():
    recs = {key: {"abn": {"abn"} if key == "anchor" else set(), "acn": set()} for key in ("anchor", "b", "c", "d")}
    result = {"recs": recs, "clusters": {"anchor": list(recs)}, "decisions": [
        {"a": a, "b": b, "score": score, "decision": "LINK"}
        for a, b, score in [("anchor", "b", 0.97), ("b", "c", 0.86), ("c", "d", 0.97)]
    ]}
    assert _membership_conf(result, path_aware=True) == {"anchor": 0.97, "b": 0.97, "c": 0.86, "d": 0.86}


def test_unrelated_corroborated_legal_names_require_review():
    p = _profile([_obs("asic_companies", "a", "entity.legal_name", "DOVER PTY LTD", rel=0.97),
                  _obs("ato_tax_transparency", "b", "entity.legal_name", "BALM PTY LTD", rel=0.9)],
                 version=EVIDENCE_PROFILE)
    winner = p["fields"]["entity.legal_name"]
    assert winner["resolution"]["decision"] == "review_required"
    assert winner["value_confidence"] <= 0.55
