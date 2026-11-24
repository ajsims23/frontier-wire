"""The System page's numbers: how the agent actually behaved, computed from its own run reports (data/runs/),
the published stories and the audits. Nothing here is estimated or typed in by hand."""
from __future__ import annotations

import glob
import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .text import domain

DROP_GROUPS = [
    ("not ai", "Not AI news"),
    ("loosely ai", "Loosely AI, lower priority"),
    ("score", "Below the bar"),
    ("duplicate", "Duplicate or already covered"),
    ("already covered", "Duplicate or already covered"),
    ("could not verify", "Couldn't verify"),
    ("variety", "Variety cap (one source flooding)"),
    ("stale", "Too old"),
    ("not suitable", "Not suitable for the site"),
]
FALLBACK = re.compile(r"trying next model|moving to next provider|skipping provider|retrying without forcing|retrying with a")


def _dt(iso: str) -> datetime:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _group(reason: str) -> str:
    r = reason.lower()
    return next((name for key, name in DROP_GROUPS if r.startswith(key) or (key == "duplicate" and key in r)), "Other")


def load_runs(data_dir: Path, since: datetime) -> list[dict]:
    stamp = since.strftime("%Y%m%dT%H%M%SZ")
    runs = []
    for f in sorted(glob.glob(str(data_dir / "runs" / "*.json"))):
        if Path(f).stem < stamp:
            continue
        try:
            runs.append(json.loads(Path(f).read_text()))
        except json.JSONDecodeError:
            continue
    return runs


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 1) if xs else None


def stats(cfg: Any, stories: list[dict], now: datetime, days: int = 7) -> dict[str, Any]:
    data = cfg.data_dir
    since = now - timedelta(days=days)
    runs = load_runs(data, since)
    full = [r for r in runs if r.get("mode", "full") == "full"]
    sum_ = lambda k, rs=runs: sum(int(r.get(k) or 0) for r in rs)  # noqa: E731
    written = sum(len(r.get("written", [])) for r in runs)
    drops: dict[str, int] = {}
    for r in runs:
        for d in r.get("dropped", []):
            g = _group(d.get("reason", ""))
            drops[g] = drops.get(g, 0) + 1
    notes = [n for r in runs for n in r.get("notes", [])]
    plog = [l for r in runs for l in r.get("provider_log", [])]
    research = {k: sum(int((r.get("research") or {}).get(k) or 0) for r in runs) for k in ("investigated", "confirmed", "tool_calls")}
    durations = [sum(v for v in (r.get("timings") or {}).values() if isinstance(v, (int, float)) and v > 0) / 60 for r in full]
    plans = [r["plan"] for r in full if r.get("plan")]

    # verification mix of the stories published in the window
    roles = {s["id"]: s.get("role", "news") for s in cfg.sources}
    lab_domains = {d.lower().removeprefix("www.") for d in (cfg.lab_domains or {})}  # {domain: lab}
    recent = [s for s in stories if _dt(s["published_at"]) >= since]
    official = two = researched = quoted = 0
    lat = []
    for s in recent:
        doms = {domain(x["url"]) for x in s.get("sources", [])}
        is_official = roles.get(s.get("source_id"), "news") in ("lab", "paper", "voice") or bool(doms & lab_domains) \
            or any(d.endswith(("arxiv.org", "bsky.app", "huggingface.co")) for d in doms)
        official += is_official
        two += len(doms) >= 2
        researched += bool((s.get("research") or {}).get("decision") == "confirmed")
        quoted += bool(s.get("quotes"))
        if s.get("created_at"):
            h = (_dt(s["created_at"]) - _dt(s["published_at"])).total_seconds() / 3600
            if 0 <= h < 96:
                lat.append(h)
    n = len(recent) or 1

    usage = {}
    for f, label in ((data / "usage.json", "newsroom"), (data / "dpa" / "usage.json", "dpa"), (data / "bench" / "usage.json", "bench")):
        try:
            for day, u in json.loads(f.read_text()).items():
                usage.setdefault(day, {"newsroom": 0, "dpa": 0, "bench": 0, "tokens": 0})
                usage[day][label] += int(u.get("requests") or 0)
                usage[day]["tokens"] += int(u.get("tokens") or 0)
        except (OSError, json.JSONDecodeError):
            continue
    days_u = sorted(usage.items())[-14:]
    cap = int(cfg.limits.get("max_requests_per_day", 450))

    audit_hist = [h for h in (json.loads((data / "audit.json").read_text()).get("history", []) if (data / "audit.json").exists() else [])
                  if h.get("coverage") is not None]
    review = (data / "self_review.md").read_text() if (data / "self_review.md").exists() else ""
    suggestions = [{"kind": m.group(1), "target": m.group(2), "text": m.group(3).strip()}
                   for m in re.finditer(r"- \[[ x]\] \*\*([^*]+)\*\* · `([^`]*)`: (.+)", review)][:5]
    review_date = (re.search(r"self-review, (\d{4}-\d{2}-\d{2})", review) or [None, ""])[1]

    return {
        "days": days,
        "runs": len(runs), "full_runs": len(full), "breaking_runs": len(runs) - len(full),
        "sources": len(cfg.sources), "auto_sources": len((json.loads((data / "audit.json").read_text()).get("auto_sources", [])
                                                           if (data / "audit.json").exists() else [])),
        "scanned": sum_("fetched"), "scanned_per_run": _median([float(r.get("fetched") or 0) for r in full]),
        "fresh": sum_("fresh"), "judged": sum_("judged"), "kept": sum_("kept"), "written": written,
        "dropped": sum(drops.values()), "drops": sorted(drops.items(), key=lambda kv: -kv[1]),
        "research": research, "plans": len(plans), "searches": sum(len(p.get("searches", [])) for p in plans),
        "quotes_removed": sum(1 for x in notes if x.startswith(("dropped unverifiable quote", "dropped non-quote"))),
        "benchmarks_removed": sum(1 for x in notes if x.startswith("dropped unverifiable benchmark")),
        "made_up_ids": sum(1 for x in notes if x.startswith("ignored made-up duplicate id")),
        "fallbacks": sum(1 for l in plog if FALLBACK.search(l)),
        "providers": sorted({p for r in runs for p in r.get("providers", [])}),
        "run_minutes": _median(durations),
        "stories": len(recent), "official_pct": round(100 * official / n), "two_pct": round(100 * two / n),
        "researched": researched, "quoted": quoted,
        "latency_h": _median(lat), "fast_pct": round(100 * sum(1 for h in lat if h <= 6) / len(lat)) if lat else None,
        "usage": [{"day": d, **u, "total": u["newsroom"] + u["dpa"] + u["bench"]} for d, u in days_u], "cap": cap,
        "coverage7": round(sum(h["coverage"] for h in audit_hist[-7:]) / len(audit_hist[-7:])) if audit_hist else None,
        "suggestions": suggestions, "review_date": review_date,
        "per_day": _per_day(runs, now, days),
    }


def _per_day(runs: list[dict], now: datetime, days: int) -> list[dict]:
    out = []
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).date()
        rs = [r for r in runs if _dt(r["started_at"]).date() == day]
        out.append({"day": day.strftime("%-d %b"), "runs": len(rs), "fresh": sum(int(r.get("fresh") or 0) for r in rs),
                    "written": sum(len(r.get("written", [])) for r in rs)})
    return out
