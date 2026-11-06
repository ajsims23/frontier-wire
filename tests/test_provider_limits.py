"""Free-tier failure modes seen in production (Nov 2026): out-of-quota 402s, Groq's per-request size
limit (413), per-minute 429s, and model discovery picking speech / non-English models."""
import json

import httpx
import pytest

from agent.llm import LLM, Limits, RequestTooLarge
from tests.fakes import completion

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def make(providers, handler, tmp_path, env=None):
    lim = Limits({"max_requests_per_run": 50, "max_requests_per_day": 50, "max_tokens_per_day": 10**7}, tmp_path / "u.json")
    env = env or {p["key_env"]: "k" for p in providers}
    return LLM(providers, lim, http=httpx.Client(transport=httpx.MockTransport(handler)), env=env, sleep=lambda s: None)


def ask(llm, max_tokens=6000):
    return llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA, max_tokens=max_tokens)


TWO = [
    {"name": "cerebras", "base_url": "https://cerebras.example/v1", "key_env": "C", "models": ["gpt-oss-120b"]},
    {"name": "groq", "base_url": "https://groq.example/v1", "key_env": "G", "models": ["big", "small"]},
]


def test_402_skips_provider_for_the_rest_of_the_run(tmp_path):
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append((req.url.host, body["model"]))
        if req.url.host == "cerebras.example":
            return httpx.Response(402, json={"message": "Payment required to access this resource."})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    llm = make(TWO, handler, tmp_path)
    assert ask(llm) == {"ok": True}
    seen.clear()
    assert ask(llm) == {"ok": True}
    assert seen == [("groq.example", "big")]  # Cerebras not asked again this run
    assert any("payment required" in l for l in llm.log)


def test_413_shrinks_the_answer_budget_to_fit(tmp_path):
    budgets = []

    def handler(req):
        body = json.loads(req.content)
        if req.url.host == "cerebras.example":
            return httpx.Response(402, json={})
        budgets.append(body["max_tokens"])
        if body["max_tokens"] + 4000 > 8000:  # 4,000-token prompt; 8,000 tokens/request limit
            msg = (f"Request too large for model `big` on tokens per minute (TPM): Limit 8000, "
                   f"Requested {body['max_tokens'] + 4000}, please reduce your message size and try again.")
            return httpx.Response(413, json={"error": {"message": msg}})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    llm = make(TWO, handler, tmp_path)
    assert ask(llm) == {"ok": True}
    assert budgets[0] == 6000 and budgets[1] <= 3700


def test_413_everywhere_raises_request_too_large(tmp_path):
    def handler(req):
        return httpx.Response(413, json={"error": {"message": "Request too large: Limit 8000, Requested 30000"}})

    llm = make(TWO[1:], handler, tmp_path)
    with pytest.raises(RequestTooLarge):
        ask(llm)


def test_per_minute_429_tries_the_next_model_not_the_next_provider(tmp_path):
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append(body["model"])
        if body["model"] == "big":
            return httpx.Response(429, headers={"retry-after": "2"},
                                  json={"error": {"message": "Rate limit reached on tokens per minute (TPM): Limit 8000"}})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    llm = make(TWO[1:], handler, tmp_path)
    assert ask(llm) == {"ok": True}
    assert seen == ["big", "big", "small"]
    seen.clear()
    ask(llm)
    assert seen[0] == "big"  # the provider wasn't written off: next call starts from its best model again


def test_discovery_skips_speech_and_arabic_models(tmp_path):
    asked = []

    def handler(req):
        if req.method == "GET":
            ids = ["canopylabs/orpheus-v1-english", "allam-2-7b", "playai-tts", "qwen/qwen3.8-27b"]
            return httpx.Response(200, json={"data": [{"id": i} for i in ids]})
        model = json.loads(req.content)["model"]
        asked.append(model)
        if model == "retired":
            return httpx.Response(404, json={"error": {"message": "The model `retired` has been decommissioned"}})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    providers = [{"name": "groq", "base_url": "https://groq.example/v1", "key_env": "G", "models": ["retired"]}]
    llm = make(providers, handler, tmp_path)
    assert ask(llm) == {"ok": True}
    assert asked == ["retired", "qwen/qwen3.8-27b"]
