"""Draft 3 renderer: "The Hero With Infinite Faces", TikTok cut (1080×1920).

    python tools/render_v3.py preview                 → draft3/build/preview_540x960.mp4
    python tools/render_v3.py final                   → final/hero_infinite_faces_v3_vertical.mp4
    python tools/render_v3.py still s4.10@0.5 …       → draft3/build/still_<ref>.png  (1080×1920)
    python tools/render_v3.py still --safe s1.6 …     → same, with TikTok's covered areas overlaid

Design: draft3/DESIGN.md · settings: draft3/config.yaml · plan: draft3/PLAN.md
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

sys.path.insert(0, str(Path(__file__).parent))
import render_stack as RS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "draft3"
CFG = yaml.safe_load((D3 / "config.yaml").read_text())
TIMING = json.loads((D3 / "build" / "timing.json").read_text())
CUTSPEC = yaml.safe_load((ROOT / "assets" / "cutouts.yaml").read_text(encoding="utf-8"))
Image.MAX_IMAGE_PIXELS = None
SECS = TIMING["sections"]
DUR = TIMING["duration"]
MISSING = set()


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


# ── pools ────────────────────────────────────────────────────
def load_pool():
    pool = {}
    for p in CFG["collage"]["pools"]:
        f = ROOT / p
        if f.exists():
            for k, v in json.loads(f.read_text()).items():
                if (ROOT / v["local"]).exists():
                    pool[k] = v
    for p in CFG["collage"]["exclude"]:
        f = ROOT / p
        if f.exists():
            for line in f.read_text().splitlines():
                pool.pop(line.split("#")[0].strip(), None)
    return pool


POOL = load_pool()
NAMED = json.loads((D3 / "named_credits.json").read_text()) if (D3 / "named_credits.json").exists() else {}
# named public-domain works from DESIGN.md go into the collage pool with their own themes
_NAMED_THEMES = {"fludd": ["labyrinth", "esoteric", "stars", "named"], "michelspacher": ["labyrinth", "named"],
                 "remmelin": ["labyrinth", "layers", "named"], "flap_sheet": ["labyrinth", "layers", "named"],
                 "valentine": ["emblem", "rational", "named"], "bell_symbols": ["emblem", "rational", "named"]}
for _k, _v in NAMED.items():
    for _pre, _ths in _NAMED_THEMES.items():
        if _k.startswith(_pre) and (ROOT / _v["local"]).exists():
            POOL[_k] = {**_v, "themes": _ths, "query": _pre}
BY_THEME, BY_QUERY = {}, {}
for _k, _v in POOL.items():
    for _th in _v.get("themes", []):
        BY_THEME.setdefault(_th, []).append(_k)
    BY_QUERY.setdefault(_v.get("query", ""), []).append(_k)
FACEY = {"faces", "portrait", "costume", "scripture", "question", "infinite"}


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


ALL_LINES = [(s["id"], ln) for s in SECS for ln in s["lines"]]


def beat_at(t):
    cur = SECS[0]["id"]
    for s in SECS:
        if t >= s["start"] - 0.65:
            cur = s["id"]
    return cur


def register_at(t):
    reg = ALL_LINES[0][1]["register"]
    for _, ln in ALL_LINES:
        if t >= ln["start"] - 0.3:
            reg = ln["register"]
    return reg


REG_CHANGES = []
_prev = None
for _b, _ln in ALL_LINES:
    if _ln["register"] != _prev:
        REG_CHANGES.append((_ln["start"] - 0.3, _ln["register"]))
        _prev = _ln["register"]


def grade_at(t):
    regs = CFG["registers"]
    cur_t, cur = REG_CHANGES[0]
    prev = cur
    for ct, r in REG_CHANGES:
        if t >= ct:
            prev, cur_t, cur = cur, ct, r
    k = ease((t - cur_t) / CFG["motion"]["grade_xfade_s"])
    a, b = regs[prev]["grade"], regs[cur]["grade"]
    g = {key: a.get(key, 0) + (b.get(key, 0) - a.get(key, 0)) * k for key in set(a) | set(b)}
    g["keep_red"] = regs[cur].get("keep_red", False) and k > 0.5
    # light curve per beat
    L = CFG["light"]
    bt = beat_at(t)
    s0 = sec(bt)["start"] - 0.65
    prevb = max([s["id"] for s in SECS if s["id"] < bt] or [bt])
    lk = ease((t - s0) / 1.2)
    g["light"] = L.get(prevb, 1.0) + (L.get(bt, 1.0) - L.get(prevb, 1.0)) * lk
    return g


# ── fonts & text tokens ─────────────────────────────────────
@lru_cache(maxsize=64)
def font(kind, px):
    F = CFG["fonts"]
    path = {"r": F["body"], "b": F["body"], "i": F["body_italic"], "bi": F["body_italic"], "t": F["title"], "ti": F["title_italic"]}[kind]
    f = ImageFont.truetype(str(ROOT / path), int(px))
    try:
        f.set_variation_by_name("Bold" if kind in ("b", "bi") else "Regular")
    except Exception:
        pass
    return f


def tokens(line, force_italic=False):
    """→ [(word, style)], styles r/b/i/bi. Handles **bold**, *italic* spans, whole-line italics."""
    s = line.strip()
    whole = bool(re.fullmatch(r"\*[^*].*[^*]\*", s)) and s.count("*") == 2
    if whole:
        s = s[1:-1]
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", s):
        if not part:
            continue
        if part.startswith("**"):
            st = "b"
        elif part.startswith("*"):
            st = "i"
        else:
            st = "r"
        if whole or force_italic:
            st = "bi" if st == "b" else "i"
        for w in part.strip("*").split():
            out.append((w, st))
    glued = []
    for w, st in out:   # leading punctuation sticks to the previous word
        if glued and re.fullmatch(r"[.,;:!?…’”)\]]+", w):
            pw, pst = glued[-1]
            glued[-1] = (pw + "\x00" + w, pst + "|" + st)
        else:
            glued.append((w, st))
    return glued, whole


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
        self.rng = random.Random(CFG["collage"]["seed"])
        self._img = {}
        self.cut_title = T(CFG["cuts"]["title"])
        self.cut_stack = T(CFG["cuts"]["stack"]) - 0.25
        self.stack_end = sec(6)["start"] - 0.3
        self.cut_black = T(CFG["cuts"]["black"]) - 0.6
        self.black_end = sec(8)["start"] - 0.25
        self.endcard = T(CFG["cuts"]["end_card_after"])
        self.reprise = (T("s12.1") - 0.4, T("s12.3e") + 0.6)
        self.final_black = (T("s12.6") - 1.2, self.endcard)
        self.title_img = self.load_art(self.title_id())
        self.build_heroes()
        self.build_schedule()
        self.build_text()
        self.build_tags()
        self.build_cards()
        self.vignettes = {}
        self.stack = None
        self._snap = {}
        self._canvas = None

    # ── assets ──────────────────────────────────────────────
    def title_id(self):
        q = CFG["title"]["image_query"]
        hits = BY_QUERY.get(q) or list(POOL)
        return hits[0]

    def load_art(self, key, maxside=1500):
        if key in self._img:
            return self._img[key]
        path = ROOT / (POOL[key]["local"] if key in POOL else NAMED[key]["local"])
        im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        im.thumbnail((maxside, maxside), Image.LANCZOS)
        self._img[key] = im
        return im

    def hero_source(self, hid):
        """Flat hero cut-out (rembg mask, no sticker border), mirroring tools/make_cutouts.py crops."""
        key = "hero::" + hid
        if key in self._img:
            return self._img[key]
        if hid == "deku_tree":
            im = self.deku_tree(900)
            self._img[key] = im
            return im
        spec = CUTSPEC.get(hid) or {}
        src = None
        for d in ("stills", "public_domain"):
            hits = [p for p in sorted((ROOT / "assets" / d).glob(f"{hid}.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
            if hits:
                src = hits[0]
                break
        if src is None:
            MISSING.add(hid)
            self._img[key] = None
            return None
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
        if mode in ("rembg", "alpha"):
            alpha = None
            mp = ROOT / "build" / "masks" / f"{hid}.png"
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
        else:
            im.putalpha(self.cut_mask(im.width, im.height, "poly", random.Random(len(hid))))
        if spec.get("grey"):
            a = im.getchannel("A")
            im = ImageOps.grayscale(im.convert("RGB")).convert("RGBA")
            im.putalpha(a)
        self._img[key] = im
        return im

    def deku_tree(self, h):
        w = int(h * 0.9)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        rng = random.Random(4)
        trunk = (92, 62, 38, 255)
        d.polygon([(w * 0.40, h), (w * 0.44, h * 0.45), (w * 0.56, h * 0.45), (w * 0.62, h)], fill=trunk)
        for _ in range(5):
            x = w * rng.uniform(0.3, 0.7)
            d.polygon([(w * 0.5, h * 0.88), (x - w * 0.12, h), (x + w * 0.04, h)], fill=trunk)
        for _ in range(26):
            cx, cy = w * rng.uniform(0.18, 0.82), h * rng.uniform(0.08, 0.5)
            r = w * rng.uniform(0.12, 0.22)
            d.ellipse([cx - r, cy - r * 0.85, cx + r, cy + r * 0.85], fill=rng.choice([(46, 96, 52), (62, 120, 60), (84, 140, 70), (38, 82, 46)]) + (255,))
        for (a, b) in ((0.45, 0.49), (0.52, 0.56)):
            d.arc([w * a, h * 0.58, w * b, h * 0.62], 200, 340, fill=(40, 25, 15, 255), width=6)
        d.arc([w * 0.46, h * 0.64, w * 0.55, h * 0.72], 20, 160, fill=(40, 25, 15, 255), width=6)
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

    def pick(self, themes, rng, exclude=()):
        pool = [k for th in themes for k in BY_THEME.get(th, []) if k not in exclude]
        return rng.choice(pool) if pool else rng.choice(list(POOL))

    def pick_query(self, q, rng):
        hits = BY_QUERY.get(q)
        return rng.choice(hits) if hits else None

    # ── heroes ──────────────────────────────────────────────
    def build_heroes(self):
        self.heroes = []
        for h in CFG["heroes"]:
            if self.hero_source(h["id"]) is None:
                continue
            self.heroes.append({"id": h["id"], "t0": T(h["at"]), "t1": T(h["until"]), "keep_red": h.get("keep_red", False)})
        # slots: overlapping heroes share the band side by side
        for h in self.heroes:
            others = [o for o in self.heroes if o is not h and o["t0"] < h["t1"] and h["t0"] < o["t1"]]
            if not others:
                h["x"] = 0.463
            else:
                first = min([h] + others, key=lambda o: o["t0"])
                h["x"] = 0.30 if h is first else 0.64
        cas = CFG["cascade"]
        a, b = T(cas["from"]), T(cas["until"])
        rng = random.Random(11)
        tt, i = a, 0
        self.cascade = []
        while tt < b:
            frac = (tt - a) / (b - a)
            gap = max(cas["min_gap_s"], 1.1 * (1 - frac) ** 1.6 + cas["min_gap_s"] * frac)
            if i % 3 == 2 or frac < 0.15:
                hid = cas["heroes"][(i // 3) % len(cas["heroes"])]
                if self.hero_source(hid) is not None:
                    self.cascade.append({"t": tt, "hero": hid, "x": rng.uniform(0.12, 0.8), "y": rng.uniform(0.18, 0.72), "w": rng.uniform(0.16, 0.26), "rot": rng.uniform(-5, 5)})
            else:
                self.cascade.append({"t": tt, "art": self.pick(["portrait", "faces"], rng), "x": rng.uniform(0.12, 0.8), "y": rng.uniform(0.15, 0.74), "w": rng.uniform(0.2, 0.34), "rot": rng.uniform(-5, 5)})
            tt += gap
            i += 1

    def active_heroes(self, t):
        return [h for h in self.heroes if h["t0"] <= t < h["t1"] + 0.4]

    # ── collage schedule ────────────────────────────────────
    def segments(self):
        """Collage segments (start, end, base) between cuts / beat changes."""
        segs = [(0.0, "black")]
        segs.append((self.cut_title + 0.0, "title"))
        for s in SECS:
            st = s["start"] - CFG["motion"]["beat_change_s"] - 0.05
            if s["id"] in (0, 1, 5, 6, 8):
                continue
            segs.append((st, f"beat{s['id']}"))
        segs.append((self.stack_end, "stark"))
        segs.append((self.black_end, "rational"))
        segs.sort()
        return segs

    def build_schedule(self):
        c = CFG["collage"]
        rng = self.rng
        W, H = self.W, self.H
        events = []
        t = 0.6
        while t < self.endcard:
            if self.cut_stack <= t < self.stack_end or self.cut_black <= t < self.black_end or self.final_black[0] <= t:
                t += 0.5
                continue
            if self.cut_title - 0.3 <= t < T("s1.1") - 0.2:
                t = T("s1.1") - 0.2
                continue
            reg = register_at(t)
            R = CFG["registers"][reg]
            n = rng.randint(*R["burst"])
            bt = beat_at(t)
            themes = R["themes"] + CFG["beat_themes"].get(bt, [])
            for _ in range(n):
                ev = {"t": t, "seed": rng.randint(0, 10 ** 9), "rot": rng.uniform(-CFG["motion"]["rotation_deg"], CFG["motion"]["rotation_deg"]),
                      "entry": R["entry"], "cut": rng.choices(list(c["cut_mix"]), weights=list(c["cut_mix"].values()))[0]}
                if rng.random() < c["swatch_share"] or (R.get("black_share") and rng.random() < R["black_share"]):
                    col = "#0b0a0a" if R.get("black_share") else rng.choice(CFG["colors"]["swatches"])
                    ev.update(kind="swatch", color=col, w=rng.uniform(0.25, 0.55) * W)
                else:
                    pid = self.pick(themes, rng) if rng.random() < c["relevance"] else rng.choice(list(POOL))
                    facey = bool(set(POOL[pid].get("themes", [])) & FACEY)
                    ev.update(kind="art", id=pid, w=rng.uniform(*c["size_px"]) * self.S, facey=facey)
                events.append(ev)
                t += rng.uniform(0.1, 0.25)
            t += rng.expovariate(1 / R["interval_s"]) * (1.0 if n == 1 else 1.4)
        # placement on the stalest area; respect TikTok zones for faces and the hero band while a hero holds
        grid = np.full((16, 9), -99.0)
        for ev in events:
            ev["dur"] = rng.uniform(*CFG["motion"]["piece_slide_s"]) if ev["entry"] == "slide" else CFG["motion"]["fade_drift_s"]
            hero_on = self.active_heroes(ev["t"] + 0.3)
            best, score = (0.5, 0.5), -1e9
            for _ in range(26):
                if ev.get("facey"):
                    x, y = rng.uniform(0.12, 0.72), rng.uniform(0.16, 0.7)
                else:
                    x, y = rng.uniform(0.02, 0.98), rng.uniform(0.02, 0.98)
                gx, gy = int(x * 8.99), int(y * 15.99)
                r = max(1, int(ev["w"] / W * 4))
                sc = -grid[max(0, gy - r):gy + r + 1, max(0, gx - r):gx + r + 1].mean() + rng.uniform(0, 0.5)
                if hero_on:
                    hw = ev["w"] / W / 2
                    band0, band1 = CFG["layout"]["hero_band"][0] / 1920, CFG["layout"]["hero_band"][1] / 1920
                    if y + hw * 0.8 > band0 and y - hw * 0.8 < band1:
                        sc -= 1000
                if sc > score:
                    best, score = (x, y), sc
            ev["x"], ev["y"] = best
            gx, gy = int(best[0] * 8.99), int(best[1] * 15.99)
            r = max(1, int(ev["w"] / W * 4))
            grid[max(0, gy - r):gy + r + 1, max(0, gx - r):gx + r + 1] = ev["t"]
            d = {"l": best[0], "r": 1 - best[0], "t": best[1], "b": 1 - best[1]}
            ev["edge"] = min(d, key=d.get)
        self.events = sorted(events, key=lambda e: e["t"])
        self.segs = self.segments()

    def make_piece(self, ev):
        if "img" in ev:
            return ev["img"]
        rng = random.Random(ev["seed"])
        if ev["kind"] == "swatch":
            w = int(ev["w"])
            h = int(w * rng.uniform(0.5, 1.4))
            col = hexrgb(ev["color"])
            im = Image.new("RGB", (w, h), col)
            if sum(col) < 200 and rng.random() < 0.6 and ev["color"] != "#0b0a0a":
                d = ImageDraw.Draw(im)
                for _ in range(int(w * h / 900)):
                    x, y = rng.uniform(0, w), rng.uniform(0, h)
                    r = rng.choice([0.6, 0.8, 1.0, 1.4, 2.0]) * self.S * 1.4
                    v = rng.randint(150, 255)
                    d.ellipse([x - r, y - r, x + r, y + r], fill=(v, v, int(v * 0.92)))
            out = im.convert("RGBA")
            out.putalpha(self.cut_mask(w, h, ev["cut"], rng))
        else:
            src = self.load_art(ev["id"])
            sw, sh = src.size
            area, asp = rng.uniform(0.35, 1.0), rng.uniform(0.6, 1.7)
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
        u = (t - ev["t"]) / ev["dur"]
        if ev["entry"] == "fade":
            return x + (1 - ease_out(u)) * 0.03 * self.W * (1 if ev["edge"] in "lt" else -1), y, ease(u)
        k = 1 - ease_out(u, 5)
        if ev["edge"] == "l":
            x -= k * (x + im.width + 20)
        elif ev["edge"] == "r":
            x += k * (self.W - x + 20)
        elif ev["edge"] == "t":
            y -= k * (y + im.height + 20)
        else:
            y += k * (self.H - y + 20)
        return x, y, 1.0

    def paste(self, frame, im, x, y, alpha=1.0):
        x, y = int(x), int(y)
        if im is None or x >= frame.width or y >= frame.height or x + im.width <= 0 or y + im.height <= 0:
            return
        if alpha < 0.999:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
        frame.alpha_composite(im, (max(0, x), max(0, y)), (max(0, -x), max(0, -y), min(im.width, frame.width - x), min(im.height, frame.height - y)))

    # ── collage canvas per segment (with snapshot for beat-change shards) ──
    def base_for(self, name, t):
        W, H = self.W, self.H
        if name == "title":
            return ImageOps.fit(self.title_img, (W, H), Image.LANCZOS, centering=(0.5, 0.35)).convert("RGBA")
        col = {"black": (8, 7, 8), "stark": (10, 10, 10), "rational": (14, 16, 30)}.get(name)
        if col is None:
            reg = register_at(t + 1.0)
            col = {"scripture": (22, 14, 12), "mythmaker": (34, 26, 18), "rational": (14, 16, 30), "labyrinth": (16, 14, 30),
                   "stark": (10, 10, 10), "prologue": (8, 7, 8)}.get(reg, (14, 12, 12))
        return Image.new("RGBA", (W, H), col + (255,))

    def segment_at(self, t):
        idx = max(i for i, (st, _) in enumerate(self.segs) if st <= t)
        return idx

    def canvas_at(self, t):
        """Baked collage canvas for time t (pieces fully landed), built incrementally when possible."""
        si = self.segment_at(t)
        st, name = self.segs[si]
        c = self._canvas
        if c is None or c["seg"] != si or t < c["t"]:
            c = {"seg": si, "t": st, "img": self.base_for(name, st), "i": 0}
            while c["i"] < len(self.events) and self.events[c["i"]]["t"] < st:
                c["i"] += 1
        while c["i"] < len(self.events):
            ev = self.events[c["i"]]
            if ev["t"] + ev["dur"] > t:
                break
            im = self.make_piece(ev)
            x, y, _ = self.piece_xy(ev, ev["t"] + ev["dur"] + 1)
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
            x, y, a = self.piece_xy(ev, t)
            self.paste(frame, im, x, y, a)
        # beat-change cascade: the previous segment's collage breaks into shards that slide out
        st, name = self.segs[c["seg"]]
        if name.startswith("beat") and t < st + CFG["motion"]["beat_change_s"]:
            for shard, (dx, dy), delay, (sx, sy) in self.shards(c["seg"]):
                u = (t - st - delay) / 0.38
                k = ease_in(u)
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
        seeds = [(rng.uniform(0, gw), rng.uniform(0, gh)) for _ in range(14)]
        yy, xx = np.mgrid[0:gh, 0:gw]
        dist = np.stack([(xx - sx) ** 2 + (yy - sy) ** 2 for sx, sy in seeds])
        lab = np.argmin(dist, axis=0)
        out = []
        for i, (sx, sy) in enumerate(seeds):
            m = Image.fromarray(((lab == i) * 255).astype(np.uint8)).resize((self.W, self.H), Image.NEAREST)
            bbox = m.getbbox()
            if not bbox:
                continue
            piece = snap.crop(bbox)
            piece.putalpha(m.crop(bbox))
            cx, cy = (bbox[0] + bbox[2]) / 2 / self.W, (bbox[1] + bbox[3]) / 2 / self.H
            d = {(-1, 0): cx, (1, 0): 1 - cx, (0, -1): cy, (0, 1): 1 - cy}
            out.append((piece, min(d, key=d.get), rng.uniform(0, 0.22), (bbox[0], bbox[1])))
        self._snap[seg] = out
        return out

    # ── grade ───────────────────────────────────────────────
    def vignette(self, strength):
        key = round(strength, 2)
        if key not in self.vignettes:
            yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
            r = np.sqrt(((xx - self.W / 2) / (self.W / 2)) ** 2 + ((yy - self.H / 2) / (self.H / 2)) ** 2)
            self.vignettes[key] = (1 - key * np.clip(r - 0.4, 0, 1) ** 1.5)[..., None]
        return self.vignettes[key]

    def grade(self, img, g):
        a = np.asarray(img.convert("RGB"), np.float32)
        lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
        ds = g["desaturate"]
        if g.get("keep_red"):
            red = np.clip((a[..., 0] - np.maximum(a[..., 1], a[..., 2])) / 80.0, 0, 1)
            k = (ds * (1 - red))[..., None]
        else:
            k = ds
        a = a * (1 - k) + lum[..., None] * k
        a = a * np.array([1 + g["warm"], 1.0, 1 - g["warm"]], np.float32)
        a = (a - 128) * g["contrast"] + 128
        a = a * g["darken"] * g["light"]
        if g["vignette"] > 0 and a.shape[0] == self.H and a.shape[1] == self.W:
            a = a * self.vignette(g["vignette"])
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")

    # ── heroes, ember, moments ──────────────────────────────
    def draw_heroes(self, frame, t, g):
        y0, y1 = [v * self.S for v in CFG["layout"]["hero_band"]]
        M = CFG["motion"]
        for h in self.active_heroes(t):
            src = self.hero_source(h["id"])
            n_share = 2 if h["x"] != 0.463 else 1
            maxw = (0.40 if n_share == 2 else 0.56) * self.W
            im = ImageOps.contain(src, (int(maxw), int((y1 - y0) * 0.96)), Image.LANCZOS)
            u = (t - h["t0"]) / M["hero_in_s"]
            hold = clamp((t - h["t0"]) / max(0.5, h["t1"] - h["t0"]))
            sc = (M["hero_settle_from"] + (1 - M["hero_settle_from"]) * ease_out(u)) * (1 + M["hero_push"] * hold)
            im = im.resize((max(2, int(im.width * sc)), max(2, int(im.height * sc))), Image.BILINEAR)
            cx = h["x"] * self.W
            x = cx - im.width / 2
            if u < 1:
                x += (-1 if h["x"] < 0.5 else 1) * (1 - ease_out(u, 4)) * self.W * 0.7
            y = y1 - im.height
            alpha = clamp(1 - (t - h["t1"]) / 0.4) if t > h["t1"] else 1.0
            hg = dict(g)
            hg.update(desaturate=g["desaturate"] * (0.95 if h["keep_red"] else 0.5), vignette=0, contrast=1.04,
                      darken=max(0.85, g["darken"]), light=1.0, keep_red=h["keep_red"])
            gim = self.grade(im, hg)
            gim.putalpha(im.getchannel("A"))
            self.paste(frame, gim, x, y, alpha)
        return frame

    def ember_target(self, t):
        hs = self.active_heroes(t)
        if hs:
            h = max(hs, key=lambda o: o["t0"])
            return (h["x"] * self.W, (CFG["layout"]["hero_band"][0] + 60) * self.S), h["t0"]
        for (t0, t1, pos) in self.ember_points:
            if t0 <= t < t1:
                return pos, t0
        return (0.46 * self.W, 1220 * self.S), 0.0

    def ember_pos(self, t):
        # smooth approach to the current target from the previous one
        (tx, ty), t0 = self.ember_target(t)
        (px, py), _ = self.ember_target(t0 - 0.05) if t0 > 0.05 else ((tx, ty), 0)
        k = ease((t - t0) / 1.4)
        x, y = px + (tx - px) * k, py + (ty - py) * k
        x += math.sin(t * 0.7) * 10 * self.S
        y += math.cos(t * 0.53) * 8 * self.S
        return x, y

    def draw_ember(self, frame, t, scale=1.0, flicker=0.0):
        x, y = self.ember_pos(t)
        pulse = 0.88 + 0.12 * math.sin(2 * math.pi * t / CFG["motion"]["ember_pulse_s"])
        if flicker:
            pulse *= 0.6 + 0.4 * abs(math.sin(t * 23)) * flicker + (1 - flicker) * 0.4
        e = RS.ember_sprite(int(150 * self.S * scale * pulse))
        self.paste(frame, e, x - e.width / 2, y - e.height / 2)

    # ── text ────────────────────────────────────────────────
    def build_text(self):
        tc, L = CFG["text"], CFG["layout"]
        S = self.S
        px = tc["size_px"] * S
        self.px = px
        x0, x1 = L["text_x"][0] * S, L["text_x"][1] * S
        pad = tc["pad_x_px"] * S
        strip_h = int(tc["strip_h_em"] * px)
        gap = tc["gap_px"] * S
        rng = random.Random(9)
        self.lines = []
        self.special_lines = []  # prologue / black-card lines (centred)
        for si, s in enumerate(SECS):
            y = 0.0
            for pi, ln in enumerate(s["lines"]):
                reg = ln["register"]
                toks, whole = tokens(ln["text"])
                on_black = (self.cut_black <= ln["start"] < self.black_end) or (ln["start"] >= self.final_black[0])
                if reg == "prologue" or on_black:
                    self.special_lines.append({"sec": si, "line": ln, "toks": tokens(ln["text"], force_italic=(reg == "prologue"))[0],
                                               "on_black": on_black, "t0": ln["start"] - 0.1})
                    continue
                rows = wrap(toks, px, (x1 - x0) - 2 * pad)
                total = sum(len(" ".join(w for w, _ in r)) for r in rows)
                acc = 0
                if pi and y > 0:
                    y += tc["para_gap_px"] * S
                xj = x0 + rng.uniform(-1, 1) * L["margin_jitter_px"] * S
                for r in rows:
                    t0 = ln["start"] + (ln["end"] - ln["start"]) * acc / max(1, total) - 0.05
                    acc += len(" ".join(w for w, _ in r)) + 1
                    img = self.render_strip(r, strip_h, inscription=whole)
                    self.lines.append({"sec": si, "y_rel": y, "x": xj, "t0": t0, "img": img, "reg": reg})
                    y += strip_h + gap
        top, bottom = L["text_y"][0] * S, L["text_y"][1] * S
        self.col_top = top
        self.scrolls = {si: [] for si in range(len(SECS))}
        for si in range(len(SECS)):
            off = 0.0
            mine = [l for l in self.lines if l["sec"] == si]
            for j, Lr in enumerate(mine):
                maxn = 4 if Lr["reg"] == "labyrinth" else L["max_strips"]
                need = top + Lr["y_rel"] + Lr["img"].height - bottom
                if j >= maxn:
                    need = max(need, mine[j - maxn + 1]["y_rel"])
                if need > off:
                    self.scrolls[si].append((Lr["t0"] - 0.05, need - off))
                    off = need

    def render_strip(self, row, strip_h, inscription=False):
        px = self.px
        pad = int(CFG["text"]["pad_x_px"] * self.S)
        tw = text_width(row, px)
        C = CFG["colors"]
        bg = hexrgb(C["inscription_bg"] if inscription else C["strip"])
        ink = hexrgb(C["inscription_ink"] if inscription else C["ink"])
        im = Image.new("RGBA", (int(tw + 2 * pad), strip_h), bg + (255,))
        draw_row(ImageDraw.Draw(im), pad, strip_h * 0.52, row, px, ink + (255,))
        return im

    def text_offset(self, si, t):
        off = sum(d * ease((t - ts) / CFG["motion"]["scroll_s"]) for ts, d in self.scrolls[si] if t > ts)
        if si + 1 < len(SECS):
            tn = SECS[si + 1]["start"] - CFG["motion"]["beat_change_s"] - 0.1
            if t > tn:
                off += self.H * 0.8 * ease_in((t - tn) / 0.5)
        return off

    def draw_text(self, frame, t, only_black=False):
        fade = CFG["layout"]["header_fade_px"] * self.S
        for Lr in ([] if only_black else self.lines):
            if t < Lr["t0"]:
                continue
            if Lr["sec"] + 1 < len(SECS) and t > SECS[Lr["sec"] + 1]["start"] + 0.2:
                continue
            y = self.col_top + Lr["y_rel"] - self.text_offset(Lr["sec"], t)
            a = clamp((y - (self.col_top - fade)) / fade)
            if a <= 0 or y > self.H:
                continue
            wipe = CFG["registers"][Lr["reg"]]["wipe_s"] or 0.15
            r = ease_out((t - Lr["t0"]) / wipe, 5)
            im = Lr["img"]
            if r < 1:
                im = im.crop((0, 0, max(1, int(im.width * r)), im.height))
            self.paste(frame, im, Lr["x"], y, a)
        # centred lines: prologue (italic, no strip) and lines on black
        groups = {}
        for sl in self.special_lines:
            groups.setdefault((sl["sec"], sl["on_black"]), []).append(sl)
        for (si, on_black), lst in groups.items():
            if only_black and not on_black:
                continue
            std = [l["t0"] for l in self.lines if l["sec"] == si]
            if not on_black and std and t >= min(std) - 0.3:
                continue
            shown = [sl for sl in lst if t >= sl["t0"]]
            if not shown:
                continue
            last_end = lst[-1]["line"]["end"]
            if on_black:
                if t > last_end + 2.6 and not (lst[-1]["line"]["start"] >= self.final_black[0]):
                    continue
                if lst[-1]["line"]["start"] >= self.final_black[0] and t >= self.endcard:
                    continue
            else:
                nxt = next((s["start"] for s in SECS if s["id"] > SECS[si]["id"]), DUR)
                if t > nxt - 0.4 or (SECS[si]["id"] == 0 and t >= self.cut_title):
                    if not (SECS[si]["id"] == 0 and len(shown) == len(lst) and t < T("s1.1")):
                        continue
            title_line = SECS[si]["id"] == 0 and t >= self.cut_title
            vis = [lst[-1]] if title_line else (shown[-4:] if not on_black else shown[-3:])
            px = (CFG["text"]["prologue_size_px"] if not on_black else 66) * self.S
            lh = px * 1.32
            if title_line:   # an inscription strip under the title box
                sl = lst[-1]
                rows = wrap(sl["toks"], self.px, 820 * self.S)
                y = 1360 * self.S
                for r in rows:
                    im = self.render_strip(r, int(CFG["text"]["strip_h_em"] * self.px), inscription=True)
                    self.paste(frame, im, 60 * self.S, y, ease((t - self.cut_title) / 0.4))
                    y += im.height + 8 * self.S
                continue
            blocks = []
            for j, sl in enumerate(vis):
                rows = wrap(sl["toks"], px, 820 * self.S)
                blocks.append((sl, rows))
            total = sum(len(r) * lh for _, r in blocks) + (len(blocks) - 1) * lh * 0.6
            ycur = ((600 if not on_black else 860) * self.S) - total / 2
            for j, (sl, rows) in enumerate(blocks):
                k = ease((t - sl["t0"]) / 0.9)
                old = 1.0 if j == len(blocks) - 1 else 0.6
                for r in rows:
                    tw = text_width(r, px)
                    img = Image.new("RGBA", (int(tw + 24), int(px * 1.6)), (0, 0, 0, 0))
                    draw_row(ImageDraw.Draw(img), 12, px * 0.8, r, px, hexrgb(CFG["colors"]["inscription_ink"]) + (255,))
                    sh = img.getchannel("A").filter(ImageFilter.GaussianBlur(7 * self.S))
                    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    shadow.putalpha(sh.point(lambda v: min(255, int(v * 1.6))))
                    xx = (self.W - 140 * self.S) / 2 - img.width / 2 + 30 * self.S
                    self.paste(frame, shadow, xx, ycur + 3, k * old)
                    self.paste(frame, img, xx, ycur, k * old)
                    ycur += lh
                ycur += lh * 0.6

    # ── tags & cards ────────────────────────────────────────
    def tag_img(self, text, bold=False):
        px = 30 * self.S
        f = font("b" if bold else "r", px)
        h = int(60 * self.S)
        pad = int(28 * self.S)
        im = Image.new("RGBA", (int(f.getlength(text) + 2 * pad), h), hexrgb(CFG["colors"]["strip"]) + (255,))
        ImageDraw.Draw(im).text((pad, h * 0.53), text, font=f, fill=hexrgb(CFG["colors"]["ink"]) + (255,), anchor="lm")
        return im

    def build_tags(self):
        self.tag_series = self.tag_img(CFG["series_name"], bold=True)
        self.tag_secs = {s["id"]: self.tag_img(s["tag"]) for s in SECS}

    def draw_tags(self, frame, t):
        if t < T("s1.1") - 0.2 or self.cut_black <= t < self.black_end or t >= self.final_black[0]:
            return
        y = 230 * self.S
        self.paste(frame, self.tag_series, 60 * self.S, y)
        bt = beat_at(t)
        im = self.tag_secs[bt]
        st = sec(bt)["start"] - 0.65
        k = ease_out((t - st) / 0.35, 4)
        if k < 1:
            im = im.crop((0, 0, max(1, int(im.width * k)), im.height))
        self.paste(frame, im, 0.45 * self.W, y)

    def build_cards(self):
        W, H, S = self.W, self.H, self.S
        # title box over Dürer (within TikTok safe area)
        box = Image.new("RGBA", (int(700 * S), int(300 * S)), hexrgb(CFG["colors"]["strip"]) + (255,))
        d = ImageDraw.Draw(box)
        px = 120 * S
        ink = hexrgb(CFG["colors"]["ink"]) + (255,)
        y = 24 * S
        for line in (CFG["title"]["line1"], CFG["title"]["line2"]):
            x = 48 * S
            for part in re.split(r"(\*[^*]+\*)", line):
                if not part:
                    continue
                f = font("ti" if part.startswith("*") else "t", px)
                d.text((x, y), part.strip("*"), font=f, fill=ink)
                x += f.getlength(part.strip("*"))
            y += px * 1.0
        self.title_box = box
        # end card: black, title (last word italic) + series name
        card = Image.new("RGBA", (W, H), (6, 5, 6, 255))
        d = ImageDraw.Draw(card)
        tpx = 104 * S
        lines = [CFG["title"]["line1"], CFG["title"]["line2"]]
        y = 760 * S
        for line in lines:
            parts = [p for p in re.split(r"(\*[^*]+\*)", line) if p]
            tw = sum(font("ti" if p.startswith("*") else "t", tpx).getlength(p.strip("*")) for p in parts)
            x = (W - 140 * S) / 2 - tw / 2 + 40 * S
            for p in parts:
                f = font("ti" if p.startswith("*") else "t", tpx)
                d.text((x, y), p.strip("*"), font=f, fill=hexrgb(CFG["colors"]["inscription_ink"]))
                x += f.getlength(p.strip("*"))
            y += tpx * 1.02
        f = font("r", 40 * S)
        sn = CFG["series_name"]
        d.text(((W - 140 * S) / 2 + 40 * S, y + 60 * S), sn, font=f, fill=hexrgb(CFG["colors"]["mark"]), anchor="mm")
        self.end_card = card

    # ── special moments ─────────────────────────────────────
    def feature(self, key, w_px, rot=0.0, source="pool", cut="rect"):
        ck = ("feat", key, int(w_px), round(rot, 1), cut)
        if ck in self._img:
            return self._img[ck]
        src = self.load_art(key) if source == "pool" else self.load_art_named(key)
        im = ImageOps.contain(src, (int(w_px), int(w_px * 1.5))).convert("RGBA")
        im.putalpha(self.cut_mask(im.width, im.height, cut, random.Random(hash(ck) % 999)))
        if rot:
            im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        self._img[ck] = im
        return im

    def load_art_named(self, key):
        k = "named::" + key
        if k not in self._img:
            im = ImageOps.exif_transpose(Image.open(ROOT / NAMED[key]["local"])).convert("RGB")
            im.thumbnail((1600, 1600), Image.LANCZOS)
            self._img[k] = im
        return self._img[k]

    def setup_moments(self):
        rng = random.Random(77)
        S, W = self.S, self.W
        self.m_hands = [self.pick_query("hand anatomy", rng) or self.pick(["hands"], rng) for _ in range(6)]
        self.m_hands = [self.pick(["hands"], rng) for _ in range(6)]
        self.m_faces = []
        faces_pool = [k for k in BY_THEME.get("faces", []) + BY_THEME.get("portrait", [])]
        rng.shuffle(faces_pool)
        self.m_faces = faces_pool[:8]
        self.m_costume = [self.pick(["costume"], rng) for _ in range(3)]
        self.m_burn = self.pick_query("burning books", rng) or self.pick(["fire"], rng)
        self.m_masks0 = [self.pick(["faces"], rng) for _ in range(5)]
        self.m_dragon = self.pick_query("Saint George dragon", rng) or self.pick(["dragon"], rng)
        self.m_eyes = [self.pick_query("octopus", rng) or self.pick(["eyes"], rng), self.pick_query("eye anatomy", rng) or self.pick(["eyes"], rng)]
        self.m_wings = [self.pick_query("insect wings", rng), self.pick_query("bird wing", rng), self.pick_query("bat", rng)]
        self.m_wings = [w or self.pick(["wings"], rng) for w in self.m_wings]
        self.m_virtues = [self.pick_query(q, rng) or self.pick(["emblem"], rng) for q in ("anchor emblem hope", "kneeling figure", "telescope", "scales balance", "lion")]
        self.m_wall = self.pick_query("castle walls", rng) or self.pick(["walls"], rng)
        self.m_portrait = self.pick(["portrait"], rng)
        self.m_torch = self.pick_query("torch race runners", rng) or self.pick(["tradition"], rng)
        self.m_tree = self.pick_query("tree of knowledge", rng) or self.pick(["tree"], rng)
        cur = D3 / "moments.yaml"
        if cur.exists():   # curated picks override the search-based ones
            M = yaml.safe_load(cur.read_text())
            ok = lambda lst: [k for k in lst if k in POOL]  # noqa: E731
            if ok(M.get("hands", [])): self.m_hands = (ok(M["hands"]) * 3)[:6]
            if ok(M.get("faces", [])): self.m_faces = ok(M["faces"])[:8]
            if ok(M.get("costume", [])): self.m_costume = ok(M["costume"])
            if ok(M.get("masks0", [])): self.m_masks0 = ok(M["masks0"])
            for attr, key in (("m_burn", "burn"), ("m_dragon", "dragon"), ("m_wall", "wall"), ("m_portrait", "portrait"), ("m_tree", "tree"), ("m_torch", "torch")):
                if ok(M.get(key, [])): setattr(self, attr, ok(M[key])[0])
            if ok(M.get("eyes", [])): self.m_eyes = ok(M["eyes"])
            if ok(M.get("wings", [])): self.m_wings = ok(M["wings"])
            if ok(M.get("virtues", [])): self.m_virtues = ok(M["virtues"])
        # ember points (where the ember goes when no hero holds)
        b = self.H / 1920
        self.ember_points = [
            (T("s0.3"), T("s0.4"), (0.30 * W, 1180 * b)), (T("s0.4"), T("s0.5"), (0.62 * W, 1150 * b)),
            (T("s0.5"), T("s0.6"), (0.36 * W, 1220 * b)), (T("s0.6"), T("s0.7"), (0.58 * W, 1190 * b)),
            (T("s1.6"), T("s1.8e"), (0.43 * W, 1220 * b)),
            (T("s4.10"), T("s4.10e"), (0.43 * W, 1220 * b)),
            (T("s9.7"), T("s9.8e"), (0.43 * W, 1150 * b)),
            (T("s10.5"), T("s10.6"), (0.25 * W, 1200 * b)), (T("s10.6"), T("s10.7e"), (0.66 * W, 1200 * b)),
            (T("s12.4"), T("s12.4e"), (0.30 * W, 1200 * b)), (T("s12.5"), T("s12.5e"), (0.62 * W, 1200 * b)),
        ]

    def band_xy(self, fx, h_img):
        y1 = CFG["layout"]["hero_band"][1] * self.S
        return fx * self.W, y1 - h_img

    def moments(self, frame, t, g):
        S, W, H = self.S, self.W, self.H
        b0, b1 = [v * S for v in CFG["layout"]["hero_band"]]
        bh = b1 - b0
        gr = lambda im: self.graded_feature(im, g)  # noqa: E731

        def land(im, cx, t0, edge=-1, dur=0.5, alpha=1.0, y=None):
            u = (t - t0) / dur
            if u < 0:
                return
            x = cx - im.width / 2 + edge * (1 - ease_out(u, 4)) * W * 0.8
            yy = (b1 - im.height) if y is None else y
            self.paste(frame, im, x, yy, alpha)

        # beat 0: hands receiving the ember; burning pages; masks gather
        for i, ref in enumerate(("s0.3", "s0.4", "s0.5", "s0.6")):
            t0 = T(ref) - 0.3
            if t0 <= t < self.cut_title:
                im = gr(self.feature(self.m_hands[i], 360 * S, rot=(-4 + 3 * i)))
                xs = (0.30, 0.62, 0.36, 0.58)[i]
                a = ease((t - t0) / 1.2) * (0.55 if t > T(("s0.4", "s0.5", "s0.6", "s0.7")[i]) + 0.5 else 1)
                self.paste(frame, im, xs * W - im.width / 2, (1240 - 60 * (i % 2)) * S - im.height / 2, a)
        if T("s0.8") - 0.3 <= t < self.cut_title:
            im = gr(self.feature(self.m_burn, 520 * S, rot=2))
            a = ease((t - T("s0.8") + 0.3) / 1.2)
            self.paste(frame, im, 0.45 * W - im.width / 2, 520 * S, a * 0.9)
            fl = 0.5 + 0.5 * math.sin(t * 11) * math.sin(t * 7.3)
            glow = Image.new("RGBA", (W, H), (255, 120, 30, int(40 * a * fl)))
            frame.alpha_composite(glow)
        if T("s0.11") - 0.2 <= t < self.cut_title:
            for i, k in enumerate(self.m_masks0):
                t0 = T("s0.11") + i * 0.32
                if t >= t0:
                    im = gr(self.feature(k, 220 * S, rot=(-6 + 3 * i)))
                    self.paste(frame, im, (0.16 + 0.15 * i) * W - im.width / 2, (420 + 90 * (i % 2)) * S, ease((t - t0) / 0.8))
        # beat 1: eight faces in one second on "infinite"; costume plates
        if T("s1.6") - 0.1 <= t < SECS[2]["start"] - 0.7:
            for i, k in enumerate(self.m_faces):
                t0 = T("s1.6") + i * 0.125
                if t < t0:
                    continue
                im = gr(self.feature(k, 230 * S, rot=(-5 + (i % 3) * 5)))
                col, row = i % 4, i // 4
                cx = (0.14 + 0.21 * col) * W
                cy = b0 + (0.27 + 0.5 * row) * bh
                land(im, cx, t0, edge=(-1 if col < 2 else 1), dur=0.25, y=cy - im.height / 2)
        if T("s1.7") <= t < SECS[2]["start"] - 0.7:
            for i, k in enumerate(self.m_costume):
                t0 = T("s1.7") + i * 0.4
                im = gr(self.feature(k, 260 * S, rot=(-3 + 3 * i)))
                land(im, (0.2 + 0.28 * i) * W, t0, edge=1, dur=0.4, y=b0 - im.height * 0.55)
        # beat 2: Campbell's circle drawn as a ring, opening into the mark (around Gilgamesh)
        if T("s2.3") - 0.2 <= t < T("s2.5"):
            p = ease((t - T("s2.3")) / 2.2)
            opening = ease((t - T("s2.4")) / 0.9)
            size = int(bh * 1.02)
            gap = 0.5 + 47.5 * opening
            m = RS.draw_mark(size, hexrgb(CFG["colors"]["mark"]), progress=max(0.01, p), gap_deg=gap)
            if opening < 0.99:
                m = RS.draw_mark(size, hexrgb(CFG["colors"]["mark"]), progress=max(0.01, p) * (1 if opening <= 0 else 1), gap_deg=gap)
            self.paste(frame, m, 0.463 * W - m.width / 2, (b0 + bh / 2) - m.height / 2, 0.95)
        # the dragon being learned: label lines draw across a St George dragon engraving
        if T("s2.10") - 0.3 <= t < SECS[3]["start"] - 0.7:
            im = gr(self.feature(self.m_dragon, 760 * S, cut="rect"))
            u = (t - T("s2.10") + 0.3) / 0.6
            x = 0.463 * W - im.width / 2 + (1 - ease_out(u, 4)) * W
            y = b1 - im.height if im.height < bh * 1.3 else b0 - (im.height - bh) * 0.6
            y = max(y, 1000 * S - im.height * 0.25)
            self.paste(frame, im, x, y)
            lp = clamp((t - T("s2.10") - 0.6) / 2.8)
            if lp > 0:
                d = ImageDraw.Draw(frame)
                rng = random.Random(3)
                col = hexrgb(CFG["colors"]["mark"]) + (255,)
                dark = (10, 8, 6, 255)
                for k in range(6):
                    kp = clamp(lp * 6 - k)
                    if kp <= 0:
                        continue
                    ax, ay = x + im.width * rng.uniform(0.2, 0.8), y + im.height * rng.uniform(0.25, 0.8)
                    side = -1 if k % 2 == 0 else 1
                    bx = x + (im.width + 40 * S if side > 0 else -40 * S)
                    bx = min(max(bx, 70 * S), W - 210 * S)
                    by = y + im.height * (0.15 + 0.14 * k)
                    ex, ey = ax + (bx - ax) * kp, ay + (by - ay) * kp
                    d.line([(ax, ay), (ex, ey)], fill=dark, width=max(2, int(6 * S)))
                    d.line([(ax, ay), (ex, ey)], fill=col, width=max(1, int(3 * S)))
                    d.ellipse([ax - 7 * S, ay - 7 * S, ax + 7 * S, ay + 7 * S], fill=col, outline=dark, width=max(1, int(2 * S)))
                    if kp >= 1:
                        lx = bx + (22 if side > 0 else -22) * S
                        d.rectangle([lx - 20 * S, by - 24 * S, lx + 20 * S, by + 24 * S], fill=hexrgb(CFG["colors"]["strip"]) + (255,))
                        d.text((lx, by), "ABCDEF"[k], font=font("i", 36 * S), fill=hexrgb(CFG["colors"]["ink"]) + (255,), anchor="mm")
        # beat 3: paired eye plates from opposite edges; wings; beat 1's masks return aligned
        if T("s3.3") - 0.2 <= t < T("s3.4"):
            for i, k in enumerate(self.m_eyes):
                im = gr(self.feature(k, 400 * S, cut="rect"))
                land(im, (0.25 + 0.42 * i) * W, T("s3.3") - 0.1, edge=(-1 if i == 0 else 1), dur=0.6)
        if T("s3.4") - 0.2 <= t < T("s3.7"):
            for i, k in enumerate(self.m_wings):
                im = gr(self.feature(k, 300 * S, cut="rect"))
                land(im, (0.17 + 0.29 * i) * W, T("s3.4") + 0.25 * i, edge=(-1, 1, -1)[i], dur=0.45)
        if T("s3.8") - 0.1 <= t < SECS[4]["start"] - 0.7:
            for i, k in enumerate(self.m_faces):
                t0 = T("s3.8") + i * 0.06
                im = gr(self.feature(k, 190 * S, rot=0))
                col, row = i % 4, i // 4
                land(im, (0.13 + 0.21 * col) * W, t0, edge=(-1 if col < 2 else 1), dur=0.35, y=b0 + (0.05 + 0.5 * row) * bh)
        # beat 4: five virtue emblems; the mark as the cycle with the ember travelling round once
        for i, k in enumerate(self.m_virtues):
            t0 = T(f"s4.{5 + i}") - 0.1
            if t0 <= t < T("s4.10") - 0.2:
                im = gr(self.feature(k, 200 * S, cut="poly"))
                land(im, (0.11 + 0.175 * i) * W, t0, edge=1, dur=0.4, y=b0 + bh * (0.18 + 0.2 * (i % 2)))
        if T("s4.10") - 0.3 <= t < T("s4.11"):
            size = int(bh * 0.92)
            p = ease((t - T("s4.10") + 0.3) / 0.8)
            m = RS.draw_mark(size, hexrgb(CFG["colors"]["mark"]), progress=max(0.01, p))
            cx, cy = 0.43 * W, b0 + bh / 2
            self.paste(frame, m, cx - m.width / 2, cy - m.height / 2)
            if p >= 0.99:
                d = ImageDraw.Draw(frame)
                r = size * 0.5
                for j, word in enumerate(("problem", "guess", "error", "correction")):
                    a = math.radians(-90 + 90 * j)
                    lx, ly = cx + (r + 34 * S) * math.cos(a), cy + (r + 34 * S) * math.sin(a)
                    tw = font("i", 34 * S).getlength(word)
                    anchor = "mm"
                    if j == 1:
                        lx = min(lx + tw / 2, W - 170 * S - tw / 2)
                    if j == 3:
                        lx = max(lx - tw / 2, 70 * S + tw / 2)
                    strip = Image.new("RGBA", (int(tw + 24 * S), int(50 * S)), hexrgb(CFG["colors"]["strip"]) + (255,))
                    ImageDraw.Draw(strip).text((12 * S, 25 * S), word, font=font("i", 34 * S), fill=hexrgb(CFG["colors"]["ink"]) + (255,), anchor="lm")
                    self.paste(frame, strip, lx - strip.width / 2, ly - strip.height / 2)
                # the ember travels round the ring once over the line
                u = clamp((t - T("s4.10") - 0.4) / max(0.5, T("s4.10e") - T("s4.10") - 0.4))
                a = math.radians(-90 + 24 + (360 - 48) * u)
                e = RS.ember_sprite(int(130 * S))
                self.paste(frame, e, cx + r * 0.86 * math.cos(a) - e.width / 2, cy + r * 0.86 * math.sin(a) - e.height / 2)
        # beat 6: "I was wrong" — black space around the line
        if T("s6.6") - 0.2 <= t < T("s6.6e") + 0.6:
            k = ease((t - T("s6.6") + 0.2) / 0.5) * (1 - ease((t - T("s6.6e") - 0.1) / 0.5))
            frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(200 * k))))
        # beat 7: the mark alone; a crack runs through it, then mends with a thin gold seam
        if SECS[7]["start"] - 0.3 <= t < self.cut_black:
            dk = ease((t - SECS[7]["start"] + 0.3) / 0.8)
            frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(150 * dk))))
            crack = ease((t - T("s7.2")) / 0.9)
            seam = ease((t - T("s7.3")) / 3.5)
            m = RS.draw_mark(int(560 * S), hexrgb(CFG["colors"]["mark"]), crack=crack, seam=seam)
            self.paste(frame, m, 0.43 * W - m.width / 2, (b0 + bh / 2) - m.height / 2, dk)
        # beat 8: wall stones slide out on "no wall holds"
        if T("s8.3") - 0.3 <= t < T("s8.6"):
            wall = gr(self.feature(self.m_wall, 780 * S, cut="rect"))
            x0 = 0.43 * W - wall.width / 2
            y0 = b1 - min(wall.height, bh)
            wall = wall.crop((0, 0, wall.width, min(wall.height, int(bh))))
            ts = T("s8.4") + 0.2
            if t < ts:
                land(wall, 0.43 * W, T("s8.3") - 0.3, edge=1, dur=0.6, y=y0)
            else:
                cols, rows = 6, 4
                bw, bhh = wall.width / cols, wall.height / rows
                rng = random.Random(8)
                for r in range(rows):
                    for cidx in range(cols + 1):
                        ox = (bw / 2 if r % 2 else 0)
                        xa = int(cidx * bw - ox)
                        xb = int(min(wall.width, xa + bw))
                        xa = max(0, xa)
                        if xb - xa < 4:
                            continue
                        brick = wall.crop((xa, int(r * bhh), xb, int((r + 1) * bhh)))
                        delay = rng.uniform(0, 1.2)
                        k = ease_in((t - ts - delay) / 0.5)
                        dirx = -1 if (xa + xb) / 2 < wall.width / 2 else 1
                        self.paste(frame, brick, x0 + xa + dirx * k * W, y0 + r * bhh + k * 80 * S * (r - 1.5), 1 - 0.3 * k)
        # beat 9: the ember flickers on an anonymous portrait on "for one moment"
        if T("s9.7") - 0.4 <= t < SECS[10]["start"] - 0.7:
            im = gr(self.feature(self.m_portrait, 330 * S, cut="poly"))
            k = ease((t - T("s9.7") + 0.4) / 0.6) * (1 - ease((t - T("s9.8e")) / 0.6))
            self.paste(frame, im, 0.43 * W - im.width / 2, b1 - im.height, k)
        # beat 10: torch race; the ember passed between engraved hands; tree of knowledge
        if T("s10.5") - 0.4 <= t < SECS[11]["start"] - 0.7:
            for i, k in enumerate(self.m_hands[4:6]):
                im = gr(self.feature(k, 330 * S, rot=(-5 if i == 0 else 5)))
                land(im, (0.25 if i == 0 else 0.66) * W, T("s10.5") - 0.4 + 0.3 * i, edge=(-1 if i == 0 else 1), dur=0.5)
        if T("s10.7") - 0.3 <= t < SECS[11]["start"] - 0.7:
            im = gr(self.feature(self.m_tree, 420 * S, cut="poly"))
            land(im, 0.46 * W, T("s10.7") - 0.3, edge=1, dur=0.5, y=b0 - im.height * 0.5)
        # beat 11: accelerating face cascade; Flammarion engraving on "edge of the map"
        for ev in self.cascade:
            if ev["t"] <= t < T("s11.8") + 0.2:
                if "hero" in ev:
                    src = self.hero_source(ev["hero"])
                    im = ImageOps.contain(src, (int(ev["w"] * W), int(ev["w"] * W * 1.4)))
                    gim = self.graded_feature(im, g, mild=True)
                    gim.putalpha(im.getchannel("A"))
                    im = gim
                else:
                    im = gr(self.feature(ev["art"], ev["w"] * W, rot=ev["rot"], cut="rect"))
                land(im, ev["x"] * W, ev["t"], edge=(-1 if ev["x"] < 0.5 else 1), dur=0.3, y=ev["y"] * H - im.height / 2)
        if "flammarion" in NAMED and T("s11.8") - 0.2 <= t < SECS[12]["start"] - 0.7:
            fl = self.load_art_named("flammarion")
            u = ease((t - T("s11.8") + 0.2) / 0.8)
            # starfield beyond the sky, then the engraving
            star = self.starfield()
            self.paste(frame, star, 0, 0, u)
            im = ImageOps.contain(fl, (int(0.80 * W), int(0.56 * H))).convert("RGBA")
            im = self.graded_feature(im, dict(g, light=g["light"] * 1.05))
            self.paste(frame, im, 0.435 * W - im.width / 2, (b1 - im.height) + (1 - u) * 120 * S, u)
        # beat 12: ember passes hand to hand once more
        if T("s12.4") - 0.4 <= t < self.final_black[0]:
            for i, k in enumerate(self.m_hands[:2]):
                im = gr(self.feature(k, 330 * S, rot=(-5 if i == 0 else 5)))
                land(im, (0.30 if i == 0 else 0.62) * W, T("s12.4") - 0.4 + 0.3 * i, edge=(-1 if i == 0 else 1), dur=0.5)
        return frame

    def graded_feature(self, im, g, mild=False):
        hg = dict(g)
        hg.update(vignette=0, light=min(1.15, g["light"] * (1.05 if not mild else 1.1)), darken=max(0.7, g["darken"] * 1.1))
        out = self.grade(im, hg)
        out.putalpha(im.getchannel("A"))
        return out

    @lru_cache(maxsize=2)
    def starfield(self):
        im = Image.new("RGBA", (self.W, self.H), (8, 10, 24, 255))
        d = ImageDraw.Draw(im)
        rng = random.Random(42)
        for _ in range(int(self.W * self.H / 1400)):
            x, y = rng.uniform(0, self.W), rng.uniform(0, self.H)
            r = rng.choice([0.6, 0.8, 1.0, 1.3, 2.2]) * self.S * 1.5
            v = rng.randint(140, 255)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(v, v, int(v * 0.9), 255))
        return im

    # ── the stack ───────────────────────────────────────────
    def get_stack(self):
        if self.stack is None:
            heroes = [self.hero_source(h) for h in ["link_botw", "guts", "aragorn", "nausicaa", "master_chief", "gilgamesh", "frodo", "sam",
                                                     "goku", "naruto", "kusanagi", "heracles", "zelda", "gandalf", "link_oot"]]
            heroes = [h for h in heroes if h is not None]
            rng = random.Random(5)
            named = [k for k in POOL if POOL[k].get("query") in ("fludd", "michelspacher", "remmelin", "flap_sheet", "valentine", "bell_symbols")]
            others = [k for th in ("library", "labyrinth", "stars", "esoteric", "cosmos") for k in BY_THEME.get(th, []) if k not in named]
            arts = [self.load_art(k, 700) for k in named + rng.sample(others, min(28, len(others)))]
            dore = self.load_art_named("dore_paradiso_31") if "dore_paradiso_31" in NAMED else None
            if dore is None:
                dore = self.procedural_light()
            self.stack = RS.Stack(self.W, self.H, heroes, arts, dore=dore, mark_color=hexrgb(CFG["colors"]["mark"]))
        return self.stack

    def procedural_light(self):
        """Stand-in for Doré's Empyrean if the engraving is unavailable: rings of light round an empty centre."""
        W, H = self.W, self.H
        im = Image.new("RGB", (W, H), (20, 16, 24))
        d = ImageDraw.Draw(im)
        cx, cy = W / 2, H * 0.22
        for i in range(40, 0, -1):
            r = i * W * 0.03
            v = int(255 * (1 - i / 42) ** 1.6)
            d.ellipse([cx - r, cy - r * 0.7, cx + r, cy + r * 0.7], fill=(v, int(v * 0.9), int(v * 0.7)))
        return im.filter(ImageFilter.GaussianBlur(W * 0.01))

    def stack_frame(self, t):
        st = self.get_stack()
        if self.reprise[0] <= t < self.reprise[1]:
            dur = self.reprise[1] - self.reprise[0]
            fr = st.frame(t - self.reprise[0], RS.default_plan(dur, reprise=True))
        else:
            dur = self.stack_end - self.cut_stack
            fr = st.frame(t - self.cut_stack, self.stack_plan())
        return fr

    def stack_plan(self):
        o = self.cut_stack
        return {"hold": (T("s5.2") - o, T("s5.3") - o), "pull": (T("s5.3") - o, T("s5.3e") - o), "fan": (T("s5.4") - o, T("s5.4e") + 0.4 - o),
                "align": (T("s5.5") - o, T("s5.6e") - o), "tilt": (T("s5.7") - o, T("s5.9e") - o), "rise": (T("s5.10") - o, self.stack_end - o + 3)}

    def title_frame(self, t, box_alpha=1.0):
        g = grade_at(t)
        frame = self.grade(self.base_for("title", t), dict(g, light=1.0, darken=0.9, vignette=0.4, desaturate=0.1))
        if box_alpha > 0:
            self.paste(frame, self.title_box, 60 * self.S, 1030 * self.S, box_alpha)
        self.draw_ember(frame, t, scale=0.6)
        self.draw_text(frame, t)
        return frame

    # ── frame ───────────────────────────────────────────────
    def frame(self, t):
        if not hasattr(self, "ember_points"):
            self.setup_moments()
        W, H = self.W, self.H
        if t >= self.endcard:
            return np.asarray(self.end_card.convert("RGB"))
        g = grade_at(t)
        if self.cut_black <= t < self.black_end:
            frame = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            self.draw_ember(frame, t, scale=0.55)
            self.draw_text(frame, t, only_black=True)
            return np.asarray(frame.convert("RGB"))
        in_stack = self.cut_stack <= t < self.stack_end
        in_reprise = self.reprise[0] <= t < self.reprise[1]
        t_title_end = T("s1.1") - 0.2
        if self.cut_title <= t < t_title_end:
            return np.asarray(self.title_frame(t).convert("RGB"))
        if in_stack:
            frame = self.stack_frame(t)
        else:
            frame = self.grade(self.collage_frame(t), g)
            frame = self.moments(frame, t, g)
            frame = self.draw_heroes(frame, t, g)
            if t_title_end <= t < t_title_end + 1.0:      # dissolve from the title card into the collage
                tf = self.title_frame(t_title_end - 1e-3, box_alpha=1 - ease((t - t_title_end) / 0.6))
                tf.putalpha(int(255 * (1 - ease((t - t_title_end) / 1.0))))
                frame.alpha_composite(tf)
            if self.stack_end <= t < self.stack_end + 1.0:  # dissolve out of the stack (not a cut)
                sf = self.stack_frame(self.stack_end - 1e-3)
                sf.putalpha(int(255 * (1 - ease((t - self.stack_end) / 1.0))))
                frame.alpha_composite(sf)
            if in_reprise:
                k = ease((t - self.reprise[0]) / 1.3) * (1 - ease((t - self.reprise[1] + 1.2) / 1.2))
                sf = self.stack_frame(min(t, self.reprise[1] - 1e-3))
                sf.putalpha(int(255 * k))
                frame.alpha_composite(sf)
            if t >= self.final_black[0]:
                k = ease((t - self.final_black[0]) / 0.9)
                frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * k))))
        if not in_stack:
            self.draw_ember(frame, t, flicker=(1.0 if T("s9.7") <= t < T("s9.8e") else 0.0))
        self.draw_text(frame, t, only_black=(t >= self.final_black[0] + 0.6))
        self.draw_tags(frame, t)
        return np.asarray(frame.convert("RGB"))


# ── audio mix ───────────────────────────────────────────────
def mix_audio(out_wav):
    vo_user = ROOT / "assets" / "voiceover_draft3.wav"
    vo = vo_user if vo_user.exists() else D3 / "build" / "vo.wav"
    music_user = ROOT / CFG["music"]["file"]
    sound = D3 / "build" / "sound_bed.wav"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_sound_v3.py")] + ([str(music_user)] if music_user.exists() else []), check=True)
    m = CFG["music"]
    parts = [f"between(t,{ln['start'] - m['duck_attack']:.2f},{ln['end'] + m['duck_release']:.2f})" for s in SECS for ln in s["lines"]]
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
        refs = [a for a in args[1:] if a != "--safe"]
        R = Renderer("final")
        for ref in sorted(refs, key=T):
            img = Image.fromarray(R.frame(T(ref)))
            if safe:
                img = overlay_safe(img)
            out = D3 / "build" / f"still_{ref}{'_safe' if safe else ''}.png"
            img.save(out)
            print(out.relative_to(ROOT), f"t={T(ref):.2f}")
        if MISSING:
            print("missing hero images:", sorted(MISSING))
        return
    from moviepy.editor import AudioFileClip, VideoClip
    R = Renderer(mode)
    wav = D3 / "build" / "mix.wav"
    mix_audio(wav)
    o = CFG["output"][mode]
    out = ROOT / o["file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    VideoClip(R.frame, duration=DUR).set_audio(AudioFileClip(str(wav), fps=48000)).write_videofile(
        str(out), fps=R.fps, codec="libx264", audio_codec="aac", audio_bitrate="192k", audio_fps=48000, preset=o["preset"],
        ffmpeg_params=["-crf", str(o["crf"]), "-pix_fmt", "yuv420p", "-movflags", "+faststart"], threads=4, logger=None)
    print("wrote", out.relative_to(ROOT))
    if MISSING:
        print("missing hero images:", sorted(MISSING))


def overlay_safe(img):
    W, H = img.size
    s = W / 1080
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    red = (255, 0, 60, 70)
    d.rectangle([0, 0, W, 220 * s], fill=red)
    d.rectangle([0, H - 480 * s, W, H], fill=red)
    d.rectangle([W - 140 * s, 0, W, H], fill=red)
    out = img.convert("RGBA")
    out.alpha_composite(ov)
    return out.convert("RGB")


if __name__ == "__main__":
    main()
