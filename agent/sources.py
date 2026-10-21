"""Gather candidate items from feeds, free news/research APIs and listing pages."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol
from urllib.parse import quote, quote_plus, urljoin, urlparse

import feedparser
from bs4 import BeautifulSoup

from .text import canonical_url, extract_published, extract_text, stable_id

USER_AGENT = "FrontierWireBot/0.2 (AI news aggregation; contact via GitHub repo)"
QUANTISED = re.compile(r"gguf|awq|gptq|exl2|mlx|bnb|int4|int8|4bit|8bit|-fp8-dynamic", re.I)


@dataclass
class Item:
    url: str
    title: str
    source_id: str
    source_name: str
    role: str  # lab | paper | news | voice
    snippet: str = ""
    published: str | None = None  # ISO 8601
    lab: str | None = None
    person: str | None = None
    text: str = ""  # full text when the source gives it (posts), used instead of fetching the page
    id: str = field(default="")

    def __post_init__(self) -> None:
        self.url = canonical_url(self.url)
        if not self.id:
            self.id = stable_id(self.url)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Fetcher(Protocol):
    def get(self, url: str) -> str: ...


class HttpFetcher:
    """Real HTTP fetcher (used in GitHub Actions)."""

    def __init__(self, timeout: float = 20.0):
        import httpx

        self._client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    def get(self, url: str) -> str:
        r = self._client.get(url)
        r.raise_for_status()
        return r.text


def _iso_struct(struct: time.struct_time | None) -> str | None:
    if not struct:
        return None
    return datetime(*struct[:6], tzinfo=timezone.utc).isoformat()


def _clean(html_snippet: str, limit: int = 600) -> str:
    return extract_text(f"<body>{html_snippet}</body>", limit=limit)


def _one_line(s: str, limit: int = 200) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= limit else s[: limit - 1].rsplit(" ", 1)[0] + "…"


# ------------------------------------------------------------------ feeds & pages
def parse_feed(raw: str, src: dict[str, Any]) -> list[Item]:
    feed = feedparser.parse(raw)
    items = []
    for e in feed.entries:
        link, title = e.get("link"), (e.get("title") or "").strip()
        if not link or not title:
            continue
        items.append(Item(
            url=link, title=_one_line(title), source_id=src["id"], source_name=src["name"], role=src["role"],
            snippet=_clean(e.get("summary", "")),
            published=_iso_struct(e.get("published_parsed") or e.get("updated_parsed")),
            lab=src.get("lab"), person=src.get("person"),
        ))
    return items


def arxiv_url(src: dict[str, Any]) -> str:
    return ("http://export.arxiv.org/api/query?search_query=" + quote_plus(src["query"])
            + f"&sortBy=submittedDate&sortOrder=descending&max_results={src.get('max_results', 30)}")


def parse_page(raw: str, src: dict[str, Any], fetcher: Fetcher, max_links: int = 6) -> list[Item]:
    """Listing page with no feed: take article links, then read each one's publish date."""
    soup = BeautifulSoup(raw, "html.parser")
    pattern = re.compile(src["link_pattern"])
    seen: set[str] = set()
    items: list[Item] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(src["url"], a["href"]).split("#")[0]
        if not pattern.match(href) or href in seen:
            continue
        seen.add(href)
        title = _one_line(a.get_text(" ", strip=True))
        if len(title) < 8:
            continue
        published = None
        try:
            published = extract_published(fetcher.get(href))
        except Exception:  # noqa: BLE001
            pass
        items.append(Item(url=href, title=title, source_id=src["id"], source_name=src["name"],
                          role=src["role"], published=published, lab=src.get("lab"), person=src.get("person")))
        if len(items) >= max_links:
            break
    return items


# ------------------------------------------------------------------ GDELT
class Gdelt:
    """GDELT DOC 2.0 article search. Free, no key; asks for at most one request every 5 seconds."""

    BASE = "https://api.gdeltproject.org/api/v2/doc/doc"

    def __init__(self, fetcher: Fetcher, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.fetcher, self.sleep, self.clock = fetcher, sleep, clock
        self._last = -1e9

    def search(self, query: str, timespan: str = "1d", max_records: int = 50) -> list[dict[str, Any]]:
        wait = 5.5 - (self.clock() - self._last)
        if wait > 0:
            self.sleep(wait)
        self._last = self.clock()
        url = (f"{self.BASE}?query={quote(query)}&mode=artlist&format=json"
               f"&maxrecords={max_records}&timespan={timespan}&sort=datedesc")
        raw = self.fetcher.get(url)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"GDELT returned non-JSON: {raw[:120]}") from exc
        out = []
        for a in data.get("articles", []) or []:
            if not a.get("url") or not a.get("title"):
                continue
            seen = a.get("seendate")  # e.g. 20261021T101500Z
            iso = None
            if seen:
                try:
                    iso = datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    pass
            out.append({"url": a["url"], "title": _one_line(a["title"]), "domain": a.get("domain", ""), "published": iso})
        return out


def from_gdelt(src: dict[str, Any], gdelt: Gdelt, settings: dict[str, Any], lookback_hours: int) -> list[Item]:
    span = f"{max(1, min(lookback_hours, 72))}h"
    rows = gdelt.search(settings["query"], timespan=span, max_records=settings.get("max_records", 50))
    return [Item(url=r["url"], title=r["title"], source_id=src["id"], source_name=r["domain"] or "GDELT",
                 role=src["role"], published=r["published"]) for r in rows]


# ------------------------------------------------------------------ Hacker News
def from_hn(src: dict[str, Any], fetcher: Fetcher, now: datetime, lookback_hours: int) -> list[Item]:
    since = int((now - timedelta(hours=lookback_hours)).timestamp())
    seen: dict[str, Item] = {}
    for q in src.get("queries", ["AI"]):
        url = ("https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=30"
               f"&query={quote_plus(q)}&numericFilters=created_at_i>{since},points>={src.get('min_points', 100)}")
        for h in json.loads(fetcher.get(url)).get("hits", []):
            if not h.get("url") or not h.get("title"):
                continue
            it = Item(url=h["url"], title=_one_line(h["title"]), source_id=src["id"],
                      source_name=urlparse(h["url"]).netloc.removeprefix("www."), role=src["role"],
                      snippet=f"{h.get('points', 0)} points on Hacker News", published=h.get("created_at"))
            seen.setdefault(it.url, it)
    return list(seen.values())


# ------------------------------------------------------------------ Hugging Face
def from_hf_models(src: dict[str, Any], fetcher: Fetcher) -> list[Item]:
    items = []
    for org, lab in src["orgs"].items():
        url = f"https://huggingface.co/api/models?author={quote(org)}&sort=createdAt&direction=-1&limit={src.get('per_org', 5)}"
        for m in json.loads(fetcher.get(url)):
            mid = m.get("id") or m.get("modelId")
            if not mid or QUANTISED.search(mid):
                continue
            name = mid.split("/", 1)[-1]
            details = ", ".join(x for x in [m.get("pipeline_tag") or "", f"{m.get('likes', 0)} likes"] if x)
            items.append(Item(url=f"https://huggingface.co/{mid}", title=f"{lab} publishes {name} on Hugging Face",
                              source_id=src["id"], source_name="Hugging Face", role="lab", lab=lab,
                              snippet=f"New model upload: {mid} ({details})", published=m.get("createdAt")))
    return items


def from_hf_papers(src: dict[str, Any], fetcher: Fetcher) -> list[Item]:
    items = []
    for row in json.loads(fetcher.get("https://huggingface.co/api/daily_papers?limit=50")):
        p = row.get("paper") or {}
        if not p.get("id") or (p.get("upvotes") or 0) < src.get("min_upvotes", 10):
            continue
        items.append(Item(url=f"https://arxiv.org/abs/{p['id']}", title=_one_line(p.get("title") or row.get("title", "")),
                          source_id=src["id"], source_name="Hugging Face daily papers", role="paper",
                          snippet=f"{p.get('upvotes')} upvotes. " + _one_line(p.get("summary", ""), 450),
                          published=row.get("publishedAt") or p.get("publishedAt")))
    return items


# ------------------------------------------------------------------ Bluesky
def from_bluesky(src: dict[str, Any], fetcher: Fetcher) -> tuple[list[Item], list[str]]:
    items, failed = [], []
    for handle, person in src["accounts"].items():
        url = ("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
               f"?actor={quote(handle)}&limit={src.get('per_account', 10)}&filter=posts_no_replies")
        try:
            feed = json.loads(fetcher.get(url)).get("feed", [])
        except Exception:  # noqa: BLE001
            failed.append(handle)
            continue
        for row in feed:
            post = row.get("post") or {}
            if row.get("reason") or (post.get("author") or {}).get("handle") != handle:
                continue  # skip reposts of other people
            text = ((post.get("record") or {}).get("text") or "").strip()
            if len(text) < 40:
                continue
            rkey = post.get("uri", "").rsplit("/", 1)[-1]
            items.append(Item(url=f"https://bsky.app/profile/{handle}/post/{rkey}", title=f"{person}: {_one_line(text, 140)}",
                              source_id=src["id"], source_name=f"{person} on Bluesky", role="voice", person=person,
                              snippet=_one_line(text, 600), text=text,
                              published=(post.get("record") or {}).get("createdAt")))
    return items, failed


# ------------------------------------------------------------------ gather
def lab_for(url: str, lab_domains: dict[str, str]) -> str | None:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for dom, lab in lab_domains.items():
        if host == dom or host.endswith("." + dom):
            return lab
    return None


def gather(sources: list[dict[str, Any]], fetcher: Fetcher, *, now: datetime, lookback_hours: int,
           gdelt: Gdelt, gdelt_settings: dict[str, Any], lab_domains: dict[str, str]) -> tuple[list[Item], dict[str, str]]:
    """Fetch every source. One failing source never stops the run; failures are reported."""
    items: list[Item] = []
    status: dict[str, str] = {}
    for src in sources:
        try:
            kind, note = src["kind"], ""
            if kind == "rss":
                got = parse_feed(fetcher.get(src["url"]), src)
            elif kind == "arxiv":
                got = parse_feed(fetcher.get(arxiv_url(src)), src)
            elif kind == "page":
                got = parse_page(fetcher.get(src["url"]), src, fetcher)
            elif kind == "gdelt":
                got = from_gdelt(src, gdelt, gdelt_settings, lookback_hours)
            elif kind == "hn":
                got = from_hn(src, fetcher, now, lookback_hours)
            elif kind == "hf_models":
                got = from_hf_models(src, fetcher)
            elif kind == "hf_papers":
                got = from_hf_papers(src, fetcher)
            elif kind == "bluesky":
                got, failed = from_bluesky(src, fetcher)
                note = f"; failed accounts: {', '.join(failed)}" if failed else ""
            else:
                raise ValueError(f"unknown kind {kind}")
            items.extend(got)
            status[src["id"]] = f"ok ({len(got)}){note}"
        except Exception as exc:  # noqa: BLE001
            status[src["id"]] = f"failed: {type(exc).__name__}: {str(exc)[:120]}"

    # A link to a lab's own site is a primary source, wherever we found it.
    for it in items:
        if it.role == "news":
            lab = lab_for(it.url, lab_domains)
            if lab:
                it.role, it.lab = "lab", lab
    return items, status
