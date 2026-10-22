"""JSON files under data/: stories, seen URLs, lab tracker, front-page payload."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _read(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return default
    return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


class Store:
    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.stories: list[dict[str, Any]] = _read(data_dir / "stories.json", [])
        self.seen: dict[str, str] = _read(data_dir / "seen.json", {})
        self.labs: dict[str, dict[str, Any]] = _read(data_dir / "labs.json", {})
        self.retries: dict[str, int] = _read(data_dir / "retries.json", {})
        self.threads: dict[str, dict[str, Any]] = _read(data_dir / "threads.json", {})
        self.briefing: dict[str, Any] = _read(data_dir / "briefing.json", {})
        self.desk_briefings: dict[str, Any] = _read(data_dir / "desk_briefings.json", {})
        self.review_state: dict[str, Any] = _read(data_dir / "review_state.json", {})
        self.newsletter_state: dict[str, Any] = _read(data_dir / "newsletter_state.json", {})
        self.videos: dict[str, Any] = _read(data_dir / "videos.json", {})
        self.models: dict[str, Any] = _read(data_dir / "models.json", {})
        self.weekly: dict[str, Any] = _read(data_dir / "weekly.json", {})

    def is_seen(self, url: str) -> bool:
        return url in self.seen

    def mark_seen(self, urls: list[str], now: datetime) -> None:
        for u in urls:
            self.seen.setdefault(u, now.isoformat())

    def recent_headlines(self, now: datetime, days: int = 7) -> list[dict[str, str]]:
        cutoff = now - timedelta(days=days)
        return [
            {"id": s["id"], "headline": s["headline"]}
            for s in self.stories
            if datetime.fromisoformat(s["published_at"]) >= cutoff
        ]

    def add_story(self, story: dict[str, Any]) -> None:
        self.stories = [s for s in self.stories if s["id"] != story["id"]] + [story]

    def save(self, now: datetime, site: dict[str, Any], report: dict[str, Any]) -> None:
        # forget seen URLs after 30 days so the file doesn't grow forever
        cutoff = (now - timedelta(days=30)).isoformat()
        self.seen = {u: t for u, t in self.seen.items() if t >= cutoff}
        self.stories.sort(key=lambda s: s["published_at"], reverse=True)
        _write(self.dir / "stories.json", self.stories)
        _write(self.dir / "seen.json", self.seen)
        _write(self.dir / "labs.json", self.labs)
        self.retries = {u: n for u, n in self.retries.items() if u not in self.seen}
        _write(self.dir / "retries.json", self.retries)
        _write(self.dir / "threads.json", self.threads)
        _write(self.dir / "briefing.json", self.briefing)
        _write(self.dir / "desk_briefings.json", self.desk_briefings)
        _write(self.dir / "review_state.json", self.review_state)
        _write(self.dir / "newsletter_state.json", self.newsletter_state)
        _write(self.dir / "videos.json", self.videos)
        _write(self.dir / "models.json", self.models)
        _write(self.dir / "weekly.json", self.weekly)
        _write(self.dir / "site.json", site)
        (self.dir / "feed.xml").write_text(rss(self.stories[:30], now))
        _write(self.dir / "runs" / f"{now.strftime('%Y%m%dT%H%M%SZ')}.json", report)
        _write(self.dir / "last_run.json", report)


def rss(stories: list[dict[str, Any]], now: datetime) -> str:
    """RSS 2.0 feed of the latest stories (links go to the primary source)."""
    from email.utils import format_datetime
    from xml.sax.saxutils import escape

    site = os.environ.get("SITE_URL", "").rstrip("/") or "https://github.com"
    items = "".join(
        f"<item><title>{escape(s['headline'])}</title><link>{escape(s['url'])}</link>"
        f"<guid isPermaLink=\"false\">{s['id']}</guid>"
        f"<pubDate>{format_datetime(datetime.fromisoformat(s['published_at']))}</pubDate>"
        f"<category>{escape(s['category'])}</category>"
        f"<description>{escape(s['summary'] + ' ' + s['why_it_matters'])}</description></item>"
        for s in stories
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        f"<title>Frontier Wire</title><link>{escape(site)}</link>"
        "<description>AI news: frontier labs, research, policy and commentary.</description>"
        f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>{items}</channel></rss>\n"
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
