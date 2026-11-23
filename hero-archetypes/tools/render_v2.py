"""Draft 2 renderer: text-led archival collage, vertical 9:16.

    python tools/render_v2.py preview          → draft2/build/preview_540x960.mp4
    python tools/render_v2.py final            → final/hero_infinite_faces_vertical.mp4
    python tools/render_v2.py still 12 s3.2@0.5 → draft2/build/still_*.png

Inputs: draft2/narration.md (via draft2/build/timing.json), draft2/config.yaml,
assets/collage/ (harvested art), hero images in assets/stills + assets/public_domain.
Style: style/collage_style_prompt.md
"""
import json
import math
import random
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
D2 = ROOT / "draft2"
CFG = yaml.safe_load((D2 / "config.yaml").read_text())
TIMING = json.loads((D2 / "build" / "timing.json").read_text())
CUTSPEC = yaml.safe_load((ROOT / "assets" / "cutouts.yaml").read_text(encoding="utf-8"))
CREDITS = json.loads((D2 / "collage_credits.json").read_text())
_EXCL = D2 / "collage_exclude.txt"
if _EXCL.exists():
    for _l in _EXCL.read_text().splitlines():
        _k = _l.split("#")[0].strip()
        CREDITS.pop(_k, None)
Image.MAX_IMAGE_PIXELS = None


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease_out_quint(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 5


def ease_io(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


# ── time references (same syntax as draft 1) ────────────────
def T(ref):
    if isinstance(ref, (int, float)):
        return float(ref)
    m = re.fullmatch(r"s(\d+)(?:\.(\d+))?(e)?(?:@([\d.]+))?([+-][\d.]+)?", str(ref))
    if not m:
        return float(ref)
    sec = next(s for s in TIMING["sections"] if s["id"] == int(m.group(1)))
    a, b = (sec["lines"][int(m.group(2)) - 1]["start"], sec["lines"][int(m.group(2)) - 1]["end"]) if m.group(2) else (sec["start"], sec["end"])
    t = b if m.group(3) else a
    if m.group(4):
        t = a + (b - a) * float(m.group(4))
    if m.group(5):
        t += float(m.group(5))
    return t


# ── fonts ───────────────────────────────────────────────────
@lru_cache(maxsize=32)
def font(kind, px):
    F = CFG["fonts"]
    path = {"r": F["body"], "b": F["body"], "i": F["body_italic"], "t": F["title"], "ti": F["title_italic"]}[kind]
    f = ImageFont.truetype(str(ROOT / path), int(px))
    try:
        if kind == "b":
            f.set_variation_by_name("Bold")
        elif kind in ("r", "i"):
            f.set_variation_by_name("Regular")
    except Exception:
        pass
    return f


def tokens(line):
    """→ list of (word, style) with style r/b/i; a line wrapped in single *…* is italic."""
    s = line.strip()
    italic = bool(re.fullmatch(r"\*[^*].*[^*]\*", s))
    if italic:
        s = s[1:-1]
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*)", s):
        if not part:
            continue
        st = "b" if part.startswith("**") else ("i" if italic else "r")
        for w in part.strip("*").split():
            out.append((w, st))
    # glue leading punctuation (e.g. "." after a bold word) onto the previous token: no space
    glued = []
    for w, st in out:
        if glued and re.fullmatch(r"[.,;:!?…’”)\]]+", w):
            pw, pst = glued[-1]
            glued[-1] = (pw + "\x00" + w, pst + st)   # mixed-style token, split when drawing
        else:
            glued.append((w, st))
    return glued


class Renderer:
    def __init__(self, mode):
        o = CFG["output"][mode]
        self.mode = mode
        self.W, self.H, self.fps = o["width"], o["height"], o["fps"]
        self.S = self.W / 1080
        self.dur = TIMING["duration"]
        self.rng = random.Random(CFG["collage"]["seed"])
        self.secs = TIMING["sections"]
        self.first_line = self.secs[0]["lines"][0]["start"]
        self._img_cache = {}
        self.build_text()
        self.build_tags()
        self.build_title()
        self.build_schedule()
        self.vignette = self.make_vignette()
        self.reset_canvas()

    # ── text column ─────────────────────────────────────────
    def build_text(self):
        tc, W, H = CFG["text"], self.W, self.H
        px = tc["size_w"] * W
        self.font_px = px
        maxw = tc["max_width_w"] * W - 2 * tc["pad_x_w"] * W
        strip_h = int(tc["strip_h_em"] * px)
        gap = tc["gap_h"] * H
        self.lines = []          # dicts: sec, y_rel, x, t0, img
        rng = random.Random(5)
        for si, s in enumerate(self.secs):
            y = 0.0
            for pi, ln in enumerate(s["lines"]):
                toks = tokens(ln["text"])
                rows, cur, curw = [], [], 0.0
                for w, st in toks:
                    ww = sum(font(s[:1] if i == 0 else (s[1:2] or "r"), px).getlength(x) for i, (x, s) in enumerate(zip(w.split("\x00"), [st, st]))) + font("r", px).getlength(" ")
                    if cur and curw + ww > maxw:
                        rows.append(cur)
                        cur, curw = [], 0.0
                    cur.append((w, st))
                    curw += ww
                if cur:
                    rows.append(cur)
                total = sum(len(" ".join(w.replace("\x00", "") for w, _ in r)) for r in rows)
                x0 = rng.uniform(*tc["left_x_w"]) * W
                acc = 0
                if pi:
                    y += tc["para_gap_h"] * H
                for r in rows:
                    t0 = ln["start"] + (ln["end"] - ln["start"]) * acc / max(1, total) - 0.05
                    acc += len(" ".join(w.replace("\x00", "") for w, _ in r)) + 1
                    self.lines.append({"sec": si, "y_rel": y, "x": x0, "t0": t0, "img": self.render_strip(r, strip_h)})
                    y += strip_h + gap
        # scroll events per section
        top, bottom = tc["column_top_h"] * H, tc["column_bottom_h"] * H
        self.scrolls = {si: [] for si in range(len(self.secs))}
        for si in range(len(self.secs)):
            off = 0.0
            for L in [l for l in self.lines if l["sec"] == si]:
                need = top + L["y_rel"] + L["img"].height - bottom
                if need > off:
                    self.scrolls[si].append((L["t0"] - 0.05, need - off))
                    off = need
        self.col_top = top

    def render_strip(self, row, strip_h):
        tc = CFG["text"]
        px = self.font_px
        pad = int(tc["pad_x_w"] * self.W)
        def seg(w, st):   # mixed tokens: "word\x00." with styles "br"
            if "\x00" in w:
                a, b = w.split("\x00")
                return [(a, st[0]), (b, st[1:2] or "r")]
            return [(w, st)]
        widths = [sum(font(s, px).getlength(x) for x, s in seg(w, st)) for w, st in row]
        space = font("r", px).getlength(" ")
        tw = sum(widths) + space * (len(row) - 1)
        im = Image.new("RGBA", (int(tw + 2 * pad), strip_h), hexrgb(CFG["colors"]["strip"]) + (255,))
        d = ImageDraw.Draw(im)
        x = pad
        ink = hexrgb(CFG["colors"]["ink"]) + (255,)
        for (w, st), ww in zip(row, widths):
            xx = x
            for txt, s in seg(w, st):
                d.text((xx, strip_h * 0.52), txt, font=font(s, px), fill=ink, anchor="lm")
                xx += font(s, px).getlength(txt)
            x += ww + space
        return im

    def text_offset(self, si, t):
        off = sum(d * ease_io((t - ts) / CFG["text"]["scroll_s"]) for ts, d in self.scrolls[si] if t > ts)
        # clear the column when the next section starts
        if si + 1 < len(self.secs):
            tn = self.secs[si + 1]["start"] - CFG["text"]["section_clear_s"] - 0.1
            if t > tn:
                off += self.H * ease_io((t - tn) / CFG["text"]["section_clear_s"])
        return off

    def draw_text(self, frame, t):
        rv = CFG["text"]["reveal_s"]
        for L in self.lines:
            if t < L["t0"]:
                continue
            y = self.col_top + L["y_rel"] - self.text_offset(L["sec"], t)
            if y > self.H or y + L["img"].height < 0:
                continue
            r = ease_out_quint((t - L["t0"]) / rv)
            im = L["img"]
            if r < 1:
                im = im.crop((0, 0, max(1, int(im.width * r)), im.height))
            self.paste(frame, im, int(L["x"]), int(y))

    # ── header tags ─────────────────────────────────────────
    def tag_img(self, text, bold=False, dark=False):
        g = CFG["tags"]
        px = g["size_w"] * self.W
        f = font("b" if bold else "r", px)
        pad = int(0.04 * self.W)
        h = int(px * 1.9)
        w = int(f.getlength(text) + 2 * pad)
        bg = hexrgb(CFG["colors"]["end_tag_bg"] if dark else CFG["colors"]["strip"])
        ink = hexrgb(CFG["colors"]["end_tag_ink"] if dark else CFG["colors"]["ink"])
        im = Image.new("RGBA", (w, h), bg + (255,))
        ImageDraw.Draw(im).text((pad, h * 0.52), text, font=f, fill=ink + (255,), anchor="lm")
        return im

    def build_tags(self):
        self.tag_series = self.tag_img(CFG["tags"]["series"], bold=True)
        self.tag_secs = [self.tag_img(s["tag"]) for s in self.secs]
        self.tag_end = self.tag_img(CFG["tags"]["end_text"], dark=True)
        self.end_t = self.secs[-1]["end"] + 1.2

    def draw_tags(self, frame, t):
        y = int(CFG["tags"]["y_h"] * self.H)
        self.paste(frame, self.tag_series, 0, y)
        x = int(CFG["tags"]["right_x_w"] * self.W)
        if t >= self.end_t:
            self.paste(frame, self.tag_end, x, y)
            return
        si = max([i for i, s in enumerate(self.secs) if s["start"] - 0.6 <= t] or [0])
        im = self.tag_secs[si]
        k = ease_out_quint((t - (self.secs[si]["start"] - 0.6)) / 0.3) if si else 1
        if k < 1:
            im = im.crop((0, 0, max(1, int(im.width * k)), im.height))
        self.paste(frame, im, x, y)

    # ── title card ──────────────────────────────────────────
    def resolve_image_id(self, spec):
        if str(spec).startswith("query:"):
            q = spec.split(":", 1)[1]
            hits = [k for k, v in CREDITS.items() if v.get("query") == q]
            return hits[0] if hits else next(iter(CREDITS))
        return spec

    def build_title(self):
        tcfg = CFG["title"]
        self.title_id = self.resolve_image_id(tcfg["image"])
        x0, y0, x1, y1 = tcfg["box"]
        W, H = self.W, self.H
        box = Image.new("RGBA", (int((x1 - x0) * W), int((y1 - y0) * H)), hexrgb(CFG["colors"]["strip"]) + (255,))
        d = ImageDraw.Draw(box)
        px = tcfg["size_w"] * W
        ink = hexrgb(CFG["colors"]["ink"]) + (255,)
        y = int(0.07 * box.height)
        for line in (tcfg["line1"], tcfg["line2"]):
            x = int(0.09 * box.width)
            for part in re.split(r"(\*[^*]+\*)", line):
                if not part:
                    continue
                f = font("ti" if part.startswith("*") else "t", px)
                txt = part.strip("*")
                d.text((x, y), txt, font=f, fill=ink)
                x += f.getlength(txt)
            y += int(px * 1.02)
        fs = font("i", 0.034 * W)
        # wrap subtitle
        words, rows, cur = tcfg["subtitle"].split(), [], ""
        for w in words:
            if fs.getlength(cur + " " + w) > box.width * 0.84 and cur:
                rows.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        rows.append(cur)
        y += int(px * 0.18)
        for r in rows:
            d.text((int(0.09 * box.width), y), r, font=fs, fill=ink)
            y += int(0.034 * W * 1.3)
        self.title_box = box
        self.title_xy = (int(x0 * W), int(y0 * H))

    # ── images & pieces ─────────────────────────────────────
    def load_img(self, key, path, mask=None):
        if key in self._img_cache:
            return self._img_cache[key]
        im = Image.open(path)
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((1500, 1500), Image.LANCZOS)
        g = CFG["collage"]["grade"]
        im = ImageEnhance.Color(im).enhance(1 - g["desaturate"])
        im = ImageEnhance.Contrast(im).enhance(g["contrast"])
        a = np.asarray(im, np.float32)
        a = a * np.array([1 + g["warm"], 1.0, 1 - g["warm"]], np.float32) * g["darken"]
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        self._img_cache[key] = im
        return im

    def hero_source(self, hid):
        """Return (RGBA image, is_figure) for a hero id, mirroring tools/make_cutouts.py crops."""
        spec = CUTSPEC.get(hid) or {}
        src = None
        for d in ("stills", "public_domain"):
            hits = [p for p in sorted((ROOT / "assets" / d).glob(f"{hid}.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
            if hits:
                src = hits[0]
                break
        if src is None:
            return None, False
        key = f"hero::{hid}"
        if key in self._img_cache:
            return self._img_cache[key]
        im = ImageOps.exif_transpose(Image.open(src))
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA")
        if "crop" in spec:
            x0, y0, x1, y1 = spec["crop"]
            w, h = im.size
            im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        if max(im.size) > 1600:
            im.thumbnail((1600, 1600), Image.LANCZOS)
        if im.height < spec.get("min_h", 760):
            f = spec.get("min_h", 760) / im.height
            im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
        mode = spec.get("mode", "card")
        figure = False
        if mode in ("rembg", "alpha"):
            mp = ROOT / "build" / "masks" / f"{hid}.png"
            alpha = None
            if mode == "alpha" and has_alpha:
                alpha = im.getchannel("A")
            elif mp.exists():
                m = Image.open(mp).convert("L")
                if m.size == im.size:
                    alpha = m
            if alpha is not None:
                alpha = alpha.point(lambda v: 255 if v > 110 else 0).filter(ImageFilter.MedianFilter(5))
                bbox = alpha.getbbox()
                im.putalpha(alpha)
                if bbox:
                    im = im.crop(bbox)
                figure = True
        if spec.get("grey"):
            a = im.getchannel("A")
            im = ImageOps.grayscale(im.convert("RGB")).convert("RGBA")
            im.putalpha(a)
        g = CFG["collage"]["grade"]
        rgb = ImageEnhance.Color(im.convert("RGB")).enhance(1 - g["desaturate"] * 0.6)
        a = im.getchannel("A")
        im = rgb.convert("RGBA")
        im.putalpha(a)
        self._img_cache[key] = (im, figure)
        return im, figure

    def cut_mask(self, w, h, style, rng):
        m = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(m)
        if style == "rect":
            d.rectangle([0, 0, w - 1, h - 1], fill=255)
        elif style == "poly":
            n = rng.randint(5, 9)
            pts = []
            for i in range(n):
                a = 2 * math.pi * i / n + rng.uniform(-0.25, 0.25)
                # points on a rectangle-ish boundary, pulled inward a little
                cx, cy = math.cos(a), math.sin(a)
                k = 1 / max(abs(cx), abs(cy))
                px = (0.5 + 0.5 * cx * k * rng.uniform(0.82, 1.0)) * (w - 1)
                py = (0.5 + 0.5 * cy * k * rng.uniform(0.82, 1.0)) * (h - 1)
                pts.append((px, py))
            d.polygon(pts, fill=255)
        else:  # torn
            j = max(2, int(0.012 * max(w, h)))
            pts = []
            steps = 28
            for i in range(steps):
                pts.append((i / steps * w, rng.uniform(0, j)))
            for i in range(steps):
                pts.append((w - rng.uniform(0, j), i / steps * h))
            for i in range(steps):
                pts.append((w - i / steps * w, h - rng.uniform(0, j)))
            for i in range(steps):
                pts.append((rng.uniform(0, j), h - i / steps * h))
            d.polygon(pts, fill=255)
        return m

    def make_piece(self, ev):
        """Build the RGBA image for a scheduled piece (lazy)."""
        if "img" in ev:
            return ev["img"]
        rng = random.Random(ev["seed"])
        W = self.W
        c = CFG["collage"]
        if ev["kind"] == "swatch":
            w = int(ev["w"])
            h = int(w * rng.uniform(0.5, 1.4))
            col = hexrgb(ev["color"])
            im = Image.new("RGB", (w, h), col)
            if sum(col) < 200 and rng.random() < 0.6:   # starfield on dark swatches
                d = ImageDraw.Draw(im)
                for _ in range(int(w * h / 900)):
                    x, y = rng.uniform(0, w), rng.uniform(0, h)
                    r = rng.choice([0.6, 0.8, 1.0, 1.2, 1.8]) * self.S * 1.4
                    v = rng.randint(150, 255)
                    d.ellipse([x - r, y - r, x + r, y + r], fill=(v, v, int(v * 0.92)))
            noise = np.random.default_rng(ev["seed"]).normal(0, 6, (h, w, 1))
            im = Image.fromarray(np.clip(np.asarray(im, np.float32) + noise, 0, 255).astype(np.uint8))
            mask = self.cut_mask(w, h, ev["cut"], rng)
            out = im.convert("RGBA")
            out.putalpha(mask)
        elif ev["kind"] == "hero":
            src, figure = self.hero_source(ev["id"])
            if src is None:
                ev["img"] = None
                return None
            w = int(ev["w"])
            h = int(src.height * w / src.width)
            if h > 0.62 * self.H:
                h = int(0.62 * self.H)
                w = int(src.width * h / src.height)
            out = src.resize((max(2, w), max(2, h)), Image.LANCZOS)
            if not figure:
                mask = self.cut_mask(out.width, out.height, ev["cut"] if ev["cut"] != "torn" else "rect", rng)
                out.putalpha(mask)
        else:
            path = ROOT / CREDITS[ev["id"]]["local"]
            src = self.load_img(ev["id"], path)
            sw, sh = src.size
            area = rng.uniform(0.35, 1.0)
            asp = rng.uniform(0.6, 1.7)
            cw = min(sw, int(math.sqrt(area * sw * sh * asp)))
            ch = min(sh, int(cw / asp))
            x0 = rng.randint(0, max(0, sw - cw))
            y0 = rng.randint(0, max(0, sh - ch))
            crop = src.crop((x0, y0, x0 + cw, y0 + ch))
            w = int(ev["w"])
            h = int(ch * w / max(1, cw))
            out = crop.resize((max(2, w), max(2, h)), Image.LANCZOS).convert("RGBA")
            out.putalpha(self.cut_mask(out.width, out.height, ev["cut"], rng))
            if ev["cut"] == "torn":   # light paper fringe
                fr = out.getchannel("A").filter(ImageFilter.MaxFilter(5))
                base = Image.new("RGBA", out.size, (238, 232, 218, 255))
                base.putalpha(fr)
                base.alpha_composite(out)
                out = base
        if out is not None and abs(ev["rot"]) > 0.1:
            out = out.rotate(ev["rot"], resample=Image.BICUBIC, expand=True)
        ev["img"] = out
        return out

    def build_schedule(self):
        c = CFG["collage"]
        rng = self.rng
        W, H = self.W, self.H
        by_theme = {}
        for k, v in CREDITS.items():
            for th in v.get("themes", []):
                by_theme.setdefault(th, []).append(k)
        all_ids = list(CREDITS)
        events = []

        def sec_at(t):
            return max([s for s in self.secs if s["start"] - 0.5 <= t] or [self.secs[0]], key=lambda s: s["start"])

        # ambient clusters
        t = self.first_line - 0.6
        while t < self.dur - 1.0:
            n = rng.randint(*c["cluster"])
            for _ in range(n):
                s = sec_at(t)
                ev = {"t": t, "seed": rng.randint(0, 10 ** 9), "rot": rng.uniform(-c["rotation_deg"], c["rotation_deg"])}
                r = rng.random()
                if r < c["swatch_share"]:
                    ev.update(kind="swatch", color=rng.choice(c["swatches"]), w=rng.uniform(0.25, 0.55) * W)
                else:
                    themes = CFG["themes"].get(s["id"], CFG["themes"].get(str(s["id"]), []))
                    pool = [i for th in themes for i in by_theme.get(th, [])]
                    pid = rng.choice(pool) if pool and rng.random() < c["relevance"] * 1.6 else rng.choice(all_ids)
                    ev.update(kind="art", id=pid, w=rng.uniform(*c["size_w"]) * W)
                ev["cut"] = rng.choices(list(c["cut_mix"]), weights=list(c["cut_mix"].values()))[0]
                events.append(ev)
                t += rng.uniform(0.12, 0.3)
            t += rng.expovariate(1 / (c["mean_gap_s"] * (sum(c["cluster"]) / 2)))
        # hero pieces
        for s in self.secs:
            ids = CFG["heroes"].get(s["id"], CFG["heroes"].get(str(s["id"]), []))
            if not ids:
                continue
            if s["id"] == len(self.secs):     # finale: accelerating cascade of faces
                a, b = s["lines"][2]["start"] - 0.2, s["lines"][min(5, len(s["lines"]) - 1)]["end"]
                tt, k = a, 0
                while tt < b:
                    hid = ids[k % len(ids)]
                    frac = (tt - a) / max(0.1, b - a)
                    gap = max(c["finale_rate_s"], 0.9 * (1 - frac) + c["finale_rate_s"] * frac)
                    events.append({"t": tt, "kind": "hero", "id": hid, "seed": rng.randint(0, 10 ** 9),
                                   "w": rng.uniform(0.32, 0.6) * W, "rot": rng.uniform(-4, 4), "cut": "rect", "anywhere": True})
                    tt += gap
                    k += 1
                ids = ids[:1]
            span = (s["end"] - s["start"]) * 0.82
            reps = min(len(ids) * 2, max(len(ids), int((s["end"] - s["start"]) / 9.0)))   # roughly every 9 s, each image at most twice
            ids = [ids[i % len(ids)] for i in range(reps)]
            for i, hid in enumerate(ids):
                tt = s["start"] - 0.25 + (span * i / max(1, len(ids)))
                events.append({"t": tt, "kind": "hero", "id": hid, "seed": rng.randint(0, 10 ** 9),
                               "w": rng.uniform(*c["hero_size_w"]) * W, "rot": rng.uniform(-2.5, 2.5),
                               "cut": rng.choice(["rect", "poly"])})
        events.sort(key=lambda e: e["t"])
        # placement: cover the stalest area; heroes biased to the lower band
        grid = np.full((16, 9), -99.0)
        protect = []     # (t_until, x0, y0, x1, y1) zones kept clear around recent hero pieces
        for ev in events:
            ev["dur"] = rng.uniform(*c["slide_s"])
            best, score = None, -1e9
            for _ in range(24):
                if ev["kind"] == "hero" and not ev.get("anywhere"):
                    x = rng.uniform(0.25, 0.75)
                    y = rng.uniform(0.70, 0.86)
                else:
                    x, y = rng.uniform(0.05, 0.95), rng.uniform(0.05, 0.95)
                gx, gy = int(x * 8.99), int(y * 15.99)
                r = max(1, int(ev["w"] / W * 4))
                cells = grid[max(0, gy - r):gy + r + 1, max(0, gx - r):gx + r + 1]
                sc = -cells.mean() + rng.uniform(0, 0.5)
                if ev["kind"] != "hero":
                    hw = ev["w"] / W / 2
                    for (tu, zx0, zy0, zx1, zy1) in protect:
                        if ev["t"] < tu and not (x + hw < zx0 or x - hw > zx1 or y + hw < zy0 or y - hw > zy1):
                            sc -= 1000
                if sc > score:
                    best, score = (x, y), sc
            ev["x"], ev["y"] = best
            if ev["kind"] == "hero" and not ev.get("anywhere"):
                hw = ev["w"] / W / 2 * 0.8
                protect.append((ev["t"] + 8.0, best[0] - hw, best[1] - hw * 1.2, best[0] + hw, best[1] + hw * 1.2))
            gx, gy = int(best[0] * 8.99), int(best[1] * 15.99)
            r = max(1, int(ev["w"] / W * 4))
            grid[max(0, gy - r):gy + r + 1, max(0, gx - r):gx + r + 1] = ev["t"]
            # slide in from the nearest edge
            dists = {"l": best[0], "r": 1 - best[0], "t": best[1], "b": 1 - best[1]}
            ev["edge"] = min(dists, key=dists.get) if rng.random() < 0.8 else rng.choice("lrtb")
            ev["cut_in"] = rng.random() < 0.12
        self.events = events

    # ── canvas ──────────────────────────────────────────────
    def make_vignette(self):
        g = CFG["collage"]["grade"]["vignette"]
        yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
        r = np.sqrt(((xx - self.W / 2) / (self.W / 2)) ** 2 + ((yy - self.H / 2) / (self.H / 2)) ** 2)
        return (1 - g * np.clip(r - 0.45, 0, 1) ** 1.6)[..., None]

    def reset_canvas(self):
        src = self.load_img("title::" + self.title_id, ROOT / CREDITS[self.title_id]["local"])
        self.canvas = ImageOps.fit(src, (self.W, self.H), Image.LANCZOS, centering=(0.5, 0.35)).convert("RGBA")
        self.baked = 0
        self.last_t = -1

    def piece_pos(self, ev, t):
        im = ev["img"]
        x = ev["x"] * self.W - im.width / 2
        y = ev["y"] * self.H - im.height / 2
        if ev["cut_in"]:
            return x, y
        k = 1 - ease_out_quint((t - ev["t"]) / ev["dur"])
        if ev["edge"] == "l":
            x -= k * (x + im.width + 20)
        elif ev["edge"] == "r":
            x += k * (self.W - x + 20)
        elif ev["edge"] == "t":
            y -= k * (y + im.height + 20)
        else:
            y += k * (self.H - y + 20)
        return x, y

    def frame(self, t):
        if t < self.last_t:
            self.reset_canvas()
        self.last_t = t
        # bake every piece that has landed, in order
        while self.baked < len(self.events):
            ev = self.events[self.baked]
            if ev["t"] + (0 if ev.get("cut_in") else ev["dur"]) > t:
                break
            im = self.make_piece(ev)
            if im is not None:
                x, y = self.piece_pos(ev, ev["t"] + ev["dur"] + 1)
                self.paste(self.canvas, im, int(x), int(y))
            self.baked += 1
        frame = self.canvas.copy()
        for ev in self.events[self.baked:]:
            if ev["t"] > t:
                break
            im = self.make_piece(ev)
            if im is None:
                continue
            x, y = self.piece_pos(ev, t)
            self.paste(frame, im, int(x), int(y))
        rgb = (np.asarray(frame.convert("RGB"), np.float32) * self.vignette).astype(np.uint8)
        frame = Image.fromarray(rgb).convert("RGBA")
        # title card
        if t < self.first_line - 0.05:
            frame.alpha_composite(self.title_box, self.title_xy)
        else:
            self.draw_text(frame, t)
        self.draw_tags(frame, t)
        return np.asarray(frame.convert("RGB"))

    def paste(self, frame, im, x, y):
        if x >= frame.width or y >= frame.height or x + im.width <= 0 or y + im.height <= 0:
            return
        frame.alpha_composite(im, (max(0, x), max(0, y)),
                              (max(0, -x), max(0, -y), min(im.width, frame.width - x), min(im.height, frame.height - y)))


def mix_audio(out_wav):
    vo_user = ROOT / "assets" / "voiceover_draft2.wav"
    vo = vo_user if vo_user.exists() else D2 / "build" / "vo.wav"
    m = CFG["music"]
    music = ROOT / m["file"]
    dur = TIMING["duration"]
    if not music.exists() and m.get("placeholder_drone"):
        music = D2 / "build" / "drone.wav"
        if not music.exists():
            subprocess.run([sys.executable, str(ROOT / "tools" / "make_drone.py"), str(dur + 1), str(music)], check=True)
    if not music.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vo), "-af",
                        f"aresample=48000,pan=stereo|c0=c0|c1=c0,apad,atrim=0:{dur},loudnorm=I=-15:TP=-1.5:LRA=11,aresample=48000",
                        str(out_wav)], check=True)
        return
    parts = [f"between(t,{ln['start'] - m['duck_attack']:.2f},{ln['end'] + m['duck_release']:.2f})"
             for s in TIMING["sections"] for ln in s["lines"]]
    duck = 10 ** (-m["duck_db"] / 20)
    base = 10 ** (m["level_db"] / 20)
    fc = (f"[1:a]aresample=48000,aloop=loop=-1:size=2e9,atrim=0:{dur},volume={base:.4f},"
          f"volume='if({'+'.join(parts)},{duck:.4f},1)':eval=frame,afade=t=in:d=2,afade=t=out:st={dur - 4:.2f}:d=4[mus];"
          f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,apad[v];[v][mus]amix=inputs=2:duration=longest:normalize=0,"
          f"atrim=0:{dur},loudnorm=I=-15:TP=-1.5:LRA=11,aresample=48000[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vo), "-i", str(music), "-filter_complex", fc,
                    "-map", "[a]", str(out_wav)], check=True)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    if mode == "still":
        R = Renderer("final")
        for ts in sorted(sys.argv[2:], key=T):
            out = D2 / "build" / f"still_{ts}.png"
            Image.fromarray(R.frame(T(ts))).save(out)
            print(out.relative_to(ROOT), f"t={T(ts):.2f}")
        return
    from moviepy.editor import AudioFileClip, VideoClip
    R = Renderer(mode)
    wav = D2 / "build" / "mix.wav"
    mix_audio(wav)
    o = CFG["output"][mode]
    out = ROOT / o["file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    VideoClip(R.frame, duration=R.dur).set_audio(AudioFileClip(str(wav))).write_videofile(
        str(out), fps=R.fps, codec="libx264", audio_codec="aac", audio_bitrate="192k", preset=o["preset"],
        ffmpeg_params=["-crf", str(o["crf"]), "-pix_fmt", "yuv420p", "-movflags", "+faststart"], threads=4, logger=None)
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
