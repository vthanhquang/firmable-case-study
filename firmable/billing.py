"""Optional direct DeepSeek balance snapshots; balances are not per-run costs.

Historical receipts remain unchanged in runs/billing_snapshots.jsonl.
This command is never needed by the offline replay or by onboarding.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import httpx

from . import llm
from .paths import RUNS

SNAPSHOTS = Path(os.environ["FIRMABLE_BILLING_LEDGER"]) if "FIRMABLE_BILLING_LEDGER" in os.environ else RUNS / "deepseek_balance_snapshots.jsonl"


def snapshot(label: str) -> dict:
    if os.environ.get("FIRMABLE_OFFLINE") == "1":
        raise RuntimeError("Provider calls are disabled by FIRMABLE_OFFLINE=1")
    from urllib.parse import urlparse
    if urlparse(llm.BASE_URL).hostname != "api.deepseek.com":
        raise RuntimeError("Balance snapshots support only the direct DeepSeek endpoint")
    key = llm._api_key()
    r = httpx.get("https://api.deepseek.com/user/balance",
                  headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    rec = {"label": label, "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "key_var": llm.KEY_VAR, "balance": r.json(),
           "ledger_tokens": llm.tokens_used()}
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    with open(SNAPSHOTS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


if __name__ == "__main__":
    import sys
    print(snapshot(sys.argv[1] if len(sys.argv) > 1 else "manual"))
