"""Daily recap bulletin (a minute and a half to two minutes), in a broadcast news style: pick the day's top five stories, check the on-screen script, render the narrated video.

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

On screen: a 5s opening title, about 10s per story (picture, lower third with the line, the detail and the source,
a stat card), a 4s close, and a headline ticker throughout. Scenes stretch to fit the narration (55-118s in all).

The anchor's bulletin (format 2): the code opens with a greeting for the time of day, a welcome to Frontier Wire
and the date, then the editor's teaser ("open"); each story is told in the anchor's own words ("anchor"); an
optional closing thought ("close") leads into a rotating sign-off that points viewers to the website.
"""
from __future__ import annotations

import json
import math
import random
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFilter

from . import newsgfx
from .cards import GROUND, LABEL, MUTED, TEXT, TOPIC, _font, _wrap

IST = timezone(timedelta(hours=5, minutes=30))
W, H, FPS = 1920, 1080, 30
HOOK_S, STORY_S, OUTRO_S = 5.0, 10.0, 4.0   # 5s open, 10s per story, 4s close: about one minute
MIN_S, MAX_S = 55, 118
SOFT = (179, 207, 203)
PANEL = (10, 31, 34)
LIMITS = {"hook": 64, "line": 72, "detail": 120, "summary": 150, "say": 110, "footage": 80,
          "open": 90, "anchor": 160, "close": 70}
# Format 2 (the anchor programme): a longer teaser, room for context in each story, and a closing thought.
LIMITS_V2 = {"open": 170, "anchor": 230, "close": 110}
ANCHOR_MIN_V2 = 110
# The anchor's read: ~12.2 spoken characters a second for Aura-2 at an unhurried newsreader's pace, so the whole
# bulletin (greeting, teaser, five stories, sign-off) must stay under this many characters (about 105 seconds).
SPOKEN_BUDGET = 740         # format 1 scripts (the one-minute headline read)
SPOKEN_BUDGET_V2 = 1250
CPS = 12.2
# Two original US cable-news anchors, alternating day by day. Aura-2 voices on the
# worker's allow-list; Kokoro voices for the backup. Delivery, not a copy of any real presenter.
ANCHORS = {
    # Played only a little faster than the TTS reads: a hurried read is the quickest way to sound synthetic.
    # gemini: the main voice (Gemini TTS, read at its natural pace); aura and kokoro: the fallbacks
    "female": {"gemini": "Kore", "aura": "thalia", "kokoro": "af_heart", "speed": 1.15},     # firm, crisp, confident
    "male": {"gemini": "Charon", "aura": "odysseus", "kokoro": "am_michael", "speed": 1.1},  # informative, calm, measured
}


def anchor_for(day: str) -> dict[str, str]:
    """Which anchor reads the recap dated `day` (YYYY-MM-DD): alternating female and male day by day
    (RECAP_ANCHOR=male|female overrides it, for voice samples)."""
    import os
    if os.environ.get("RECAP_ANCHOR") in ANCHORS:
        return ANCHORS[os.environ["RECAP_ANCHOR"]]
    try:
        n = date.fromisoformat(str(day)[:10]).toordinal()
    except ValueError:
        n = 0
    return ANCHORS["male" if n % 2 else "female"]


VOICE_SPEED = 1.15          # the read is played 1.15x faster than the TTS delivers it
# A studio-mic broadcast chain on the voice: cut rumble, a little chest warmth and presence, gentle compression
# so every word sits forward like a TV anchor's read.
BROADCAST_CHAIN = ("highpass=f=80,equalizer=f=160:t=q:w=1:g=1.5,equalizer=f=3200:t=q:w=1.2:g=2.5,"
                   "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2")
MAX_SPEED = 1.3             # and sped up a little more, to this at most, when the lines run long
VOICE_LEAD = {"hook": 0.35, "story": 0.3, "outro": 0.2}   # seconds into a scene before the voice starts
VOICE_TAIL = {"hook": 0.5, "story": 0.6, "outro": 0.8}   # a breath after it, before the scene changes
# The anchor's beats inside a scene: after the greeting and date, before the teaser; between a closing thought
# and the sign-off; between a story's line and its detail (format 1).
BEAT = {"hook": 0.55, "story": 0.3, "outro": 0.6}
OUTRO_SAY = "That's the day in AI. Full stories at Frontier Wire."
MAX_BYTES = 15 * 1024 * 1024
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
AGGREGATORS = {"techmeme.com", "news.ycombinator.com", "msn.com"}


# ---------------------------------------------------------------- the anchor's open and sign-off
_ORD = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh",
        "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth",
        "twentieth", "twenty-first", "twenty-second", "twenty-third", "twenty-fourth", "twenty-fifth", "twenty-sixth",
        "twenty-seventh", "twenty-eighth", "twenty-ninth", "thirtieth", "thirty-first"]
_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _two(n: int) -> str:
    return _ONES[n] if n < 20 else _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")


def say_date(day: str) -> str:
    """The date the way an anchor says it: "Wednesday, November eighteenth, twenty twenty-six" (spelled out so
    neither voice misreads it)."""
    d = date.fromisoformat(str(day)[:10])
    yy = d.year % 100
    return f"{d:%A}, {d:%B} {_ORD[d.day]}, {_two(d.year // 100)} {_two(yy) if yy >= 10 else 'oh ' + _ONES[yy]}"


def part_of_day(script: dict[str, Any]) -> str:
    """morning, afternoon or evening in India when the script was written (the bulletin normally goes out at about
    8 PM IST, so evening if the time isn't recorded)."""
    try:
        h = _dt(script["written_at"]).astimezone(IST).hour
    except Exception:  # noqa: BLE001
        return "evening"
    return "morning" if 4 <= h < 12 else "afternoon" if 12 <= h < 17 else "evening"


_OPENERS = (
    "Good {part}, and welcome to Frontier Wire. It's {date}.",
    "Good {part}, and thanks for joining us on Frontier Wire. Today is {date}.",
    "Good {part}. Welcome to Frontier Wire, on this {date}.",
    "Good {part}, everyone, and welcome to Frontier Wire. It's {date}.",
)
_SIGNOFFS = (
    "And that's your AI update for {when}. Thank you for watching Frontier Wire. For more details, deeper insight "
    "and the latest developments, visit our website. Until next time, have a great {rest}.",
    "And that's where we'll leave it {when}. Thanks for watching Frontier Wire. Every story, with its sources, is on "
    "our website. Until next time, have a great {rest}.",
    "That's all from us {when}. Thank you for joining us on Frontier Wire. For the full stories and what comes next, "
    "head to our website. Have a great {rest}, and we'll see you next time.",
    "And that's the day in AI. Thanks for watching Frontier Wire. You'll find more on every story at our website. "
    "Until next time, have a wonderful {rest}.",
)


def _rotate(options: tuple[str, ...], day: str, salt: int = 0) -> str:
    try:
        n = date.fromisoformat(str(day)[:10]).toordinal()
    except ValueError:
        n = 0
    return options[(n + salt) % len(options)]


def greeting(script: dict[str, Any]) -> str:
    """The anchor's first line: greeting for the time of day, welcome, date. Worded a little differently each day."""
    return _rotate(_OPENERS, script.get("date", "")).format(part=part_of_day(script), date=say_date(script["date"]))


def sign_off(script: dict[str, Any]) -> str:
    part = part_of_day(script)
    when = {"morning": "this morning", "afternoon": "this afternoon"}.get(part, "tonight")
    rest = {"morning": "day", "afternoon": "afternoon"}.get(part, "evening")
    return _rotate(_SIGNOFFS, script.get("date", ""), 1).format(when=when, rest=rest)


def is_programme(script: dict[str, Any]) -> bool:
    """Format 2: the code supplies the greeting and sign-off around the editor's anchor copy."""
    try:
        return int(script.get("format") or 1) >= 2
    except (TypeError, ValueError):
        return False


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
        "format": 2,
        "written_at": now.astimezone(IST).isoformat(timespec="minutes"),
        "hook": "",
        "open": "",
        "close": "",
        "summary": ["", "", ""],
        "stories": [{
            "id": s["id"], "category": s["category"], "lab": s.get("lab", ""), "source": credit(s),
            "headline": s["headline"], "summary": s["summary"], "why_it_matters": s.get("why_it_matters", ""),
            "source_titles": [x.get("title", "") for x in s.get("sources") or []],
            "quotes": [{"text": q.get("text", ""), "speaker": q.get("speaker", ""), "role": q.get("speaker_role", "")}
                       for q in (s.get("quotes") or [])[:3] if q.get("text") and q.get("speaker")],
            "line": "", "detail": "", "anchor": "", "graphic": {}, "say": "", "footage": "", "image_prompt": "",
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
    v2 = is_programme(script)
    lim = {**LIMITS, **LIMITS_V2} if v2 else LIMITS
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
        anchor = (s.get("anchor") or "").strip()
        if anchor:
            least = ANCHOR_MIN_V2 if v2 else 70
            if len(anchor) < least:
                errs.append(f"story {i}: anchor copy is too thin (at least {least} characters: what happened, context, why it matters)")
            if _similar(anchor, s.get("line", "")) >= 0.6 or _similar(anchor, (s.get("line", "") + " " + s.get("detail", ""))) >= 0.75:
                errs.append(f"story {i}: anchor copy just repeats the on-screen text; tell the story in your own words with context")
        for key in ("say", "footage", "anchor"):
            if len((s.get(key) or "").strip()) > lim[key]:
                errs.append(f"story {i}: {key} must be at most {lim[key]} characters")
        if len(s.get("image_prompt") or "") > 300:
            errs.append(f"story {i}: image_prompt must be at most 300 characters")
        if v2:  # every story is told with a news graphic built from its own facts
            g = s.get("graphic")
            if not g:
                errs.append(f"story {i}: add a \"graphic\" (map, number, change, bars, list, steps or quote) built from the story's facts")
            else:
                errs += [f"story {i}: {e}" for e in newsgfx.check(g, story_facts(s), s.get("quotes"))]
        originals = [s.get("headline", "")] + list(s.get("source_titles") or [])
        for key in ("line", "detail", "say", "anchor"):
            v = s.get(key) or ""
            for o in originals if v else []:
                if o and (_similar(v, o) >= 0.72 or _copied_run(v, o)):
                    errs.append(f"story {i}: {key} is too close to a published headline; paraphrase it")
                    break
    for key in ("open", "close"):
        if len((script.get(key) or "").strip()) > lim[key]:
            errs.append(f"{key} must be at most {lim[key]} characters")
    anchors = [(st.get("anchor") or "").strip() for st in script.get("stories") or []]
    if v2:
        if not all(anchors):
            errs.append("write anchor copy for every story")
        if len((script.get("open") or "").strip()) < 40:
            errs.append("open: write the anchor's teaser of tonight's stories (40-170 characters)")
        for key in ("open", "close"):
            v = (script.get(key) or "").strip()
            if re.match(r"(?i)\W*good (morning|afternoon|evening|night)\b", v) or "frontier wire" in v.lower():
                errs.append(f"{key}: leave out the greeting, the show's name and the sign-off; the code adds them")
        firsts = [re.split(r"[\s,]+", a.lower())[0] for a in anchors if a]
        if len(firsts) >= 4 and len(set(firsts)) <= 2:
            errs.append("vary how the stories begin; several start with the same word")
    elif any(anchors) and not all(anchors):
        errs.append("write anchor copy for every story, or for none")
    if all(anchors) and anchors:
        budget = SPOKEN_BUDGET_V2 if v2 else SPOKEN_BUDGET
        total = sum(len(t) for k, t in narration(script))
        if total > budget:
            errs.append(f"the spoken bulletin is {total} characters (about {total / CPS:.0f}s); cut it to {budget} "
                        f"(about {budget / CPS:.0f}s)" + ("" if v2 else " so it stays within a minute"))
    return errs


def story_facts(st: dict[str, Any]) -> str:
    """What a story's graphic may draw on: its own reporting and the editor's lines about it."""
    return " ".join(str(st.get(k) or "") for k in ("headline", "summary", "why_it_matters", "line", "detail", "anchor")) + " " + \
        " ".join(st.get("source_titles") or [])


def graphic_for(st: dict[str, Any]) -> dict[str, Any] | None:
    """The story's graphic if it has a valid one, else its key figure as a number graphic, else None."""
    g = st.get("graphic")
    if g and not newsgfx.check(g, story_facts(st), st.get("quotes")):
        return g
    return newsgfx.auto(st, key_figure(st)) if not g else None


# ---------------------------------------------------------------- narration and timing
_UNITS = {"B": "billion", "M": "million", "K": "thousand", "T": "trillion"}


def spoken(text: str) -> str:
    """On-screen shorthand read the way a newsreader would say it."""
    t = text.strip()
    if not t:
        return ""
    t = re.sub(r"\$(\d+(?:\.\d+)?)\s?([BMKT])\b", lambda m: f"{m.group(1)} {_UNITS[m.group(2)]} dollars", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s?([BMKT])\b", lambda m: f"{m.group(1)} {_UNITS[m.group(2)]}", t)
    t = re.sub(r"\$(\d+(?:\.\d+)?)", r"\1 dollars", t)
    t = t.replace("~", "about ").replace("&", " and ").replace(" · ", ", ").replace("/s", " per second")
    t = re.sub(r"\s+", " ", t).strip()
    return t if t.endswith((".", "!", "?")) else t + "."


def narration(script: dict[str, Any]) -> list[tuple[str, str]]:
    """What the voice reads: (file name, text). Each story is two files, the line (story<i>) and the detail
    (story<i>d); the render reads both when they fit in the minute, else the lines alone."""
    stories = script.get("stories") or []
    if is_programme(script):
        # the anchor programme: greeting, welcome and date; a beat; the editor's teaser; each story; an optional
        # closing thought; a beat; the sign-off
        teaser, kicker = (script.get("open") or "").strip(), (script.get("close") or "").strip()
        out = [("hook", greeting(script)), ("hookd", spoken(teaser) if teaser else "")]
        for i, st in enumerate(stories, 1):
            out.append((f"story{i}", spoken(st.get("anchor") or "")))
            out.append((f"story{i}d", ""))
        out.append(("outro", spoken(kicker) if kicker else sign_off(script)))
        out.append(("outrod", sign_off(script) if kicker else ""))
        return out
    if all((st.get("anchor") or "").strip() for st in stories) and stories:
        # the anchor's bulletin: an opening, each story told in the anchor's own words, a sign-off
        out = [("hook", spoken((script.get("open") or "").strip() or "Good evening. This is Frontier Wire."))]
        for i, st in enumerate(stories, 1):
            out.append((f"story{i}", spoken(st["anchor"])))
            out.append((f"story{i}d", ""))
        out.append(("outro", spoken((script.get("close") or "").strip() or OUTRO_SAY)))
        return out
    out = [("hook", spoken("This is Frontier Wire. " + script["hook"]))]
    for i, st in enumerate(stories, 1):
        out.append((f"story{i}", spoken((st.get("say") or "").strip() or st["line"])))
        out.append((f"story{i}d", spoken(st["detail"])))
    out.append(("outro", OUTRO_SAY))
    return out


def _join(a: Path, b: Path, pause: float, f: Path) -> tuple[Path, float]:
    """Two reads as one clip, with the anchor's beat between them."""
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-i", str(b), "-filter_complex",
          f"[0:a]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur={pause}[a];[1:a]aresample=44100,aformat=channel_layouts=mono[b];[a][b]concat=n=2:v=0:a=1[o]",
          "-map", "[o]", str(f)])
    return f, _duration(f)


def compose_voice(vc: dict[str, tuple[Path, float]], n: int, with_detail: bool, work: Path) -> dict[str, tuple[Path, float]]:
    """One clip per scene (hook, story1..n, outro). The opening is the greeting, a beat, then the teaser; the close is
    the closing thought, a beat, then the sign-off; each story is its line, then (with_detail) a short pause and its
    detail."""
    out = {}
    for key in ("hook", "outro"):
        out[key] = _join(vc[key][0], vc[key + "d"][0], BEAT[key], work / f"{key}.full.wav") if key + "d" in vc else vc[key]
    for i in range(1, n + 1):
        if not with_detail or f"story{i}d" not in vc:
            out[f"story{i}"] = vc[f"story{i}"]
            continue
        out[f"story{i}"] = _join(vc[f"story{i}"][0], vc[f"story{i}d"][0], BEAT["story"], work / f"story{i}.full.wav")
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
    for key, text in narration(script):
        if not text:
            continue
        f = voice_dir / f"{key}.mp3"
        if not f.exists() and key.endswith("d") and (voice_dir / f"{key[:-1]}.mp3").exists():
            continue  # a one-take voice (Gemini) reads a scene's second part in the same clip
        try:
            out[key] = (f, _duration(f))
        except Exception:  # noqa: BLE001
            return {}
    return out


def voice_provider(voice_dir: Path | None) -> str:
    try:
        return json.loads((voice_dir / "provider.json").read_text()).get("provider", "")
    except Exception:  # noqa: BLE001
        return ""


def timing(n: int, clips: dict[str, tuple[Path, float]], speed: float = VOICE_SPEED) -> tuple[list[float], float]:
    """Scene lengths [hook, story 1..n, outro] and the voice tempo. Silent: 3s, 5s each, 2s. Narrated: each scene
    is long enough for its line, read at VOICE_SPEED (never shorter than the silent length). If that runs long the
    quiet tails shrink, then the voice is sped up further (at most MAX_SPEED). Tempo 0 means the lines can't fit:
    render silent."""
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
        if sum(lay(speed, squeeze)) <= cap:
            return lay(speed, squeeze), speed
    lo, hi = speed, MAX_SPEED
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
        f"amix=inputs={len(keys)}:normalize=0,{BROADCAST_CHAIN},loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=0:{total:.3f}[out]"
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


def _pexels(http: Any, q: str, key: str) -> list[dict[str, Any]]:
    """Candidate clips from Pexels: [{id, link, name, url, provider}]."""
    params = {"query": q, "orientation": "landscape", "size": "medium", "per_page": 15}
    r = http.get("https://api.pexels.com/v1/videos/search", params=params, headers={"Authorization": key})
    if r.status_code == 404:
        r = http.get("https://api.pexels.com/videos/search", params=params, headers={"Authorization": key})
    r.raise_for_status()
    out = []
    for v in r.json().get("videos") or []:
        if not 6 <= (v.get("duration") or 0) <= 60:
            continue
        files = [f for f in v.get("video_files") or [] if f.get("file_type") == "video/mp4"
                 and 1280 <= (f.get("width") or 0) <= 1920 and (f.get("height") or 0) >= 720]
        if files:
            f = min(files, key=lambda f: abs((f.get("width") or 0) - 1920))
            out.append({"id": f"px{v['id']}", "link": f["link"], "name": ((v.get("user") or {}).get("name") or "")[:60],
                        "url": v.get("url") or "https://www.pexels.com", "provider": "Pexels"})
    return out


def _pixabay(http: Any, q: str, key: str) -> list[dict[str, Any]]:
    """Candidate clips from Pixabay (free key, Pixabay Content License, no attribution required; we credit anyway)."""
    r = http.get("https://pixabay.com/api/videos/", params={"key": key, "q": q[:100], "video_type": "film",
                                                            "safesearch": "true", "per_page": 15})
    r.raise_for_status()
    out = []
    for v in r.json().get("hits") or []:
        if not 6 <= (v.get("duration") or 0) <= 60:
            continue
        vids = v.get("videos") or {}
        f = next((vids[k] for k in ("large", "medium") if (vids.get(k) or {}).get("url") and (vids[k].get("width") or 0) >= 1280), None)
        if f:
            out.append({"id": f"pb{v['id']}", "link": f["url"], "name": (v.get("user") or "")[:60],
                        "url": v.get("pageURL") or "https://pixabay.com", "provider": "Pixabay"})
    return out


UA = "FrontierWire/1.0 (https://ajsims23.github.io/frontier-wire/; recap bot)"
FREE_LICENSES = re.compile(r"^(cc0|public domain|pd|cc by \d(\.\d)?|cc-by-\d(\.\d)?)$", re.I)


def _commons(http: Any, q: str, key: str = "") -> list[dict[str, Any]]:
    """Candidate clips from Wikimedia Commons (no key). Only public domain, CC0 or CC BY (attribution, no share-alike),
    and only the site's own 720p/1080p transcodes, so we never pull a huge original."""
    r = http.get("https://commons.wikimedia.org/w/api.php", headers={"User-Agent": UA}, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f"{q} filetype:video", "prop": "videoinfo",
        "viprop": "url|size|mediatype|extmetadata|derivatives"})
    r.raise_for_status()
    out = []
    words = [w[:5] for w in re.findall(r"[a-z]+", q.lower()) if len(w) > 2]
    need = min(2, len(words))
    for page in ((r.json().get("query") or {}).get("pages") or {}).values():
        title = (page.get("title") or "").lower()
        if sum(w in title for w in words) < need:  # Commons search also matches descriptions; insist on the title
            continue
        info = (page.get("videoinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = re.sub(r"\s+", " ", ((meta.get("LicenseShortName") or {}).get("value") or "")).strip()
        if not FREE_LICENSES.match(lic):
            continue
        dur = info.get("duration")
        if dur is not None and not 6 <= float(dur) <= 900:
            continue
        ders = [d for d in info.get("derivatives") or [] if 700 <= (d.get("height") or 0) <= 1080
                and (d.get("width") or 0) >= 1200 and str(d.get("src", "")).startswith("https://upload.wikimedia.org/")]
        if not ders:
            continue
        d = min(ders, key=lambda d: d.get("height") or 0)
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value") or "").strip()
        out.append({"id": f"wc{page.get('pageid')}", "link": d["src"], "name": (artist or "Wikimedia Commons")[:60],
                    "url": info.get("descriptionurl") or "https://commons.wikimedia.org", "provider": f"Wikimedia Commons, {lic}",
                    "ffmpeg": True})
    return out


def _download(http: Any, c: dict[str, Any], dest: Path) -> None:
    if c.get("ffmpeg"):  # read only the first 15 seconds of the stream and re-encode to MP4
        _run(["ffmpeg", "-v", "error", "-y", "-user_agent", UA, "-t", "15", "-i", c["link"], "-an", "-c:v", "libx264",
              "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(dest)], timeout=180)
        if _duration(dest) < 5:
            raise RuntimeError("clip too short")
        return
    with http.stream("GET", c["link"]) as dl:
        dl.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in dl.iter_bytes():
                fh.write(chunk)


def fetch_footage(script: dict[str, Any], out: Path, pexels_key: str = "", pixabay_key: str = "") -> list[str]:
    """Run in GitHub Actions: one free stock clip per story, from Pexels and/or Pixabay (whichever keys exist), searched
    by the editor's `footage` query, else a query for the story's beat. Saves out/<i>.mp4 and out/credits.json.
    Failures are reported; that story falls back to the AI illustration."""
    import httpx
    out.mkdir(parents=True, exist_ok=True)
    # Pexels / Pixabay when their keys exist; Wikimedia Commons (no key) always, as the last resort
    sources = [(fn, k) for fn, k in ((_pexels, pexels_key), (_pixabay, pixabay_key)) if k] + [(_commons, "")]
    notes, used, credits = [], set(), []
    with httpx.Client(timeout=60, follow_redirects=True) as http:
        for i, st in enumerate(script["stories"], 1):
            if is_programme(script) and st.get("graphic"):
                continue  # told with a news graphic: no stock clip (they too often show unrelated people)
            q = (st.get("footage") or "").strip() or DEFAULT_FOOTAGE.get(st["category"], DEFAULT_FOOTAGE["industry"])
            try:
                cands, errs = [], []
                for fn, k in sources:
                    if cands and fn is _commons:
                        break  # a stock library had something; Commons is only the fallback
                    try:
                        cands += [c for c in fn(http, q, k) if c["id"] not in used][:4]
                    except Exception as exc:  # noqa: BLE001
                        errs.append(f"{fn.__name__[1:]}: {str(exc)[:80]}")
                if not cands:
                    raise RuntimeError(f"no usable clip for {q!r}" + (f" ({'; '.join(errs)})" if errs else ""))
                random.Random(st["id"]).shuffle(cands)
                dest = out / f"{i}.mp4"
                for c in cands[:3]:  # try a few before giving up on this story
                    try:
                        _download(http, c, dest)
                        if usable_clip(dest):
                            break
                    except Exception as exc:  # noqa: BLE001
                        errs.append(f"{c['id']}: {str(exc)[:80]}")
                    dest.unlink(missing_ok=True)
                else:
                    raise RuntimeError("no clip downloaded (" + "; ".join(errs[-3:]) + ")")
                used.add(c["id"])
                credits.append({"story": i, "name": c["name"] or f"{c['provider']} contributor", "url": c["url"], "provider": c["provider"]})
            except Exception as exc:  # noqa: BLE001
                notes.append(f"story {i}: no stock clip ({str(exc)[:160]}); using the illustration")
    (out / "credits.json").write_text(json.dumps(credits, indent=2))
    return notes


def fetch_voice(script: dict[str, Any], out: Path, api: str, secret: str) -> list[str]:
    """Run in GitHub Actions: the narration, one MP3 per scene, from the worker (Workers AI, Deepgram Aura-2)."""
    import base64
    import httpx
    out.mkdir(parents=True, exist_ok=True)
    notes = []
    for key, text in narration(script):
        if not text:
            continue
        try:
            r = httpx.post(f"{api.rstrip('/')}/api/recap/voice", json={"text": text, "speaker": anchor_for(script.get("date", ""))["aura"]}, timeout=90,
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


# ---------------------------------------------------------------- the main voice: Gemini TTS
# An acted read from Google's Gemini TTS (free tier: 10 requests a day per model). The whole bulletin is read in ONE
# take, scenes separated by long pauses, so the anchor's tone carries from story to story; the take is then cut
# into scenes at its longest silences. If the cut doesn't line up, each scene is read separately; if a model is out
# of quota, the next one is tried. Aura-2 (Workers AI) and Kokoro stay as the fallbacks.
GEMINI_MODELS = ("gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview")
GEMINI_STYLE = {
    "female": "Warm, confident American evening-news anchor. Clear, crisp and unhurried, with natural emphasis.",
    "male": "Warm, authoritative American evening-news anchor. Calm, measured and unhurried, with natural emphasis.",
}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def scene_texts(script: dict[str, Any]) -> list[tuple[str, str]]:
    """The bulletin as scenes (hook, story1..n, outro), each one take's worth of text with its inner beat marked."""
    said = dict(narration(script))
    keys = ["hook"] + [f"story{i}" for i in range(1, len(script.get("stories") or []) + 1)] + ["outro"]
    out = []
    for k in keys:
        a, b = said.get(k, ""), said.get(k + "d", "")
        out.append((k, f"{a} <short pause> {b}" if a and b else a or b))
    return out


def _gemini_say(http: Any, model: str, key: str, voice: str, style: str, text: str) -> tuple[bytes, int]:
    """One Gemini TTS request -> (16-bit mono PCM, sample rate). Raises with the API's own message on failure."""
    import base64
    if model.startswith("gemini-3.8"):
        part = {"text": text, "speech_metadata": {"style": style}}
    else:  # earlier models take the direction as a prompt line, and square-bracket pause tags
        part = {"text": f"{style} Read this news bulletin:\n" + text.replace("<short pause>", "[short pause]").replace("<long pause>", "[long pause]")}
    body = {"contents": [{"role": "user", "parts": [part]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    r = http.post(GEMINI_URL.format(model=model), json=body, headers={"x-goog-api-key": key}, timeout=300)
    if r.status_code == 400 and model.startswith("gemini-3.8"):  # the newer voice field, if the classic one is refused
        body["generationConfig"]["speechConfig"] = {"voiceConfig": {"voice": voice}}
        r = http.post(GEMINI_URL.format(model=model), json=body, headers={"x-goog-api-key": key}, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"{model} HTTP {r.status_code}: {r.text[:200]}")
    inline = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    data = base64.b64decode(inline["data"])
    if data[:4] == b"RIFF":  # a WAV file: find the PCM
        import io
        import wave
        with wave.open(io.BytesIO(data)) as w:
            return w.readframes(w.getnframes()), w.getframerate()
    m = re.search(r"rate=(\d+)", inline.get("mimeType", ""))
    return data, int(m.group(1)) if m else 24000


def _pcm_to_wav(pcm: bytes, rate: int, f: Path) -> Path:
    import wave
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return f


def _silences(wav: Path, min_s: float = 0.35) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af", f"silencedetect=noise=-35dB:d={min_s}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def split_take(wav: Path, texts: list[str], out: Path, keys: list[str]) -> bool:
    """Cut one take into len(texts) scenes at the anchor's long pauses. Picks the set of pauses that together are
    longest while keeping every scene close to its share of the words (dynamic programming over the take's
    pauses). False (and nothing written) if no sensible set exists, so the caller reads scene by scene instead."""
    total = _duration(wav)
    gaps = [((a_ + b_) / 2, b_ - a_) for a_, b_ in _silences(wav, 0.22)]
    chars = sum(len(t) for t in texts)
    exp = [total * len(t) / chars for t in texts]
    n, k = len(texts), len(gaps)
    if k < n - 1:
        return False

    def fit(i: int, dur: float) -> float:   # how far scene i's length is from its share, in log terms
        return abs(math.log(max(dur, 0.1) / exp[i]))

    # best[j][g]: best score with cut j placed at gap g (cuts 0..j used)
    LAM = 0.5
    best = [[-1e9] * k for _ in range(n - 1)]
    prev = [[-1] * k for _ in range(n - 1)]
    for g, (m, w) in enumerate(gaps):
        best[0][g] = w - LAM * fit(0, m)
    for j in range(1, n - 1):
        for g, (m, w) in enumerate(gaps):
            for h in range(g):
                if best[j - 1][h] <= -1e8:
                    continue
                sc = best[j - 1][h] + w - LAM * fit(j, m - gaps[h][0])
                if sc > best[j][g]:
                    best[j][g], prev[j][g] = sc, h
    last = max(range(k), key=lambda g: best[n - 2][g] - LAM * fit(n - 1, total - gaps[g][0]) if best[n - 2][g] > -1e8 else -1e9)
    if best[n - 2][last] <= -1e8:
        return False
    picks = [last]
    for j in range(n - 2, 0, -1):
        picks.append(prev[j][picks[-1]])
    bounds = [0.0] + [gaps[g][0] for g in reversed(picks)] + [total]
    for i in range(n):  # a sanity check: no scene wildly off its share of the words
        if not 0.5 <= (bounds[i + 1] - bounds[i]) / exp[i] <= 1.9:
            print(f"split: scene {i + 1} would run {bounds[i + 1] - bounds[i]:.1f}s against {exp[i]:.1f}s expected", flush=True)
            return False
    print("split: cuts at " + ", ".join(f"{x:.1f}s" for x in bounds[1:-1]) + f" of {total:.1f}s", flush=True)
    for i, key in enumerate(keys):
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{bounds[i]:.3f}", "-to", f"{bounds[i + 1]:.3f}", "-i", str(wav), "-af", _TRIM,
              "-c:a", "libmp3lame", "-q:a", "2", str(out / f"{key}.mp3")])
    return True


_TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
         "silenceremove=start_periods=1:start_threshold=-45dB,areverse")


def fetch_voice_gemini(script: dict[str, Any], out: Path, key: str, http: Any = None) -> list[str]:
    """Run in GitHub Actions: the anchor's read from Gemini TTS into out/<scene>.mp3 (and out/provider.json).
    Returns notes; an empty list means the narration is in place. On failure nothing is left behind."""
    import time
    if not key:
        return ["no GEMINI_API_KEY; using the fallback voices"]
    if http is None:
        import httpx
        http = httpx.Client()
    out.mkdir(parents=True, exist_ok=True)
    who = "male" if anchor_for(script.get("date", ""))["aura"] == ANCHORS["male"]["aura"] else "female"
    voice, style = ANCHORS[who]["gemini"], GEMINI_STYLE[who]
    scenes = [(k, t) for k, t in scene_texts(script) if t]
    keys, texts = [k for k, _ in scenes], [t for _, t in scenes]
    notes: list[str] = []
    for model in GEMINI_MODELS:
        try:  # one take, the way an anchor reads the whole bulletin
            pcm, rate = _gemini_say(http, model, key, voice, style, " <long pause> ".join(texts))
            take = _pcm_to_wav(pcm, rate, out / "take.wav")
            if split_take(take, texts, out, keys):   # the take stays in the voice folder (never published)
                (out / "provider.json").write_text(json.dumps({"provider": "gemini", "model": model, "voice": voice, "mode": "one take"}))
                return []
            take.rename(out / "take-unsplit.wav")
            notes.append(f"{model}: the one-take read didn't split cleanly into scenes; reading scene by scene")
            for i, (k, t) in enumerate(scenes):  # scene by scene, inside the 3-requests-a-minute limit
                if i:
                    time.sleep(21)
                pcm, rate = _gemini_say(http, model, key, voice, style, t)
                wav = _pcm_to_wav(pcm, rate, out / f"{k}.wav")
                _run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", _TRIM, "-c:a", "libmp3lame", "-q:a", "2", str(out / f"{k}.mp3")])
                wav.unlink()
            (out / "provider.json").write_text(json.dumps({"provider": "gemini", "model": model, "voice": voice, "mode": "scene by scene"}))
            return []
        except Exception as exc:  # noqa: BLE001 - out of quota, refused, malformed: try the next model
            notes.append(f"{model}: {str(exc)[:200]}")
            for f in list(out.glob("*.mp3")) + [x for x in out.glob("*.wav") if x.name != "take-unsplit.wav"] + list(out.glob("provider.json")):
                f.unlink()
    return notes + ["no Gemini narration; using the fallback voices"]


KOKORO_SPEED = 0.9   # open-source Kokoro-82M reads faster than Aura-2; slowed so the backup keeps the same unhurried pace
# (about 15 spoken characters a second once the anchor's tempo is applied). The voice follows the day's anchor (ANCHORS)


def fetch_voice_backup(script: dict[str, Any], out: Path, model_dir: Path) -> list[str]:
    """Run in GitHub Actions when the Workers AI voice fails: the same narration from Kokoro (open weights, runs on
    the runner's CPU, no key, no quota). model_dir holds kokoro-v1.0.onnx and voices-v1.0.bin."""
    import soundfile as sf
    from kokoro_onnx import Kokoro
    out.mkdir(parents=True, exist_ok=True)
    k = Kokoro(str(model_dir / "kokoro-v1.0.onnx"), str(model_dir / "voices-v1.0.bin"))
    voice = anchor_for(script.get("date", ""))["kokoro"]
    notes = []
    for key, text in narration(script):
        if not text:
            continue
        try:
            audio, sr = k.create(text, voice=voice, speed=KOKORO_SPEED, lang="en-us")
            wav = out / f"{key}.wav"
            sf.write(wav, audio, sr)
            _run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af",
                  "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                  "-c:a", "libmp3lame", "-q:a", "3", str(out / f"{key}.mp3")])
            wav.unlink()
        except Exception as exc:  # noqa: BLE001
            notes.append(f"{key}: no backup narration ({str(exc)[:120]})")
    if notes:
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


RED = (226, 54, 54)
INK = (8, 14, 16)
PAPER = (244, 246, 245)


# ---------------------------------------------------------------- the studio set (opening shot)
WALL = (300, 110, 1620, 690)   # the video wall behind the desk, in frame coordinates


def _vgrad(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    col = Image.new("RGB", (1, h))
    for y in range(h):
        k = y / max(1, h - 1)
        col.putpixel((0, y), tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)))
    return col.resize((w, h))


def _studio_set() -> Image.Image:
    """An original, generated TV-news studio: a lit back wall, a big video wall, side screens, a glossy floor that
    reflects the wall, and a curved anchor desk carrying the Frontier Wire wordmark. Drawn once, reused per frame."""
    img = _vgrad(W, H, (10, 20, 40), (3, 8, 18)).convert("RGBA")
    # back-wall light columns
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i, x in enumerate(range(60, W, 180)):
        c = TOPIC["research"] if i % 2 else (70, 120, 220)
        gd.rectangle((x, 40, x + 14, 760), fill=c + (150,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3)))
    d = ImageDraw.Draw(img)
    # side screens, angled toward camera
    for (x0, x1, near) in ((40, 250, 0), (1670, 1880, 1)):
        top_in, bot_in = (180, 640)
        pts = [(x0, 170 if near else 210), (x1, 210 if near else 170), (x1, 670 if near else 630), (x0, 630 if near else 670)]
        d.polygon(pts, fill=(14, 30, 52))
        d.line(pts + [pts[0]], fill=(40, 70, 100), width=4)
        for j, c in enumerate((TOPIC["models"], TOPIC["research"], TOPIC["policy"], TOPIC["industry"])):
            y = 260 + j * 90
            d.rectangle((x0 + 40, y, x0 + 40 + 60 + 25 * ((j * 7 + near * 3) % 5), y + 34), fill=c)
    # the video wall: bezel, panel seams
    x0, y0, x1, y1 = WALL
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((x0 - 30, y0 - 20, x1 + 30, y1 + 40), fill=(0, 0, 0, 200))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(24)))
    d = ImageDraw.Draw(img)
    d.rectangle((x0 - 14, y0 - 14, x1 + 14, y1 + 14), fill=(20, 26, 34))
    img.paste(_vgrad(x1 - x0, y1 - y0, (16, 44, 76), (6, 16, 30)), (x0, y0))
    d = ImageDraw.Draw(img)
    for x in range(x0, x1, (x1 - x0) // 4):
        d.line((x, y0, x, y1), fill=(4, 10, 18), width=2)
    for y in range(y0, y1, (y1 - y0) // 3):
        d.line((x0, y, x1, y), fill=(4, 10, 18), width=2)
    # floor with perspective lines and a soft reflection of the wall
    floor_y = 745
    img.paste(_vgrad(W, H - floor_y, (12, 22, 38), (4, 8, 14)), (0, floor_y))
    d = ImageDraw.Draw(img)
    for k in range(-12, 13):
        d.line((W / 2 + k * 40, floor_y, W / 2 + k * 260, H), fill=(22, 36, 56), width=2)
    refl = img.crop((x0, y0, x1, y1)).transpose(Image.FLIP_TOP_BOTTOM).resize((x1 - x0, 140))
    mask = _vgrad(x1 - x0, 140, (70, 70, 70), (0, 0, 0)).convert("L")
    img.paste(refl, (x0, floor_y), mask)
    # the anchor desk: glossy curved top, dark front, teal light strip, wordmark
    d = ImageDraw.Draw(img)
    cx = W / 2
    d.polygon([(470, 792), (cx, 770), (W - 470, 792), (W - 390, 836), (cx, 814), (390, 836)], fill=(200, 212, 224))
    d.polygon([(390, 836), (cx, 814), (W - 390, 836), (W - 390, 858), (cx, 836), (390, 858)], fill=(118, 134, 150))
    d.polygon([(390, 858), (cx, 836), (W - 390, 858), (W - 430, 1010), (430, 1010)], fill=(12, 24, 40))
    strip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(strip).line([(400, 872), (cx, 850), (W - 400, 872)], fill=TOPIC["research"] + (255,), width=6)
    img.alpha_composite(strip.filter(ImageFilter.GaussianBlur(6)))
    img.alpha_composite(strip)
    d = ImageDraw.Draw(img)
    wm = _font(46, 820, 125)
    tw = d.textlength("FRONTIER WIRE", font=wm)
    x = int(cx - (tw + 70) / 2)
    for i, (h, c) in enumerate([(26, TOPIC["models"]), (40, TOPIC["research"]), (20, TOPIC["policy"]), (32, TOPIC["industry"])]):
        d.rounded_rectangle((x + i * 14, 948 - h, x + i * 14 + 8, 948), radius=3, fill=c)
    d.text((x + 70, 902), "FRONTIER WIRE", font=wm, fill=TEXT)
    # a desk microphone
    d.line((1130, 790, 1150, 730), fill=(40, 44, 50), width=6)
    d.ellipse((1136, 700, 1168, 738), fill=(30, 32, 38))
    d.ellipse((1100, 784, 1160, 800), fill=(30, 32, 38))
    return img


class Renderer:
    """Broadcast-style recap: an opening title, one full-screen scene per story (picture behind, a lower third with
    the headline, the detail and the source, a stat card for the key figure), a closing card, and a headline ticker
    crawling along the bottom throughout."""

    def __init__(self, script: dict[str, Any], site_label: str, images: Path | None = None,
                 durations: list[float] | None = None, clips: Path | None = None):
        self.s = script
        self.images: dict[int, Image.Image] = {}
        self.clips: dict[int, Clip] = {}
        self.credits: dict[int, str] = {}
        self.provider: dict[int, str] = {}
        if clips and clips.exists():
            try:
                meta = {c["story"]: c for c in json.loads((clips / "credits.json").read_text())}
            except Exception:  # noqa: BLE001
                meta = {}
            for i in range(len(script["stories"])):
                f = clips / f"{i + 1}.mp4"
                if f.exists() and usable_clip(f):
                    self.clips[i] = Clip(f, W, H)
                    self.credits[i] = (meta.get(i + 1) or {}).get("name", "")
                    self.provider[i] = (meta.get(i + 1) or {}).get("provider", "Pexels")
        if images:
            for i in range(len(script["stories"])):
                f = images / f"{i + 1}.jpg"
                if f.exists():
                    try:
                        self.images[i] = _cover(Image.open(f).convert("RGB"), int(W * 1.1), int(H * 1.1))
                    except Exception:  # noqa: BLE001 - a broken image falls back to the drawn illustration
                        pass
        self.site = site_label
        self.n = len(script["stories"])
        self.durs = durations or [HOOK_S] + [STORY_S] * self.n + [OUTRO_S]
        assert len(self.durs) == self.n + 2
        self.starts = [sum(self.durs[:i]) for i in range(len(self.durs))]
        self.total = sum(self.durs)
        self.bg = _background()
        self.date_h = _human(script["date"])
        self.shade = self._shade()
        self._scenes = [self._story_layers(st, i) for i, st in enumerate(script["stories"])]
        small = _font(24, 600)
        self.ai_label = _plate(_text_layer(["AI-generated illustration"], small, (215, 226, 224)))
        self.clip_labels = {i: _plate(_text_layer([f"Footage: {self.credits[i]} / {self.provider[i]}" if self.credits[i] else f"Footage: {self.provider[i]}"], small, (215, 226, 224)))
                            for i in self.clips}
        # opening and closing
        f, lines = _fit(script["hook"], 1600, (96, 88, 80, 72), 2, 820)
        self.hook = _text_layer(lines, f, TEXT, 1.06)
        self.eyebrow = _text_layer(["TODAY IN AI"], _font(44, 820, 112), INK)
        self.open_date = _text_layer([self.date_h.upper()], _font(36, 700, 112), TEXT)
        self.count = _text_layer([f"The day's top {self.n} stories in " + ("one minute" if 50 <= self.total <= 70 else "under two minutes")], _font(36, 500), SOFT)
        f, lines = _fit(script["hook"], WALL[2] - WALL[0] - 140, (74, 68, 62, 56), 2, 820)
        self.wall_hook = _text_layer(lines, f, TEXT, 1.06)
        self._studio: Image.Image | None = None
        self.out1 = _text_layer(["That's the day in AI."], _font(92, 820), TEXT)
        self.out2 = _text_layer([site_label], _font(54, 700, 110), TOPIC["research"])
        self.out3 = _text_layer(["Every story, with its sources. Updated every three hours by our newsroom agent."], _font(32, 500), MUTED)
        # the ticker
        tk = _font(30, 650)
        items = "      ·      ".join(st["line"].upper() for st in script["stories"])
        self.ticker = _text_layer([items + "      ·      "], tk, TEXT)
        self.tick_label = _text_layer(["HEADLINES"], _font(28, 820, 112), INK)
        self.bug = _text_layer(["TODAY IN AI"], _font(26, 820, 112), INK)
        self.date_l = _text_layer([self.date_h.upper()], _font(26, 700, 110), TEXT)

    def _shade(self) -> Image.Image:
        """Darkening over full-screen pictures: strong at the bottom (for the lower third) and a little at the top."""
        g = Image.new("L", (1, H))
        for y in range(H):
            v = 0.25 + 0.65 * max(0.0, (y - H * 0.35) / (H * 0.65)) ** 1.3 + 0.25 * max(0.0, 1 - y / (H * 0.18))
            g.putpixel((0, y), int(255 * min(0.95, v)))
        alpha = g.resize((W, H))
        layer = Image.new("RGBA", (W, H), INK + (0,))
        layer.putalpha(alpha)
        return layer

    def _story_layers(self, st: dict[str, Any], i: int) -> dict[str, Any]:
        color = TOPIC.get(st["category"], TOPIC["industry"])
        label = LABEL.get(st["category"], "News").upper() + (f"  ·  {st['lab'].upper()}" if st.get("lab") else "")
        f, lines = _fit(st["line"], 1620, (64, 58, 54), 2, 820)
        head = _text_layer(lines, f, INK, 1.08)
        fd, dl = _fit(st["detail"], 1620, (38, 34, 32), 2, 520)
        detail = _text_layer(dl, fd, TEXT, 1.15)
        source = _text_layer([f"SOURCE: {st['source'].upper()}"], _font(26, 700, 110), MUTED)
        chip = _text_layer([label], _font(30, 820, 112), INK)
        fig = key_figure(st)
        figl = None
        if fig:
            tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
            for size in range(150, 54, -6):
                ffig = _font(size, 820, 100 if len(fig) > 8 else 105)
                if tmp.textlength(fig, font=ffig) <= 520:
                    break
            figl = _text_layer([fig], ffig, TEXT, 1.0)
        spec = graphic_for(st) if is_programme(self.s) or st.get("graphic") else None
        return {"color": color, "seed": st["id"], "cat": st["category"], "head": head, "detail": detail,
                "source": source, "chip": chip, "figure": figl, "spec": spec, "gfx": None,
                "num": _text_layer([f"{i + 1}/{self.n}"], _font(26, 700, 110), TEXT)}

    def _graphic(self, L: dict[str, Any], w: int, h: int) -> "newsgfx.Graphic | None":
        if L["spec"] and L["gfx"] is None:
            try:
                L["gfx"] = newsgfx.Graphic(L["spec"], L["color"], w, h)
            except Exception as exc:  # noqa: BLE001 - a graphic that can't be drawn falls back to the picture
                print(f"::warning::graphic for {L['seed']} not drawn ({str(exc)[:120]})", flush=True)
                L["spec"] = None
        return L["gfx"]

    def _backdrop(self, w: int, h: int, color: tuple[int, int, int], t: float, seed: str) -> Image.Image:
        """The graphics studio: the dark ground with a slow glow of the story's colour drifting behind."""
        img = (self.bg if self.bg.size == (w, h) else _cover(self.bg, w, h)).copy().convert("RGBA")
        g = Image.new("RGBA", (w // 8, h // 8), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        ph = (sum(map(ord, seed)) % 7) / 7 * math.tau
        cx, cy = g.width * (0.7 + 0.12 * math.sin(t * 0.25 + ph)), g.height * (0.3 + 0.1 * math.cos(t * 0.2 + ph))
        for r in range(int(g.width * 0.6), 0, -4):
            a = int(46 * (1 - r / (g.width * 0.6)) ** 1.5)
            gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (a,))
        img.alpha_composite(g.resize((w, h), Image.BILINEAR))
        return img

    # ------------------------------------------------------------ pieces
    def _picture(self, idx: int, lt: float, dur: float) -> tuple[Image.Image | None, str]:
        if idx in self.clips:
            pic = self.clips[idx].frame(int(lt * FPS))
            if lt + 1 / FPS >= dur:
                self.clips[idx].close()
            if pic is not None:
                return pic, "clip"
        if idx in self.images:
            big = self.images[idx]
            z = 0.1 * (lt / dur)  # slow push-in across the scene
            cw, ch = int(big.width * (1 - z * 0.9)), int(big.height * (1 - z * 0.9))
            ox, oy = (big.width - cw) // 2, int((big.height - ch) * 0.4)
            return big.crop((ox, oy, ox + cw, oy + ch)).resize((W, H), Image.BILINEAR), "image"
        return None, ""

    def _ticker(self, img: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(img)
        y0 = H - 72
        d.rectangle((0, y0, W, H), fill=(6, 18, 20))
        d.rectangle((0, y0, W, y0 + 3), fill=TOPIC["research"])
        lw = self.tick_label.width + 48
        tw = self.ticker.width
        x = int(lw + 40 - (t * 150) % tw)
        while x < W:
            img.alpha_composite(self.ticker, (x, y0 + 18))
            x += tw
        d.rectangle((0, y0 + 3, lw, H), fill=TOPIC["research"])
        img.alpha_composite(self.tick_label, (24, y0 + 20))

    def _top(self, img: Image.Image, idx: int | None) -> None:
        d = ImageDraw.Draw(img)
        _brand(d, 80, 52)
        bx = 80 + 46 + int(d.textlength("Frontier Wire", font=_font(30, 800, 125))) + 28
        d.rectangle((bx, 50, bx + self.bug.width + 28, 50 + 40), fill=RED)
        img.alpha_composite(_recolor(self.bug, PAPER), (bx + 14, 55))
        img.alpha_composite(self.date_l, (bx + self.bug.width + 48, 57))
        if idx is not None:
            n = self._scenes[idx]["num"]
            d.rectangle((W - 80 - n.width - 28, 50, W - 80, 90), fill=(6, 18, 20))
            img.alpha_composite(n, (W - 80 - n.width - 14, 56))

    @staticmethod
    def _wipe(layer: Image.Image, k: float) -> Image.Image:
        """Reveal a layer left to right (a broadcast wipe)."""
        if k >= 1:
            return layer
        out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        w = int(layer.width * max(0.0, k))
        if w > 0:
            out.paste(layer.crop((0, 0, w, layer.height)), (0, 0))
        return out

    # ------------------------------------------------------------ scenes
    def frame(self, t: float) -> Image.Image:
        hook_s = self.durs[0]
        if t < hook_s:
            return self._open(t, hook_s)
        idx = next((j for j in range(self.n) if t < self.starts[j + 2]), self.n)
        if idx < self.n:
            return self._story(t, idx)
        return self._close(t, t - self.starts[-1])

    def _open(self, t: float, dur: float) -> Image.Image:
        """The studio shot: the camera pushes in slowly on the anchor desk while the day's headline builds on the
        video wall behind it."""
        if self._studio is None:
            self._studio = _studio_set()
        img = self._studio.copy()
        x0, y0, x1, y1 = WALL
        out_k = 1 - _ease((t - (dur - 0.4)) / 0.4)
        wall = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wall)
        _signal(wd, "frontier-wire-hook", TOPIC["research"], (60, 40, x1 - x0 - 60, 200), t)
        k = _ease((t - 0.35) / 0.5)
        if k > 0:  # the red title bar wipes in on the wall
            bw = self.eyebrow.width + 56
            bar = Image.new("RGBA", (bw, 70), RED + (255,))
            bar.alpha_composite(_recolor(self.eyebrow, PAPER), (28, 10))
            wall.alpha_composite(self._wipe(bar, k), (70, 220))
            wall.alpha_composite(_fade(self.open_date, k), (70 + bw + 30, 236))
        k2 = _ease((t - 0.7) / 0.6)
        if k2 > 0:
            wall.alpha_composite(_fade(self.wall_hook, k2), (70, 320 + int((1 - k2) * 24)))
        k3 = _ease((t - 1.1) / 0.6)
        if k3 > 0 and 340 + self.wall_hook.height + self.count.height < y1 - y0:
            wall.alpha_composite(_fade(self.count, k3), (70, 340 + self.wall_hook.height))
        img.alpha_composite(wall, (x0, y0))
        # slow camera push-in toward the desk
        z = 1 + 0.07 * _ease(t / dur)
        cw, ch = int(W / z), int(H / z)
        ox, oy = (W - cw) // 2, int((H - ch) * 0.55)
        img = img.crop((ox, oy, ox + cw, oy + ch)).resize((W, H), Image.BILINEAR)
        if out_k < 1:  # dip to the first story
            img.alpha_composite(Image.new("RGBA", (W, H), INK + (int(255 * (1 - out_k)),)))
        _brand(ImageDraw.Draw(img), 80, 52)
        self._ticker(img, t)
        return img.convert("RGB")

    def _story(self, t: float, idx: int) -> Image.Image:
        dur = self.durs[idx + 1]
        lt = t - self.starts[idx + 1]
        L = self._scenes[idx]
        out_k = 1 - _ease((lt - (dur - 0.35)) / 0.35)
        y_top = H - 72 - 34 - (L["detail"].height + L["source"].height + 52) - (L["head"].height + 36) - 50
        gfx = self._graphic(L, W - 160, max(300, y_top - 40 - 140))
        pic, kind = (None, "") if gfx else self._picture(idx, lt, dur)
        if gfx:
            img = self._backdrop(W, H, L["color"], t, L["seed"])
            img.alpha_composite(_fade(gfx.render(lt), out_k), (80, 140))
        elif pic is not None:
            img = pic.convert("RGBA")
            img.alpha_composite(self.shade)
        else:
            img = self.bg.copy().convert("RGBA")
            panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            pd = ImageDraw.Draw(panel)
            _illustration(pd, L["cat"], (80, 150, 560, 420), L["color"], t)
            img.alpha_composite(_fade(panel, _ease(lt / 0.6) * out_k))
        fade_in = _ease(lt / 0.35)  # scenes cut in from a quick dip
        if fade_in < 1:
            img.alpha_composite(Image.new("RGBA", (W, H), INK + (int(255 * (1 - fade_in)),)))
        d = ImageDraw.Draw(img)
        self._top(img, idx)
        # the key figure: a stat card, top right (a news graphic already carries it)
        if L["figure"] is not None and not gfx:
            k = _ease((lt - 0.9) / 0.5) * out_k
            if k > 0:
                fw, fh = L["figure"].width + 72, L["figure"].height + 48
                card = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
                cd = ImageDraw.Draw(card)
                cd.rectangle((0, 0, fw - 1, fh - 1), fill=(6, 18, 20, 215))
                cd.rectangle((0, 0, 8, fh - 1), fill=L["color"] + (255,))
                card.alpha_composite(L["figure"], (40, 16))
                img.alpha_composite(_fade(card, k), (W - 80 - fw, 150 + int((1 - k) * 24)))
        if kind:
            lab = self.clip_labels.get(idx) if kind == "clip" else self.ai_label
            if lab is not None:
                img.alpha_composite(_fade(lab, 0.85 * out_k), (W - 80 - lab.width, 112 if L["figure"] is None else 150 + L["figure"].height + 64))
        # lower third: category tab, headline bar, detail and source
        y_head = H - 72 - 34 - (L["detail"].height + L["source"].height + 52) - (L["head"].height + 36)
        k = _ease((lt - 0.25) / 0.45) * out_k
        if k > 0:
            tab = Image.new("RGBA", (L["chip"].width + 40, 50), L["color"] + (255,))
            tab.alpha_composite(L["chip"], (20, 8))
            img.alpha_composite(self._wipe(tab, k), (80, y_head - 50))
        k = _ease((lt - 0.4) / 0.55) * out_k
        if k > 0:
            hw, hh = W - 160, L["head"].height + 36
            bar = Image.new("RGBA", (hw, hh), PAPER + (255,))
            ImageDraw.Draw(bar).rectangle((0, 0, 10, hh), fill=L["color"] + (255,))
            bar.alpha_composite(L["head"], (36, 14))
            img.alpha_composite(self._wipe(bar, k), (80, y_head))
        k = _ease((lt - 1.2) / 0.5) * out_k
        if k > 0:
            y = y_head + L["head"].height + 36
            pw, ph = W - 160, L["detail"].height + L["source"].height + 52
            plate = Image.new("RGBA", (pw, ph), (6, 18, 20, 225))
            plate.alpha_composite(L["detail"], (36, 18))
            plate.alpha_composite(L["source"], (36, 30 + L["detail"].height))
            img.alpha_composite(_fade(plate, k), (80, y + int((1 - k) * 16)))
        self._ticker(img, t)
        return img.convert("RGB")

    def _close(self, t: float, lt: float) -> Image.Image:
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        _signal(d, "frontier-wire-outro", TOPIC["research"], (1000, 130, 1840, 440), t)
        _brand(d, 120, 300, scale=2.4, grow=_ease(lt / 0.8))
        self._place(img, self.out1, 120, 470, lt, 0.2, 1)
        self._place(img, self.out2, 120, 600, lt, 0.45, 1)
        self._place(img, self.out3, 120, 700, lt, 0.7, 1)
        self._ticker(img, t)
        return img.convert("RGB")

    def _place(self, frame: Image.Image, layer: Image.Image, x: int, y: int, t: float, start: float, out_k: float) -> None:
        k = _ease((t - start) / 0.55)
        if k <= 0:
            return
        frame.alpha_composite(_fade(layer, k * out_k), (x, int(y + (1 - k) * 36)))

    def poster(self) -> Image.Image:
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        self._top(img, None)
        mins = "ONE-MINUTE" if 45 <= self.total <= 70 else "DAILY" if self.total > 70 else f"{int(round(self.total))}-SECOND"
        bar = Image.new("RGBA", (self.eyebrow.width + 56, 70), RED + (255,))
        bar.alpha_composite(_recolor(self.eyebrow, PAPER), (28, 10))
        img.alpha_composite(bar, (120, 170))
        d.text((120 + bar.width + 30, 188), f"{mins} RECAP  ·  {self.date_h.upper()}", font=_font(34, 700, 112), fill=TEXT)
        f, lines = _fit(self.s["hook"], 1500, (88, 80, 72), 2, 820)
        hook = _text_layer(lines, f, TEXT, 1.06)
        img.alpha_composite(hook, (120, 280))
        y = 310 + hook.height + 20
        fl = _font(38, 600)
        for i, st in enumerate(self.s["stories"]):
            c = TOPIC.get(st["category"], TOPIC["industry"])
            d.rectangle((120, y + 12, 132, y + 40), fill=c)
            line = st["line"] if d.textlength(st["line"], font=fl) <= 1400 else _wrap(d, st["line"], fl, 1360)[0] + "…"
            d.text((160, y), line, font=fl, fill=SOFT)
            y += 62
        cx, cy, r = W - 260, H - 260, 110
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=RED)
        d.polygon([(cx - 34, cy - 52), (cx - 34, cy + 52), (cx + 58, cy)], fill=PAPER)
        d.text((120, H - 110), self.site, font=_font(34, 700, 110), fill=MUTED)
        return img.convert("RGB")


def _recolor(layer: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    out = Image.new("RGBA", layer.size, color + (0,))
    out.putalpha(layer.getchannel("A"))
    return out


VW, VH = 1080, 1920   # the vertical cut, for Shorts, Reels and LinkedIn
VPIC_H = 1300         # pictures fill the top of the frame down to here


class VerticalRenderer(Renderer):
    """The same bulletin laid out 9:16: picture on top, a big headline card under it, the ticker at the bottom."""

    def __init__(self, script: dict[str, Any], site_label: str, images: Path | None = None,
                 durations: list[float] | None = None, clips: Path | None = None):
        super().__init__(script, site_label, None, durations, None)
        self.images, self.clips, self.credits, self.provider = {}, {}, {}, {}
        if clips and clips.exists():
            try:
                meta = {c["story"]: c for c in json.loads((clips / "credits.json").read_text())}
            except Exception:  # noqa: BLE001
                meta = {}
            for i in range(self.n):
                f = clips / f"{i + 1}.mp4"
                if f.exists() and usable_clip(f):
                    self.clips[i] = Clip(f, VW, VPIC_H)
                    self.credits[i] = (meta.get(i + 1) or {}).get("name", "")
                    self.provider[i] = (meta.get(i + 1) or {}).get("provider", "Pexels")
        if images:
            for i in range(self.n):
                f = images / f"{i + 1}.jpg"
                if f.exists():
                    try:
                        self.images[i] = _cover(Image.open(f).convert("RGB"), int(VW * 1.1), int(VPIC_H * 1.1))
                    except Exception:  # noqa: BLE001
                        pass
        small = _font(24, 600)
        self.clip_labels = {i: _plate(_text_layer([f"Footage: {self.credits[i]} / {self.provider[i]}" if self.credits[i] else f"Footage: {self.provider[i]}"], small, (215, 226, 224)))
                            for i in self.clips}
        self.bg = _cover(_background(), VW, VH)
        self.shade = self._vshade()
        self._scenes = [self._vlayers(st, i) for i, st in enumerate(script["stories"])]
        f, lines = _fit(script["hook"], 960, (92, 84, 76, 68), 3, 820)
        self.hook = _text_layer(lines, f, TEXT, 1.06)
        self.count = _text_layer([f"Top {self.n} stories in " + ("one minute" if 50 <= self.total <= 70 else "under two minutes")], _font(36, 500), SOFT)
        self.out1 = _text_layer(["That's the day", "in AI."], _font(96, 820), TEXT, 1.04)
        f2, l2 = _fit(site_label, 960, (50, 44, 40, 36), 1, 700, 110)
        self.out2 = _text_layer(l2, f2, TOPIC["research"])
        self.out3 = _text_layer(["Every story, with its sources.", "Updated every three hours."], _font(36, 500), MUTED, 1.3)

    def _vshade(self) -> Image.Image:
        g = Image.new("L", (1, VPIC_H))
        for y in range(VPIC_H):
            v = 0.15 + 0.85 * max(0.0, (y - VPIC_H * 0.55) / (VPIC_H * 0.45)) ** 1.6 + 0.35 * max(0.0, 1 - y / (VPIC_H * 0.16))
            g.putpixel((0, y), int(255 * min(1.0, v)))
        layer = Image.new("RGBA", (VW, VPIC_H), INK + (0,))
        layer.putalpha(g.resize((VW, VPIC_H)))
        return layer

    def _vlayers(self, st: dict[str, Any], i: int) -> dict[str, Any]:
        L = self._story_layers(st, i)
        f, lines = _fit(st["line"], 940, (68, 62, 56, 50), 3, 820)
        L["head"] = _text_layer(lines, f, INK, 1.08)
        fd, dl = _fit(st["detail"], 940, (40, 36, 32), 3, 520)
        L["detail"] = _text_layer(dl, fd, TEXT, 1.18)
        if L["figure"] is not None:
            fig = key_figure(st)
            tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
            for size in range(130, 50, -6):
                ffig = _font(size, 820, 100 if len(fig) > 8 else 105)
                if tmp.textlength(fig, font=ffig) <= 440:
                    break
            L["figure"] = _text_layer([fig], ffig, TEXT, 1.0)
        return L

    def _picture(self, idx: int, lt: float, dur: float) -> tuple[Image.Image | None, str]:
        if idx in self.clips:
            pic = self.clips[idx].frame(int(lt * FPS))
            if lt + 1 / FPS >= dur:
                self.clips[idx].close()
            if pic is not None:
                return pic, "clip"
        if idx in self.images:
            big = self.images[idx]
            z = 0.1 * (lt / dur)
            cw, ch = int(big.width * (1 - z * 0.9)), int(big.height * (1 - z * 0.9))
            ox, oy = (big.width - cw) // 2, int((big.height - ch) * 0.4)
            return big.crop((ox, oy, ox + cw, oy + ch)).resize((VW, VPIC_H), Image.BILINEAR), "image"
        return None, ""

    def _ticker(self, img: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(img)
        y0 = VH - 96
        d.rectangle((0, y0, VW, VH), fill=(6, 18, 20))
        d.rectangle((0, y0, VW, y0 + 3), fill=TOPIC["research"])
        lw = self.tick_label.width + 40
        tw = self.ticker.width
        x = int(lw + 30 - (t * 150) % tw)
        while x < VW:
            img.alpha_composite(self.ticker, (x, y0 + 30))
            x += tw
        d.rectangle((0, y0 + 3, lw, VH), fill=TOPIC["research"])
        img.alpha_composite(self.tick_label, (20, y0 + 32))

    def _top(self, img: Image.Image, idx: int | None) -> None:
        d = ImageDraw.Draw(img)
        _brand(d, 56, 70, scale=1.15)
        bx = 56
        d.rectangle((bx, 128, bx + self.bug.width + 28, 168), fill=RED)
        img.alpha_composite(_recolor(self.bug, PAPER), (bx + 14, 133))
        img.alpha_composite(self.date_l, (bx + self.bug.width + 48, 135))
        if idx is not None:
            n = self._scenes[idx]["num"]
            d.rectangle((VW - 56 - n.width - 28, 66, VW - 56, 106), fill=(6, 18, 20))
            img.alpha_composite(n, (VW - 56 - n.width - 14, 72))

    def _open(self, t: float, dur: float) -> Image.Image:
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        _signal(d, "frontier-wire-hook", TOPIC["research"], (60, 260, 1020, 560), t)
        out_k = 1 - _ease((t - (dur - 0.4)) / 0.4)
        bars = [(170, TOPIC["models"]), (260, TOPIC["research"]), (130, TOPIC["policy"]), (210, TOPIC["industry"])]
        for i, (h, c) in enumerate(bars):
            hh = h * _ease((t - i * 0.1) / 0.7) * out_k
            if hh > 2:
                d.rounded_rectangle((60 + i * 70, 860 - hh, 60 + i * 70 + 42, 860), radius=21, fill=c)
        k = _ease((t - 0.35) / 0.5) * out_k
        if k > 0:
            bw = self.eyebrow.width + 56
            bar = Image.new("RGBA", (bw, 70), RED + (255,))
            bar.alpha_composite(_recolor(self.eyebrow, PAPER), (28, 10))
            img.alpha_composite(self._wipe(bar, k), (60, 920))
            img.alpha_composite(_fade(self.open_date, k), (60, 1012))
        k2 = _ease((t - 0.7) / 0.6) * out_k
        if k2 > 0:
            img.alpha_composite(_fade(self.hook, k2), (60, 1090 + int((1 - k2) * 30)))
        k3 = _ease((t - 1.1) / 0.6) * out_k
        if k3 > 0:
            img.alpha_composite(_fade(self.count, k3), (60, 1120 + self.hook.height))
        self._ticker(img, t)
        return img.convert("RGB")

    def _story(self, t: float, idx: int) -> Image.Image:
        dur = self.durs[idx + 1]
        lt = t - self.starts[idx + 1]
        L = self._scenes[idx]
        out_k = 1 - _ease((lt - (dur - 0.35)) / 0.35)
        gfx = self._graphic(L, VW - 100, VPIC_H - 150 - 250 - 20)
        pic, kind = (None, "") if gfx else self._picture(idx, lt, dur)
        if gfx:
            img = self._backdrop(VW, VH, L["color"], t, L["seed"])
            img.alpha_composite(_fade(gfx.render(lt), out_k), (50, 250))
        elif pic is not None:
            img = self.bg.copy().convert("RGBA")
            top = pic.convert("RGBA")
            top.alpha_composite(self.shade)
            img.alpha_composite(top, (0, 0))
        else:
            img = self.bg.copy().convert("RGBA")
            panel = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
            _illustration(ImageDraw.Draw(panel), L["cat"], (160, 300, 920, 760), L["color"], t)
            img.alpha_composite(_fade(panel, _ease(lt / 0.6) * out_k))
        fade_in = _ease(lt / 0.35)
        if fade_in < 1:
            img.alpha_composite(Image.new("RGBA", (VW, VH), INK + (int(255 * (1 - fade_in)),)))
        self._top(img, idx)
        if L["figure"] is not None and not gfx:
            k = _ease((lt - 0.9) / 0.5) * out_k
            if k > 0:
                fw, fh = L["figure"].width + 64, L["figure"].height + 40
                card = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
                cd = ImageDraw.Draw(card)
                cd.rectangle((0, 0, fw - 1, fh - 1), fill=(6, 18, 20, 215))
                cd.rectangle((0, 0, 8, fh - 1), fill=L["color"] + (255,))
                card.alpha_composite(L["figure"], (36, 12))
                img.alpha_composite(_fade(card, k), (VW - 56 - fw, 220 + int((1 - k) * 24)))
        if kind:
            lab = self.clip_labels.get(idx) if kind == "clip" else self.ai_label
            if lab is not None:
                img.alpha_composite(_fade(lab, 0.85 * out_k), (VW - 56 - lab.width, VPIC_H - 150))
        y_tab = VPIC_H - 110
        k = _ease((lt - 0.25) / 0.45) * out_k
        if k > 0:
            tab = Image.new("RGBA", (L["chip"].width + 40, 50), L["color"] + (255,))
            tab.alpha_composite(L["chip"], (20, 8))
            img.alpha_composite(self._wipe(tab, k), (40, y_tab))
        k = _ease((lt - 0.4) / 0.55) * out_k
        y_head = y_tab + 50
        if k > 0:
            hw, hh = VW - 80, L["head"].height + 40
            bar = Image.new("RGBA", (hw, hh), PAPER + (255,))
            ImageDraw.Draw(bar).rectangle((0, 0, 10, hh), fill=L["color"] + (255,))
            bar.alpha_composite(L["head"], (34, 16))
            img.alpha_composite(self._wipe(bar, k), (40, y_head))
        k = _ease((lt - 1.2) / 0.5) * out_k
        if k > 0:
            y = y_head + L["head"].height + 40
            pw, ph = VW - 80, L["detail"].height + L["source"].height + 60
            plate = Image.new("RGBA", (pw, ph), (6, 18, 20, 235))
            plate.alpha_composite(L["detail"], (34, 20))
            plate.alpha_composite(L["source"], (34, 36 + L["detail"].height))
            img.alpha_composite(_fade(plate, k), (40, y + int((1 - k) * 16)))
        self._ticker(img, t)
        return img.convert("RGB")

    def _close(self, t: float, lt: float) -> Image.Image:
        img = self.bg.copy().convert("RGBA")
        d = ImageDraw.Draw(img)
        _signal(d, "frontier-wire-outro", TOPIC["research"], (60, 260, 1020, 560), t)
        _brand(d, 60, 700, scale=2.4, grow=_ease(lt / 0.8))
        self._place(img, self.out1, 60, 820, lt, 0.2, 1)
        self._place(img, self.out2, 60, 1060, lt, 0.45, 1)
        self._place(img, self.out3, 60, 1150, lt, 0.7, 1)
        self._ticker(img, t)
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
    raw = voice_clips(script, voice)
    n = len(script["stories"])
    vc, durs, tempo, read = {}, *timing(n, {}), "none"
    for with_detail in (True, False):  # line and detail if they fit; else the lines alone; else silent
        if not raw:
            break
        cand = compose_voice(raw, n, with_detail, out_dir)
        natural = voice_provider(voice) == "gemini"   # an acted read: never speed it up unless it can't fit
        d, tp = timing(n, cand, 1.0 if natural else anchor_for(script.get("date", "")).get("speed", VOICE_SPEED))
        if tp:
            vc, durs, tempo, read = cand, d, tp, ("line and detail" if with_detail else "lines only")
            break
    if raw and not vc:
        print("::warning::narration too long for the recap even without the details; rendering silent", flush=True)
    elif raw and read == "lines only":
        print("::warning::narration with the details ran past the minute; the voice reads the headlines only", flush=True)
    r = Renderer(script, site_label, images if images and images.exists() else None, durs, clips)
    mp4, poster, gif = out_dir / "recap.mp4", out_dir / "poster.jpg", out_dir / "teaser.gif"
    frames = int(round(r.total * FPS))
    audio = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]  # silent track, so every recap has one
    if vc:  # the voice, with the news theme ducked underneath it
        voice_wav = mix_voice(vc, durs, tempo, out_dir / "narration.wav")
        audio = ["-i", str(with_music(voice_wav, r.total, r.starts, out_dir))]
    _encode(r, W, H, audio, frames, mp4, f"Frontier Wire recap {script['date']}")
    # the vertical cut for Shorts, Reels and LinkedIn: same bulletin, same audio
    rv = VerticalRenderer(script, site_label, images if images and images.exists() else None, durs, clips)
    _encode(rv, VW, VH, audio, frames, out_dir / "recap-vertical.mp4", f"Frontier Wire recap {script['date']} (vertical)")
    (out_dir / "render.json").write_text(json.dumps({"narrated": bool(vc), "voice": read, "tempo": round(tempo, 3),
                                                     "provider": voice_provider(voice) if vc else "",
                                                     "footage": sorted(i + 1 for i in r.clips), "scenes": [round(d, 2) for d in durs]}))
    r.poster().save(poster, quality=86, optimize=True, progressive=True)
    # teaser: the hook into the first story, small enough for an email
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.8", "-t", "5", "-i", str(mp4), "-vf",
          "fps=10,scale=600:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
          "-loop", "0", str(gif)])
    return check(out_dir)


def with_music(voice_wav: Path, total: float, starts: list[float], out_dir: Path) -> Path:
    """The narration over the news theme: the music dips under the voice (sidechain) and the whole track is
    levelled to broadcast loudness."""
    from . import music
    theme = music.theme(total, starts, out_dir / "theme.wav")
    out = out_dir / "audio.wav"
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(voice_wav), "-i", str(theme), "-filter_complex",
          "[0:a]aresample=44100,asplit=2[v1][v2];[1:a]aresample=44100,volume=0.9[m];"
          "[m][v1]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=400:makeup=1[duck];"
          f"[duck][v2]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11,atrim=0:{total:.3f}[o]",
          "-map", "[o]", "-ar", "44100", "-c:a", "pcm_s16le", str(out)])
    return out


def _encode(r: Renderer, w: int, h: int, audio: list[str], frames: int, mp4: Path, title: str) -> None:
    # 1400 kb/s for a one-minute recap; a longer bulletin gets less per second so the file stays well under MAX_BYTES
    rate = int(min(1400, MAX_BYTES * 0.8 * 8 / 1000 / max(frames / FPS, 1) - 128))
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
         *audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k", "-t", f"{frames / FPS:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", "20", "-maxrate", f"{rate}k", "-bufsize", f"{2 * rate}k",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-metadata", f"title={title}", str(mp4)],
        stdin=subprocess.PIPE)
    assert enc.stdin
    try:
        for i in range(frames):
            enc.stdin.write(r.frame(i / FPS).tobytes())
    finally:
        enc.stdin.close()
        for c in r.clips.values():
            c.close()
    if enc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed while encoding {mp4.name}")


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
    vert = out_dir / "recap-vertical.mp4"
    if vert.exists():  # optional: re-published older videos have no vertical cut
        vp = json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height",
                              "-of", "json", str(vert)], text=True).stdout)["streams"][0]
        info["vertical_bytes"] = vert.stat().st_size
        if (vp["codec_name"], vp["width"], vp["height"]) != ("h264", VW, VH):
            problems.append(f"vertical cut: expected h264 {VW}x{VH}, got {vp['codec_name']} {vp['width']}x{vp['height']}")
        if info["vertical_bytes"] >= MAX_BYTES:
            problems.append(f"vertical cut is {info['vertical_bytes'] / 1e6:.1f} MB (limit 15 MB)")
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
        if is_programme(script) and st.get("graphic"):
            continue  # told with a news graphic
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
    script["video"] = {k: info[k] for k in ("duration", "bytes", "poster_bytes", "gif_bytes", "vertical_bytes") if k in info}
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
            "vertical": asset_url(repo, r["date"], "recap-vertical.mp4") if r["video"].get("vertical_bytes") else "",
            "entries": [{**s, "href": f"story/{s['id']}/" if s["id"] in story_ids else "",
                         "video": videos.get(s["id"]) if VIDEO_ID.match((videos.get(s["id"]) or {}).get("id") or "") else None}
                        for s in r["stories"]],
            "footage": [c for c in r.get("footage_credits") or [] if str(c.get("url", "")).startswith(("https://www.pexels.com/", "https://pixabay.com/", "https://commons.wikimedia.org/"))],
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
            "<description>The day in AI in under two minutes: the top five stories, each checked against its sources.</description>"
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
        **common, rows=rows, root="../", api_url=api_url, title="Daily recaps: today in AI in under two minutes | Frontier Wire",
        description="Every evening, the day's top five AI stories in a short video bulletin, each checked against its sources.",
        canonical=f"{base}videos/", og_image=rows[0]["poster_url"] if rows else f"{base}og/home.png"))
    urls.append(f"{base}videos/")
    top = rows[0] if rows and rows[0]["live"] else None
    return env.get_template("_recap.html").render(**common, r=top, root="") if top else ""
