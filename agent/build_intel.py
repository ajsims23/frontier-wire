"""The intelligence pages: For DPA, the AI Radar, pilot proposals, the task bench, the System page and the
agent API (static JSON + the MCP server's documentation). Called from build.py."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import bench as bench_mod
from . import factcheck as fc_mod
from . import system as sys_mod

QUAD_COLOR = {"models": "var(--models)", "tools": "var(--research)", "techniques": "var(--industry)", "policy": "var(--policy)"}
# quadrant → (start angle, end angle) in degrees, 0 = east, counter-clockwise; drawn with y pointing down
QUAD_ANGLES = {"models": (0, 90), "tools": (90, 180), "techniques": (180, 270), "policy": (270, 360)}
RING_BANDS = {"adopt": (0.08, 0.34), "trial": (0.38, 0.6), "assess": (0.64, 0.8), "hold": (0.84, 0.97)}


def _dt(iso: str) -> datetime:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def short(iso: str) -> str:
    return _dt(iso if "T" in iso else iso + "T00:00:00+00:00").strftime("%-d %b")


def radar_svg(entries: list[dict], size: int = 640) -> dict[str, Any]:
    """Blip positions for the radar picture: each item sits in its quadrant and ring, spread out so none overlap."""
    c, R = size / 2, size / 2 - 18
    placed: list[tuple[float, float]] = []
    blips = []
    for e in entries:
        a0, a1 = QUAD_ANGLES.get(e.get("quadrant", "tools"), (90, 180))
        r0, r1 = RING_BANDS[e["ring"]]
        h = int(hashlib.sha1(e["key"].encode()).hexdigest(), 16)
        best = None
        for attempt in range(40):
            u = ((h >> (attempt * 3)) % 1000) / 1000
            v = ((h >> (attempt * 5 + 7)) % 1000) / 1000
            ang = math.radians(a0 + 9 + u * (a1 - a0 - 18))
            rad = R * (r0 + v * (r1 - r0))
            x, y = c + rad * math.cos(ang), c - rad * math.sin(ang)
            gap = min((math.hypot(x - px, y - py) for px, py in placed), default=99)
            if best is None or gap > best[0]:
                best = (gap, x, y)
            if gap >= 25:
                break
        _, x, y = best
        placed.append((x, y))
        blips.append({"n": e["n"], "x": round(x, 1), "y": round(y, 1), "color": QUAD_COLOR.get(e.get("quadrant"), "var(--brand)"),
                      "name": e["name"], "ring": e["ring"], "key": e["key"], "proposed": bool(e.get("proposed")), "human": e.get("human")})
    rings = [{"r": round(R * RING_BANDS[r][1] + (R * 0.02 if r != "hold" else R * 0.03), 1), "label": r.capitalize(),
              "ly": round(c - R * (RING_BANDS[r][0] + RING_BANDS[r][1]) / 2, 1)} for r in ("adopt", "trial", "assess", "hold")]
    return {"size": size, "c": c, "R": R, "blips": blips, "rings": rings}


def build_intel(out: Path, env: Any, common: dict, base: str, cfg: Any, stories: list[dict], by_id: dict[str, dict],
                lens: dict[str, Any], page: Callable[..., None], site: dict, now: datetime) -> str:
    """Renders the pages and the API files; returns the home page's For DPA strip."""
    data = cfg.data_dir
    org = lens["profile"]["org"]
    caps = lens["caps"]
    og = f"{base}og/home.png"

    fc = fc_mod.summary(lens["factcheck"], lens["review"]["corrections"], by_id, now)
    st = sys_mod.stats(cfg, stories, now, days=7)
    st30 = sys_mod.stats(cfg, stories, now, days=30)
    bv = bench_mod.site_view(data)
    top_cards = [c for c in lens["cards"] if c["status"] != "rejected"][:3]
    mcp_url = (site.get("api_url") or "").rstrip("/") + "/mcp" if site.get("api_url") else ""

    # ------------------------------------------------------------------ For DPA (the hub)
    page("dpa", "dpa.html", title=f"For {org['name']}: what to do about AI this week | Frontier Wire",
         description=f"Frontier Wire's intelligence agent reads every AI story with {org['name']}'s work in mind: what it means, "
                     "whether to try it, the AI Radar, pilot proposals and a benchmark of free models on DPA-style tasks.",
         canonical=f"{base}dpa/", og_image=og, org=org, lens=lens, fc=fc, bench=bv, cards=top_cards, mcp_url=mcp_url,
         radar=radar_svg(lens["radar"], 420) if lens["radar"] else None, short=short,
         heat=[{"label": h["short"], "n": h["n"], "href": "", "pct": max(3, round(100 * h["n"] / max([x["n"] for x in lens["heat"]] + [1])))}
               for h in sorted(lens["heat"], key=lambda h: -h["n"])])

    # ------------------------------------------------------------------ the radar
    rings = []
    for r in lens["rings"]:
        rows = [e for e in lens["radar"] if e["ring"] == r["id"]]
        rings.append({**r, "rows": rows})
    page("radar", "radar.html", title=f"The {org['name']} AI Radar: adopt, trial, assess, hold | Frontier Wire",
         description=f"AI models, tools, techniques and rules placed for {org['name']}'s work, with the evidence and every move logged.",
         canonical=f"{base}radar/", og_image=og, org=org, lens=lens, rings=rings, svg=radar_svg(lens["radar"]) if lens["radar"] else None,
         quads=[{**q, "color": QUAD_COLOR[q["id"]], "n": sum(1 for e in lens["radar"] if e.get("quadrant") == q["id"])} for q in lens["quadrants"]],
         moves=[{**mv, "when": short(mv["date"])} for mv in lens["moves"]], short=short,
         updated=short(lens["radar_updated"]) if lens["radar_updated"] else "")

    # ------------------------------------------------------------------ pilot proposals
    page("poc", "poc.html", title=f"Pilot proposals for {org['name']}'s AI Champions | Frontier Wire",
         description="One-page pilot proposals drafted by the agent from the AI Radar's Trial items. A person approves or rejects each one.",
         canonical=f"{base}poc/", og_image=og, org=org, cards=lens["cards"], short=short,
         counts={k: sum(1 for c in lens["cards"] if c["status"] == k) for k in ("awaiting", "approved", "rejected")})

    # ------------------------------------------------------------------ the task bench
    page("bench", "bench.html", title="DPA Task Bench: free AI models tested on financial-document work | Frontier Wire",
         description="Every free model our agent can use, tested weekly on DPA-style tasks: extraction from fund reports and statements, "
                     "reconciliation, checklist QA, ownership and credit arithmetic, document routing. Scored automatically.",
         canonical=f"{base}bench/", og_image=og, b=bv, org=org, short=short,
         example=next((t for t in bv["spec"]["tasks"] if t["id"] == "capital-call"), bv["spec"]["tasks"][0]))

    # ------------------------------------------------------------------ the System page
    page("system", "system.html", title="How the agent works: live pipeline, accuracy and safeguards | Frontier Wire",
         description="Frontier Wire's agent in numbers, from its own run logs: what it read, what it dropped and why, how it verifies, "
                     "its audited accuracy, corrections, and how it runs on free AI tiers.",
         canonical=f"{base}system/", og_image=og, st=st, st30=st30, fc=fc, lens=lens, bench=bv, short=short,
         drop_bars=[{"label": k, "n": v, "href": "", "pct": max(3, round(100 * v / max([n for _, n in st["drops"]] + [1])))} for k, v in st["drops"]],
         usage_max=max([u["total"] for u in st["usage"]] + [st["cap"]]), mcp_url=mcp_url)

    # ------------------------------------------------------------------ the agent API
    page("api", "agent_api.html", title="Use Frontier Wire from your own AI: MCP server and JSON API | Frontier Wire",
         description="Connect Claude, ChatGPT or Gemini to Frontier Wire's verified AI news, the DPA AI Radar, the task bench and the "
                     "accuracy audit through an MCP server, or read the open JSON API.",
         canonical=f"{base}api/", og_image=og, mcp_url=mcp_url, base=base, org=org)
    write_api(out, base, stories, lens, fc, st, bv, now)

    # ------------------------------------------------------------------ the home page strip
    calls = (lens["brief"] or {}).get("calls") or [
        {"title": r["headline"], "text": r["so_what"], "move": r["move"], "move_name": r["move_name"], "stories": [r]}
        for r in lens["recent"][:3] if r.get("so_what")]
    return env.get_template("_dpa_strip.html").render(**common, root="", org=org, brief=lens["brief"], calls=calls[:3],
                                                       stats=lens["stats"], fc=fc, bench=bv, st=st)


def _story_api(s: dict, base: str, lens: dict, audits: dict) -> dict:
    imp = lens["impact"].get(s["id"])
    a = audits.get(s["id"])
    return {"id": s["id"], "headline": s["headline"], "summary": s["summary"], "why_it_matters": s.get("why_it_matters", ""),
            "category": s["category"], "lab": s.get("lab", ""), "published_at": s["published_at"], "page": f"{base}story/{s['id']}/",
            "primary_source": s["url"], "sources": [{"url": x["url"], "publisher": x.get("publisher", "")} for x in s.get("sources", [])],
            "dpa": {k: imp[k] for k in ("relevance", "capabilities", "so_what", "move", "test", "item", "confidence") if k in imp} if imp else None,
            "fact_check": {"verdict": a["verdict"], "date": a["date"], "score": a.get("score")} if a else None}


def write_api(out: Path, base: str, stories: list[dict], lens: dict, fc: dict, st: dict, bv: dict, now: datetime) -> None:
    api = out / "api" / "v1"
    api.mkdir(parents=True, exist_ok=True)
    newest = sorted(stories, key=lambda s: s["published_at"], reverse=True)
    audits = lens["factcheck"].get("audits") or {}
    radar = [{k: e.get(k) for k in ("n", "name", "key", "ring", "proposed", "human", "quadrant", "capability", "cap_name", "rationale",
                                    "first_seen", "updated", "moved", "history")} | {"evidence": [{"id": i, "page": f"{base}story/{i}/",
                                    "headline": next((s["headline"] for s in stories if s["id"] == i), "")} for i in e.get("evidence", [])]}
             for e in lens["radar"]]
    files = {
        "stories.json": {"generated_at": now.isoformat(), "count": min(200, len(newest)),
                         "stories": [_story_api(s, base, lens, audits) for s in newest[:200]]},
        "radar.json": {"generated_at": now.isoformat(), "updated_at": lens["radar_updated"],
                       "rings": lens["rings"], "quadrants": lens["quadrants"], "entries": radar},
        "dpa.json": {"generated_at": now.isoformat(), "org": lens["profile"]["org"]["name"],
                     "capabilities": [{k: c[k] for k in ("id", "name", "about")} for c in lens["profile"]["capabilities"]],
                     "brief": {k: v for k, v in (lens["brief"] or {}).items() if k != "calls"} | {"calls": [
                         {k: c[k] for k in ("title", "text", "move", "story_ids")} for c in (lens["brief"] or {}).get("calls", [])]},
                     "act_on": [{k: r.get(k) for k in ("id", "headline", "so_what", "move", "test", "capabilities", "relevance", "published_at")}
                                | {"page": f"{base}story/{r['id']}/"} for r in lens["recent"]],
                     "roles": [{"id": r["id"], "name": r["name"], "items": [{"id": x["id"], "headline": x["headline"], "so_what": x.get("so_what"),
                                                                              "move": x.get("move")} for x in r["picks"]]} for r in lens["roles"]],
                     "stats": lens["stats"]},
        "poc.json": {"generated_at": now.isoformat(), "cards": [{k: c[k] for k in ("id", "item", "title", "status", "capability", "problem", "proposal",
                                                                                  "plan", "metric", "data_safety", "effort", "owner", "drafted", "evidence")}
                                                               for c in lens["cards"]]},
        "bench.json": {"generated_at": now.isoformat(), "tasks": [{k: t[k] for k in ("id", "type", "title", "capability")} for t in bv["spec"]["tasks"]],
                       "latest": bv["latest"]},
        "system.json": {"generated_at": now.isoformat(), "window_days": st["days"],
                        "pipeline": {k: st[k] for k in ("runs", "full_runs", "breaking_runs", "sources", "scanned", "fresh", "judged", "kept", "written", "dropped")},
                        "drop_reasons": dict(st["drops"]), "verification": {k: st[k] for k in ("official_pct", "two_pct", "researched", "quotes_removed",
                                                                                               "benchmarks_removed", "made_up_ids")},
                        "latency_hours_median": st["latency_h"], "fallbacks_handled": st["fallbacks"], "providers": st["providers"],
                        "ai_cost_inr": 0, "accuracy": {k: fc[k] for k in ("rate", "strict", "claims", "stories", "accurate_stories", "flagged_stories", "since")},
                        "corrections_log": fc["log"]},
    }
    for name, body in files.items():
        (api / name).write_text(json.dumps(body, ensure_ascii=False, indent=1))
    (api / "index.json").write_text(json.dumps({
        "name": "Frontier Wire API", "version": 1, "generated_at": now.isoformat(),
        "about": "Verified AI news with a DPA lens: every story checked against its sources, assessed for DPA, plus the DPA AI Radar, "
                 "pilot proposals, a benchmark of free models on DPA-style tasks and the agent's own accuracy audit.",
        "endpoints": {n.removesuffix(".json"): f"{base}api/v1/{n}" for n in files}, "docs": f"{base}api/"}, indent=1))
