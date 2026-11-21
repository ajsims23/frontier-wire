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
            return {"headline": "One tool to try.", "calls": [{"title": "Pilot DocParse 2", "text": "Test it on public filings.",
                                                                "move": "trial", "story_ids": ["s1", "nope"]}]}
        if schema_name == "submit_poc":
            return {"title": "Pilot DocParse 2 for fund-report tables", "problem": "Manual table capture is slow.",
                    "proposal": "Run DocParse 2 beside the current step.", "plan": ["Pick 20 public reports", "Run both", "Compare"],
                    "metric": "Field accuracy and minutes per document.", "data_safety": "Public documents only.", "effort": "S", "owner": "extraction"}
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
    card = st.poc["cards"][dpa.poc_id("docparse-2")]
    assert card["owner"] == "extraction" and len(card["plan"]) == 3 and card["kind"] == "pilot"
    # the audit keeps only evidence that is really in the source
    a = next(iter(st.factcheck["audits"].values()))
    assert a["verdict"] == "minor" and a["claims"][0]["evidence"] and not a["claims"][1]["evidence"] and len(a["claims"]) == 2
    assert "factcheck" in report and not [n for n in report["notes"] if "failed" in n]
    # a second run the same day doesn't repeat the daily steps
    llm2 = FakeLLM()
    dpa.run(cfg, Fetch(), NOW, llm=llm2)
    assert "submit_brief" not in llm2.calls and "submit_poc" not in llm2.calls and "submit_check" not in llm2.calls


def test_people_decide(tmp_path):
    cfg = setup(tmp_path)
    dpa.run(cfg, Fetch(), NOW, llm=FakeLLM())
    conf = tmp_path / "config"
    shutil.copytree(ROOT / "config", conf)
    pid = dpa.poc_id("docparse-2")
    (conf / "dpa_review.yaml").write_text(f"radar_adopt: [DocParse 2]\npoc_approved: [{pid}]\n")
    view = dpa.site_view(STORIES, cfg.data_dir, NOW, config_dir=conf)
    assert view["radar"][0]["ring"] == "adopt" and view["radar"][0]["human"]
    assert view["cards"][0]["status"] == "approved"
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
