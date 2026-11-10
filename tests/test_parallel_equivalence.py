"""Partitioned extraction must produce exactly the serial statistics (the WRITEUP's throughput claim).
Uses the real QBCC snapshot when it has been downloaded (`python -m firmable.cli fetch`); skipped otherwise."""
import pytest

from firmable.paths import ROOT


def _snapshot_present():
    try:
        from firmable.sources.select import load_manifest
        return (ROOT / load_manifest()["qbcc_licensees"]["snapshot"]["path"]).exists()
    except Exception:
        return False


@pytest.mark.skipif(not _snapshot_present(), reason="raw data not downloaded")
def test_partitioned_equals_serial():
    from firmable.extract import load_config
    from firmable.fullcheck import parallel_stats
    from firmable.mapping.engine import Engine
    from firmable.sources.readers import iter_records
    from firmable.sources.select import load_manifest
    cfg, _ = load_config("qbcc_licensees")
    src = load_manifest()["qbcc_licensees"]
    eng = Engine(cfg, src)
    for rec in iter_records(ROOT / src["snapshot"]["path"], cfg.reader):
        eng.process(rec)
    serial = eng.report()
    par = parallel_stats("qbcc_licensees", workers=3, chunk=5000)
    assert par["rows"] == serial["records_in"]
    assert par["emitted"] == sum(f["emitted"] for f in serial["fields"])
    serial_errors = {f"{f['target']}:{k}": v for f in serial["fields"] for k, v in f["errors"].items()}
    assert par["errors"] == serial_errors
