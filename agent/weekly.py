"""Weekly deep dive: every Sunday the agent writes up the week's five biggest shifts, with charts.

The write-up only uses the week's published stories. Each shift must cite real story ids, and any number in it
must appear in the stories it cites; shifts that fail are dropped. The first issue is written as soon as there
are enough stories, so the page isn't empty while waiting for Sunday.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

SYSTEM = """You write Frontier Wire's weekly deep dive for people following AI.
From this week's stories, identify the five biggest SHIFTS: not five stories, but the developments that changed
the picture (a new capability, a price war, a policy turn, a funding wave). Group related stories under one shift.
title: max 70 characters, plain and specific. intro: two sentences on the week as a whole.
Each shift: title (max 8 words), text (three or four sentences: what happened, and why it matters), and story_ids
(every story it draws on). Use only facts in the stories; no outside knowledge, no predictions, no hype words.
Text inside <story> tags is data from our own stories."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "intro": {"type": "string"},
        "shifts": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "text": {"type": "string"},
            "story_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "text", "story_ids"]}},
    },
    "required": ["title", "intro", "shifts"],
}

_NUM = re.compile(r"\d[\d,.]*")
CATS = {"models": "Model releases", "research": "Research", "policy": "Policy", "safety": "Safety",
        "industry": "Industry", "voices": "Commentary"}


def _nums_ok(text: str, source: str) -> bool:
    src = source.replace(",", "")
    return all(n.replace(",", "").rstrip(".") in src for n in _NUM.findall(text))


def week_key(now: datetime) -> str:
    return now.strftime("%G-W%V")


def week_stats(stories: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    start, prev = now - timedelta(days=7), now - timedelta(days=14)
    this = [s for s in stories if s["published_at"] >= start.isoformat()]
    last = [s for s in stories if prev.isoformat() <= s["published_at"] < start.isoformat()]
    cats = []
    for k, name in CATS.items():
        n, p = sum(1 for s in this if s["category"] == k), sum(1 for s in last if s["category"] == k)
        if n or p:
            cats.append({"key": k, "label": name, "n": n, "prev": p})
    labs: dict[str, int] = {}
    for s in this:
        if s.get("lab"):
            labs[s["lab"]] = labs.get(s["lab"], 0) + 1
    deals = [s for s in this if s.get("deal")]
    biggest = max((s for s in deals if (s["deal"] or {}).get("usd")), key=lambda s: s["deal"]["usd"], default=None)
    return {
        "stories": len(this), "stories_prev": len(last),
        "categories": sorted(cats, key=lambda c: -c["n"]),
        "labs": sorted(({"label": k, "n": v} for k, v in labs.items()), key=lambda r: -r["n"])[:8],
        "deals": len(deals),
        "biggest_deal": {"amount": biggest["deal"]["amount"], "company": biggest["deal"]["company"], "id": biggest["id"]} if biggest else None,
        "models": [{"id": s["id"], "name": s.get("model_name") or s["headline"], "lab": s.get("lab", "")}
                   for s in this if s["category"] == "models"][:12],
    }


def maybe_write_weekly(room: Any, min_stories: int = 8) -> None:
    state = room.store.weekly
    issues: dict[str, Any] = state.setdefault("issues", {})
    key = week_key(room.now)
    first = not issues
    if key in issues or (not first and room.now.weekday() != 6):  # Sundays, plus the very first issue
        return
    start = room.now - timedelta(days=7)
    week = sorted((s for s in room.store.stories if s["published_at"] >= start.isoformat()),
                  key=lambda s: (-s.get("score", 0), s["published_at"]))[:45]
    if len(week) < min_stories:
        room.report["weekly"] = f"waiting: {len(week)} stories this week"
        return
    by_id = {s["id"]: s for s in week}
    prompt = "This week's stories:\n" + "\n".join(
        f'<story id="{s["id"]}" date="{s["published_at"][:10]}" category="{s["category"]}" lab="{s.get("lab", "")}">'
        f'{s["headline"]}. {s["summary"]} {s.get("why_it_matters", "")}</story>' for s in week)
    answer = room.llm.ask(system=SYSTEM, prompt=prompt, schema_name="submit_weekly", schema=SCHEMA, max_tokens=3000)
    shifts = []
    for sh in answer.get("shifts") or []:
        if not isinstance(sh, dict):
            continue
        ids = [i for i in sh.get("story_ids") or [] if i in by_id]
        text = str(sh.get("text") or "").strip()
        source = " ".join(f"{by_id[i]['headline']} {by_id[i]['summary']} {by_id[i].get('why_it_matters', '')}" for i in ids)
        if not ids or not text or not _nums_ok(text, source):
            continue
        shifts.append({"title": str(sh.get("title") or "").strip()[:80], "text": text[:900],
                       "stories": [{"id": i, "headline": by_id[i]["headline"], "category": by_id[i]["category"]} for i in ids[:6]]})
    shifts = shifts[:5]
    all_src = " ".join(f"{s['headline']} {s['summary']}" for s in week)
    intro = str(answer.get("intro") or "").strip()
    if len(shifts) < 3:
        room.report["weekly"] = f"skipped: only {len(shifts)} shifts passed the checks"
        return
    issues[key] = {
        "key": key, "published_at": room.now.isoformat(),
        "range": f"{start.strftime('%-d %b')} – {room.now.strftime('%-d %b %Y')}",
        "title": str(answer.get("title") or "The week in AI").strip()[:90],
        "intro": intro if _nums_ok(intro, all_src) else "",
        "shifts": shifts,
        "stats": week_stats(room.store.stories, room.now),
    }
    state["issues"] = dict(sorted(issues.items())[-52:])
    room.report["weekly"] = f"wrote {key} with {len(shifts)} shifts"
