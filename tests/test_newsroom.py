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
    assert "could not verify yet" in dropped["Startup claims AGI will arrive next week"]
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
    assert any("Atlas" in h for h in heads)  # the editor's made-up duplicate id was ignored
    assert any("made-up duplicate id deadbeef0000" in n for n in report["notes"])

    # tracker: newest release per lab
    labs = json.loads((tmp_path / "labs.json").read_text())
    assert labs["Example Lab"]["model"] == "Nova 2"
    site = json.loads((tmp_path / "site.json").read_text())
    assert site["lead"]["headline"].startswith("Introducing Nova 2")
    assert any(l["lab"] == "Other Lab" and l["model"] is None for l in site["labs"])
    assert {q["speaker"] for q in site["voices"]} == {"Ada Example", "Jane Doe"}
    assert (tmp_path / "feed.xml").read_text().count("<item>") == len(stories)

    # preview images: the page's own og:image (made absolute); generic logos are skipped
    assert nova["image"] == "https://examplelab.ai/images/nova2-hero.jpg"
    assert stories["Atlas robotics safety update"]["image"] is None
    assert site["lead"]["image"] == "https://examplelab.ai/images/nova2-hero.jpg"

    # the research agent investigated the stories without official sources, plus the top story
    r = report["research"]
    assert r["investigated"] == 4 and r["confirmed"] == 2
    assert council["research"]["decision"] == "confirmed" and council["research"]["steps"] >= 2
    tool_turns = [c for c in calls if any(t["function"]["name"] == "search_news" for t in c.get("tools", []))]
    assert any(m.get("role") == "tool" for c in tool_turns for m in c["messages"])  # real multi-turn tool use
    assert "Research agent" in summary_markdown(report)

    assert report["ai_requests_run"] == len(calls) <= 70
    assert "New stories" in summary_markdown(report)


def test_carry_over_then_nothing_new(tmp_path):
    room, _ = make(tmp_path, max_stories=8)
    first = room.run()
    assert len(first["written"]) == 7 and any("carried over" in n for n in first["notes"])
    room2, _ = make(tmp_path, now=NOW + timedelta(hours=3), max_stories=8)
    second = room2.run()
    assert {w["category"] for w in second["written"]} == {"voices"}  # the two items the cap pushed out
    # the unverifiable claim got exactly one retry in run 2, and is now dropped for good
    assert any("after a second try" in d["reason"] for d in second["dropped"])
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
    # council story confirmed by the other outlet already fetched this run
    council = stories["City council approves AI rules for public buses"]
    assert "https://othernews.example.org/council-bus-ai" in {s["url"] for s in council["sources"]}
    # unconfirmable claim still blocked
    assert not any("AGI" in h for h in stories)


def test_backfills_images_for_existing_stories(tmp_path):
    room, _ = make(tmp_path)
    room.run()
    stories = json.loads((tmp_path / "stories.json").read_text())
    for st in stories:
        st.pop("image", None)  # stories written before images existed
    (tmp_path / "stories.json").write_text(json.dumps(stories))
    room2, calls2 = make(tmp_path, now=NOW + timedelta(hours=3))
    room2.run()
    after = {s["headline"]: s for s in json.loads((tmp_path / "stories.json").read_text())}
    assert after["Introducing Nova 2, our new multimodal model"]["image"] == "https://examplelab.ai/images/nova2-hero.jpg"
    assert all("image" in s for s in after.values())
    assert not any(c["tools"][0]["function"]["name"] == "submit_story" for c in calls2)  # images need no AI


def test_retry_unusable_then_discover_new_models(tmp_path):
    seen = []
    state = {"bad_once": True}

    def handler(req):
        if req.method == "GET" and req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "whisper-large"}, {"id": "llama-9-70b-new"}, {"id": "gpt-oss-120b"}]})
        body = json.loads(req.content)
        seen.append(body["model"])
        if body["model"] == "gpt-oss-120b" and state["bad_once"]:
            state["bad_once"] = False
            return httpx.Response(200, json={"choices": [{"message": {"content": "no json here"}}]})
        if body["model"] in ("retired-a", "retired-b"):
            return httpx.Response(404, json={"error": {"message": "Model not found"}})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    providers = [{"name": "c", "base_url": "https://c.example/v1", "key_env": "K", "models": ["gpt-oss-120b", "retired-a"]}]
    lim = Limits({"max_requests_per_run": 20, "max_requests_per_day": 20, "max_tokens_per_day": 10**6}, tmp_path / "u.json")
    llm = LLM(providers, lim, http=httpx.Client(transport=httpx.MockTransport(handler)), env={"K": "x"}, sleep=lambda s: None)
    # bad answer is retried once on the same model, then succeeds
    assert llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA) == {"ok": True}
    assert seen == ["gpt-oss-120b", "gpt-oss-120b"]

    # all listed models retired -> discover from /models (skipping non-chat models)
    providers2 = [{"name": "c", "base_url": "https://c.example/v1", "key_env": "K", "models": ["retired-a", "retired-b"]}]
    seen.clear()
    llm2 = LLM(providers2, lim, http=httpx.Client(transport=httpx.MockTransport(handler)), env={"K": "x"}, sleep=lambda s: None)
    assert llm2.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA) == {"ok": True}
    assert seen == ["retired-a", "retired-b", "gpt-oss-120b"]
    assert any("listed models retired" in l for l in llm2.log)


def test_tracker_rebuilt_from_existing_stories(tmp_path):
    room, _ = make(tmp_path)
    room.run()
    (tmp_path / "labs.json").write_text("{}")  # tracker lost / written before the fallback existed
    room2, _ = make(tmp_path, now=NOW + timedelta(hours=3))
    room2.run()
    labs = json.loads((tmp_path / "labs.json").read_text())
    assert labs["Example Lab"]["model"] == "Nova 2"


@pytest.mark.parametrize("title,ok", [
    ("US orders federal agencies to remove China's DeepSeek AI from their systems", True),
    ("Google open-sources TorchTPU, a native PyTorch back end for TPUs", False),
    ("Why Super Micro Computer Stock Popped Today", False),
    ("Said the AIDS charity", False),
    ("OpenAI acquires biotech startup", True),
])
def test_gdelt_headline_filter(title, ok):
    from agent.sources import is_ai_headline
    assert is_ai_headline(title) is ok


def test_research_agent_guardrails():
    from agent.research import Researcher
    from agent.sources import Item

    class ScriptedLLM:
        """Tries to read an unlisted page, cites an invented URL, and never finishes on its own."""
        def __init__(self):
            self.turns = 0
            self.forced = []

        def step(self, messages, tools, force=None, max_tokens=1200):
            self.turns += 1
            self.forced.append(force)
            if force == "finish":
                return {"calls": [{"id": "f", "name": "finish", "args": {"decision": "confirmed", "sources": [
                    "https://invented.example.com/story", "https://othernews.example.org/council-bus-ai"]}}], "text": ""}
            if self.turns == 1:
                return {"calls": [{"id": "r", "name": "read_page", "args": {"url": "https://secret.example.com/x"}}], "text": ""}
            return {"calls": [{"id": f"s{self.turns}", "name": "search_news", "args": {"query": "council AI rules buses"}}], "text": ""}

    pool = [Item(url="https://othernews.example.org/council-bus-ai", title="Council approves new AI rules for city buses",
                 source_id="o", source_name="Other News", role="news")]
    fetcher = FixtureFetcher()
    llm = ScriptedLLM()
    r = Researcher(llm, fetcher, Gdelt(fetcher, sleep=lambda s: None), pool, max_steps=4)
    out = r.investigate("City council approves AI rules for public buses", "", [
        {"url": "https://technews.example.com/council-ai", "publisher": "Tech News", "title": "x"}])

    assert "https://secret.example.com/x" not in fetcher.requests       # can't read pages outside its results
    assert llm.forced[-1] == "finish" and llm.turns == 4                  # step budget enforced
    assert [s["url"] for s in out["sources"]] == ["https://othernews.example.org/council-bus-ai"]  # invented URL dropped
    assert out["decision"] == "confirmed"
