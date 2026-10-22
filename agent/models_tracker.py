"""Model fact tracker: prices, context windows and release dates for frontier labs' models.

Facts come from OpenRouter's public model list (free, no key), which lists the price each model is actually
served at. Every run compares against the last snapshot and logs what changed (new models, price moves), so
the site can show "what changed" without anyone checking by hand. Benchmark results come from our own stories
(only figures that appear in the story's sources) and link back to them.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

API = "https://openrouter.ai/api/v1/models"
LABS = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "meta-llama": "Meta", "mistralai": "Mistral AI",
    "x-ai": "xAI", "deepseek": "DeepSeek", "qwen": "Alibaba (Qwen)", "cohere": "Cohere", "amazon": "Amazon",
    "microsoft": "Microsoft", "nvidia": "NVIDIA", "moonshotai": "Moonshot AI", "z-ai": "Zhipu AI", "perplexity": "Perplexity",
}
SKIP = re.compile(r":(free|beta|extended|floor|nitro|online)$|-(preview-\d{2}-\d{2}|\d{4}-\d{2}-\d{2})$|guard|embed|moderation|tts|whisper", re.I)
PER_LAB = 6


def _per_m(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f < 0 else round(f * 1_000_000, 4)


def parse_models(raw: str) -> list[dict[str, Any]]:
    rows = []
    for m in json.loads(raw).get("data", []):
        mid = str(m.get("id") or "")
        prefix = mid.split("/", 1)[0]
        outputs = (m.get("architecture") or {}).get("output_modalities") or ["text"]
        if prefix not in LABS or SKIP.search(mid) or "text" not in outputs or "image" in outputs or re.search(r"\((batch|flex|priority)\)", str(m.get("name") or ""), re.I):
            continue
        price = m.get("pricing") or {}
        p_in, p_out = _per_m(price.get("prompt")), _per_m(price.get("completion"))
        if p_in is None or p_out is None:
            continue
        name = re.sub(r"^[^:]{1,40}:\s*", "", str(m.get("name") or mid))
        created = m.get("created")
        rows.append({
            "id": mid, "name": name[:60], "lab": LABS[prefix],
            "released": datetime.fromtimestamp(created, tz=timezone.utc).date().isoformat() if isinstance(created, (int, float)) else "",
            "context": int(m.get("context_length") or 0),
            "price_in": p_in, "price_out": p_out,
            "inputs": [x for x in ((m.get("architecture") or {}).get("input_modalities") or []) if x in ("text", "image", "audio", "video", "file")],
        })
    keep = []
    for lab in sorted({r["lab"] for r in rows}):
        keep += sorted((r for r in rows if r["lab"] == lab), key=lambda r: r["released"], reverse=True)[:PER_LAB]
    return sorted(keep, key=lambda r: r["released"], reverse=True)


def update_tracker(room: Any) -> None:
    state = room.store.models
    try:
        models = parse_models(room.fetcher.get(API))
    except Exception as exc:  # noqa: BLE001
        room.report["model_tracker"] = f"failed: {type(exc).__name__}: {str(exc)[:80]}"
        return
    if not models:
        room.report["model_tracker"] = "no models parsed; kept last snapshot"
        return
    before = {m["id"]: m for m in state.get("models", [])}
    changes = state.get("changes", [])
    today = room.now.date().isoformat()
    if before:  # the very first snapshot isn't "news"
        for m in models:
            old = before.get(m["id"])
            if not old:
                recent = m["released"] >= (room.now.date() - timedelta(days=14)).isoformat()
                if not recent:
                    continue  # an older model newly in view (e.g. a list reshuffle) isn't news
                changes.append({"date": today, "model": m["name"], "lab": m["lab"], "kind": "new",
                                "text": f"Now available: {m['name']} (${m['price_in']:g} in / ${m['price_out']:g} out per 1M tokens)"})
                continue
            for field, label in (("price_in", "input"), ("price_out", "output")):
                if old.get(field) is not None and m[field] != old[field]:
                    kind = "price_cut" if m[field] < old[field] else "price_rise"
                    changes.append({"date": today, "model": m["name"], "lab": m["lab"], "kind": kind,
                                    "text": f"{m['name']} {label} price {'cut' if kind == 'price_cut' else 'raised'}: "
                                            f"${old[field]:g} → ${m[field]:g} per 1M tokens"})
            if old.get("context") and m["context"] and m["context"] != old["context"]:
                changes.append({"date": today, "model": m["name"], "lab": m["lab"], "kind": "context",
                                "text": f"{m['name']} context window: {old['context']:,} → {m['context']:,} tokens"})
    state["models"] = models
    state["changes"] = changes[-60:]
    state["updated_at"] = room.now.isoformat()
    room.report["model_tracker"] = f"{len(models)} models, {sum(1 for c in changes if c['date'] == today)} changes today"


def benchmark_rows(stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for s in sorted(stories, key=lambda x: x["published_at"], reverse=True):
        for b in s.get("benchmarks") or []:
            rows.append({**b, "story_id": s["id"], "headline": s["headline"], "date": s["published_at"][:10]})
    return rows[:80]
