"""Evidence collection for the Part-1 hand check: a seeded random 20 of the frozen shortlist.

For each sampled dataset we fetch the first bytes of its first machine-readable resource and show
the header + a few rows, so the label (YES/NO/UNCERTAIN: contains identifiable business entities)
is made from the data, not from the title. Labels live in outputs/evaluation/triage_audit_20.csv.
"""
from __future__ import annotations

import io
import json
import random

import httpx

from ..paths import OUT_DISCOVERY, OUT_EVAL

SEED = 20261109
UA = {"User-Agent": "firmable-case-study/0.1"}
ORDER = ("CSV", "TSV", "XLSX", "XLS", "JSON", "XML", "ZIP")


def sample_ids(shortlist: str = "shortlist_50.jsonl", seed: int = SEED) -> list[dict]:
    short = [json.loads(l) for l in open(OUT_DISCOVERY / shortlist, encoding="utf-8")]
    idx = sorted(random.Random(seed).sample(range(len(short)), 20))
    return [short[i] for i in idx]


def _peek(url: str, fmt: str) -> dict:
    try:
        with httpx.stream("GET", url, headers=UA, timeout=40, follow_redirects=True) as r:
            buf = b""
            for ch in r.iter_bytes():
                buf += ch
                if len(buf) > (3_000_000 if fmt in ("XLSX", "XLS", "ZIP") else 20_000):
                    break
            status = r.status_code
    except Exception as e:
        return {"error": str(e)[:200]}
    if status != 200 or not buf:
        return {"error": f"HTTP {status}, {len(buf)} bytes"}
    if buf[:2] == b"PK" and fmt in ("XLSX", "XLS"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(buf), read_only=True, data_only=True)
            ws = wb.worksheets[0]
            rows = [[None if c is None else str(c)[:40] for c in row[:15]] for _, row in zip(range(6), ws.iter_rows(values_only=True))]
            return {"sheet": ws.title, "rows": rows}
        except Exception as e:
            return {"error": f"xlsx partial read failed: {e}"[:200]}
    text = buf.decode("utf-8", errors="replace")
    return {"head": [ln[:300] for ln in text.splitlines()[:6]]}


def collect(shortlist: str = "shortlist_50.jsonl", seed: int = SEED,
            out_name: str = "triage_audit_evidence.json") -> list[dict]:
    pool = {}
    for line in open(OUT_DISCOVERY / "catalogue_pool.jsonl", encoding="utf-8"):
        r = json.loads(line)
        pool[r["dataset_id"]] = r
    out = []
    for s in sample_ids(shortlist, seed):
        res = pool[s["dataset_id"]]["resources"]
        pick = None
        for f in ORDER:
            pick = next((r for r in res if (r.get("format") or "").upper() == f), None)
            if pick:
                break
        ev = _peek(pick["url"], (pick.get("format") or "").upper()) if pick else {"error": "no machine-readable resource"}
        out.append({"rank": s["rank"], "dataset_id": s["dataset_id"], "title": s["title"],
                    "publisher": s["publishing_organisation"], "confidence": s["confidence"],
                    "resource_checked": pick["url"] if pick else None, "evidence": ev})
    OUT_EVAL.mkdir(parents=True, exist_ok=True)
    (OUT_EVAL / out_name).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out
