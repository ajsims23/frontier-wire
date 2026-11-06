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


def test_gemini_per_minute_429_waits_for_retry_delay_then_moves_on(tmp_path):
    waits, seen = [], []
    body = {"error": {"code": 429, "message": "Quota exceeded for metric: generate_content_free_tier_requests",
                      "details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
                                  {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "23s"}]}}

    def handler(req):
        model = json.loads(req.content)["model"]
        seen.append((req.url.host, model))
        if req.url.host == "gemini.example":
            return httpx.Response(429, json=body)
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    providers = [{"name": "gemini", "base_url": "https://gemini.example/v1", "key_env": "GM", "models": ["lite", "flash"]},
                 {"name": "groq", "base_url": "https://groq.example/v1", "key_env": "G", "models": ["big"]}]
    lim = Limits({"max_requests_per_run": 50, "max_requests_per_day": 50, "max_tokens_per_day": 10**7}, tmp_path / "u.json")
    llm = LLM(providers, lim, http=httpx.Client(transport=httpx.MockTransport(handler)), env={"GM": "k", "G": "k"},
              sleep=waits.append)
    assert ask(llm) == {"ok": True}
    assert waits[0] == 23.0
    assert seen == [("gemini.example", "lite"), ("gemini.example", "lite"),
                    ("gemini.example", "flash"), ("gemini.example", "flash"), ("groq.example", "big")]


def test_gemini_thought_signature_round_trip_and_stripped_for_others(tmp_path):
    sent = []

    def handler(req):
        body = json.loads(req.content)
        sent.append((req.url.host, body["messages"]))
        return httpx.Response(200, json={"choices": [{"message": {"content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "search_news", "arguments": "{\"query\": \"x\"}"},
             "extra_content": {"google": {"thought_signature": "SIG123"}}}]}}], "usage": {"total_tokens": 10}})

    gem = [{"name": "gemini", "base_url": "https://gemini.example/v1", "key_env": "GM", "models": ["lite"]}]
    llm = make(gem, handler, tmp_path)
    tools = [{"type": "function", "function": {"name": "search_news", "parameters": {"type": "object"}}}]
    msg = llm.step([{"role": "user", "content": "go"}], tools)
    assert msg["calls"][0]["extra_content"]["google"]["thought_signature"] == "SIG123"

    from agent.llm import _for_provider
    history = [{"role": "user", "content": "go"},
               {"role": "assistant", "content": None, "tool_calls": [
                   {"id": "c1", "type": "function", "function": {"name": "search_news", "arguments": "{}"},
                    "extra_content": {"google": {"thought_signature": "SIG123"}}},
                   {"id": "c2", "type": "function", "function": {"name": "read_page", "arguments": "{}"}}]},
               {"role": "assistant", "content": None, "tool_calls": [  # made by Groq before a fallback to Gemini
                   {"id": "c3", "type": "function", "function": {"name": "finish", "arguments": "{}"}}]}]
    g = _for_provider("gemini", history)
    assert g[1]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "SIG123"
    assert "extra_content" not in g[1]["tool_calls"][1]
    assert g[2]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "skip_thought_signature_validator"
    q = _for_provider("groq", history)
    assert all("extra_content" not in c for m in q[1:] for c in m["tool_calls"])


def test_mistral_gets_any_for_a_forced_single_tool_and_9_char_ids(tmp_path):
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    mis = [{"name": "mistral", "base_url": "https://mistral.example/v1", "key_env": "M", "models": ["mistral-medium-latest"]}]
    llm = make(mis, handler, tmp_path)
    assert ask(llm) == {"ok": True}
    assert bodies[0]["tool_choice"] == "any"

    from agent.llm import _for_provider
    history = [{"role": "user", "content": "go"},
               {"role": "assistant", "content": None, "tool_calls": [
                   {"id": "function-call-1234567890", "type": "function", "function": {"name": "search_news", "arguments": "{}"},
                    "extra_content": {"google": {"thought_signature": "SIG"}}},
                   {"id": "abcDEF123", "type": "function", "function": {"name": "read_page", "arguments": "{}"}}]},
               {"role": "tool", "tool_call_id": "function-call-1234567890", "content": "r1"},
               {"role": "tool", "tool_call_id": "abcDEF123", "content": "r2"}]
    m = _for_provider("mistral", history)
    a, b = m[1]["tool_calls"][0]["id"], m[1]["tool_calls"][1]["id"]
    assert len(a) == 9 and a.isalnum() and b == "abcDEF123"
    assert m[2]["tool_call_id"] == a and m[3]["tool_call_id"] == b
    assert all("extra_content" not in c for c in m[1]["tool_calls"])
    assert history[1]["tool_calls"][0]["id"] == "function-call-1234567890"  # caller's history untouched


def test_410_gone_counts_as_retired_and_triggers_discovery(tmp_path):
    asked = []

    def handler(req):
        if req.method == "GET":
            ids = ["nvidia/nemotron-3.5-embed-1b", "nvidia/nemotron-4-340b-reward", "nvidia/nemotron-3-super-120b-a12b"]
            return httpx.Response(200, json={"data": [{"id": i} for i in ids]})
        model = json.loads(req.content)["model"]
        asked.append(model)
        if model == "openai/gpt-oss-120b":
            return httpx.Response(410, json={"title": "Gone", "detail": "The model has reached its end of life"})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    providers = [{"name": "nvidia", "base_url": "https://nim.example/v1", "key_env": "N", "models": ["openai/gpt-oss-120b"]}]
    llm = make(providers, handler, tmp_path)
    assert ask(llm) == {"ok": True}
    assert asked == ["openai/gpt-oss-120b", "nvidia/nemotron-3-super-120b-a12b"]
