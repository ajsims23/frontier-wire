"""The API usage meter behind the admin dashboard's Usage & limits tab."""
import json

import httpx

from agent import usage
from agent.llm import LLM, Limits
from tests.fakes import completion

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def test_llm_calls_are_metered_with_limits_and_headers(tmp_path, monkeypatch):
    meter = usage.Meter()
    monkeypatch.setattr("agent.llm.METER", meter)
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] <= 2:   # first try and its retry hit the per-minute limit
            return httpx.Response(429, json={"error": {"message": "Rate limit reached: tokens per minute"}})
        body = completion("submit", {"ok": True})
        body["usage"] = {"total_tokens": 1234}
        return httpx.Response(200, json=body, headers={"x-ratelimit-remaining-requests": "987", "x-ratelimit-limit-requests": "1000"})

    providers = [{"name": "groq", "base_url": "https://groq.example/v1", "key_env": "G", "models": ["big", "small"]}]
    lim = Limits({"max_requests_per_run": 50, "max_requests_per_day": 50, "max_tokens_per_day": 10**7}, tmp_path / "u.json")
    llm = LLM(providers, lim, http=httpx.Client(transport=httpx.MockTransport(handler)), env={"G": "k"}, sleep=lambda s: None)
    assert llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA) == {"ok": True}
    big, small = meter.rows[("groq", "big")], meter.rows[("groq", "small")]
    assert (big["requests"], big["limited"]) == (2, 2)
    assert (small["requests"], small["ok"], small["tokens"]) == (1, 1, 1234)
    assert meter.state[("groq", "small|x-ratelimit-remaining-requests")] == "987"
    assert "tokens per minute" in meter.state[("groq", "big|last limit")]


def test_flush_reports_to_the_worker_once_and_only_with_the_secret(monkeypatch):
    sent = []
    monkeypatch.setattr(usage.httpx, "post", lambda url, json, timeout, headers: sent.append((url, json, headers)))
    m = usage.Meter()
    m.source = "Newsroom agent"
    m.add("pexels", "video search", "ok", headers={"X-Ratelimit-Remaining": "19000", "Content-Type": "x"})
    monkeypatch.delenv("ALERTS_DISPATCH_SECRET", raising=False)
    monkeypatch.delenv("RECAP_SECRET", raising=False)
    m.flush(force=True)
    assert sent == []   # no secret: nothing sent (and nothing lost from the counts)
    monkeypatch.setenv("API_URL", "https://api.example.dev/")
    monkeypatch.setenv("ALERTS_DISPATCH_SECRET", "s")
    m.flush(force=True)
    url, body, headers = sent[0]
    assert url == "https://api.example.dev/api/usage/report" and headers["Authorization"] == "Bearer s"
    assert body["source"] == "Newsroom agent"
    assert body["rows"] == [{"service": "pexels", "model": "video search", "requests": 1, "tokens": 0, "ok": 1, "limited": 0, "busy": 0, "failed": 0}]
    assert body["state"] == [{"service": "pexels", "k": "video search|x-ratelimit-remaining", "v": "19000"}]
    m.flush(force=True)
    assert len(sent) == 1   # cleared after reporting


def test_outcomes():
    assert [usage.outcome_for(c) for c in (200, 429, 402, 503, None, 400)] == ["ok", "limited", "limited", "busy", "busy", "failed"]
