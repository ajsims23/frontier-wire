"""Link-preview cards (1200x630 PNG) for stories and the home page, drawn with Pillow."""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).parent / "assets" / "Archivo.ttf"
W, H = 1200, 630

# Abyss palette
GROUND = (5, 20, 22)
PANEL = (15, 41, 45)
TEXT = (233, 245, 243)
MUTED = (132, 166, 161)
TOPIC = {
    "models": (138, 171, 255), "research": (95, 227, 207), "policy": (255, 194, 102),
    "safety": (255, 143, 128), "industry": (201, 164, 255), "voices": (241, 238, 230),
}
LABEL = {"models": "Model release", "research": "Research", "policy": "Policy", "safety": "Safety",
         "industry": "Industry", "voices": "Commentary"}


def _font(size: int, weight: int = 700, width: int = 100) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_axes([weight, width])  # axes: weight, width
    except Exception:  # noqa: BLE001
        pass
    return f


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _signal(draw: ImageDraw.ImageDraw, seed: str, color: tuple[int, int, int], box: tuple[int, int, int, int]) -> None:
    """Generated 'signal' lines, the same motif the site uses when a story has no photo."""
    r = random.Random(seed)
    x0, y0, x1, y1 = box
    cx = x0 + (x1 - x0) * (0.3 + r.random() * 0.4)
    spread = (x1 - x0) * (0.12 + r.random() * 0.12)
    n = 7
    for i in range(n):
        base = y0 + 30 + i * (y1 - y0 - 60) / (n - 1)
        amp = 10 + r.random() * (90 if i == 3 else 40)
        freq, phase = 2 + r.random() * 5, r.random() * 6.28
        pts = []
        for x in range(x0, x1 + 1, 8):
            env = math.exp(-(((x - cx) / spread) ** 2))
            y = base - amp * env * abs(math.sin((x - x0) / (x1 - x0) * 6.28 * freq + phase)) - 3 * math.sin(x / 23 + i)
            pts.append((x, y))
        main = i == 3
        fill = color if main else tuple(int(c * 0.35 + g * 0.65) for c, g in zip(MUTED, GROUND))
        draw.line(pts, fill=fill, width=4 if main else 2)


def _brand(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    bars = [(13, TOPIC["models"]), (20, TOPIC["research"]), (10, TOPIC["policy"]), (16, TOPIC["industry"])]
    for i, (h, c) in enumerate(bars):
        bx = x + i * 9
        draw.rounded_rectangle((bx, y + 24 - h, bx + 5, y + 24), radius=2, fill=c)
    draw.text((x + 46, y - 2), "Frontier Wire", font=_font(30, 800, 125), fill=TEXT)


def story_card(story: dict, out: Path) -> None:
    cat = story.get("category", "industry")
    color = TOPIC.get(cat, TOPIC["models"])
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    _signal(d, story["id"], color, (700, 60, W, H - 40))
    # fade the art under the text column
    fade = Image.new("L", (W, H), 0)
    fd = ImageDraw.Draw(fade)
    for x in range(0, 760):
        fd.line([(x, 0), (x, H)], fill=int(255 * max(0, min(1, (760 - x) / 260))))
    img.paste(Image.new("RGB", (W, H), GROUND), (0, 0), fade)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 10), fill=color)
    _brand(d, 64, 54)
    label = f"{LABEL.get(cat, cat.title())}" + (f" · {story['lab']}" if story.get("lab") else "")
    d.text((64, 130), label, font=_font(28, 600, 100), fill=color)
    size = 64
    font = _font(size, 800, 112)
    lines = _wrap(d, story["headline"], font, 760)
    while len(lines) > 4 and size > 40:
        size -= 6
        font = _font(size, 800, 112)
        lines = _wrap(d, story["headline"], font, 760)
    if len(lines) > 4:
        lines = lines[:4]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    y = 182
    for line in lines:
        d.text((64, y), line, font=font, fill=TEXT)
        y += int(size * 1.08)
    n = len(story.get("sources", []))
    d.text((64, H - 78), f"Checked against {n} source{'s' if n != 1 else ''}", font=_font(26, 500, 100), fill=MUTED)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)


def home_card(line: str, out: Path) -> None:
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    _signal(d, "home", TOPIC["research"], (560, 40, W, H - 40))
    fade = Image.new("L", (W, H), 0)
    fd = ImageDraw.Draw(fade)
    for x in range(0, 700):
        fd.line([(x, 0), (x, H)], fill=int(255 * max(0, min(1, (700 - x) / 240))))
    img.paste(Image.new("RGB", (W, H), GROUND), (0, 0), fade)
    d = ImageDraw.Draw(img)
    _brand(d, 64, 54)
    d.text((64, 150), "Today in AI", font=_font(88, 800, 125), fill=TEXT)
    font = _font(36, 500, 100)
    y = 280
    for l in _wrap(d, line or "Frontier model releases, research, policy and commentary, checked against sources.", font, 640)[:5]:
        d.text((64, y), l, font=font, fill=MUTED)
        y += 48
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)


def art_image(story: dict, out: Path) -> None:
    """Picture used on a story page when there's no photo: the signal motif on a transparent background."""
    cat = story.get("category", "industry")
    color = TOPIC.get(cat, TOPIC["models"])
    w, h = 1200, 520
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = random.Random(story["id"])
    cx, spread = w * (0.3 + r.random() * 0.4), w * (0.1 + r.random() * 0.1)
    d.rectangle((cx - spread, 0, cx + spread, h), fill=color + (22,))
    for i in range(8):
        base = 50 + i * (h - 100) / 7
        amp = 12 + r.random() * (150 if i == 3 else 60)
        freq, phase = 2 + r.random() * 5, r.random() * 6.28
        pts = []
        for x in range(0, w + 1, 8):
            env = math.exp(-(((x - cx) / spread) ** 2))
            pts.append((x, base - amp * env * abs(math.sin(x / w * 6.28 * freq + phase)) - 4 * math.sin(x / 23 + i)))
        main = i == 3
        d.line(pts, fill=(color + (255,)) if main else (132, 150, 160, 90), width=5 if main else 2)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
