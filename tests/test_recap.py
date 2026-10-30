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
