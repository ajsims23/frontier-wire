"""Photos: keep our own copy of each recent story's photo, resized, in data/img/<id>.jpg.

Publishers often block their images from being shown elsewhere (in emails especially: Gmail and Outlook fetch
images through their own servers, which many sites refuse). Serving a copy from our own site makes photos show
reliably in emails and load faster on the site. Copies older than the front-page window are deleted.
"""
from __future__ import annotations

import io
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

WIDTH = 960           # sharp in the 552px email column and on the site
MAX_BYTES = 8_000_000


def save_photo(content: bytes, out: Path) -> bool:
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(content))
        img.load()
    except Exception:  # noqa: BLE001
        return False
    if img.width < 300 or img.height < 160:
        return False  # icons and logos, not photos
    img = img.convert("RGB")
    if img.width > WIDTH:
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
    if img.height > img.width * 1.2:  # very tall images: keep a landscape crop from the top
        img = img.crop((0, 0, img.width, round(img.width * 0.75)))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=76, optimize=True, progressive=True)
    return True


def update_photos(room: Any, http: Any = None, limit: int = 25) -> None:
    folder = room.store.dir / "img"
    cutoff = (room.now - timedelta(days=room.cfg.run.get("front_page_days", 14) + 2)).isoformat()
    live = [s for s in room.store.stories if s["published_at"] >= cutoff]
    keep = {s["id"] for s in live}
    if folder.exists():  # drop copies for stories that left the site
        for f in folder.glob("*.jpg"):
            if f.stem not in keep:
                f.unlink()
    import httpx
    client = http or getattr(room, "photo_http", None) or httpx.Client(timeout=15, follow_redirects=True)
    got = failed = 0
    for s in [s for s in live if s.get("image") and not s.get("photo_local") and not s.get("photo_failed")][:limit]:
        url = s["image"]
        if not str(url).startswith("https://"):
            continue
        try:
            u = urlparse(url)
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FrontierWireBot/1.0)",
                                         "Referer": f"{u.scheme}://{u.netloc}/", "Accept": "image/avif,image/webp,image/*,*/*"})
            ok = r.status_code == 200 and len(r.content) < MAX_BYTES and save_photo(r.content, folder / f"{s['id']}.jpg")
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            s["photo_local"] = True
            got += 1
        else:
            s["photo_failed"] = True  # don't keep retrying a blocked image
            failed += 1
    for s in live:  # a copy can disappear (e.g. folder cleared); don't point at a missing file
        if s.get("photo_local") and not (folder / f"{s['id']}.jpg").exists():
            s.pop("photo_local", None)
    room.report["photos"] = f"{got} saved, {failed} unavailable"
