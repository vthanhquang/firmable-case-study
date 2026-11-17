import pytest

from firmable.discovery.quality import RANKING_MAX_POINTS, _catalogue_signals, _rank_score
from firmable.discovery.rerank import column_score
from firmable.discovery.triage import score_package


def test_licence_boilerplate_cannot_supply_identifier_evidence():
    package = {
        "title": "Public Toilet Map",
        "notes": "Locations and opening hours for toilet facilities.\r\n\r\n**Licence**\r\nPublisher ABN 61 970 632 495.",
        "resources": [{"format": "CSV"}],
    }

    assert score_package(package) == (2, ["machine_readable(+2)"])
    package["notes"] = "Each row has a permit holder's ABN.\n\n## Terms of use\nStandard terms apply."
    assert "identifier_terms(+3)" in score_package(package)[1]


@pytest.mark.parametrize("fields", [
    ["FacilityID", "Name", "Address1", "Latitude", "Longitude"],
    ["Project Name", "Business Unit", "Business Unit Name"],
    ["Transfer Date", "Licence Type", "Transfer Price"],
    ["Supplier Count", "Number of Supplier ABNs", "ABN status"],
])
def test_non_business_columns_do_not_earn_identity_points(fields):
    assert column_score(fields)[0] < 0


@pytest.mark.parametrize(("fields", "score"), [
    (["TradingName", "Premises Address"], 3),
    (["Name of Supplier", "Supplier Address"], 3),
    (["Company Name", "AFS_LIC_ABN_ACN"], 6),
    (["Customer Name", "Business Number"], 3),
])
def test_business_identifiers_and_explicit_name_columns_earn_points(fields, score):
    assert column_score(fields)[0] == score


@pytest.mark.parametrize(("signals", "category_points"), [
    (["machine_readable(+2)", "entity_name_terms(+2)"], 5),
    (["machine_readable(+2)", "register_title(+2)", "publisher_regulator(+1)"], 5),
    (["machine_readable(+2)", "contract_terms(+2)", "publisher_regulator(+1)"], 3),
    (["machine_readable(+2)", "entity_title(+3)"], 1),
    (["machine_readable(+2)"], 0),
    (["register_title(+2)", "publisher_regulator(+1)", "documents_only(-3)"], 0),
    (["machine_readable(+2)", "identifier_terms(+3)", "aggregate_terms(-3)"], 0),
])
def test_catalogue_category_adds_points_without_rescaling_publisher_evidence(signals, category_points):
    evidence = {"sampled_rows": 50, "business_rows": 50, "row_signal_counts": {
        "valid_identifier": 50, "corporate_name": 50, "business_name": 50, "identifier_and_name": 50,
    }}
    final, components = _rank_score(evidence, signals)
    assert RANKING_MAX_POINTS == 100
    assert components["publisher_points"] == 95
    assert components["catalogue_category"]["points"] == category_points
    assert components["ranking_points"] == 95 + category_points
    assert final == (95 + category_points) / 100


def test_round_publisher_points_replay_an_archived_multi_column_preview():
    evidence = {
        "sampled_rows": 50, "business_rows": 50, "row_score": 0.993,
        "fields": [
            {"signal": "corporate_name_suffix", "count": 33},
            {"signal": "corporate_name_suffix", "count": 49},
            {"signal": "named_business_role", "count": 50},
            {"signal": "checksum_valid_identifier", "count": 50},
        ],
    }
    _, components = _rank_score(evidence, ["machine_readable(+2)", "entity_name_terms(+2)"])
    breakdown = components["publisher_breakdown"]
    assert [row["max_points"] for row in breakdown] == [45, 20, 10, 10, 10]
    assert [row["points"] for row in breakdown] == [45, 20, 9.8, 10, 10]
    assert components["ranking_points"] == 99.8


def test_catalogue_category_recognizes_publisher_excel_format():
    _, reasons = _catalogue_signals({
        "title": "Register of operators",
        "resources": [{"format": "EXCEL (.XLSX)", "url": "https://example.org/operators"}],
    })
    assert "machine_readable(+2)" in reasons
    assert "documents_only(-3)" not in reasons
