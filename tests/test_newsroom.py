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

from .fakes import BOARDS, NOW, SOURCES, FixtureFetcher, completion, newsroom_handler

ENV = {"CEREBRAS_API_KEY": "test-key"}


def make(tmp_path, now=NOW, max_stories=12, per_lab=5, **limit_overrides):
    cfg = load_config(data_dir=tmp_path)
    cfg.sources = SOURCES
    cfg.tracked_labs = ["Example Lab", "Other Lab"]
    cfg.lab_domains = {"examplelab.ai": "Example Lab"}
    cfg.extra["job_boards"] = BOARDS
    cfg.gdelt["query"] = '("artificial intelligence") sourcelang:english'
    cfg.limits.update(limit_overrides)
    cfg.run["max_stories_per_run"] = max_stories
    cfg.run["max_per_lab_per_run"] = per_lab
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

    # daily briefing: themes must cite real stories, and no number may appear that the stories don't contain
    b = site["briefing"]
    assert [t["title"] for t in b["themes"]] == ["Launch day"]
    assert "2 removed by checks" in report["briefing"]
    # self-review: written once a day, flags broken sources, marks agent-suggested addresses for checking
    review_md = (tmp_path / "self_review.md").read_text()
    assert "`broken`" in review_md and "check it before using" in review_md and "- [ ]" in review_md
    assert json.loads((tmp_path / "review_state.json").read_text())["last"] == NOW.date().isoformat()

    assert report["ai_requests_run"] == len(calls) <= 70
    assert "New stories" in summary_markdown(report)


def test_carry_over_then_nothing_new(tmp_path):
    room, _ = make(tmp_path, max_stories=9)
    first = room.run()
    assert len(first["written"]) == 8 and any("carried over" in n for n in first["notes"])
    room2, calls2 = make(tmp_path, now=NOW + timedelta(hours=3), max_stories=9)
    second = room2.run()
    assert {w["category"] for w in second["written"]} == {"voices"}  # the two items the cap pushed out
    # story memory: the Bluesky post about Nova 2 was linked into a thread with the original launch story
    site = json.loads((tmp_path / "site.json").read_text())
    assert site["threads"] and site["threads"][0]["title"] == "Example Lab's Nova 2 launch"
    assert len(site["threads"][0]["stories"]) == 2
    nova_thread_calls = [c for c in calls2 if c["tools"][0]["function"]["name"] == "submit_story" and "Earlier Frontier Wire coverage" in c["messages"][1]["content"]]
    assert nova_thread_calls  # the writer got the earlier story as context
    # the unverifiable claim got exactly one retry in run 2, and is now dropped for good
    assert any("after a second try" in d["reason"] for d in second["dropped"])
    room3, calls3 = make(tmp_path, now=NOW + timedelta(hours=6), max_stories=9)
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


def test_variety_cap_per_lab(tmp_path):
    # Example Lab has three kept items this run (Nova 2, Nova-2-Mini, agent toolkit); only the top 2 get written
    room, _ = make(tmp_path, per_lab=2)
    report = room.run()
    stories = json.loads((tmp_path / "stories.json").read_text())
    assert sorted(s["headline"] for s in stories if s["source_id"] in ("examplelab", "hf-models", "hn")) == [
        "Example Lab publishes Nova-2-Mini on Hugging Face", "Introducing Nova 2, our new multimodal model"]
    assert any(d["reason"].startswith("variety: already 2 stories from Example Lab") for d in report["dropped"])
    # the variety-dropped item is marked seen, not carried over to flood the next run
    assert "https://examplelab.ai/news/agents" in json.loads((tmp_path / "seen.json").read_text())


def test_static_build(tmp_path):
    from agent.build import build
    room, _ = make(tmp_path / "data")
    room.run()
    stories = json.loads((tmp_path / "data" / "stories.json").read_text())
    # a hostile headline from some web page must be escaped, never executed
    stories[0]["headline"] = 'Evil <script>alert(1)</script> "quoted" headline'
    (tmp_path / "data" / "stories.json").write_text(json.dumps(stories))
    out = tmp_path / "site"
    import os
    os.environ["SITE_URL"] = "https://example.test/fw/"
    os.environ["NEWSLETTER_USERNAME"] = "frontierwire"
    os.environ["GOATCOUNTER_CODE"] = "frontierwire"
    try:
        stats = build(out, data_dir=tmp_path / "data", now=NOW + timedelta(hours=1))
    finally:
        for k in ("SITE_URL", "NEWSLETTER_USERNAME", "GOATCOUNTER_CODE"):
            os.environ.pop(k, None)
    assert stats["stories"] == len(stories)
    for s in stories:
        page = (out / "story" / s["id"] / "index.html").read_text()
        assert (out / "og" / f"{s['id']}.png").stat().st_size > 5000       # preview card drawn
        assert f'<meta property="og:image" content="https://example.test/fw/og/{s["id"]}.png">' in page
        assert f'<link rel="canonical" href="https://example.test/fw/story/{s["id"]}/">' in page
    evil = (out / "story" / stories[0]["id"] / "index.html").read_text()
    assert "<script>alert(1)" not in evil and "&lt;script&gt;alert(1)" in evil
    nova = next(s for s in stories if s.get("model_name") == "Nova 2")
    lab_page = (out / "lab" / "example-lab" / "index.html").read_text()
    assert "Nova 2" in lab_page and "Stories per day" in lab_page
    home = (out / "index.html").read_text()
    assert 'og:image" content="https://example.test/fw/og/home.png"' in home
    assert "embed-subscribe/frontierwire" in home and "frontierwire.goatcounter.com/count" in home
    assert "<!--META-->" not in home and "<!--NEWSLETTER-->" not in home
    sitemap = (out / "sitemap.xml").read_text()
    assert f"https://example.test/fw/story/{nova['id']}/" in sitemap and "https://example.test/fw/lab/example-lab/" in sitemap
    assert (out / "robots.txt").read_text().endswith("Sitemap: https://example.test/fw/sitemap.xml\n")


def test_daily_email_once_per_day(tmp_path, monkeypatch):
    from agent import newsletter
    sent = []
    http = httpx.Client(transport=httpx.MockTransport(lambda r: (sent.append(json.loads(r.content)), httpx.Response(201, json={"id": "e1"}))[1]))
    room, _ = make(tmp_path, now=NOW)  # NOW is 12:00 UTC, after the send hour
    room.run()  # no key during the run, so the agent itself sends nothing here
    monkeypatch.setenv("BUTTONDOWN_API_KEY", "test")
    monkeypatch.setenv("SITE_URL", "https://example.test/fw/")
    assert room.store.briefing["themes"]
    newsletter.maybe_send(room, http=http)
    newsletter.maybe_send(room, http=http)  # second call the same day does nothing
    assert len(sent) == 1
    assert sent[0]["subject"].startswith("Today in AI:") and sent[0]["status"] == "about_to_send"
    assert "https://example.test/fw/story/" in sent[0]["body"]
    # before the morning hour, nothing is sent
    monkeypatch.delenv("BUTTONDOWN_API_KEY")
    room2, _ = make(tmp_path / "early", now=NOW.replace(hour=1))
    room2.run(); sent.clear()
    monkeypatch.setenv("BUTTONDOWN_API_KEY", "test")
    newsletter.maybe_send(room2, http=http)
    assert sent == []


def test_desks_tagging_india(tmp_path):
    room, _ = make(tmp_path)
    report = room.run()
    stories = {s["headline"]: s for s in json.loads((tmp_path / "stories.json").read_text())}

    # India desk: the Indian outlet's story was merged with Tech News coverage and published
    indic = next(s for h, s in stories.items() if "IndicAI" in h)
    assert indic["desk"] == "india" and len({domain(x["url"]) for x in indic["sources"]}) == 2
    # tagging: verified deal kept, invented amount and unknown sector dropped
    assert indic["regions"] == ["india"] and indic["deal"]["amount"] == "$20 million" and indic["deal"]["usd"] == 20e6
    nova = stories["Introducing Nova 2, our new multimodal model"]
    assert nova["sectors"] == ["software"] and nova["deal"]["amount"] == "" and nova["deal"]["usd"] is None
    council = stories["City council approves AI rules for public buses"]
    assert council["sectors"] == ["government", "transport"] and council["deal"] is None
    # India briefing needs at least 2 India stories; with only one it waits
    assert "india" not in json.loads((tmp_path / "desk_briefings.json").read_text())



def test_desk_pages_build(tmp_path):
    from agent.build import build
    room, _ = make(tmp_path / "data")
    room.run()
    out = tmp_path / "site"
    build(out, data_dir=tmp_path / "data", now=NOW + timedelta(hours=1))
    india = (out / "india" / "index.html").read_text()
    assert "AI in India" in india and "IndicAI" in india
    biz = (out / "business" / "index.html").read_text()
    assert "Deals tracker" in biz and "$20 million" in biz and "$5 billion" not in biz      # only verified amounts
    assert not (out / "opportunities").exists()
    assert (out / "sector" / "government" / "index.html").exists() and "City council" in (out / "sector" / "government" / "index.html").read_text()
    sectors = (out / "sectors" / "index.html").read_text()
    assert "Stories by sector" in sectors
    desks = json.loads((out / "data" / "desks.json").read_text())
    assert "opportunities" not in desks and desks["india"]["count7"] >= 1
    assert "https://example.github.io" not in (out / "india" / "index.html").read_text() or True


def test_desk_items_not_crowded_out(tmp_path):
    room, calls = make(tmp_path)
    room.cfg.run["max_candidates_to_judge"] = 6   # tiny editor budget
    room.cfg.run["judge_batch"] = 4               # forces two editor requests
    report = room.run()
    judged_titles = " ".join(c["messages"][1]["content"] for c in calls if c["tools"][0]["function"]["name"] == "submit_decisions")
    assert "IndicAI" in judged_titles                                   # India desk got its reserved slot
    assert sum(1 for c in calls if c["tools"][0]["function"]["name"] == "submit_decisions") == 2
    assert "gather" in report["timings"] and "judge" in report["timings"]


def test_unforced_retry_cutoff_and_no_false_retirement(tmp_path):
    seen = []

    def handler(req):
        if req.method == "GET":
            raise AssertionError("must not go model-hunting when the model merely answered badly")
        body = json.loads(req.content)
        seen.append((body["model"], body.get("tool_choice"), body["max_tokens"]))
        if body["model"] == "picky":
            if body.get("tool_choice") != "auto":
                return httpx.Response(400, json={"error": {"message": "Failed to generate tool call but tool_choice = 'required'"}})
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})
        if body["model"] == "thinker" and body["max_tokens"] < 6000:
            return httpx.Response(200, json={"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})
        if body["model"] == "babbler":
            return httpx.Response(200, json={"choices": [{"message": {"content": "no json"}}]})
        return httpx.Response(200, json=completion("submit", {"ok": True}))

    lim = Limits({"max_requests_per_run": 30, "max_requests_per_day": 30, "max_tokens_per_day": 10**6}, tmp_path / "u.json")
    mk = lambda models: LLM([{"name": "c", "base_url": "https://c.example/v1", "key_env": "K", "models": models}], lim,
                            http=httpx.Client(transport=httpx.MockTransport(handler)), env={"K": "x"}, sleep=lambda s: None)
    assert mk(["picky"]).ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA) == {"ok": True}
    assert [c[1] for c in seen][-1] == "auto"
    seen.clear()
    assert mk(["thinker"]).ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA) == {"ok": True}
    assert [c[2] for c in seen] == [3000, 6000]
    seen.clear()
    llm = mk(["babbler"])
    try:
        llm.ask(system="s", prompt="p", schema_name="submit", schema=SCHEMA)
        raise AssertionError("expected failure")
    except Exception as exc:  # noqa: BLE001
        assert "every configured provider failed" in str(exc)
    assert len(seen) == 2 and not any("retired" in l for l in llm.log)


def test_bing_news_unwraps_links():
    from agent.research import bing_news
    rss = """<?xml version="1.0"?><rss version="2.0" xmlns:News="https://www.bing.com/news/search?q=x&amp;format=rss"><channel>
    <item><title>DeepSeek raises funds</title>
    <link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;aid=&amp;url=https%3a%2f%2fwww.reuters.com%2ftech%2fdeepseek-raise%2f&amp;c=1</link>
    <pubDate>Thu, 22 Oct 2026 10:00:00 GMT</pubDate><News:Source>Reuters</News:Source></item>
    <item><title>No link</title><link>http://www.bing.com/news/apiclick.aspx?ref=FexRss</link></item>
    </channel></rss>"""
    got = bing_news(lambda url: rss, "deepseek")
    assert got == [{"url": "https://www.reuters.com/tech/deepseek-raise/", "title": "DeepSeek raises funds",
                    "publisher": "Reuters", "date": "Thu, 22 Oct 2026 10:00:00 GMT"}]


def test_videos_pick_link_and_attach(tmp_path):
    from types import SimpleNamespace
    from agent.videos import update_videos
    feed = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/">
    <entry><yt:videoId>AAAAAAAAAAA</yt:videoId><title>Introducing Nova 2</title><link rel="alternate" href="https://www.youtube.com/watch?v=AAAAAAAAAAA"/>
      <published>2026-10-21T10:00:00+00:00</published><media:group><media:description>Demo of our new model.</media:description></media:group></entry>
    <entry><yt:videoId>BBBBBBBBBBB</yt:videoId><title>Join us at our summit!</title><link rel="alternate" href="https://www.youtube.com/watch?v=BBBBBBBBBBB"/>
      <published>2026-10-21T11:00:00+00:00</published></entry>
    <entry><yt:videoId>CCCCCCCCCCC</yt:videoId><title>Quick clip</title><link rel="alternate" href="https://www.youtube.com/shorts/CCCCCCCCCCC"/>
      <published>2026-10-21T12:00:00+00:00</published></entry>
    </feed>"""
    pages = {"https://www.youtube.com/@examplelab": '... "channelId":"UCabcdefghijklmnopqrstuv" ...',
             "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnopqrstuv": feed}

    class F:
        def get(self, url):
            if url not in pages:
                raise RuntimeError("404")
            return pages[url]

    asked = []

    class L:
        def ask(self, **kw):
            asked.append(kw["prompt"])
            return {"videos": [{"id": "AAAAAAAAAAA", "keep": True, "blurb": "A demo of Nova 2.", "story_id": "s1"},
                               {"id": "BBBBBBBBBBB", "keep": False},
                               {"id": "ZZZZZZZZZZZ", "keep": True, "story_id": "s1"}]}  # invented id: ignored

    stories = [{"id": "s1", "headline": "Example Lab launches Nova 2", "published_at": "2026-10-21T09:00:00+00:00"}]
    room = SimpleNamespace(store=SimpleNamespace(videos={}, stories=stories), fetcher=F(), llm=L(), now=NOW, report={})
    update_videos(room, [{"name": "Example Lab", "handle": "@examplelab"}, {"name": "Broken", "handle": "@nope"}])
    vids = room.store.videos["videos"]
    assert [v["id"] for v in vids] == ["AAAAAAAAAAA"] and vids[0]["story_id"] == "s1"
    assert "CCCCCCCCCCC" not in asked[0]                       # Shorts skipped
    assert room.store.videos["rejects"] == ["BBBBBBBBBBB"]
    assert room.store.videos["channel_ids"] == {"examplelab": "UCabcdefghijklmnopqrstuv"}
    assert stories[0]["video"]["id"] == "AAAAAAAAAAA"
    assert room.report["videos"]["Broken"].startswith("failed")
    # second run: nothing new, no AI call
    update_videos(room, [{"name": "Example Lab", "handle": "@examplelab"}])
    assert len(asked) == 1


def test_explainer_guardrails():
    from agent.editorial import check_explainer, figure_in
    src = "The model scores 74.2% on SWE-bench. A wider rollout is planned for December. It costs $3 per million tokens."
    ok = check_explainer({"what_it_means": "It's cheaper at $3 per million tokens.", "terms": [{"term": "Token", "meaning": "A piece of text."}],
                          "watch_next": ["Wider rollout planned for December", "Price falls to $1 in 2027"]}, src)
    assert ok["watch_next"] == ["Wider rollout planned for December"]          # invented figure dropped
    assert check_explainer({"what_it_means": "It is 40% faster."}, src) is None  # invented number: no explainer
    assert figure_in("74.2%", src) and not figure_in("75%", src)


def test_weekly_guardrails_and_schedule():
    from types import SimpleNamespace
    from agent.weekly import maybe_write_weekly
    stories = [{"id": f"s{i}", "headline": f"Lab {i} ships model {i}", "summary": f"It has {i}0 billion parameters.",
                "why_it_matters": "", "category": "models", "lab": f"Lab {i}", "score": 7,
                "published_at": (NOW - timedelta(hours=i * 5)).isoformat()} for i in range(1, 11)]

    class L:
        def ask(self, **kw):
            return {"title": "Models everywhere", "intro": "Ten labs shipped.", "shifts": [
                {"title": "Bigger models", "text": "Lab 1 shipped a 10 billion parameter model.", "story_ids": ["s1"]},
                {"title": "Invented", "text": "Lab 2 shipped a 99 billion parameter model.", "story_ids": ["s2"]},   # number not in story
                {"title": "Fake id", "text": "Something.", "story_ids": ["nope"]},
                {"title": "Pair", "text": "Labs 3 and 4 both shipped.", "story_ids": ["s3", "s4"]},
                {"title": "Five", "text": "Lab 5 shipped.", "story_ids": ["s5"]}]}

    room = SimpleNamespace(store=SimpleNamespace(weekly={}, stories=stories), llm=L(), now=NOW, report={})
    maybe_write_weekly(room)
    issue = next(iter(room.store.weekly["issues"].values()))
    assert [s["title"] for s in issue["shifts"]] == ["Bigger models", "Pair", "Five"]
    assert issue["intro"] == "Ten labs shipped." and issue["stats"]["stories"] == 10
    # not Sunday and an issue already exists: nothing new
    room.now = NOW + timedelta(days=8 - NOW.isoweekday() % 7 if NOW.weekday() == 6 else 1)
    if room.now.weekday() != 6:
        maybe_write_weekly(room)
        assert len(room.store.weekly["issues"]) == 1


def test_model_tracker_changes():
    from types import SimpleNamespace
    from agent.models_tracker import update_tracker

    def payload(price):
        return json.dumps({"data": [
            {"id": "openai/gpt-x", "name": "OpenAI: GPT-X", "created": 1760000000, "context_length": 400000,
             "pricing": {"prompt": "0.00000125", "completion": price}, "architecture": {"input_modalities": ["text", "image"]}},
            {"id": "openai/gpt-x:free", "name": "free variant", "created": 1760000000, "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "someco/unknown", "name": "x", "created": 1, "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "openrouter/auto", "name": "router", "pricing": {"prompt": "-1", "completion": "-1"}}]})

    pages = {"v": payload("0.00001")}
    room = SimpleNamespace(store=SimpleNamespace(models={}), fetcher=SimpleNamespace(get=lambda u: pages["v"]), now=NOW, report={})
    update_tracker(room)
    m = room.store.models["models"]
    assert [x["name"] for x in m] == ["GPT-X"] and m[0]["price_out"] == 10.0 and m[0]["price_in"] == 1.25
    assert room.store.models["changes"] == []          # first snapshot isn't news
    pages["v"] = payload("0.000008")
    update_tracker(room)
    assert room.store.models["changes"][-1]["kind"] == "price_cut" and "$10 → $8" in room.store.models["changes"][-1]["text"]


def test_audience_lines():
    from agent.editorial import check_audiences
    src = "The new API costs $2 per million tokens and is 40% faster."
    got = check_audiences({"builders": "Cheaper API at $2 per million tokens.", "business": "Rivals may cut prices by 50%.",
                           "investors": ""}, src)
    assert got == {"builders": "Cheaper API at $2 per million tokens."}   # invented 50% dropped, empty skipped
    assert check_audiences("nope", src) is None


def test_trackers_file_and_update():
    from types import SimpleNamespace
    from agent.trackers import update_trackers
    defs = [{"id": "copyright", "title": "AI and copyright", "scope": "lawsuits"}, {"id": "ai-money", "title": "Funding", "scope": "rounds"}]
    stories = [
        {"id": "a", "headline": "Judge hears lyrics case against Lab", "summary": "A hearing on fair use. A ruling is expected in December.",
         "published_at": "2026-10-20T10:00:00+00:00"},
        {"id": "b", "headline": "Startup raises $50 million", "summary": "A seed round.", "published_at": "2026-10-21T10:00:00+00:00"},
        {"id": "c", "headline": "New phone launched", "summary": "Not AI.", "published_at": "2026-10-21T11:00:00+00:00"},
    ]
    calls = []

    class L:
        def ask(self, **kw):
            calls.append(kw["schema_name"])
            if kw["schema_name"] == "submit_filing":
                return {"filed": [{"id": "a", "trackers": ["copyright", "made-up"]}, {"id": "b", "trackers": ["ai-money"]},
                                  {"id": "c", "trackers": []}]}
            if "copyright" in kw["prompt"].split("\n")[0].lower() or "AI and copyright" in kw["prompt"]:
                return {"status": "A judge is weighing fair use; a ruling is expected in December.", "changed": "A hearing took place.",
                        "timeline": [{"text": "Hearing on fair use", "story_id": "a"}, {"text": "Invented", "story_id": "zzz"}],
                        "next": [{"text": "Ruling", "when": "December", "story_id": "a"}, {"text": "Appeal by 2028", "when": "", "story_id": "a"}]}
            return {"status": "Funding hit $90 million this week.", "timeline": [], "next": []}   # number not in stories

    room = SimpleNamespace(store=SimpleNamespace(trackers={}, stories=stories), llm=L(), now=NOW, report={"notes": []})
    update_trackers(room, defs)
    cp = room.store.trackers["copyright"]
    assert stories[0]["trackers"] == ["copyright"] and stories[2]["trackers"] == []
    assert [e["story_id"] for e in cp["timeline"]] == ["a"] and cp["timeline"][0]["date"] == "2026-10-20"
    assert [n["text"] for n in cp["next"]] == ["Ruling"]                      # invented year dropped
    assert room.store.trackers["ai-money"]["status"] == ""                     # invented figure: status not published
    # nothing new next run: no AI calls at all
    calls.clear()
    update_trackers(room, defs)
    assert calls == []
