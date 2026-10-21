import json
from datetime import timedelta

import httpx
import pytest

from agent.config import load_config
from agent.llm import LLM, AllProvidersFailed, Limits
from agent.pipeline import Newsroom, keywords, summary_markdown
from agent.sources import Gdelt
from agent.store import Store
from agent.text import canonical_url, domain, quote_in_text

from .fakes import NOW, SOURCES, FixtureFetcher, completion, newsroom_handler

ENV = {"CEREBRAS_API_KEY": "test-key"}


def make(tmp_path, now=NOW, max_stories=12, **limit_overrides):
    cfg = load_config(data_dir=tmp_path)
    cfg.sources = SOURCES
    cfg.tracked_labs = ["Example Lab", "Other Lab"]
    cfg.lab_domains = {"examplelab.ai": "Example Lab"}
    cfg.gdelt["query"] = '("artificial intelligence") sourcelang:english'
    cfg.limits.update(limit_overrides)
    cfg.run["max_stories_per_run"] = max_stories
    calls: list[dict] = []
    http = httpx.Client(transport=httpx.MockTransport(newsroom_handler(calls)))
    llm = LLM(cfg.providers, Limits(cfg.limits, tmp_path / "usage.json", today=now.date().isoformat()),
              http=http, env=ENV, sleep=lambda s: None)
    fetcher = FixtureFetcher()
    room = Newsroom(cfg, llm, fetcher, Store(tmp_path), now, gdelt=Gdelt(fetcher, sleep=lambda s: None))
    return room, calls


def test_full_run(tmp_path):
    room, calls = make(tmp_path)
    report = room.run()
    heads = [w["headline"] for w in report["written"]]
    dropped = {d["title"]: d["reason"] for d in report["dropped"]}
    stories = {s["headline"]: s for s in json.loads((tmp_path / "stories.json").read_text())}

    # sources: failures reported, not fatal; quantised HF copy, repost, short post and Ask HN filtered
    assert report["sources"]["broken"].startswith("failed")
    assert "failed accounts: missing.example.social" in report["sources"]["bluesky"]
    assert report["sources"]["hf-models"] == "ok (1)"
    assert report["sources"]["hn"] == "ok (1)"
    assert report["sources"]["hf-papers"] == "ok (1)"
    assert report["providers"] == ["cerebras"]
    assert calls[0]["model"] == "gpt-oss-120b"

    # lab post written once with the news coverage merged in
    nova = stories["Introducing Nova 2, our new multimodal model"]
    assert {s["url"] for s in nova["sources"]} == {"https://examplelab.ai/news/nova-2", "https://technews.example.com/nova-2-launch"}
    assert [q["speaker"] for q in nova["quotes"]] == ["Ada Example"]  # invented quote removed
    assert any("unverifiable quote" in n for n in report["notes"])

    # news-only stories need a second outlet, found through GDELT
    council = stories["City council approves AI rules for public buses"]
    assert {domain(s["url"]) for s in council["sources"]} == {"example.com", "example.org"} or len(council["sources"]) == 2
    assert "could not verify" in dropped["Startup claims AGI will arrive next week"]
    assert any("Regulator" in h for h in heads)  # GDELT-scouted story, confirmed

    # HN link to a lab's own site counts as a primary source
    assert "Example Lab ships an agent toolkit" in stories

    # arXiv and HF daily papers point at the same paper → one story
    assert sum("Looped" in h for h in heads) == 1

    # Bluesky post: quote checked against the post text itself
    jane = next(s for h, s in stories.items() if h.startswith("Jane Doe:"))
    assert jane["quotes"][0]["text"] == "evaluation needs to catch up fast"

    # filtering
    assert "score 2" in dropped["10 prompts to boost your productivity"]
    assert not any("old" in h.lower() for h in heads)
    assert any("Atlas" in h for h in heads)

    # tracker: newest release per lab
    labs = json.loads((tmp_path / "labs.json").read_text())
    assert labs["Example Lab"]["model"] == "Nova 2"
    site = json.loads((tmp_path / "site.json").read_text())
    assert site["lead"]["headline"].startswith("Introducing Nova 2")
    assert any(l["lab"] == "Other Lab" and l["model"] is None for l in site["labs"])
    assert {q["speaker"] for q in site["voices"]} == {"Ada Example", "Jane Doe"}
    assert (tmp_path / "feed.xml").read_text().count("<item>") == len(stories)

    assert report["ai_requests_run"] == len(calls) <= 40
    assert "New stories" in summary_markdown(report)


def test_carry_over_then_nothing_new(tmp_path):
    room, _ = make(tmp_path, max_stories=8)
    first = room.run()
    assert len(first["written"]) == 7 and any("carried over" in n for n in first["notes"])
    room2, _ = make(tmp_path, now=NOW + timedelta(hours=3), max_stories=8)
    second = room2.run()
    assert {w["category"] for w in second["written"]} == {"voices"}  # the two items the cap pushed out
    room3, calls3 = make(tmp_path, now=NOW + timedelta(hours=6), max_stories=8)
    third = room3.run()
    assert third["written"] == [] and calls3 == []  # nothing new → no AI calls at all


def test_run_cap(tmp_path):
    room, calls = make(tmp_path, max_requests_per_run=2)
    report = room.run()
    assert len(calls) == 2
    assert any("cap" in n for n in report["notes"])


def test_daily_cap(tmp_path):
    (tmp_path / "usage.json").write_text(json.dumps({NOW.date().isoformat(): {"requests": 999, "tokens": 0}}))
    room, calls = make(tmp_path)
    report = room.run()
    assert calls == [] and report["written"] == []
    assert json.loads((tmp_path / "seen.json").read_text()) == {}  # retried next run


# ------------------------------------------------------------------ provider fallback
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
PROVIDERS = [
    {"name": "first", "base_url": "https://first.example/v1", "key_env": "K1", "models": ["m1"]},
    {"name": "second", "base_url": "https://second.example/v1", "key_env": "K2", "models": ["retired", "good"]},
    {"name": "third", "base_url": "https://third.example/v1", "key_env": "K3", "models": ["m3"]},
]


def llm_with(handler, env, tmp_path):
    lim = Limits({"max_requests_per_run": 10, "max_requests_per_day": 10, "max_tokens_per_day": 10**6}, tmp_path / "u.json")
    return LLM(PROVIDERS, lim, http=httpx.Client(transport=httpx.MockTransport(handler)), env=env, sleep=lambda s: None)


def test_fallback_rate_limit_then_retired_model(tmp_path):
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append((req.url.host, body["model"]))
        if req.url.host == "first.example":
            return httpx.Response(429, headers={"retry-after": "1"}, json={"error": "rate limited"})
        if body["model"] == "retired":
            return httpx.Response(404, json={"error": {"message": "The model `retired` does not exist"}})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    llm = llm_with(handler, {"K1": "a", "K2": "b"}, tmp_path)
    assert llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA) == {"ok": True}
    assert seen == [("first.example", "m1"), ("first.example", "m1"), ("second.example", "retired"), ("second.example", "good")]
    # next call skips the rate-limited provider and the retired model
    seen.clear()
    llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA)
    assert seen == [("second.example", "good")]


def test_bad_key_and_text_answer(tmp_path):
    def handler(req):
        if req.url.host == "first.example":
            return httpx.Response(401, json={"error": "bad key"})
        if req.url.host == "second.example":
            return httpx.Response(200, json={"choices": [{"message": {"content": "garbage"}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "Sure!\n```json\n{\"ok\": true}\n```"}}]})

    llm = llm_with(handler, {"K1": "a", "K2": "b", "K3": "c"}, tmp_path)
    assert llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA) == {"ok": True}
    assert any("key rejected" in l for l in llm.log)


def test_no_keys(tmp_path):
    llm = llm_with(lambda r: httpx.Response(500), {}, tmp_path)
    with pytest.raises(AllProvidersFailed):
        llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA)


# ------------------------------------------------------------------ helpers
@pytest.mark.parametrize("quote,ok", [
    ("We built Nova 2 to reason across text, images and audio", True),
    ("we built nova 2 to reason across text,   images and audio.", True),
    ("We built Nova 2 to reason across text and video", False),
    ("Nova 2", False),
])
def test_quote_check(quote, ok):
    text = "Today. “We built Nova 2 to reason across text, images and audio,” said Ada."
    assert quote_in_text(quote, text) is ok


def test_url_helpers():
    assert canonical_url("http://www.Example.com/a/?utm_source=x&id=3") == "https://example.com/a?id=3"
    assert canonical_url("http://arxiv.org/abs/2610.00001v2") == canonical_url("https://arxiv.org/pdf/2610.00001.pdf")
    assert domain("https://news.bbc.co.uk/x") == "bbc.co.uk"
    assert keywords("City council approves AI rules for public buses")[:2] == ["City", "approves"] or "council" in keywords("City council approves AI rules for public buses")


# ------------------------------------------------------------------ GDELT rate-limits + free corroboration
class RateLimitedFetcher(FixtureFetcher):
    """Every GDELT call is rate-limited (as on shared GitHub runners); a second outlet's feed exists."""
    OTHER = """<?xml version="1.0"?><rss version="2.0"><channel><title>Other News</title>
<item><title>Council approves new AI rules for city buses</title><link>https://othernews.example.org/council-bus-ai</link>
<description>Vote passed.</description></item></channel></rss>"""

    def get(self, url):
        if url.startswith("https://api.gdeltproject.org"):
            self.requests.append(url)
            raise RuntimeError("Client error '429 Too Many Requests'")
        if url == "https://othernews.example.org/feed":
            return self.OTHER
        return super().get(url)


def test_gdelt_rate_limited_falls_back_to_fetched_items(tmp_path):
    room, _ = make(tmp_path)
    room.cfg.sources = SOURCES + [{"id": "othernews", "name": "Other News", "kind": "rss",
                                   "url": "https://othernews.example.org/feed", "role": "news"}]
    room.fetcher = RateLimitedFetcher()
    room.gdelt = Gdelt(room.fetcher, sleep=lambda s: None)
    report = room.run()
    stories = {s["headline"]: s for s in json.loads((tmp_path / "stories.json").read_text())}

    assert report["sources"]["gdelt"].startswith("failed")
    # 3 tries, then GDELT is paused for the rest of the run (no more requests)
    assert sum(u.startswith("https://api.gdeltproject.org") for u in room.fetcher.requests) == 3
    assert any("GDELT unavailable" in n for n in report["notes"])
    # council story confirmed by the other outlet already fetched this run
    council = stories["City council approves AI rules for public buses"]
    assert "https://othernews.example.org/council-bus-ai" in {s["url"] for s in council["sources"]}
    # unconfirmable claim still blocked
    assert not any("AGI" in h for h in stories)
