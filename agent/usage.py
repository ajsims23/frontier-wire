"""API usage meter for the admin dashboard's "Usage & limits" tab.

Every outside API call the agent makes (AI providers, Gemini voice, Pexels/Pixabay) is counted here, along with
the rate-limit headers providers send back (how much of today's or this minute's allowance is left). When the
process ends the totals go to the worker (POST /api/usage/report), which keeps them in its database; nothing is
committed to the repo, so workflows never clash over a usage file.

Reporting needs API_URL (or config/api_url.txt) and ALERTS_DISPATCH_SECRET (or RECAP_SECRET); without them,
or if the worker is unreachable, the counts are simply dropped. Metering must never break a run.
"""
from __future__ import annotations

import atexit
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

import httpx

# outcome -> column
OUTCOMES = ("ok", "limited", "busy", "failed")
_HEADER = re.compile(r"^x-ratelimit-|^ratelimit-|^retry-after$", re.I)


def outcome_for(code: int | None) -> str:
    """Map an HTTP status (None = no answer at all) to how the tracker counts it."""
    if code is None or code >= 500:
        return "busy"
    if code == 429 or code == 402:
        return "limited"
    if code >= 400:
        return "failed"
    return "ok"


class Meter:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, int]] = {}
        self.state: dict[tuple[str, str], str] = {}
        self.source = os.environ.get("GITHUB_WORKFLOW", "") or "local"
        self._lock = threading.Lock()
        self._registered = False

    def add(self, service: str, model: str, outcome: str, tokens: int = 0, headers: Any = None, note: str = "") -> None:
        try:
            with self._lock:
                r = self.rows.setdefault((service, model or "-"), {"requests": 0, "tokens": 0, **{o: 0 for o in OUTCOMES}})
                r["requests"] += 1
                r[outcome if outcome in OUTCOMES else "failed"] += 1
                r["tokens"] += int(tokens or 0)
                for k, v in dict(headers or {}).items():
                    if _HEADER.search(k):
                        self.state[(service, f"{model or '-'}|{k.lower()}")] = str(v)[:80]
                if outcome == "limited" and note:
                    self.state[(service, f"{model or '-'}|last limit")] = note[:200]
                if not self._registered:
                    atexit.register(self.flush)
                    self._registered = True
        except Exception:  # noqa: BLE001
            pass

    def payload(self) -> dict[str, Any]:
        return {"source": self.source,
                "rows": [{"service": s, "model": m, **v} for (s, m), v in self.rows.items()],
                "state": [{"service": s, "k": k, "v": v} for (s, k), v in self.state.items()]}

    def flush(self, force: bool = False) -> None:
        if not self.rows and not self.state:
            return
        if "pytest" in sys.modules and not force:   # test runs make fake calls: never report them
            return
        recorded = Path(__file__).resolve().parent.parent / "config" / "api_url.txt"
        api = (os.environ.get("API_URL") or os.environ.get("RECAP_API")
               or (recorded.read_text().strip() if recorded.exists() else "")).rstrip("/")
        secret = os.environ.get("ALERTS_DISPATCH_SECRET") or os.environ.get("RECAP_SECRET") or ""
        if not api or not secret:
            return
        try:
            httpx.post(f"{api}/api/usage/report", json=self.payload(), timeout=20,
                       headers={"Authorization": f"Bearer {secret}"})
        except Exception:  # noqa: BLE001
            pass
        self.rows.clear()
        self.state.clear()


METER = Meter()
