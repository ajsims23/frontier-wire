"""The DPA Task Bench: every free AI model the newsroom can reach, tested on DPA-style work.

Public leaderboards measure general ability. This bench measures the work DPA does: pulling figures out of fund
reports and financial statements, reconciling totals, checking deliverables against a checklist, ownership and credit
arithmetic, and routing documents. The documents are synthetic (fictional funds and companies, written for the
bench) so no client data is ever sent to a free-tier model. Answers are scored automatically against known answers:
no AI judges another AI.

    python -m agent bench            # runs weekly, and whenever the tasks change
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT, Config
from .llm import LLM, AllProvidersFailed, LimitReached, Limits

TASKS = ROOT / "data" / "bench" / "tasks.json"


# ---------------------------------------------------------------------------------------------- scoring
def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "").replace("$", "").replace("%", "").replace("x", "").replace("USD", "").strip()
        neg = s.startswith("(") and s.endswith(")")
        try:
            n = float(s.strip("()"))
        except ValueError:
            return None
        return -n if neg else n
    return None


def _txt(v: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()


def _bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "yes", "pass"):
        return True
    if isinstance(v, str) and v.strip().lower() in ("false", "no", "fail"):
        return False
    return None


def _f1(got: set, want: set) -> float:
    if not got and not want:
        return 1.0
    if not got or not want:
        return 0.0
    tp = len(got & want)
    if not tp:
        return 0.0
    p, r = tp / len(got), tp / len(want)
    return 2 * p * r / (p + r)


def score_field(f: dict, got: Any) -> float:
    kind, want = f["kind"], f.get("expect")
    if kind == "number":
        n = _num(got)
        if n is None:
            return 0.0
        tol = f.get("tol", max(0.011, abs(want) * 0.005))
        return 1.0 if abs(n - want) <= tol else 0.0
    if kind == "text":
        g, w = _txt(got), _txt(want)
        return 1.0 if (g == w if f.get("exact") else (w in g and len(g) <= len(w) + 25)) else 0.0
    if kind == "bool":
        return 1.0 if _bool(got) is want else 0.0
    if kind == "set":
        return _f1({_txt(x) for x in (got or []) if isinstance(x, str)}, {_txt(x) for x in want})
    if kind == "empty":
        return 1.0 if isinstance(got, list) and not [x for x in got if str(x).strip()] else 0.0
    if kind == "map":
        got = got if isinstance(got, dict) else {}
        return sum(_txt(got.get(k)) == _txt(v) for k, v in want.items()) / len(want)
    if kind == "rules":
        got = got if isinstance(got, dict) else {}
        total = 0.0
        for rule, ids in want.items():
            g = got.get(rule) if isinstance(got.get(rule), dict) else {}
            status = "fail" if ids else "pass"
            if _txt(g.get("status")) != status:
                continue
            total += 1.0 if {_txt(i) for i in g.get("ids") or []} == {_txt(i) for i in ids} else 0.5
        return total / len(want)
    if kind == "owners":
        def pairs(rows: Any) -> set:
            out = set()
            for r in rows or []:
                if isinstance(r, dict):
                    name, pct = r.get("name"), _num(r.get("pct"))
                elif isinstance(r, (list, tuple)) and len(r) == 2:
                    name, pct = r[0], _num(r[1])
                else:
                    continue
                if name and pct is not None:
                    out.add((_txt(name).replace(" ltd", "").replace(" pvt", ""), round(pct, 1)))
            return out
        want_p = {(_txt(n), float(p)) for n, p in want}
        got_p = {(n, p) for n, p in pairs(got)}
        # names match if the expected name is contained in the given one ("pinecrest holdings" in "pinecrest holdings")
        matched = {w for w in want_p if any(w[0] in g[0] and abs(g[1] - w[1]) < 0.06 for g in got_p)}
        if not got_p:
            return 0.0
        p, r = len(matched) / len(got_p), len(matched) / len(want_p)
        return 0.0 if not matched else 2 * p * r / (p + r)
    return 0.0


def score_task(task: dict, answer: dict) -> tuple[float, list[dict]]:
    rows, total, weights = [], 0.0, 0.0
    for f in task["fields"]:
        s = score_field(f, (answer or {}).get(f["key"]))
        w = float(f.get("weight", 1))
        rows.append({"key": f["key"], "score": round(s, 3)})
        total += s * w
        weights += w
    return (total / weights if weights else 0.0), rows


# ---------------------------------------------------------------------------------------------- running
def load_tasks(path: Path | None = None) -> dict:
    return json.loads((path or TASKS).read_text())


def contenders(cfg: Config, env: dict[str, str]) -> list[tuple[dict, str]]:
    """Every model the newsroom is configured to use, on every provider with a key."""
    return [(p, m) for p in cfg.providers if env.get(p["key_env"]) for m in p["models"]]


def run(cfg: Config, now: datetime, env: dict[str, str], llm_for: Any = None, sleep: Any = time.sleep,
        tasks_path: Path | None = None) -> dict[str, Any]:
    spec = load_tasks(tasks_path)
    out_dir = cfg.data_dir / "bench"
    limits = Limits({"max_requests_per_run": 260, "max_requests_per_day": 400, "max_tokens_per_day": 900000},
                    out_dir / "usage.json", today=now.date().isoformat())
    llm_for = llm_for or (lambda p, m: LLM([dict(p, models=[m])], limits, env=env))
    models = []
    for p, m in contenders(cfg, env):
        llm = llm_for(p, m)
        rec: dict[str, Any] = {"provider": p["name"], "model": m, "tasks": {}, "errors": 0, "latency": []}
        tokens0 = limits.run_tokens
        for t in spec["tasks"]:
            prompt = f"{t['instruction']}\n\n<document>\n{t['document']}\n</document>"
            t0 = time.monotonic()
            try:
                try:
                    answer = llm.ask(system=spec["system"], prompt=prompt, schema_name="submit_answer", schema=t["schema"], max_tokens=1500)
                except AllProvidersFailed as e:
                    if not re.search(r"per-minute|server busy|after retry|network", str(e)):
                        raise
                    sleep(45)  # a busy minute on a free tier is not the model's fault: wait and ask once more
                    t0 = time.monotonic()
                    answer = llm.ask(system=spec["system"], prompt=prompt, schema_name="submit_answer", schema=t["schema"], max_tokens=1500)
            except LimitReached:
                rec["stopped"] = "bench request cap reached"
                break
            except AllProvidersFailed as e:
                rec["errors"] += 1
                rec["tasks"][t["id"]] = {"score": 0.0, "error": str(e)[-160:]}
                if re.search(r"unavailable|key rejected|payment required|skipping provider", str(e)):
                    rec["stopped"] = "model unavailable on the free tier"
                    break
                continue
            finally:
                sleep(6.5 if p["name"] == "gemini" else 2.5)  # stay inside per-minute free limits
            rec["latency"].append(round(time.monotonic() - t0, 2))
            s, fields = score_task(t, answer)
            rec["tasks"][t["id"]] = {"score": round(s, 3), "fields": fields}
        rec["tokens"] = limits.run_tokens - tokens0
        done = [t for t in spec["tasks"] if t["id"] in rec["tasks"]]
        if not done or rec.get("stopped") == "model unavailable on the free tier" and rec["errors"] == len(done):
            rec["available"] = False
        else:
            rec["available"] = True
            rec["score"] = round(100 * sum(rec["tasks"][t["id"]]["score"] for t in spec["tasks"] if t["id"] in rec["tasks"]) / len(spec["tasks"]), 1)
            rec["by_type"] = {}
            for typ in spec["types"]:
                ts = [t for t in spec["tasks"] if t["type"] == typ]
                rec["by_type"][typ] = round(100 * sum(rec["tasks"].get(t["id"], {}).get("score", 0) for t in ts) / len(ts), 1) if ts else None
            lat = sorted(rec["latency"])
            rec["median_latency_s"] = lat[len(lat) // 2] if lat else None
        rec.pop("latency")
        models.append(rec)
    results = json.loads((out_dir / "results.json").read_text()) if (out_dir / "results.json").exists() else {"runs": []}
    run_rec = {"date": now.date().isoformat(), "at": now.isoformat(), "tasks_version": spec["version"], "tasks": len(spec["tasks"]),
               "models": sorted(models, key=lambda r: -(r.get("score") or -1))}
    results["runs"] = (results.get("runs") or [])[-25:] + [run_rec]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    limits.save()
    return run_rec


# ---------------------------------------------------------------------------------------------- for the website
MODEL_NAMES = {"gemini-flash-lite-latest": "Gemini Flash-Lite", "gemini-flash-latest": "Gemini Flash",
               "openai/gpt-oss-120b": "gpt-oss-120b", "openai/gpt-oss-20b": "gpt-oss-20b", "qwen/qwen3.8-27b": "Qwen3.8 27B",
               "nvidia/nemotron-3-ultra-550b-a55b": "Nemotron 3 Ultra", "mistralai/mistral-large-4-1t-a52b": "Mistral Large 4",
               "gpt-oss-120b": "gpt-oss-120b"}
PROVIDER_NAMES = {"gemini": "Google AI Studio (free)", "groq": "Groq (free)", "nvidia": "NVIDIA NIM (free)",
                  "cerebras": "Cerebras", "openrouter": "OpenRouter (free)", "mistral": "Mistral (free)"}


def site_view(data_dir: Path) -> dict[str, Any] | None:
    p = data_dir / "bench" / "results.json"
    spec = load_tasks(data_dir / "bench" / "tasks.json") if (data_dir / "bench" / "tasks.json").exists() else load_tasks()
    runs = (json.loads(p.read_text()).get("runs") if p.exists() else []) or []
    latest = runs[-1] if runs else None
    rows = []
    if latest:
        prev = {(m["provider"], m["model"]): m.get("score") for m in (runs[-2]["models"] if len(runs) > 1 else [])}
        for m in latest["models"]:
            if not m.get("available"):
                continue
            last = prev.get((m["provider"], m["model"]))
            rows.append({**m, "name": MODEL_NAMES.get(m["model"], m["model"].split("/")[-1]),
                         "provider_name": PROVIDER_NAMES.get(m["provider"], m["provider"]),
                         "delta": None if last is None else round(m["score"] - last, 1),
                         "cells": [{"id": t["id"], "score": m["tasks"].get(t["id"], {}).get("score")} for t in spec["tasks"]]})
    return {"spec": spec, "latest": latest, "rows": rows, "runs": len(runs),
            "unavailable": [m for m in (latest or {}).get("models", []) if not m.get("available")],
            "history": [{"date": r["date"], "best": max([m.get("score") or 0 for m in r["models"]] or [0])} for r in runs]}
