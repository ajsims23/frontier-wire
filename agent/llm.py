"""AI calls through free providers (standard chat-completions API) with automatic fallback.

Each call asks for a JSON answer matching a schema, by giving the model one tool
to call ("submit_…"). If a provider is rate-limited, down or rejects the key, the
next provider is tried; if a model has been retired, the next model is tried.
Request and token caps keep usage inside free tiers.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx


class LimitReached(RuntimeError):
    pass


class AllProvidersFailed(RuntimeError):
    pass


class Limits:
    """Request/token caps per run and per day, persisted in data/usage.json."""

    def __init__(self, cfg: dict[str, Any], usage_file: Path, today: str | None = None):
        self.max_run = int(cfg["max_requests_per_run"])
        self.max_day = int(cfg["max_requests_per_day"])
        self.max_tokens_day = int(cfg["max_tokens_per_day"])
        self.usage_file = usage_file
        self.today = today or datetime.now(timezone.utc).date().isoformat()
        self._usage: dict[str, dict[str, int]] = {}
        if usage_file.exists():
            try:
                self._usage = json.loads(usage_file.read_text())
            except json.JSONDecodeError:
                pass
        self.run_requests = 0
        self.run_tokens = 0

    @property
    def day(self) -> dict[str, int]:
        return self._usage.setdefault(self.today, {"requests": 0, "tokens": 0})

    def check(self) -> None:
        if self.run_requests >= self.max_run:
            raise LimitReached(f"per-run cap of {self.max_run} AI requests reached")
        if self.day["requests"] >= self.max_day:
            raise LimitReached(f"daily cap of {self.max_day} AI requests reached")
        if self.day["tokens"] >= self.max_tokens_day:
            raise LimitReached(f"daily cap of {self.max_tokens_day:,} tokens reached")

    def add(self, tokens: int) -> None:
        self.run_requests += 1
        self.run_tokens += tokens
        self.day["requests"] += 1
        self.day["tokens"] += tokens

    def save(self) -> None:
        keep = dict(sorted(self._usage.items())[-60:])
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        self.usage_file.write_text(json.dumps(keep, indent=2))


def _extract_json(text: str) -> dict[str, Any] | None:
    """Fallback when a model answers in plain text instead of calling the tool."""
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        val = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return val if isinstance(val, dict) else None


class LLM:
    def __init__(self, providers: list[dict[str, Any]], limits: Limits, *,
                 http: httpx.Client | None = None, env: dict[str, str] | None = None,
                 sleep: Callable[[float], None] = time.sleep, timeout: float = 90.0):
        env = env if env is not None else dict(os.environ)
        self.providers = [dict(p, key=env[p["key_env"]]) for p in providers if env.get(p["key_env"])]
        self.limits = limits
        self.http = http or httpx.Client(timeout=timeout)
        self.sleep = sleep
        self._dead_providers: set[str] = set()
        self._dead_models: set[tuple[str, str]] = set()
        self.log: list[str] = []

    @property
    def configured(self) -> list[str]:
        return [p["name"] for p in self.providers]

    def _post(self, p: dict[str, Any], body: dict[str, Any]) -> httpx.Response:
        url = p["base_url"].rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
        if p["name"] == "openrouter":
            headers["X-Title"] = "Frontier Wire"
        resp = None
        for attempt in range(2):
            try:
                resp = self.http.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                if attempt == 1:
                    raise
                self.log.append(f"{p['name']}: network error {type(exc).__name__}, retrying")
                self.sleep(3)
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                wait = min(float(resp.headers.get("retry-after", "5") or 5), 20.0)
                self.sleep(wait)
                continue
            break
        return resp

    _PREFERRED = [r"gpt-oss-120b", r"qwen.*(235b|480b|coder)", r"llama.*(3\.3|4).*(70b|maverick|scout)", r"glm", r"qwen", r"llama", r"gpt-oss"]
    _NOT_CHAT = re.compile(r"embed|whisper|tts|guard|rerank|moderation|vision-preview|audio|image", re.I)

    def _discover(self, p: dict[str, Any], tried: set[str]) -> list[str]:
        """List the provider's current models and pick likely chat models we haven't tried."""
        try:
            resp = self.http.get(p["base_url"].rstrip("/") + "/models", headers={"Authorization": f"Bearer {p['key']}"})
            ids = [m.get("id") for m in (resp.json().get("data") or []) if isinstance(m, dict)]
        except Exception as exc:  # noqa: BLE001
            self.log.append(f"{p['name']}: couldn't list models ({type(exc).__name__})")
            return []
        ids = [i for i in ids if i and i not in tried and not self._NOT_CHAT.search(i)
               and (p["name"], i) not in self._dead_models]
        ranked = sorted(ids, key=lambda i: next((n for n, pat in enumerate(self._PREFERRED) if re.search(pat, i, re.I)), 99))
        picks = ranked[:3]
        if picks:
            self.log.append(f"{p['name']}: listed models retired; trying {', '.join(picks)} (update settings.yaml when convenient)")
        return picks

    def _attempt(self, p: dict[str, Any], model: str, system: str, prompt: str, tool: dict[str, Any],
                 schema_name: str, required: list[str], max_tokens: int) -> tuple[str, dict[str, Any] | None]:
        """One request. Returns ("ok", answer) | ("retry", None) | ("next", None) | ("dead", None)."""
        self.limits.check()
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "tools": [tool],
            "tool_choice": {"type": "function", "function": {"name": schema_name}},
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        try:
            resp = self._post(p, body)
        except httpx.HTTPError as exc:
            self.log.append(f"{p['name']}: unreachable ({type(exc).__name__}); skipping provider")
            self._dead_providers.add(p["name"])
            return "dead", None
        code = resp.status_code
        if code in (401, 403):
            self.log.append(f"{p['name']}: key rejected ({code}); skipping provider")
            self._dead_providers.add(p["name"])
            return "dead", None
        if code in (400, 404) and re.search(r"model|decommission|not found|does not exist", resp.text, re.I):
            self.log.append(f"{p['name']}/{model}: model unavailable ({code}); trying next model")
            self._dead_models.add((p["name"], model))
            return "next", None
        if code == 429 or code >= 500:
            self.log.append(f"{p['name']}: {code} after retry; moving to next provider for this run")
            self._dead_providers.add(p["name"])
            return "dead", None
        if code != 200:
            self.log.append(f"{p['name']}/{model}: HTTP {code}: {resp.text[:150]}")
            return "next", None

        data = resp.json()
        usage = data.get("usage") or {}
        self.limits.add(int(usage.get("total_tokens") or 0))
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        answer = None
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            if fn.get("name") == schema_name:
                args = fn.get("arguments")
                answer = args if isinstance(args, dict) else _extract_json(args or "")
                break
        if answer is None:
            answer = _extract_json(msg.get("content") or "")
        if answer is None or any(k not in answer for k in required):
            self.log.append(f"{p['name']}/{model}: unusable answer")
            return "retry", None
        return "ok", answer

    def ask(self, *, system: str, prompt: str, schema_name: str, schema: dict[str, Any],
            max_tokens: int = 3000) -> dict[str, Any]:
        if not self.providers:
            raise AllProvidersFailed("no AI provider key is set (e.g. CEREBRAS_API_KEY or GROQ_API_KEY)")
        tool = {"type": "function", "function": {
            "name": schema_name,
            "description": "Submit your final answer. Call this exactly once.",
            "parameters": schema,
        }}
        required = schema.get("required", [])

        for p in self.providers:
            if p["name"] in self._dead_providers:
                continue
            queue = list(p["models"])
            tried: set[str] = set()
            discovered = False
            while True:
                if not queue:
                    # Every listed model is gone or failing: ask the provider what it offers now.
                    if discovered or p["name"] in self._dead_providers:
                        break
                    discovered = True
                    queue = self._discover(p, tried)
                    if not queue:
                        break
                model = queue.pop(0)
                if model in tried or (p["name"], model) in self._dead_models:
                    continue
                tried.add(model)
                outcome, answer = "retry", None
                for attempt in range(2):  # one retry when the answer comes back unusable
                    outcome, answer = self._attempt(p, model, system, prompt, tool, schema_name, required, max_tokens)
                    if outcome != "retry":
                        break
                if outcome == "ok":
                    return answer
                if outcome == "dead":
                    break

        raise AllProvidersFailed("every configured provider failed: " + " | ".join(self.log[-4:]))
