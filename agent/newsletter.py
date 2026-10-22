"""Daily email: send the briefing to newsletter subscribers once a day (Buttondown)."""
from __future__ import annotations

import os
from typing import Any

import httpx

API = "https://api.buttondown.com/v1/emails"


def compose(briefing: dict[str, Any], base_url: str) -> tuple[str, str]:
    line = briefing.get("one_line", "").strip()
    subject = "Today in AI: " + (line if len(line) <= 80 else line[:79].rsplit(" ", 1)[0] + "…")
    parts = [line, ""]
    for t in briefing.get("themes", []):
        parts.append(f"## {t['title']}")
        parts.append(t["text"])
        for s in t.get("stories", []):
            parts.append(f"- [{s['headline']}]({base_url}story/{s['id']}/)")
        parts.append("")
    parts.append(f"More on [Frontier Wire]({base_url}): every story links to its sources. "
                 "Written by our newsroom agent from stories it checked against official sources or two independent outlets.")
    return subject, "\n".join(parts)


def maybe_send(room: Any, http: httpx.Client | None = None) -> None:
    key = os.environ.get("BUTTONDOWN_API_KEY", "").strip()
    cfg = room.cfg.settings.get("newsletter", {}) or {}
    if not key or not cfg.get("enabled", True):
        return
    b = room.store.briefing or {}
    today = room.now.date().isoformat()
    state = room.store.newsletter_state
    if not b.get("themes") or state.get("last_sent") == today:
        return
    if room.now.hour < int(cfg.get("send_after_utc_hour", 2)):  # wait for the morning run (IST)
        return
    if not (b.get("written_at") or "").startswith(today):
        return  # only send a briefing written today
    from .build import site_settings
    subject, body = compose(b, site_settings(room.cfg)["base_url"])
    client = http or httpx.Client(timeout=30)
    resp = client.post(API, headers={"Authorization": f"Token {key}"},
                       json={"subject": subject, "body": body, "status": "about_to_send"})
    if resp.status_code in (200, 201, 202):
        state["last_sent"] = today
        room.report["newsletter"] = f"sent: {subject}"
    else:
        room.report["notes"].append(f"daily email not sent (Buttondown {resp.status_code}): {resp.text[:160]}")
