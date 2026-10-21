"""The newsroom run: gather → group → judge → verify → write → check → curate → publish."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from . import prompts as P
from .config import Config
from .llm import LLM, AllProvidersFailed, LimitReached
from .research import Researcher
from .sources import Fetcher, Gdelt, Item, gather
from .store import Store
from .text import canonical_url, domain, extract_image, extract_text, quote_in_text, similar, stable_id

ROLE_RANK = {"lab": 0, "paper": 1, "voice": 2, "news": 3}
STOP = set("""a an and are as at be by for from has have how in into is it its new of on or our that the their
this to was what when which who why will with after over says say said just more than about up out""".split())


def _parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _item_xml(it: Item) -> str:
    who = f' person="{_esc(it.person)}"' if it.person else ""
    return (f'<item id="{it.id}" source="{_esc(it.source_name)}" role="{it.role}"{who} '
            f'published="{it.published or "unknown"}"><title>{_esc(it.title)}</title>'
            f"<snippet>{_esc(it.snippet[:300])}</snippet></item>")


def keywords(title: str, n: int = 5) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]+", title)
    picked = [w for w in words if w.lower() not in STOP and len(w) > 2]
    # prefer names and numbers (capitalised words, versions) first
    picked.sort(key=lambda w: 0 if (w[0].isupper() or any(c.isdigit() for c in w)) else 1)
    return picked[:n]


class Newsroom:
    def __init__(self, cfg: Config, llm: LLM, fetcher: Fetcher, store: Store, now: datetime, gdelt: Gdelt | None = None):
        self.cfg, self.llm, self.fetcher, self.store, self.now = cfg, llm, fetcher, store, now
        self.gdelt = gdelt or Gdelt(fetcher)
        self.report: dict[str, Any] = {
            "started_at": now.isoformat(), "review_mode": cfg.review_mode,
            "providers": llm.configured, "sources": {}, "dropped": [], "written": [], "notes": [],
        }
        self._page_cache: dict[str, str] = {}
        self._images: dict[str, str | None] = {}
        self._research_meta: dict[str, dict[str, Any]] = {}
        self._enriched = 0
        self._texts: dict[str, str] = {}

    # ------------------------------------------------------------ 1. gather
    def collect(self) -> list[Item]:
        lookback = self.cfg.run["lookback_hours"]
        items, status = gather(self.cfg.sources, self.fetcher, now=self.now, lookback_hours=lookback,
                               gdelt=self.gdelt, gdelt_settings=self.cfg.gdelt, lab_domains=self.cfg.lab_domains)
        self.report["sources"] = status
        # Everything fetched in the last 3 days (seen or not) can corroborate a story.
        pool_cutoff = self.now - timedelta(hours=72)
        self._pool = [it for it in items if (_parse_time(it.published) or self.now) >= pool_cutoff]
        cutoff = self.now - timedelta(hours=lookback)
        fresh = []
        for it in items:
            pub = _parse_time(it.published)
            if self.store.is_seen(it.url) or (pub and pub < cutoff):
                continue
            if it.text:
                self._texts[it.url] = it.text
            fresh.append(it)
        self.report["fetched"], self.report["fresh"] = len(items), len(fresh)
        return fresh

    # ------------------------------------------------------------ 2. group duplicates
    @staticmethod
    def group(items: list[Item]) -> dict[str, list[Item]]:
        """Merge identical URLs and near-identical titles into one cluster per event."""
        clusters: dict[str, list[Item]] = {}
        urls: set[str] = set()
        for it in items:
            if it.url in urls:
                continue
            urls.add(it.url)
            home = next((cid for cid, m in clusters.items() if similar(m[0].title, it.title) > 0.85), None)
            if home:
                clusters[home].append(it)
            else:
                clusters[it.id] = [it]
        return clusters

    # ------------------------------------------------------------ 3. judge
    def judge(self, clusters: dict[str, list[Item]]) -> list[tuple[int, str, list[Item]]]:
        ordered = sorted(clusters.items(), key=lambda kv: ROLE_RANK.get(kv[1][0].role, 9))
        ordered = ordered[: self.cfg.run["max_candidates_to_judge"]]
        judged_ids = {cid for cid, _ in ordered}
        # Clusters beyond the cap are left unjudged (and unseen) for the next run.
        for cid in list(clusters):
            if cid not in judged_ids:
                clusters.pop(cid)

        recent = self.store.recent_headlines(self.now)
        prompt = ("Already published (for duplicate checks):\n"
                  + ("\n".join(f'- [{r["id"]}] {r["headline"]}' for r in recent) or "- none")
                  + "\n\nCandidates:\n" + "\n".join(_item_xml(m[0]) for _, m in ordered)
                  + "\n\nReturn one decision per candidate id.")
        answer = self.llm.ask(system=P.JUDGE_SYSTEM, prompt=prompt, schema_name="submit_decisions",
                              schema=P.JUDGE_SCHEMA, max_tokens=6000)
        decisions = {d["id"]: d for d in answer.get("decisions", []) if isinstance(d, dict) and "id" in d}

        for cid, d in list(decisions.items()):
            other = d.get("same_event_as") or ""
            if other and other != cid and other in clusters and cid in clusters:
                clusters[other].extend(clusters.pop(cid))
                decisions.pop(cid)

        kept = []
        for cid, members in clusters.items():
            d = decisions.get(cid)
            if d is None:
                continue
            title = members[0].title
            try:
                score = int(d.get("score", 0))
            except (TypeError, ValueError):
                score = 0
            if d.get("duplicate_of_story"):
                self.report["dropped"].append({"title": title, "reason": f"duplicate of {d['duplicate_of_story']}"})
            elif not d.get("keep") or score < self.cfg.run["min_score"]:
                self.report["dropped"].append({"title": title, "reason": f"score {score}: {d.get('reason', '')}"})
            else:
                members.sort(key=lambda m: ROLE_RANK.get(m.role, 9))
                category = d.get("category") if d.get("category") in P.CATEGORIES else "industry"
                kept.append((score, category, members))
        kept.sort(key=lambda k: -k[0])
        self.report["judged"], self.report["kept"] = len(ordered), len(kept)
        return kept

    # ------------------------------------------------------------ 4. verify
    def research(self, members: list[Item], sources: list[dict[str, str]], domains: set[str]) -> dict[str, Any]:
        """Let the research agent investigate; add the independent sources it confirmed."""
        cfg = self.cfg.settings.get("research", {})
        r = Researcher(self.llm, self.fetcher, self.gdelt, getattr(self, "_pool", []),
                       max_steps=int(cfg.get("max_steps", 5)), page_chars=int(cfg.get("page_chars", 2500)))
        result = r.investigate(members[0].title, members[0].snippet, sources)
        for src in result["sources"]:
            if domain(src["url"]) not in domains:
                sources.append(src)
                domains.add(domain(src["url"]))
        self._texts.update(result["texts"])  # the writer gets the pages the agent read
        self._images.update(result["images"])
        stats = self.report.setdefault("research", {"investigated": 0, "confirmed": 0, "tool_calls": 0})
        stats["investigated"] += 1
        stats["tool_calls"] += result["steps"]
        stats["confirmed"] += result["decision"] == "confirmed"
        self.report.setdefault("research_log", []).append(
            f"{members[0].title[:70]}: {result['decision']} ({'; '.join(result['trail']) or 'no tool use'})")
        self._research_meta[members[0].url] = {"steps": result["steps"], "read": len(result["texts"]),
                                               "decision": result["decision"]}
        return result

    def verify(self, members: list[Item], score: int = 0) -> list[dict[str, str]] | None:
        """Return the story's sources, or None if it can't be confirmed."""
        sources = [{"url": m.url, "publisher": m.source_name, "title": m.title} for m in members]
        official = any(m.role in ("lab", "paper", "voice") for m in members)
        domains = {domain(s["url"]) for s in sources}
        need = self.cfg.guardrails["min_independent_sources"]
        rcfg = self.cfg.settings.get("research", {})
        confirmed_enough = official or len(domains) >= need
        if rcfg.get("enabled", True):
            enrich = (confirmed_enough and score >= int(rcfg.get("enrich_min_score", 8))
                      and self._enriched < int(rcfg.get("enrich_top", 2)))
            if not confirmed_enough or enrich:
                if enrich:
                    self._enriched += 1
                self.research(members, sources, domains)
                return sources if (confirmed_enough or len(domains) >= need) else None
        if confirmed_enough:
            return sources

        words = keywords(members[0].title)
        if len(words) < 2:
            return None

        # 1) Free check first: other outlets among everything fetched this run.
        key = {w.lower() for w in keywords(members[0].title, 8)}
        scored = []
        for it in getattr(self, "_pool", []):
            if domain(it.url) in domains:
                continue
            overlap = len(key & {w.lower() for w in keywords(it.title, 8)})
            if overlap >= 2:  # loose on purpose: the fact-checker model confirms the real matches
                scored.append((overlap, it))
        scored.sort(key=lambda x: -x[0])
        results: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for _, it in scored[:10]:
            if it.url not in seen_urls:
                results.append({"url": it.url, "title": it.title, "domain": it.source_name or domain(it.url)})
                seen_urls.add(it.url)

        # 2) Then GDELT news search, if it's available this run.
        try:
            # broad first (3 key terms), then broader (2) if that finds nothing new
            for n in (3, 2):
                before = len(results)
                for r in self.gdelt.search(" ".join(words[:n]) + " sourcelang:english", timespan="3d", max_records=25):
                    cu = canonical_url(r["url"])
                    if domain(cu) not in domains and cu not in seen_urls:
                        results.append(r)
                        seen_urls.add(cu)
                if len(results) > before or len(words) <= 2:
                    break
        except Exception as e:  # noqa: BLE001
            note = f"GDELT unavailable: {str(e)[:80]}"
            if note not in self.report["notes"]:
                self.report["notes"].append(note)
        results = results[:15]
        if not results:
            return None
        listing = "\n".join(f'<result n="{i}">{_esc(r["title"])} ({r["domain"]})</result>' for i, r in enumerate(results))
        answer = self.llm.ask(
            system=P.VERIFY_SYSTEM, schema_name="submit_matches", schema=P.VERIFY_SCHEMA, max_tokens=800,
            prompt=f"Claim:\n<item>{_esc(members[0].title)} — {_esc(members[0].snippet[:400])}</item>\n\nSearch results:\n{listing}",
        )
        for n in answer.get("matches", []):
            if isinstance(n, int) and 0 <= n < len(results):  # only results we actually got back
                r = results[n]
                if domain(r["url"]) not in domains:
                    sources.append({"url": canonical_url(r["url"]), "publisher": r["domain"], "title": r["title"]})
                    domains.add(domain(r["url"]))
        return sources if len(domains) >= need else None

    # ------------------------------------------------------------ 5. write + quote check
    def _text(self, url: str, fallback: str) -> str:
        if url in self._texts:
            return self._texts[url]
        if url not in self._page_cache:
            try:
                html = self.fetcher.get(url)
                self._page_cache[url] = extract_text(html)
                self._images[url] = extract_image(html, url)
            except Exception:  # noqa: BLE001
                self._page_cache[url] = fallback
        return self._page_cache[url]

    def write(self, score: int, category: str, members: list[Item], sources: list[dict[str, str]]) -> dict[str, Any]:
        lead = members[0]
        snippets = {m.url: m.snippet for m in members}
        limit = self.cfg.run.get("source_text_chars", 3000)
        texts = {s["url"]: self._text(s["url"], snippets.get(s["url"]) or s.get("title", "")) for s in sources[:4]}
        pubs = {s["url"]: s["publisher"] for s in sources}
        who = f"\nPerson (author of the post): {lead.person}" if lead.person else ""
        blocks = "\n\n".join(f'<source url="{u}" publisher="{_esc(pubs[u])}">\n{_esc(t[:limit])}\n</source>' for u, t in texts.items())
        answer = self.llm.ask(
            system=P.WRITE_SYSTEM, schema_name="submit_story", schema=P.WRITE_SCHEMA, max_tokens=1500,
            prompt=f"Suggested category: {category}\nItem: {lead.title}{who}\n\n{blocks}",
        )

        quotes = []
        for q in answer.get("quotes") or []:
            if not isinstance(q, dict) or not q.get("text"):
                continue
            src_url = canonical_url(q.get("source_url", ""))
            if not self.cfg.guardrails["require_verbatim_quotes"] or quote_in_text(q["text"], texts.get(src_url, "")):
                quotes.append({"text": q["text"].strip().strip('"“”'), "speaker": q.get("speaker", ""),
                               "speaker_role": q.get("speaker_role", ""), "source_url": src_url})
            else:
                self.report["notes"].append(f"dropped unverifiable quote ({q.get('speaker')}): {q['text'][:60]}…")

        pub = _parse_time(lead.published) or self.now
        cat = answer.get("category") if answer.get("category") in P.CATEGORIES else category
        return {
            "id": stable_id(lead.url),
            "headline": answer["headline"].strip()[:140],
            "summary": answer["summary"].strip(),
            "why_it_matters": answer["why_it_matters"].strip(),
            "category": cat,
            "lab": answer.get("lab") or lead.lab or "",
            "model_name": answer.get("model_name") or "",
            "model_type": answer.get("model_type") or "",
            "tags": [t for t in answer.get("tags") or [] if isinstance(t, str)][:5],
            "quotes": quotes,
            "score": score,
            "url": lead.url,
            "image": next((self._images[s["url"]] for s in sources[:4] if self._images.get(s["url"])), None),
            "sources": sources,
            "research": self._research_meta.get(lead.url),
            "published_at": min(pub, self.now).isoformat(),
            "created_at": self.now.isoformat(),
        }

    # ------------------------------------------------------------ 6. curate
    def update_labs(self, story: dict[str, Any]) -> None:
        if story["category"] != "models" or not story.get("lab"):
            return
        model = story.get("model_name") or story["headline"]  # fall back to the headline if the writer left it blank
        cur = self.store.labs.get(story["lab"])
        if cur and cur["date"] > story["published_at"]:
            return
        self.store.labs[story["lab"]] = {"model": model[:80], "type": story.get("model_type") or "Other",
                                         "date": story["published_at"], "story_id": story["id"], "url": story["url"]}

    def add_missing_images(self, limit: int = 12) -> None:
        """Look up preview images for recent stories that don't have one yet (no AI calls)."""
        cutoff = (self.now - timedelta(days=self.cfg.run["front_page_days"])).isoformat()
        todo = [s for s in self.store.stories if "image" not in s and s["published_at"] >= cutoff][:limit]
        for story in todo:
            image = None
            for src in story.get("sources", [])[:2]:
                if src["url"] not in self._images:
                    try:
                        self._images[src["url"]] = extract_image(self.fetcher.get(src["url"]), src["url"])
                    except Exception:  # noqa: BLE001
                        self._images[src["url"]] = None
                image = self._images[src["url"]]
                if image:
                    break
            story["image"] = image  # None means "looked, none found" so we don't retry every run

    def build_site(self) -> dict[str, Any]:
        cutoff = self.now - timedelta(days=self.cfg.run["front_page_days"])
        live = sorted((s for s in self.store.stories if datetime.fromisoformat(s["published_at"]) >= cutoff),
                      key=lambda s: s["published_at"], reverse=True)
        window = [s for s in live if datetime.fromisoformat(s["published_at"]) >= self.now - timedelta(hours=36)]
        pool = window or live[:20]
        lead = max(pool, key=lambda s: (s["score"], s["published_at"])) if pool else None

        voices = [{**q, "story_id": s["id"], "headline": s["headline"], "published_at": s["published_at"]}
                  for s in live for q in s.get("quotes", [])]
        labs = sorted(({"lab": n, **i} for n, i in self.store.labs.items()), key=lambda l: l["date"], reverse=True)
        have = {l["lab"] for l in labs}
        labs += [{"lab": n, "model": None, "type": None, "date": None} for n in self.cfg.tracked_labs if n not in have]
        month = self.now.strftime("%Y-%m")
        return {
            "updated_at": self.now.isoformat(),
            "lead": lead,
            "stories": live[:60],  # the site filters by category client-side
            "voices": voices[:6],
            "labs": labs,
            "stats": {
                "stories_this_month": sum(1 for s in self.store.stories if s["published_at"].startswith(month)),
                "model_releases_this_month": sum(1 for s in self.store.stories
                                                 if s["category"] == "models" and s["published_at"].startswith(month)),
                "labs_tracked": len(labs),
            },
        }

    # ------------------------------------------------------------ run
    def run(self) -> dict[str, Any]:
        clusters = self.group(self.collect())
        kept: list[tuple[int, str, list[Item]]] = []
        if clusters:
            try:
                kept = self.judge(clusters)
            except (LimitReached, AllProvidersFailed) as e:
                self.report["notes"].append(f"judging skipped: {e}")
                clusters = {}  # nothing judged → nothing marked seen; retried next run

        # Kept stories not reached this run (per-run cap, limits) stay unseen so the next run picks them up.
        not_reached = {m.url for _, _, ms in kept for m in ms}
        for score, category, members in kept[: self.cfg.run["max_stories_per_run"]]:
            not_reached -= {m.url for m in members}
            try:
                sources = self.verify(members, score)
                if sources is None:
                    self.report["dropped"].append({"title": members[0].title, "reason": "could not verify with enough independent sources"})
                    continue
                story = self.write(score, category, members, sources)
            except (LimitReached, AllProvidersFailed) as e:
                self.report["notes"].append(f"stopped writing: {e}")
                not_reached |= {m.url for m in members}
                break
            except Exception as e:  # noqa: BLE001
                self.report["dropped"].append({"title": members[0].title, "reason": f"error: {type(e).__name__}: {e}"})
                continue
            self.store.add_story(story)
            self.update_labs(story)
            self.report["written"].append({"id": story["id"], "headline": story["headline"], "category": story["category"],
                                           "summary": story["summary"], "url": story["url"],
                                           "sources": len(story["sources"]), "quotes": len(story["quotes"])})

        if not_reached:
            self.report["notes"].append(f"{len(not_reached)} kept item(s) carried over to the next run")
        self.store.mark_seen([m.url for ms in clusters.values() for m in ms if m.url not in not_reached], self.now)
        self.report["ai_requests_run"] = self.llm.limits.run_requests
        self.report["ai_tokens_run"] = self.llm.limits.run_tokens
        self.report["ai_requests_today"] = self.llm.limits.day["requests"]
        self.report["provider_log"] = self.llm.log[-20:]
        self.llm.limits.save()
        self.add_missing_images()
        # Rebuild the lab tracker from every model-release story (oldest first, so the newest wins).
        for st in sorted(self.store.stories, key=lambda x: x["published_at"]):
            self.update_labs(st)
        self.store.save(self.now, self.build_site(), self.report)
        return self.report


def summary_markdown(report: dict[str, Any]) -> str:
    lines = [f"## Frontier Wire newsroom run — {report['started_at']}", ""]
    lines.append(f"Fetched {report.get('fetched', 0)} items · fresh {report.get('fresh', 0)} · judged {report.get('judged', 0)} · "
                 f"kept {report.get('kept', 0)} · **written {len(report['written'])}**")
    lines.append(f"AI: {report.get('ai_requests_run', 0)} requests, {report.get('ai_tokens_run', 0):,} tokens this run · "
                 f"{report.get('ai_requests_today', 0)} requests today · providers: {', '.join(report['providers']) or 'none'}")
    if report.get("research"):
        r = report["research"]
        lines.append(f"Research agent: investigated {r['investigated']} stories with {r['tool_calls']} tool calls, "
                     f"confirmed {r['confirmed']}")
    lines += ["", "### New stories"]
    lines += [f"- **{w['category']}** — [{w['headline']}]({w['url']})  \n  {w['summary']}  \n"
              f"  _{w['sources']} source(s), {w['quotes']} verified quote(s)_" for w in report["written"]] or ["- none"]
    if report["dropped"]:
        lines += ["", "<details><summary>Dropped</summary>", ""]
        lines += [f"- {d['title']} — {d['reason']}" for d in report["dropped"][:60]] + ["", "</details>"]
    failed = {k: v for k, v in report["sources"].items() if not v.startswith("ok") or "failed" in v}
    if failed:
        lines += ["", "### Sources with problems"] + [f"- `{k}`: {v}" for k, v in failed.items()]
    if report.get("research_log"):
        lines += ["", "<details><summary>Research agent's work</summary>", ""]
        lines += [f"- {l}" for l in report["research_log"]] + ["", "</details>"]
    if report["notes"] or report.get("provider_log"):
        lines += ["", "### Notes"] + [f"- {n}" for n in report["notes"] + report.get("provider_log", [])]
    return "\n".join(lines) + "\n"
