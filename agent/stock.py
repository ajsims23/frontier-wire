"""Stock photos: a real, freely licensed photo for stories whose sources had no usable picture.

Many stories come from posts, papers or blogs without a preview image. Rather than leave them without a picture,
we look for a relevant photo on Openverse (Flickr and other open collections, no key needed) and, failing that,
Wikimedia Commons. Only licences that allow commercial use and cropping are taken, and the photographer and licence
are kept with the story so the site can credit them. The search words come from the story itself (what it's about:
chips, data centres, a classroom, a parliament), so no AI requests are spent. Each photo is used once at a time, so
the front page doesn't repeat itself.
"""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

from .photos import MAX_BYTES, save_photo

UA = {"User-Agent": "FrontierWire/1.0 (AI news site; https://github.com/ajsims23/frontier-wire)", "Accept": "application/json"}

# What the story is about -> words that find a good photo. First match wins, so specific topics come first.
TOPICS: list[tuple[str, str]] = [
    (r"\b(gpus?|chips?|semiconductor|nvidia|tsmc|wafer|foundry|blackwell|hopper|tpus?)\b", "computer chip semiconductor"),
    (r"\b(data ?cent(?:er|re)s?|compute capacity|gigawatt|\d+ ?gw|server farm|supercomputer|hyperscale)\b", "data center servers"),
    (r"\b(storage|database|disk|ssd)\b", "server room storage"),
    (r"\b(robots?|robotics|humanoid|autonomous vehicle|self-driving|drones?)\b", "robot"),
    (r"\b(satellite|space|spacex|rocket|orbit)\b", "rocket launch"),
    (r"\b(forest|climate|earth|weather|biodiversity|agricultur\w*|farm\w*)\b", "forest aerial view"),
    (r"\b(school|students?|curriculum|ncert|classroom|universit\w+|education|teachers?)\b", "students classroom computers"),
    (r"\b(hospital|doctors?|medical|diagnos\w+|health\w*|patients?|clinical|drug|biotech|pharma\w*)\b", "doctor hospital technology"),
    (r"\b(sebi|broker\w*|stock exchange|trading|bank\w*|fintech|bonds?|insurance)\b", "stock exchange trading"),
    (r"\b(cyber\w*|vulnerab\w+|hack\w*|exploit\w*|malware|breach|phishing)\b", "computer security hacker"),
    (r"\b(voice|speech|audio|podcast|music|text-to-speech|tts)\b", "studio microphone"),
    (r"\b(coding|developers?|programm\w+|software engineer\w*|github|open[- ]source)\b", "programmer laptop code"),
    (r"\b(china|chinese|beijing)\b", "shanghai skyline"),
    (r"\b(india|indian|bengaluru|bangalore|mumbai|delhi|crore|lakh)\b", "bengaluru city"),
    (r"\b(parliament|congress|senate|lawmakers?|legislat\w+|bill|act|treasury|ministry|government|regulat\w+|white house)\b", "government building"),
    (r"\b(court|lawsuit|sued|judge|copyright|antitrust)\b", "courthouse"),
    (r"\b(raises?|raised|funding|valuation|ipo|investors?|venture|fund|acqui\w+|deal)\b", "business meeting office"),
    (r"\b(jobs?|workers?|workforce|employment|layoffs?|hiring)\b", "office workers"),
    (r"\b(phones?|smartphone|iphone|android|app)\b", "smartphone in hand"),
    (r"\b(glasses|headset|wearable|vr|ar)\b", "virtual reality headset"),
]
BY_CATEGORY = {"models": "artificial intelligence computer", "research": "science laboratory research",
               "policy": "government building", "safety": "computer security hacker", "industry": "technology office",
               "voices": "conference speaker"}
AVOID = re.compile(r"\b(logo|icon|diagram|chart|map|screenshot|poster|flyer|meme|clipart|drawing|cartoon|text|sign|graph|figure|table|"
                   r"report|document|page|slide|infographic|brochure|assessment|framework|agency|seal|emblem|cover|scan)\b|\.(pdf|png|svg|tiff?|djvu|gif)\b", re.I)


def query_for(story: dict[str, Any]) -> str:
    text = " ".join(str(story.get(k) or "") for k in ("headline", "summary")).lower()
    text += " " + " ".join(str(t).lower() for t in (story.get("tags") or []) + (story.get("sectors") or []))
    for pattern, words in TOPICS:
        if re.search(pattern, text):
            return words
    return BY_CATEGORY.get(story.get("category", ""), "artificial intelligence technology")


def openverse(http: Any, q: str) -> list[dict[str, Any]]:
    params = {"q": q, "license_type": "commercial,modification", "aspect_ratio": "wide", "size": "large",
              "mature": "false", "page_size": 20}
    r = http.get(f"https://api.openverse.org/v1/images/?{urlencode(params)}", headers=UA)
    if r.status_code != 200:
        return []
    out = []
    for it in r.json().get("results") or []:
        lic = str(it.get("license") or "").lower()
        if lic in ("by-nc", "by-nc-sa", "by-nc-nd", "by-nd", "sampling+", "nc-sampling+"):
            continue
        out.append({"key": f"ov:{it.get('id')}", "url": it.get("url") or "", "title": it.get("title") or "",
                    "w": it.get("width") or 0, "h": it.get("height") or 0, "by": (it.get("creator") or "").strip(),
                    "license": ("CC0" if lic == "cc0" else "Public domain" if lic == "pdm" else
                                f"CC {lic.upper()} {it.get('license_version') or ''}".strip()),
                    "page": it.get("foreign_landing_url") or "", "via": (it.get("source") or "Openverse").replace("_", " ").title()})
    return out


def commons(http: Any, q: str) -> list[dict[str, Any]]:
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:bitmap {q}",
              "gsrnamespace": 6, "gsrlimit": 20, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1280}
    r = http.get(f"https://commons.wikimedia.org/w/api.php?{urlencode(params)}", headers=UA)
    if r.status_code != 200:
        return []
    out = []
    for p in ((r.json().get("query") or {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        val = lambda k: re.sub(r"<[^>]+>", "", str((meta.get(k) or {}).get("value") or "")).strip()  # noqa: E731
        lic = val("LicenseShortName")
        if not lic or re.search(r"\b(nc|nd|fair use|non-free)\b", lic, re.I) or ii.get("mime") != "image/jpeg":
            continue
        out.append({"key": f"wc:{p.get('pageid')}", "url": ii.get("thumburl") or ii.get("url") or "", "title": p.get("title") or "",
                    "w": ii.get("width") or 0, "h": ii.get("height") or 0, "by": val("Artist")[:80], "license": lic,
                    "page": ii.get("descriptionurl") or "", "via": "Wikimedia Commons"})
    return out


def looks_like_photo(content: bytes) -> bool:
    """Scanned pages, slides and diagrams are mostly flat white or one flat colour; photos aren't."""
    import io
    from PIL import Image, ImageStat
    try:
        im = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception:  # noqa: BLE001
        return False
    im.thumbnail((160, 160))
    px = list(im.getdata())
    white = sum(1 for r, g, b in px if r > 232 and g > 232 and b > 232) / max(1, len(px))
    spread = sum(ImageStat.Stat(im.convert("L")).stddev)
    colours = len(set((r >> 4, g >> 4, b >> 4) for r, g, b in px))
    return white < 0.3 and spread > 25 and colours > 60


def usable(c: dict[str, Any]) -> bool:
    w, h = c.get("w") or 0, c.get("h") or 0
    return (str(c.get("url", "")).startswith("https://") and w >= 900 and h and 1.2 <= w / h <= 2.4
            and not AVOID.search(c.get("title") or ""))


def add_stock_photos(room: Any, http: Any = None, limit: int = 8) -> None:
    """Give up to `limit` live stories without a photo a credited stock photo."""
    folder = room.store.dir / "img"
    cutoff = (room.now - timedelta(days=room.cfg.run.get("front_page_days", 14))).isoformat()
    live = [s for s in room.store.stories if s["published_at"] >= cutoff]
    used = {s["photo_credit"]["key"] for s in live if isinstance(s.get("photo_credit"), dict) and s["photo_credit"].get("key")}
    want = [s for s in live if not s.get("photo_local") and s.get("image_kind") != "figure" and not s.get("stock_tried")
            and (not s.get("image") or s.get("photo_failed"))]
    want.sort(key=lambda s: s["published_at"], reverse=True)  # newest first: they're the ones on the front page
    if not want:
        return
    if http is None:
        import httpx
        http = getattr(room, "photo_http", None) or httpx.Client(timeout=15, follow_redirects=True)
    cache: dict[str, list[dict[str, Any]]] = {}
    got = 0
    for s in want[:limit]:
        q = query_for(s)
        s["stock_tried"] = room.now.isoformat()
        if q not in cache:
            found: list[dict[str, Any]] = []
            for search in (openverse, commons):
                try:
                    found = [c for c in search(http, q) if usable(c)]
                except Exception:  # noqa: BLE001
                    found = []
                if found:
                    break
            cache[q] = found
        for c in cache[q]:
            if c["key"] in used:
                continue
            used.add(c["key"])  # tried once, whatever happens: don't hand a broken photo to the next story
            try:
                r = http.get(c["url"], headers={**UA, "Accept": "image/avif,image/webp,image/*,*/*"})
                ok = (r.status_code == 200 and len(r.content) < MAX_BYTES and looks_like_photo(r.content)
                      and save_photo(r.content, folder / f"{s['id']}.jpg"))
            except Exception:  # noqa: BLE001
                ok = False
            if ok:
                s["photo_local"] = True
                s["image_kind"] = "stock"
                s["photo_credit"] = {k: c[k] for k in ("key", "by", "license", "page", "via")}
                got += 1
                break
    room.report["stock photos"] = f"{got} added"
