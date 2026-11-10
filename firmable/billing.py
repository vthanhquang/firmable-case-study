"""Provider-side spend snapshots via the proxy's OpenAI-compatible billing endpoint.

`total_usage` is reported in hundredths of the proxy's billing currency (OpenAI convention: cents).
Taking a snapshot before and after a set of runs and dividing by the ledger's token counts for the
same window gives the actually-billed cost, independent of any published price list.
"""
from __future__ import annotations

import datetime as dt
import json

import httpx

from . import llm
from .paths import RUNS

SNAPSHOTS = RUNS / "billing_snapshots.jsonl"


def snapshot(label: str) -> dict:
    key = llm._api_key()
    today = dt.date.today()
    r = httpx.get("https://api.miraiapi.com/v1/dashboard/billing/usage",
                  params={"start_date": (today - dt.timedelta(days=60)).isoformat(),
                          "end_date": (today + dt.timedelta(days=1)).isoformat()},
                  headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    rec = {"label": label, "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "key_var": llm.KEY_VAR, "total_usage_cents": r.json().get("total_usage"),
           "ledger_tokens": llm.tokens_used()}
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    import sys
    print(snapshot(sys.argv[1] if len(sys.argv) > 1 else "manual"))
