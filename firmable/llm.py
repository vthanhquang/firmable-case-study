"""DeepSeek's OpenAI-compatible API, with explicit credentials and a usage ledger.

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

BASE_URL = os.environ.get("FIRMABLE_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.environ.get("FIRMABLE_MODEL", "deepseek-flash")
CRITIC_MODEL = os.environ.get("FIRMABLE_CRITIC_MODEL", DEFAULT_MODEL)
LEDGER = Path(os.environ["FIRMABLE_USAGE_LEDGER"]) if "FIRMABLE_USAGE_LEDGER" in os.environ else RUNS / "usage_ledger.jsonl"
TOKEN_BUDGET = int(os.environ.get("FIRMABLE_TOKEN_BUDGET", "350000"))  # applies to one onboarding run, including resumes
TOTAL_TOKEN_BUDGET = int(os.environ["FIRMABLE_TOTAL_TOKEN_BUDGET"]) if "FIRMABLE_TOTAL_TOKEN_BUDGET" in os.environ else None

# New calls are recorded in tokens; the submission's declared tariff is calculated
# separately in its report. Historical gateway prices must not price direct calls.
PRICE_PER_MTOK: dict[str, tuple[float, float] | None] = {
    "deepseek-flash": None, "deepseek-v4-flash": None, "deepseek-v4-pro": None, "deepseek-v4.1-flash": None,
    "glm-5.3-flash": None, "qwen3.8-max": None, "kimi-k3": None, "hy3": None,
}


class BudgetExceeded(RuntimeError):
    pass


KEY_VAR = os.environ.get("FIRMABLE_KEY_VAR", "DEEPSEEK_API_KEY")


def _api_key() -> str:
    key = os.environ.get(KEY_VAR)
    if key:
        return key
    raise RuntimeError(f"{KEY_VAR} is not set; export it in this terminal before onboarding")


_client = None


def client():
    if os.environ.get("FIRMABLE_OFFLINE") == "1":
        raise RuntimeError("Model calls are disabled by FIRMABLE_OFFLINE=1")
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=_api_key(), base_url=BASE_URL, timeout=180, max_retries=0)
    return _client


def tokens_used(run_id: str | None = None, source_id: str | None = None) -> int:
    if not LEDGER.exists():
        return 0
    total = 0
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if run_id is not None and (r.get("run_id") != run_id or r.get("source_id") != source_id):
            continue
        total += r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)
    return total


def chat(messages: list[dict], *, stage: str, source_id: str, run_id: str, tools: list | None = None,
         model: str | None = None, temperature: float = 0.0, max_tokens: int = 6000, json_mode: bool = False):
    """One chat completion with transient-error retries. Returns the message object."""
    if tokens_used(run_id, source_id) >= TOKEN_BUDGET:
        raise BudgetExceeded(f"run token budget {TOKEN_BUDGET} exhausted")
    if TOTAL_TOKEN_BUDGET is not None:
        # Use a conservative byte-based prompt reserve to leave room for the
        # whole request, including the maximum possible completion.
        prompt_reserve = len(json.dumps([messages, tools], ensure_ascii=False).encode("utf-8")) + 2048
        if tokens_used() + prompt_reserve + max_tokens > TOTAL_TOKEN_BUDGET:
            raise BudgetExceeded(f"request would exceed total token budget {TOTAL_TOKEN_BUDGET}")
    model = model or DEFAULT_MODEL
    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    # Ordinary tool transcripts do not carry the provider's reasoning_content.
    # Disable its default thinking mode explicitly for the direct endpoint.
    from urllib.parse import urlparse
    thinking_disabled = (urlparse(BASE_URL).hostname == "api.deepseek.com"
                         or os.environ.get("FIRMABLE_DISABLE_THINKING") == "1")
    if thinking_disabled:
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
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
          "latency_ms": round(latency), "finish_reason": r.choices[0].finish_reason,
          "thinking_disabled_requested": thinking_disabled})
    return r.choices[0].message


def _log(rec: dict):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(LEDGER, "a", encoding="utf-8", newline="\n") as fh:
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
