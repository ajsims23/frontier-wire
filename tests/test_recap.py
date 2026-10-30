"""Daily recap: picking, credits and the script checks (no rendering)."""
from datetime import datetime, timedelta, timezone

from agent import recap

NOW = datetime(2026, 10, 30, 13, 10, tzinfo=timezone.utc)


def story(i, score, cat="industry", lab="", hours=2, rel="core", sources=None):
    return {"id": f"s{i}", "headline": f"Headline number {i} about something", "summary": "x", "category": cat, "lab": lab,
            "score": score, "ai_relevance": rel, "published_at": (NOW - timedelta(hours=hours)).isoformat(),
            "sources": sources or [{"url": "https://example.com/a", "publisher": "Example", "title": "t"}]}


def test_pick_window_lead_and_category_cap():
    stories = [story(1, 9, lab="A"), story(2, 9, lab="B"), story(3, 8, lab="C"), story(4, 8, lab="D"),
               story(5, 7, "safety", "E"), story(6, 7, "models", "F"), story(7, 10, lab="G", hours=30),
               story(8, 9, lab="H", rel="adjacent"), story(9, 6, "research", "I")]
    got = [s["id"] for s in recap.pick(stories, NOW)]
    assert "s7" not in got                      # older than 24 hours
    assert got[0] in {"s1", "s2"}               # lead is a core story
    assert sum(1 for s in stories if s["id"] in got and s["category"] == "industry") <= 2
    assert {"s5", "s6"} <= set(got)


def test_pick_fills_on_a_thin_day():
    stories = [story(i, 8, lab=str(i)) for i in range(4)]
    assert len(recap.pick(stories, NOW)) == 4


def test_credit_skips_aggregators():
    s = story(1, 9, sources=[{"url": "https://techmeme.com/x", "publisher": "techmeme.com", "title": "Sources: thing (Bloomberg)"},
                             {"url": "https://www.msn.com/y", "publisher": "TechCrunch on MSN", "title": "t"}])
    assert recap.credit(s) == "Bloomberg · TechCrunch"


def test_validate_catches_copied_headlines_and_lengths():
    script = {"hook": "Five things", "summary": ["a", "b", "c"], "stories": [
        {"headline": "OpenAI revises Model Spec around five core values", "source_titles": [], "source": "OpenAI",
         "line": "OpenAI revises its Model Spec around five core values", "detail": "Fine."},
        {"headline": "H", "source_titles": ["Mistral releases the weights for its big new coding model today"], "source": "Mistral",
         "line": "Big news: Mistral releases the weights for its big new coding model", "detail": "Fine."},
        {"headline": "H2", "source_titles": [], "source": "", "line": "x" * 80, "detail": "ok"}]}
    errs = recap.validate(script)
    assert any("story 1: line is too close" in e for e in errs)
    assert any("story 2: line is too close" in e for e in errs)
    assert any("story 3: line must be" in e for e in errs)
    assert any("story 3: no source" in e for e in errs)


def test_validate_passes_a_good_script():
    script = {"hook": "Chip money and open weights", "summary": ["one", "two", "three"], "stories": [
        {"headline": f"Original headline {i}", "source_titles": ["Some outlet title"], "source": "Outlet",
         "line": f"A fresh way of saying story {i}", "detail": "One fact that matters."} for i in range(3)]}
    assert recap.validate(script) == []


def _published(date="2026-10-30"):
    return {"date": date, "hook": "Chip money and open weights", "summary": ["one", "two", "three"],
            "published_at": "2026-10-30T13:10:00+00:00", "video": {"duration": 30.0, "bytes": 3_600_000},
            "stories": [{"id": f"s{i}", "category": "industry", "headline": f"Original headline {i}", "source_titles": [],
                         "source": "Outlet", "line": f"A fresh way of saying story {i}", "detail": "One fact."} for i in range(5)]}


def test_site_view_ages_out_video_then_images():
    base, repo = "https://x.github.io/fw/", "o/fw"
    live, old, older = (recap.site_view([_published()], NOW + timedelta(days=d), base, repo, {"s0"})[0] for d in (0, 4, 40))
    assert live["live"] and live["mp4"] == "videos/2026-10-30/recap.mp4" and live["label"] == "Today's"
    assert live["entries"][0]["href"] == "story/s0/" and live["entries"][1]["href"] == ""
    assert not old["live"] and old["mp4"].startswith("https://github.com/o/fw/releases/download/recap-2026-10-30/")
    assert old["poster"] and old["poster_url"] == base + "videos/2026-10-30/poster.jpg"
    assert not older["poster"] and older["poster_url"].endswith("/recap-2026-10-30/poster.jpg")


def test_feed_has_one_item_per_day_with_poster_and_link():
    import xml.dom.minidom
    rows = recap.site_view([_published("2026-10-30"), _published("2026-10-29")], NOW, "https://x.github.io/fw/", "o/fw", set())
    xml_text = recap.feed(rows, "https://x.github.io/fw/")
    doc = xml.dom.minidom.parseString(xml_text)
    items = doc.getElementsByTagName("item")
    assert len(items) == 2
    assert items[0].getElementsByTagName("link")[0].firstChild.data == "https://x.github.io/fw/videos/2026-10-30/"
    assert "poster.jpg" in items[0].getElementsByTagName("enclosure")[0].getAttribute("url")
    assert "Read on Frontier Wire" in xml_text
