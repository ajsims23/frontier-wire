"""Builders desk and Top Voices: sources, guardrails and schedule (offline fixtures)."""
import io
import json
from datetime import timedelta

import httpx
from types import SimpleNamespace
from urllib.parse import unquote

from agent import builders, top_voices
from agent.sources import Gdelt, Item
from agent.text import canonical_url, stable_id

from .fakes import NOW, iso

SHOW_HN = {"hits": [
    {"objectID": "101", "title": "Show HN: PDFChat – chat with a folder of PDFs, fully local", "url": "https://pdfchat.example.dev",
     "points": 210, "num_comments": 64, "created_at": iso(6), "story_text": "Runs on a laptop with a 7B model. Open source."},
    {"objectID": "102", "title": "Show HN: AgentBench Lite", "url": "", "points": 40, "num_comments": 9, "created_at": iso(10),
     "story_text": "A tiny harness to compare agent frameworks on 12 tasks."},
]}
GITHUB = {"items": [
    {"name": "tinyrag", "full_name": "ana/tinyrag", "html_url": "https://github.com/ana/tinyrag", "description": "RAG in 200 lines",
     "stargazers_count": 1840, "created_at": iso(100), "language": "Python", "topics": ["rag", "llm"], "owner": {"login": "ana"}, "fork": False},
    {"name": "tinyrag-copy", "full_name": "bob/tinyrag", "html_url": "https://github.com/bob/tinyrag", "description": "fork",
     "stargazers_count": 90, "created_at": iso(50), "topics": [], "owner": {"login": "bob"}, "fork": True},
]}
SPACES = [
    {"id": "lab/voice-clone-demo", "likes": 900, "trendingScore": 300, "tags": ["gradio"], "createdAt": iso(200)},
    {"id": "someone/Model-UNCENSORED", "likes": 400, "trendingScore": 250, "tags": ["gradio"], "createdAt": iso(200)},
]
SPACE_CARD = {"cardData": {"title": "Voice Clone Demo", "short_description": "Clone a voice from 10 seconds of audio"}}
PH = f"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>PH</title>
<entry><id>1</id><title>MeetNotes</title><link rel="alternate" href="https://www.producthunt.com/products/meetnotes"/>
<published>{iso(5)}</published><content type="html">&lt;p&gt;AI meeting notes that file themselves&lt;/p&gt;&lt;p&gt;Discussion | Link&lt;/p&gt;</content></entry>
<entry><id>2</id><title>Old launch</title><link rel="alternate" href="https://www.producthunt.com/products/old"/>
<published>{iso(200)}</published><content type="html">old</content></entry></feed>"""

BUILD_SOURCES = [
    {"id": "show-hn", "kind": "show_hn", "queries": ["AI"], "min_points": 15},
    {"id": "github-new", "kind": "github", "topics": ["llm"], "min_stars": 50},
    {"id": "hf-spaces", "kind": "hf_spaces", "limit": 25, "details": 10},
    {"id": "product-hunt", "kind": "feed", "name": "Product Hunt", "url": "https://ph.example/feed", "signal": "launched on Product Hunt"},
    {"id": "r-localllama", "kind": "feed", "name": "r/LocalLLaMA", "url": "https://reddit.example/top.rss"},
]


class Fetcher:
    def __init__(self, pages):
        self.pages, self.requests = pages, []

    def get(self, url):
        self.requests.append(url)
        for prefix, body in self.pages.items():
            if url.startswith(prefix):
                return body(url) if callable(body) else body
        raise ConnectionError(f"no fixture for {url}")


def build_fetcher():
    return Fetcher({
        "https://hn.algolia.com": json.dumps(SHOW_HN),
        "https://api.github.com/search": json.dumps(GITHUB),
        "https://huggingface.co/api/spaces/": json.dumps(SPACE_CARD),
        "https://huggingface.co/api/spaces?": json.dumps(SPACES),
        "https://ph.example/feed": PH,
    })


def png(w=800, h=420):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 120, 110)).save(buf, "PNG")
    return buf.getvalue()


def image_http(seen):
    def handler(req):
        seen.append(str(req.url))
        if "blocked" in str(req.url):
            return httpx.Response(403)
        return httpx.Response(200, content=png())
    return httpx.Client(transport=httpx.MockTransport(handler))


class LLM:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def ask(self, **kw):
        self.prompts.append(kw["prompt"])
        return self.answer(kw["prompt"]) if callable(self.answer) else self.answer


def cid(url):
    return stable_id(canonical_url(url))


def test_builders_desk_picks_checks_and_rotates(tmp_path):
    pdf, bench, rag = cid("https://pdfchat.example.dev"), cid("https://news.ycombinator.com/item?id=102"), cid("https://github.com/ana/tinyrag")
    voice, meet = cid("https://huggingface.co/spaces/lab/voice-clone-demo"), cid("https://www.producthunt.com/products/meetnotes")
    llm = LLM({"intro": "Local tools and voice demos lead today.", "picks": [
        {"id": pdf, "name": "PDFChat", "what": "Chat with a folder of PDFs on your laptop.", "why": "Runs a 7B model locally.", "kind": "app", "for": "builders"},
        {"id": rag, "name": "tinyrag", "what": "RAG in 200 lines of Python.", "why": "1,840 stars in days.", "kind": "open-source"},
        {"id": voice, "name": "Voice Clone Demo", "what": "Clones a voice from 10 seconds of audio.", "why": "A striking demo.", "kind": "demo"},
        {"id": meet, "name": "MeetNotes", "what": "Meeting notes that file themselves.", "why": "Used by 50,000 teams.", "kind": "app"},  # invented number
        {"id": "made-up", "name": "Ghost", "what": "x", "why": "y"},
        {"id": pdf, "name": "PDFChat again", "what": "dup", "why": "dup"},
        {"id": bench, "name": "AgentBench Lite", "what": "Compares agent frameworks on 12 tasks.", "why": "Handy before picking one.", "kind": "tool"},
    ]})
    store = SimpleNamespace(builders={}, dir=tmp_path)
    fetcher = build_fetcher()
    fetcher.pages["https://pdfchat.example.dev"] = ('<html><head><meta property="og:image" content="/shot.png"></head>'
                                                    '<body><iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe></body></html>')
    fetcher.pages["https://www.producthunt.com/products/meetnotes"] = '<meta property="og:image" content="https://blocked.example/x.png">'
    fetcher.pages["https://api.microlink.io"] = json.dumps({"data": {"screenshot": {"url": "https://shots.example/page.png"}}})
    images: list[str] = []
    room = SimpleNamespace(store=store, llm=llm, now=NOW, report={}, fetcher=fetcher, photo_http=image_http(images),
                           cfg=SimpleNamespace(extra={"builders": BUILD_SOURCES}))
    builders.update_builders(room)

    status = room.report["builders_sources"]
    assert status["r-localllama"].startswith("failed") and status["show-hn"] == "ok (2)"
    prompt = llm.prompts[0]
    assert "UNCENSORED" not in prompt and "Old launch" not in prompt and "fork" not in prompt  # spam, stale, forks out
    assert "Clone a voice from 10 seconds of audio" in prompt  # the Space card was read for its description
    assert "AI meeting notes that file themselves" in prompt and "Discussion | Link" not in prompt
    picks = store.builders["picks"]
    assert [p["name"] for p in picks] == ["PDFChat", "tinyrag", "Voice Clone Demo", "AgentBench Lite"]
    assert picks[0]["discussion"] == "https://news.ycombinator.com/item?id=101" and picks[1]["kind"] == "open-source"
    assert "3 removed by checks" in room.report["builders"]
    site = builders.site_builders(store.builders)
    assert len(site["picks"]) == 4 and site["intro"].startswith("Local tools")
    # pictures: the page's preview image, GitHub's own social card; videos: a YouTube demo embedded on the page
    by = {p["name"]: p for p in picks}
    assert by["PDFChat"]["video"] == "dQw4w9WgXcQ" and by["PDFChat"]["image"] == f"img/builders/{pdf}.jpg"
    assert "https://pdfchat.example.dev/shot.png" in images
    assert any(u.startswith("https://opengraph.githubassets.com/1/ana/tinyrag") for u in images) and by["tinyrag"]["image"]
    assert (tmp_path / "img" / "builders" / f"{pdf}.jpg").exists()
    assert "with pictures" in room.report["builders"] and site["picks"][0]["video"] == "dQw4w9WgXcQ"
    # no preview image on the page: a screenshot instead; never a screenshot of a Hacker News thread
    assert by["Voice Clone Demo"]["image"] and "https://shots.example/page.png" in images
    assert not by["AgentBench Lite"].get("image")
    assert not any("microlink" in u and "ycombinator" in unquote(u) for u in room.fetcher.requests)

    # not due again the same day; the next day, already-featured builds aren't offered again
    room.now = NOW + timedelta(hours=5)
    builders.update_builders(room)
    assert len(llm.prompts) == 1
    room.now = NOW + timedelta(days=1)
    builders.update_builders(room)
    assert "waiting" in room.report["builders"]  # only 1 unfeatured candidate left (MeetNotes)
    assert len(llm.prompts) == 1


ARTICLE = """<html><body><article><h1>Altman weighs in on compute</h1>
<p>OpenAI chief Sam Altman posted on X on Tuesday that the company would double its compute by 2027.
He did not give details. Other news followed.</p><p>Elsewhere, a robot learned to fold laundry.</p></article></body></html>"""


def voices_room(answer, tmp_path=None):
    pool = [
        Item(url="https://bsky.app/profile/jane.example.social/post/1", title="Jane Doe: scaling", source_id="bluesky",
             source_name="Jane Doe on Bluesky", role="voice", person="Jane Doe", published=iso(5),
             text="Scaling alone won't get us to reliable agents; we need better evals."),
        Item(url="https://kim.example.net/post", title="Why evals matter", source_id="kim", source_name="Kim's blog",
             role="voice", person="Kim Lee", published=iso(30), snippet="Benchmarks are saturated; we need harder evals."),
        Item(url="https://technews.example.com/x", title="News", source_id="t", source_name="Tech", role="news", published=iso(2)),
    ]
    feed = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Ed</title>
<item><title>Compute is the moat</title><link>https://ed.example.org/moat</link><pubDate>{NOW.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
<description>Whoever has the most compute wins the next two years.</description></item></channel></rss>"""
    gdelt_rows = {"articles": [{"url": "https://outlet.example.com/altman-x", "title": "Altman says OpenAI will double compute",
                                "domain": "outlet.example.com", "seendate": NOW.strftime("%Y%m%dT%H%M%SZ")}]}
    fetcher = Fetcher({
        "https://ed.example.org/feed": feed,
        "https://api.gdeltproject.org": json.dumps(gdelt_rows),
        "https://outlet.example.com/altman-x": ARTICLE,
        "https://ed.example.org/moat": '<meta property="og:image" content="https://ed.example.org/cover.png"><a href="https://youtu.be/abcdefghijk">talk</a>',
        "https://en.wikipedia.org/api/rest_v1/page/summary/Sam_Altman": json.dumps(
            {"type": "standard", "thumbnail": {"source": "https://upload.wikimedia.org/altman.jpg"}}),
        "https://en.wikipedia.org/api/rest_v1/page/summary/Ed_Park": json.dumps(
            {"type": "standard", "thumbnail": {"source": "https://upload.wikimedia.org/wrong-ed-park.jpg"}}),
        "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile": json.dumps({"avatar": "https://cdn.bsky.app/jane.jpg"}),
        "https://hn.algolia.com": lambda u: json.dumps({"hits": [
            {"objectID": "9", "title": "Sam Altman: The road ahead", "url": "https://blog.example/road", "points": 400,
             "num_comments": 300, "created_at": iso(20)}]} if "Sam%20Altman" in u or "Sam+Altman" in u else {"hits": []}),
    })
    cfg = {"people": [{"name": "Sam Altman", "role": "OpenAI CEO"}, {"name": "Elon Musk", "role": "xAI"}],
           "feeds": [{"id": "tv-ed", "name": "Ed's notes", "person": "Ed Park", "url": "https://ed.example.org/feed"},
                     {"id": "tv-broken", "name": "Broken", "person": "Nobody", "url": "https://broken.example/feed"}]}
    images: list[str] = []
    return SimpleNamespace(store=SimpleNamespace(top_voices={}, dir=tmp_path), llm=LLM(answer), now=NOW, report={"notes": []},
                           fetcher=fetcher, gdelt=Gdelt(fetcher, sleep=lambda s: None), _pool=pool, photo_http=image_http(images),
                           images=images, cfg=SimpleNamespace(extra={"top_voices": cfg}, sources=[
                               {"kind": "bluesky", "accounts": {"jane.example.social": "Jane Doe"}}]))


def test_top_voices_sources_attribution_and_checks(tmp_path):
    jane, kim = cid("https://bsky.app/profile/jane.example.social/post/1"), cid("https://kim.example.net/post")
    ed, altman_x = cid("https://ed.example.org/moat"), cid("https://outlet.example.com/altman-x")
    hn = cid("https://news.ycombinator.com/item?id=9")

    def answer(prompt):
        return {"headline": "Evals and compute dominate the week.", "debates": [
            {"title": "Are evals keeping up?", "summary": "Researchers say benchmarks are saturated.", "positions": [
                {"person": "Jane Doe", "stance": "Scaling alone won't make agents reliable without better evals.", "post_ids": [jane]},
                {"person": "Kim Lee", "stance": "Benchmarks are saturated.", "post_ids": [kim]},
                {"person": "Sam Altman", "stance": "Evals are fine.", "post_ids": [jane]}]},   # wrong person for that post
            {"title": "Is compute the moat?", "summary": "Two views on compute.", "positions": [
                {"person": "Ed Park", "stance": "The most compute wins the next two years.", "post_ids": [ed]},
                {"person": "Sam Altman", "stance": "OpenAI will double its compute by 2027.", "post_ids": [altman_x]}]},
            {"title": "Made-up numbers", "summary": "Labs spent $9 trillion.", "positions": [
                {"person": "Ed Park", "stance": "Spend more.", "post_ids": [ed]}]},
        ], "standouts": [{"post_id": hn, "why": "A long essay readers argued over."}, {"post_id": "nope", "why": "x"}]}

    room = voices_room(answer, tmp_path)
    top_voices.update_top_voices(room)
    st = room.report["top_voices_sources"]
    assert st["tv-ed"] == "ok (1)" and st["tv-broken"].startswith("failed") and st["x-coverage"].startswith("ok (1")
    assert any("on X" in unquote(u) for u in room.fetcher.requests if "gdelt" in u)  # X coverage via news reports, not X
    posts = room.store.top_voices["posts"]
    reported = next(p for p in posts.values() if p["kind"] == "reported")
    assert reported["person"] == "Sam Altman" and reported["via"] == "outlet.example.com" and "posted on X" in reported["text"]
    assert "laundry" not in reported["text"]  # only the sentences about the post
    assert not any(p["url"].startswith("https://technews") for p in posts.values())  # news items aren't voices
    assert 'reported="true"' in room.llm.prompts[0]

    d = room.store.top_voices["digest"]
    assert [x["title"] for x in d["debates"]] == ["Are evals keeping up?", "Is compute the moat?"]
    assert [p["person"] for p in d["debates"][0]["positions"]] == ["Jane Doe", "Kim Lee"]  # misattribution dropped
    assert d["debates"][1]["positions"][1]["posts"][0]["via"] == "outlet.example.com"
    assert [s["url"] for s in d["standouts"]] == ["https://news.ycombinator.com/item?id=9"]
    assert "removed by checks" in room.report["top_voices"]
    site = top_voices.site_top_voices(room.store.top_voices)
    assert [p["name"] for p in site["debates"][1]["people"]] == ["Ed Park", "Sam Altman"]
    # portraits: Bluesky avatar for people we follow there, Wikipedia only for the curated list (never a look-alike)
    assert d["portraits"]["Jane Doe"] == "img/people/jane-doe.jpg" and "https://cdn.bsky.app/jane.jpg" in room.images
    assert d["portraits"]["Sam Altman"] == "img/people/sam-altman.jpg"
    assert "Ed Park" not in d["portraits"] and not any("wrong-ed-park" in u for u in room.images)
    assert set(d["portrait_credits"]) == {"Bluesky", "Wikimedia Commons"}
    # the compute debate gets the blog post's picture and its linked video
    assert d["debates"][1]["image"] == f"img/voices/{ed}.jpg" and d["debates"][1]["video"] == "abcdefghijk"
    assert site["debates"][1]["people"][1]["photo"] == "img/people/sam-altman.jpg"

    # same day: posts keep collecting from the newsroom, but no new digest or extra fetching
    n = len(room.fetcher.requests)
    room.now = NOW + timedelta(hours=3)
    top_voices.update_top_voices(room)
    assert len(room.llm.prompts) == 1 and len(room.fetcher.requests) == n


def test_top_voices_waits_for_enough_people(tmp_path):
    room = voices_room({"headline": "", "debates": [], "standouts": []}, tmp_path)
    room._pool = room._pool[:1]
    room.cfg.extra["top_voices"] = {}
    top_voices.update_top_voices(room)
    assert room.report["top_voices"].startswith("waiting") and not room.llm.prompts


def test_builders_and_voices_pages_build(tmp_path):
    from agent.build import build
    from .test_newsroom import make
    room, _ = make(tmp_path / "data")
    room.run()
    evil = '<script>alert(1)</script>'
    pick = {"id": "b1", "name": f"Evil {evil}", "what": "Does a thing.", "why": "Neat.", "kind": "tool", "for": "builders",
            "url": "javascript:alert(1)", "discussion": "", "source": "Show HN", "signal": "40 points", "maker": "ana"}
    (tmp_path / "data" / "builders.json").write_text(json.dumps({
        "written_at": NOW.isoformat(), "intro": "Today's builds.", "picks": [pick], "from_candidates": 30,
        "featured": {"x": NOW.isoformat()}, "history": {"2026-10-20": [dict(pick, name="Older pick", url="https://old.example")],
                                                         NOW.date().isoformat(): [pick]}}))
    (tmp_path / "data" / "top_voices.json").write_text(json.dumps({"digest": {
        "written_at": NOW.isoformat(), "range": "14 – 21 Oct 2026", "headline": "Evals and compute",
        "debates": [{"title": "Is compute the moat?", "summary": "Two views.", "positions": [
            {"person": "Sam Altman", "stance": f"More compute {evil}.", "posts": [
                {"url": "https://outlet.example.com/a", "via": "outlet.example.com", "kind": "reported", "date": "2026-10-20"}]}]}],
        "standouts": [], "people": ["Sam Altman"], "from_posts": 12, "reported": 1}}))
    out = tmp_path / "site"
    build(out, data_dir=tmp_path / "data", now=NOW + timedelta(hours=1))
    bp = (out / "builders" / "index.html").read_text()
    assert "Today&#39;s picks" in bp or "Today's picks" in bp
    assert "<script>alert(1)" not in bp and "Older pick" in bp and "Show HN" in bp
    vp = (out / "voices" / "index.html").read_text()
    assert 'class="face initials"' in vp and ">SA<" in vp  # no portrait saved: initials instead
    assert "Is compute the moat?" in vp and "Reported by outlet.example.com" in vp and "<script>alert(1)" not in vp
    assert "Dario Amodei" in vp  # who we follow, from the sources file
    assert "javascript:" not in bp
    assert '../../builders/' in (out / "story" / room.report["written"][0]["id"] / "index.html").read_text()  # in the nav


def test_news_search_falls_back_to_bing():
    from agent.sources import news_search
    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>Bing</title>
<item><title>Altman says compute will double</title><pubDate>Wed, 21 Oct 2026 08:00:00 GMT</pubDate>
<link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fnews.example.com%2faltman&amp;c=1</link></item>
<item><title>Altman compute plan, from last month</title><pubDate>Fri, 18 Sep 2026 08:00:00 GMT</pubDate>
<link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fnews.example.com%2fold&amp;c=1</link></item>
<item><title>Altman compute, no date</title>
<link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;url=https%3a%2f%2fnews.example.com%2fundated&amp;c=1</link></item>
</channel></rss>"""

    def gdelt_down(url):
        raise ConnectionError("The handshake operation timed out")
    f = Fetcher({"https://api.gdeltproject.org": gdelt_down, "https://www.bing.com/news/search": rss})
    rows, engine = news_search(Gdelt(f, sleep=lambda s: None), f, "Altman compute", now=NOW)
    assert engine == "bing" and rows[0]["url"] == "https://news.example.com/altman" and rows[0]["domain"] == "news.example.com"
    assert [r["url"] for r in rows] == ["https://news.example.com/altman"]  # Bing's old and undated results are cut


def test_editor_searches_skip_old_articles():
    """Bing ignores time windows; the editor-in-chief's searches must not bring months-old news into a run."""
    from types import SimpleNamespace
    from agent.chief import run_searches
    rows = [{"url": "https://news.example.com/today", "title": "AI lab raises $1B", "domain": "news.example.com",
             "published": (NOW - timedelta(hours=5)).isoformat()},
            {"url": "https://news.example.com/march", "title": "AI lab launches agent tool", "domain": "news.example.com",
             "published": "2026-03-09T17:00:00+00:00"},
            {"url": "https://news.example.com/nodate", "title": "AI lab update", "domain": "news.example.com", "published": None}]

    class G:
        def search(self, *a, **k):
            return rows
    room = SimpleNamespace(gdelt=G(), fetcher=None, now=NOW, report={"notes": []},
                           cfg=SimpleNamespace(run={"lookback_hours": 36}),
                           store=SimpleNamespace(is_seen=lambda u: False))
    plan = {"searches": [{"query": "AI lab funding"}]}
    found = run_searches(room, plan, set())
    assert [it.url for it in found] == ["https://news.example.com/today"] and plan["searches"][0]["found"] == 1


def test_x_coverage_bing_fallback_per_person(tmp_path):
    rss = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>Bing</title>
<item><title>Altman says compute will double</title><link>https://outlet.example.com/altman-x</link>
<pubDate>{NOW.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item></channel></rss>"""
    room = voices_room({}, tmp_path)
    room.fetcher.pages["https://api.gdeltproject.org"] = lambda u: (_ for _ in ()).throw(ConnectionError("timed out"))
    room.fetcher.pages["https://www.bing.com/news/search"] = lambda u: rss if "Sam+Altman" in u else "<rss><channel></channel></rss>"
    out, status = top_voices.from_x_coverage(room, room.cfg.extra["top_voices"]["people"])
    assert status.endswith("bing)") and [p["person"] for p in out] == ["Sam Altman"] and out[0]["kind"] == "reported"
