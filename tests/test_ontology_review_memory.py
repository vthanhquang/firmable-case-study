import copy

from firmable.evolution.schema import digest
from firmable.evolution2.review import ReviewMemory


def item(kind="concept", definition="Reported annual revenue in AUD"):
    contract = {"definition": definition, "owner": "business", "period_required": True}
    if kind == "binding":
        contract["source_schema"] = {"column": "Revenue", "year": "2024"}
    return {"key": kind + ":revenue", "kind": kind, "contract": contract, "fingerprint": digest(contract)}


def test_synthetic_review_is_never_a_production_approval(tmp_path):
    memory = ReviewMemory(tmp_path / "synthetic-decisions.jsonl")
    concept = item()
    memory.record(concept, reviewer="synthetic fixture", reviewer_kind="synthetic_test", decision="approve", evidence_digest="fixture")
    assert memory.queue([concept])[0]["review_state"] == "new_requires_review"
    assert memory.queue([concept], test_mode=True)[0]["review_state"] == "approved_unchanged"


def test_changed_meaning_or_period_reopens_review_and_binding_is_separate(tmp_path):
    memory = ReviewMemory(tmp_path / "synthetic-decisions.jsonl")
    concept, binding = item(), item("binding")
    for old in [concept, binding]:
        memory.record(old, reviewer="synthetic fixture", reviewer_kind="synthetic_test", decision="approve", evidence_digest="fixture")
    changed = item(definition="Group consolidated annual revenue in AUD")
    assert memory.queue([changed], test_mode=True)[0]["review_state"] == "changed_requires_review"
    new_binding = copy.deepcopy(binding)
    new_binding["contract"]["source_schema"]["year"] = "2025"
    new_binding["fingerprint"] = digest(new_binding["contract"])
    result = memory.queue([concept, new_binding], test_mode=True)
    assert result[0]["review_state"] == "approved_unchanged"
    assert result[1]["review_state"] == "changed_requires_review"
    assert result[1]["changed_contract_parts"] == ["source_schema"]


def test_later_rejection_overrides_earlier_approval(tmp_path):
    memory = ReviewMemory(tmp_path / "synthetic-decisions.jsonl")
    for decision in ["approve", "reject"]:
        memory.record(item(), reviewer="synthetic fixture", reviewer_kind="synthetic_test", decision=decision, evidence_digest="fixture")
    assert memory.queue([item()], test_mode=True)[0]["review_state"] == "rejected_unchanged"
