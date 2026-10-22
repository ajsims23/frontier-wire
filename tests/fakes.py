"""Offline stand-ins for the web, the free data APIs and the AI providers (fictional sample content)."""
from __future__ import annotations

import json
import re
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
<item><title>Indic language model startup raises $20 million</title><link>https://technews.example.com/indic-llm-funding</link><pubDate>{H5}</pubDate><description>Bengaluru-based startup raised $20 million.</description></item>
<item><title>Example Lab launches free course on building AI agents</title><link>https://technews.example.com/agents-course</link><pubDate>{H5}</pubDate><description>A free beginner course with a certificate.</description></item>
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

NOVA_ARTICLE = """<html><head><meta property="og:image" content="/images/nova2-hero.jpg"></head><body><nav>menu</nav><article><h1>Introducing Nova 2</h1>
<p>Today we release Nova 2. “We built Nova 2 to reason across text, images and audio,” said Ada Example, CEO of Example Lab.</p>
</article></body></html>"""

BSKY_TEXT = "Big week: Nova 2 shows how far multimodal reasoning has come, and evaluation needs to catch up fast."

GDELT_SCOUT = {"articles": [
    {"url": "https://regulator.example.gov/inquiry", "title": "Regulator opens inquiry into AI hiring tools", "domain": "regulator.example.gov", "seendate": NOW.strftime("%Y%m%dT%H%M%SZ")},
    {"url": "https://technews.example.com/nova-2-launch", "title": "Example Lab launches Nova 2 multimodal model", "domain": "technews.example.com", "seendate": NOW.strftime("%Y%m%dT%H%M%SZ")},
]}

INDIA_FEED = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>India AI News</title>
<item><title>Bengaluru startup IndicAI raises $20 million to build Indic language models</title><link>https://indianews.example.in/indicai-20m</link><pubDate>{H5}</pubDate><description>IndicAI raised $20 million led by investors.</description></item>
</channel></rss>"""

JOB_BOARDS = {
    "https://boards-api.greenhouse.io/v1/boards/examplelab/jobs": {"jobs": [
        {"title": "Research Engineer, Agents", "absolute_url": "https://jobs.example.com/1", "location": {"name": "San Francisco"}, "updated_at": iso(5)},
        {"title": "Applied AI Engineer", "absolute_url": "https://jobs.example.com/2", "location": {"name": "Bengaluru, India"}, "updated_at": iso(30)},
        {"title": "Research Intern, Summer 2027", "absolute_url": "https://jobs.example.com/3", "location": {"name": "London"}, "updated_at": iso(50)}]},
    "https://api.ashbyhq.com/posting-api/job-board/otherlab": {"jobs": [
        {"title": "ML Engineer", "jobUrl": "https://jobs.example.org/a", "location": "Remote", "isRemote": True, "publishedAt": iso(8)}]},
}

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
        f'<html><head><meta property="article:published_time" content="{iso(3)}"><meta property="og:image" content="https://pagelab.example.com/static/site-logo.png"></head><body><article>Atlas update text.</article></body></html>',
    "https://pagelab.example.com/blog/old-thing":
        f'<html><head><meta property="article:published_time" content="{iso(480)}"></head><body>old</body></html>',
    "https://examplelab.ai/news/nova-2": NOVA_ARTICLE,
    "https://india.example.in/feed": INDIA_FEED,
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
    {"id": "indianews", "name": "India AI News", "kind": "rss", "url": "https://india.example.in/feed", "role": "news", "desk": "india"},
]

BOARDS = [
    {"company": "Example Lab", "platform": "greenhouse", "token": "examplelab", "lab": "Example Lab"},
    {"company": "Other Lab", "platform": "ashby", "token": "otherlab", "lab": "Other Lab"},
    {"company": "Broken Lab", "platform": "lever", "token": "brokenlab", "lab": "Broken Lab"},
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
                    {"url": "https://othernews.example.org/hiring-inquiry", "title": "Watchdog opens inquiry into AI hiring software", "domain": "othernews.example.org"}]})
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
        if url in JOB_BOARDS:
            return json.dumps(JOB_BOARDS[url])
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
    indic = next((i for i, t in cands if "IndicAI raises" in t), "")
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
        ("Atlas", dict(keep=True, score=6, category="safety", duplicate_of_story="deadbeef0000")),  # made-up id
        ("IndicAI raises", dict(keep=True, score=7, category="industry")),
        ("Indic language model startup", dict(keep=True, score=6, category="industry", same_event_as=indic)),
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


def tool_call(name: str, args: dict, n: int) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"call_{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}],
        "usage": {"total_tokens": 900}}


def research_turn(body: dict) -> dict:
    """A stand-in research agent: search with the claim's words, read the best match, then finish."""
    import re
    msgs = body["messages"]
    claim = re.search(r"<item>(.+?)\n", msgs[1]["content"]).group(1)
    words = {w for w in re.findall(r"[a-z]{4,}", claim.lower())}
    n = len(msgs)
    forced = isinstance(body.get("tool_choice"), dict)
    last = msgs[-1]
    if forced:
        return tool_call("finish", {"decision": "unconfirmed", "sources": []}, n)
    if last["role"] == "user":
        return tool_call("search_news", {"query": claim}, n)
    prev_call = msgs[-2]["tool_calls"][0]["function"]
    if prev_call["name"] == "search_news":
        for line in last["content"].splitlines():
            if len(words & set(re.findall(r"[a-z]{4,}", line.lower()))) >= 2:
                return tool_call("read_page", {"url": line.rsplit(" — ", 1)[-1]}, n)
        return tool_call("finish", {"decision": "unconfirmed", "sources": [], "note": "nothing independent"}, n)
    if prev_call["name"] == "read_page":
        url = json.loads(prev_call["arguments"])["url"]
        return tool_call("finish", {"decision": "confirmed", "sources": [url], "note": "same event"}, n)
    return tool_call("finish", {"decision": "unconfirmed", "sources": []}, n)


def newsroom_handler(calls: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if any(t["function"]["name"] == "search_news" for t in body.get("tools", [])):
            return httpx.Response(200, json=research_turn(body))
        name = body["tools"][0]["function"]["name"]
        prompt = body["messages"][1]["content"]
        data = {"submit_decisions": judge, "submit_story": story, "submit_matches": verify,
                "submit_links": links, "submit_briefing": briefing, "submit_review": review,
                "submit_tags": tags, "submit_courses": courses,
                "submit_weekly": lambda p: {"title": "A week of new models", "intro": "Labs shipped models.", "shifts": [
                    {"title": f"Shift {i}", "text": "Labs shipped new models.", "story_ids": re.findall(r'<story id="([^"]+)"', p)[i:i + 1]}
                    for i in range(4)]},
                "submit_explainer": lambda p: {"explainer": {"what_it_means": "It means more capable assistants.", "terms": [], "watch_next": []},
                                               "benchmarks": []}}[name](prompt)
        return httpx.Response(200, json=completion(name, data))
    return handler


def links(prompt: str) -> dict:
    import re
    earlier = re.findall(r'<story id="([^"]+)" date="[^"]+">([^<]+)</story>', prompt)
    new = re.findall(r'<story id="([^"]+)">([^<]+)</story>', prompt)
    nova = next((i for i, h in earlier if h.startswith("Introducing Nova 2")), "")
    out = [{"new_id": i, "follows": nova, "thread_title": "Example Lab's Nova 2 launch"} for i, t in new if "Nova" in t and nova]
    out.append({"new_id": "made-up", "follows": "also-made-up", "thread_title": "x"})  # must be ignored
    return {"links": out}


def briefing(prompt: str) -> dict:
    import re
    rows = re.findall(r'<story id="([^"]+)"[^>]*>([^<]+)</story>', prompt)
    ids = [i for i, _ in rows]
    return {"one_line": "A busy day across labs and policy.", "themes": [
        {"title": "Launch day", "text": "Example Lab shipped Nova 2.", "story_ids": ids[:2]},
        {"title": "Usage jumps", "text": "Usage rose 99% overnight.", "story_ids": ids[:1]},          # invented number
        {"title": "Ghost theme", "text": "Something happened.", "story_ids": ["not-a-real-id"]},      # no real story
    ]}


def review(prompt: str) -> dict:
    return {"suggestions": [
        {"kind": "fix_source", "target": "broken", "suggestion": "Fix or remove the broken feed.", "reason": "fails every run", "url": ""},
        {"kind": "add_source", "target": "Press", "suggestion": "Add a press feed such as https://made-up-press.ai/ for labs.", "reason": "gap", "url": ""},
        {"kind": "add_source", "target": "Some Lab", "suggestion": "Add their blog feed.", "reason": "under-covered",
         "url": "https://invented.example.com/feed.xml"},
    ]}


def tags(prompt: str) -> dict:
    import re
    out = []
    for i, text in re.findall(r'<story id="([^"]+)"[^>]*>([^<]+)</story>', prompt):
        if "IndicAI" in text:
            out.append({"id": i, "sectors": ["software"], "regions": ["india"], "deal_type": "funding", "company": "IndicAI", "amount": "$20 million"})
        elif "Nova 2" in text:
            # invented figure: not in the story, must be dropped
            out.append({"id": i, "sectors": ["software", "not-a-sector"], "regions": ["global"], "deal_type": "funding", "company": "Example Lab", "amount": "$5 billion"})
        elif "council" in text.lower():
            out.append({"id": i, "sectors": ["government", "transport"], "regions": ["us"], "deal_type": "none"})
        else:
            out.append({"id": i, "sectors": [], "regions": ["global"], "deal_type": "none"})
    return {"tags": out}


def courses(prompt: str) -> dict:
    import re
    out = []
    for i, text in re.findall(r'<item id="([^"]+)"[^>]*>([^<]+)</item>', prompt):
        is_course = "free course" in text.lower()
        out.append({"id": i, "is_course": is_course, "provider": "Example Lab", "cost": "free", "level": "beginner",
                    "description": "A free beginner course on building AI agents, with a certificate."})
    return {"items": out}
