"""The DPA lens, the fact-check audit, the task bench and the System numbers (offline, with a stand-in model)."""
import json
import shutil
from datetime import timedelta
from pathlib import Path

from agent import bench, dpa, factcheck
from agent.config import ROOT, load_config
from agent.llm import Limits
from agent.text import duplicate_ids, near_duplicate

from .fakes import NOW


def story(i, headline, summary, hours, score=7, lab="", url=None):
    return {"id": f"s{i}", "headline": headline, "summary": summary, "why_it_matters": "", "category": "models",
            "lab": lab, "score": score, "url": url or f"https://example.com/{i}", "source_id": "openai",
            "sources": [{"url": url or f"https://example.com/{i}", "publisher": "Example", "title": headline}],
            "published_at": (NOW - timedelta(hours=hours)).isoformat(), "created_at": (NOW - timedelta(hours=hours - 1)).isoformat()}


STORIES = [
    story(1, "Example Lab releases DocParse 2 for PDF table extraction", "DocParse 2 is open source and reads scanned PDFs.", 30, lab="Example Lab"),
    story(2, "Startup raises $40 million for AI chips", "The round was led by Example Capital.", 20, score=6),
    story(3, "Regulator publishes rules on AI use of customer data", "Firms must log AI decisions from March.", 50),
    story(4, "Example Lab releases DocParse 2 for PDF table extraction", "DocParse 2 is open source and reads scanned PDFs.", 28, lab="Example Lab"),
]


class FakeLLM:
    """Answers by schema name, like the real client does after the tool call is parsed."""

    def __init__(self):
        self.limits = Limits({"max_requests_per_run": 50, "max_requests_per_day": 50, "max_tokens_per_day": 10**6},
                             Path("/tmp/fw-test-usage.json"))
        self.last_model, self.log, self.configured, self.calls = "fake/model", [], ["fake"], []

    def ask(self, *, system, prompt, schema_name, schema, max_tokens=3000):
        self.calls.append(schema_name)
        if schema_name == "submit_assessments":
            return {"assessments": [
                {"id": "s1", "relevance": 3, "capabilities": ["doc_extraction", "bogus"], "so_what": "Could cut manual table capture in fund reports.",
                 "move": "trial", "test": "Run it on 20 public 10-K tables.", "item": "DocParse 2", "kind": "tools", "confidence": "high"},
                {"id": "s2", "relevance": 0, "capabilities": [], "so_what": "Nothing.", "move": "trial", "item": "ChipCo", "kind": "tools"},
                {"id": "s3", "relevance": 2, "capabilities": ["governance"], "so_what": "May require logging of AI steps in client work.",
                 "move": "caution", "test": "", "item": "Invented Act 2030", "kind": "policy", "confidence": "medium"},
            ]}
        if schema_name == "submit_radar":
            return {"subjects": [{"name": "DocParse 2", "same_as": "", "keep": True, "ring": "adopt", "quadrant": "tools",
                                  "capability": "doc_extraction", "rationale": "Open source and handles scanned PDFs; worth a pilot."}]}
        if schema_name == "submit_brief":
            return {"headline": "One tool to try.", "calls": [{"title": "Try DocParse 2", "text": "Test it on public filings.",
                                                                "move": "trial", "story_ids": ["s1", "nope"]}]}
        if schema_name == "submit_takeaways":
            return {"headline": "Two tools to try and one rule to heed", "takeaways": [
                {"title": "Faster table capture", "meaning": "Could cut manual table work.", "use": "Run it on 20 public reports.",
                 "items": ["Tool 1", "tool 2", "Made Up Tool"]},
                {"title": "Tighten logging", "meaning": "May require logs of AI steps.", "use": "List where we use AI on client data.",
                 "items": ["Tool 7", "Tool 3"]},
                {"title": "No items", "meaning": "x", "use": "y", "items": ["Nothing on the radar"]}]}
        if schema_name == "submit_check":
            return {"claims": [{"claim": "DocParse 2 is open source", "type": "fact", "verdict": "supported", "evidence": "DocParse 2 is open source"},
                               {"claim": "This shows open tools are winning", "type": "analysis", "verdict": "unsupported"},
                               {"claim": "It reads scanned PDFs", "verdict": "partly", "evidence": "made up words", "note": "only some scans"}]}
        raise AssertionError(schema_name)


class Fetch:
    def get(self, url):
        return "<html><body><article><p>" + "DocParse 2 is open source and reads many scanned PDFs. " * 12 + "</p></article></body></html>"


def setup(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "stories.json").write_text(json.dumps(STORIES))
    return load_config(data_dir=data)


def test_near_duplicates_are_found():
    assert near_duplicate(STORIES[0], STORIES[3])
    assert not near_duplicate(STORIES[0], STORIES[1])
    assert duplicate_ids(STORIES) == {"s4": "s1"}


def test_lens_run_end_to_end(tmp_path):
    cfg = setup(tmp_path)
    llm = FakeLLM()
    report = dpa.run(cfg, Fetch(), NOW, llm=llm)
    st = dpa.LensState(cfg.data_dir)
    # duplicates aren't assessed; invented items and capabilities are dropped; relevance 0 clears the move
    assert set(st.impact) == {"s1", "s2", "s3"}
    assert st.impact["s1"]["capabilities"] == ["doc_extraction"] and st.impact["s1"]["model"] == "fake/model"
    assert st.impact["s2"] == {**st.impact["s2"], "relevance": 0, "move": "none", "so_what": "", "item": ""}
    assert st.impact["s3"]["item"] == ""  # "Invented Act 2030" isn't named in the story
    # only a person moves something into Adopt: the agent's adopt becomes trial, proposed for adopt
    e = st.radar["entries"]["docparse-2"]
    assert e["ring"] == "trial" and e["proposed"] == "adopt" and e["evidence"] == ["s1"]
    assert st.brief["calls"][0]["story_ids"] == ["s1"]
    assert report["takeaways"].startswith("skipped") and "takeaways" not in st.radar  # one item isn't a top 10 to write about
    assert not (cfg.data_dir / "dpa" / "poc.json").exists()
    # the audit keeps only evidence that is really in the source
    a = next(iter(st.factcheck["audits"].values()))
    assert a["verdict"] == "minor" and a["claims"][0]["evidence"] and not a["claims"][1]["evidence"] and len(a["claims"]) == 2
    assert "factcheck" in report and not [n for n in report["notes"] if "failed" in n]
    # a second run the same day doesn't repeat the daily steps
    llm2 = FakeLLM()
    dpa.run(cfg, Fetch(), NOW, llm=llm2)
    assert "submit_brief" not in llm2.calls and "submit_check" not in llm2.calls and "submit_takeaways" not in llm2.calls


def test_people_decide(tmp_path):
    cfg = setup(tmp_path)
    dpa.run(cfg, Fetch(), NOW, llm=FakeLLM())
    conf = tmp_path / "config"
    shutil.copytree(ROOT / "config", conf)
    (conf / "dpa_review.yaml").write_text("radar_adopt: [DocParse 2]\n")
    view = dpa.site_view(STORIES, cfg.data_dir, NOW, config_dir=conf)
    assert view["radar"][0]["ring"] == "adopt" and view["radar"][0]["human"] and view["radar"][0]["n"] == 1
    assert view["radar"][0]["note"]["test"] == "Run it on 20 public 10-K tables."
    # before the agent writes the panel, the top items are grouped by what to do about them
    tk = view["takeaways"]
    assert not tk["by_agent"] and tk["items"][0]["title"] == "Worth trying now" and tk["items"][0]["rows"][0]["key"] == "docparse-2"
    assert tk["items"][0]["use"] == "First step: Run it on 20 public 10-K tables." and tk["headline"] == "1 to try now"
    assert view["recent"][0]["id"] == "s1" and view["stats"]["trial"] == 0


def test_bench_scores_and_unavailable_models(tmp_path):
    cfg = setup(tmp_path)
    spec = bench.load_tasks()

    class Perfectish:
        def __init__(self, dead):
            self.dead = dead

        def ask(self, *, system, prompt, schema_name, schema, max_tokens=1500):
            if self.dead:
                from agent.llm import AllProvidersFailed
                raise AllProvidersFailed("x/y: model unavailable (404); trying next model")
            return {"inconsistent": ["S2", "S4"], "total_matches": False, "computed_total": 87565, "difference": 900}

    env = {p["key_env"]: "k" for p in cfg.providers[:2]}
    rec = bench.run(cfg, NOW, env, llm_for=lambda p, m: Perfectish(dead=p["name"] != "gemini"), sleep=lambda s: None)
    gem = [m for m in rec["models"] if m["provider"] == "gemini"]
    assert gem and all(m["available"] for m in gem)
    assert gem[0]["tasks"]["narrative-vs-table"]["score"] == 1.0 and gem[0]["tasks"]["holdings-total"]["score"] == 1.0
    assert 0 < gem[0]["score"] < 100 and gem[0]["by_type"]["quality"] > 0
    assert all(not m["available"] for m in rec["models"] if m["provider"] != "gemini")
    view = bench.site_view(cfg.data_dir)
    assert view["rows"] and len(view["rows"][0]["cells"]) == len(spec["tasks"])


def test_system_numbers(tmp_path):
    from agent import system
    cfg = setup(tmp_path)
    (cfg.data_dir / "runs").mkdir()
    rep = {"started_at": NOW.isoformat(), "mode": "full", "fetched": 100, "fresh": 10, "judged": 9, "kept": 3,
           "written": [{"id": "s1"}], "dropped": [{"reason": "not AI: x"}, {"reason": "score 3: y"}, {"reason": "duplicate of abc"}],
           "notes": ["dropped unverifiable quote (A): b"], "provider_log": ["groq/x: per-minute limit hit; trying next model"],
           "timings": {"gather": 60, "write": 120}, "providers": ["gemini"]}
    (cfg.data_dir / "runs" / f"{NOW.strftime('%Y%m%dT%H%M%SZ')}.json").write_text(json.dumps(rep))
    st = system.stats(cfg, STORIES, NOW + timedelta(hours=1))
    assert st["runs"] == 1 and st["written"] == 1 and st["fallbacks"] == 1 and st["quotes_removed"] == 1
    assert dict(st["drops"]) == {"Not AI news": 1, "Below the bar": 1, "Duplicate or already covered": 1}
    assert st["run_minutes"] == 3.0 and st["latency_h"] == 1.0


def test_factcheck_summary():
    fc = {"audits": {"s1": {"date": "2026-10-21", "verdict": "flagged", "headline": "H", "claims": [
        {"claim": "a", "verdict": "supported"}, {"claim": "b", "verdict": "contradicted", "note": "wrong date"}]}}}
    out = factcheck.summary(fc, {"s1": "fixed the date"}, {"s1": {"headline": "H"}}, NOW)
    assert out["rate"] == 50.0 and out["log"][0]["resolution"] == "fixed the date" and out["flagged_stories"] == 1


def _radar_fixture(tmp_path, n=14):
    """n stories, each the evidence for one radar item, with falling relevance and scores; items 1-3 are models."""
    data = tmp_path / "data"
    (data / "dpa").mkdir(parents=True)
    quads = ["models", "models", "models", "models", "models", "tools", "policy", "tools", "techniques", "tools", "policy", "tools", "models", "tools"]
    stories, impact, entries = [], {}, {}
    for i in range(1, n + 1):
        sid = f"r{i}"
        stories.append(story(i, f"Story about Tool {i}", f"Tool {i} does things.", 24 * (i % 5) + 2, score=10 - (i % 5)))
        stories[-1]["id"] = sid
        impact[sid] = {"relevance": 3 if i <= 7 else 2, "capabilities": ["doc_extraction"], "so_what": f"Tool {i} could help.",
                       "move": "trial" if i in (4, 9) else "assess", "test": f"Test tool {i}." if i % 2 else "", "item": f"Tool {i}",
                       "kind": quads[i - 1], "confidence": "high"}
        key = f"tool-{i}"
        entries[key] = {"key": key, "name": f"Tool {i}", "first_seen": "2026-10-20", "history": [{"date": "2026-10-20", "from": "", "to": "assess", "why": "x"}],
                        "evidence": [sid], "ring": "trial" if i in (4, 9) else "hold" if i == 7 else "assess", "proposed": "",
                        "quadrant": quads[i - 1], "capability": "doc_extraction", "rationale": f"Why tool {i}.", "updated": "2026-10-20"}
    entries["tool"] = {**entries["tool-1"], "key": "tool", "name": "Tool"}  # a bare family name while "Tool 1" exists
    (data / "stories.json").write_text(json.dumps(stories))
    (data / "dpa" / "impact.json").write_text(json.dumps(impact))
    (data / "dpa" / "radar.json").write_text(json.dumps({"entries": entries, "considered": []}))
    return load_config(data_dir=data), stories


def test_radar_shows_only_the_top_10(tmp_path):
    cfg, stories = _radar_fixture(tmp_path)
    view = dpa.site_view(stories, cfg.data_dir, NOW)
    top = view["radar"]
    assert len(top) == 10 and [e["n"] for e in top] == list(range(1, 11))
    assert len(view["watchlist"]) == 5 and view["stats"]["radar"] == 10 and view["stats"]["tracked"] == 15
    assert sum(1 for e in top if e["quadrant"] == "models") <= 4  # no quadrant crowds out the rest
    assert "tool" not in {e["key"] for e in top}  # the bare family name ranks below its specific releases
    imp = [e["importance"] for e in top]
    assert imp == sorted(imp, reverse=True)
    assert {"tool-4", "tool-7"} <= {e["key"] for e in top}  # calls for action (trial, hold) with relevance 3 make it
    # the story pages and the API only point at items that are on the radar
    assert all(e["rank"] == 0 for e in view["watchlist"])


def test_takeaways_are_written_for_the_top_10_and_kept_until_it_changes(tmp_path):
    cfg, stories = _radar_fixture(tmp_path)
    st = dpa.LensState(cfg.data_dir)
    prof, review, report = dpa.load_profile(), dpa.load_review(), {}
    llm = FakeLLM()
    assert dpa.write_takeaways(llm, stories, st, prof, review, NOW, report)
    tk = st.radar["takeaways"]
    # names map to keys (case-insensitive); names not in the top 10 (Tool 3 is a fifth model) are dropped, and a
    # takeaway with none is dropped
    assert [t["items"] for t in tk["items"]] == [["tool-1", "tool-2"], ["tool-7"]]
    assert tk["headline"] and tk["sig"] and report["takeaways"].startswith("2 takeaways")
    # same top 10 a few hours later: nothing to rewrite
    assert not dpa.write_takeaways(FakeLLM(), stories, st, prof, review, NOW + timedelta(hours=5), {})
    st.save({}, NOW)
    view = dpa.site_view(stories, cfg.data_dir, NOW + timedelta(hours=1))
    assert view["takeaways"]["by_agent"] and view["takeaways"]["items"][0]["rows"][0]["name"] == "Tool 1"
    # once an item a takeaway rests on leaves the top 10, the agent's panel gives way to the grouped view
    radar = json.loads((cfg.data_dir / "dpa" / "radar.json").read_text())
    radar["takeaways"]["items"][1]["items"] = ["tool-13"]
    radar["takeaways"]["items"][0]["items"] = ["tool-14"]
    (cfg.data_dir / "dpa" / "radar.json").write_text(json.dumps(radar))
    view = dpa.site_view(stories, cfg.data_dir, NOW + timedelta(hours=1))
    assert not view["takeaways"]["by_agent"] and {t["title"] for t in view["takeaways"]["items"]} <= {
        "Worth trying now", "Test before relying on them", "Pause and check"}
