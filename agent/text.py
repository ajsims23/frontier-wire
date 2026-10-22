"""Text helpers: page extraction, URL/domain handling, quote checking, similarity."""
from __future__ import annotations

import hashlib
import re
import unicodedata
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
