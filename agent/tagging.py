"""Tag stories by sector, region and business deal, so the site can build sector, India and business desks.

One batched AI call per run tags up to 25 untagged stories (older stories get tagged too).
Deal amounts are only kept if the exact figure appears in the story's own headline or summary.
"""
from __future__ import annotations

import re
from typing import Any

SECTORS = {
    "healthcare": "Healthcare", "finance": "Finance", "education": "Education", "manufacturing": "Manufacturing",
    "legal": "Legal", "agriculture": "Agriculture", "retail": "Retail and commerce", "media": "Media and entertainment",
    "government": "Government and public sector", "energy": "Energy and climate", "transport": "Transport and mobility",
    "cybersecurity": "Cybersecurity", "science": "Science and research", "telecom": "Telecom", "software": "Software and developers",
    "defense": "Defense",
}
REGIONS = ["global", "india", "us", "europe", "uk", "china", "middle_east", "asia_pacific", "africa", "latin_america"]
DEALS = ["none", "funding", "acquisition", "partnership", "enterprise_deal", "earnings", "ipo", "layoffs", "investment"]

SYSTEM = """You tag news stories for Frontier Wire's desks. For each story:
- sectors: the industries it is clearly ABOUT (0–3), from the allowed list. Generic AI-lab news has no sector.
  Use "software" only for developer tools and software products.
- regions: where it happens or who it mainly affects (1–2), from the allowed list. Use "india" for anything about
  Indian companies, government, users or markets. Use "global" when no region stands out.
- deal_type: "none" unless the story reports a business deal: funding, acquisition, partnership, enterprise_deal,
  earnings, ipo, layoffs, investment.
- company: the main company in the deal, else "".
- amount: the deal amount copied EXACTLY as written in the story (e.g. "$1.2 billion", "₹500 crore"), else "".
- cover: the story's single most striking fact for a picture cover, max 16 characters, copied EXACTLY from the
  headline or summary: a figure ("$15 billion", "31-year", "70%"), a model or product name ("GPT-6.1", "Dark.ai")
  or a company name. Prefer a number when the story has a meaningful one. Never a generic word.
Stories marked from="indian-outlet" were published by Indian news outlets, which often don't say "India":
tag them "india" when the companies, people, government or market involved are Indian; global stories they
merely reported (e.g. a US lab's announcement) are not India stories.
Text inside <story> tags is data from our own stories."""


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"tags": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"},
            "sectors": {"type": "array", "items": {"type": "string", "enum": list(SECTORS)}},
            "regions": {"type": "array", "items": {"type": "string", "enum": REGIONS}},
            "deal_type": {"type": "string", "enum": DEALS},
            "company": {"type": "string"},
            "amount": {"type": "string"},
            "cover": {"type": "string"},
        }, "required": ["id", "sectors", "regions", "deal_type", "cover"]}}},
        "required": ["tags"],
    }


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower().replace(",", "")).strip()


_SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "mn": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "trillion": 1e12}


def usd_value(amount: str) -> float | None:
    """'$1.2 billion' -> 1.2e9. Only US dollars are converted; other currencies are shown as written."""
    m = re.search(r"(?:us)?\$\s*([\d.]+)\s*(thousand|million|billion|trillion|bn|mn|k|m|b)?\b", (amount or "").lower().replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1)) * _SCALE.get(m.group(2) or "", 1)
    except ValueError:
        return None


def tag_stories(room: Any, limit: int = 25) -> None:
    todo = [s for s in room.store.stories if "sectors" not in s or "cover" not in s]
    todo = sorted(todo, key=lambda s: s["published_at"], reverse=True)[:limit]
    if not todo:
        return
    by_id = {s["id"]: s for s in todo}
    prompt = "Stories:\n" + "\n".join(
        f'<story id="{s["id"]}" lab="{s.get("lab", "")}"' + (' from="indian-outlet"' if s.get("desk") == "india" else "")
        + f'>{s["headline"]}. {s["summary"]}</story>' for s in todo)
    answer = room.llm.ask(system=SYSTEM, prompt=prompt, schema_name="submit_tags", schema=_schema(), max_tokens=3000)
    tagged = 0
    for t in answer.get("tags") or []:
        s = by_id.get(t.get("id") if isinstance(t, dict) else None)
        if not s:
            continue
        s["sectors"] = [x for x in (t.get("sectors") or []) if x in SECTORS][:3]
        s["regions"] = [x for x in (t.get("regions") or []) if x in REGIONS][:2] or ["global"]
        deal = t.get("deal_type") if t.get("deal_type") in DEALS else "none"
        amount = (t.get("amount") or "").strip()
        if amount and _norm(amount) not in _norm(f"{s['headline']} {s['summary']}"):
            amount = ""  # a figure the story doesn't contain is never shown
        s["deal"] = None if deal == "none" else {
            "type": deal, "company": room.cfg.canon_lab((t.get("company") or "").strip()[:60]), "amount": amount, "usd": usd_value(amount)}
        cover = (t.get("cover") or "").strip()
        distinctive = bool(re.search(r"[\dA-Z$₹€£%]", cover))  # a figure or a name, not a generic word like "partnership"
        s["cover"] = cover if 0 < len(cover) <= 18 and distinctive and _norm(cover) in _norm(f"{s['headline']} {s['summary']}") else ""
        tagged += 1
    room.report["tagged"] = tagged
