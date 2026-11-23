"""Build the collage video timeline with MoviePy and render it.

    python tools/render.py preview      → build/preview_540p.mp4   (fast check)
    python tools/render.py final        → final/hero_archetypes_1080p.mp4
    python tools/render.py still 42.5   → build/still_42.5.png      (single frame)

Timeline source: script/scenes.yaml (the storyboard), timed against
build/narration_timing.json (written by tools/make_voiceover.py).

Time references used in scenes.yaml:
    s3        start of section 3          s3e     end of section 3
    s3.2      start of section 3, line 2  s3.2e   end of that line
    s3.2@0.5  halfway through that line   s3.2+0.4 / s3.2-1  offsets in seconds
    12.5      absolute seconds            end     end of the video
"""
import json
import math
import random
import re
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import collage as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
TIMING = json.loads((ROOT / "build" / "narration_timing.json").read_text())
SCENES = yaml.safe_load((ROOT / "script" / "scenes.yaml").read_text(encoding="utf-8"))
MISSING = set()


# ── time references ─────────────────────────────────────────
def T(ref):
    if ref is None:
        return None
    if isinstance(ref, (int, float)):
        return float(ref)
    ref = str(ref).strip()
    m = re.fullmatch(r"end([+-][\d.]+)?", ref)
    if m:
        return TIMING["duration"] + float(m.group(1) or 0)
    m = re.fullmatch(r"s(\d+)(?:\.(\d+))?(e)?(?:@([\d.]+))?([+-][\d.]+)?", ref)
    if not m:
        return float(ref)
    sec = next(s for s in TIMING["sections"] if s["id"] == int(m.group(1)))
    if m.group(2):
        ln = sec["lines"][int(m.group(2)) - 1]
        a, b = ln["start"], ln["end"]
    else:
        a, b = sec["start"], sec["end"]
    t = b if m.group(3) else a
    if m.group(4):
        t = a + (b - a) * float(m.group(4))
    if m.group(5):
        t += float(m.group(5))
    return t


# ── image cache ─────────────────────────────────────────────
_img_cache = {}


def cutout(name):
    names = name if isinstance(name, list) else [name]
    for n in names:
        p = ROOT / "assets" / "cutouts" / f"{n}.png"
        if p.exists():
            if n not in _img_cache:
                _img_cache[n] = Image.open(p).convert("RGBA")
            return _img_cache[n]
    MISSING.add(names[0])
    return None


def fit(im, W, H, h=None, w=None):
    if h is not None:
        th = max(2, int(h * H))
        tw = max(2, int(im.width * th / im.height))
        if w is not None and tw > w * W:
            tw = int(w * W)
            th = int(im.height * tw / im.width)
    else:
        tw = max(2, int(w * W))
        th = max(2, int(im.height * tw / im.width))
    return im.resize((tw, th), Image.LANCZOS)


# ── head silhouette for the finale mosaic ───────────────────
HEAD = [(0.30, 1.00), (0.33, 0.80), (0.22, 0.70), (0.16, 0.52), (0.18, 0.32), (0.28, 0.16), (0.45, 0.07),
        (0.62, 0.08), (0.75, 0.15), (0.80, 0.27), (0.80, 0.37), (0.83, 0.43), (0.91, 0.56), (0.85, 0.60),
        (0.86, 0.64), (0.83, 0.67), (0.85, 0.70), (0.81, 0.74), (0.82, 0.80), (0.74, 0.84), (0.62, 0.84),
        (0.62, 1.00)]


# ── elements ────────────────────────────────────────────────
class Element:
    def __init__(self, spec, scene, R):
        self.s, self.scene, self.R = spec, scene, R
        self.at = T(spec.get("at", scene["t0"])) if spec.get("at") is not None else scene["t0"]
        self.until = T(spec["until"]) if spec.get("until") is not None else None
        self.seed = abs(hash(json.dumps(spec, sort_keys=True, default=str))) % 10000
        self.base = None

    def active(self, t):
        return t >= self.at and (self.until is None or t < self.until + 0.35)

    # keyframed property
    def prop(self, name, t, default):
        v = self.s.get(name, default)
        for k in self.s.get("keys", []):
            kt = T(k["at"])
            if name in k and t >= kt:
                prev = v
                d = k.get("dur", 0.6)
                e = C.ease_in_out((t - kt) / d)
                v = prev + (k[name] - prev) * e
        return v

    def motion(self, t):
        """→ (dx, dy, scale, rot, alpha) from entrance/exit/wobble."""
        M = CFG["motion"]
        u = t - self.at
        enter = self.s.get("enter", "pop")
        dur = self.s.get("enter_dur", M["slide_in"])
        e = u / dur if dur > 0 else 1
        dx = dy = 0.0
        scale, alpha = 1.0, 1.0
        W, H = self.R.W, self.R.H
        if enter == "pop":
            scale = max(0.0, C.ease_out_back(e, M["overshoot"])) if e < 1 else 1.0
        elif enter.startswith("slide"):
            k = 1 - C.ease_out_back(e, M["overshoot"] * 0.6) if e < 1 else 0
            off = {"slide_left": (-1.1 * W, 0), "slide_right": (1.1 * W, 0),
                   "slide_up": (0, -1.1 * H), "slide_down": (0, 1.1 * H)}[enter]
            dx, dy = off[0] * k, off[1] * k
        elif enter == "drop":
            k = 1 - C.ease_out_back(e, M["overshoot"]) if e < 1 else 0
            dy = -0.9 * H * k
        elif enter == "fade":
            alpha = C.ease_in_out(e)
        if self.until is not None and t > self.until:
            x = (t - self.until) / 0.3
            scale *= max(0.0, 1 - C.ease_in_out(x))
            alpha *= max(0.0, 1 - x)
        rot = 0.0
        if self.s.get("wobble", True):
            rot = M["wobble_deg"] * math.sin(2 * math.pi * M["wobble_hz"] * t + self.seed)
        drift = 1 + self.s.get("drift", 0.025) * max(0.0, u) / 6.0
        return dx, dy, scale * drift, rot, alpha

    def place(self, frame, im, x, y, t, extra_rot=0.0):
        dx, dy, sc, rot, alpha = self.motion(t)
        if sc <= 0.01 or alpha <= 0.01 or im is None:
            return
        r = self.prop("rot", t, 0.0) + rot + extra_rot
        if abs(sc - 1) > 0.004:
            im = im.resize((max(2, int(im.width * sc)), max(2, int(im.height * sc))), Image.BILINEAR)
        if abs(r) > 0.05:
            im = im.rotate(r, resample=Image.BICUBIC, expand=True)
        if alpha < 0.999:
            a = im.getchannel("A").point(lambda v: int(v * alpha))
            im = im.copy()
            im.putalpha(a)
        px = int(x * self.R.W + dx - im.width / 2)
        py = int(y * self.R.H + dy - im.height / 2)
        self.R.paste(frame, im, px, py)


class CutoutEl(Element):
    def draw(self, frame, t):
        if self.base is None:
            src = cutout(self.s["img"])
            if src is None:
                label = self.s.get("missing_label") or str(self.s["img"] if not isinstance(self.s["img"], list) else self.s["img"][0]).replace("_", " ").upper()
                self.base = C.caption_image(label, "tape", CFG, self.R.S, self.scene["pal"], size=40, seed=self.seed)
            else:
                self.base = fit(src, self.R.W, self.R.H, self.s.get("h"), self.s.get("w"))
        h0 = self.s.get("h") or 1
        sc = self.prop("h", t, h0) / h0 if self.s.get("h") else 1.0
        im = self.base if abs(sc - 1) < 0.004 else self.base.resize((int(self.base.width * sc), int(self.base.height * sc)), Image.BILINEAR)
        self.place(frame, im, self.prop("x", t, 0.5), self.prop("y", t, 0.5), t)


class CaptionEl(Element):
    def draw(self, frame, t):
        if self.base is None:
            self.base = C.caption_image(self.s["text"], self.s.get("style", "tape"), CFG, self.R.S,
                                        self.scene["pal"], size=self.s.get("size", 60), seed=self.seed)
        if self.s.get("blink") and int((t - self.at) * 2.2) % 2 == 1:
            return
        self.place(frame, self.base, self.prop("x", t, 0.5), self.prop("y", t, 0.15), t)


class PathEl(Element):
    def draw(self, frame, t):
        R = self.R
        if self.base is None:
            pts = [(x * R.W, y * R.H) for x, y in self.s["points"]]
            self.dots, _ = C.path_dots(pts, CFG["path"]["dot_spacing"] * R.S, seed=self.seed)
            self.stops = [pts[i] for i in self.s.get("stops", [])]
            curve_len = len(self.dots)
            # stop progress positions along the dots
            self.stop_frac = []
            for sx, sy in self.stops:
                dd = np.hypot(self.dots[:, 0] - sx, self.dots[:, 1] - sy)
                self.stop_frac.append(int(np.argmin(dd)) / max(1, curve_len - 1))
            self.base = True
        dur = self.s.get("dur", 3.0)
        p = C.ease_in_out((t - self.at) / dur)
        sp = [max(0.0, min(1.0, (p - f) * 8 + 0.2)) if p >= f else 0 for f in self.stop_frac]
        col = C.hex_rgb(self.s.get("color", CFG["path"]["color"])) + (230,)
        C.draw_path(frame, self.dots, p, CFG["path"]["dot_radius"] * R.S, col, self.stops, sp, R.S)


class DarkenEl(Element):
    def draw(self, frame, t):
        a = self.s.get("alpha", 0.45) * C.ease_in_out((t - self.at) / self.s.get("dur", 1.2))
        col = C.hex_rgb(self.s.get("color", "#120a18"))
        box = self.s.get("box")
        ov = Image.new("RGBA", frame.size, col + (int(255 * a),))
        if box:
            m = Image.new("L", frame.size, 0)
            x0, y0, x1, y1 = box
            ImageDraw.Draw(m).rectangle([x0 * self.R.W, y0 * self.R.H, x1 * self.R.W, y1 * self.R.H], fill=int(255 * a))
            ov.putalpha(m)
        frame.alpha_composite(ov)


class DividerEl(Element):
    """A torn strip of white paper (split screens)."""
    def draw(self, frame, t):
        R = self.R
        if self.base is None:
            h = R.H + 40
            w = int(26 * R.S)
            prof = C.tear_profile(h, seed=9)
            m = Image.new("L", (w * 3, h), 0)
            d = ImageDraw.Draw(m)
            for y in range(h):
                c = w * 1.5 + prof[y] * 0.15 * R.S
                d.line([(c - w / 2 - abs(prof[y]) % 4, y), (c + w / 2 + abs(prof[(y * 7) % h]) % 4, y)], fill=255)
            strip = Image.new("RGBA", m.size, (248, 245, 236, 255))
            strip.putalpha(m)
            sh = Image.new("RGBA", m.size, (0, 0, 0, 0))
            sh.putalpha(m.filter(ImageFilter.GaussianBlur(6 * R.S)).point(lambda v: v // 3))
            out = Image.new("RGBA", m.size, (0, 0, 0, 0))
            out.alpha_composite(sh, (int(6 * R.S), 0))
            out.alpha_composite(strip)
            self.base = out
        p = C.ease_out((t - self.at) / 0.5)
        im = self.base.crop((0, 0, self.base.width, max(2, int(self.base.height * p))))
        frame.alpha_composite(im, (int(self.s.get("x", 0.5) * R.W - im.width / 2), -20))


class TintEl(Element):
    """Coloured paper panel over part of the frame (e.g. Hyrule-green half of a split screen)."""
    def draw(self, frame, t):
        R = self.R
        x0, y0, x1, y1 = self.s["box"]
        col = C.hex_rgb(self.s.get("color") or CFG["palettes"][self.s.get("palette", "hyrule")]["paper"])
        a = self.s.get("alpha", 0.75) * C.ease_in_out((t - self.at) / 0.4)
        panel = Image.new("RGBA", (int((x1 - x0) * R.W), int((y1 - y0) * R.H)), col + (int(255 * a),))
        frame.alpha_composite(panel, (int(x0 * R.W), int(y0 * R.H)))


class TreeEl(Element):
    """Paper-cut tree illustration (stands in for the Great Deku Tree; labelled on screen)."""
    def draw(self, frame, t):
        R = self.R
        if self.base is None:
            h = int(self.s.get("h", 0.6) * R.H)
            w = int(h * 0.9)
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            rng = random.Random(4)
            trunk = (92, 62, 38, 255)
            d.polygon([(w * 0.40, h), (w * 0.44, h * 0.45), (w * 0.56, h * 0.45), (w * 0.62, h)], fill=trunk)
            for _ in range(5):  # roots
                x = w * rng.uniform(0.3, 0.7)
                d.polygon([(w * 0.5, h * 0.88), (x - w * 0.12, h), (x + w * 0.04, h)], fill=trunk)
            greens = [(46, 96, 52), (62, 120, 60), (84, 140, 70), (38, 82, 46)]
            for _ in range(26):
                cx, cy = w * rng.uniform(0.18, 0.82), h * rng.uniform(0.08, 0.5)
                r = w * rng.uniform(0.12, 0.22)
                d.ellipse([cx - r, cy - r * 0.85, cx + r, cy + r * 0.85], fill=rng.choice(greens) + (255,))
            # a kindly face in the bark
            d.arc([w * 0.45, h * 0.58, w * 0.49, h * 0.62], 200, 340, fill=(40, 25, 15, 255), width=max(2, int(4 * R.S)))
            d.arc([w * 0.52, h * 0.58, w * 0.56, h * 0.62], 200, 340, fill=(40, 25, 15, 255), width=max(2, int(4 * R.S)))
            d.arc([w * 0.46, h * 0.64, w * 0.55, h * 0.72], 20, 160, fill=(40, 25, 15, 255), width=max(2, int(4 * R.S)))
            st = CFG["sticker"]
            self.base = C.make_sticker(im, border=int(st["border_px"] * R.S), shadow_offset=(int(10 * R.S), int(14 * R.S)),
                                       shadow_blur=int(14 * R.S), shadow_opacity=0.45)
        self.place(frame, self.base, self.s.get("x", 0.5), self.s.get("y", 0.55), t)


class LoopEl(Element):
    """Problem-solving cycle: labels around a circle with arrows, revealed one by one."""
    def draw(self, frame, t):
        R = self.R
        labels = self.s["labels"]
        cx, cy, rad = self.s.get("x", 0.7) * R.W, self.s.get("y", 0.55) * R.H, self.s.get("r", 0.22) * R.H
        step = self.s.get("step", 0.8)
        if self.base is None:
            self.base = [C.caption_image(l, "tape", CFG, R.S, self.scene["pal"], size=self.s.get("size", 40), seed=i) for i, l in enumerate(labels)]
        d = ImageDraw.Draw(frame)
        col = C.hex_rgb(self.scene["pal"]["accent"]) + (255,)
        n = len(labels)
        for i in range(n):
            ti = self.at + i * step
            if t < ti:
                continue
            a0 = -90 + i * 360 / n + 18
            a1 = -90 + (i + 1) * 360 / n - 18
            p = C.ease_out((t - ti - 0.25) / 0.5)
            if p > 0:
                a_end = a0 + (a1 - a0) * p
                d.arc([cx - rad, cy - rad, cx + rad, cy + rad], a0, a_end, fill=col, width=max(3, int(6 * R.S)))
                if p >= 1:
                    ang = math.radians(a1)
                    hx, hy = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
                    tx, ty = -math.sin(ang), math.cos(ang)
                    s = 16 * R.S
                    d.polygon([(hx + tx * s, hy + ty * s), (hx - tx * s * 0.2 + math.cos(ang) * s * 0.7, hy - ty * s * 0.2 + math.sin(ang) * s * 0.7),
                               (hx - tx * s * 0.2 - math.cos(ang) * s * 0.7, hy - ty * s * 0.2 - math.sin(ang) * s * 0.7)], fill=col)
        for i, im in enumerate(self.base):
            ti = self.at + i * step
            if t < ti:
                continue
            ang = math.radians(-90 + i * 360 / n)
            e = C.ease_out_back((t - ti) / 0.4, CFG["motion"]["overshoot"])
            if e <= 0.02:
                continue
            j = im.resize((max(2, int(im.width * e)), max(2, int(im.height * e))), Image.BILINEAR)
            R.paste(frame, j, int(cx + rad * math.cos(ang) - j.width / 2), int(cy + rad * math.sin(ang) - j.height / 2))


class MontageEl(Element):
    """Fast montage: each hero lands big, gets a stamp, then shrinks onto the journey trail."""
    def setup(self):
        R = self.R
        self.items = []
        for it in self.s["items"]:
            imgs = it["img"] if isinstance(it["img"], list) else [it["img"]]
            ims = [cutout(i) for i in imgs]
            ims = [i for i in ims if i is not None]
            if not ims:
                ims = [C.caption_image(imgs[0].replace("_", " ").upper(), "tape", CFG, R.S, self.scene["pal"], size=48)]
            # group image
            Hbig = int(self.s.get("h", 0.62) * R.H)
            parts = [i.resize((max(2, int(i.width * Hbig / i.height)), Hbig), Image.LANCZOS) for i in ims]
            ov = int(Hbig * 0.12)
            gw = sum(p.width for p in parts) - ov * (len(parts) - 1)
            maxw = int(self.s.get("max_w", 0.62) * R.W)
            g = Image.new("RGBA", (gw, Hbig), (0, 0, 0, 0))
            x = 0
            for k, p in enumerate(parts):
                g.alpha_composite(p, (x, int((k % 2) * Hbig * 0.03)) if k else (x, 0))
                x += p.width - ov
            if g.width > maxw:
                g = g.resize((maxw, int(g.height * maxw / g.width)), Image.LANCZOS)
            stamp = C.caption_image(it["caption"], "stamp", CFG, R.S, self.scene["pal"], size=it.get("size", 66), seed=len(self.items))
            tag = C.caption_image(it["label"], "type", CFG, R.S, self.scene["pal"], size=26, seed=len(self.items) + 40) if it.get("label") else None
            small = g.resize((max(2, int(g.width * 0.24)), max(2, int(g.height * 0.24))), Image.LANCZOS)
            self.items.append({"t": T(it["at"]), "big": g, "small": small, "stamp": stamp, "tag": tag})
        n = len(self.items)
        self.slots = [(0.07 + 0.86 * i / max(1, n - 1), 0.135 + 0.035 * math.sin(i * 1.7)) for i in range(n)]
        self.path_pts = [(x * R.W, y * R.H) for x, y in self.slots]
        self.dots, _ = C.path_dots(self.path_pts, CFG["path"]["dot_spacing"] * R.S, seed=3)
        self.base = True

    def draw(self, frame, t):
        R = self.R
        if self.base is None:
            self.setup()
        col = C.hex_rgb(CFG["path"]["color"]) + (220,)
        times = [it["t"] for it in self.items]
        cur = max([i for i, ti in enumerate(times) if ti <= t], default=-1)
        # trail path grows with each landed hero
        if cur >= 0:
            p = (cur + min(1.0, (t - times[cur]) / 0.6)) / max(1, len(self.items) - 1)
            C.draw_path(frame, self.dots, min(1.0, p), CFG["path"]["dot_radius"] * R.S * 0.8, col,
                        self.path_pts[:cur + 1], None, R.S)
        for i, it in enumerate(self.items):
            if t < it["t"]:
                continue
            nxt = times[i + 1] if i + 1 < len(times) else None
            sx, sy = self.slots[i]
            bx, by = self.s.get("x", 0.36), self.s.get("y", 0.58)
            if nxt is not None and t >= nxt:   # fly to trail slot
                k = C.ease_in_out((t - nxt) / 0.5)
                if k < 1:
                    s = 1 - 0.76 * k
                    im = it["big"].resize((max(2, int(it["big"].width * s)), max(2, int(it["big"].height * s))), Image.BILINEAR)
                    x, y = bx + (sx - bx) * k, by + (sy - by) * k
                else:
                    im, x, y = it["small"], sx, sy
                rot = 3 * math.sin(i * 2.1)
                im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
                R.paste(frame, im, int(x * R.W - im.width / 2), int(y * R.H - im.height / 2))
                continue
            u = t - it["t"]
            k = C.ease_out_back(u / 0.5, CFG["motion"]["overshoot"] * 0.6)
            x = bx + (1 - k) * -0.7
            rot = CFG["motion"]["wobble_deg"] * math.sin(2 * math.pi * CFG["motion"]["wobble_hz"] * t + i)
            im = it["big"].rotate(rot, resample=Image.BICUBIC, expand=True)
            R.paste(frame, im, int(x * R.W - im.width / 2), int(by * R.H - im.height / 2))
            if u > 0.35:
                e = C.ease_out_back((u - 0.35) / 0.3, 2.2)
                st = it["stamp"].rotate(-7 + 3 * math.sin(i), resample=Image.BICUBIC, expand=True)
                st = st.resize((max(2, int(st.width * e)), max(2, int(st.height * e))), Image.BILINEAR)
                R.paste(frame, st, int(self.s.get("stamp_x", 0.76) * R.W - st.width / 2), int(self.s.get("stamp_y", 0.52) * R.H - st.height / 2))
            if it["tag"] is not None and u > 0.6:
                tg = it["tag"]
                R.paste(frame, tg, int(self.s.get("stamp_x", 0.76) * R.W - tg.width / 2), int(0.70 * R.H))


class MosaicEl(Element):
    """'A thousand faces': every cutout assembles into one big head silhouette, piece by piece."""
    def setup(self):
        R = self.R
        box_h = self.s.get("h", 0.86) * R.H
        box_w = box_h
        ox, oy = self.s.get("x", 0.5) * R.W - box_w / 2, self.s.get("y", 0.52) * R.H - box_h / 2
        mask = Image.new("L", (int(box_w), int(box_h)), 0)
        ImageDraw.Draw(mask).polygon([(x * box_w, y * box_h) for x, y in HEAD], fill=255)
        # erode so tiles stay inside the outline
        m = np.asarray(mask.filter(ImageFilter.MinFilter(max(3, int(cell_px := self.s.get("cell", 54) * R.S * 0.5) | 1)))) > 0
        names = sorted(p.stem for p in (ROOT / "assets" / "cutouts").glob("*.png"))
        thumbs = []
        cell = int(self.s.get("cell", 54) * R.S)
        for n in names:
            im = cutout(n)
            t = im.copy()
            t.thumbnail((int(cell * 1.5), int(cell * 1.5)), Image.LANCZOS)
            thumbs.append(t)
        rng = random.Random(7)
        tiles = []
        for yy in range(0, int(box_h), int(cell * 0.78)):
            for xx in range(0, int(box_w), int(cell * 0.78)):
                jx, jy = xx + rng.uniform(-cell * 0.2, cell * 0.2), yy + rng.uniform(-cell * 0.2, cell * 0.2)
                cxp, cyp = int(min(box_w - 1, max(0, jx))), int(min(box_h - 1, max(0, jy)))
                if m[cyp, cxp]:
                    im = rng.choice(thumbs).rotate(rng.uniform(-25, 25), resample=Image.BICUBIC, expand=True)
                    tiles.append((ox + jx, oy + jy, im))
        # assemble from the face outward (front of the face first)
        fx, fy = ox + box_w * 0.75, oy + box_h * 0.45
        tiles.sort(key=lambda p: math.hypot(p[0] - fx, p[1] - fy) + rng.uniform(0, cell * 2))
        self.tiles = tiles
        outline = Image.new("RGBA", (int(box_w), int(box_h)), (0, 0, 0, 0))
        ImageDraw.Draw(outline).line([(x * box_w, y * box_h) for x, y in HEAD] + [(HEAD[0][0] * box_w, HEAD[0][1] * box_h)],
                                     fill=C.hex_rgb(self.scene["pal"]["accent"]) + (255,), width=max(3, int(7 * R.S)))
        self.outline, self.oxy = outline, (int(ox), int(oy))
        self.base = True

    def draw(self, frame, t):
        R = self.R
        if self.base is None:
            self.setup()
        dur = T(self.s["build_until"]) - self.at
        n = len(self.tiles)
        for i, (x, y, im) in enumerate(self.tiles):
            ti = self.at + dur * (i / n) ** 0.8
            if t < ti:
                break
            e = C.ease_out_back((t - ti) / 0.35, 2.0)
            j = im if e >= 0.999 else im.resize((max(2, int(im.width * e)), max(2, int(im.height * e))), Image.BILINEAR)
            R.paste(frame, j, int(x - j.width / 2), int(y - j.height / 2))
        if t > self.at + dur:
            a = C.ease_in_out((t - self.at - dur) / 0.8)
            o = self.outline.copy()
            o.putalpha(o.getchannel("A").point(lambda v: int(v * a)))
            frame.alpha_composite(o, self.oxy)


class CreditsEl(Element):
    def draw(self, frame, t):
        R = self.R
        if self.base is None:
            F = CFG["fonts"]
            ft = C.font(F["caption"], 54 * R.S)
            fb = C.font(F["type"], 25 * R.S)
            ink = C.hex_rgb(self.scene["pal"]["ink"]) + (255,)
            cols = self.s["columns"]
            W, H = int(0.88 * R.W), int(0.86 * R.H)
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.text((W // 2, 0), self.s.get("title", "CREDITS"), font=ft, fill=ink, anchor="ma")
            cw = W // len(cols)
            for ci, col in enumerate(cols):
                y = int(90 * R.S)
                for line in col:
                    bold = line.startswith("#")
                    txt = line.lstrip("# ")
                    f = C.font(F["body"], 28 * R.S, bold=True) if bold else fb
                    d.text((ci * cw + int(20 * R.S), y), txt, font=f, fill=ink)
                    y += int((40 if bold else 32) * R.S)
            self.base = im
        a = C.ease_in_out((t - self.at) / 0.6)
        im = self.base.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
        frame.alpha_composite(im, (int(0.06 * R.W), int(0.07 * R.H)))


TYPES = {"cutout": CutoutEl, "caption": CaptionEl, "path": PathEl, "darken": DarkenEl, "divider": DividerEl,
         "tint": TintEl, "tree": TreeEl, "loop": LoopEl, "montage": MontageEl, "mosaic": MosaicEl, "credits": CreditsEl}


# ── renderer ────────────────────────────────────────────────
class Renderer:
    def __init__(self, mode):
        o = CFG["output"][mode]
        self.W, self.H, self.fps = o["width"], o["height"], o["fps"]
        self.S = self.H / 1080
        self.mode = mode
        gcfg = CFG.get("grain", {})
        self.grain_hold = gcfg.get("hold_frames", 3)
        self.grain = C.grain_frames(self.W, self.H, n=4, strength=gcfg.get("strength", 2.5)) if gcfg.get("strength", 2.5) > 0 else None
        self.bg_cache = {}
        self.scenes = []
        for i, sc in enumerate(SCENES):
            sc = dict(sc)
            sc["t0"] = T(sc.get("start", 0)) if i else 0.0
            self.scenes.append(sc)
        for i, sc in enumerate(self.scenes):
            sc["t1"] = self.scenes[i + 1]["t0"] if i + 1 < len(self.scenes) else TIMING["duration"]
            sc["pal"] = CFG["palettes"][sc.get("palette", "title")]
            sc["els"] = [TYPES[e["type"]](e, sc, self) for e in sc.get("elements", [])]
        self.duration = TIMING["duration"]

    def paste(self, frame, im, x, y):
        if x >= frame.width or y >= frame.height or x + im.width <= 0 or y + im.height <= 0:
            return
        frame.alpha_composite(im, (max(0, x), max(0, y)),
                              (max(0, -x), max(0, -y), min(im.width, frame.width - x), min(im.height, frame.height - y)))

    def background(self, sc):
        key = (sc.get("palette", "title"), sc.get("bg", "paper"))
        if key not in self.bg_cache:
            self.bg_cache[key] = C.paper_texture(self.W, self.H, sc["pal"], style=sc.get("bg", "paper"),
                                                 seed=hash(key) % 100).convert("RGBA")
        return self.bg_cache[key]

    def scene_frame(self, sc, t):
        frame = self.background(sc).copy()
        for el in sc["els"]:
            if el.active(t):
                el.draw(frame, t)
        img = frame.convert("RGB")
        z = sc.get("zoom", CFG["motion"]["bg_zoom"])
        if z:
            k = 1 + z * C.ease_in_out((t - sc["t0"]) / max(0.1, sc["t1"] - sc["t0"]))
            cw, ch = self.W / k, self.H / k
            fx, fy = sc.get("focus", (0.5, 0.5))
            x0 = (self.W - cw) * fx
            y0 = (self.H - ch) * fy
            img = img.resize((self.W, self.H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        return np.asarray(img)

    def frame(self, t):
        idx = max(i for i, s in enumerate(self.scenes) if s["t0"] <= t)
        sc = self.scenes[idx]
        out = self.scene_frame(sc, t)
        tr = sc.get("transition", "tear")
        dur = CFG["motion"]["transition"] if tr == "tear" else 0.35
        if idx > 0 and tr != "cut" and t < sc["t0"] + dur:
            prev = self.scenes[idx - 1]
            old = self.scene_frame(prev, t)
            out = C.paper_tear(old, out, (t - sc["t0"]) / dur, self.S)
        if self.grain is not None:
            g = self.grain[(int(t * self.fps) // self.grain_hold) % len(self.grain)]
            out = np.clip(out.astype(np.int16) + g[..., None], 0, 255).astype(np.uint8)
        return out


def mix_audio(out_wav):
    """Voiceover over the music bed, music ducked under speech (ffmpeg)."""
    import subprocess
    vo_user = ROOT / "assets" / "voiceover.wav"
    vo = vo_user if vo_user.exists() else ROOT / "build" / "vo" / "voiceover_tts.wav"
    music = ROOT / CFG["music"]["file"]
    dur = TIMING["duration"]
    if not music.exists():
        print("  (no assets/music.mp3: music track left silent)")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vo), "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo",
                        "-filter_complex", "[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,apad[v];[v][1:a]amix=inputs=2:duration=longest:normalize=0,atrim=0:%f,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]" % dur,
                        "-map", "[a]", str(out_wav)], check=True)
        return
    m = CFG["music"]
    # volume automation: duck by duck_db during each narration line
    parts = []
    for s in TIMING["sections"]:
        for ln in s["lines"]:
            a, b = ln["start"] - m["duck_attack"], ln["end"] + m["duck_release"]
            parts.append(f"between(t,{a:.2f},{b:.2f})")
    duck = 10 ** (-m["duck_db"] / 20)
    expr = f"if({'+'.join(parts)},{duck:.4f},1)"
    base = 10 ** (m["level_db"] / 20)
    fc = (f"[1:a]aresample=48000,aloop=loop=-1:size=2e9,atrim=0:{dur},volume={base:.4f},volume='{expr}':eval=frame,"
          f"afade=t=in:d=1.5,afade=t=out:st={dur-3:.2f}:d=3[mus];"
          f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,apad[v];[v][mus]amix=inputs=2:duration=longest:normalize=0,atrim=0:{dur},"
          f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vo), "-i", str(music), "-filter_complex", fc, "-map", "[a]", str(out_wav)], check=True)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "still":
        R = Renderer("final")
        for ts in sys.argv[2:]:
            t = T(ts)
            out = ROOT / "build" / f"still_{ts}.png"
            Image.fromarray(R.frame(t)).save(out)
            print(out.relative_to(ROOT), f"t={t:.2f}")
        if MISSING:
            print("missing cutouts (placeholders shown):", sorted(MISSING))
        return
    from moviepy.editor import AudioFileClip, VideoClip
    R = Renderer(mode)
    o = CFG["output"][mode]
    wav = ROOT / "build" / "mix.wav"
    mix_audio(wav)
    clip = VideoClip(R.frame, duration=R.duration).set_audio(AudioFileClip(str(wav)))
    out = ROOT / o["file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    clip.write_videofile(str(out), fps=R.fps, codec="libx264", audio_codec="aac", audio_bitrate="192k",
                         preset=o["preset"], ffmpeg_params=["-crf", str(o["crf"]), "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
                         threads=4, logger="bar" if sys.stdout.isatty() else None)
    print("wrote", out.relative_to(ROOT))
    if MISSING:
        print("missing cutouts (placeholders shown):", sorted(MISSING))


if __name__ == "__main__":
    main()
