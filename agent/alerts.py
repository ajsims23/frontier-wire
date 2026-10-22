"""Alerts: after each run, tell the Frontier Wire API what happened so readers who follow it get an email.

Events: new stories, tracker updates, model launches and price changes, and resolved claims. Each event lists the
follow keys it matches (e.g. "lab:OpenAI", "tracker:copyright"); the API emails only subscribers who follow one,
and never sends the same event twice. Runs only when API_URL and ALERTS_DISPATCH_SECRET are set.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

from .editorial import is_india


def follow_keys(s: dict[str, Any]) -> list[str]:
    keys = [f"lab:{s['lab']}"] if s.get("lab") else []
    keys += [f"tracker:{t}" for t in s.get("trackers") or []] + [f"sector:{t}" for t in s.get("sectors") or []]
    keys.append(f"topic:{s['category']}")
    if is_india(s):
        keys.append("region:india")
    if s.get("deal"):
        keys.append("deals")
    return keys


def build_events(room: Any, site: str) -> list[dict[str, Any]]:
    today = room.now.date().isoformat()
    by_id = {s["id"]: s for s in room.store.stories}
    events = []
    for w in room.report.get("written", []):
        s = by_id.get(w["id"])
        if s:
            events.append({"key": f"story:{s['id']}", "title": s["headline"], "summary": s["summary"],
                           "url": f"{site}story/{s['id']}/", "follows": follow_keys(s)})
    for tid, t in (room.store.trackers or {}).items():
        if (t.get("updated_at") or "")[:10] == today and t.get("status"):
            events.append({"key": f"tracker:{tid}:{t['updated_at']}", "title": f"Where things stand: {t.get('title') or tid}",
                           "summary": t.get("changed") or t["status"], "url": f"{site}tracker/{tid}/", "follows": [f"tracker:{tid}"]})
    for c in (room.store.models or {}).get("changes", []):
        if c.get("date") == today:
            h = hashlib.sha1(c["text"].encode()).hexdigest()[:10]
            events.append({"key": f"model:{h}", "title": c["text"], "summary": "From the Frontier Wire model tracker.",
                           "url": f"{site}models/", "follows": ["models"] + ([f"lab:{c['lab']}"] if c.get("lab") else [])})
    for c in (room.store.claims or {}).get("claims", []):
        if c.get("resolved") == today:
            events.append({"key": f"claim:{c['id']}:{c['status']}", "title": f"Claim {c['status']}: {c['claim']}",
                           "summary": f"{c['who']}: “{c['quote']}”", "url": f"{site}claims/",
                           "follows": [f"lab:{c['lab']}"] if c.get("lab") else []})
    return [e for e in events if e["follows"]]


def dispatch(room: Any, http: Any = None) -> None:
    api, secret = os.environ.get("API_URL", "").rstrip("/"), os.environ.get("ALERTS_DISPATCH_SECRET", "")
    if not api or not secret:
        return
    site = (os.environ.get("SITE_URL") or room.cfg.settings.get("site", {}).get("base_url", "")).rstrip("/") + "/"
    events = build_events(room, site)
    if not events:
        room.report["alerts"] = "no events"
        return
    import httpx
    client = http or httpx.Client(timeout=30)
    try:
        r = client.post(f"{api}/api/dispatch", json={"events": events}, headers={"authorization": f"Bearer {secret}"})
        room.report["alerts"] = f"{len(events)} events sent: {r.text[:120]}" if r.status_code == 200 else f"dispatch failed: HTTP {r.status_code}"
    except Exception as exc:  # noqa: BLE001
        room.report["alerts"] = f"dispatch failed: {type(exc).__name__}"
