"""End to end on synthetic extension observations: challenger matching, relationships and profile-v3."""
import json

import pytest

from firmable.rawdata import match as M
from firmable.rawdata import profiles as P

LIC = {"id": "cc-by", "title": "Creative Commons Attribution 3.0 Australia", "url": None, "attribution": "x", "known": True}


def obs(source, rid, field, value, role="subject", ref=None, grain="legal_entity", **extra):
    return {"observation_id": f"{source}|{rid}|{field}|{value}|{role}", "source_id": source, "source_record_id": rid,
            "record_grain": grain, "field": field, "value": value, "raw_value": value, "source_fields": ["c"],
            "transform": [], "derivation_level": "L0", "observed_at": "2026-11-01T00:00:00+00:00",
            "ingested_at": "2026-11-12T00:00:00+00:00", "valid_from": None, "valid_to": None, "licence": "cc-by",
            "licence_detail": LIC, "extractor_version": "engine-0.3.0+map:test",
            "confidence": {"source_reliability": 0.9, "field_confidence": 0.9}, "entity_role": role,
            "entity_ref": ref or rid, "sample_stratum": "random", "approval_state": "pending_human_review", **extra}


@pytest.fixture
def world(tmp_path, monkeypatch):
    out = tmp_path / "raw-data"
    obs_dir = out / "observations"
    obs_dir.mkdir(parents=True)
    rows = {
        "charities": [obs("charities", "r1", "entity.legal_name", "Brotherhood of St Laurence"),
                      obs("charities", "r1", "entity.abn", "53004085616"),
                      obs("charities", "r1", "entity.website", "https://www.bsl.org.au"),
                      obs("charities", "r1", "address.postcode", "3065"),
                      obs("charities", "r1", "ext.financial.total_income", 1000,
                          qualifiers={"period": "2023-24", "currency": "AUD"}),
                      obs("charities", "r1", "ext.financial.total_income", 1500,
                          qualifiers={"period": "2024-25", "currency": "AUD"}),
                      obs("charities", "r2", "entity.legal_name", "ACME PTY LTD")],
        "sites": [obs("sites", "s1", "entity.trading_name", "Brotherhood of St Laurence Frankston", grain="establishment"),
                  obs("sites", "s1", "ext.contact.email_domain", "bsl.org.au", role="site", ref="establishment:sites:A1",
                      grain="establishment"),
                  obs("sites", "s1", "address.postcode", "3199", role="site", ref="establishment:sites:A1",
                      grain="establishment"),
                  obs("sites", "s1", "ext.establishment.program", "DESB", role="site", ref="establishment:sites:A1",
                      grain="establishment"),
                  obs("sites", "s1", "ext.contact.phone", "+61412345678", role="site", ref="establishment:sites:A1",
                      grain="establishment", privacy="personal")],
        "register": [obs("register", "c1", "entity.legal_name", "ACME PTY LTD"),
                     obs("register", "c1", "entity.acn", "004085616"),
                     obs("register", "c1", "ext.entity.status_detail", "EXAD: External administration")],
    }
    for source, items in rows.items():
        (obs_dir / f"{source}.jsonl").write_text("\n".join(json.dumps(o) for o in items) + "\n", encoding="utf-8")
    (obs_dir / "edges").mkdir()
    (obs_dir / "edges" / "sites.jsonl").write_text(json.dumps(
        {"type": "OPERATES_ESTABLISHMENT", "source_id": "sites", "source_record_id": "s1",
         "from_ref": "s1", "to_ref": "establishment:sites:A1", "approval_state": "pending_human_review"}) + "\n",
        encoding="utf-8")
    ident = out / "identity"
    ident.mkdir()
    (ident / "former_name_reuse.json").write_text(json.dumps({"names": []}), encoding="utf-8")
    for mod in (M, P):
        monkeypatch.setattr(mod, "OUT_RD_OBS", obs_dir, raising=False)
    monkeypatch.setattr(M, "OUT_RD_IDENTITY", ident)
    monkeypatch.setattr(M, "NAME_REUSE_PATH", ident / "former_name_reuse.json")
    monkeypatch.setattr(M, "OUT_RD_EVAL", out / "evaluation")
    monkeypatch.setattr(P, "OUT_RD_PROFILES", out / "profiles")
    monkeypatch.setattr(P, "OUT_RD_EVAL", out / "evaluation")
    monkeypatch.setattr(M, "load", lambda observations=obs_dir, _f=M.load: _f(observations))
    return out


def test_domain_links_site_and_name_only_waits_for_review(world):
    summary = M.run()
    rules = summary["challenger"]["links_by_rule"]
    assert rules == {"domain_equal_and_name": 1}
    assert summary["comparison"]["links_added"] == 1
    decisions = [json.loads(l) for l in open(world / "identity" / "link_decisions.jsonl", encoding="utf-8")]
    acme = next(d for d in decisions if {d["a"], d["b"]} == {"charities::r2", "register::c1"})
    assert acme["decision"] == "REVIEW" and acme["rule"] == "registered_name_exact_uncorroborated"
    rel = {json.loads(l)["type"] for l in open(world / "identity" / "relationships.jsonl", encoding="utf-8")}
    assert {"OPERATES_ESTABLISHMENT", "DELIVERS_PROGRAM_FOR"} <= rel


def test_profile_v3_separates_site_from_business_and_withholds_personal(world, monkeypatch):
    monkeypatch.setattr(P, "_rule_tables", lambda: {})
    profiles, _ = P.materialise()
    (p,) = profiles.values()
    assert p["sources"] == ["charities", "sites"]
    assert p["fields"]["address.postcode"]["value"] == "3065"          # the site's 3199 is not the charity's address
    assert p["locations"][0]["fields"]["address.postcode"]["value"] == "3065"
    assert all(location["fields"]["address.postcode"]["value"] != "3199" for location in p["locations"])
    assert p["establishments"][0]["fields"]["address.postcode"] == "3199"
    assert p["contact_points_withheld_personal"] == 1
    facts = p["firmographics"]["financial_facts"]
    assert [f["period"] for f in facts] == ["2023-24", "2024-25"]
    assert p["firmographics"]["derived"][0]["value"] == 0.5 and p["firmographics"]["derived"][0]["derivation_level"] == "L2"
