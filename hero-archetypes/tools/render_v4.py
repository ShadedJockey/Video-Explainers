"""Draft 4 renderer: "The Hero With Infinite Faces", 3-minute TikTok cut (1080×1920).

    python tools/render_v4.py preview              → draft4/build/preview_540x960.mp4
    python tools/render_v4.py final                → final/hero_infinite_faces_v4_vertical.mp4
    python tools/render_v4.py still [--safe] s3.4@0.8 …   → draft4/build/still_<ref>.png

Layout (1080×1920): header tags at y 230 · narration strips y 300–900 · stage (pictures, panels, maps) y 930–1430.
Everything below 1440, above 220 and right of 940 is background only (TikTok covers it).
Script: draft4/narration.md · stage: draft4/scenes.yaml · settings: draft4/config.yaml
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
D4 = ROOT / "draft4"
CFG = yaml.safe_load((D4 / "config.yaml").read_text())
TIMING = json.loads((D4 / "build" / "timing.json").read_text())
SCENES = yaml.safe_load((D4 / "scenes.yaml").read_text())
CUTSPEC = yaml.safe_load((ROOT / "assets" / "cutouts.yaml").read_text(encoding="utf-8"))
Image.MAX_IMAGE_PIXELS = None
SECS = TIMING["sections"]
DUR = TIMING["duration"]
MISSING = set()
RELIGIOUS = re.compile(
    r"\b(angel\w*|saint|st\.|christ\w*|jesus|madonna|virgin|gods?|goddess|heaven\w*|paradise|paradiso|church|cathedral|bible|biblical|"
    r"apostle|crucif\w*|resurrect\w*|holy|divine|prophet|moses|lucifer|devil|demon\w*|hell|inferno|purgatory|psalm|gospel|monk|nun|"
    r"bishop|pope|temple|buddha\w*|bodhisattva|shiva|vishnu|krishna|deity|deities|altar|sacred|relig\w*|prayer|annunciation|nativity|"
    r"trinity|baptism|cross|crucifix|cherub\w*|seraph\w*|soul|spirit\w*|zodiac|astrolog\w*|alchem\w*|kabbal\w*|tarot|rosicruc\w*|"
    r"mystic\w*|occult|hermetic|shaman\w*|rosary|funerary|mummy|tomb|death|skull\w*|skeleton|races|slave|mask\w*|masquerade|egungun|ritual\w*|ceremon\w*|idol\w*|reliquar\w*|goddess\w*|eve|adam|noah|ark|abraham|isaac|jacob|solomon|judith|samson|jonah|magi|lord|rama|sita|lakshmana|ravana|ramayana|mahabharata|hanuman|ganesh\w*|durga|garuda|hindu|buddhist|jain|jina|tirthankara|avalokiteshvara|kannon|amida|arhat|lohan|tara|jerusalem|teotihuacan|olmec|aztec|faun|satyr|nymph\w*|venus|jupiter|zeus|apollo|minerva|mars|bacchus|cupid|psyche|mercury|neptune|pluto|diana|juno|vulcan|hercules|herakles|mythological|allegor\w*)\b", re.I)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x, p=3):
    x = clamp(x)
    return 1 - (1 - x) ** p


def ease_in(x):
    x = clamp(x)
    return x * x * x


# ── time references ─────────────────────────────────────────
def sec(i):
    return next(s for s in SECS if s["id"] == i)


def T(ref):
    if isinstance(ref, (int, float)):
        return float(ref)
    ref = str(ref).strip()
    m = re.fullmatch(r"end([+-][\d.]+)?", ref)
    if m:
        return DUR + float(m.group(1) or 0)
    m = re.fullmatch(r"s(\d+)(?:\.(\d+))?(e)?(?:@([\d.]+))?([+-][\d.]+)?", ref)
    if not m:
        return float(ref)
    s = sec(int(m.group(1)))
    if m.group(2):
        ln = s["lines"][int(m.group(2)) - 1]
        a, b = ln["start"], ln["end"]
    else:
        a, b = s["start"], s["end"]
    t = b if m.group(3) else a
    if m.group(4):
        t = a + (b - a) * float(m.group(4))
    if m.group(5):
        t += float(m.group(5))
    return t


def section_at(t):
    cur = SECS[0]["id"]
    for s in SECS:
        if t >= s["start"] - 0.65:
            cur = s["id"]
    return cur


# ── pools ───────────────────────────────────────────────────
def load_pools():
    allp = {}
    for p in CFG["collage"]["pools"]:
        f = ROOT / p
        if f.exists():
            for k, v in json.loads(f.read_text()).items():
                if (ROOT / v["local"]).exists():
                    allp[k] = v
    pool = dict(allp)
    for p in CFG["collage"]["exclude"]:
        f = ROOT / p
        if f.exists():
            for line in f.read_text().splitlines():
                pool.pop(line.split("#")[0].strip(), None)
    drop = set(CFG["collage"]["drop_themes"])
    pool = {k: v for k, v in pool.items() if not (set(v.get("themes", [])) & drop) and not RELIGIOUS.search(v.get("title", "") + " " + v.get("query", ""))}
    return allp, pool


ALLPOOL, POOL = load_pools()
BY_THEME = {}
for _k, _v in POOL.items():
    for _th in _v.get("themes", []):
        BY_THEME.setdefault(_th, []).append(_k)


# ── fonts & text tokens (same conventions as drafts 2–3) ────
@lru_cache(maxsize=64)
def font(kind, px):
    F = CFG["fonts"]
    path = {"r": F["body"], "b": F["body"], "i": F["body_italic"], "bi": F["body_italic"], "t": F["title"], "ti": F["title_italic"]}[kind]
    f = ImageFont.truetype(str(ROOT / path), int(px))
    try:
        f.set_variation_by_name("Bold" if kind in ("b", "bi") else ("Medium" if kind == "m" else "Regular"))
    except Exception:
        pass
    return f


def tokens(line):
    s = line.strip()
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", s):
        if not part:
            continue
        st = "b" if part.startswith("**") else ("i" if part.startswith("*") else "r")
        for w in part.strip("*").split():
            out.append((w, st))
    glued = []
    for w, st in out:
        if glued and re.fullmatch(r"[.,;:!?…’”)\]]+", w):
            pw, pst = glued[-1]
            glued[-1] = (pw + "\x00" + w, pst + "|" + st)
        else:
            glued.append((w, st))
    return glued


def segs(w, st):
    if "\x00" in w:
        a, b = w.split("\x00")
        s1, s2 = st.split("|")
        return [(a, s1), (b, s2)]
    return [(w, st)]


def text_width(row, px):
    sp = font("r", px).getlength(" ")
    return sum(sum(font(s, px).getlength(x) for x, s in segs(w, st)) for w, st in row) + sp * (len(row) - 1)


def wrap(toks, px, maxw):
    rows, cur = [], []
    for tok in toks:
        if cur and text_width(cur + [tok], px) > maxw:
            rows.append(cur)
            cur = []
        cur.append(tok)
    if cur:
        rows.append(cur)
    return rows


def draw_row(d, x, y, row, px, fill):
    sp = font("r", px).getlength(" ")
    for w, st in row:
        for txt, s in segs(w, st):
            d.text((x, y), txt, font=font(s, px), fill=fill, anchor="lm")
            x += font(s, px).getlength(txt)
        x += sp


# ── renderer ────────────────────────────────────────────────
class Renderer:
    def __init__(self, mode):
        o = CFG["output"][mode]
        self.W, self.H, self.fps = o["width"], o["height"], o["fps"]
        self.S = self.W / 1080
        S = self.S
        L = CFG["layout"]
        self.sx0, self.sx1 = L["text_x"][0] * S, L["text_x"][1] * S
        self.sy0, self.sy1 = L["stage"][0] * S, L["stage"][1] * S
        self.scx = (self.sx0 + self.sx1) / 2
        self.C = {k: hexrgb(v) for k, v in CFG["colors"].items()}
        self._img = {}
        self._canvas = None
        self._snap = {}
        self._vig = {}
        self.title_end = T("s1.1") - 0.25
        self.endcard = DUR - CFG["voice"]["tail"] + 0.35
        self.sfx = []                 # times of picture landings, for foley
        self.build_collage()
        self.build_text()
        self.build_tags()
        self.build_stage()
        self.build_cards()

    # ── image sources ───────────────────────────────────────
    def src_image(self, src):
        """→ (RGBA image, is_rectangle)."""
        if src in self._img:
            return self._img[src]
        kind, val = src.split(":", 1)
        rect = True
        if kind == "file":
            im = Image.open(ROOT / val)
        elif kind == "pool":
            im = Image.open(ROOT / ALLPOOL[val]["local"])
        elif kind == "still":
            hits = [p for p in sorted((ROOT / "assets" / "stills").glob(f"{val}.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
            if not hits:
                MISSING.add(val)
                self._img[src] = (None, True)
                return self._img[src]
            im = Image.open(hits[0])
        elif kind == "hero":
            im = self.hero_source(val)
            rect = False
            if im is None:
                self._img[src] = (None, False)
                return self._img[src]
        else:
            raise ValueError(src)
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGBA") if not rect else im.convert("RGB").convert("RGBA")
        if max(im.size) > 1500:
            im.thumbnail((1500, 1500), Image.LANCZOS)
        self._img[src] = (im, rect)
        return self._img[src]

    def hero_source(self, hid):
        """Flat cut-out from assets/stills using the rembg masks in build/masks (as in drafts 2–3)."""
        spec = CUTSPEC.get(hid) or {}
        src = None
        for d in ("stills", "public_domain"):
            hits = [p for p in sorted((ROOT / "assets" / d).glob(f"{hid}.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
            if hits:
                src = hits[0]
                break
        if src is None:
            MISSING.add(hid)
            return None
        im = ImageOps.exif_transpose(Image.open(src))
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA")
        if "crop" in spec:
            x0, y0, x1, y1 = spec["crop"]
            w, h = im.size
            im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        alpha = None
        mp = ROOT / "build" / "masks" / f"{hid}.png"
        if spec.get("mode") == "alpha" and has_alpha:
            alpha = im.getchannel("A")
        elif mp.exists():
            m = Image.open(mp).convert("L")
            if m.size == im.size:
                alpha = m
        if alpha is None and has_alpha:
            alpha = im.getchannel("A")
        if alpha is not None:
            alpha = alpha.point(lambda v: 255 if v > 110 else 0).filter(ImageFilter.MedianFilter(5))
            bbox = alpha.getbbox()
            im.putalpha(alpha)
            if bbox:
                im = im.crop(bbox)
        return im

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
                cx, cy = math.cos(a), math.sin(a)
                k = 1 / max(abs(cx), abs(cy))
                pts.append(((0.5 + 0.5 * cx * k * rng.uniform(0.82, 1.0)) * (w - 1), (0.5 + 0.5 * cy * k * rng.uniform(0.82, 1.0)) * (h - 1)))
            d.polygon(pts, fill=255)
        else:
            j = max(2, int(0.012 * max(w, h)))
            pts = [(i / 28 * w, rng.uniform(0, j)) for i in range(28)] + [(w - rng.uniform(0, j), i / 28 * h) for i in range(28)]
            pts += [(w - i / 28 * w, h - rng.uniform(0, j)) for i in range(28)] + [(rng.uniform(0, j), h - i / 28 * h) for i in range(28)]
            d.polygon(pts, fill=255)
        return m

    def paste(self, frame, im, x, y, alpha=1.0):
        x, y = int(round(x)), int(round(y))
        if im is None or alpha <= 0.003 or x >= frame.width or y >= frame.height or x + im.width <= 0 or y + im.height <= 0:
            return
        if alpha < 0.997:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
        frame.alpha_composite(im, (max(0, x), max(0, y)), (max(0, -x), max(0, -y), min(im.width, frame.width - x), min(im.height, frame.height - y)))

    # ── labels, chips, cards ────────────────────────────────
    def label_img(self, title, sub=None, maxw=None):
        """Museum label: dark chip, italic title, smaller subtitle; words wrap to maxw instead of being cut."""
        S = self.S
        key = ("label", title, sub, maxw)
        if key in self._img:
            return self._img[key]
        ft, fs = font("i", 30 * S), font("r", 23 * S)
        pad = int(14 * S)
        limit = (maxw or 10 ** 6) - 2 * pad
        lines = []
        for text, f, col in ((title, ft, self.C["label_ink"]), (sub, fs, tuple(int(c * 0.8) for c in self.C["label_ink"]))):
            if not text:
                continue
            cur = ""
            for w in text.split():
                if cur and f.getlength(cur + " " + w) > limit:
                    lines.append((cur, f, col))
                    cur = w
                else:
                    cur = (cur + " " + w).strip()
            lines.append((cur, f, col))
        w = int(max(f.getlength(tx) for tx, f, _ in lines) + 2 * pad)
        h = int(pad * 1.6 + sum(f.size * 1.18 for _, f, _ in lines))
        im = Image.new("RGBA", (w, h), self.C["label_bg"] + (238,))
        d = ImageDraw.Draw(im)
        y = pad * 0.8
        for tx, f, col in lines:
            d.text((pad, y), tx, font=f, fill=col + (255,))
            y += f.size * 1.18
        self._img[key] = im
        return im

    def chip_img(self, text, style="paper", px=34):
        S = self.S
        key = ("chip", text, style, px)
        if key in self._img:
            return self._img[key]
        f = font("b" if style == "accent" else "r", px * S)
        pad = int(20 * S)
        h = int(px * S * 1.55)
        bg = self.C["accent"] if style == "accent" else self.C["strip"]
        ink = self.C["strip"] if style == "accent" else self.C["ink"]
        im = Image.new("RGBA", (int(f.getlength(text) + 2 * pad), h), bg + (255,))
        ImageDraw.Draw(im).text((pad, h * 0.52), text, font=f, fill=ink + (255,), anchor="lm")
        self._img[key] = im
        return im

    def picture(self, src, max_w, max_h, fill=False, rot=0.0):
        """Image fitted to a box; rectangles get a paper border and a soft shadow."""
        key = ("pic", src, int(max_w), int(max_h), fill, round(rot, 1))
        if key in self._img:
            return self._img[key]
        im, rect = self.src_image(src)
        if im is None:
            self._img[key] = None
            return None
        S = self.S
        b = int(6 * S) if rect else 0
        if fill:
            im = ImageOps.fit(im, (int(max_w - 2 * b), int(max_h - 2 * b)), Image.LANCZOS)
        else:
            im = ImageOps.contain(im, (int(max_w - 2 * b), int(max_h - 2 * b)), Image.LANCZOS)
        if rect:
            framed = Image.new("RGBA", (im.width + 2 * b, im.height + 2 * b), self.C["strip"] + (255,))
            framed.alpha_composite(im, (b, b))
            im = framed
        if rot:
            im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        sh_off = int(8 * S)
        out = Image.new("RGBA", (im.width + sh_off * 3, im.height + sh_off * 3), (0, 0, 0, 0))
        shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        shadow.putalpha(im.getchannel("A").point(lambda v: int(v * 0.55)))
        out.alpha_composite(shadow, (sh_off * 2, sh_off * 2))
        out = out.filter(ImageFilter.GaussianBlur(sh_off * 0.9)) if rect else out
        out.alpha_composite(im, (sh_off, sh_off))
        self._img[key] = (out, sh_off, im.width, im.height)
        return self._img[key]

    def card(self, item, max_w, max_h, fill=False, rot=0.0):
        """Picture with an optional museum label underneath → (image, image box (x, y, w, h) inside it)."""
        key = ("card", item.get("src"), item.get("label"), item.get("sub"), int(max_w), int(max_h), fill, round(rot, 1))
        if key in self._img:
            return self._img[key]
        pic = self.picture(item["src"], max_w, max_h, fill=fill, rot=rot)
        if pic is None:
            self._img[key] = (None, None)
            return self._img[key]
        im, off, iw, ih = pic
        lab = self.label_img(item.get("label"), item.get("sub"), maxw=max(iw + 30 * self.S, 300 * self.S)) if (item.get("label") or item.get("sub")) else None
        gap = int(8 * self.S)
        w = max(im.width, (lab.width + off) if lab else 0)
        h = im.height + ((lab.height + gap - off * 2) if lab else 0)
        out = Image.new("RGBA", (w, max(h, im.height)), (0, 0, 0, 0))
        px = (w - im.width) // 2
        out.alpha_composite(im, (px, 0))
        if lab:
            lx = px + off
            out.alpha_composite(lab, (min(lx, w - lab.width), off + ih + gap))
        self._img[key] = (out, (px + off, off, iw, ih))
        return self._img[key]

    # ── background collage ──────────────────────────────────
    def build_collage(self):
        c = CFG["collage"]
        rng = random.Random(c["seed"])
        W, H, S = self.W, self.H, self.S
        events = []
        t = 0.2
        while t < self.endcard:
            sid = section_at(t)
            themes = c["section_themes"].get(sid, [])
            cands = [k for th in themes for k in BY_THEME.get(th, [])] or list(POOL)
            pid = rng.choice(cands) if rng.random() < 0.8 else rng.choice(list(POOL))
            ev = {"t": t, "id": pid, "seed": rng.randint(0, 10 ** 9), "w": rng.uniform(*c["size_px"]) * S,
                  "rot": rng.uniform(-CFG["motion"]["rotation_deg"], CFG["motion"]["rotation_deg"]),
                  "cut": rng.choice(["rect", "rect", "poly", "torn"]), "x": rng.uniform(0.0, 1.0), "y": rng.uniform(0.0, 1.0),
                  "dur": rng.uniform(*CFG["motion"]["piece_slide_s"])}
            d = {"l": ev["x"], "r": 1 - ev["x"], "t": ev["y"], "b": 1 - ev["y"]}
            ev["edge"] = min(d, key=d.get)
            events.append(ev)
            t += rng.expovariate(1 / c["interval_s"]) + 0.25
        # each section's canvas starts empty: seed it with a quick burst so the background never sits black
        for s in SECS:
            st = s["start"] - CFG["motion"]["section_change_s"] - 0.05 + 0.08
            themes = c["section_themes"].get(s["id"], [])
            cands = [k for th in themes for k in BY_THEME.get(th, [])] or list(POOL)
            for j in range(7):
                ev = {"t": st + 0.12 * j, "id": rng.choice(cands), "seed": rng.randint(0, 10 ** 9), "w": rng.uniform(380, 720) * S,
                      "rot": rng.uniform(-2.5, 2.5), "cut": rng.choice(["rect", "rect", "poly", "torn"]),
                      "x": (j % 3) / 2 * 0.9 + 0.05 + rng.uniform(-0.05, 0.05), "y": (j / 7) * 0.95 + rng.uniform(0, 0.08), "dur": 0.35}
                d = {"l": ev["x"], "r": 1 - ev["x"], "t": ev["y"], "b": 1 - ev["y"]}
                ev["edge"] = min(d, key=d.get)
                events.append(ev)
        events.sort(key=lambda e: e["t"])
        self.events = events
        self.segs = [(0.0, 0)] + [(s["start"] - CFG["motion"]["section_change_s"] - 0.05, s["id"]) for s in SECS[1:]]

    def make_piece(self, ev):
        if "img" in ev:
            return ev["img"]
        rng = random.Random(ev["seed"])
        src = Image.open(ROOT / POOL[ev["id"]]["local"]).convert("RGB")
        src.thumbnail((1200, 1200))
        sw, sh = src.size
        area, asp = rng.uniform(0.4, 1.0), rng.uniform(0.6, 1.6)
        cw = min(sw, int(math.sqrt(area * sw * sh * asp)))
        ch = min(sh, int(cw / asp))
        x0, y0 = rng.randint(0, max(0, sw - cw)), rng.randint(0, max(0, sh - ch))
        crop = src.crop((x0, y0, x0 + cw, y0 + ch))
        w = int(ev["w"])
        h = int(ch * w / max(1, cw))
        out = crop.resize((max(2, w), max(2, h)), Image.LANCZOS).convert("RGBA")
        out.putalpha(self.cut_mask(out.width, out.height, ev["cut"], rng))
        if abs(ev["rot"]) > 0.1:
            out = out.rotate(ev["rot"], resample=Image.BICUBIC, expand=True)
        ev["img"] = out
        return out

    def piece_xy(self, ev, t):
        im = ev["img"]
        x = ev["x"] * self.W - im.width / 2
        y = ev["y"] * self.H - im.height / 2
        k = 1 - ease_out((t - ev["t"]) / ev["dur"], 5)
        if ev["edge"] == "l":
            x -= k * (x + im.width + 20)
        elif ev["edge"] == "r":
            x += k * (self.W - x + 20)
        elif ev["edge"] == "t":
            y -= k * (y + im.height + 20)
        else:
            y += k * (self.H - y + 20)
        return x, y

    def segment_at(self, t):
        return max(i for i, (st, _) in enumerate(self.segs) if st <= t)

    def canvas_at(self, t):
        si = self.segment_at(t)
        st, _ = self.segs[si]
        c = self._canvas
        if c is None or c["seg"] != si or t < c["t"]:
            c = {"seg": si, "t": st, "img": Image.new("RGBA", (self.W, self.H), self.C["background"] + (255,)), "i": 0}
            while c["i"] < len(self.events) and self.events[c["i"]]["t"] < st:
                c["i"] += 1
        while c["i"] < len(self.events):
            ev = self.events[c["i"]]
            if ev["t"] + ev["dur"] > t:
                break
            im = self.make_piece(ev)
            x, y = self.piece_xy(ev, ev["t"] + ev["dur"] + 1)
            self.paste(c["img"], im, x, y)
            c["i"] += 1
        c["t"] = t
        self._canvas = c
        return c

    def collage_frame(self, t):
        c = self.canvas_at(t)
        frame = c["img"].copy()
        for ev in self.events[c["i"]:]:
            if ev["t"] > t:
                break
            if ev["t"] < self.segs[c["seg"]][0]:
                continue
            im = self.make_piece(ev)
            x, y = self.piece_xy(ev, t)
            self.paste(frame, im, x, y)
        st, sid = self.segs[c["seg"]]
        if c["seg"] > 0 and t < st + CFG["motion"]["section_change_s"]:
            for shard, (dx, dy), delay, (sx, sy) in self.shards(c["seg"]):
                k = ease_in((t - st - delay) / 0.38)
                self.paste(frame, shard, sx + dx * k * self.W * 1.1, sy + dy * k * self.H * 1.1)
        return frame

    def shards(self, seg):
        if seg in self._snap:
            return self._snap[seg]
        st, _ = self.segs[seg]
        saved = self._canvas
        self._canvas = None
        snap = self.collage_frame(st - 1e-3)
        self._canvas = saved
        rng = random.Random(seg * 7 + 3)
        gw, gh = 27, 48
        seeds = [(rng.uniform(0, gw), rng.uniform(0, gh)) for _ in range(12)]
        yy, xx = np.mgrid[0:gh, 0:gw]
        lab = np.argmin(np.stack([(xx - sx) ** 2 + (yy - sy) ** 2 for sx, sy in seeds]), axis=0)
        out = []
        for i in range(len(seeds)):
            m = Image.fromarray(((lab == i) * 255).astype(np.uint8)).resize((self.W, self.H), Image.NEAREST)
            bbox = m.getbbox()
            if not bbox:
                continue
            piece = snap.crop(bbox)
            piece.putalpha(m.crop(bbox))
            cx, cy = (bbox[0] + bbox[2]) / 2 / self.W, (bbox[1] + bbox[3]) / 2 / self.H
            d = {(-1, 0): cx, (1, 0): 1 - cx, (0, -1): cy, (0, 1): 1 - cy}
            out.append((piece, min(d, key=d.get), rng.uniform(0, 0.2), (bbox[0], bbox[1])))
        self._snap[seg] = out
        return out

    def vignette(self, s):
        if s not in self._vig:
            yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
            r = np.sqrt(((xx - self.W / 2) / (self.W / 2)) ** 2 + ((yy - self.H * 0.45) / (self.H / 2)) ** 2)
            self._vig[s] = (1 - s * np.clip(r - 0.35, 0, 1) ** 1.4)[..., None]
        return self._vig[s]

    def background(self, t):
        """Quiet, dimmed collage: the stage and text sit on top at full brightness."""
        a = np.asarray(self.collage_frame(t).convert("RGB"), np.float32)
        lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
        a = a * 0.62 + lum[..., None] * 0.38
        a = a * np.array([1.04, 1.0, 0.95], np.float32)
        sid = section_at(t)
        dim = CFG["collage"]["dim"] * (0.9 + 0.05 * sid)          # slowly brighter through the video
        a = (a * dim) * self.vignette(0.6)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")

    # ── narration strips ────────────────────────────────────
    def build_text(self):
        tc, L = CFG["text"], CFG["layout"]
        S = self.S
        px = tc["size_px"] * S
        self.px = px
        pad = tc["pad_x_px"] * S
        strip_h = int(tc["strip_h_em"] * px)
        gap = tc["gap_px"] * S
        self.lines = []
        for si, s in enumerate(SECS):
            y = 0.0
            for pi, ln in enumerate(s["lines"]):
                rows = wrap(tokens(ln["text"]), px, (self.sx1 - self.sx0) - 2 * pad)
                total = sum(len(" ".join(w for w, _ in r)) for r in rows)
                acc = 0
                if pi:
                    y += tc["para_gap_px"] * S
                for r in rows:
                    t0 = ln["start"] + (ln["end"] - ln["start"]) * acc / max(1, total) - 0.05
                    acc += len(" ".join(w for w, _ in r)) + 1
                    self.lines.append({"sec": si, "y_rel": y, "x": self.sx0, "t0": t0, "img": self.render_strip(r, strip_h)})
                    y += strip_h + gap
        top, bottom = L["text_y"][0] * S, L["text_y"][1] * S
        self.col_top = top
        self.scrolls = {si: [] for si in range(len(SECS))}
        for si in range(len(SECS)):
            off = 0.0
            mine = [l for l in self.lines if l["sec"] == si]
            for j, Lr in enumerate(mine):
                need = top + Lr["y_rel"] + Lr["img"].height - bottom
                if j >= L["max_strips"]:
                    need = max(need, mine[j - L["max_strips"] + 1]["y_rel"])
                if need > off:
                    self.scrolls[si].append((Lr["t0"] - 0.05, need - off))
                    off = need

    def render_strip(self, row, strip_h):
        pad = int(CFG["text"]["pad_x_px"] * self.S)
        tw = text_width(row, self.px)
        im = Image.new("RGBA", (int(tw + 2 * pad), strip_h), self.C["strip"] + (255,))
        draw_row(ImageDraw.Draw(im), pad, strip_h * 0.52, row, self.px, self.C["ink"] + (255,))
        return im

    def text_offset(self, si, t):
        off = sum(d * ease((t - ts) / CFG["motion"]["scroll_s"]) for ts, d in self.scrolls[si] if t > ts)
        if si + 1 < len(SECS):
            tn = SECS[si + 1]["start"] - CFG["motion"]["section_change_s"] - 0.1
            if t > tn:
                off += self.H * 0.8 * ease_in((t - tn) / 0.5)
        return off

    def draw_text(self, frame, t):
        fade = CFG["layout"]["header_fade_px"] * self.S
        for Lr in self.lines:
            if t < Lr["t0"] or t >= self.endcard:
                continue
            if Lr["sec"] + 1 < len(SECS) and t > SECS[Lr["sec"] + 1]["start"] + 0.2:
                continue
            y = self.col_top + Lr["y_rel"] - self.text_offset(Lr["sec"], t)
            a = clamp((y - (self.col_top - fade)) / fade)
            if a <= 0 or y > self.H:
                continue
            r = ease_out((t - Lr["t0"]) / 0.16, 5)
            im = Lr["img"]
            if r < 1:
                im = im.crop((0, 0, max(1, int(im.width * r)), im.height))
            self.paste(frame, im, Lr["x"], y, a)

    # ── header tags ─────────────────────────────────────────
    def tag_img(self, text, bold=False):
        px = 30 * self.S
        f = font("b" if bold else "r", px)
        h = int(60 * self.S)
        pad = int(28 * self.S)
        im = Image.new("RGBA", (int(f.getlength(text) + 2 * pad), h), self.C["strip"] + (255,))
        ImageDraw.Draw(im).text((pad, h * 0.53), text, font=f, fill=self.C["ink"] + (255,), anchor="lm")
        return im

    def build_tags(self):
        self.tag_series = self.tag_img(CFG["series_name"], bold=True)
        self.tag_secs = {s["id"]: self.tag_img(s["tag"]) for s in SECS}

    def draw_tags(self, frame, t):
        if t < self.title_end or t >= self.endcard:
            return
        y = 230 * self.S
        k0 = ease((t - self.title_end) / 0.5)
        self.paste(frame, self.tag_series, 60 * self.S, y, k0)
        sid = section_at(t)
        im = self.tag_secs[sid]
        st = sec(sid)["start"] - 0.65
        k = ease_out((t - st) / 0.35, 4)
        if k < 1:
            im = im.crop((0, 0, max(1, int(im.width * k)), im.height))
        self.paste(frame, im, 60 * self.S + self.tag_series.width + 16 * self.S, y, k0)

    # ── title & end card ────────────────────────────────────
    def title_text(self, px, color):
        lines = ["The Hero With", "Infinite *Faces*"]
        rows = []
        for line in lines:
            parts = [p for p in re.split(r"(\*[^*]+\*)", line) if p]
            w = sum(font("ti" if p.startswith("*") else "t", px).getlength(p.strip("*")) for p in parts)
            rows.append((parts, w))
        W = int(max(w for _, w in rows) + 20)
        im = Image.new("RGBA", (W, int(px * 2.2)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        y = 0
        for parts, w in rows:
            x = (W - w) / 2
            for p in parts:
                f = font("ti" if p.startswith("*") else "t", px)
                d.text((x, y), p.strip("*"), font=f, fill=color + (255,))
                x += f.getlength(p.strip("*"))
            y += px * 1.02
        return im

    def build_cards(self):
        S = self.S
        self.title_img = self.title_text(128 * S, self.C["label_ink"])
        bg = Image.open(ROOT / "assets/public_domain/flood_tablet.jpg").convert("RGB")
        bg = ImageOps.fit(bg, (self.W, self.H), Image.LANCZOS)
        bg = ImageEnhance.Brightness(ImageOps.grayscale(bg).convert("RGB")).enhance(0.22)
        self.title_bg = bg.convert("RGBA")
        self.title_faces = [{"src": "file:assets/public_domain/gilgamesh.jpg"}, {"src": "file:assets/v4/achilles.jpg"},
                            {"src": "file:assets/v4/knight.jpg"}, {"src": "hero:link_botw"}, {"src": "still:nausicaa"}]
        card = Image.new("RGBA", (self.W, self.H), (12, 11, 11, 255))
        ti = self.title_text(112 * S, self.C["label_ink"])
        cx = self.scx
        card.alpha_composite(ti, (int(cx - ti.width / 2), int(700 * S)))
        f = font("r", 40 * S)
        ImageDraw.Draw(card).text((cx, 700 * S + ti.height + 50 * S), CFG["series_name"], font=f, fill=self.C["accent"], anchor="mm")
        self.end_card = card

    def draw_title(self, frame, t, alpha):
        S = self.S
        self.paste(frame, self.title_bg, 0, 0, alpha)
        k = ease_out(t / 0.9, 3)
        self.paste(frame, self.title_img, self.scx - self.title_img.width / 2, 470 * S + (1 - k) * 30 * S, alpha * k)
        # five faces, one after another: the same figure in different people
        n = len(self.title_faces)
        cw = (self.sx1 - self.sx0 - 16 * S * (n - 1)) / n
        for i, it in enumerate(self.title_faces):
            pic = self.picture(it["src"], cw, 300 * S, fill=True)
            if pic is None:
                continue
            im = pic[0]
            u = ease_out((t - 0.25 - 0.22 * i) / 0.4, 4)
            x = self.sx0 + i * (cw + 16 * S) - pic[1]
            self.paste(frame, im, x, 1000 * S + (1 - u) * 50 * S, alpha * u)

    # ── stage ───────────────────────────────────────────────
    def build_stage(self):
        self.items = []
        for sc in SCENES:
            it = dict(sc)
            it["t0"], it["t1"] = T(sc["at"]), T(sc["until"])
            for x in it.get("items", []):
                x["t"] = T(x["at"]) if "at" in x else it["t0"]
                self.sfx.append(x["t"] + 0.3)
            self.items.append(it)

    def life(self, t, t0, t1, din=0.45, dout=0.35):
        """→ (alpha, entry progress, exit progress)."""
        ui = ease_out((t - t0) / din, 4)
        uo = ease_in((t - (t1 - dout)) / dout)
        return clamp((t - t0) / (din * 0.5)) * (1 - uo), ui, uo

    def draw_stage(self, frame, t):
        for it in self.items:
            if it["t0"] - 0.05 <= t < it["t1"]:
                getattr(self, "st_" + it["kind"])(frame, t, it)

    def layout_row(self, it, reserve=0.0):
        S = self.S
        items = it["items"]
        n = len(items)
        gap = 22 * S
        aw = self.sx1 - self.sx0
        mw = (aw - gap * (n - 1)) / n
        mh = it.get("max_h", 380) * S
        if it.get("equal"):
            mw = min(mw, mh * 0.82)
        cards = []
        for x in items:
            im, box = self.card(x, mw, mh, fill=bool(it.get("equal")))
            cards.append((x, im, box))
        tot = sum(c[1].width for c in cards if c[1] is not None) + gap * (n - 1)
        x = self.scx - tot / 2
        avail = (self.sy1 - self.sy0) - reserve
        out = []
        top = any(x.get("tags") for x in items)        # trait chips go underneath, so start at the top of the stage
        for x_it, im, box in cards:
            if im is None:
                continue
            y = self.sy0 + (0 if top else max(0, (avail - im.height) / 2))
            out.append((x_it, im, box, x, y))
            x += im.width + gap
        return out

    def st_cards(self, frame, t, it):
        S = self.S
        reserve = 0
        if it.get("caption") or it.get("bracket"):
            reserve = 90 * S
        if it.get("correction"):
            reserve = 150 * S
        if it.get("layout") == "fan":
            return self.st_fan(frame, t, it)
        placed = self.layout_row(it, reserve)
        if it.get("chips") and len(placed) == 1:     # one picture, chips in a column beside it
            x_it, im, box, x, y = placed[0]
            placed = [(x_it, im, box, self.sx0 + 10 * S, y)]
        boxes = []
        for i, (x_it, im, box, x, y) in enumerate(placed):
            a, ui, uo = self.life(t, x_it["t"], it["t1"])
            if a <= 0:
                continue
            dx = (1 - ui) * 90 * S * (1 if i % 2 == 0 else -1)
            self.paste(frame, im, x + dx, y - uo * 30 * S, a)
            boxes.append((x + box[0], y + box[1], box[2], box[3]))
            if x_it.get("tag"):          # a single quality: chip under the picture
                ka, kui, _ = self.life(t, x_it["t"] + 0.2, it["t1"], din=0.3)
                ch = self.chip_img(x_it["tag"], "accent", px=32)
                cx = clamp(x + box[0] + box[2] / 2 - ch.width / 2, self.sx0 - 20 * S, self.sx1 - ch.width)
                self.paste(frame, ch, cx, y + box[1] + box[3] + 14 * S + (1 - kui) * 14 * S, ka)
            tags = list(x_it.get("tags", []))       # traits: chips stacked under the card's label
            ty = y + im.height + 10 * S
            for j, (txt, style, ref) in enumerate(tags):
                tt = T(ref) if ref else x_it["t"] + 0.25
                ka, kui, _ = self.life(t, tt, it["t1"], din=0.3)
                ch = self.chip_img(txt, style, px=30)
                if ka > 0:
                    cx = clamp(x + box[0] + box[2] / 2 - ch.width / 2, self.sx0 - 20 * S, self.sx1 - ch.width)
                    self.paste(frame, ch, cx, ty + (1 - kui) * 16 * S, ka)
                ty += ch.height + 10 * S
        if it.get("chips"):
            x0 = placed[0][3] + placed[0][1].width + 30 * S if placed else self.scx
            y = self.sy0 + 40 * S
            for c in it["chips"]:
                tt = T(c["at"])
                ka, kui, _ = self.life(t, tt, it["t1"], din=0.3)
                ch = self.chip_img(c["text"], c.get("style", "paper"))
                self.paste(frame, ch, min(x0, self.sx1 - ch.width) + (1 - kui) * 40 * S, y, ka)
                y += ch.height + 18 * S
        if it.get("caption"):
            c = it["caption"]
            ka, kui, _ = self.life(t, T(c["at"]), it["t1"], din=0.35)
            ch = self.chip_img(c["text"], "accent")
            self.paste(frame, ch, self.scx - ch.width / 2, self.sy1 - ch.height + (1 - kui) * 16 * S, ka)
        if it.get("bracket") and boxes:
            b = it["bracket"]
            ka, kui, _ = self.life(t, T(b["at"]), it["t1"], din=0.5)
            if ka > 0:
                xa = min(bx for bx, _, _, _ in boxes)
                xb = max(bx + bw for bx, _, bw, _ in boxes)
                yb = max(by + bh for _, by, _, bh in boxes) + 70 * S
                d = ImageDraw.Draw(frame)
                col = self.C["accent"] + (int(255 * ka),)
                xm = xa + (xb - xa) * kui
                d.line([(xa, yb), (xm, yb)], fill=col, width=int(5 * S))
                d.line([(xa, yb - 18 * S), (xa, yb)], fill=col, width=int(5 * S))
                if kui > 0.98:
                    d.line([(xb, yb - 18 * S), (xb, yb)], fill=col, width=int(5 * S))
                ch = self.chip_img(b["text"], "accent", px=30)
                self.paste(frame, ch, self.scx - ch.width / 2, yb + 10 * S, ka * kui)
        if it.get("correction"):
            c = it["correction"]
            yw = self.sy1 - 140 * S
            ka, kui, _ = self.life(t, it["t0"] + 0.4, it["t1"], din=0.35)
            wrong = self.chip_img(c["wrong"], "paper", px=32)
            xw = self.scx - wrong.width / 2
            self.paste(frame, wrong, xw, yw, ka)
            ks = ease_out((t - T(c["strike_at"])) / 0.5)
            if ks > 0 and ka > 0:
                d = ImageDraw.Draw(frame)
                ym = yw + wrong.height * 0.52
                d.line([(xw + 10 * S, ym), (xw + 10 * S + (wrong.width - 20 * S) * ks, ym)], fill=self.C["accent"] + (int(255 * ka),), width=int(6 * S))
            kr, krui, _ = self.life(t, T(c["right_at"]), it["t1"], din=0.35)
            right = self.chip_img(c["right"], "accent", px=30)
            self.paste(frame, right, self.scx - right.width / 2, yw + wrong.height + 14 * S + (1 - krui) * 14 * S, kr)

    def st_fan(self, frame, t, it):
        S = self.S
        n = len(it["items"])
        for i, x_it in enumerate(it["items"]):
            rot = (i - (n - 1) / 2) * 7
            pic = self.picture(x_it["src"], 560 * S, 400 * S, rot=rot)
            if pic is None:
                continue
            im = pic[0]
            a, ui, uo = self.life(t, x_it["t"], it["t1"])
            x = self.scx - im.width / 2 + (i - (n - 1) / 2) * 150 * S
            y = self.sy0 + (self.sy1 - self.sy0 - im.height) / 2 + (1 - ui) * 120 * S
            self.paste(frame, im, x, y, a)

    def st_conveyor(self, frame, t, it):
        S = self.S
        gap = 90 * S
        cards = []
        for x_it in it["items"]:
            im, box = self.card(x_it, 400 * S, 330 * S)
            if im is not None:
                cards.append((x_it, im, box))
        xs, x = [], 0.0
        for _, im, _ in cards:
            xs.append(x + im.width / 2)
            x += im.width + gap
        focus = [T(c[0]["focus"]) for c in cards]
        # strip offset: hold on each card, glide to the next over the 0.8 s before its focus time
        off = xs[0]
        for i in range(len(cards) - 1):
            if t >= focus[i]:
                k = ease((t - (focus[i + 1] - 0.8)) / 0.8)
                off = xs[i] + (xs[i + 1] - xs[i]) * k
        off -= (1 - ease_out((t - it["t0"]) / 0.9, 3)) * self.W * 0.9       # slides in from the right
        a_all, _, _ = self.life(t, it["t0"], it["t1"], din=0.2)
        ybase = self.sy0 + 20 * S
        d = ImageDraw.Draw(frame)
        shelf_y = ybase + 345 * S
        d.line([(0, shelf_y), (self.W, shelf_y)], fill=self.C["label_ink"] + (int(70 * a_all),), width=max(1, int(2 * S)))
        for (x_it, im, box), cx, ft in zip(cards, xs, focus):
            x = self.scx + (cx - off) - im.width / 2
            if x > self.W or x + im.width < 0:
                continue
            dist = abs(cx - off) / (400 * S)
            a = a_all * (1.0 if dist < 0.5 else max(0.35, 1 - 0.45 * dist))
            if x + im.width > self.sx1 + 10 * S or x < self.sx0 - 30 * S:   # dim where TikTok's buttons sit
                a *= 0.3
            y = ybase + (330 * S + box[1] - box[3] - box[1]) * 0 + (330 * S - box[3]) * 0.5
            self.paste(frame, im, x, y, a)

    def st_route(self, frame, t, it):
        S = self.S
        bw, bh = self.sx1 - self.sx0, self.sy1 - self.sy0 - 10 * S
        key = ("routemap", int(bw), int(bh))
        if key not in self._img:
            m, _ = self.src_image(it["map"])
            m = ImageOps.fit(m.convert("RGB"), (int(bw), int(bh)), Image.LANCZOS)
            m = ImageEnhance.Color(m).enhance(0.35)
            m = ImageEnhance.Brightness(m).enhance(0.92)
            self._img[key] = m.convert("RGBA")
        m = self._img[key]
        a, ui, uo = self.life(t, it["t0"], it["t1"])
        x0, y0 = self.sx0, self.sy0
        self.paste(frame, m, x0, y0 + (1 - ui) * 40 * S, a)
        ch = self.chip_img(it["title"], "paper", px=28)
        self.paste(frame, ch, x0 + 16 * S, y0 + 16 * S, a)
        # the route: out from home, through the test, and back to a new place near home (an open line, not a circle)
        P = [(0.12, 0.8), (0.28, 0.6), (0.5, 0.52), (0.8, 0.34), (0.74, 0.6), (0.5, 0.7), (0.3, 0.52), (0.2, 0.42)]
        pts = []
        for i in range(len(P) - 1):
            p0, p1 = P[max(0, i - 1)], P[i]
            p2, p3 = P[i + 1], P[min(len(P) - 1, i + 2)]
            for k in range(14):
                u = k / 14
                u2, u3 = u * u, u * u * u
                pts.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * u + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u2
                                        + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * u3) for j in (0, 1)))
        pts.append(P[-1])
        stops = it["stops"]
        tA, tB = T(stops[0]["at"]) - 0.3, T(stops[-1]["at"])
        prog = clamp((t - tA) / max(0.1, tB - tA))
        n = int(len(pts) * prog)
        d = ImageDraw.Draw(frame)
        col = self.C["accent"] + (int(255 * a),)
        yo = y0 + (1 - ui) * 40 * S
        for i in range(0, max(0, n - 1), 2):          # dashed
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            d.line([(x0 + ax * bw, yo + ay * bh), (x0 + bx * bw, yo + by * bh)], fill=col, width=int(7 * S))
        stop_pos = [P[0], P[3], P[-1]]
        for (sx, sy), s in zip(stop_pos, stops):
            ka, kui, _ = self.life(t, T(s["at"]), it["t1"], din=0.3)
            if ka <= 0:
                continue
            r = 13 * S * (0.6 + 0.4 * kui)
            X, Y = x0 + sx * bw, yo + sy * bh
            d.ellipse([X - r, Y - r, X + r, Y + r], fill=self.C["accent"] + (int(255 * ka * a),), outline=self.C["strip"] + (int(255 * ka * a),), width=int(3 * S))
            lab = self.chip_img(s["text"], "paper", px=28)
            lx = clamp(X - lab.width / 2, x0 + 6 * S, x0 + bw - lab.width - 6 * S)
            ly = Y - lab.height - 22 * S if sy > 0.5 else Y + 22 * S
            self.paste(frame, lab, lx, ly, ka * a)

    def st_branches(self, frame, t, it):
        S = self.S
        bw, bh = self.sx1 - self.sx0, self.sy1 - self.sy0 - 10 * S
        a, ui, uo = self.life(t, it["t0"], it["t1"])
        panel = Image.new("RGBA", (int(bw), int(bh)), self.C["strip"] + (255,))
        d = ImageDraw.Draw(panel)
        ink = self.C["ink"] + (255,)
        root = (0.5, 0.86)
        split = (0.5, 0.74)
        tips = [(0.17, 0.4), (0.5, 0.36), (0.83, 0.4)]
        kinks = [(0.3, 0.6), (0.46, 0.55), (0.7, 0.61)]
        prog = clamp((t - it["t0"] - 0.3) / 2.6)
        def seg(p, q, k):
            d.line([(p[0] * bw, p[1] * bh), ((p[0] + (q[0] - p[0]) * k) * bw, (p[1] + (q[1] - p[1]) * k) * bh)], fill=ink, width=int(6 * S))
        seg(root, split, clamp(prog / 0.25))
        for tip, kink in zip(tips, kinks):
            k = clamp((prog - 0.25) / 0.75)
            seg(split, kink, clamp(k / 0.5))
            seg(kink, tip, clamp((k - 0.5) / 0.5))
        f = font("i", 28 * S)
        d.text((root[0] * bw, root[1] * bh + 12 * S), it["root"], font=f, fill=ink, anchor="mt")
        ft = font("r", 32 * S)
        for tip, name in zip(tips, it["tips"]):
            if prog > 0.95:
                d.text((tip[0] * bw, tip[1] * bh - 14 * S), name, font=ft, fill=ink, anchor="md")
        self.paste(frame, panel, self.sx0, self.sy0 + (1 - ui) * 40 * S, a)
        ts = T(it["solution_at"])
        for i, tip in enumerate(tips):
            ka, kui, _ = self.life(t, ts + 0.18 * i, it["t1"], din=0.3)
            ch = self.chip_img(it["solution"], "accent", px=32)
            self.paste(frame, ch, self.sx0 + tip[0] * bw - ch.width / 2, self.sy0 + tip[1] * bh - ch.height - 62 * S + (1 - kui) * 14 * S, ka * a)

    FACES = ["file:assets/public_domain/gilgamesh.jpg", "pool:aic_862", "hero:link_botw", "file:assets/v4/achilles.jpg", "pool:wellcome_shcnbaq7",
             "still:nausicaa", "pool:cma_170811", "hero:aragorn", "file:assets/public_domain/heracles.jpg", "pool:aic_29230", "hero:frodo",
             "file:assets/v4/knight.jpg", "pool:aic_11", "hero:master_chief", "pool:wellcome_jbmrvh53", "hero:sam", "pool:cma_153683",
             "still:nausicaa_study", "pool:wellcome_mvexkxsk", "hero:link", "pool:cma_98348", "hero:goku",
             "pool:wellcome_rp6na57s", "still:link_oot", "pool:cma_140084", "hero:luke"]

    def grid_img(self, cols, rows, seed):
        S = self.S
        key = ("grid", cols, rows, seed)
        if key in self._img:
            return self._img[key]
        bw, bh = int(self.sx1 - self.sx0), int(self.sy1 - self.sy0 - 10 * S)
        g = max(1, int(6 * S * min(1.0, 8 / cols)))
        cw, ch = (bw - g * (cols - 1)) / cols, (bh - g * (rows - 1)) / rows
        im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        rng = random.Random(seed)
        order = list(self.FACES)
        tiles = []
        for r in range(rows):
            for c in range(cols):
                if not order:
                    order = list(self.FACES)
                    rng.shuffle(order)
                src = order.pop(rng.randrange(len(order)))
                base, rect = self.src_image(src)
                if base is None:
                    continue
                tk = ("tile", src, int(cw), int(ch))
                if tk not in self._img:
                    if rect:
                        tile = ImageOps.fit(base.convert("RGB"), (max(2, int(cw)), max(2, int(ch))), Image.LANCZOS).convert("RGBA")
                    else:
                        tile = Image.new("RGBA", (max(2, int(cw)), max(2, int(ch))), (38, 34, 32, 255))
                        cut = ImageOps.contain(base, (max(2, int(cw)), max(2, int(ch))), Image.LANCZOS)
                        tile.alpha_composite(cut, ((tile.width - cut.width) // 2, tile.height - cut.height))
                    self._img[tk] = tile
                x, y = int(c * (cw + g)), int(r * (ch + g))
                tiles.append((self._img[tk], x, y))
                im.alpha_composite(self._img[tk], (x, y))
        self._img[key] = (im, tiles)
        return self._img[key]

    def st_grid(self, frame, t, it):
        S = self.S
        a, ui, uo = self.life(t, it["t0"], it["t1"])
        cols, rows = it["cols"], it["rows"]
        if it.get("grow"):
            im, tiles = self.grid_img(cols, rows, 3)
            span = max(0.5, it["t1"] - it["t0"] - 1.0)
            for i, (tile, x, y) in enumerate(tiles):
                tt = it["t0"] + span * i / len(tiles)
                ka = ease((t - tt) / 0.3)
                self.paste(frame, tile, self.sx0 + x, self.sy0 + y + (1 - ka) * 14 * S, ka * a)
            return
        levels = [it["t0"]] + [T(r) for r in it.get("subdivide", [])]
        lvl = max(i for i, lt in enumerate(levels) if t >= lt - 1e-6) if t >= levels[0] else 0
        im, _ = self.grid_img(cols * 2 ** lvl, rows * 2 ** lvl, 5 + lvl)
        if lvl == 0:
            k = ease((t - it["t0"]) / 0.6)
            self.paste(frame, im, self.sx0, self.sy0 + (1 - k) * 30 * S, a * k)
        else:
            prev, _ = self.grid_img(cols * 2 ** (lvl - 1), rows * 2 ** (lvl - 1), 4 + lvl)
            k = ease((t - levels[lvl]) / 0.5)
            self.paste(frame, prev, self.sx0, self.sy0, a * (1 - k))
            self.paste(frame, im, self.sx0, self.sy0, a * k)

    def st_chain(self, frame, t, it):
        S = self.S
        n = len(it["items"])
        gap = 46 * S
        cw = (self.sx1 - self.sx0 - gap * (n - 1)) / n
        cards = [self.picture(x["src"], cw, 300 * S, fill=True) for x in it["items"]]
        d = ImageDraw.Draw(frame)
        y = self.sy0 + 80 * S
        for i, (x_it, pic) in enumerate(zip(it["items"], cards)):
            if pic is None:
                continue
            im, off, iw, ih = pic
            a, ui, uo = self.life(t, x_it["t"], it["t1"])
            if it.get("improve"):
                a *= 0.45 + 0.55 * (i / max(1, n - 1)) if t > it["items"][-1]["t"] + 0.4 else 1.0
            x = self.sx0 + i * (cw + gap)
            self.paste(frame, im, x - off, y - off + (1 - ui) * 40 * S, a)
            if i < n - 1:
                ka = ease((t - it["items"][i + 1]["t"]) / 0.3) * (1 - uo)
                if ka > 0:
                    ax0, ax1 = x + iw + 8 * S, x + cw + gap - 8 * S
                    ay = y + ih / 2
                    col = (self.C["accent"] if it.get("improve") else self.C["label_ink"]) + (int(255 * ka),)
                    d.line([(ax0, ay), (ax1, ay)], fill=col, width=int(5 * S))
                    d.polygon([(ax1 + 4 * S, ay), (ax1 - 10 * S, ay - 9 * S), (ax1 - 10 * S, ay + 9 * S)], fill=col)
        if it.get("improve"):
            ka, kui, _ = self.life(t, it["items"][-1]["t"] + 0.5, it["t1"], din=0.35)
            ch = self.chip_img("keep what worked, correct what did not", "accent", px=28)
            self.paste(frame, ch, self.scx - ch.width / 2, y + 330 * S + (1 - kui) * 14 * S, ka)

    # ── frame ───────────────────────────────────────────────
    def frame(self, t):
        if t >= self.endcard + 0.6:
            return np.asarray(self.end_card.convert("RGB"))
        frame = self.background(t)
        if t < self.title_end + 0.7:
            self.draw_title(frame, t, 1 - ease((t - self.title_end) / 0.7))
        self.draw_stage(frame, t)
        self.draw_text(frame, t)
        self.draw_tags(frame, t)
        if t >= self.endcard:
            frame.alpha_composite(Image.blend(Image.new("RGBA", frame.size, (0, 0, 0, 0)), self.end_card, ease((t - self.endcard) / 0.6)))
        return np.asarray(frame.convert("RGB"))


def overlay_safe(img):
    S = img.width / 1080
    o = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(o)
    d.rectangle([0, 0, img.width, 220 * S], fill=(255, 0, 0, 70))
    d.rectangle([0, img.height - 480 * S, img.width, img.height], fill=(255, 0, 0, 70))
    d.rectangle([img.width - 140 * S, 0, img.width, img.height], fill=(255, 0, 0, 70))
    return Image.alpha_composite(img.convert("RGBA"), o).convert("RGB")


def mix_audio(out_wav):
    vo_user = ROOT / "assets" / "voiceover_draft4.wav"
    vo = vo_user if vo_user.exists() else D4 / "build" / "vo.wav"
    music_user = ROOT / CFG["music"]["file"]
    sound = D4 / "build" / "sound_bed.wav"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_sound_v4.py")] + ([str(music_user)] if music_user.exists() else []), check=True)
    m = CFG["music"]
    parts = [f"between(t,{ln['start'] - 0.3:.2f},{ln['end'] + 0.8:.2f})" for s in SECS for ln in s["lines"]]
    duck = 10 ** (-m["duck_db"] / 20)
    L = CFG["loudness"]
    fc = (f"[1:a]aresample=48000,volume='if({'+'.join(parts)},{duck:.4f},1)':eval=frame[bed];"
          f"[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,apad[v];[v][bed]amix=inputs=2:duration=longest:normalize=0,"
          f"atrim=0:{DUR},loudnorm=I={L['integrated_lufs']}:TP={L['true_peak_db']}:LRA=11,aresample=48000[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vo), "-i", str(sound), "-filter_complex", fc,
                    "-map", "[a]", "-ar", "48000", str(out_wav)], check=True)


def main():
    args = sys.argv[1:]
    mode = args[0] if args else "preview"
    if mode == "still":
        safe = "--safe" in args
        R = Renderer("final")
        for ref in sorted([a for a in args[1:] if a != "--safe"], key=T):
            img = Image.fromarray(R.frame(T(ref)))
            if safe:
                img = overlay_safe(img)
            out = D4 / "build" / f"still_{ref}{'_safe' if safe else ''}.png"
            img.save(out)
            print(out.relative_to(ROOT), f"t={T(ref):.2f}")
        if MISSING:
            print("missing images:", sorted(MISSING))
        return
    from moviepy.editor import AudioFileClip, VideoClip
    R = Renderer(mode)
    wav = D4 / "build" / "mix.wav"
    mix_audio(wav)
    o = CFG["output"][mode]
    out = ROOT / o["file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    VideoClip(R.frame, duration=DUR).set_audio(AudioFileClip(str(wav), fps=48000)).write_videofile(
        str(out), fps=R.fps, codec="libx264", audio_codec="aac", audio_bitrate="192k", audio_fps=48000, preset=o["preset"],
        ffmpeg_params=["-crf", str(o["crf"]), "-pix_fmt", "yuv420p", "-movflags", "+faststart"], threads=4, logger=None)
    print("wrote", out.relative_to(ROOT))
    if MISSING:
        print("missing images:", sorted(MISSING))


if __name__ == "__main__":
    main()
