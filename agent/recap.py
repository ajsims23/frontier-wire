"""Daily 30-second recap: pick the day's top five stories, check the on-screen script, render the narrated video.

The script (hook, one line and one detail per story, a three-line summary) is written by the editor in a Claude
session and saved to data/recaps/YYYY-MM-DD.json. This module drafts that file from the site's own data, checks
it (lengths, headlines paraphrased rather than copied, every story credits its source) and renders original
motion graphics with Pillow and ffmpeg. In GitHub Actions each story also gets a free stock clip from Pexels
(licensed for reuse; credited on screen and on the page), else an AI illustration, else a drawn one, and an AI voice
(Deepgram Aura-2 on Workers AI) reads the hook and each story's line. Without those files (a Claude session) the
same script renders silent, with drawn illustrations, so the editor can still check the layout.

    python -m agent recap draft            # pick today's five, write the skeleton for the editor to fill
    python -m agent recap render --out DIR # check the script, render recap.mp4, poster.jpg, teaser.gif
    python -m agent recap footage|voice --out DIR   # (Actions) stock clips into DIR/clips, narration into DIR/voice

On screen: a 3s hook, 5s per story (the paraphrased line and its source), a 2s outro with the site address.
Each story's detail line is not shown in the video; it goes on the video page, in the feed and in the email.
"""
from __future__ import annotations

import json
import math
import random
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image, ImageDraw

from .cards import GROUND, LABEL, MUTED, TEXT, TOPIC, _font, _wrap

IST = timezone(timedelta(hours=5, minutes=30))
W, H, FPS = 1920, 1080, 30
HOOK_S, STORY_S, OUTRO_S = 3.0, 5.0, 2.0   # 3s hook, 5s per story (headline + source), 2s outro
MIN_S, MAX_S = 27, 33
SOFT = (179, 207, 203)
PANEL = (10, 31, 34)
LIMITS = {"hook": 64, "line": 72, "detail": 120, "summary": 150, "say": 110, "footage": 80}
VOICE_LEAD = {"hook": 0.35, "story": 0.3, "outro": 0.2}   # seconds into a scene before the voice starts
VOICE_TAIL = {"hook": 0.35, "story": 0.45, "outro": 0.3}  # quiet after it, before the scene changes
OUTRO_SAY = "Full stories at Frontier Wire."
MAX_BYTES = 15 * 1024 * 1024
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
AGGREGATORS = {"techmeme.com", "news.ycombinator.com", "msn.com"}


# ---------------------------------------------------------------- picking
def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def pick(stories: list[dict[str, Any]], now: datetime, n: int = 5, hours: int = 24, per_category: int = 2) -> list[dict[str, Any]]:
    """The homepage's top-stories rule, limited to the last `hours`: the lead is the best core-AI story, the rest
    are the highest scored, preferring different labs. At most `per_category` stories per category, so the recap
    covers more than one beat on a deals-heavy day."""
    pool = [s for s in stories if timedelta(0) <= now - _dt(s["published_at"]) <= timedelta(hours=hours)]
    if not pool:
        return []
    lead = max(pool, key=lambda s: (s.get("ai_relevance") != "adjacent", s["score"], s["published_at"]))
    rest = sorted((s for s in pool if s["id"] != lead["id"]),
                  key=lambda s: (s["score"], s.get("ai_relevance") != "adjacent", bool(s.get("lab")), len(s.get("sources") or []), s["published_at"]),
                  reverse=True)
    out, labs, cats = [lead], {lead.get("lab") or lead["id"]}, {lead["category"]: 1}

    def ok(s: dict[str, Any], strict: bool) -> bool:
        if s in out or cats.get(s["category"], 0) >= per_category:
            return False
        return not strict or (s.get("lab") or s["id"]) not in labs

    for strict in (True, False):
        for s in rest:
            if len(out) < n and ok(s, strict):
                out.append(s)
                labs.add(s.get("lab") or s["id"])
                cats[s["category"]] = cats.get(s["category"], 0) + 1
    for s in rest:  # a thin day: fill up regardless of category
        if len(out) < n and s not in out:
            out.append(s)
    return out[:n]


def credit(story: dict[str, Any], limit: int = 2) -> str:
    """Who reported it: the outlets behind the story, never the aggregator that linked to them."""
    names: list[str] = []
    for src in story.get("sources") or []:
        dom = (urlparse(src.get("url", "")).hostname or "").removeprefix("www.")
        pub = (src.get("publisher") or dom).strip()
        if pub.endswith(" on MSN"):
            pub = pub[:-7]
        elif dom in AGGREGATORS or pub in AGGREGATORS:
            m = re.search(r"\(([^()]*)\)\s*$", src.get("title", ""))
            pub = m.group(1).split("/")[-1].strip() if m else ""
        pub = re.sub(r"\s*\(.*?\)\s*$", "", pub).strip()
        if pub and pub.lower() not in {x.lower() for x in names}:
            names.append(pub)
    return " · ".join(names[:limit]) or "Frontier Wire"


def today(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(IST).date().isoformat()


def draft(stories: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    picks = pick(stories, now)
    return {
        "date": today(now),
        "hook": "",
        "summary": ["", "", ""],
        "stories": [{
            "id": s["id"], "category": s["category"], "lab": s.get("lab", ""), "source": credit(s),
            "headline": s["headline"], "summary": s["summary"], "why_it_matters": s.get("why_it_matters", ""),
            "source_titles": [x.get("title", "") for x in s.get("sources") or []],
            "line": "", "detail": "", "say": "", "footage": "", "image_prompt": "",
        } for s in picks],
    }


# ---------------------------------------------------------------- checking
def _similar(a: str, b: str) -> float:
    norm = lambda t: re.sub(r"[^a-z0-9 ]", "", t.lower())  # noqa: E731
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def _copied_run(a: str, b: str, k: int = 6) -> bool:
    """True if `a` repeats any k consecutive words of `b`."""
    wa, wb = re.findall(r"[a-z0-9$.]+", a.lower()), re.findall(r"[a-z0-9$.]+", b.lower())
    grams = {tuple(wb[i:i + k]) for i in range(len(wb) - k + 1)}
    return any(tuple(wa[i:i + k]) in grams for i in range(len(wa) - k + 1))


def validate(script: dict[str, Any]) -> list[str]:
    errs = []
    if not 3 <= len(script.get("stories") or []) <= 5:
        errs.append("needs 3 to 5 stories")
    hook = (script.get("hook") or "").strip()
    if not hook or len(hook) > LIMITS["hook"]:
        errs.append(f"hook must be 1-{LIMITS['hook']} characters")
    summ = [x.strip() for x in script.get("summary") or [] if x.strip()]
    if len(summ) != 3 or any(len(x) > LIMITS["summary"] for x in summ):
        errs.append(f"summary needs exactly 3 lines of at most {LIMITS['summary']} characters")
    for i, s in enumerate(script.get("stories") or [], 1):
        for key in ("line", "detail"):
            v = (s.get(key) or "").strip()
            if not v or len(v) > LIMITS[key]:
                errs.append(f"story {i}: {key} must be 1-{LIMITS[key]} characters (has {len(v)})")
        if not (s.get("source") or "").strip():
            errs.append(f"story {i}: no source")
        for key in ("say", "footage"):
            if len((s.get(key) or "").strip()) > LIMITS[key]:
                errs.append(f"story {i}: {key} must be at most {LIMITS[key]} characters")
        if len(s.get("image_prompt") or "") > 300:
            errs.append(f"story {i}: image_prompt must be at most 300 characters")
        originals = [s.get("headline", "")] + list(s.get("source_titles") or [])
        for key in ("line", "detail", "say"):
            v = s.get(key) or ""
            for o in originals if v else []:
                if o and (_similar(v, o) >= 0.72 or _copied_run(v, o)):
                    errs.append(f"story {i}: {key} is too close to a published headline; paraphrase it")
                    break
    return errs


# ---------------------------------------------------------------- narration and timing
_UNITS = {"B": "billion", "M": "million", "K": "thousand", "T": "trillion"}


def spoken(text: str) -> str:
    """On-screen shorthand read the way a newsreader would say it."""
    t = text.strip()
    t = re.sub(r"\$(\d+(?:\.\d+)?)\s?([BMKT])\b", lambda m: f"{m.group(1)} {_UNITS[m.group(2)]} dollars", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s?([BMKT])\b", lambda m: f"{m.group(1)} {_UNITS[m.group(2)]}", t)
    t = re.sub(r"\$(\d+(?:\.\d+)?)", r"\1 dollars", t)
    t = t.replace("~", "about ").replace("&", " and ").replace(" · ", ", ").replace("/s", " per second")
    t = re.sub(r"\s+", " ", t).strip()
    return t if t.endswith((".", "!", "?")) else t + "."


def narration(script: dict[str, Any]) -> list[tuple[str, str]]:
    """What the voice reads, scene by scene: (file name, text)."""
    out = [("hook", spoken(script["hook"]))]  # "Today in AI" is already on screen
    for i, st in enumerate(script["stories"], 1):
        out.append((f"story{i}", spoken((st.get("say") or "").strip() or st["line"])))
    out.append(("outro", OUTRO_SAY))
    return out


def _duration(path: Path) -> float:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], text=True)
    return float(r.stdout.strip())


def voice_clips(script: dict[str, Any], voice_dir: Path | None) -> dict[str, tuple[Path, float]]:
    """The narration files present for this script, with their lengths. All or nothing: a half-read recap is worse
    than a silent one."""
    if not voice_dir or not voice_dir.exists():
        return {}
    out = {}
    for key, _ in narration(script):
        f = voice_dir / f"{key}.mp3"
        try:
            out[key] = (f, _duration(f))
        except Exception:  # noqa: BLE001
            return {}
    return out


def timing(n: int, clips: dict[str, tuple[Path, float]]) -> tuple[list[float], float]:
    """Scene lengths [hook, story 1..n, outro] and the voice tempo. Silent: 3s, 5s each, 2s. Narrated: each scene
    is long enough for its line (never shorter than the silent length). If that runs past 32.5s the quiet tails
    shrink, then the voice is sped up (at most 1.3x). Tempo 0 means the lines can't fit: render silent."""
    base = [HOOK_S] + [STORY_S] * n + [OUTRO_S]
    if not clips:
        return base, 1.0
    kinds = ["hook"] + ["story"] * n + ["outro"]
    keys = ["hook"] + [f"story{i}" for i in range(1, n + 1)] + ["outro"]
    cap = MAX_S - 0.5

    def lay(tempo: float, squeeze: float) -> list[float]:
        return [max(b, VOICE_LEAD[k] + clips[key][1] / tempo + 0.1 + (VOICE_TAIL[k] - 0.1) * (1 - squeeze))
                for b, k, key in zip(base, kinds, keys)]

    for squeeze in (0.0, 0.5, 1.0):
        if sum(lay(1.0, squeeze)) <= cap:
            return lay(1.0, squeeze), 1.0
    lo, hi = 1.0, 1.3
    if sum(lay(hi, 1.0)) > cap:
        return base, 0.0
    for _ in range(30):  # the gentlest speed-up that fits
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if sum(lay(mid, 1.0)) <= cap else (mid, hi)
    return lay(hi, 1.0), hi


def mix_voice(clips: dict[str, tuple[Path, float]], durs: list[float], tempo: float, out: Path) -> Path:
    """One narration track the length of the video: each line placed at the start of its scene."""
    keys = ["hook"] + [f"story{i}" for i in range(1, len(durs) - 1)] + ["outro"]
    kinds = ["hook"] + ["story"] * (len(durs) - 2) + ["outro"]
    starts = [sum(durs[:i]) for i in range(len(durs))]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    parts = []
    for j, key in enumerate(keys):
        cmd += ["-i", str(clips[key][0])]
        ms = int((starts[j] + VOICE_LEAD[kinds[j]]) * 1000)
        speed = f"atempo={tempo:.3f}," if tempo > 1.001 else ""
        parts.append(f"[{j}:a]aresample=44100,aformat=channel_layouts=mono,{speed}adelay={ms}:all=1[a{j}]")
    total = sum(durs)
    graph = ";".join(parts) + ";" + "".join(f"[a{j}]" for j in range(len(keys))) + \
        f"amix=inputs={len(keys)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total:.3f}[out]"
    cmd += ["-filter_complex", graph, "-map", "[out]", "-ar", "44100", "-c:a", "pcm_s16le", str(out)]
    _run(cmd)
    return out


# ---------------------------------------------------------------- stock footage
class Clip:
    """A stock clip decoded on the fly, cropped to the picture area, read frame by frame (loops if short)."""

    def __init__(self, path: Path, w: int, h: int):
        self.path, self.w, self.h = path, w, h
        self.proc: subprocess.Popen | None = None
        self.pos = -1
        self.last: Image.Image | None = None

    def _open(self) -> None:
        vf = (f"fps={FPS},scale={self.w}:{self.h}:force_original_aspect_ratio=increase,crop={self.w}:{self.h},"
              "eq=brightness=-0.05:saturation=0.85")
        self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(self.path), "-an", "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.pos = -1

    def frame(self, k: int) -> Image.Image | None:
        if self.proc is None or k < self.pos:
            self.close()
            self._open()
        size = self.w * self.h * 3
        while self.pos < k:
            assert self.proc and self.proc.stdout
            buf = self.proc.stdout.read(size)
            if len(buf) < size:
                return self.last
            self.pos += 1
            if self.pos == k:
                self.last = Image.frombytes("RGB", (self.w, self.h), buf)
        return self.last

    def close(self) -> None:
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc = None


def usable_clip(path: Path) -> bool:
    try:
        probe = json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                 "-of", "json", str(path)], text=True).stdout)
        st = probe["streams"][0]
        return st["width"] >= 640 and st["height"] >= 360
    except Exception:  # noqa: BLE001
        return False


DEFAULT_FOOTAGE = {
    "models": "data center servers lights", "research": "scientist laboratory computer screen",
    "policy": "government building", "safety": "cyber security code screen", "industry": "technology office city",
    "voices": "conference stage speaker", "india": "india city technology", "business": "stock market trading screen",
}


def fetch_footage(script: dict[str, Any], out: Path, key: str) -> list[str]:
    """Run in GitHub Actions: one free stock clip per story from Pexels (search by the editor's `footage` query, else a
    query for the story's beat). Saves out/<i>.mp4 and out/credits.json. Failures are reported; that story falls back
    to the AI illustration."""
    import httpx
    out.mkdir(parents=True, exist_ok=True)
    if not key:
        return ["no PEXELS_API_KEY: no stock footage today"]
    notes, used, credits = [], set(), []
    with httpx.Client(timeout=60, headers={"Authorization": key}, follow_redirects=True) as http:
        for i, st in enumerate(script["stories"], 1):
            q = (st.get("footage") or "").strip() or DEFAULT_FOOTAGE.get(st["category"], DEFAULT_FOOTAGE["industry"])
            try:
                r = http.get("https://api.pexels.com/v1/videos/search",
                             params={"query": q, "orientation": "landscape", "size": "medium", "per_page": 15})
                if r.status_code == 404:  # the older path, in case the new one isn't live for this key
                    r = http.get("https://api.pexels.com/videos/search",
                                 params={"query": q, "orientation": "landscape", "size": "medium", "per_page": 15})
                r.raise_for_status()
                cands = []
                for v in r.json().get("videos") or []:
                    if v.get("id") in used or not 6 <= (v.get("duration") or 0) <= 60:
                        continue
                    files = [f for f in v.get("video_files") or [] if f.get("file_type") == "video/mp4"
                             and 1280 <= (f.get("width") or 0) <= 1920 and (f.get("height") or 0) >= 720]
                    if files:
                        cands.append((v, min(files, key=lambda f: abs((f.get("width") or 0) - 1920))))
                if not cands:
                    raise RuntimeError(f"no usable clip for {q!r}")
                v, f = random.Random(st["id"]).choice(cands[:4])
                dest = out / f"{i}.mp4"
                with http.stream("GET", f["link"]) as dl:
                    dl.raise_for_status()
                    with dest.open("wb") as fh:
                        for chunk in dl.iter_bytes():
                            fh.write(chunk)
                if not usable_clip(dest):
                    dest.unlink(missing_ok=True)
                    raise RuntimeError("downloaded clip does not decode")
                used.add(v["id"])
                user = v.get("user") or {}
                credits.append({"story": i, "name": (user.get("name") or "Pexels contributor")[:60], "url": v.get("url") or "https://www.pexels.com"})
            except Exception as exc:  # noqa: BLE001
                notes.append(f"story {i}: no stock clip ({str(exc)[:140]}); using the illustration")
    (out / "credits.json").write_text(json.dumps(credits, indent=2))
    return notes


def fetch_voice(script: dict[str, Any], out: Path, api: str, secret: str) -> list[str]:
    """Run in GitHub Actions: the narration, one MP3 per scene, from the worker (Workers AI, Deepgram Aura-2)."""
    import base64
    import httpx
    out.mkdir(parents=True, exist_ok=True)
    notes = []
    for key, text in narration(script):
        try:
            r = httpx.post(f"{api.rstrip('/')}/api/recap/voice", json={"text": text}, timeout=90,
                           headers={"Authorization": f"Bearer {secret}"})
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code != 200 or not data.get("audio"):
                raise RuntimeError(f"HTTP {r.status_code}: {str(data.get('error') or r.text)[:120]}")
            (out / f"{key}.mp3").write_bytes(base64.b64decode(data["audio"]))
            _duration(out / f"{key}.mp3")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{key}: no narration ({exc})")
    if notes:  # all or nothing
        for f in out.glob("*.mp3"):
            f.unlink()
    return notes


# ---------------------------------------------------------------- drawing
def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _fade(layer: Image.Image, k: float) -> Image.Image:
    if k >= 0.999:
        return layer
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * k)))
    return out


def _text_layer(lines: list[str], font: Any, fill: tuple[int, int, int], spacing: float = 1.12) -> Image.Image:
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * spacing)
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = max(int(tmp.textlength(t, font=font)) for t in lines) + 8
    img = Image.new("RGBA", (w, lh * len(lines) + desc), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, t in enumerate(lines):
        d.text((0, i * lh), t, font=font, fill=fill)
    return img


def _fit(text: str, max_w: int, sizes: tuple[int, ...], max_lines: int, weight: int = 750, width: int = 100) -> tuple[Any, list[str]]:
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    for size in sizes:
        f = _font(size, weight, width)
        lines = _wrap(tmp, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines
    return f, lines[:max_lines]


def _background() -> Image.Image:
    """Deep ground with a soft glow and a faint grid (all generated)."""
    img = Image.new("RGB", (W, H), GROUND)
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    for r in range(900, 0, -30):
        gd.ellipse((W * 0.78 - r, -r * 0.6, W * 0.78 + r, r * 0.9), fill=int(26 * (1 - r / 900)))
    img = Image.composite(Image.new("RGB", (W, H), (20, 60, 64)), img, glow)
    d = ImageDraw.Draw(img)
    grid = tuple(int(g + (m - g) * 0.08) for g, m in zip(GROUND, MUTED))
    for x in range(0, W, 96):
        d.line((x, 0, x, H), fill=grid, width=1)
    for y in range(0, H, 96):
        d.line((0, y, W, y), fill=grid, width=1)
    return img


def _signal(d: ImageDraw.ImageDraw, seed: str, color: tuple[int, int, int], box: tuple[int, int, int, int], t: float) -> None:
    """The site's generated 'signal' motif, drifting over time."""
    r = random.Random(seed)
    x0, y0, x1, y1 = box
    cx = x0 + (x1 - x0) * (0.3 + r.random() * 0.4) + math.sin(t * 0.6) * 40
    spread = (x1 - x0) * (0.14 + r.random() * 0.1)
    n = 7
    for i in range(n):
        base = y0 + 20 + i * (y1 - y0 - 40) / (n - 1)
        amp = 10 + r.random() * (80 if i == 3 else 34)
        freq, phase = 2 + r.random() * 4, r.random() * 6.28
        pts = []
        for x in range(x0, x1 + 1, 10):
            env = math.exp(-(((x - cx) / spread) ** 2))
            y = base - amp * env * abs(math.sin((x - x0) / (x1 - x0) * 6.28 * freq + phase + t * 1.4)) - 3 * math.sin(x / 23 + i + t)
            pts.append((x, y))
        main = i == 3
        fill = color if main else tuple(int(c * 0.3 + g * 0.7) for c, g in zip(MUTED, GROUND))
        d.line(pts, fill=fill, width=5 if main else 2)


def _brand(d: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0, grow: float = 1.0) -> None:
    bars = [(13, TOPIC["models"]), (20, TOPIC["research"]), (10, TOPIC["policy"]), (16, TOPIC["industry"])]
    for i, (h, c) in enumerate(bars):
        bx, hh = x + i * 9 * scale, max(2, h * scale * grow)
        d.rounded_rectangle((bx, y + 24 * scale - hh, bx + 5 * scale, y + 24 * scale), radius=max(1, int(2 * scale)), fill=c)
    d.text((x + 46 * scale, y - 2 * scale), "Frontier Wire", font=_font(int(30 * scale), 800, 125), fill=TEXT)


def key_figure(st: dict[str, Any]) -> str:
    """The number that carries the story ($2.7B, 48.1%, 200+), else the company or lab, for the big visual."""
    text = f"{st.get('line', '')} {st.get('detail', '')}"
    m = re.search(r"[$₹€£]\s?\d[\d.,]*\s?(?:billion|million|trillion|[BMKT]\b)?", text, re.I)
    if m:
        return re.sub(r"\s?billion", "B", re.sub(r"\s?million", "M", re.sub(r"\s?trillion", "T", m.group(0).replace(" ", ""), flags=re.I), flags=re.I), flags=re.I)
    for pat in (r"\d[\d.,]*%", r"\d[\d,]*\+", r"\b\d[\d.,]*\s?(?:x|GW|MW|countries|parameters)\b"):
        m = re.search(pat, text, re.I)
        if m:
            return m.group(0)
    lab = (st.get("lab") or "").strip()
    return lab if 0 < len(lab) <= 14 else ""


def _illustration(d: ImageDraw.ImageDraw, cat: str, box: tuple[int, int, int, int], color: tuple[int, int, int], t: float) -> None:
    """An original line illustration per beat (no photos, no logos), gently animated."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    dim = tuple(int(c * 0.42 + g * 0.58) for c, g in zip(color, GROUND))
    faint = tuple(int(c * 0.2 + g * 0.8) for c, g in zip(color, GROUND))
    pulse = 0.5 + 0.5 * math.sin(t * 2.2)
    if cat == "models":  # a small neural network
        layers = [3, 5, 5, 2]
        pts = [[(x0 + w * (0.12 + 0.76 * i / (len(layers) - 1)), y0 + h * (j + 1) / (n + 1)) for j in range(n)] for i, n in enumerate(layers)]
        for a, b in zip(pts, pts[1:]):
            for p in a:
                for q in b:
                    d.line((p, q), fill=faint, width=2)
        for i, layer in enumerate(pts):
            for j, (px, py) in enumerate(layer):
                r = 13 + 5 * (pulse if (i + j) % 2 else 1 - pulse)
                d.ellipse((px - r, py - r, px + r, py + r), fill=color if (i + j) % 3 == 0 else dim)
    elif cat == "research":  # a rising result curve with data points
        d.line((x0 + 30, y1 - 30, x1 - 20, y1 - 30), fill=faint, width=3)
        d.line((x0 + 30, y0 + 20, x0 + 30, y1 - 30), fill=faint, width=3)
        n = 9
        grow = min(1.0, t % 5 / 1.4)
        pts = [(x0 + 50 + (w - 90) * i / (n - 1), y1 - 50 - (h - 100) * (i / (n - 1)) ** 1.6 * grow) for i in range(n)]
        d.line(pts, fill=color, width=6, joint="curve")
        for px, py in pts:
            d.ellipse((px - 9, py - 9, px + 9, py + 9), fill=color)
    elif cat == "policy":  # balance scale
        cx, top = x0 + w / 2, y0 + 40
        tilt = math.sin(t * 1.3) * 18
        d.line((cx, top, cx, y1 - 40), fill=dim, width=8)
        d.rounded_rectangle((cx - 110, y1 - 52, cx + 110, y1 - 32), radius=8, fill=dim)
        lx, ly, rx, ry = cx - w * 0.36, top + 30 - tilt, cx + w * 0.36, top + 30 + tilt
        d.line((lx, ly, rx, ry), fill=color, width=8)
        for px, py in ((lx, ly), (rx, ry)):
            d.line((px, py, px - 60, py + 130), fill=faint, width=3)
            d.line((px, py, px + 60, py + 130), fill=faint, width=3)
            d.chord((px - 80, py + 90, px + 80, py + 170), 0, 180, fill=color)
    elif cat == "safety":  # shield with a lock
        cx, cy = x0 + w / 2, y0 + h / 2
        sw, sh = w * 0.62, h * 0.86
        shield = [(cx - sw / 2, cy - sh / 2), (cx + sw / 2, cy - sh / 2), (cx + sw / 2, cy), (cx, cy + sh / 2), (cx - sw / 2, cy)]
        d.polygon(shield, outline=color, fill=faint, width=8)
        d.rounded_rectangle((cx - 60, cy - 10, cx + 60, cy + 80), radius=12, fill=color)
        d.arc((cx - 42, cy - 80, cx + 42, cy + 10), 180, 360, fill=color, width=14)
        r = 60 + 40 * pulse
        d.ellipse((cx - sw / 2 - r * 0.2, cy - sh / 2 - r * 0.2, cx + sw / 2 + r * 0.2, cy + sh / 2 + r * 0.2), outline=faint, width=2)
    elif cat == "voices":  # speech bubbles
        d.rounded_rectangle((x0 + 20, y0 + 30, x1 - 80, y0 + h * 0.55), radius=36, outline=color, width=8)
        d.rounded_rectangle((x0 + 90, y0 + h * 0.5, x1 - 10, y1 - 20), radius=36, fill=faint, outline=dim, width=6)
    else:  # industry: bars and a rising trend
        n = 6
        bw = (w - 60) / n
        for i in range(n):
            bh = (h - 70) * (0.25 + 0.75 * (i + 1) / n) * (0.92 + 0.08 * math.sin(t * 2 + i))
            bx = x0 + 30 + i * bw
            d.rounded_rectangle((bx + 10, y1 - 30 - bh, bx + bw - 10, y1 - 30), radius=10, fill=color if i == n - 1 else dim)
        d.line((x0 + 30, y1 - 30, x1 - 30, y1 - 30), fill=faint, width=3)


def _human(date: str) -> str:
    d = datetime.fromisoformat(date)
    return f"{d.day} {d.strftime('%B %Y')}"


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale and centre-crop to exactly w x h."""
    k = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * k)), max(h, round(img.height * k))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


IMG_X = 1000          # the AI illustration fills the frame from here to the right edge
IMG_W = W - IMG_X


def _fade_mask() -> Image.Image:
    """Opaque on the right, fading into the background towards the text column and at the top and bottom."""
    from PIL import ImageChops
    horiz = Image.new("L", (IMG_W, H))
    hd = ImageDraw.Draw(horiz)
    for x in range(IMG_W):
        hd.line((x, 0, x, H), fill=int(235 * min(1.0, x / (IMG_W * 0.42)) ** 1.6))
    vert = Image.new("L", (IMG_W, H))
    vd = ImageDraw.Draw(vert)
    for y in range(H):
        f = min(1.0, y / (H * 0.12), (H - 1 - y) / (H * 0.18))
        vd.line((0, y, IMG_W, y), fill=int(255 * max(0.0, f)))
    return ImageChops.multiply(horiz, vert)


def _plate(layer: Image.Image, pad: int = 12) -> Image.Image:
    """A small dark rounded plate behind a label, so it reads over moving footage."""
    out = Image.new("RGBA", (layer.width + 2 * pad, layer.height + pad), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle((0, 0, out.width - 1, out.height - 1), radius=10, fill=(5, 20, 22, 190))
    out.alpha_composite(layer, (pad, pad // 2))
    return out


class Renderer:
    def __init__(self, script: dict[str, Any], site_label: str, images: Path | None = None,
                 durations: list[float] | None = None, clips: Path | None = None):
        self.s = script
        self.images: dict[int, Image.Image] = {}
        self.clips: dict[int, Clip] = {}
        self.credits: dict[int, str] = {}
        if clips and clips.exists():
            try:
                names = {c["story"]: c["name"] for c in json.loads((clips / "credits.json").read_text())}
            except Exception:  # noqa: BLE001
                names = {}
            for i in range(len(script["stories"])):
                f = clips / f"{i + 1}.mp4"
                if f.exists() and usable_clip(f):
                    self.clips[i] = Clip(f, IMG_W, H)
                    self.credits[i] = names.get(i + 1, "")
        if images:
            for i in range(len(script["stories"])):
                f = images / f"{i + 1}.jpg"
                if f.exists():
                    try:
                        # a little larger than the area, so it can zoom slowly
                        self.images[i] = _cover(Image.open(f).convert("RGB"), int(IMG_W * 1.08), int(H * 1.08))
                    except Exception:  # noqa: BLE001 - a broken image falls back to the drawn illustration
                        pass
        self.mask = _fade_mask() if (self.images or self.clips) else None
        self.site = site_label
        self.n = len(script["stories"])
        self.durs = durations or [HOOK_S] + [STORY_S] * self.n + [OUTRO_S]
        assert len(self.durs) == self.n + 2
        self.starts = [sum(self.durs[:i]) for i in range(len(self.durs))]
        self.total = sum(self.durs)
        self.bg = _background()
        self.date_h = _human(script["date"])
        self._scenes = [self._story_layers(st, i) for i, st in enumerate(script["stories"])]
        self.ai_label = _text_layer(["AI-generated illustration"], _font(24, 600), (205, 220, 218))
        self.clip_labels = {i: _plate(_text_layer([f"Stock footage: {n} / Pexels" if n else "Stock footage: Pexels"], _font(24, 600), (205, 220, 218)))
                            for i, n in self.credits.items()}
        f, lines = _fit(script["hook"], 1500, (104, 96, 88, 80), 2, 800)
        self.hook = _text_layer(lines, f, TEXT, 1.08)
        self.eyebrow = _text_layer([f"TODAY IN AI  ·  {self.date_h.upper()}"], _font(34, 700, 112), TOPIC["research"])
        self.count = _text_layer([f"{self.n} stories. {int(round(self.total))} seconds."], _font(40, 500), SOFT)
        self.out1 = _text_layer(["Every story, with its sources."], _font(78, 800), TEXT)
        self.out2 = _text_layer([site_label], _font(58, 700, 110), TOPIC["research"])
        self.out3 = _text_layer(["Updated every three hours. Written by our newsroom agent, checked against its sources."], _font(32, 500), MUTED)

    def _story_layers(self, st: dict[str, Any], i: int) -> dict[str, Any]:
        color = TOPIC.get(st["category"], TOPIC["industry"])
        label = LABEL.get(st["category"], "News").upper() + (f"  ·  {st['lab']}" if st.get("lab") else "")
        f, lines = _fit(st["line"], 1000, (80, 72, 66, 60), 3, 800)
        fig = key_figure(st)
        ffig, figlines = None, []
        if fig:  # largest size at which the figure fits the panel on one line
            tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
            for size in range(150, 54, -6):
                ffig = _font(size, 800, 100 if len(fig) > 8 else 105)
                if tmp.textlength(fig, font=ffig) <= 470:
                    break
            figlines = [fig]
        return {
            "color": color, "seed": st["id"], "cat": st["category"],
            "figure": _text_layer(figlines, ffig, TEXT, 1.0) if fig else None,
            "num": _text_layer([f"{i + 1:02d}"], _font(190, 800, 112), color),
            "chip": _text_layer([label], _font(34, 700, 112), color),
            "line": _text_layer(lines, f, TEXT, 1.06),
            "source": _text_layer([f"Source: {st['source']}"], _font(34, 600), MUTED),
        }

    # each scene draws onto a copy of the background
    def _place(self, frame: Image.Image, layer: Image.Image, x: int, y: int, t: float, start: float, out_k: float) -> None:
        k = _ease((t - start) / 0.55)
        if k <= 0:
            return
        frame.alpha_composite(_fade(layer, k * out_k), (x, int(y + (1 - k) * 36)))

    def _chrome(self, d: ImageDraw.ImageDraw, idx: int, progress: float) -> None:
        _brand(d, 140, 72)
        date = self.date_h
        f = _font(30, 600)
        d.text((W - 140 - d.textlength(date, font=f), 74), date, font=f, fill=MUTED)
        seg_w, gap, y = (W - 280 - gap_total(self.n)) / self.n, 14, 1000
        for j in range(self.n):
            x0 = 140 + j * (seg_w + gap)
            d.rounded_rectangle((x0, y, x0 + seg_w, y + 8), radius=4, fill=(30, 58, 62))
            fill = 1.0 if j < idx else (progress if j == idx else 0.0)
            if fill > 0:
                d.rounded_rectangle((x0, y, x0 + seg_w * fill, y + 8), radius=4, fill=TOPIC["research"])

    def frame(self, t: float) -> Image.Image:
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        hook_s = self.durs[0]
        if t < hook_s:
            out_k = 1 - _ease((t - (hook_s - 0.35)) / 0.35)
            _brand(d, 140, 72)
            _signal(d, "frontier-wire-hook", TOPIC["research"], (980, 160, 1800, 470), t)
            # big bars mark
            bars = [(130, TOPIC["models"]), (200, TOPIC["research"]), (100, TOPIC["policy"]), (160, TOPIC["industry"])]
            for i, (h, c) in enumerate(bars):
                hh = h * _ease((t - i * 0.12) / 0.8)
                if hh > 2:
                    d.rounded_rectangle((140 + i * 58, 470 - hh, 140 + i * 58 + 34, 470), radius=17, fill=c)
            self._place(img, self.eyebrow, 140, 540, t, 0.3, out_k)
            self._place(img, self.hook, 140, 610, t, 0.55, out_k)
            self._place(img, self.count, 140, 640 + self.hook.height, t, 0.9, out_k)
            return img.convert("RGB")
        idx = next((j for j in range(self.n) if t < self.starts[j + 2]), self.n)
        if idx < self.n:
            story_s = self.durs[idx + 1]
            lt = t - self.starts[idx + 1]
            L = self._scenes[idx]
            out_k = 1 - _ease((lt - (story_s - 0.35)) / 0.35)
            # the visual: a stock clip, else an AI illustration of the story, else a drawn one; and the key figure
            k = _ease(lt / 0.6) * out_k
            pic = None
            if k > 0 and idx in self.clips:
                pic = self.clips[idx].frame(int(lt * FPS))
                if pic is not None:
                    pic = pic.convert("RGBA")
                if lt + 1 / FPS >= story_s:
                    self.clips[idx].close()
            if pic is None and k > 0 and idx in self.images:
                big = self.images[idx]
                z = 1.0 + 0.06 * (lt / story_s)  # slow push-in over the story's scene
                cw, ch = int(big.width / 1.08 * (1.08 - (z - 1))), int(big.height / 1.08 * (1.08 - (z - 1)))
                ox, oy = (big.width - cw) // 2, (big.height - ch) // 2
                pic = big.crop((ox, oy, ox + cw, oy + ch)).resize((IMG_W, H), Image.BILINEAR).convert("RGBA")
            if pic is not None:
                pic.putalpha(self.mask.point(lambda v: int(v * k)))
                img.alpha_composite(pic, (IMG_X, 0))
                if L["figure"] is not None:
                    fw, fh = L["figure"].width + 64, L["figure"].height + 40
                    plate = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
                    ImageDraw.Draw(plate).rounded_rectangle((0, 0, fw - 1, fh - 1), radius=26, fill=(5, 20, 22, 205))
                    plate.alpha_composite(L["figure"], (32, 14))
                    img.alpha_composite(_fade(plate, k), (W - 120 - fw, 820 - fh + int((1 - k) * 30)))
                lab = self.clip_labels.get(idx, self.ai_label) if idx in self.clips and self.clips[idx].last is not None else self.ai_label
                img.alpha_composite(_fade(lab, k * 0.8), (W - 120 - lab.width, 846))
            elif k > 0:
                panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                pd = ImageDraw.Draw(panel)
                tint = tuple(int(c * 0.10 + g * 0.90) for c, g in zip(L["color"], GROUND))
                pd.rounded_rectangle((1220, 150, 1780, 900), radius=36, fill=tint + (255,), outline=tuple(int(c * 0.35 + g * 0.65) for c, g in zip(L["color"], GROUND)) + (255,), width=2)
                _illustration(pd, L["cat"], (1290, 210, 1710, 590), L["color"], t)
                if L["figure"] is not None:
                    fx = 1500 - L["figure"].width // 2
                    panel.alpha_composite(L["figure"], (max(1240, fx), 640))
                img.alpha_composite(_fade(panel, k), (0, int((1 - k) * 30)))
            self._chrome(d, idx, lt / story_s)  # drawn over the picture so the date and progress stay visible
            self._place(img, L["num"], 130, 150, lt, 0.0, out_k)
            self._place(img, L["chip"], 140, 400, lt, 0.12, out_k)
            self._place(img, L["line"], 140, 470, lt, 0.25, out_k)
            self._place(img, L["source"], 140, 470 + L["line"].height + 48, lt, 0.45, out_k)
            return img.convert("RGB")
        lt = t - self.starts[-1]
        _signal(d, "frontier-wire-outro", TOPIC["research"], (980, 160, 1800, 470), t)
        _brand(d, 140, 300, scale=2.2, grow=_ease(lt / 0.8))
        self._place(img, self.out1, 140, 470, lt, 0.2, 1)
        self._place(img, self.out2, 140, 590, lt, 0.45, 1)
        self._place(img, self.out3, 140, 700, lt, 0.7, 1)
        return img.convert("RGB")

    def poster(self) -> Image.Image:
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        _brand(d, 140, 72)
        _signal(d, "frontier-wire-hook", TOPIC["research"], (1180, 40, 1800, 190), 1.0)
        d.text((140, 200), f"TODAY'S {int(round(self.total))}-SECOND RECAP  ·  {self.date_h.upper()}", font=_font(34, 700, 112), fill=TOPIC["research"])
        f, lines = _fit(self.s["hook"], 1500, (88, 80, 72), 2, 800)
        img.alpha_composite(_text_layer(lines, f, TEXT, 1.06), (140, 260))
        y = 290 + _text_layer(lines, f, TEXT, 1.06).height + 30
        fl = _font(38, 600)
        for i, st in enumerate(self.s["stories"]):
            c = TOPIC.get(st["category"], TOPIC["industry"])
            d.rounded_rectangle((140, y + 12, 152, y + 40), radius=6, fill=c)
            line = st["line"] if d.textlength(st["line"], font=fl) <= 1400 else _wrap(d, st["line"], fl, 1360)[0] + "…"
            d.text((180, y), line, font=fl, fill=SOFT)
            y += 64
        # play button
        cx, cy, r = W - 260, H - 240, 110
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=TOPIC["research"])
        d.polygon([(cx - 34, cy - 52), (cx - 34, cy + 52), (cx + 58, cy)], fill=GROUND)
        d.text((140, H - 110), self.site, font=_font(34, 700, 110), fill=MUTED)
        return img.convert("RGB")


def gap_total(n: int, gap: int = 14) -> int:
    return gap * (n - 1)


# ---------------------------------------------------------------- output
def _run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, **kw)


def render(script: dict[str, Any], out_dir: Path, site_label: str = "ajsims23.github.io/frontier-wire",
           images: Path | None = None, voice: Path | None = None, clips: Path | None = None) -> dict[str, Any]:
    errs = validate(script)
    if errs:
        raise ValueError("script problems:\n- " + "\n- ".join(errs))
    out_dir.mkdir(parents=True, exist_ok=True)
    vc = voice_clips(script, voice)
    durs, tempo = timing(len(script["stories"]), vc)
    if not tempo:  # the narration can't fit in 33 seconds: publish the silent cut rather than nothing
        print("::warning::narration too long for the recap; rendering silent", flush=True)
        vc, tempo = {}, 1.0
    r = Renderer(script, site_label, images if images and images.exists() else None, durs, clips)
    mp4, poster, gif = out_dir / "recap.mp4", out_dir / "poster.jpg", out_dir / "teaser.gif"
    frames = int(round(r.total * FPS))
    audio = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]  # silent track, so every recap has one
    if vc:
        audio = ["-i", str(mix_voice(vc, durs, tempo, out_dir / "narration.wav"))]
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         *audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k", "-t", f"{frames / FPS:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "20", "-maxrate", "1600k", "-bufsize", "3200k",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-metadata", f"title=Frontier Wire recap {script['date']}", str(mp4)],
        stdin=subprocess.PIPE)
    assert enc.stdin
    for i in range(frames):
        enc.stdin.write(r.frame(i / FPS).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("ffmpeg failed while encoding")
    for c in r.clips.values():
        c.close()
    (out_dir / "render.json").write_text(json.dumps({"narrated": bool(vc), "tempo": round(tempo, 3),
                                                     "footage": sorted(i + 1 for i in r.clips), "scenes": [round(d, 2) for d in durs]}))
    r.poster().save(poster, quality=86, optimize=True, progressive=True)
    # teaser: the hook into the first story, small enough for an email
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.8", "-t", "5", "-i", str(mp4), "-vf",
          "fps=10,scale=600:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
          "-loop", "0", str(gif)])
    return check(out_dir)


def check(out_dir: Path) -> dict[str, Any]:
    mp4 = out_dir / "recap.mp4"
    probe = json.loads(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height",
                             "-of", "json", str(mp4)], text=True).stdout)
    v = next(st for st in probe["streams"] if st.get("codec_type") == "video")
    dur = float(probe["format"]["duration"])
    decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-f", "null", "-"], capture_output=True, text=True)
    info = {"duration": round(dur, 2), "bytes": mp4.stat().st_size, "codec": v["codec_name"], "size": f"{v['width']}x{v['height']}",
            "poster_bytes": (out_dir / "poster.jpg").stat().st_size, "gif_bytes": (out_dir / "teaser.gif").stat().st_size}
    problems = []
    if not MIN_S <= dur <= MAX_S:
        problems.append(f"duration {dur:.1f}s is outside {MIN_S}-{MAX_S}s")
    if info["bytes"] >= MAX_BYTES:
        problems.append(f"video is {info['bytes'] / 1e6:.1f} MB (limit 15 MB)")
    if v["codec_name"] != "h264" or (v["width"], v["height"]) != (W, H):
        problems.append(f"expected h264 1920x1080, got {v['codec_name']} {v['width']}x{v['height']}")
    if decode.returncode != 0 or decode.stderr.strip():
        problems.append("video does not decode cleanly: " + decode.stderr.strip()[:200])
    info["ok"] = not problems
    info["problems"] = problems
    return info


# ---------------------------------------------------------------- publishing (GitHub Releases) and the website
ASSETS = ("recap.mp4", "poster.jpg", "teaser.gif")
LIVE_DAYS = 3     # the video itself is served from the site for this many days, then only from Releases
IMAGE_DAYS = 30   # poster and teaser stay on the site this long, so images in older emails keep working


def tag(date: str) -> str:
    return f"recap-{date}"


def asset_url(repo: str, date: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag(date)}/{name}"


def upload(script: dict[str, Any], out_dir: Path, repo_dir: Path) -> str:
    """Hand the day's script to GitHub Actions on a short-lived branch `recap-upload/<date>` (main plus one commit).
    The "Recap release" workflow generates the AI illustrations, renders and checks the video, creates the Release,
    puts the recap on the site and deletes the branch. (Claude sessions can't reach the image model or create
    Releases themselves.) `out_dir` is unused; kept so the command line stays the same."""
    errs = validate(script)
    if errs:
        raise RuntimeError("not uploading: " + "; ".join(errs))
    branch = f"recap-upload/{script['date']}"
    git = lambda *a: _run(["git", "-C", str(repo_dir), *a], text=True).stdout  # noqa: E731
    git("fetch", "-q", "origin", "main")
    wt = Path(tempfile.mkdtemp(prefix="recap-upload-"))
    try:
        git("worktree", "add", "-q", "--detach", str(wt), "origin/main")
        dest = wt / "recap-upload"
        dest.mkdir()
        (dest / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n")
        _run(["git", "-C", str(wt), "add", "-f", "recap-upload"])
        _run(["git", "-C", str(wt), "-c", "user.name=frontier-wire-recap", "-c", "user.email=actions@users.noreply.github.com",
              "commit", "-q", "-m", f"Recap upload {script['date']}"])
        _run(["git", "-C", str(wt), "push", "-q", "--force", "origin", f"HEAD:refs/heads/{branch}"])
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force", str(wt)], capture_output=True)
    return branch


def fetch_images(script: dict[str, Any], out: Path, api: str, secret: str) -> list[str]:
    """Run in GitHub Actions: one AI illustration per story from the worker (Workers AI). Failures are reported
    and that story falls back to the drawn illustration."""
    import base64
    import httpx
    out.mkdir(parents=True, exist_ok=True)
    notes = []
    for i, st in enumerate(script["stories"], 1):
        prompt = (st.get("image_prompt") or "").strip() or DEFAULT_PROMPT.get(st["category"], DEFAULT_PROMPT["industry"])
        try:
            r = httpx.post(f"{api.rstrip('/')}/api/recap/image", json={"prompt": prompt}, timeout=120,
                           headers={"Authorization": f"Bearer {secret}"})
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if r.status_code != 200 or not data.get("image"):
                raise RuntimeError(f"HTTP {r.status_code}: {str(data.get('error') or r.text)[:120]}")
            Image.open(__import__("io").BytesIO(base64.b64decode(data["image"]))).convert("RGB").save(out / f"{i}.jpg", quality=90)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"story {i}: no AI image ({exc}); using the drawn illustration")
    return notes


DEFAULT_PROMPT = {
    "models": "An abstract glowing neural network of light filaments floating above a dark server room",
    "research": "A laboratory desk at night with glowing charts on screens and a scientific instrument, close-up",
    "policy": "A government building's stone columns at dusk with a faint digital grid in the sky",
    "safety": "A glowing digital padlock over streams of code in a dark security operations room",
    "industry": "Rows of data-centre server racks with blue light, seen down a long corridor",
    "voices": "An empty conference stage with a single microphone under a spotlight",
}


def stamp(script: dict[str, Any], out_dir: Path, now: datetime) -> dict[str, Any]:
    """Run by the release workflow once the files are checked: mark the recap published so the site shows it."""
    errs = validate(script)
    info = check(out_dir)
    if errs or not info["ok"]:
        raise RuntimeError("; ".join(errs + info["problems"]))
    script["video"] = {k: info[k] for k in ("duration", "bytes", "poster_bytes", "gif_bytes")}
    try:
        made = json.loads((out_dir / "render.json").read_text())
    except Exception:  # noqa: BLE001
        made = {}
    script["video"]["narrated"] = bool(made.get("narrated"))
    try:
        credits = json.loads((out_dir / "clips" / "credits.json").read_text())
    except Exception:  # noqa: BLE001
        credits = []
    used = set(made.get("footage") or [])
    script["footage_credits"] = [c for c in credits if c.get("story") in used]
    script["published_at"] = script.get("published_at") or now.isoformat()
    return script


def load_published(data_dir: Path) -> list[dict[str, Any]]:
    out = []
    for p in sorted((data_dir / "recaps").glob("*.json"), reverse=True):
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if r.get("published_at") and r.get("video") and not validate(r):
            out.append(r)
    return out


def site_view(recaps: list[dict[str, Any]], now: datetime, base: str, repo: str, story_ids: set[str],
              videos: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Everything the pages and the feed need about each recap: which files are on the site, URLs, labels.
    `videos`: story id -> the lab's own YouTube video for that story (from the Watch desk), shown under the recap."""
    videos = videos or {}
    day = now.astimezone(IST).date()
    rows = []
    for r in recaps:
        d = datetime.fromisoformat(r["date"]).date()
        age = (day - d).days
        live, images = age < LIVE_DAYS, age < IMAGE_DAYS
        page = f"videos/{r['date']}/"
        rows.append({
            **r, "age": age, "live": live, "images": images, "page": page, "page_url": base + page,
            "human": _human(r["date"]), "short": f"{d.day} {d.strftime('%b')}",
            "label": "Today's" if age == 0 else ("Yesterday's" if age == 1 else "Latest"),
            "seconds": int(round(r["video"]["duration"])),
            "mp4": f"{page}recap.mp4" if live else asset_url(repo, r["date"], "recap.mp4"),
            "poster": f"{page}poster.jpg" if images else "",
            "poster_url": base + f"{page}poster.jpg" if images else asset_url(repo, r["date"], "poster.jpg"),
            "gif_url": base + f"{page}teaser.gif" if images else asset_url(repo, r["date"], "teaser.gif"),
            "release": f"https://github.com/{repo}/releases/tag/{tag(r['date'])}",
            "entries": [{**s, "href": f"story/{s['id']}/" if s["id"] in story_ids else "",
                         "video": videos.get(s["id"]) if VIDEO_ID.match((videos.get(s["id"]) or {}).get("id") or "") else None}
                        for s in r["stories"]],
            "footage": [c for c in r.get("footage_credits") or [] if str(c.get("url", "")).startswith("https://www.pexels.com/")],
        })
    return rows


def feed(rows: list[dict[str, Any]], base: str) -> str:
    """One item per day: the daily email is triggered from this feed (one new item = one email)."""
    from email.utils import format_datetime
    from xml.sax.saxutils import escape

    def item(r: dict[str, Any]) -> str:
        lis = "".join(
            f'<li style="margin:0 0 12px"><strong>{escape(s["line"])}</strong><br>{escape(s["detail"])} '
            + (f'<a href="{base}{s["href"]}">Read</a>' if s["href"] else "") + f'<br><small>Source: {escape(s["source"])}</small></li>'
            for s in r["entries"])
        html = (f'<p><a href="{r["page_url"]}"><img src="{r["poster_url"]}" width="600" style="width:100%;max-width:600px;height:auto" '
                f'alt="Play the {r["seconds"]}-second recap for {r["human"]}"></a></p>'
                f'<p>{"<br>".join(escape(x) for x in r["summary"])}</p><ol>{lis}</ol>'
                f'<p><a href="{r["page_url"]}">Watch the {r["seconds"]}-second recap</a> · <a href="{base}">Read on Frontier Wire</a></p>')
        return (f"<item><title>{escape('Today in AI, ' + r['human'] + ': ' + r['hook'])}</title>"
                f"<link>{r['page_url']}</link><guid isPermaLink=\"false\">{tag(r['date'])}</guid>"
                f"<pubDate>{format_datetime(datetime.fromisoformat(r['published_at']))}</pubDate>"
                f"<description>{escape(' '.join(r['summary']))}</description>"
                f"<content:encoded><![CDATA[{html}]]></content:encoded>"
                f'<enclosure url="{r["poster_url"]}" type="image/jpeg" length="{int(r["video"].get("poster_bytes") or 0)}"/>'
                f'<media:thumbnail url="{r["poster_url"]}" width="1920" height="1080"/></item>')

    latest = rows[0]["published_at"] if rows else datetime.now(timezone.utc).isoformat()
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
            'xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f"<title>Frontier Wire: daily recap</title><link>{base}videos/</link>"
            f'<atom:link href="{base}videos/feed.xml" rel="self" type="application/rss+xml"/>'
            "<description>The day in AI in 30 seconds: the top five stories, each checked against its sources.</description>"
            f"<lastBuildDate>{format_datetime(datetime.fromisoformat(latest))}</lastBuildDate>"
            + "".join(item(r) for r in rows[:30]) + "</channel></rss>\n")


def latest_json(r: dict[str, Any], base: str) -> dict[str, Any]:
    """What the email worker needs to write the recap email (read from videos/latest.json)."""
    return {"date": r["date"], "human": r["human"], "hook": r["hook"], "summary": r["summary"], "seconds": r["seconds"],
            "page_url": r["page_url"], "poster_url": r["poster_url"], "gif_url": r["gif_url"],
            "entries": [{"line": s["line"], "detail": s["detail"], "source": s["source"], "category": s["category"],
                         "url": base + s["href"] if s["href"] else ""} for s in r["entries"]]}


def build_site(out: Path, env: Any, common: dict[str, Any], base: str, repo: str, data_dir: Path, now: datetime,
               story_ids: set[str], urls: list[str], api_url: str = "", videos: dict[str, dict[str, Any]] | None = None) -> str:
    """Write /videos/, one page per recap and /videos/feed.xml. Returns the home-page strip (empty if no live recap).
    Also writes videos/assets.txt: the Release files the deploy workflow downloads into the site."""
    rows = site_view(load_published(data_dir), now, base, repo, story_ids, videos)
    vdir = out / "videos"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "feed.xml").write_text(feed(rows, base))
    if rows:
        (vdir / "latest.json").write_text(json.dumps(latest_json(rows[0], base), ensure_ascii=False))
    need = []
    for r in rows:
        if r["images"]:
            need += [f"{tag(r['date'])} {r['date']} {a}" for a in ASSETS if a != "recap.mp4" or r["live"]]
        page = vdir / r["date"] / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        og = r["poster_url"]
        page.write_text(env.get_template("recap.html").render(
            **common, r=r, root="../../", api_url=api_url, title=f"Today in AI, {r['human']}: {r['hook']} | Frontier Wire",
            og_title=f"Today in AI, {r['human']}", description=" ".join(r["summary"])[:300], canonical=r["page_url"],
            og_image=og, og_type="video.other"))
        urls.append(r["page_url"])
    (vdir / "assets.txt").write_text("\n".join(need) + ("\n" if need else ""))
    (vdir / "index.html").write_text(env.get_template("videos.html").render(
        **common, rows=rows, root="../", api_url=api_url, title="Daily recaps: today in AI in 30 seconds | Frontier Wire",
        description="Every evening, the day's top five AI stories in a 30-second video, each checked against its sources.",
        canonical=f"{base}videos/", og_image=rows[0]["poster_url"] if rows else f"{base}og/home.png"))
    urls.append(f"{base}videos/")
    top = rows[0] if rows and rows[0]["live"] else None
    return env.get_template("_recap.html").render(**common, r=top, root="") if top else ""
