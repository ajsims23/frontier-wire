"""Offline stand-ins for the web, the free data APIs and the AI providers (fictional sample content)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import httpx

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


def rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def iso(hours: float) -> str:
    return (NOW - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


H2, H5, OLD = rfc822(NOW - timedelta(hours=2)), rfc822(NOW - timedelta(hours=5)), rfc822(NOW - timedelta(hours=100))

LAB_FEED = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Example Lab</title>
<item><title>Introducing Nova 2, our new multimodal model</title><link>https://examplelab.ai/news/nova-2?utm_source=rss</link>
<pubDate>{H2}</pubDate><description>Nova 2 reasons across text, images and audio.</description></item>
<item><title>An old post</title><link>https://examplelab.ai/news/old</link><pubDate>{OLD}</pubDate><description>old</description></item>
</channel></rss>"""

NEWS_FEED = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Tech News</title>
<item><title>Example Lab launches Nova 2 multimodal model</title><link>https://technews.example.com/nova-2-launch</link><pubDate>{H2}</pubDate><description>Coverage.</description></item>
<item><title>City council approves AI rules for public buses</title><link>https://technews.example.com/council-ai</link><pubDate>{H5}</pubDate><description>The council voted 7-2.</description></item>
<item><title>Startup claims AGI will arrive next week</title><link>https://technews.example.com/agi-claim</link><pubDate>{H5}</pubDate><description>Bold claim.</description></item>
<item><title>10 prompts to boost your productivity</title><link>https://technews.example.com/prompts</link><pubDate>{H5}</pubDate><description>Listicle.</description></item>
</channel></rss>"""

VOICE_FEED = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Jane's blog</title>
<item><title>On scaling and what comes next</title><link>https://voiceblog.example.net/scaling</link><pubDate>{H5}</pubDate><description>Essay.</description></item>
</channel></rss>"""

ARXIV_FEED = f"""<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Looped transformers with adjustable depth</title><link href="http://arxiv.org/abs/2610.00001v1"/>
<published>{iso(10)}</published><summary>We propose a looped model.</summary></entry>
<entry><title>A minor ablation of tokenizer settings</title><link href="http://arxiv.org/abs/2610.00002v1"/>
<published>{iso(10)}</published><summary>Small study.</summary></entry>
</feed>"""

LISTING = """<html><body><a href="/blog/atlas-update">Atlas robotics safety update</a>
<a href="/blog/old-thing">An older announcement post</a><a href="/about">About</a></body></html>"""

NOVA_ARTICLE = """<html><body><nav>menu</nav><article><h1>Introducing Nova 2</h1>
<p>Today we release Nova 2. “We built Nova 2 to reason across text, images and audio,” said Ada Example, CEO of Example Lab.</p>
</article></body></html>"""

BSKY_TEXT = "Big week: Nova 2 shows how far multimodal reasoning has come, and evaluation needs to catch up fast."

GDELT_SCOUT = {"articles": [
    {"url": "https://regulator.example.gov/inquiry", "title": "Regulator opens inquiry into AI hiring tools", "domain": "regulator.example.gov", "seendate": NOW.strftime("%Y%m%dT%H%M%SZ")},
    {"url": "https://technews.example.com/nova-2-launch", "title": "Example Lab launches Nova 2 multimodal model", "domain": "technews.example.com", "seendate": NOW.strftime("%Y%m%dT%H%M%SZ")},
]}

JSON_PAGES = {
    "hn": {"hits": [
        {"title": "Example Lab ships an agent toolkit", "url": "https://examplelab.ai/news/agents", "points": 340, "created_at": iso(4)},
        {"title": "Ask HN: favourite editor?", "url": None, "points": 500, "created_at": iso(4)},
    ]},
    "hf_models": [
        {"id": "exampleorg/Nova-2-Mini", "createdAt": iso(6), "likes": 120, "pipeline_tag": "image-text-to-text"},
        {"id": "exampleorg/Nova-2-Mini-GGUF", "createdAt": iso(6), "likes": 3},
    ],
    "hf_papers": [
        {"paper": {"id": "2610.00001", "title": "Looped transformers with adjustable depth", "upvotes": 80, "summary": "Looped."}, "publishedAt": iso(9)},
        {"paper": {"id": "2610.00099", "title": "Low-interest paper", "upvotes": 2, "summary": "x"}, "publishedAt": iso(9)},
    ],
    "bsky_jane": {"feed": [
        {"post": {"uri": "at://did:plc:jane/app.bsky.feed.post/3abc", "author": {"handle": "jane.example.social"},
                  "record": {"text": BSKY_TEXT, "createdAt": iso(3)}}},
        {"post": {"uri": "at://did:plc:x/app.bsky.feed.post/9zzz", "author": {"handle": "someone.else"},
                  "record": {"text": "A repost of someone else's long thoughts about AI that should be skipped.", "createdAt": iso(3)}},
         "reason": {"$type": "app.bsky.feed.defs#reasonRepost"}},
        {"post": {"uri": "at://did:plc:jane/app.bsky.feed.post/3abd", "author": {"handle": "jane.example.social"},
                  "record": {"text": "lol", "createdAt": iso(3)}}},
    ]},
}

PAGES = {
    "https://examplelab.ai/feed.xml": LAB_FEED,
    "https://technews.example.com/feed": NEWS_FEED,
    "https://voiceblog.example.net/feed": VOICE_FEED,
    "https://pagelab.example.com/blog": LISTING,
    "https://pagelab.example.com/blog/atlas-update":
        f'<html><head><meta property="article:published_time" content="{iso(3)}"></head><body><article>Atlas update text.</article></body></html>',
    "https://pagelab.example.com/blog/old-thing":
        f'<html><head><meta property="article:published_time" content="{iso(480)}"></head><body>old</body></html>',
    "https://examplelab.ai/news/nova-2": NOVA_ARTICLE,
}

SOURCES = [
    {"id": "examplelab", "name": "Example Lab", "kind": "rss", "url": "https://examplelab.ai/feed.xml", "role": "lab", "lab": "Example Lab"},
    {"id": "pagelab", "name": "Page Lab", "kind": "page", "url": "https://pagelab.example.com/blog",
     "link_pattern": r"^https://pagelab\.example\.com/blog/[a-z0-9-]+$", "role": "lab", "lab": "Page Lab"},
    {"id": "hf-models", "name": "HF models", "kind": "hf_models", "role": "lab", "orgs": {"exampleorg": "Example Lab"}},
    {"id": "arxiv", "name": "arXiv", "kind": "arxiv", "query": "cat:cs.AI", "max_results": 5, "role": "paper"},
    {"id": "hf-papers", "name": "HF papers", "kind": "hf_papers", "min_upvotes": 15, "role": "paper"},
    {"id": "gdelt", "name": "GDELT", "kind": "gdelt", "role": "news"},
    {"id": "hn", "name": "Hacker News", "kind": "hn", "role": "news", "queries": ["AI"]},
    {"id": "technews", "name": "Tech News", "kind": "rss", "url": "https://technews.example.com/feed", "role": "news"},
    {"id": "jane", "name": "Jane's blog", "kind": "rss", "url": "https://voiceblog.example.net/feed", "role": "voice", "person": "Jane Doe"},
    {"id": "bluesky", "name": "Bluesky", "kind": "bluesky", "role": "voice",
     "accounts": {"jane.example.social": "Jane Doe", "missing.example.social": "Nobody"}},
    {"id": "broken", "name": "Broken feed", "kind": "rss", "url": "https://broken.example.com/feed", "role": "news"},
]


class FixtureFetcher:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def get(self, url: str) -> str:
        self.requests.append(url)
        if url.startswith("http://export.arxiv.org/api/query"):
            return ARXIV_FEED
        if url.startswith("https://api.gdeltproject.org"):
            q = unquote(url)
            if "artificial intelligence" in q:
                return json.dumps(GDELT_SCOUT)
            if "council" in q.lower():
                return json.dumps({"articles": [
                    {"url": "https://othernews.example.org/council-bus-ai", "title": "Council passes AI rules for city buses", "domain": "othernews.example.org"},
                    {"url": "https://sports.example.org/match", "title": "Local team wins", "domain": "sports.example.org"}]})
            if "inquiry" in q.lower() or "regulator" in q.lower():
                return json.dumps({"articles": [
                    {"url": "https://othernews.example.org/hiring-inquiry", "title": "Watchdog probes AI hiring software", "domain": "othernews.example.org"}]})
            if "agi" in q.lower():
                return json.dumps({"articles": [
                    {"url": "https://unrelated.example.org/a", "title": "Weather update", "domain": "unrelated.example.org"}]})
            return json.dumps({"articles": []})
        if url.startswith("https://hn.algolia.com"):
            return json.dumps(JSON_PAGES["hn"])
        if url.startswith("https://huggingface.co/api/models"):
            return json.dumps(JSON_PAGES["hf_models"])
        if url.startswith("https://huggingface.co/api/daily_papers"):
            return json.dumps(JSON_PAGES["hf_papers"])
        if url.startswith("https://public.api.bsky.app"):
            if "jane.example.social" in url:
                return json.dumps(JSON_PAGES["bsky_jane"])
            raise ConnectionError("400 profile not found")
        if url in PAGES:
            return PAGES[url]
        raise ConnectionError(f"no fixture for {url}")


# ------------------------------------------------------------------ fake AI provider (chat-completions format)
def completion(name: str, data: dict, tokens: int = 1500) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": name, "arguments": json.dumps(data)}}]}}],
        "usage": {"total_tokens": tokens}}


def judge(prompt: str) -> dict:
    import re
    cands = re.findall(r'<item id="([^"]+)"[^>]*><title>([^<]+)</title>', prompt)
    nova_lab = next((i for i, t in cands if t.startswith("Introducing Nova 2")), "")
    rules = [
        ("Introducing Nova 2", dict(keep=True, score=9, category="models")),
        ("launches Nova 2", dict(keep=True, score=8, category="models", same_event_as=nova_lab)),
        ("Nova-2-Mini", dict(keep=True, score=7, category="models")),
        ("agent toolkit", dict(keep=True, score=7, category="industry")),
        ("City council", dict(keep=True, score=7, category="policy")),
        ("AGI", dict(keep=True, score=6, category="industry")),
        ("prompts", dict(keep=False, score=2, category="industry")),
        ("scaling", dict(keep=True, score=6, category="voices")),
        ("Jane Doe:", dict(keep=True, score=6, category="voices")),
        ("Looped", dict(keep=True, score=7, category="research")),
        ("ablation", dict(keep=False, score=3, category="research")),
        ("Atlas", dict(keep=True, score=6, category="safety")),
        ("Regulator", dict(keep=True, score=7, category="policy")),
    ]
    out = []
    for cid, title in cands:
        for key, d in rules:
            if key in title:
                out.append({"id": cid, "reason": "test", "duplicate_of_story": "", "same_event_as": "", **d})
                break
    return {"decisions": out}


def story(prompt: str) -> dict:
    import re
    item = re.search(r"Item: (.+)", prompt).group(1)
    base = {"headline": item[:90], "summary": f"Summary of {item}.", "why_it_matters": "It matters.",
            "category": re.search(r"Suggested category: (\w+)", prompt).group(1), "quotes": [], "tags": [],
            "lab": "", "model_name": "", "model_type": ""}
    if item.startswith("Introducing Nova 2"):
        base.update(lab="Example Lab", model_name="Nova 2", model_type="Multimodal", quotes=[
            {"text": "We built Nova 2 to reason across  text, images and audio", "speaker": "Ada Example",
             "speaker_role": "CEO, Example Lab", "source_url": "https://examplelab.ai/news/nova-2"},
            {"text": "Nova 2 is the best model anyone has ever made", "speaker": "Ada Example",
             "speaker_role": "CEO, Example Lab", "source_url": "https://examplelab.ai/news/nova-2"},
        ])
    if item.startswith("Example Lab publishes Nova-2-Mini"):
        base.update(lab="Example Lab", model_name="Nova-2-Mini", model_type="Vision-language")
    if item.startswith("Jane Doe:"):
        base["quotes"] = [{"text": "evaluation needs to catch up fast", "speaker": "Jane Doe", "speaker_role": "Researcher",
                           "source_url": "https://bsky.app/profile/jane.example.social/post/3abc"}]
    return base


def verify(prompt: str) -> dict:
    if "City council" in prompt or "Regulator" in prompt:
        return {"matches": [0]}
    return {"matches": [99]}  # out of range — must be ignored


def newsroom_handler(calls: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        name = body["tools"][0]["function"]["name"]
        prompt = body["messages"][1]["content"]
        data = {"submit_decisions": judge, "submit_story": story, "submit_matches": verify}[name](prompt)
        return httpx.Response(200, json=completion(name, data))
    return handler
