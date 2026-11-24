"""Text helpers: page extraction, URL/domain handling, quote checking, similarity."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}


def canonical_url(url: str) -> str:
    """Normalise a URL so the same article from different links compares equal."""
    p = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in _TRACKING]
    path = p.path.rstrip("/") or "/"
    netloc = p.netloc.lower().removeprefix("www.")
    if netloc in ("arxiv.org", "export.arxiv.org"):
        netloc = "arxiv.org"
        path = re.sub(r"^/(abs|pdf)/([\w.\-/]+?)(v\d+)?(\.pdf)?$", r"/abs/\2", path)
    return urlunparse(("https", netloc, path, "", urlencode(query), ""))


def domain(url: str) -> str:
    """Registrable-ish domain (last two labels), used to count independent sources."""
    host = urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "ac", "gov", "net"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def stable_id(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def extract_text(html: str, limit: int = 15000) -> str:
    """Main readable text of a page (article > main > body), whitespace-collapsed."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg"]):
        tag.decompose()
    node = soup.find("article") or soup.find("main") or soup.body or soup
    text = node.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def extract_published(html: str) -> str | None:
    """Best-effort publish date from common meta tags / <time>."""
    soup = BeautifulSoup(html, "html.parser")
    for attrs in (
        {"property": "article:published_time"},
        {"name": "article:published_time"},
        {"name": "date"},
        {"itemprop": "datePublished"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"]
    t = soup.find("time", attrs={"datetime": True})
    return t["datetime"] if t else None


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = (
        s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
        .replace("–", "-").replace("—", "-").replace(" ", " ")
    )
    s = re.sub(r"[\"']", "", s.lower())
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,;:!?-")


def quote_in_text(quote: str, text: str) -> bool:
    """True only if the quote appears word-for-word (ignoring case, quote marks, spacing)."""
    q = _norm(quote)
    if len(q) < 12:  # too short to be a meaningful, checkable quote
        return False
    return q in _norm(text)


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


_GENERIC_IMG = re.compile(r"logo|favicon|icon|avatar|placeholder|default[-_]?(og|share|social)|sprite|blank", re.I)


def extract_image(html: str, page_url: str) -> str | None:
    """The page's own preview image (og:image / twitter:image), as an absolute https URL.

    Generic site logos and icons are skipped so the site can fall back to generated art.
    """
    soup = BeautifulSoup(html, "html.parser")
    for attrs in ({"property": "og:image"}, {"property": "og:image:url"}, {"name": "twitter:image"},
                  {"name": "twitter:image:src"}, {"property": "twitter:image"}):
        tag = soup.find("meta", attrs=attrs)
        src = (tag.get("content") or "").strip() if tag else ""
        if not src:
            continue
        url = urljoin(page_url, src)
        if url.startswith("http://"):
            url = "https://" + url[len("http://"):]
        if url.startswith("https://") and not _GENERIC_IMG.search(urlparse(url).path) and len(url) < 600:
            return url
    return None


ARXIV_ID = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/|huggingface\.co/papers/)(\d{4}\.\d{4,5})", re.I)


def arxiv_id(url: str) -> str | None:
    m = ARXIV_ID.search(url or "")
    return m.group(1) if m else None


def paper_figure(fetcher, paper_id: str) -> str | None:
    """The first figure from the paper's arXiv HTML version (most recent papers have one), as an https URL."""
    page = f"https://arxiv.org/html/{paper_id}"
    fetch = getattr(fetcher, "fetch", None)
    html, final = fetch(page) if fetch else (fetcher.get(page), page)
    soup = BeautifulSoup(html, "html.parser")
    for fig in soup.find_all("figure")[:6]:
        img = fig.find("img")
        src = (img.get("src") or "").strip() if img else ""
        if not src or src.startswith("data:") or src.lower().endswith(".svg"):
            continue
        try:
            if int(img.get("width") or 999) < 160:
                continue  # icons and tiny inline images
        except ValueError:
            pass
        if src.startswith("http"):
            url = src
        elif src.startswith(paper_id):
            url = urljoin("https://arxiv.org/html/", src)
        else:
            url = urljoin(final.rstrip("/") + "/", src)
        if url.startswith("https://arxiv.org/"):
            return url
    return None


_DUP_STOP = set("""this that with from into over after their they have will been were what when which while about also
than more just only says said report reports reported according announced announces launch launches new""".split())


def content_tokens(text: str) -> set[str]:
    """Distinctive words of a story (names, numbers, nouns), for near-duplicate checks."""
    words = re.findall(r"[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]", (text or "").lower().replace("‑", "-"))
    return {w for w in words if len(w) > 3 and w not in _DUP_STOP}


def near_duplicate(a: dict, b: dict) -> bool:
    """True when two stories report the same news (identical or reworded headlines, same facts)."""
    ha, hb = a.get("headline", ""), b.get("headline", "")
    sim = similar(ha, hb)
    if sim >= 0.8:
        return True
    ta = content_tokens(f"{ha} {a.get('summary', '')}")
    tb = content_tokens(f"{hb} {b.get('summary', '')}")
    if not ta or not tb:
        return False
    jac = len(ta & tb) / len(ta | tb)
    return jac >= 0.6 or (jac >= 0.48 and sim >= 0.55)


def duplicate_ids(stories: list[dict], hours: int = 72) -> dict[str, str]:
    """{duplicate story id: id of the story it repeats}. Within each pair published close together, the earlier
    (or, at the same time, higher-scored) story is the original; the other is the repeat."""
    from datetime import datetime, timedelta

    def when(s: dict) -> datetime:
        return datetime.fromisoformat(s["published_at"].replace("Z", "+00:00"))

    ordered = sorted(stories, key=lambda s: (s["published_at"], -int(s.get("score") or 0)))
    out: dict[str, str] = {}
    span = timedelta(hours=hours)
    for i, s in enumerate(ordered):
        if s["id"] in out:
            continue
        t = when(s)
        for o in ordered[i + 1:]:
            if when(o) - t > span:
                break
            if o["id"] not in out and near_duplicate(s, o):
                out[o["id"]] = s["id"]
    return out


# Frontier Wire doesn't run stories whose subject is sexual abuse or sexual imagery (CSAM, non-consensual or explicit
# deepfakes, "nudify" apps), however newsworthy: the site is read at work and shown on screens in offices.
_UNSUITABLE = re.compile(
    r"child (?:sexual|sex) abuse|\bcsam\b|sexual abuse (?:material|imag)|child (?:sexual|sex) (?:images|imagery|content)"
    r"|non-?consensual|revenge porn|porn|nudif|\bnudes?\b|undress|sexuali[sz]ed|sexually explicit|explicit (?:images|imagery|deepfakes?)"
    r"|intimate (?:images|imagery)|sextortion", re.I)


def unsuitable(item: Any) -> bool:
    """True for a story (or a title) whose subject is sexual abuse or sexual imagery."""
    if isinstance(item, dict):
        item = " ".join(str(item.get(k) or "") for k in ("headline", "summary", "why_it_matters", "title", "text"))
    return bool(_UNSUITABLE.search(str(item or "")))


def scrub(obj: Any, bad_ids: frozenset | set = frozenset()) -> Any:
    """Take those topics out of anything built from stories (briefings, trackers, threads, recaps): list entries
    about them or pointing at a removed story go, and sentences about them go from longer text."""
    if isinstance(obj, dict):
        return {k: scrub(v, bad_ids) for k, v in obj.items()}
    if isinstance(obj, list):
        out = []
        for v in obj:
            if isinstance(v, dict) and (unsuitable(v) or v.get("id") in bad_ids or v.get("story_id") in bad_ids):
                continue
            if isinstance(v, str) and v in bad_ids:
                continue
            out.append(scrub(v, bad_ids))
        return out
    if isinstance(obj, str) and " " in obj and unsuitable(obj):
        return " ".join(p for p in re.split(r"(?<=[.!?])\s+", obj) if not unsuitable(p))
    return obj
