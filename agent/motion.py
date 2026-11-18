"""The broadcast renderer: the bulletin drawn as an animated web page (video/engine.html) and recorded frame by frame
in headless Chrome (video/capture.mjs), then encoded with ffmpeg. Everything on screen is computed from the
playhead, so every render of the same script is identical.

This module builds the engine's timeline: scene timings, the story text and graphics, and when the anchor says each
word. Word times come from the voice clips themselves, with no speech model: the pauses inside each scene's clip
mark where its sentences fall (fitted to the script with the same best-fit cut used to split the one-take read),
and the words inside a sentence are spread by their length. That is close enough to time phrase captions and to
make graphics react to what the anchor is saying (the map arrow draws as the anchor names the place, a list item
appears as it's named).

Recap.render() tries this first and falls back to the Pillow renderer if Chrome or Node isn't available.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import newsgfx, recap
from .cards import LABEL, TOPIC

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "video"
STOP = set("the a an and or of to in on for with at by from is are was were be been it its this that these those as "
           "into over than then their there they them we our you your he she his her has have had will would can could "
           "just now new more most also about after before up out not no but so if what which who".split())


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


# ---------------------------------------------------------------- when the anchor says each word
def _pauses(clip: Path) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(clip), "-af", "silencedetect=noise=-34dB:d=0.16", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    e = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(s, e))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.?!:])\s+(?=[A-Z\"'0-9$])", (text or "").strip())
    return [p for p in (x.strip() for x in parts) if p]


def best_cuts(gaps: list[tuple[float, float]], total: float, weights: list[float], lam: float = 0.5) -> list[tuple[float, float]] | None:
    """Pick len(weights)-1 of the pauses in `gaps` (start, end) to cut at, so the pieces are as close as possible to
    their share of `weights` while preferring long pauses (dynamic programming). None if there aren't enough."""
    n = len(weights)
    if n <= 1:
        return []
    gs = [g for g in gaps if 0.05 < (g[0] + g[1]) / 2 < total - 0.05]
    mids = [((a + b) / 2, b - a) for a, b in gs]
    k = len(mids)
    if k < n - 1:
        return None
    tot_w = sum(weights) or 1
    exp = [total * w / tot_w for w in weights]

    def fit(i: int, dur: float) -> float:
        return abs(math.log(max(dur, 0.05) / max(exp[i], 0.05)))

    best = [[-1e9] * k for _ in range(n - 1)]
    prev = [[-1] * k for _ in range(n - 1)]
    for g, (m, w) in enumerate(mids):
        best[0][g] = w - lam * fit(0, m)
    for j in range(1, n - 1):
        for g, (m, w) in enumerate(mids):
            for h in range(g):
                if best[j - 1][h] > -1e8:
                    sc = best[j - 1][h] + w - lam * fit(j, m - mids[h][0])
                    if sc > best[j][g]:
                        best[j][g], prev[j][g] = sc, h
    cands = [g for g in range(k) if best[n - 2][g] > -1e8]
    if not cands:
        return None
    last = max(cands, key=lambda g: best[n - 2][g] - lam * fit(n - 1, total - mids[g][0]))
    picks = [last]
    for j in range(n - 2, 0, -1):
        picks.append(prev[j][picks[-1]])
    return [gs[g] for g in reversed(picks)]


def word_times(text: str, clip: Path | None, offset: float, tempo: float, span: float) -> list[dict[str, Any]]:
    """[{w, t0, t1}] for each word of `text`, in video time. With a clip: sentences fitted to its pauses, words
    spread inside them by length. Without one (silent render): spread over `span` seconds."""
    sents = _sentences(text)
    if not sents:
        return []
    weights = [len(s) + 8 for s in sents]
    if clip is not None and clip.exists():
        total = recap._duration(clip)
        gaps = _pauses(clip)
        lead = gaps[0][1] if gaps and gaps[0][0] < 0.05 else 0.0           # quiet before the first word
        tail = gaps[-1][0] if gaps and gaps[-1][1] > total - 0.05 else total  # and after the last
        inner = [g for g in gaps if g[0] > lead + 0.02 and g[1] < tail - 0.02]
        cut = best_cuts(inner, tail, weights)
        if cut is None:  # not enough pauses: spread by length
            acc, cut = lead, []
            for wt in weights[:-1]:
                acc += wt / sum(weights) * (tail - lead)
                cut.append((acc, acc))
        edges = [lead] + [x for g in cut for x in g] + [tail]
        spans = [(edges[2 * i], edges[2 * i + 1]) for i in range(len(sents))]
        scale = 1.0 / tempo
    else:
        spans, acc = [], 0.0
        for wt in weights:
            d = wt / sum(weights) * span
            spans.append((acc, acc + d - 0.15))
            acc += d
        scale = 1.0
    out = []
    for s, (a, b) in zip(sents, spans):
        words = s.split()
        ws = [len(w) + (2 if re.search(r"[,;]$", w) else 0) + 1.5 for w in words]
        tot = sum(ws) or 1
        t = a
        for w, wt in zip(words, ws):
            d = (b - a) * wt / tot
            out.append({"w": w, "t0": round(offset + t * scale, 3), "t1": round(offset + (t + d) * scale, 3)})
            t += d
    return out


def phrases(words: list[dict[str, Any]], max_chars: int = 34) -> list[dict[str, Any]]:
    """Caption chunks: break at sentence ends and commas, and before a line would pass max_chars."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x["w"] for x in cur)
        if re.search(r"[.?!:;,]$", w["w"]) or len(text) >= max_chars:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [{"t0": c[0]["t0"], "t1": c[-1]["t1"], "words": c} for c in out]


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def cue(words: list[dict[str, Any]], text: str, after: float = 0.0, exact: str = "") -> float | None:
    """When the anchor first says one of the meaningful words of `text` (or any word of `exact`, however short),
    at or after `after`."""
    toks = {_norm(x) for x in re.split(r"[\s/,-]+", text or "")} - {""}
    toks = {t for t in toks if t.isdigit() or (len(t) >= 3 and t not in STOP)} | ({_norm(x) for x in exact.split()} - {""})
    toks |= {re.sub(r"s$", "", t) for t in toks if len(t) > 4}
    if not toks:
        return None
    for w in words:
        n = _norm(w["w"])
        if w["t0"] >= after and (n in toks or re.sub(r"s$", "", n) in toks):
            return w["t0"]
    return None


# ---------------------------------------------------------------- the timeline
def _place_cues(spec: dict[str, Any], words: list[dict[str, Any]], t_from: float) -> dict[str, Any]:
    aka = {"United States": "us u.s. america american washington", "China": "china chinese beijing",
           "United Kingdom": "uk britain british london", "European Union": "eu europe european brussels",
           "India": "india indian", "Japan": "japan japanese", "South Korea": "korea korean"}
    places = []
    for p in spec.get("places") or []:
        pl = newsgfx.place(p)
        if not pl:
            continue
        said = cue(words, f"{pl['label']} {p}", t_from, aka.get(pl["label"], ""))
        places.append({"name": p, "label": pl["label"], "countries": pl["countries"], "pin": pl["pin"], "city": bool(pl.get("city")),
                       "cue": said})
    return {"places": places}


def _graphic(st: dict[str, Any], spec: dict[str, Any] | None, words: list[dict[str, Any]], t_from: float) -> dict[str, Any] | None:
    if not spec:
        return None
    g = dict(spec)
    kind = g["type"]
    if kind == "map":
        g.update(_place_cues(spec, words, t_from))
        to = next((p for p in g["places"] if p["name"] == spec.get("to")), None)
        g["arrow_cue"] = (to or {}).get("cue")
    elif kind in ("list", "steps"):
        g["cues"] = [cue(words, it, t_from) for it in spec.get("items") or []]
    elif kind == "bars":
        g["cues"] = [cue(words, re.sub(r"[^\d.]", " ", v) + " " + lab, t_from) for lab, v in spec.get("items") or []]
        g["values"] = [newsgfx._value(v)[1] for _, v in spec.get("items") or []]
    elif kind == "number":
        g["cue"] = cue(words, re.sub(r"[^\d.]", " ", spec.get("value", "")), t_from)
        v = newsgfx._value(spec["value"])
        g["num"] = {"pre": v[0], "x": v[1], "dec": v[2], "suf": v[3]}
        g["parts_v"] = [newsgfx._value(b)[1] for _, b in spec.get("parts") or []]
        g["part_cues"] = [cue(words, re.sub(r"[^\d.]", " ", b) + " " + a, t_from) for a, b in spec.get("parts") or []]
    elif kind == "change":
        g["cue"] = cue(words, re.sub(r"[^\d.]", " ", str(spec.get("change", ""))) + " percent cheaper less more", t_from)
        g["pct"] = float(str(spec["change"]).strip().rstrip("%"))
    elif kind == "quote":
        g["cue"] = None
    return g


def timeline(script: dict[str, Any], durs: list[float], clips: dict[str, tuple[Path, float]], tempo: float,
             site_label: str) -> dict[str, Any]:
    n = len(script["stories"])
    starts = [sum(durs[:i]) for i in range(len(durs))]
    said = dict(recap.narration(script))
    texts = {"hook": " ".join(x for x in (said.get("hook"), said.get("hookd")) if x),
             "outro": " ".join(x for x in (said.get("outro"), said.get("outrod")) if x)}
    for i in range(1, n + 1):
        texts[f"story{i}"] = " ".join(x for x in (said.get(f"story{i}"), said.get(f"story{i}d")) if x)
    keys = ["hook"] + [f"story{i}" for i in range(1, n + 1)] + ["outro"]
    kinds = ["hook"] + ["story"] * n + ["outro"]
    words: dict[str, list[dict[str, Any]]] = {}
    for j, key in enumerate(keys):
        clip = clips.get(key, (None, 0))[0] if clips else None
        lead = recap.VOICE_LEAD[kinds[j]]
        words[key] = word_times(texts[key], clip, starts[j] + lead, tempo, durs[j] - lead - 0.6)
    narrated = bool(clips)
    scenes = [{"kind": "open", "start": starts[0], "dur": durs[0], "words": words["hook"], "teaser_t": None}]
    if recap.is_programme(script) and said.get("hookd"):  # when the anchor moves from the welcome to the teaser
        k = len(said["hook"].split())
        if len(words["hook"]) > k:
            scenes[0]["teaser_t"] = words["hook"][k]["t0"]
    tiles = []
    for i, st in enumerate(script["stories"]):
        s0, d = starts[i + 1], durs[i + 1]
        w = words[f"story{i + 1}"]
        sents = _sentences(texts[f"story{i + 1}"])
        first_end = next((x["t1"] for x in w if re.search(r"[.?!]$", x["w"])), s0 + 3.0) if sents else s0 + 3.0
        shot2 = min(max(first_end - s0 + 0.15, 2.4), 4.6, d * 0.4)
        spec = recap.graphic_for(st) if recap.is_programme(script) or st.get("graphic") else None
        color = TOPIC.get(st.get("category"), TOPIC["industry"])
        scenes.append({
            "kind": "story", "i": i + 1, "start": s0, "dur": d, "shot2": round(shot2, 2), "words": w,
            "line": st["line"], "detail": st["detail"], "source": st["source"], "lab": st.get("lab") or "",
            "label": LABEL.get(st.get("category"), "News"), "color": _hex(color), "figure": recap.key_figure(st),
            "graphic": _graphic(st, spec, w, s0 + shot2 - 0.2),
        })
        tiles.append({"line": st["line"], "label": LABEL.get(st.get("category"), "News"), "color": _hex(color),
                      "cue": cue(words["hook"], f"{st.get('lab') or ''} {st['line']}", starts[0] + 2.0)})
    scenes[0]["tiles"] = tiles
    scenes.append({"kind": "close", "start": starts[-1], "dur": durs[-1], "words": words["outro"],
                   "url_cue": cue(words["outro"], "website site", starts[-1])})
    caps = []
    if narrated:
        for key in keys:
            caps += phrases(words[key])
    d = recap.date.fromisoformat(script["date"][:10])
    return {
        "fps": recap.FPS, "total": round(sum(durs), 3), "date": f"{d.day} {d:%B %Y}".upper(), "weekday": f"{d:%A}".upper(),
        "hook": script.get("hook", ""), "site": site_label, "accent": _hex(TOPIC["research"]),
        "ticker": [st["line"] for st in script["stories"]], "scenes": scenes, "captions": caps, "narrated": narrated,
    }


# ---------------------------------------------------------------- B-roll
def with_broll(tl: dict[str, Any], clips: Path | None, w: int, h: int, work: Path) -> dict[str, Any]:
    """A copy of the timeline with each story's picked clip as a folder of frames sized for a w x h cut (cropped
    to fill it), as long as the story's scene (looped if the clip is shorter)."""
    import copy
    out = copy.deepcopy(tl)
    if not clips or not clips.exists():
        return out
    try:
        credits = {c["story"]: c for c in json.loads((clips / "credits.json").read_text())}
    except Exception:  # noqa: BLE001
        credits = {}
    for sc in out["scenes"]:
        if sc["kind"] != "story":
            continue
        f = clips / f"{sc['i']}.mp4"
        if not f.exists() or not recap.usable_clip(f):
            continue
        d = (work / f"broll-{w}x{h}-{sc['i']}").resolve()
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        try:
            recap._run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", str(f), "-t", f"{sc['dur'] + 0.5:.2f}", "-an",
                        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={tl['fps']},eq=saturation=0.92",
                        "-q:v", "4", str(d / "%04d.jpg")], timeout=300)
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::story {sc['i']}: B-roll frames failed ({str(exc)[:120]})", flush=True)
            continue
        n = len(list(d.glob("*.jpg")))
        if n < tl["fps"]:
            continue
        c = credits.get(sc["i"]) or {}
        prov = re.sub(r",.*", "", c.get("provider") or "")
        sc["broll"] = {"dir": str(d), "n": n, "credit": f"{c.get('name') or prov} / {prov}" if c.get("name") and prov else (prov or "Stock")}
    return out


# ---------------------------------------------------------------- recording
def available() -> str | None:
    """Why the browser renderer can't run here (None if it can)."""
    if os.environ.get("RECAP_RENDERER") == "pillow":
        return "RECAP_RENDERER=pillow"
    if not shutil.which("node"):
        return "no node"
    if not (ENGINE / "node_modules" / "puppeteer-core").exists():
        return "video/node_modules missing (run npm ci in video/)"
    if not chrome():
        return "no Chrome"
    return None


def chrome() -> str | None:
    for c in (os.environ.get("CHROME_PATH"), "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
              "/usr/bin/chromium", "/usr/bin/chromium-browser", shutil.which("google-chrome") or "", shutil.which("chromium") or ""):
        if c and Path(c).exists():
            return c
    return None


def record(tl: dict[str, Any], w: int, h: int, audio: list[str], mp4: Path, title: str, work: Path) -> None:
    """Render the timeline at w x h in headless Chrome and encode it, with the given ffmpeg audio input args."""
    work = work.resolve()   # the recorder runs from video/, so every path it gets must be absolute
    mp4 = mp4.resolve()
    work.mkdir(parents=True, exist_ok=True)
    tlf = work / f"timeline-{w}x{h}.json"
    tlf.write_text(json.dumps(tl))
    frames_dir = work / f"frames-{w}x{h}"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames = int(round(tl["total"] * tl["fps"]))
    workers = max(1, min(4, (os.cpu_count() or 2)))
    cap = subprocess.run(["node", str(ENGINE / "capture.mjs"), str(tlf), str(w), str(h), str(frames), str(frames_dir), str(workers), chrome() or ""],
                         cwd=str(ENGINE))
    got = len(list(frames_dir.glob("*.jpg"))) if frames_dir.exists() else 0
    if cap.returncode != 0 or got != frames:
        raise RuntimeError(f"browser render failed (exit {cap.returncode}, {got}/{frames} frames)")
    rate = int(min(2200, recap.MAX_BYTES * 0.8 * 8 / 1000 / max(frames / tl["fps"], 1) - 128))
    recap._run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(tl["fps"]), "-i", str(frames_dir / "%05d.jpg"),
                *audio, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "128k", "-t", f"{frames / tl['fps']:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-maxrate", f"{rate}k", "-bufsize", f"{2 * rate}k",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-metadata", f"title={title}", str(mp4)])
    shutil.rmtree(frames_dir, ignore_errors=True)


def stills(script: dict[str, Any], out: Path) -> list[Path]:
    """PNG stills for a layout check without a voice: each story's graphic once it has built, and the rundown, in
    both cuts. Uses the silent scene timing."""
    n = len(script["stories"])
    durs, _ = recap.timing(n, {})
    tl = timeline(script, durs, {}, 1.0, "ajsims23.github.io/frontier-wire")
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    tlf = out / "timeline.json"
    tlf.write_text(json.dumps(tl))
    times = [round(tl["scenes"][0]["dur"] * 0.8, 2)] + [round(sc["start"] + min(sc["dur"] - 0.6, sc["shot2"] + 2.6), 2) for sc in tl["scenes"][1:-1]]
    for w, h in ((recap.W, recap.H), (recap.VW, recap.VH)):
        recap._run(["node", str(ENGINE / "snap.mjs"), str(tlf), str(w), str(h), str(out), *map(str, times)], cwd=str(ENGINE))
    return sorted(out.glob("f_*.png"))
