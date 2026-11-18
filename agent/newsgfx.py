"""News graphics for the recap: each story's scene shows a graphic built from that story's own facts, the way a TV
newsroom explains a story (a map of where it happens, the number that matters counting up, a before-and-after, a
funding split, a list, the steps of what happened, or a named person's own words), instead of generic footage.

The editor picks the template and fills it with facts from the story in the script ("graphic" on each story). The
checks here make sure every number in a graphic is one the story itself reports, every quote is one the story
carries, and every place is one we can draw. Everything is drawn from scratch with Pillow: no photos, no logos.
The world map is Natural Earth 1:110m (public domain), simplified, in agent/assets/world.json.

    {"type": "map", "places": ["United States", "China"], "from": "United States", "to": "China", "blocked": true,
     "caption": "H200 chip sales to China halted"}
    {"type": "number", "value": "$47M", "caption": "Raised to film robot training video",
     "parts": [["Equity, led by Accel", "$26M"], ["Venture debt", "$21M"]]}
    {"type": "change", "change": "-20%", "before": "Previous Astra price", "after": "GPT-6.2 Astra", "caption": "..."}
    {"type": "bars", "caption": "...", "items": [["Label", "$10M"], ["Label", "$47M"]]}
    {"type": "list", "caption": "Six new Microsoft models", "items": ["Coding", "Cybersecurity", "Images", "Voice"]}
    {"type": "steps", "caption": "How the test worked", "items": ["Framed as a game", "Models flag schools", "..."]}
    {"type": "quote", "text": "...", "by": "Manish Agarwal", "role": "Co-founder, Humyn Labs"}
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .cards import MUTED, TEXT, _font, _wrap

TYPES = ("map", "number", "change", "bars", "list", "steps", "quote")
LAND = (22, 46, 50)
EDGE = (38, 72, 76)
RED = (226, 54, 54)
PLATE = (6, 18, 20)

# Places that aren't countries on the 1:110m map, or that people name differently: (country it sits in, lon, lat)
CITIES = {
    "san francisco": ("United States of America", -122.4, 37.8), "silicon valley": ("United States of America", -122.0, 37.4),
    "seattle": ("United States of America", -122.3, 47.6), "new york": ("United States of America", -74.0, 40.7),
    "washington": ("United States of America", -77.0, 38.9), "austin": ("United States of America", -97.7, 30.3),
    "boston": ("United States of America", -71.1, 42.4), "los angeles": ("United States of America", -118.2, 34.1),
    "toronto": ("Canada", -79.4, 43.7), "montreal": ("Canada", -73.6, 45.5), "london": ("United Kingdom", -0.1, 51.5),
    "paris": ("France", 2.35, 48.9), "berlin": ("Germany", 13.4, 52.5), "munich": ("Germany", 11.6, 48.1),
    "brussels": ("Belgium", 4.35, 50.85), "zurich": ("Switzerland", 8.5, 47.4), "amsterdam": ("Netherlands", 4.9, 52.4),
    "stockholm": ("Sweden", 18.1, 59.3), "dublin": ("Ireland", -6.3, 53.3), "tel aviv": ("Israel", 34.8, 32.1),
    "dubai": ("United Arab Emirates", 55.3, 25.2), "abu dhabi": ("United Arab Emirates", 54.4, 24.5),
    "riyadh": ("Saudi Arabia", 46.7, 24.7), "beijing": ("China", 116.4, 39.9), "shanghai": ("China", 121.5, 31.2),
    "shenzhen": ("China", 114.1, 22.5), "hangzhou": ("China", 120.2, 30.3), "hong kong": ("China", 114.2, 22.3),
    "taipei": ("Taiwan", 121.6, 25.0), "hsinchu": ("Taiwan", 121.0, 24.8), "tokyo": ("Japan", 139.7, 35.7),
    "seoul": ("South Korea", 127.0, 37.6), "singapore": ("Malaysia", 103.8, 1.35),
    "bengaluru": ("India", 77.6, 12.97), "bangalore": ("India", 77.6, 12.97), "mumbai": ("India", 72.9, 19.1),
    "new delhi": ("India", 77.2, 28.6), "delhi": ("India", 77.2, 28.6), "hyderabad": ("India", 78.5, 17.4),
    "chennai": ("India", 80.3, 13.1), "pune": ("India", 73.9, 18.5), "nashik": ("India", 73.8, 20.0),
    "sydney": ("Australia", 151.2, -33.9), "sao paulo": ("Brazil", -46.6, -23.5), "nairobi": ("Kenya", 36.8, -1.3),
    "lagos": ("Nigeria", 3.4, 6.5), "jakarta": ("Indonesia", 106.8, -6.2),
}
ALIASES = {"us": "United States of America", "u.s.": "United States of America", "usa": "United States of America",
           "united states": "United States of America", "america": "United States of America",
           "uk": "United Kingdom", "u.k.": "United Kingdom", "britain": "United Kingdom", "great britain": "United Kingdom",
           "england": "United Kingdom", "uae": "United Arab Emirates", "korea": "South Korea", "russia": "Russia",
           "czech republic": "Czechia", "holland": "Netherlands"}
EU = ["Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Finland", "France",
      "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Netherlands", "Poland",
      "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden"]
SHORT = {"United States of America": "United States"}


@lru_cache(maxsize=1)
def world() -> dict[str, dict[str, Any]]:
    data = json.loads((Path(__file__).parent / "assets" / "world.json").read_text())
    out = {}
    for c in data["countries"]:
        out[c["name"].lower()] = c
        out[c["long"].lower()] = c
    return out


def place(name: str) -> dict[str, Any] | None:
    """A place the map can draw: {"label", "countries": [names to highlight], "pin": (lon, lat)}; None if unknown."""
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    if key in ("eu", "european union", "europe"):
        return {"label": "European Union", "countries": EU, "pin": (10.0, 50.5)}
    if key in CITIES:
        country, lon, lat = CITIES[key]
        return {"label": name.strip(), "countries": [country], "pin": (lon, lat), "city": True}
    key = ALIASES.get(key, key)
    c = world().get(key.lower())
    if not c:
        return None
    return {"label": SHORT.get(c["name"], c["name"]), "countries": [c["name"]], "pin": tuple(c["c"])}


# ---------------------------------------------------------------- checking
_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _nums(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(text or "")}


def _strings(spec: Any) -> list[str]:
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, dict):
        return [s for k, v in spec.items() if k != "type" for s in _strings(v)]
    if isinstance(spec, (list, tuple)):
        return [s for v in spec for s in _strings(v)]
    return [str(spec)] if isinstance(spec, (int, float)) and not isinstance(spec, bool) else []


def check(spec: Any, facts: str, quotes: list[dict[str, Any]] | None = None) -> list[str]:
    """Problems with a story's graphic: its shape, its lengths, and whether its numbers, quote and places come from
    the story (`facts`: the story's own headline, summary, why it matters and the on-screen lines)."""
    if not isinstance(spec, dict) or spec.get("type") not in TYPES:
        return [f"graphic: type must be one of {', '.join(TYPES)}"]
    errs: list[str] = []
    kind = spec["type"]

    def short(key: str, n: int, need: bool = False) -> None:
        v = spec.get(key)
        if v is None or v == "":
            if need:
                errs.append(f"graphic: {kind} needs \"{key}\"")
            return
        if not isinstance(v, str) or len(v.strip()) > n:
            errs.append(f"graphic: \"{key}\" must be text of at most {n} characters")

    def items(n_min: int, n_max: int, each: int, pairs: bool = False) -> list[Any]:
        v = spec.get("items") if kind != "number" else spec.get("parts") or []
        if not isinstance(v, list) or not (n_min <= len(v) <= n_max):
            errs.append(f"graphic: {kind} needs {n_min}-{n_max} {'parts' if kind == 'number' else 'items'}")
            return []
        for x in v:
            if pairs:
                if not (isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) for y in x)) or len(x[0]) > each or not _value(x[1]):
                    errs.append(f"graphic: each {kind} item is [label of at most {each} characters, a figure like \"$26M\" or \"40%\"]")
                    break
            elif not isinstance(x, str) or not x.strip() or len(x) > each:
                errs.append(f"graphic: each {kind} item must be text of at most {each} characters")
                break
        return v

    short("caption", 60)
    if kind == "map":
        ps = spec.get("places")
        if not isinstance(ps, list) or not 1 <= len(ps) <= 4:
            errs.append("graphic: map needs 1-4 places")
            ps = []
        for p in ps:
            if not isinstance(p, str) or place(p) is None:
                errs.append(f"graphic: can't draw the place {p!r} (use a country, the EU, or a major tech city)")
        for k in ("from", "to"):
            if spec.get(k) and spec[k] not in ps:
                errs.append(f"graphic: map \"{k}\" must be one of its places")
        if bool(spec.get("from")) != bool(spec.get("to")):
            errs.append("graphic: map needs both \"from\" and \"to\" for an arrow, or neither")
    elif kind == "number":
        short("value", 10, True)
        if spec.get("value") and not _value(spec["value"]):
            errs.append("graphic: number \"value\" must be a figure like \"$47M\", \"25%\" or \"1.2B\"")
        short("caption", 60, True)
        if spec.get("parts"):
            items(2, 3, 28, pairs=True)
    elif kind == "change":
        if not re.fullmatch(r"[+-]?\d+(\.\d+)?%", str(spec.get("change", "")).strip()):
            errs.append("graphic: change needs \"change\" like \"-20%\" or \"+35%\"")
        short("before", 30, True)
        short("after", 30, True)
    elif kind == "bars":
        items(2, 4, 28, pairs=True)
    elif kind == "list":
        items(2, 6, 26)
        short("caption", 60, True)
    elif kind == "steps":
        items(2, 4, 44)
    elif kind == "quote":
        text = (spec.get("text") or "").strip()
        if not 20 <= len(text) <= 180:
            errs.append("graphic: quote text must be 20-180 characters")
        if not (spec.get("by") or "").strip():
            errs.append("graphic: quote needs \"by\" (the person's name)")
        short("role", 50)
        said = [q for q in quotes or [] if text and _squash(text) in _squash(q.get("text", ""))]
        if text and not said:
            errs.append("graphic: the quote must be words the story itself quotes (from its \"quotes\"), exactly")
        elif said and (spec.get("by") or "").strip().lower() != (said[0].get("speaker") or "").strip().lower():
            errs.append(f"graphic: that quote is by {said[0].get('speaker')!r}")
    if kind != "quote":
        have = _nums(facts)
        extra = sorted(n for s in _strings(spec) for n in _nums(s) if n not in have)
        if extra:
            errs.append(f"graphic: numbers not in the story: {', '.join(extra[:4])} (use only the story's own figures)")
    return errs


def _squash(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


_VAL = re.compile(r"^\s*([$₹€£]?)\s*(\d+(?:[.,]\d+)*)\s*(%|[KMBT]\b|x\b|GW\b|MW\b|bn\b|m\b)?\s*(\+?)\s*$", re.I)


def _value(v: str) -> tuple[str, float, int, str] | None:
    """'$47M' -> ('$', 47.0, 0, 'M'); '6.2%' -> ('', 6.2, 1, '%'). None if it isn't a single figure."""
    m = _VAL.match(str(v or ""))
    if not m:
        return None
    num = m.group(2).replace(",", "")
    dec = len(num.split(".")[1]) if "." in num else 0
    return m.group(1), float(num), dec, (m.group(3) or "") + m.group(4)


def _fmt(pre: str, x: float, dec: int, suf: str) -> str:
    s = f"{x:,.{dec}f}" if x >= 1000 else f"{x:.{dec}f}"
    return f"{pre}{s}{suf}"


def auto(st: dict[str, Any], figure: str) -> dict[str, Any] | None:
    """A graphic for a story the editor didn't give one: its key figure, counting up. None if it has no figure."""
    if not figure or not _value(figure):
        return None
    return {"type": "number", "value": figure, "caption": (st.get("line") or "")[:60]}


# ---------------------------------------------------------------- drawing
def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _text(lines: list[str], font: Any, fill: tuple[int, ...], spacing: float = 1.15) -> Image.Image:
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * spacing)
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = max([int(tmp.textlength(x, font=font)) for x in lines] + [1])
    img = Image.new("RGBA", (w + 4, lh * len(lines) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, x in enumerate(lines):
        d.text((0, i * lh), x, font=font, fill=fill)
    return img


def _fit_text(text: str, max_w: int, sizes: tuple[int, ...], max_lines: int, weight: int = 760, fill=TEXT) -> Image.Image:
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    for s in sizes:
        f = _font(s, weight)
        lines = _wrap(tmp, text, f, max_w)
        if len(lines) <= max_lines:
            return _text(lines, f, fill)
    f = _font(sizes[-1], weight)
    lines = _wrap(tmp, text, f, max_w)[:max_lines]
    return _text(lines, f, fill)


def _alpha(layer: Image.Image, k: float) -> Image.Image:
    if k >= 1:
        return layer
    out = layer.copy()
    a = out.getchannel("A").point(lambda v: int(v * max(0.0, k)))
    out.putalpha(a)
    return out


class Graphic:
    """One story's graphic, drawn into a w x h transparent layer at local time lt (seconds into the scene)."""

    def __init__(self, spec: dict[str, Any], color: tuple[int, int, int], w: int, h: int):
        self.s, self.c, self.w, self.h = spec, color, w, h
        self.kind = spec["type"]
        self.tall = h > w * 0.8          # the vertical cut
        u = min(w / 1760, h / 470) if not self.tall else w / 980
        self.u = u
        cap = (spec.get("caption") or "").strip()
        self.caption = _fit_text(cap.upper(), int(w * 0.9), (int(34 * u),) if not self.tall else (34, 30), 2, 800, self.c) if cap else None
        getattr(self, f"_prep_{self.kind}")()

    def render(self, lt: float) -> Image.Image:
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        getattr(self, f"_draw_{self.kind}")(layer, lt)
        return layer

    def _cap(self, layer: Image.Image, lt: float, x: int = 0, y: int = 0) -> int:
        """The caption, wiping in; returns the height it takes."""
        if not self.caption:
            return 0
        k = _ease((lt - 0.15) / 0.5)
        if k > 0:
            cw = int(self.caption.width * k)
            if cw > 0:
                layer.alpha_composite(self.caption.crop((0, 0, cw, self.caption.height)), (x, y))
        return self.caption.height + int(18 * self.u)

    # ---------------- map
    def _prep_map(self) -> None:
        self.places = [place(p) for p in self.s["places"]]
        cap_h = (self.caption.height + int(18 * self.u)) if self.caption else 0
        mw, mh = self.w, self.h - cap_h
        if mh > mw * 0.8:  # tall (the vertical cut): a wide map, centred in the space
            cap_h += int((mh - mw * 0.8) / 2)
            mh = int(mw * 0.8)
        self.map_y = cap_h
        lons = [p["pin"][0] for p in self.places]
        lats = [p["pin"][1] for p in self.places]
        for p in self.places:  # take in the whole of each highlighted country (but not all of Russia or the US's islands)
            for name in p["countries"][:3]:
                c = world().get(name.lower())
                if c and name not in ("Russia", "United States of America", "Canada", "France", "Norway"):
                    for r in c["rings"]:
                        if len(r) > 12:
                            lons += [x for x, _ in r]
                            lats += [y for _, y in r]
        lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
        span = max(lo1 - lo0, 50.0) * 1.35
        cx, cy = (lo0 + lo1) / 2, (la0 + la1) / 2
        k = math.cos(math.radians(max(-60, min(60, cy))))
        lat_span = span * k * mh / mw
        if lat_span < (la1 - la0) * 1.4:   # tall regions: widen to fit
            lat_span = (la1 - la0) * 1.4
            span = lat_span * mw / mh / k
        self.view = (cx - span / 2, cx + span / 2, cy + lat_span / 2, cy - lat_span / 2)
        self.mw, self.mh = mw, mh
        hi = {n for p in self.places for n in p["countries"]}
        base = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
        glow = Image.new("RGBA", (mw, mh), (0, 0, 0, 0))
        bd, gd = ImageDraw.Draw(base), ImageDraw.Draw(glow)
        for c in {id(v): v for v in world().values()}.values():
            for r in c["rings"]:
                pts = [self._xy(x, y) for x, y in r]
                if c["name"] in hi:
                    gd.polygon(pts, fill=self.c + (235,), outline=tuple(min(255, v + 60) for v in self.c) + (255,))
                else:
                    bd.polygon(pts, fill=LAND + (255,), outline=EDGE + (255,))
        self.base, self.glow = base, glow
        self.labels = []
        for p in self.places:
            f = _font(int(30 * self.u) if not self.tall else 32, 800)
            self.labels.append(_text([p["label"].upper()], f, TEXT))

    def _xy(self, lon: float, lat: float) -> tuple[float, float]:
        x0, x1, y0, y1 = self.view
        return (lon - x0) / (x1 - x0) * self.mw, (y0 - lat) / (y0 - y1) * self.mh

    def _draw_map(self, layer: Image.Image, lt: float) -> None:
        self._cap(layer, lt)
        oy = self.map_y
        layer.alpha_composite(_alpha(self.base, _ease(lt / 0.5)), (0, oy))
        layer.alpha_composite(_alpha(self.glow, _ease((lt - 0.4) / 0.7)), (0, oy))
        d = ImageDraw.Draw(layer)
        pins = {p["label"]: self._xy(*p["pin"]) for p in self.places}
        u = self.u if not self.tall else 1.0
        if self.s.get("from") and self.s.get("to"):
            a = pins[place(self.s["from"])["label"]]
            b = pins[place(self.s["to"])["label"]]
            k = _ease((lt - 0.9) / 1.0)
            if k > 0:
                mx, my = (a[0] + b[0]) / 2, min(a[1], b[1]) - abs(b[0] - a[0]) * 0.28 - 40 * u
                pts = []
                for i in range(int(48 * k) + 1):
                    s = i / 48
                    pts.append(((1 - s) ** 2 * a[0] + 2 * (1 - s) * s * mx + s * s * b[0], oy + (1 - s) ** 2 * a[1] + 2 * (1 - s) * s * my + s * s * b[1]))
                col = (255, 255, 255) if not self.s.get("blocked") else (255, 210, 210)
                if len(pts) > 1:
                    d.line(pts, fill=col + (255,), width=max(3, int(6 * u)), joint="curve")
                if k >= 0.999:  # arrowhead
                    (px, py), (qx, qy) = pts[-3], pts[-1]
                    ang = math.atan2(qy - py, qx - px)
                    L = 26 * u
                    d.polygon([(qx, qy), (qx - L * math.cos(ang - 0.45), qy - L * math.sin(ang - 0.45)),
                               (qx - L * math.cos(ang + 0.45), qy - L * math.sin(ang + 0.45))], fill=col + (255,))
                if self.s.get("blocked"):
                    kx = _ease((lt - 2.0) / 0.35)
                    if kx > 0:
                        cx_, cy_ = 0.25 * a[0] + 0.5 * mx + 0.25 * b[0], oy + 0.25 * a[1] + 0.5 * my + 0.25 * b[1]
                        r = 34 * u * (0.6 + 0.4 * kx)
                        d.ellipse((cx_ - r * 1.35, cy_ - r * 1.35, cx_ + r * 1.35, cy_ + r * 1.35), fill=RED + (int(255 * kx),))
                        d.line((cx_ - r * 0.7, cy_ - r * 0.7, cx_ + r * 0.7, cy_ + r * 0.7), fill=(255, 255, 255, int(255 * kx)), width=max(4, int(9 * u)))
                        d.line((cx_ - r * 0.7, cy_ + r * 0.7, cx_ + r * 0.7, cy_ - r * 0.7), fill=(255, 255, 255, int(255 * kx)), width=max(4, int(9 * u)))
        for i, p in enumerate(self.places):
            k = _ease((lt - 0.6 - 0.2 * i) / 0.4)
            if k <= 0:
                continue
            x, y = pins[p["label"]]
            y += oy
            r = 11 * u
            ring = r * (1.6 + 1.4 * ((lt * 0.8 + i * 0.3) % 1.0))
            d.ellipse((x - ring, y - ring, x + ring, y + ring), outline=(255, 255, 255, int(150 * k * (1 - (lt * 0.8 + i * 0.3) % 1.0))), width=max(2, int(3 * u)))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, int(255 * k)), outline=PLATE + (255,), width=max(2, int(3 * u)))
            lab = self.labels[i]
            lx = int(min(max(8, x - lab.width / 2), self.w - lab.width - 8))
            ly = int(y + r + 10 * u) if y + r + 10 * u + lab.height < self.h else int(y - r - 10 * u - lab.height)
            plate = Image.new("RGBA", (lab.width + int(24 * u), lab.height + int(8 * u)), PLATE + (215,))
            plate.alpha_composite(lab, (int(12 * u), int(4 * u)))
            layer.alpha_composite(_alpha(plate, k), (max(0, lx - int(12 * u)), ly))

    # ---------------- number (with an optional split)
    def _prep_number(self) -> None:
        self.val = _value(self.s["value"])
        size = int(200 * self.u) if not self.tall else 210
        self.num_font = _font(size, 840, 100)
        self.cap_big = _fit_text(self.s.get("caption", ""), int(self.w * (0.5 if not self.tall else 0.92)),
                                 (int(46 * self.u), int(40 * self.u)) if not self.tall else (52, 46), 3, 640, TEXT)
        self.caption = None
        self.parts = [(a, _value(b), b) for a, b in self.s.get("parts") or []]
        self.part_labels = [_text([f"{a}"], _font(int(28 * self.u) if not self.tall else 32, 640), MUTED) for a, _, _ in self.parts]
        self.part_vals = [_text([b], _font(int(40 * self.u) if not self.tall else 44, 820), TEXT) for _, _, b in self.parts]

    def _draw_number(self, layer: Image.Image, lt: float) -> None:
        pre, x, dec, suf = self.val
        k = _ease((lt - 0.2) / 1.3)
        shown = _fmt(pre, x * k, dec, suf) if k < 1 else self.s["value"].strip()
        d = ImageDraw.Draw(layer)
        a = int(255 * _ease(lt / 0.3))
        d.text((0, 0), shown, font=self.num_font, fill=TEXT + (a,))
        num_w = int(d.textlength(_fmt(pre, x, dec, suf), font=self.num_font))
        asc, desc = self.num_font.getmetrics()
        bar_h = int(14 * self.u) if not self.tall else 16
        d.rectangle((0, asc + desc + 6, int(num_w * _ease((lt - 0.4) / 0.8)), asc + desc + 6 + bar_h), fill=self.c + (255,))
        kc = _ease((lt - 0.7) / 0.5)
        if not self.tall:
            cx, cy = max(num_w + int(70 * self.u), int(self.w * 0.45)), int(30 * self.u)
        else:
            cx, cy = 0, asc + desc + 50
        layer.alpha_composite(_alpha(self.cap_big, kc), (cx, cy))
        if self.parts:  # a stacked bar splitting the total
            tot = sum(v[1] for _, v, _ in self.parts) or 1
            if not self.tall:
                bx, by, bw = cx, cy + self.cap_big.height + int(40 * self.u), self.w - cx
            else:
                bx, by, bw = 0, cy + self.cap_big.height + 60, self.w
            bh = int(30 * self.u) if not self.tall else 34
            kb = _ease((lt - 1.3) / 1.0)
            x0 = bx
            shades = [self.c, tuple(int(v * 0.55 + 40) for v in self.c), tuple(int(v * 0.35 + 30) for v in self.c)]
            for i, (lab, v, raw) in enumerate(self.parts):
                seg = bw * v[1] / tot
                d.rectangle((x0, by, x0 + max(0, seg * kb - 4), by + bh), fill=shades[i % 3] + (255,))
                kl = _ease((lt - 1.6 - 0.25 * i) / 0.4)
                if kl > 0:
                    layer.alpha_composite(_alpha(self.part_vals[i], kl), (int(x0), by + bh + int(12 * self.u)))
                    layer.alpha_composite(_alpha(self.part_labels[i], kl), (int(x0), by + bh + int(14 * self.u) + self.part_vals[i].height))
                x0 += seg

    # ---------------- change: before and after
    def _prep_change(self) -> None:
        self.pct = float(str(self.s["change"]).strip().rstrip("%"))
        f = _font(int(30 * self.u) if not self.tall else 34, 700)
        self.lb = _text([self.s["before"]], f, MUTED)
        self.la = _text([self.s["after"]], f, TEXT)
        self.badge = _text([("+" if self.pct > 0 else "−") + f"{abs(self.pct):g}%"], _font(int(120 * self.u) if not self.tall else 130, 840), TEXT)

    def _draw_change(self, layer: Image.Image, lt: float) -> None:
        top = self._cap(layer, lt)
        d = ImageDraw.Draw(layer)
        before, after = 1.0, max(0.05, 1 + self.pct / 100)
        mx = max(before, after)
        if not self.tall:
            bw = int(self.w * 0.62)
            bh = int(62 * self.u)
            rows = [(self.lb, before, (70, 96, 100)), (self.la, after, self.c)]
            y = top + int(10 * self.u)
            for i, (lab, v, col) in enumerate(rows):
                k = _ease((lt - 0.4 - 0.5 * i) / 0.9)
                layer.alpha_composite(_alpha(lab, _ease((lt - 0.3 - 0.5 * i) / 0.4)), (0, y))
                y2 = y + lab.height + int(8 * self.u)
                d.rectangle((0, y2, int(bw * v / mx * k), y2 + bh), fill=col + (255,))
                y = y2 + bh + int(30 * self.u)
            kb = _ease((lt - 1.5) / 0.5)
            layer.alpha_composite(_alpha(self.badge, kb), (bw + int(60 * self.u), top + int(40 * self.u)))
        else:
            base = self.h - 40
            bw = int(self.w * 0.36)
            hmax = int(self.h * 0.5)
            for i, (lab, v, col) in enumerate([(self.lb, before, (70, 96, 100)), (self.la, after, self.c)]):
                k = _ease((lt - 0.4 - 0.5 * i) / 0.9)
                x = int(self.w * (0.04 + 0.5 * i))
                hh = int(hmax * v / mx * k)
                d.rectangle((x, base - hh, x + bw, base), fill=col + (255,))
                layer.alpha_composite(_alpha(lab, _ease((lt - 0.3 - 0.5 * i) / 0.4)), (x, base + 8 - lab.height - hh - 50 if hh else base - lab.height))
            layer.alpha_composite(_alpha(self.badge, _ease((lt - 1.5) / 0.5)), (int(self.w * 0.04), top + 10))

    # ---------------- bars: a few stated figures side by side
    def _prep_bars(self) -> None:
        self.rows = [(a, _value(b), b) for a, b in self.s["items"]]
        f = _font(int(30 * self.u) if not self.tall else 34, 700)
        fv = _font(int(40 * self.u) if not self.tall else 44, 820)
        self.rl = [_text([a], f, MUTED) for a, _, _ in self.rows]
        self.rv = [_text([b], fv, TEXT) for _, _, b in self.rows]

    def _draw_bars(self, layer: Image.Image, lt: float) -> None:
        top = self._cap(layer, lt)
        d = ImageDraw.Draw(layer)
        mx = max(v[1] for _, v, _ in self.rows) or 1
        n = len(self.rows)
        avail = self.h - top
        row = avail / n
        lw = max(x.width for x in self.rl) + int(30 * self.u)
        if self.tall:
            lw = 0
        for i, (lab, v, raw) in enumerate(self.rows):
            k = _ease((lt - 0.4 - 0.3 * i) / 0.9)
            y = int(top + i * row)
            if self.tall:
                layer.alpha_composite(_alpha(self.rl[i], k), (0, y))
                y += self.rl[i].height + 6
            else:
                layer.alpha_composite(_alpha(self.rl[i], k), (0, y + int(row * 0.2)))
            bh = int(min(row * 0.5, 60 * (self.u if not self.tall else 1)))
            full = self.w - lw - self.rv[i].width - int(40 * self.u)
            ww = int(full * v[1] / mx * k)
            yb = y + (int(row * 0.2) if not self.tall else 0)
            d.rectangle((lw, yb, lw + ww, yb + bh), fill=(self.c if v[1] == mx else (70, 96, 100)) + (255,))
            if k > 0.05:
                layer.alpha_composite(_alpha(self.rv[i], k), (lw + ww + int(16 * self.u), yb + (bh - self.rv[i].height) // 2))

    # ---------------- list: tiles
    def _prep_list(self) -> None:
        f = _font(int(42 * self.u) if not self.tall else 44, 760)
        self.tiles = [_text([x], f, TEXT) for x in self.s["items"]]

    def _draw_list(self, layer: Image.Image, lt: float) -> None:
        top = self._cap(layer, lt)
        n = len(self.tiles)
        cols = (3 if n > 4 else 2) if not self.tall else 1 if n <= 4 else 2
        rows = math.ceil(n / cols)
        gap = int(18 * self.u) if not self.tall else 18
        tw = (self.w - gap * (cols - 1)) / cols
        th = min((self.h - top - gap * (rows - 1)) / rows, 150 * (self.u if not self.tall else 1.2))
        for i, lab in enumerate(self.tiles):
            k = _ease((lt - 0.4 - 0.22 * i) / 0.45)
            if k <= 0:
                continue
            c, r = i % cols, i // cols
            x, y = int(c * (tw + gap)), int(top + r * (th + gap) + (1 - k) * 20)
            tile = Image.new("RGBA", (int(tw), int(th)), PLATE + (225,))
            td = ImageDraw.Draw(tile)
            td.rectangle((0, 0, int(8 * self.u) + 2, int(th)), fill=self.c + (255,))
            td.text((int(tw - 80 * self.u), int(th / 2 - 22 * self.u)), f"{i + 1:02d}", font=_font(int(36 * self.u) if not self.tall else 38, 820), fill=self.c + (200,))
            tile.alpha_composite(lab, (int(30 * self.u) + 6, int((th - lab.height) / 2)))
            layer.alpha_composite(_alpha(tile, k), (x, y))

    # ---------------- steps: what happened, in order
    def _prep_steps(self) -> None:
        n = len(self.s["items"])
        if not self.tall:
            bw = (self.w - (n - 1) * 70 * self.u) / n
            self.step_w = bw
            self.step_txt = [_fit_text(x, int(bw - 50 * self.u), (int(42 * self.u), int(36 * self.u), int(30 * self.u)), 3, 720) for x in self.s["items"]]
        else:
            self.step_w = self.w
            self.step_txt = [_fit_text(x, self.w - 140, (40, 36), 2, 720) for x in self.s["items"]]

    def _draw_steps(self, layer: Image.Image, lt: float) -> None:
        top = self._cap(layer, lt)
        d = ImageDraw.Draw(layer)
        n = len(self.step_txt)
        for i, txt in enumerate(self.step_txt):
            k = _ease((lt - 0.4 - 0.55 * i) / 0.5)
            if k <= 0:
                continue
            if not self.tall:
                x = int(i * (self.step_w + 70 * self.u))
                h = self.h - top - int(10 * self.u)
                box = Image.new("RGBA", (int(self.step_w), int(h)), PLATE + (225,))
                bd = ImageDraw.Draw(box)
                bd.rectangle((0, 0, int(self.step_w), int(8 * self.u) + 2), fill=self.c + (255,))
                bd.text((int(24 * self.u), int(26 * self.u)), str(i + 1), font=_font(int(64 * self.u), 840), fill=self.c + (255,))
                box.alpha_composite(txt, (int(24 * self.u), int(110 * self.u)))
                layer.alpha_composite(_alpha(box, k), (x, top + int((1 - k) * 18)))
                if i < n - 1 and _ease((lt - 0.7 - 0.55 * i) / 0.4) > 0:
                    ax, ay = x + self.step_w + 14 * self.u, top + h / 2
                    d.polygon([(ax, ay - 18 * self.u), (ax + 40 * self.u, ay), (ax, ay + 18 * self.u)], fill=self.c + (255,))
            else:
                rh = (self.h - top) / n
                y = int(top + i * rh)
                box = Image.new("RGBA", (self.w, int(rh - 24)), PLATE + (225,))
                bd = ImageDraw.Draw(box)
                bd.rectangle((0, 0, 10, int(rh)), fill=self.c + (255,))
                bd.text((30, int((rh - 24) / 2 - 40)), str(i + 1), font=_font(70, 840), fill=self.c + (255,))
                box.alpha_composite(txt, (120, int((rh - 24 - txt.height) / 2)))
                layer.alpha_composite(_alpha(box, k), (int((1 - k) * 30), y))

    # ---------------- quote: a named person's own words
    def _prep_quote(self) -> None:
        text = "“" + self.s["text"].strip().strip("\"“”") + "”"
        if not self.tall:
            self.qt = _fit_text(text, int(self.w * 0.86), (int(52 * self.u), int(46 * self.u), int(40 * self.u)), 4, 620)
        else:
            self.qt = _fit_text(text, self.w - 40, (58, 52, 46), 7, 620)
        by = self.s["by"].strip() + (f", {self.s['role'].strip()}" if self.s.get("role") else "")
        self.qby = _text(["— " + by], _font(int(32 * self.u) if not self.tall else 36, 760), self.c)
        self.caption = None

    def _draw_quote(self, layer: Image.Image, lt: float) -> None:
        d = ImageDraw.Draw(layer)
        u = self.u if not self.tall else 1.0
        k = _ease(lt / 0.5)
        d.text((0, -int(40 * u)), "“", font=_font(int(220 * u), 840), fill=self.c + (int(255 * k),))
        x0 = int(120 * u)
        kq = _ease((lt - 0.3) / 0.9)
        if kq > 0:  # the words reveal top to bottom
            h = max(1, int(self.qt.height * kq))
            layer.alpha_composite(self.qt.crop((0, 0, self.qt.width, h)), (x0, int(20 * u)))
        kb = _ease((lt - 1.2) / 0.5)
        layer.alpha_composite(_alpha(self.qby, kb), (x0, int(20 * u) + self.qt.height + int(24 * u)))
