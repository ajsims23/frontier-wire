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


def test_latest_json_for_the_email_worker():
    base = "https://x.github.io/fw/"
    r = recap.site_view([_published()], NOW, base, "o/fw", {"s0"})[0]
    j = recap.latest_json(r, base)
    assert j["date"] == "2026-10-30" and j["gif_url"] == base + "videos/2026-10-30/teaser.gif"
    assert j["entries"][0]["url"] == base + "story/s0/" and j["entries"][1]["url"] == ""
    assert len(j["entries"]) == 5 and all(e["line"] and e["source"] for e in j["entries"])


def test_key_figure_prefers_the_number_then_the_company():
    assert recap.key_figure({"line": "Salesforce is paying $2.7 billion for Cresta", "detail": ""}) == "$2.7B"
    assert recap.key_figure({"line": "Model edits", "detail": "lifted MATH-500 from 7.9% to 48.1%"}) == "7.9%"
    assert recap.key_figure({"line": "Hackers hit 200+ organizations", "detail": ""}) == "200+"
    assert recap.key_figure({"line": "A rule change", "detail": "", "lab": "Anthropic"}) == "Anthropic"
    assert recap.key_figure({"line": "A rule change", "detail": "", "lab": "A very long organisation name"}) == ""


def test_frames_with_and_without_ai_images(tmp_path):
    from PIL import Image
    script = _published()
    for i, st in enumerate(script["stories"]):
        st["category"] = ["models", "research", "policy", "safety", "industry"][i]
    Image.new("RGB", (1024, 1024), (40, 120, 140)).save(tmp_path / "1.jpg")
    (tmp_path / "2.jpg").write_bytes(b"not an image")  # broken file: falls back to the drawn illustration
    r = recap.Renderer(script, "example.org", tmp_path)
    assert set(r.images) == {0}
    for t in (1.0, 5.5, 10.5, 15.5, 25.5, 40.5, 50.5, 57.0):
        assert r.frame(t).size == (1920, 1080)


def test_spoken_reads_shorthand_like_a_newsreader():
    assert recap.spoken("Revolut spend falls ~90% after a $15B deal & more") == \
        "Revolut spend falls about 90% after a 15 billion dollars deal and more."
    assert recap.spoken("Proofs check at 110 tokens/s") == "Proofs check at 110 tokens per second."


def test_narration_uses_say_when_given():
    script = _published()
    script["stories"][0]["say"] = "A spoken version"
    keys = [k for k, _ in recap.narration(script)]
    assert keys[0] == "hook" and keys[-1] == "outro" and len(keys) == len(script["stories"]) + 2
    assert recap.narration(script)[1][1].startswith("A spoken version. ")


def test_timing_silent_and_narrated_stay_in_bounds():
    durs, tempo = recap.timing(5, {})
    assert durs == [5.0, 10.0, 10.0, 10.0, 10.0, 10.0, 4.0] and tempo == 1.0
    short = {k: (None, 3.0) for k in ["hook", "story1", "story2", "story3", "story4", "story5", "outro"]}
    durs, tempo = recap.timing(5, short)
    assert [round(d, 3) for d in durs] == [5.0, 10.0, 10.0, 10.0, 10.0, 10.0, 4.0] and tempo == 1.0
    long = {k: (None, 5.0 if k in ("hook", "outro") else 10.0) for k in ["hook", "story1", "story2", "story3", "story4", "story5", "outro"]}
    durs, tempo = recap.timing(5, long)
    assert recap.MIN_S <= sum(durs) <= recap.MAX_S - 0.5 + 1e-6 and tempo == 1.0
    faster = {k: (None, 5.0 if k in ("hook", "outro") else 11.5) for k in long}
    durs, tempo = recap.timing(5, faster)
    assert recap.MIN_S <= sum(durs) <= recap.MAX_S - 0.5 + 1e-6 and 1.0 < tempo <= 1.3
    too_long = {k: (None, 16.0) for k in long}
    assert recap.timing(5, too_long) == ([5.0, 10.0, 10.0, 10.0, 10.0, 10.0, 4.0], 0.0)


def test_site_view_attaches_lab_videos_and_footage_credits():
    r = _published()
    r["footage_credits"] = [{"story": 1, "name": "A Person", "url": "https://www.pexels.com/video/x-1/"},
                            {"story": 2, "name": "Bad", "url": "https://evil.example/"}]
    sid = r["stories"][0]["id"]
    rows = recap.site_view([r], datetime.fromisoformat(r["published_at"]), "https://x/", "o/r", {sid},
                           {sid: {"id": "abcdefghijk", "title": "Launch", "channel": "Lab"}, "zz": {"id": "bad"}})
    assert rows[0]["entries"][0]["video"]["id"] == "abcdefghijk"
    assert rows[0]["entries"][1]["video"] is None
    assert [c["name"] for c in rows[0]["footage"]] == ["A Person"]


def test_commons_keeps_only_free_licences_and_transcodes():
    class R:
        def __init__(self, d): self.d = d
        def raise_for_status(self): pass
        def json(self): return self.d

    def page(pid, lic, h=720):
        return {"pageid": pid, "videoinfo": [{"duration": 30, "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{pid}.webm",
                "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": "<a href='x'>Jo Bloggs</a>"}},
                "derivatives": [{"src": f"https://upload.wikimedia.org/t/{pid}.{h}p.webm", "width": 1280, "height": h}]}]}

    class H:
        def get(self, *a, **k):
            return R({"query": {"pages": {"1": page(1, "CC BY 4.0"), "2": page(2, "CC BY-SA 4.0"), "3": page(3, "Public domain"),
                                          "4": page(4, "CC0", h=360)}}})

    got = recap._commons(H(), "data center")
    assert [c["id"] for c in got] == ["wc1", "wc3"]
    assert got[0]["name"] == "Jo Bloggs" and got[0]["provider"] == "Wikimedia Commons, CC BY 4.0"
