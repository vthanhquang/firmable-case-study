"""Exercise the direct API contract without a credential or network connection."""
import json

import httpx
import pytest
from openai import OpenAI

from firmable import billing, llm


@pytest.mark.parametrize("endpoint", ["https://api.deepseek.com", "https://gateway.example.test/v1"])
def test_direct_completion_contract_and_ledger(tmp_path, monkeypatch, endpoint):
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
            "model": "deepseek-flash", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 4, "total_tokens": 24}})
    monkeypatch.delenv("FIRMABLE_OFFLINE", raising=False)
    monkeypatch.setattr(llm, "BASE_URL", endpoint)
    if "gateway" in endpoint:
        monkeypatch.setenv("FIRMABLE_DISABLE_THINKING", "1")
    monkeypatch.setattr(llm, "LEDGER", tmp_path / "usage.jsonl")
    monkeypatch.setattr(llm, "TOTAL_TOKEN_BUDGET", None)
    with OpenAI(api_key="test-only", base_url=llm.BASE_URL,
                http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
        monkeypatch.setattr(llm, "_client", client)
        result = llm.chat([{"role": "user", "content": "Return JSON"}], stage="propose_r1",
                          source_id="test", run_id="test", model="deepseek-flash", json_mode=True)
    body = json.loads(requests[0].content)
    assert str(requests[0].url) == endpoint + "/chat/completions"
    assert body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"}
    assert result.content == '{"ok":true}'
    ledger = json.loads(llm.LEDGER.read_text())
    assert ledger["prompt_tokens"] == 20 and ledger["completion_tokens"] == 4
    assert "test-only" not in llm.LEDGER.read_text()


def test_missing_key_is_explicit(monkeypatch):
    monkeypatch.setattr(llm, "KEY_VAR", "DEEPSEEK_API_KEY")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY is not set"):
        llm._api_key()


def test_offline_blocks_balance_request_before_credentials(monkeypatch):
    monkeypatch.setenv("FIRMABLE_OFFLINE", "1")
    with pytest.raises(RuntimeError, match="disabled"):
        billing.snapshot("test")


def test_balance_never_sends_custom_provider_credentials_to_deepseek(monkeypatch):
    monkeypatch.delenv("FIRMABLE_OFFLINE", raising=False)
    monkeypatch.setattr(llm, "BASE_URL", "https://example.test/v1")
    with pytest.raises(RuntimeError, match="only the direct DeepSeek"):
        billing.snapshot("test")
