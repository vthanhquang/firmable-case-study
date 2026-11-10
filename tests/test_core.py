"""Deterministic tests: identifiers, transforms, readers, config contract, engine, validator, resolver.
No network and no model calls; runs in seconds from a clean checkout."""
import json
import zipfile

import pytest

from firmable import ids, ontology
from firmable.identity import resolve as R
from firmable.mapping import transforms as T
from firmable.mapping.engine import Engine
from firmable.mapping.schema import MappingConfig, ReaderSpec
from firmable.mapping.validate import holdout_issues, static_issues
from firmable.sources.readers import iter_records

# Public, well-known identifiers (ATO's own ABN; an example ACN from ASIC guidance).
GOOD_ABN = "51824753556"
GOOD_ACN = "000000019"


def test_abn_acn_checksums():
    assert ids.is_valid_abn(GOOD_ABN)
    assert ids.is_valid_abn("51 824 753 556")
    assert not ids.is_valid_abn("51824753557")
    assert not ids.is_valid_abn("1234")
    assert ids.is_valid_acn(GOOD_ACN)
    assert ids.is_valid_acn("004085616")
    assert not ids.is_valid_acn("004085617")


def test_identifier_transforms_fail_loudly():
    assert T.op_abn("51 824 753 556") == GOOD_ABN
    with pytest.raises(T.TransformError) as e:
        T.op_abn("51824753557")
    assert e.value.code == "ABN_CHECKSUM"
    assert T.op_acn("4085616") == "004085616"  # leading zeros restored


def test_dates_enums_states_split():
    assert T.op_parse_date("03/04/2020", formats=["%d/%m/%Y"]) == "2020-04-03"
    with pytest.raises(T.TransformError):
        T.op_parse_date("2020/31/31", formats=["%d/%m/%Y"])
    assert T.op_map_enum("REGD", mapping={"regd": "active"}) == "active"
    assert T.op_map_enum("XYZ", mapping={"regd": "active"}, default="unknown") == "unknown"
    assert T.op_state("New South Wales") == "NSW" and T.op_state("Bavaria") == "OTHER"
    assert T.op_postcode("800") == "0800"
    steps = [type("S", (), {"op": "split", "args": {"sep": ";"}})(), type("S", (), {"op": "trim", "args": {}})()]
    assert T.apply(steps, "A ; B;") == ["A", "B"]


def test_ontology_contract():
    o = ontology.load()
    assert o.has("entity.legal_name") and o.has("address.state") and o.has("observation.licence")
    assert o.check_value("entity.abn", GOOD_ABN) is None
    assert o.check_value("entity.abn", "51824753557") == "CHECKSUM_INVALID"
    assert o.check_value("entity.entity_type", "llc") == "ENUM_VALUE_INVALID"
    assert "observation.source_id" not in o.mappable()


def test_reader_detects_tab_delimited_csv_in_zip(tmp_path):
    p = tmp_path / "x.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("data.csv", "Name\tABN\nACME PTY LTD\t51824753556\n")
    recs = list(iter_records(p, ReaderSpec(format="delimited", delimiter="\t", archive_member="data.csv")))
    assert recs == [{"Name": "ACME PTY LTD", "ABN": "51824753556"}]


def test_reader_xlsx_with_title_rows_and_no_extension(tmp_path):
    # Like the VIC liquor and ATO spreadsheets: title rows above the header, and snapshots saved without '.xlsx'.
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Current licences as of 31/08/2026"])
    ws.append([])
    ws.append(["Licensee", "Postcode"])
    ws.append(["ACME PTY LTD", 3000])
    ws.append([None, None])                     # blank rows are skipped
    p = tmp_path / "snapshot_without_extension"
    wb.save(p)
    recs = list(iter_records(p, ReaderSpec(format="xlsx", sheet="Data", skip_rows=2)))
    assert recs == [{"Licensee": "ACME PTY LTD", "Postcode": "3000"}]
    from firmable.sources.readers import ReaderError
    with pytest.raises(ReaderError):
        list(iter_records(p, ReaderSpec(format="xlsx", sheet="Nope")))


def test_inspection_reports_delimiter_evidence(tmp_path):
    from firmable.sources.inspect import inspect_file
    p = tmp_path / "x.csv"
    p.write_text("a\tb\tc\n1\t2\t3\n4\t5\t6\n")
    info = inspect_file(p)
    assert info["delimiter_counts_per_line"]["tab"] == {"min": 2, "max": 2}
    assert "comma" not in info["delimiter_counts_per_line"] or info["delimiter_counts_per_line"]["comma"]["max"] == 0


def test_reader_json_and_xml(tmp_path):
    j = tmp_path / "a.json"
    j.write_text(json.dumps({"result": {"records": [{"n": "A", "addr": {"pc": "2000"}}]}}))
    assert list(iter_records(j, ReaderSpec(format="json", record_path="result.records"))) == [{"n": "A", "addr.pc": "2000"}]
    x = tmp_path / "a.xml"
    x.write_text("<r><row id='1'><name>A</name></row><row id='2'><name>B</name></row></r>")
    out = list(iter_records(x, ReaderSpec(format="xml", record_path="row")))
    assert out == [{"@id": "1", "name": "A"}, {"@id": "2", "name": "B"}]


def _cfg(**over):
    base = {"source_id": "t", "record_grain": "legal_entity", "grain_rationale": "test",
            "reader": {"format": "delimited", "delimiter": ","},
            "record_id": {"strategy": "columns", "source_paths": ["ABN"]},
            "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "steps": [{"op": "trim"}],
                        "confidence": 0.9, "rationale": "registered name column"},
                       {"source_paths": ["ABN"], "target": "entity.abn", "steps": [{"op": "abn"}],
                        "confidence": 0.95, "rationale": "abn column"}]}
    base.update(over)
    return MappingConfig.model_validate(base)


def test_config_rejects_unknown_op_and_extra_keys():
    with pytest.raises(Exception):
        _cfg(fields=[{"source_paths": ["Name"], "target": "entity.legal_name", "steps": [{"op": "eval"}],
                      "confidence": 0.9, "rationale": "nope nope"}])
    with pytest.raises(Exception):
        MappingConfig.model_validate({**_cfg().model_dump(), "python": "print(1)"})


def test_invented_transform_args_fail_closed():
    # Regression: the agent once invented default='__PASSTHROUGH__'; real semantics must be explicit.
    from firmable.mapping.schema import Step
    with pytest.raises(Exception):
        Step(op="map_enum", args={"mapping": {}, "fallthrough": True})
    s = Step(op="map_enum", args={"mapping": {"australia": "AU"}, "passthrough": True})
    assert T.apply([s], "Singapore") == "Singapore" and T.apply([s], "AUSTRALIA") == "AU"


def test_static_validation_catches_bad_targets_and_unchecked_ids():
    cfg = _cfg(fields=[{"source_paths": ["Name"], "target": "entity.ceo_name", "confidence": 0.5, "rationale": "invented"},
                       {"source_paths": ["ABN"], "target": "entity.abn", "confidence": 0.9, "rationale": "no checksum"}])
    codes = {i["code"] for i in static_issues(cfg, {"Name", "ABN"})}
    assert {"ONTOLOGY_PATH_INVALID", "IDENTIFIER_NOT_VALIDATED"} <= codes


def test_enum_default_guess_is_rejected():
    # Regression from a measured re-run: entity_type inferred from a name suffix with default 'sole_trader'.
    bad = _cfg(fields=[{"source_paths": ["Name"], "target": "entity.entity_type", "confidence": 0.6, "rationale": "suffix",
                        "steps": [{"op": "map_enum", "args": {"mapping": {"pty ltd": "company"}, "default": "sole_trader"}}]}])
    ok = _cfg(fields=[{"source_paths": ["Name"], "target": "entity.entity_type", "confidence": 0.6, "rationale": "type col",
                       "steps": [{"op": "map_enum", "args": {"mapping": {"apty": "company"}, "default": "unknown"}}]}])
    assert any(i["code"] == "ENUM_DEFAULT_GUESS" for i in static_issues(bad, {"Name", "ABN"}))
    assert not any(i["code"] == "ENUM_DEFAULT_GUESS" for i in static_issues(ok, {"Name", "ABN"}))


def test_engine_emits_one_observation_per_claim_with_envelope():
    eng = Engine(_cfg(), {"licence": "cc-by", "resource_last_modified": "2026-01-01T00:00:00+00:00"})
    obs = eng.process({"Name": " ACME PTY LTD ", "ABN": GOOD_ABN})
    assert {o["field"] for o in obs} == {"entity.legal_name", "entity.abn"}
    for o in obs:
        for k in ("source_id", "source_record_id", "observed_at", "ingested_at", "licence", "extractor_version"):
            assert o[k]
    bad = eng.process({"Name": "X", "ABN": "51824753557"})
    assert [o["field"] for o in bad] == ["entity.legal_name"]  # invalid ABN rejected, counted
    assert eng.report()["fields"][1]["errors"] == {"ABN_CHECKSUM": 1}


def test_same_claim_from_two_rules_is_one_observation():
    cfg = _cfg(fields=[{"source_paths": ["Name"], "target": "entity.trading_name", "confidence": 0.9, "rationale": "name a"},
                       {"source_paths": ["Alias"], "target": "entity.trading_name", "confidence": 0.8, "rationale": "name b",
                        "steps": [{"op": "split", "args": {"sep": ";"}}]}])
    obs = Engine(cfg, {}).process({"Name": "ACME", "Alias": "ACME;ACME;Other", "ABN": "1"})
    ids = [o["observation_id"] for o in obs]
    assert len(ids) == len(set(ids)) == 2
    assert sorted(next(o for o in obs if o["value"] == "ACME")["source_fields"]) == ["Alias", "Name"]


def test_when_condition_routes_rows():
    cfg = _cfg(fields=[{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "current",
                        "when": {"source_path": "Cur", "op": "equals", "values": ["Y"]}}])
    eng = Engine(cfg, {})
    assert eng.process({"Name": "A", "ABN": "1", "Cur": "Y"})
    assert not eng.process({"Name": "B", "ABN": "2", "Cur": "N"})


def test_rule_level_validity_dates_a_historical_claim():
    cfg = _cfg(fields=[{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "current name",
                        "when": {"source_path": "Cur", "op": "equals", "values": ["Y"]}},
                       {"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.8, "rationale": "former name",
                        "when": {"source_path": "Cur", "op": "not_equals", "values": ["Y"]},
                        "valid_to_path": "Ended", "validity_date_formats": ["%d/%m/%Y"]}])
    eng = Engine(cfg, {})
    old = eng.process({"Name": "OLD PTY LTD", "ABN": "1", "Cur": "", "Ended": "28/01/2016"})
    new = eng.process({"Name": "NEW PTY LTD", "ABN": "2", "Cur": "Y", "Ended": ""})
    assert old[0]["valid_to"] == "2016-01-28" and new[0]["valid_to"] is None


def test_approved_config_digests_survive_dsl_growth():
    import glob
    from firmable.agent.review import current_approval
    for p in glob.glob("outputs/mappings/*.json"):
        sid = p.replace("\\", "/").rsplit("/", 1)[1][:-5]
        assert current_approval(sid), f"{sid}: approval no longer matches its config digest"


def test_holdout_flags_placeholder_values():
    cfg = _cfg(fields=[{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "name col"},
                       {"source_paths": ["C"], "target": "address.country", "confidence": 0.8, "rationale": "country",
                        "steps": [{"op": "map_enum", "args": {"mapping": {"australia": "AU"}, "default": "__PASSTHROUGH__"}}]}])
    rows = [{"Name": f"N{i}", "ABN": str(i), "C": "Australia" if i else "Singapore"} for i in range(10)]
    issues, _ = holdout_issues(cfg, rows[:3], rows, {})
    assert any(i["code"] == "PLACEHOLDER_VALUE_EMITTED" and i["target"] == "address.country" for i in issues)


def test_placeholder_pattern():
    from firmable.mapping.validate import PLACEHOLDER
    for v in ["TBA", ".", "__PASSTHROUGH__", "[NOT APPLICABLE] -", "[Not applicable] -", "(n/a)", "N/A"]:
        assert PLACEHOLDER.match(v), v
    for v in ["ACME PTY LTD", "Melbourne", "N.A. Smith Pty Ltd", "0800"]:
        assert not PLACEHOLDER.match(v), v


def test_holdout_flags_high_error_rate():
    cfg = _cfg()
    good = [{"Name": f"N{i}", "ABN": GOOD_ABN if i == 0 else f"{i:011d}"} for i in range(20)]
    issues, _ = holdout_issues(cfg, good[:2], good, {})
    assert any(i["code"] == "HIGH_ERROR_RATE" and i["target"] == "entity.abn" for i in issues)


def _rec(src, abn=(), acn=(), names=(), pc=()):
    nn = {R.norm_name(n) for n in names}
    return {"source_id": src, "abn": set(abn), "acn": set(acn), "names": nn, "legal": nn,
            "postcode": set(pc), "locality": set(), "is_business": True, "grain": "legal_entity", "stratum": "random",
            "record_id": "x", "f": {}}


def test_cohort_keys_use_identifiers_and_registered_names_only():
    # The disclosed sampling bias: cohort records are chosen ONLY by ABN, ACN or a registered-company-style name.
    from firmable.extract import _keys
    obs = [{"field": "entity.abn", "value": GOOD_ABN}, {"field": "entity.acn", "value": GOOD_ACN},
           {"field": "entity.legal_name", "value": "Acme Pty Ltd"}, {"field": "entity.legal_name", "value": "John Citizen"},
           {"field": "entity.trading_name", "value": "ACME"}, {"field": "address.postcode", "value": "3000"}]
    keys = _keys(obs)
    assert ("entity.abn", GOOD_ABN) in keys and ("entity.acn", GOOD_ACN) in keys
    assert ("name", "ACME PTY LTD") in keys
    assert len(keys) == 3   # person names, trading names and addresses never select cohort records


def test_extract_refuses_missing_or_changed_snapshot(tmp_path, monkeypatch):
    import hashlib
    import firmable.extract as E
    monkeypatch.setattr(E, "ROOT", tmp_path)
    f = tmp_path / "snap.csv"
    f.write_text("Name\nACME\n")
    src = {"source_id": "s", "snapshot": {"path": "snap.csv", "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}}
    E.verify_snapshot(src)                                  # intact: passes
    f.write_text("")                                        # e.g. a failed download left an empty file
    with pytest.raises(SystemExit):
        E.verify_snapshot(src)
    f.unlink()
    with pytest.raises(SystemExit):
        E.verify_snapshot(src)


def test_triage_column_score():
    from firmable.discovery.rerank import column_score
    assert column_score(["Licensee Name", "ABN", "Postcode"])[0] == 6
    assert column_score(["Month", "Number of permits", "Total value"])[0] < 0   # aggregate table
    assert column_score([])[0] == 0                                             # unknown is not evidence


def test_cluster_never_holds_two_abns():
    # A<->B by name, B<->C by name, but A and C carry different ABNs: the second merge must be refused.
    recs = {"a": {"abn": {GOOD_ABN}, "acn": set()}, "b": {"abn": set(), "acn": set()},
            "c": {"abn": {"53004085616"}, "acn": set()}}
    cl = R.Clusters(recs)
    assert cl.try_union("a", "b") is None
    assert cl.try_union("b", "c") == "CLUSTER_WOULD_HOLD_TWO_ABNS"


def test_unlinked_records_sharing_an_anchor_get_distinct_keys(monkeypatch):
    recs = {"s1::a": {**_rec("s1", abn=[GOOD_ABN], names=["Acme Pty Ltd"]), "legal": {"ACME PTY LTD"}},
            "s2::b": {**_rec("s2", abn=[GOOD_ABN], names=["Acme Pty Ltd"]), "legal": {"ACME PTY LTD"}},
            "s3::c": {**_rec("s3", abn=[GOOD_ABN], names=["John Citizen"]), "legal": {"JOHN CITIZEN"}}}
    monkeypatch.setattr(R, "load_records", lambda exclude=frozenset(): recs)
    res = R.resolve(policy="strict-v2")
    k = res["key_of"]
    assert k["s1::a"] == k["s2::b"] != k["s3::c"]  # person with the company's ABN: not merged, own key


def test_resolver_policy():
    a = _rec("s1", abn=[GOOD_ABN], names=["Acme Pty Ltd"])
    assert R.evidence(a, _rec("s2", abn=[GOOD_ABN], names=["Totally Different"]))[1] == "abn_equal"
    s, rule, _, contra = R.evidence(a, _rec("s2", abn=["53004085616"], names=["ACME PTY. LIMITED"]))
    assert s == 0.0 and contra  # same name, different valid ABN -> veto
    assert R.evidence(_rec("s1", names=["Acme Proprietary Limited"]), _rec("s2", names=["ACME PTY LTD"]))[1] == "registered_name_exact"
    assert R.evidence(_rec("s1", names=["John Smith"]), _rec("s2", names=["JOHN SMITH"]))[1] == "ambiguous_name_exact"
    assert not R.is_registered_company_name(R.norm_name("The Trustee for Smith Family Trust Pty Ltd"))
