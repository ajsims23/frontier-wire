"""Build the static website into _site/: home page, a page per story, a page per lab,
link-preview images, sitemap and robots.txt.

    python -m agent.build            # writes _site/
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .cards import art_image, home_card, story_card
from .config import ROOT, load_config

CAT_NAME = {"models": "Model releases", "research": "Research", "policy": "Policy", "safety": "Safety",
            "industry": "Industry", "voices": "Commentary"}
TAG = {"models": "Model release", "research": "Research", "policy": "Policy", "safety": "Safety",
       "industry": "Industry", "voices": "Commentary"}
TOPIC_OF = {"models": "models", "research": "research", "policy": "policy", "safety": "policy",
            "industry": "industry", "voices": "voices"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "lab"


def _dt(iso: str) -> datetime:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def human_date(iso: str) -> str:
    return _dt(iso).strftime("%-d %b %Y, %H:%M UTC")


def short_date(iso: str) -> str:
    return _dt(iso).strftime("%-d %b")


def site_settings(cfg: Any) -> dict[str, str]:
    s = dict(cfg.settings.get("site") or {})
    base = os.environ.get("SITE_URL") or (f"https://{s['custom_domain']}/" if s.get("custom_domain") else s.get("base_url", ""))
    s["base_url"] = (base or "https://example.github.io/frontier-wire/").rstrip("/") + "/"
    for key, env in (("goatcounter", "GOATCOUNTER_CODE"), ("newsletter", "NEWSLETTER_USERNAME")):
        s[key] = (os.environ.get(env) or s.get(key) or "").strip()
    return s


def analytics_tag(code: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]{2,40}", code or ""):
        return ""
    return (f'<script data-goatcounter="https://{code}.goatcounter.com/count" async '
            f'src="https://gc.zgo.at/count.js"></script>')


def activity_chart(items: list[dict], now: datetime, days: int = 30) -> dict[str, Any]:
    counts = [0] * days
    start = (now - timedelta(days=days - 1)).date()
    for it in items:
        idx = (_dt(it["published_at"]).date() - start).days
        if 0 <= idx < days:
            counts[idx] += 1
    w, h, pad_b = 600, 140, 2
    bw = w / days
    top = max(counts) or 1
    bars, ticks = [], []
    for i, n in enumerate(counts):
        day = start + timedelta(days=i)
        bh = 4 if n == 0 else max(8, (h - pad_b - 8) * n / top)
        bars.append({"x": round(i * bw + 2, 1), "w": round(bw - 4, 1), "y": round(h - pad_b - bh, 1), "h": round(bh, 1),
                     "n": n, "label": day.strftime("%-d %b")})
        if (i % 7 == 0 and days - 1 - i >= 4) or i == days - 1:
            ticks.append({"pct": round((i + 0.5) / days * 100, 2), "label": "Today" if i == days - 1 else day.strftime("%-d %b")})
    peak = max(range(days), key=lambda i: counts[i])
    return {"w": w, "h": h, "bars": bars, "ticks": ticks, "peak_label": bars[peak]["label"]}


def build(out: Path, data_dir: Path | None = None, now: datetime | None = None) -> dict[str, int]:
    cfg = load_config(data_dir=data_dir)
    site = site_settings(cfg)
    base = site["base_url"]
    now = now or datetime.now(timezone.utc)
    data = cfg.data_dir

    def read(name: str, default: Any) -> Any:
        p = data / name
        return json.loads(p.read_text()) if p.exists() else default

    stories: list[dict] = read("stories.json", [])
    for st in stories:
        st["lab"] = cfg.canon_lab(st.get("lab"))
    home: dict = read("site.json", {"stories": [], "labs": [], "stats": {}})
    threads: dict = read("threads.json", {})
    labs_info: dict = read("labs.json", {})
    by_id = {s["id"]: s for s in stories}

    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "site", out, ignore=shutil.ignore_patterns("templates"))
    (out / "data").mkdir(exist_ok=True)
    if (data / "feed.xml").exists():
        shutil.copy(data / "feed.xml", out / "data" / "feed.xml")
    for st in home.get("stories", []) + ([home["lead"]] if home.get("lead") else []):
        st["lab"] = cfg.canon_lab(st.get("lab"))
    (out / "data" / "site.json").write_text(json.dumps(home, ensure_ascii=False))

    env = Environment(loader=FileSystemLoader(ROOT / "site" / "templates"), autoescape=select_autoescape(["html"]))
    theme_boot = (ROOT / "site" / "theme-boot.js").read_text()
    common = {"year": now.year, "theme_boot": theme_boot, "analytics": analytics_tag(site["goatcounter"]),
              "newsletter": site["newsletter"] if re.fullmatch(r"[A-Za-z0-9_-]{2,60}", site["newsletter"] or "") else ""}

    # ---------------------------------------------------------------- story pages
    urls = [base]
    for s in stories:
        og_png = out / "og" / f"{s['id']}.png"
        story_card(s, og_png)
        art_image(s, out / "art" / f"{s['id']}.png")
        tid = s.get("thread")
        thread = None
        if tid and tid in threads:
            items = sorted((by_id[i] for i in threads[tid]["story_ids"] if i in by_id), key=lambda x: x["published_at"], reverse=True)
            if len(items) >= 2:
                thread = {"title": threads[tid]["title"],
                          "stories": [{"id": t["id"], "headline": t["headline"], "category": t["category"],
                                       "when": short_date(t["published_at"])} for t in items]}
        related = [r for r in stories if r["id"] != s["id"] and ((s.get("lab") and r.get("lab") == s["lab"]) or
                                                                  (not s.get("lab") and r["category"] == s["category"]))]
        related = sorted(related, key=lambda r: r["published_at"], reverse=True)[:3]
        canonical = f"{base}story/{s['id']}/"
        jsonld = json.dumps({
            "@context": "https://schema.org", "@type": "NewsArticle", "headline": s["headline"][:110],
            "description": s["summary"], "datePublished": s["published_at"], "dateModified": s.get("created_at", s["published_at"]),
            "image": [f"{base}og/{s['id']}.png"], "mainEntityOfPage": canonical,
            "publisher": {"@type": "Organization", "name": "Frontier Wire"},
            "citation": [src["url"] for src in s.get("sources", [])],
        }, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        credit = next((src["publisher"] for src in s.get("sources", []) if src.get("publisher")), "source")
        html = env.get_template("story.html").render(
            **common, s=s, root="../../", title=f"{s['headline']} | Frontier Wire", og_title=s["headline"],
            description=s["summary"][:300], canonical=canonical, og_type="article", og_image=f"{base}og/{s['id']}.png",
            og_rel=f"../../art/{s['id']}.png", jsonld=jsonld, cat_name=TAG.get(s["category"], s["category"]),
            topic=TOPIC_OF.get(s["category"], "all"), lab_slug=slug(s.get("lab", "")), published_human=human_date(s["published_at"]),
            image_credit=credit, thread=thread,
            related=[{**r, "when": short_date(r["published_at"]), "cat_name": TAG.get(r["category"], "")} for r in related],
        )
        page = out / "story" / s["id"] / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(html)
        urls.append(canonical)

    # ---------------------------------------------------------------- lab pages
    labs = sorted(set(cfg.tracked_labs) | {s["lab"] for s in stories if s.get("lab")})
    lab_index = []
    for lab in labs:
        items = sorted((s for s in stories if s.get("lab") == lab), key=lambda x: x["published_at"], reverse=True)
        recent = [s for s in items if _dt(s["published_at"]) >= now - timedelta(days=30)]
        rel = labs_info.get(lab)
        release = {"model": (rel["model"][:57] + "…") if len(rel["model"]) > 58 else rel["model"], "href": f"../../story/{rel['story_id']}/"} if rel and rel.get("story_id") in by_id else None
        html = env.get_template("lab.html").render(
            **common, root="../../", lab=lab, title=f"{lab}: AI news and releases | Frontier Wire",
            description=f"Everything Frontier Wire has covered about {lab}: model releases, research and news, with sources.",
            canonical=f"{base}lab/{slug(lab)}/", og_image=f"{base}og/home.png",
            count30=len(recent), release=release, last_seen=short_date(items[0]["published_at"]) if items else "",
            chart=activity_chart(items, now),
            items=[{**it, "date": short_date(it["published_at"]), "cat_name": TAG.get(it["category"], "")} for it in items],
        )
        page = out / "lab" / slug(lab) / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(html)
        urls.append(f"{base}lab/{slug(lab)}/")
        lab_index.append({"lab": lab, "slug": slug(lab), "count7": sum(1 for s in items if _dt(s["published_at"]) >= now - timedelta(days=7))})

    # ---------------------------------------------------------------- home page: meta, preview card, extras
    briefing = home.get("briefing") or {}
    home_card(briefing.get("one_line", ""), out / "og" / "home.png")
    desc = briefing.get("one_line") or "Frontier model releases, research, policy and commentary, checked against sources. Updated every three hours."
    meta = env.from_string(
        '<link rel="canonical" href="{{ base }}">\n'
        '<meta property="og:site_name" content="Frontier Wire">\n<meta property="og:type" content="website">\n'
        '<meta property="og:title" content="Frontier Wire: today in AI">\n<meta property="og:description" content="{{ desc }}">\n'
        '<meta property="og:url" content="{{ base }}">\n<meta property="og:image" content="{{ base }}og/home.png">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        '<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:image" content="{{ base }}og/home.png">'
    ).render(base=base, desc=desc)
    index = (out / "index.html").read_text()
    index = index.replace("<!--META-->", meta)
    index = index.replace("<!--NEWSLETTER-->", env.get_template("_newsletter.html").render(**common))
    index = index.replace("<!--ANALYTICS-->", common["analytics"])
    (out / "index.html").write_text(index)
    (out / "data" / "labs-index.json").write_text(json.dumps(lab_index, indent=1))

    # ---------------------------------------------------------------- search engines + custom domain
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n")
    (out / ".nojekyll").write_text("")
    if site.get("custom_domain"):
        (out / "CNAME").write_text(site["custom_domain"].strip() + "\n")
    return {"stories": len(stories), "labs": len(labs), "urls": len(urls)}


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m agent.build")
    ap.add_argument("--out", default=str(ROOT / "_site"))
    args = ap.parse_args()
    print(build(Path(args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
