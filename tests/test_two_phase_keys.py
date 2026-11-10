"""Two-phase key assignment reproduces the serial engine's record ids exactly, even when exact duplicate rows
and empty rows straddle chunk boundaries (the cases that break naive partitioned extraction)."""
from collections import Counter

from firmable.mapping.engine import Engine, number_duplicate, record_base
from firmable.mapping.schema import MappingConfig

CFG = MappingConfig.model_validate({
    "source_id": "t", "record_grain": "legal_entity", "grain_rationale": "rows", "reader": {"format": "delimited"},
    "record_id": {"strategy": "content_hash"},
    "fields": [{"source_paths": ["Name"], "target": "entity.legal_name", "confidence": 0.9, "rationale": "name col"}]})


def test_two_phase_equals_serial():
    rows = []
    for i in range(30):
        rows.append({"Name": f"Co {i % 7}"})        # many exact duplicates
        if i % 5 == 0:
            rows.append({"Name": ""})                # empty records are skipped and never numbered
    serial = Engine(CFG, {}, ingested_at="x")
    serial_ids = [o["observation_id"] for r in rows for o in serial.process(r)]

    chunks = [rows[i:i + 4] for i in range(0, len(rows), 4)]          # boundaries split duplicate runs
    empty = lambda r: all(v is None or str(v).strip() == "" for v in r.values())
    bases = [[None if empty(r) else record_base(r, CFG) for r in c] for c in chunks]   # phase 1 (parallelisable)
    seen = Counter()
    rids = [[None if b is None else number_duplicate(b, seen) for b in bs] for bs in bases]  # in file order
    two_phase_ids = []
    for c, rs in zip(chunks, rids):                                    # phase 2: fresh engine per chunk
        eng = Engine(CFG, {}, ingested_at="x")
        two_phase_ids += [o["observation_id"] for r, rid in zip(c, rs) for o in eng.process(r, rid=rid)]
    assert two_phase_ids == serial_ids


def test_naive_partitioning_would_be_wrong():
    rows = [{"Name": "Same"}] * 4
    naive = []
    for c in (rows[:2], rows[2:]):
        eng = Engine(CFG, {}, ingested_at="x")
        naive += [o["source_record_id"] for r in c for o in eng.process(r)]
    assert len(set(naive)) < 4   # duplicate counters restart per chunk -> colliding keys; hence two phases
