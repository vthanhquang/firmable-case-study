"""Raw-data extension pipeline: registry, crosswalks, transforms, roles, gates, privacy and matching evidence."""
import pytest

from firmable import crosswalk, ontology
from firmable.agent.workspace import mask_personal
from firmable.mapping import transforms as T
from firmable.mapping.engine import Engine
from firmable.mapping.schema import ExtensionDraft, MappingConfig
from firmable.mapping.validate import extension_issues, list_issues, static_issues

META = {"source_id": "src", "licence": "cc-by", "publisher": "Pub", "title": "Register",
        "resource_last_modified": "2026-11-01T00:00:00+00:00"}


def base_cfg(**extra):
    doc = {"source_id": "src", "record_grain": "licence_or_permit", "grain_rationale": "one licence per row",
           "reader": {"format": "delimited", "delimiter": ","},
           "record_id": {"strategy": "columns", "source_paths": ["Licence"]},
           "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9,
                       "rationale": "licensee legal name"},
                      {"source_paths": ["Street"], "target": "address.full", "confidence": 0.8,
                       "rationale": "premises street"},
                      {"source_paths": ["From"], "target": "observation.valid_from", "confidence": 0.5,
                       "rationale": "legacy record validity", "steps": [{"op": "parse_date", "args": {"formats": ["%d/%m/%Y"]}}]}],
           "unmapped": [{"source_path": "Phone", "reason": "no target"}, {"source_path": "Lat", "reason": "no target"},
                        {"source_path": "Lon", "reason": "no target"}, {"source_path": "Year", "reason": "no target"}]}
    doc.update(extra)
    return MappingConfig.model_validate(doc)


# ---- transforms -----------------------------------------------------------------------------------------
def test_phone_au_normalises_and_completes_from_state():
    assert T.op_phone_au("02 6258 1234") == "+61262581234"
    assert T.op_phone_au("61325800|ACT", area_from_state=True) == "+61261325800"
    assert T.op_phone_au("1300 967 575") == "+611300967575"
    assert T.op_phone_au("0412 345 678") == "+61412345678"
    with pytest.raises(T.TransformError):
        T.op_phone_au("131559")
    with pytest.raises(T.TransformDrop):
        T.op_phone_au("6132", on_incomplete="drop")


def test_email_transforms_never_keep_personal_local_parts():
    assert T.op_email_domain("Kal.Perera@VisionAustralia.org") == "visionaustralia.org"
    assert T.op_role_email("info@verto.org.au") == "info@verto.org.au"
    with pytest.raises(T.TransformDrop):
        T.op_role_email("kal.perera@visionaustralia.org")
    with pytest.raises(T.TransformError) as e:
        T.op_email_domain("not an email")
    assert "not an email" not in str(e.value)


def test_url_domain_and_geo_point():
    assert T.op_url_domain("http://maxsolutions.com.au/") == "maxsolutions.com.au"
    assert T.op_url_domain("www.apm.net.au") == "apm.net.au"
    assert T.op_geo_point("NULL,NULL") is None
    assert T.op_geo_point("-35.2791945,149.1306937") == "-35.279195,149.130694"
    assert T.op_geo_point("-10.482727,105.62268")          # Christmas Island is Australian
    with pytest.raises(T.TransformError):
        T.op_geo_point("51.5,-0.12")


def test_decimal_and_flag():
    assert T.op_parse_decimal("115,090,768") == 115090768
    assert T.op_parse_decimal("$1,234.50") == 1234.5
    assert T.op_parse_decimal("(1,200)") == -1200
    assert T.op_flag("Y", value="NSW") == "NSW"
    assert T.op_flag("", value="NSW") is None


def test_crosswalk_exact_pattern_null_and_unlisted():
    assert T.op_crosswalk("EXAD", table="asic_company_status", output="key_label") == "EXAD: External administration"
    assert T.op_crosswalk("APTY", table="asic_company_type") == "proprietary_company"
    assert T.op_crosswalk("Plumbing And Draining Restricted To Plumbing", table="anzsic_qbcc_licence_class") == "3231"
    with pytest.raises(T.TransformDrop):                          # explicit "no inference" entry
        T.op_crosswalk("Limited Licence", table="anzsic_vic_liquor_category")
    with pytest.raises(T.TransformError):
        T.op_crosswalk("ZZZZ", table="asic_company_status")
    both = ("This licence authorises the licensee to:~Engage in credit activities as a credit provider by:~x"
            "~Engage in credit activities other than as a credit provider by:~y")
    assert T.op_crosswalk(both, table="anzsic_credit_authorisation") == ["6230", "6419"]
    assert crosswalk.band_labels("acnc_size_2022") == {"Small", "Medium", "Large"}


def test_mask_personal_keeps_role_mailboxes_and_domains():
    s = mask_personal("kal.perera@visionaustralia.org; info@verto.org.au; call 0412 345 678")
    assert "kal.perera" not in s and "<personal>@visionaustralia.org" in s
    assert "info@verto.org.au" in s and "0412" not in s


# ---- registry and schema --------------------------------------------------------------------------------
def test_registry_loads_beside_core():
    onto = ontology.load(None, "ext-v1")
    assert onto.fields["ext.financial.total_income"].required_qualifiers() == {"period", "currency"}
    assert onto.fields["ext.contact.phone"].personal_data == "mobile_numbers"
    assert onto.check_value("ext.establishment.geo", "-35.1,149.1") is None
    assert onto.check_value("entity.legal_name", "X PTY LTD") is None
    assert "ext.entity.former_name" not in ontology.load().fields


def test_roles_and_relationship_kinds_are_checked():
    with pytest.raises(ValueError):
        base_cfg(extensions="ext-v1", relationships=[{"type": "HOLDS_LICENCE", "from_role": "subject",
                                                      "to_role": "nope", "rationale": "undeclared role"}])
    with pytest.raises(ValueError):   # roles need the extension registry
        base_cfg(entities={"lic": {"kind": "licence", "rationale": "licence role"}})
    with pytest.raises(ValueError):   # wrong kinds for the relationship type
        base_cfg(extensions="ext-v1", entities={"site": {"kind": "establishment", "rationale": "site role"}},
                 relationships=[{"type": "HOLDS_LICENCE", "from_role": "subject", "to_role": "site",
                                 "rationale": "wrong kind"}])


def test_extension_draft_cannot_rewrite_approved_rules():
    base = base_cfg()
    draft = ExtensionDraft.model_validate({
        "entities": {"premises": {"kind": "establishment", "rationale": "the licensed premises"}},
        "base_rule_edits": [
            {"index": 1, "entity": "premises", "reason": "premises address belongs to the site"},
            {"index": 0, "replace_with": {"source_paths": ["Name"], "target": "entity.trading_name",
                                          "confidence": 0.9, "rationale": "sneaky rewrite"}, "reason": "try rewrite"},
            {"index": 2, "remove": True, "reason": "legacy record-level validity"}],
        "new_rules": [{"source_paths": ["Phone"], "target": "ext.contact.phone", "steps": [{"op": "phone_au"}],
                       "confidence": 0.8, "rationale": "published business line"}]})
    cfg, discarded, changes = draft.apply(base, editable=set())
    assert [f.target for f in cfg.fields] == ["entity.legal_name", "address.full", "ext.contact.phone"]
    assert cfg.fields[0].target == "entity.legal_name" and cfg.fields[1].entity == "premises"
    assert any("replace #0" in d for d in discarded)
    assert {u.source_path for u in cfg.unmapped} == {"Lat", "Lon", "Year"}
    assert cfg.extensions == "ext-v1" and cfg.reader == base.reader and cfg.record_id == base.record_id
    cfg2, discarded2, _ = draft.apply(base, editable={0})
    assert cfg2.fields[0].target == "entity.trading_name" and not any("replace" in d for d in discarded2)


# ---- engine ----------------------------------------------------------------------------------------------
def ext_cfg():
    base = base_cfg()
    draft = ExtensionDraft.model_validate({
        "entities": {"lic": {"kind": "licence", "key_paths": ["Licence"], "rationale": "the licence itself"},
                     "premises": {"kind": "establishment", "rationale": "the licensed premises"}},
        "relationships": [{"type": "HOLDS_LICENCE", "from_role": "subject", "to_role": "lic", "rationale": "holder"},
                          {"type": "OPERATES_ESTABLISHMENT", "from_role": "subject", "to_role": "premises",
                           "rationale": "venue"}],
        "base_rule_edits": [{"index": 1, "entity": "premises", "reason": "premises address"}],
        "new_rules": [
            {"source_paths": ["Licence"], "target": "ext.licence.number", "entity": "lic", "confidence": 0.95,
             "rationale": "licence number"},
            {"source_paths": ["Phone"], "target": "ext.contact.phone", "entity": "premises",
             "steps": [{"op": "phone_au"}], "confidence": 0.8, "rationale": "venue phone"},
            {"source_paths": ["Lat", "Lon"], "join_with": ",", "target": "ext.establishment.geo", "entity": "premises",
             "steps": [{"op": "geo_point"}], "confidence": 0.9, "rationale": "venue coordinates"},
            {"source_paths": ["Income"], "target": "ext.financial.total_income", "steps": [{"op": "parse_decimal"}],
             "qualifiers": {"period": {"source_path": "Year"}, "currency": {"value": "AUD"}},
             "confidence": 0.95, "rationale": "published income"},
            {"source_paths": ["Size"], "target": "ext.financial.revenue_band",
             "steps": [{"op": "crosswalk", "args": {"table": "acnc_size_2022", "output": "label"}}],
             "qualifiers": {"scheme": {"value": "acnc_size_2022"}}, "confidence": 0.9, "rationale": "size band"},
            {"source_paths": ["Status"], "target": "ext.entity.status_detail",
             "steps": [{"op": "crosswalk", "args": {"table": "asic_company_status", "output": "key_label"}}],
             "confidence": 0.9, "rationale": "registrar status"}]})
    cfg, _, _ = draft.apply(base, editable=set())
    return cfg


ROW = {"Licence": "L-1", "Name": "ACME PTY LTD", "Street": "1 High St", "From": "01/01/2020", "Phone": "0412 345 678",
       "Lat": "-37.8", "Lon": "144.9", "Income": "1,000", "Year": "2024-25", "Size": "Small", "Status": "SOFF"}


def test_engine_roles_refs_edges_qualifiers_privacy_and_licence():
    eng = Engine(ext_cfg(), META)
    obs = {o["field"]: o for o in eng.process(dict(ROW))}
    assert obs["address.full"]["entity_role"] == "premises" and obs["address.full"]["entity_ref"] == "L-1#premises"
    assert obs["ext.licence.number"]["entity_ref"] == "licence:src:L-1"        # stable across snapshots
    assert obs["ext.financial.total_income"]["qualifiers"] == {"period": "2024-25", "currency": "AUD"}
    assert obs["ext.financial.total_income"]["value"] == 1000
    assert obs["ext.contact.phone"]["privacy"] == "personal"                     # a mobile
    assert obs["ext.financial.revenue_band"]["derivation_level"] == "L1"
    assert obs["ext.entity.status_detail"]["value"] == "SOFF: Strike-off action in progress"
    assert obs["entity.legal_name"]["licence_detail"]["title"] == "Creative Commons Attribution 3.0 Australia"
    assert {e["type"] for e in eng.edges} == {"HOLDS_LICENCE", "OPERATES_ESTABLISHMENT"}


def test_engine_rejects_missing_qualifier_and_foreign_band_label():
    eng = Engine(ext_cfg(), META)
    eng.process(dict(ROW, Year="", Size="Huge"))
    rep = {f["target"]: f for f in eng.report()["fields"]}
    assert rep["ext.financial.total_income"]["errors"] == {"QUALIFIER_MISSING_PERIOD": 1}
    assert rep["ext.financial.revenue_band"]["errors"] == {"CROSSWALK_UNLISTED": 1}


# ---- gates -----------------------------------------------------------------------------------------------
COLS = set(ROW)


def test_extension_gates():
    good = ext_cfg()
    assert [i for i in static_issues(good, COLS | {"Size", "Status", "Income"}) if i["severity"] == "error"] == []
    bad = good.model_copy(deep=True)
    bad.fields[3].entity = None                                     # licence number on the business
    bad.fields[6].qualifiers = {"period": bad.fields[6].qualifiers["period"]}   # no currency
    bad.fields[7].steps = []                                        # band without its crosswalk
    bad.fields[4].steps = []                                        # phone without phone_au
    codes = {i["code"] for i in extension_issues(bad, COLS)}
    assert {"ROLE_TARGET_MISMATCH", "QUALIFIER_REQUIRED", "CROSSWALK_REQUIRED", "TYPE_TRANSFORM_REQUIRED",
            "BAND_SCHEME_MISMATCH"} <= codes


def test_former_name_end_date_gate_covers_extension_concept():
    cfg = base_cfg(extensions="ext-v1", fields=[
        {"source_paths": ["Name"], "target": "ext.entity.former_name", "valid_to_path": "Current Name Start Date",
         "confidence": 0.9, "rationale": "former name rows"}])
    codes = {i["code"] for i in static_issues(cfg, COLS | {"Current Name Start Date"})}
    assert "UNSUPPORTED_FORMER_NAME_END" in codes


def test_list_gates_catch_unsplit_lists_and_former_names():
    onto = ontology.load(None, "ext-v1")
    obs = [{"field": "entity.trading_name", "value": v} for v in
           ["Allergy Life, Allergy Life Australia", "Previously known as NHILL LUTHERAN SCHOOL LTD", "Plain Name"]]
    codes = {i["code"] for i in list_issues(obs, onto)}
    assert codes == {"UNSPLIT_LIST_VALUES", "FORMER_NAME_AS_TRADING_NAME"}
    assert list_issues([{"field": "entity.trading_name", "value": "Smith, Jones & Co"}] +
                       [{"field": "entity.trading_name", "value": f"Name {i}"} for i in range(100)], onto) == []


def test_one_hot_rule_emits_one_claim_per_set_indicator_column():
    cfg = base_cfg(extensions="ext-v1", fields=[
        {"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "legal name"},
        {"source_paths": ["Advancing_Education", "Advancing_Health", "Advancing_Religion"], "one_hot": True,
         "target": "ext.entity.sector_tag", "qualifiers": {"scheme": {"value": "acnc_purpose"}},
         "steps": [{"op": "crosswalk", "args": {"table": "acnc_purpose"}}], "confidence": 0.9,
         "rationale": "purpose flags"},
        {"source_paths": ["Advancing_Education", "Advancing_Health", "Advancing_Religion"], "one_hot": True,
         "target": "ext.entity.industry_code", "qualifiers": {"scheme": {"value": "anzsic2006"}},
         "steps": [{"op": "crosswalk", "args": {"table": "acnc_purpose"}},
                   {"op": "crosswalk", "args": {"table": "anzsic_acnc_purpose"}}], "confidence": 0.6,
         "rationale": "purpose to ANZSIC"}])
    eng = Engine(cfg, META)
    obs = eng.process({"Licence": "1", "Name": "X LTD", "Advancing_Education": "Y", "Advancing_Health": "",
                       "Advancing_Religion": "Y"})
    tags = sorted((o["value"], o["raw_value"]) for o in obs if o["field"] == "ext.entity.sector_tag")
    assert tags == [("Advancing education", "Advancing_Education"), ("Advancing religion", "Advancing_Religion")]
    codes = sorted(o["value"] for o in obs if o["field"] == "ext.entity.industry_code")
    assert codes == ["9540", "P"] and {o["derivation_level"] for o in obs if o["field"] == "ext.entity.industry_code"} == {"L2"}
    with pytest.raises(ValueError):
        base_cfg(extensions="ext-v1", fields=[{"source_paths": ["Name"], "one_hot": True, "target": "ext.entity.sector_tag",
                                               "confidence": 0.5, "rationale": "single column"}])


def test_no_inference_entry_emits_nothing_for_any_output():
    for output in ("code", "label", "key_label"):
        with pytest.raises(T.TransformDrop):
            T.op_crosswalk("N/A", table="qbcc_mfr", output=output)
    assert "No Financials Required" not in crosswalk.band_labels("qbcc_mfr")


# ---- change signals --------------------------------------------------------------------------------------
def test_snapshot_diff_types_events():
    from firmable.rawdata.changes import diff

    def v(**fields):
        return {k.replace("__", "."): {f'"{x}"' if isinstance(x, str) else str(x) for x in vals}
                for k, vals in fields.items()}
    old = {"rec1": v(ext__entity__status_detail=["REGD: Registered"], entity__status=["active"]),
           "licence:q:1": v(ext__licence__grade=["Trade Contractor Licence"]),
           "licence:q:2": v(ext__licence__grade=["Site Supervisor"])}
    new = {"rec1": v(ext__entity__status_detail=["EXAD: External administration"], entity__status=["unknown"]),
           "licence:q:1": v(ext__licence__grade=["Nominee Supervisor"])}
    kinds = sorted(e["event_type"] for e in diff(old, new, "q", "a" * 64, "b" * 64))
    assert kinds == ["ENTERED_DISTRESS", "FIELD_CHANGED", "LICENCE_REMOVED", "STATUS_CHANGED"]


# ---- matcher evidence ------------------------------------------------------------------------------------
def rec(source, names=(), abn=(), postcode=(), domains=(), former=None, holder_kind=None, legal=None):
    return {"key": f"{source}::1", "source_id": source, "record_id": "1", "grain": "legal_entity", "stratum": "random",
            "f": {}, "claim_quality": {}, "abn": set(abn), "acn": set(), "names": set(names),
            "legal": set(legal if legal is not None else names), "postcode": set(postcode), "locality": set(),
            "is_business": True, "domains": set(domains), "phones": set(), "geo": set(), "former": former or {},
            "holder_kind": holder_kind, "grade": None, "corr_address": set(), "programs": set(), "legal_form": None,
            "former_stems": {n.replace(" LTD", ""): n for n in (former or {})}, "stems": {n for n in names}}


def test_challenger_evidence_rules():
    from firmable.rawdata.match import make_evidence
    ev = make_evidence({}, frozenset({"OLD NAME PTY LTD"}))
    s, rule, *_ = ev(rec("a", ["ACME PTY LTD"]), rec("b", ["ACME PTY LTD"]))
    assert rule == "registered_name_exact_uncorroborated" and s < 0.85          # name alone -> review
    s, rule, *_ = ev(rec("a", ["ACME PTY LTD"], postcode=["3000"]), rec("b", ["ACME PTY LTD"], postcode=["3000"]))
    assert rule == "registered_name_exact_corroborated" and s >= 0.85
    s, rule, *_ = ev(rec("a", ["BROTHERHOOD OF ST LAURENCE"], domains=["bsl.org.au"]),
                     rec("b", ["BROTHERHOOD OF ST LAURENCE FRANKSTON"], domains=["bsl.org.au"]))
    assert rule == "domain_equal_and_name" and s >= 0.85
    s, rule, *_ = ev(rec("a", ["NEW NAME PTY LTD"], former={"OLD NAME PTY LTD": (None, None)}),
                     rec("b", ["OLD NAME PTY LTD"]))
    assert rule == "former_name_reused_on_register"
    s, rule, *_ = ev(rec("a", ["OMNIA INCLUSIVE EMPLOYMENT SOLUTIONS LTD"], former={"JOB CENTRE AUSTRALIA LTD": (None, None)}),
                     rec("b", ["JOB CENTRE AUSTRALIA"]))
    assert rule == "former_name_stem_uncorroborated" and 0.75 <= s < 0.85      # review, not a silent miss
    s, rule, *_ = ev(rec("a", ["JOHN SMITH"], abn=["53004085616"], holder_kind="individual"),
                     rec("b", ["SMITH BUILDERS PTY LTD"], abn=["53004085616"]))
    assert rule == "licensed_individual_for_company"
