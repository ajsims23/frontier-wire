"""Pictures and videos for the Builders desk and Top Voices.

- A build's picture: GitHub's own social card for repositories, otherwise the project page's preview image.
- A build's video: a YouTube demo linked from the post or embedded on the project page.
- A person's portrait: their Bluesky avatar if we follow them there, otherwise the lead image of their Wikipedia
  article (Wikimedia Commons), otherwise none (the site shows their initials).
Everything is saved as our own resized copy under data/img/ (publishers often block hotlinking), and any failure
just means no picture.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from .text import extract_image

YT = re.compile(r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^\s\"'<>]*&)?v=|embed/|shorts/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")
UA = {"User-Agent": "Mozilla/5.0 (compatible; FrontierWireBot/1.0)", "Accept": "image/avif,image/webp,image/*,*/*"}


def youtube_id(text: str) -> str:
    m = YT.search(text or "")
    return m.group(1) if m else ""


def client(room: Any) -> Any:
    http = getattr(room, "photo_http", None)
    if http is None:
        import httpx
        http = httpx.Client(timeout=15, follow_redirects=True)
        try:
            room.photo_http = http
        except Exception:  # noqa: BLE001
            pass
    return http


def page_media(fetcher: Any, url: str) -> tuple[str, str]:
    """(preview image URL, YouTube id) from a page, or empty strings."""
    try:
        html = fetcher.get(url)
    except Exception:  # noqa: BLE001
        return "", ""
    return extract_image(html, url) or "", youtube_id(html)


def github_card(url: str) -> str:
    m = re.match(r"https://github\.com/([^/\s]+)/([^/\s#?]+)", url or "")
    return f"https://opengraph.githubassets.com/1/{m.group(1)}/{m.group(2)}" if m else ""


def save_image(http: Any, url: str, out: Path, *, avatar: bool = False) -> bool:
    """Download and keep a resized JPEG copy. Avatars become 200px squares; photos 720px wide, landscape."""
    if not str(url).startswith("https://"):
        return False
    try:
        from PIL import Image
        u = urlparse(url)
        r = http.get(url, headers={**UA, "Referer": f"{u.scheme}://{u.netloc}/"})
        if r.status_code != 200 or len(r.content) > 8_000_000:
            return False
        img = Image.open(io.BytesIO(r.content))
        img.load()
        img = img.convert("RGB")
        if avatar:
            if min(img.size) < 48:
                return False
            side = min(img.size)
            left, top = (img.width - side) // 2, 0 if img.height > img.width else (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize((200, 200), Image.LANCZOS)
        else:
            if img.width < 300 or img.height < 150:
                return False
            if img.width > 720:
                img = img.resize((720, round(img.height * 720 / img.width)), Image.LANCZOS)
            if img.height > img.width * 0.75:  # keep a landscape crop from the top
                img = img.crop((0, 0, img.width, round(img.width * 0.5625)))
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, "JPEG", quality=78, optimize=True, progressive=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:60] or "x"


def portrait_url(fetcher: Any, name: str, bsky: str = "", wiki: str = "") -> tuple[str, str]:
    """(image URL, credit) for a person: Bluesky avatar first, then Wikipedia's lead image."""
    if bsky:
        try:
            prof = json.loads(fetcher.get(f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={quote(bsky)}"))
            if prof.get("avatar"):
                return prof["avatar"], "Bluesky"
        except Exception:  # noqa: BLE001
            pass
    title = wiki  # only names we were told to look up, so a look-alike's photo is never used
    if title:
        try:
            page = json.loads(fetcher.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}"))
            # only a real article about a person (not a disambiguation page)
            if page.get("type") == "standard" and (page.get("thumbnail") or {}).get("source"):
                return page["thumbnail"]["source"], "Wikimedia Commons"
        except Exception:  # noqa: BLE001
            pass
    return "", ""
