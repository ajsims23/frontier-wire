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
from .tagging import SECTORS

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
    opp: dict = read("opportunities.json", {})
    desk_briefs: dict = read("desk_briefings.json", {})
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


    # ---------------------------------------------------------------- desks: India, Business, Opportunities, Sectors
    def listing(items: list[dict]) -> list[dict]:
        return [{**it, "date": short_date(it["published_at"]), "cat_name": TAG.get(it["category"], "")} for it in items]

    def bars(pairs: list[tuple[str, int, str]]) -> list[dict]:
        top = max([n for _, n, _ in pairs] or [1]) or 1
        return [{"label": l, "n": n, "href": h, "pct": max(4, round(n / top * 100))} for l, n, h in pairs]

    month = now - timedelta(days=30)
    recent30 = [s for s in stories if _dt(s["published_at"]) >= month]
    newest_first = sorted(stories, key=lambda x: x["published_at"], reverse=True)

    def page(path: str, tpl: str, **ctx: Any) -> None:
        f = out / path / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(env.get_template(tpl).render(**common, root="../" * path.count("/") + "../", **ctx))
        urls.append(f"{base}{path}/")

    # India
    from .editorial import is_india
    india = [s for s in newest_first if is_india(s)]
    india_jobs = [{**j, "company": c} for c, v in (opp.get("jobs") or {}).items() for j in v.get("india", [])][:12]
    india_cos: dict[str, int] = {}
    for s in india:
        for name in filter(None, [(s.get("deal") or {}).get("company"), s.get("lab")]):
            india_cos[name] = india_cos.get(name, 0) + 1
    page("india", "desk.html", heading="AI in India", title="AI in India: startups, policy and adoption | Frontier Wire",
         description="Indian AI news: startups and funding, government policy, IndiaAI Mission and adoption, checked against sources.",
         canonical=f"{base}india/", og_image=f"{base}og/home.png",
         intro="Indian AI startups and funding, government policy, and how Indian companies are adopting AI. From Indian outlets and global coverage, every story checked against its sources.",
         stats=[{"label": "India stories in 30 days", "value": sum(1 for s in india if _dt(s["published_at"]) >= month)},
                {"label": "Funding and deals", "value": sum(1 for s in india if s.get("deal"))},
                {"label": "AI lab roles in India", "value": len(india_jobs), "href": "../opportunities/#ind-h"}],
         desk_brief=desk_briefs.get("india"), brief_title="India today",
         chart=activity_chart(india, now), chart_caption="India stories per day, last 30 days",
         chart_label=f"{len(india)} India stories",
         bars=bars([(k, v, "") for k, v in sorted(india_cos.items(), key=lambda kv: -kv[1])[:7]]),
         bars_caption="Companies in the news", bars_sub="India stories",
         extra_jobs=india_jobs[:8], items=listing(india[:40]), list_title="India stories",
         empty_text="India stories appear here as the newsroom finds them.")

    # Business
    deal_names = {"funding": "Funding", "acquisition": "Acquisition", "partnership": "Partnership", "enterprise_deal": "Enterprise deal",
                  "earnings": "Earnings", "ipo": "IPO", "layoffs": "Layoffs", "investment": "Investment"}
    deals = [s for s in newest_first if s.get("deal")]
    biz = [s for s in newest_first if s.get("deal") or s["category"] == "industry"]
    by_type: dict[str, int] = {}
    for s in deals:
        if _dt(s["published_at"]) >= month:
            by_type[deal_names[s["deal"]["type"]]] = by_type.get(deal_names[s["deal"]["type"]], 0) + 1
    disclosed = sorted((s for s in deals if s["deal"].get("usd")), key=lambda s: -s["deal"]["usd"])
    page("business", "desk.html", heading="AI in business", title="AI business: funding, deals and partnerships | Frontier Wire",
         description="AI funding rounds, acquisitions, partnerships and enterprise deals, with amounts only when sources state them.",
         canonical=f"{base}business/", og_image=f"{base}og/home.png",
         intro="Funding rounds, acquisitions, partnerships and enterprise deals across AI. Our agent extracts the deal details from each story and shows an amount only when the story states it.",
         stats=[{"label": "Deals in 30 days", "value": sum(by_type.values())},
                {"label": "Largest disclosed", "value": (disclosed[0]["deal"]["amount"] + (f", {disclosed[0]['deal']['company']}" if disclosed[0]["deal"]["company"] else "")) if disclosed else "None yet"},
                {"label": "Business stories in 30 days", "value": sum(1 for s in biz if _dt(s["published_at"]) >= month)}],
         chart=activity_chart(deals, now), chart_caption="Deals reported per day, last 30 days", chart_label=f"{len(deals)} deals",
         bars=bars(sorted(((k, v, "") for k, v in by_type.items()), key=lambda r: -r[1])), bars_caption="Deals by type", bars_sub="Last 30 days",
         deals=[{"id": s["id"], "date": short_date(s["published_at"]), "company": s["deal"].get("company"), "type_name": deal_names[s["deal"]["type"]],
                 "amount": s["deal"].get("amount"), "headline": s["headline"]} for s in deals[:30]],
         items=listing(biz[:40]), list_title="Business stories", empty_text="Business stories appear here as the newsroom finds them.")

    # Opportunities
    jobs = opp.get("jobs") or {}
    all_roles = [{**j, "company": c} for c, v in jobs.items() for j in v.get("newest", [])]
    boards = {b["company"]: b for b in cfg.extra.get("job_boards", [])}
    page("opportunities", "opportunities.html", title="AI jobs, internships and courses | Frontier Wire",
         description="Open roles and internships at AI labs from their official job boards, plus new AI courses and certifications.",
         canonical=f"{base}opportunities/", og_image=f"{base}og/home.png",
         labs_count=len(jobs), total_roles=sum(v.get("total", 0) for v in jobs.values()),
         role_bars=bars(sorted(((c, v.get("total", 0), v.get("careers", "")) for c, v in jobs.items()), key=lambda r: -r[1])),
         newest=sorted(all_roles, key=lambda j: j.get("posted", ""), reverse=True)[:10],
         interns=[{**j, "company": c} for c, v in jobs.items() for j in v.get("interns", [])][:40],
         india=[{**j, "company": c} for c, v in jobs.items() for j in v.get("india", [])][:40],
         courses=[{**c, "found": short_date(c["found_at"])} for c in opp.get("courses", [])],
         labs=[{"company": c, "total": v.get("total", 0), "careers": v.get("careers", ""), "board": ""} for c, v in sorted(jobs.items())])

    # Sectors
    sector_rows = []
    for key, name in SECTORS.items():
        items = [s for s in newest_first if key in (s.get("sectors") or [])]
        n30 = sum(1 for s in items if _dt(s["published_at"]) >= month)
        sector_rows.append({"slug": key, "name": name, "count": n30, "latest": items[0]["headline"] if items else ""})
        page(f"sector/{key}", "desk.html", heading=f"AI in {name.lower() if key not in ('legal',) else 'law'}", crumb=name,
             title=f"AI in {name.lower()} | Frontier Wire", description=f"How AI is changing {name.lower()}: news and developments, checked against sources.",
             canonical=f"{base}sector/{key}/", og_image=f"{base}og/home.png",
             intro=f"Every Frontier Wire story our agent tagged as affecting {name.lower()}, newest first.",
             stats=[{"label": "Stories in 30 days", "value": n30}, {"label": "All-time", "value": len(items)}],
             chart=activity_chart(items, now), chart_caption="Stories per day, last 30 days", chart_label=f"{n30} stories in 30 days",
             items=listing(items[:60]), empty_text=f"No {name.lower()} stories yet. The newsroom checks every three hours.")
    sector_rows.sort(key=lambda r: -r["count"])
    page("sectors", "sectors.html", title="AI by sector | Frontier Wire", description="How AI is changing each industry, from healthcare to finance.",
         canonical=f"{base}sectors/", og_image=f"{base}og/home.png", sectors=sector_rows,
         bars=bars([(r["name"], r["count"], f"../sector/{r['slug']}/") for r in sector_rows if r["count"]][:10]))

    # small summary for the home page's Desks section
    week = now - timedelta(days=7)
    desks_summary = {
        "india": {"count7": sum(1 for s in india if _dt(s["published_at"]) >= week),
                  "latest": [{"id": s["id"], "headline": s["headline"]} for s in india[:3]], "brief": (desk_briefs.get("india") or {}).get("one_line", "")},
        "business": {"deals7": sum(1 for s in deals if _dt(s["published_at"]) >= week),
                     "days": [b["n"] for b in activity_chart(deals, now, days=14)["bars"]],
                     "largest": ({"amount": disclosed[0]["deal"]["amount"], "company": disclosed[0]["deal"]["company"], "id": disclosed[0]["id"]} if disclosed else None)},
        "opportunities": {"roles": sum(v.get("total", 0) for v in jobs.values()), "labs": len(jobs),
                          "interns": sum(len(v.get("interns", [])) for v in jobs.values()),
                          "india": sum(len(v.get("india", [])) for v in jobs.values()), "courses": len(opp.get("courses", []))},
        "sectors": [{"slug": r["slug"], "name": r["name"], "count": r["count"]} for r in sector_rows if r["count"]][:5],
    }
    (out / "data" / "desks.json").write_text(json.dumps(desks_summary, ensure_ascii=False))

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
