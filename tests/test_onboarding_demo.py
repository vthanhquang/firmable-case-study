"""Verify that the read-only demo faithfully exports recorded experiment evidence."""
import gzip
import json
import re

import pytest

from scripts.build_onboarding_demo import ROOT, EXP, mapping_diff, safe_row


@pytest.fixture(scope="module")
def replay():
    return json.loads((ROOT / "frontend/data/onboarding.json").read_text(encoding="utf-8"))


def test_all_cases_preserve_saved_samples_measurements_and_review_contracts(replay):
    assert {s["key"] for s in replay["sources"]} == {"ip", "acnc", "wgea"}
    for source in replay["sources"]:
        folder = EXP / source["run"]["latest"] / source["source_id"]
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        with gzip.open(folder / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
            records = [json.loads(line) for line in stream]
        expected = [{"ordinal": r["ordinal"], "partition": r["partition"], "row": safe_row(r["row"])} for r in records[:50]]
        assert source["preview"] == expected
        assert source["test_quality"] == result["test_quality"]
        assert source["test_fields"] == result["test"]["fields"]
        assert source["groups"] == result["groups"]
        assert source["review_queue"] == json.loads((folder / "review-queue.json").read_text(encoding="utf-8"))
        assert source["human_verification"]["production_merged"] == 0
        assert source["human_verification"]["status"] == "Not measured"
        calls = []
        for run in (source["run"]["first"], source["run"]["latest"]):
            calls.extend(json.loads(line) for line in (EXP / run / "usage.jsonl").read_text(encoding="utf-8").splitlines())
        calls = [c for c in calls if c["source_id"] == source["source_id"]]
        assert source["run"]["calls"] == len(calls)
        assert source["run"]["input_tokens"] == sum(c.get("prompt_tokens", 0) for c in calls)
        assert source["run"]["output_tokens"] == sum(c.get("completion_tokens", 0) for c in calls)


def test_profile_examples_keep_observation_provenance_and_real_identifier_overlap(replay):
    profiles = json.loads((ROOT / "frontend/data/raw-profiles.json").read_text(encoding="utf-8"))["profiles"]
    by_id = {p["entity_key"]: p for p in profiles}
    for source in replay["sources"]:
        folder = EXP / source["run"]["latest"] / source["source_id"]
        wanted = {c["observation_id"] for e in source["examples"] for c in e["claims"]}
        by_observation = {}
        with (folder / "observations.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                observation = json.loads(line)
                if observation["observation_id"] in wanted:
                    by_observation[observation["observation_id"]] = observation
        for example in source["examples"]:
            for claim in example["claims"]:
                original = by_observation[claim["observation_id"]]
                assert original.get("privacy") != "personal"
                assert all(v == original.get(k) for k, v in claim.items())
                assert claim["source_record_id"] == example["record_id"]
            if example["existing_profile"]:
                row = example["source_row"]
                abn = str(row.get("abn") or row.get("Employer ABN") or row.get("party_activity.abn") or "").replace(" ", "")
                profile = by_id[example["existing_profile"]["id"]]
                assert abn == str(profile["fields"]["entity.abn"]["value"])


def test_revision_diffs_report_changes_without_inventing_them():
    old = {"fields": [{"source_paths": ["Revenue"], "target": "finance.revenue", "entity": "subject"}]}
    new = {"fields": [{"source_paths": ["Revenue"], "target": "finance.revenue", "entity": "charity", "qualifiers": {"year": 2024}}]}
    assert mapping_diff(old, old) == []
    delta = mapping_diff(old, new)
    assert len(delta) == 1
    assert delta[0]["kind"] == "changed"
    assert delta[0]["changes"]["entity"] == {"before": "subject", "after": "charity"}
    assert delta[0]["changes"]["qualifiers"]["after"] == {"year": 2024}


def test_personal_ip_names_and_direct_contacts_are_withheld():
    row = {"party_activity.party_type": "individual", "party_activity.party_name": "Person", "email": "private@example.test"}
    assert safe_row(row)["party_activity.party_name"] == "[withheld in demo]"
    assert safe_row(row)["email"] == "[withheld in demo]"
    row["party_activity.party_type"] = "organisation"
    assert safe_row(row)["party_activity.party_name"] == "Person"


def test_standalone_embeds_current_data_and_renderer_without_network_assets(replay):
    html = (ROOT / "reports/dataset-onboarding.html").read_text(encoding="utf-8")
    match = re.search(r'<script id="onboarding-data" type="application/json">(.*?)</script>', html, re.S)
    assert match
    assert "<" not in match[1]
    assert json.loads(match[1]) == replay
    renderer = (ROOT / "frontend/public/onboarding.js").read_text(encoding="utf-8").replace("export function mountOnboarding", "function mountOnboarding")
    assert renderer.replace("</script", "<\\/script") in html
    assert not re.search(r'<(?:script|img|link)[^>]+(?:src|href)=["\'](?:https?://|/)', html)
    assert not re.search(r'url\(["\']?(?:https?://|/)', html)
