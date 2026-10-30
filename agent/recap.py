"""Daily 30-second recap: pick the day's top five stories, check the on-screen script, render the video.

The script (hook, one line and one detail per story, a three-line summary) is written by the editor in a Claude
session and saved to data/recaps/YYYY-MM-DD.json. This module drafts that file from the site's own data, checks
it (lengths, headlines paraphrased rather than copied, every story credits its source) and renders original
motion graphics with Pillow and ffmpeg: no photos, no logos, no third-party footage, on-screen text only.

    python -m agent recap draft            # pick today's five, write the skeleton for the editor to fill
    python -m agent recap render --out DIR # check the script, render recap.mp4, poster.jpg, teaser.gif

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
LIMITS = {"hook": 64, "line": 72, "detail": 120, "summary": 150}
MAX_BYTES = 15 * 1024 * 1024
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
            "line": "", "detail": "",
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
        originals = [s.get("headline", "")] + list(s.get("source_titles") or [])
        for key in ("line", "detail"):
            v = s.get(key) or ""
            for o in originals:
                if o and (_similar(v, o) >= 0.72 or _copied_run(v, o)):
                    errs.append(f"story {i}: {key} is too close to a published headline; paraphrase it")
                    break
    return errs


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


def _human(date: str) -> str:
    d = datetime.fromisoformat(date)
    return f"{d.day} {d.strftime('%B %Y')}"


class Renderer:
    def __init__(self, script: dict[str, Any], site_label: str):
        self.s = script
        self.site = site_label
        self.n = len(script["stories"])
        self.total = HOOK_S + STORY_S * self.n + OUTRO_S
        self.bg = _background()
        self.date_h = _human(script["date"])
        self._scenes = [self._story_layers(st, i) for i, st in enumerate(script["stories"])]
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
        f, lines = _fit(st["line"], 1600, (92, 84, 76, 68), 2, 800)
        return {
            "color": color, "seed": st["id"],
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
        if t < HOOK_S:
            out_k = 1 - _ease((t - (HOOK_S - 0.35)) / 0.35)
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
        t2 = t - HOOK_S
        idx = int(t2 // STORY_S)
        if idx < self.n:
            lt = t2 - idx * STORY_S
            L = self._scenes[idx]
            out_k = 1 - _ease((lt - (STORY_S - 0.35)) / 0.35)
            self._chrome(d, idx, lt / STORY_S)
            _signal(d, L["seed"], L["color"], (1000, 150, 1800, 400), t)
            self._place(img, L["num"], 130, 150, lt, 0.0, out_k)
            self._place(img, L["chip"], 140, 400, lt, 0.12, out_k)
            self._place(img, L["line"], 140, 470, lt, 0.25, out_k)
            self._place(img, L["source"], 140, 470 + L["line"].height + 48, lt, 0.45, out_k)
            return img.convert("RGB")
        lt = t2 - self.n * STORY_S
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


def render(script: dict[str, Any], out_dir: Path, site_label: str = "ajsims23.github.io/frontier-wire") -> dict[str, Any]:
    errs = validate(script)
    if errs:
        raise ValueError("script problems:\n- " + "\n- ".join(errs))
    out_dir.mkdir(parents=True, exist_ok=True)
    r = Renderer(script, site_label)
    mp4, poster, gif = out_dir / "recap.mp4", out_dir / "poster.jpg", out_dir / "teaser.gif"
    frames = int(round(r.total * FPS))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "20", "-maxrate", "1600k", "-bufsize", "3200k",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-metadata", f"title=Frontier Wire recap {script['date']}", str(mp4)],
        stdin=subprocess.PIPE)
    assert enc.stdin
    for i in range(frames):
        enc.stdin.write(r.frame(i / FPS).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("ffmpeg failed while encoding")
    r.poster().save(poster, quality=86, optimize=True, progressive=True)
    # teaser: the hook into the first story, small enough for an email
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.8", "-t", "5", "-i", str(mp4), "-vf",
          "fps=10,scale=600:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
          "-loop", "0", str(gif)])
    return check(out_dir)


def check(out_dir: Path) -> dict[str, Any]:
    mp4 = out_dir / "recap.mp4"
    probe = json.loads(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height",
                             "-of", "json", str(mp4)], text=True).stdout)
    v = probe["streams"][0]
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
    """Hand the day's files to GitHub Actions: push them on a short-lived branch `recap-upload/<date>` (main plus one
    commit). The "Recap release" workflow checks them, creates the Release, puts the recap on the site and deletes
    the branch, so the video never lands on main. (Claude sessions can't create Releases themselves.)"""
    errs = validate(script)
    info = check(out_dir)
    if errs or not info["ok"]:
        raise RuntimeError("not uploading: " + "; ".join(errs + info["problems"]))
    branch = f"recap-upload/{script['date']}"
    git = lambda *a: _run(["git", "-C", str(repo_dir), *a], text=True).stdout  # noqa: E731
    git("fetch", "-q", "origin", "main")
    wt = Path(tempfile.mkdtemp(prefix="recap-upload-"))
    try:
        git("worktree", "add", "-q", "--detach", str(wt), "origin/main")
        dest = wt / "recap-upload"
        dest.mkdir()
        for a in ASSETS:
            shutil.copy(out_dir / a, dest / a)
        (dest / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n")
        _run(["git", "-C", str(wt), "add", "-f", "recap-upload"])
        _run(["git", "-C", str(wt), "-c", "user.name=frontier-wire-recap", "-c", "user.email=actions@users.noreply.github.com",
              "commit", "-q", "-m", f"Recap upload {script['date']}"])
        _run(["git", "-C", str(wt), "push", "-q", "--force", "origin", f"HEAD:refs/heads/{branch}"])
    finally:
        subprocess.run(["git", "-C", str(repo_dir), "worktree", "remove", "--force", str(wt)], capture_output=True)
    return branch


def stamp(script: dict[str, Any], out_dir: Path, now: datetime) -> dict[str, Any]:
    """Run by the release workflow once the files are checked: mark the recap published so the site shows it."""
    errs = validate(script)
    info = check(out_dir)
    if errs or not info["ok"]:
        raise RuntimeError("; ".join(errs + info["problems"]))
    script["video"] = {k: info[k] for k in ("duration", "bytes", "poster_bytes", "gif_bytes")}
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


def site_view(recaps: list[dict[str, Any]], now: datetime, base: str, repo: str, story_ids: set[str]) -> list[dict[str, Any]]:
    """Everything the pages and the feed need about each recap: which files are on the site, URLs, labels."""
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
            "entries": [{**s, "href": f"story/{s['id']}/" if s["id"] in story_ids else ""} for s in r["stories"]],
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
               story_ids: set[str], urls: list[str], api_url: str = "") -> str:
    """Write /videos/, one page per recap and /videos/feed.xml. Returns the home-page strip (empty if no live recap).
    Also writes videos/assets.txt: the Release files the deploy workflow downloads into the site."""
    rows = site_view(load_published(data_dir), now, base, repo, story_ids)
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
