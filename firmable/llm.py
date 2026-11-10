"""LLM access through MiraiAPI (OpenAI-compatible) with a usage ledger.

Every call appends one line to runs/usage_ledger.jsonl: model, stage, source, tokens, latency.
Cost is reported in tokens (measured) and USD (estimated from PRICE_PER_MTOK, which must be
filled from the provider's price page - see README; unknown price => USD reported as unknown).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .paths import RUNS

BASE_URL = "https://api.miraiapi.com/v1"
DEFAULT_MODEL = os.environ.get("FIRMABLE_MODEL", "deepseek-v4-flash")
CRITIC_MODEL = os.environ.get("FIRMABLE_CRITIC_MODEL", DEFAULT_MODEL)
LEDGER = RUNS / "usage_ledger.jsonl"
TOKEN_BUDGET = int(os.environ.get("FIRMABLE_TOKEN_BUDGET", "6000000"))  # hard stop across all runs

# USD per 1M tokens (input, output). None = unknown. deepseek-v4-flash is MEASURED, not published:
# billing-endpoint deltas vs ledger tokens (runs/billing_snapshots.jsonl): windows range 1.57-1.67 $/M;
# the widest window, 302.14 cents over 1,925,132 tokens, gives 1.57 $/M. Input and output are priced equally.
PRICE_PER_MTOK: dict[str, tuple[float, float] | None] = {
    "deepseek-v4-flash": (1.57, 1.57), "deepseek-v4-pro": None, "deepseek-v4.1-flash": None,
    "glm-5.3-flash": None, "qwen3.8-max": None, "kimi-k3": None, "hy3": None,
}


class BudgetExceeded(RuntimeError):
    pass


# Which environment variable holds the key (the proxy pre-reserves max_tokens of credit per call,
# so a nearly-empty key fails on large calls; point this at a funded key if needed).
KEY_VAR = os.environ.get("FIRMABLE_KEY_VAR", "MIRAI_API_KEY")


def _api_key() -> str:
    key = os.environ.get(KEY_VAR)
    if key:
        return key
    try:  # Windows: user-scope variable not inherited by this process
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, KEY_VAR)[0]
    except OSError:
        raise RuntimeError(f"{KEY_VAR} is not set")


_client = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=_api_key(), base_url=BASE_URL, timeout=180, max_retries=0)
    return _client


def tokens_used() -> int:
    if not LEDGER.exists():
        return 0
    total = 0
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        total += r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)
    return total


def chat(messages: list[dict], *, stage: str, source_id: str, run_id: str, tools: list | None = None,
         model: str | None = None, temperature: float = 0.0, max_tokens: int = 6000, json_mode: bool = False):
    """One chat completion with transient-error retries. Returns the message object."""
    if tokens_used() > TOKEN_BUDGET:
        raise BudgetExceeded(f"token budget {TOKEN_BUDGET} exhausted")
    model = model or DEFAULT_MODEL
    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    if tools:
        kwargs["tools"] = tools
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(4):
        t0 = time.perf_counter()
        try:
            r = client().chat.completions.create(**kwargs)
            break
        except Exception as e:  # rate limits / 5xx / timeouts: back off, do not count as a revision
            last = e
            status = getattr(e, "status_code", None)
            if status in (400, 401, 403) and "quota" not in str(e).lower():
                raise
            if status == 403:
                raise BudgetExceeded(f"provider quota: {e}")
            _log({"stage": stage, "source_id": source_id, "run_id": run_id, "model": model, "error": str(e)[:300],
                  "attempt": attempt, "prompt_tokens": 0, "completion_tokens": 0})
            time.sleep(3 * 2 ** attempt)
    else:
        raise RuntimeError(f"LLM call failed after retries: {last}")
    latency = (time.perf_counter() - t0) * 1000
    u = r.usage
    _log({"stage": stage, "source_id": source_id, "run_id": run_id, "model": model,
          "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
          "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
          "latency_ms": round(latency), "finish_reason": r.choices[0].finish_reason})
    return r.choices[0].message


def _log(rec: dict):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    p = PRICE_PER_MTOK.get(model)
    if not p:
        return None
    return (prompt_tokens * p[0] + completion_tokens * p[1]) / 1e6


def summarize(path: Path = LEDGER) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        k = (r.get("source_id"), r.get("run_id"))
        s = out.setdefault(k, {"calls": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0,
                               "latency_ms": 0, "stages": {}, "models": set()})
        if r.get("error"):
            s["errors"] += 1
            continue
        s["calls"] += 1
        s["prompt_tokens"] += r["prompt_tokens"]
        s["completion_tokens"] += r["completion_tokens"]
        s["latency_ms"] += r.get("latency_ms", 0)
        s["stages"][r["stage"]] = s["stages"].get(r["stage"], 0) + 1
        s["models"].add(r["model"])
    return out
