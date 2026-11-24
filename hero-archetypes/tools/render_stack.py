"""The stack sequence (draft 3, beat 5; reprised in beat 12).

One hero with the mark → pull back into a lineage collage of heroes, each with a varied mark →
the collage becomes a translucent pane; 12–20 panes fan out in depth (multiplane parallax) →
the worlds scatter, the marks snap into one column of light → the camera tilts up the column
towards Doré's light, stopping short → it keeps rising as new panes appear above.

Pseudo-3D: panes are horizontal sheets stacked along the world y axis, projected with a pinhole
camera and drawn with perspective warps (PIL), back to front, translucent.
Usage (standalone test): python tools/render_stack.py <seconds_into_scene> [reprise]
"""
import math
import random
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


# ── the mark: open ring + arrowhead (the cycle as one stroke, never closed) ──
def draw_mark(size, color=(232, 163, 61), progress=1.0, width_frac=0.075, gap_deg=48, rot=0.0, glow=True, crack=0.0, seam=0.0):
    """RGBA image of the mark. progress 0..1 draws the stroke; crack/seam 0..1 animate beat 7."""
    S = int(size)
    pad = int(S * 0.25)
    W = S + 2 * pad
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(2, int(S * width_frac))
    box = [pad + w, pad + w, pad + S - w, pad + S - w]
    start = -90 + gap_deg / 2 + rot
    sweep = (360 - gap_deg) * max(0.0, min(1.0, progress))
    if sweep > 1:
        d.arc(box, start, start + sweep, fill=color + (255,), width=w)
        if progress >= 0.999:
            a = math.radians(start + sweep)
            cx, cy, r = W / 2, W / 2, (S - 2 * w) / 2
            hx, hy = cx + r * math.cos(a), cy + r * math.sin(a)
            tx, ty = -math.sin(a), math.cos(a)          # tangent (direction of travel)
            nx, ny = math.cos(a), math.sin(a)
            L = w * 2.6
            d.polygon([(hx + tx * L, hy + ty * L), (hx + nx * L * 0.75, hy + ny * L * 0.75), (hx - nx * L * 0.75, hy - ny * L * 0.75)],
                      fill=color + (255,))
    if crack > 0:   # a jagged crack across the ring (black), then a gold seam over it
        pts = []
        rng = random.Random(7)
        for i in range(9):
            f = i / 8
            pts.append((pad + S * (0.18 + 0.64 * f) + rng.uniform(-S * 0.05, S * 0.05), pad + S * (0.12 + 0.76 * f)))
        n = max(2, int(len(pts) * min(1.0, crack)))
        d.line(pts[:n], fill=(8, 6, 5, 255), width=max(2, int(w * 0.55)))
        if seam > 0:
            m = max(2, int(len(pts) * min(1.0, seam)))
            d.line(pts[:m], fill=(240, 194, 90, 255), width=max(1, int(w * 0.28)))
    if glow:
        g = im.getchannel("A").filter(ImageFilter.GaussianBlur(S * 0.06))
        glow_im = Image.new("RGBA", im.size, color + (0,))
        glow_im.putalpha(g.point(lambda v: int(v * 0.8)))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.alpha_composite(glow_im)
        out.alpha_composite(im)
        im = out
    return im


@lru_cache(maxsize=8)
def ember_sprite(size, core=(255, 241, 201), glow=(255, 154, 46)):
    S = int(size)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    r = np.sqrt((xx - S / 2) ** 2 + (yy - S / 2) ** 2) / (S / 2)
    a_glow = np.clip(1 - r, 0, 1) ** 2.2
    a_core = np.clip(1 - r * 4.2, 0, 1) ** 1.5
    rgb = np.zeros((S, S, 3), np.float32)
    for c in range(3):
        rgb[..., c] = glow[c] * a_glow + (core[c] - glow[c]) * a_core
    a = np.clip(a_glow * 0.85 + a_core, 0, 1)
    im = np.dstack([np.clip(rgb / np.maximum(a[..., None], 1e-3), 0, 255), a * 255]).astype(np.uint8)
    return Image.fromarray(im, "RGBA")


# ── perspective helpers ─────────────────────────────────────
def perspective_coeffs(dst, src):
    """Coefficients mapping output (dst quad) → input (src quad), for Image.transform PERSPECTIVE."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def warp_onto(frame, tex, quad, alpha=1.0):
    """Paste RGBA texture `tex` onto `frame` inside screen quad [(x,y)×4: tl,tr,br,bl]."""
    xs, ys = [p[0] for p in quad], [p[1] for p in quad]
    x0, y0, x1, y1 = int(math.floor(min(xs))), int(math.floor(min(ys))), int(math.ceil(max(xs))), int(math.ceil(max(ys)))
    if x1 < 0 or y1 < 0 or x0 > frame.width or y0 > frame.height or x1 - x0 < 2 or y1 - y0 < 2:
        return
    if (x1 - x0) * (y1 - y0) > frame.width * frame.height * 6:
        return
    local = [(x - x0, y - y0) for x, y in quad]
    tw, th = tex.size
    try:
        c = perspective_coeffs(local, [(0, 0), (tw, 0), (tw, th), (0, th)])
    except np.linalg.LinAlgError:
        return
    out = tex.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, c, Image.BILINEAR)
    if alpha < 0.999:
        out.putalpha(out.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(out, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0), min(out.width, frame.width - x0), min(out.height, frame.height - y0)))


class Camera:
    def __init__(self, W, H, fov_deg=58):
        self.W, self.H = W, H
        self.f = (H / 2) / math.tan(math.radians(fov_deg / 2))

    def set(self, pos, pitch_deg):
        self.pos = np.array(pos, float)
        p = math.radians(pitch_deg)      # pitch: +down; 90 = looking straight down
        self.fwd = np.array([0, -math.sin(p), math.cos(p)])
        self.up = np.array([0, math.cos(p), math.sin(p)])
        self.right = np.array([1.0, 0, 0])

    def project(self, P):
        v = np.array(P, float) - self.pos
        z = v @ self.fwd
        if z <= 0.05:
            return None
        x = v @ self.right
        y = v @ self.up
        return (self.W / 2 + self.f * x / z, self.H / 2 - self.f * y / z, z)


class Stack:
    """Builds the textures once; frame(t_local, plan) renders one frame (RGBA, no text)."""

    def __init__(self, W, H, hero_imgs, art_imgs, dore=None, mark_color=(232, 163, 61), seed=5):
        self.W, self.H = W, H
        self.rng = random.Random(seed)
        self.hero = hero_imgs[0]
        self.mark_color = mark_color
        self.cam = Camera(W, H)
        self.lineage = self.build_lineage(hero_imgs, art_imgs)
        self.panes = [self.lineage] + [self.build_pane(hero_imgs, art_imgs, i) for i in range(1, 22)]
        self.mark_offsets = [(self.rng.uniform(-0.55, 0.55), self.rng.uniform(-0.35, 0.35), self.rng.uniform(-40, 40), self.rng.uniform(0.8, 1.25))
                             for _ in self.panes]
        self.mark_offsets[0] = (0, 0, 0, 1.0)
        self.dore = dore
        self.mark_big = draw_mark(int(W * 0.34), mark_color)
        self.mark_small = {}

    # textures
    def build_lineage(self, heroes, arts, cols=5, rows=7):
        tw, th = 300, 360
        canvas = Image.new("RGBA", (cols * tw, rows * th), (18, 14, 20, 255))
        rng = self.rng
        cells = [(c, r) for r in range(rows) for c in range(cols)]
        center = (cols // 2, rows // 2)
        for c, r in cells:
            x, y = c * tw, r * th
            if (c, r) == center:
                im = ImageOps.contain(self.hero, (tw - 12, th - 12))
            elif rng.random() < 0.55 and heroes:
                im = ImageOps.contain(rng.choice(heroes), (tw - 12, th - 12))
            else:
                a = rng.choice(arts)
                im = ImageOps.fit(a, (tw - 8, th - 8))
            bg = Image.new("RGBA", (tw, th), tuple(rng.randint(14, 60) for _ in range(3)) + (255,))
            bg.alpha_composite(im.convert("RGBA"), ((tw - im.width) // 2, (th - im.height) // 2))
            canvas.alpha_composite(bg, (x, y))
            m = draw_mark(int(tw * 0.32 * rng.uniform(0.8, 1.2)), self.mark_color, rot=rng.uniform(-50, 50), gap_deg=rng.uniform(36, 64))
            canvas.alpha_composite(m, (x + tw // 2 - m.width // 2, y + int(th * 0.52) - m.height // 2))
        self.center_cell = (center[0] * tw + tw / 2, center[1] * th + th / 2, tw, th)
        return canvas

    def build_pane(self, heroes, arts, i):
        w, h = 900, 640
        rng = random.Random(100 + i)
        pane = Image.new("RGBA", (w, h), tuple(rng.randint(16, 50) for _ in range(3)) + (255,))
        for _ in range(9):
            src = rng.choice(heroes) if rng.random() < 0.3 else rng.choice(arts)
            pw = rng.randint(180, 420)
            im = ImageOps.contain(src.convert("RGBA"), (pw, pw))
            pane.alpha_composite(im, (rng.randint(-40, w - pw + 40), rng.randint(-40, h - pw // 2)))
        pane = ImageEnhance.Brightness(pane.convert("RGB")).enhance(0.8).convert("RGBA")
        d = ImageDraw.Draw(pane)
        d.rectangle([0, 0, w - 1, h - 1], outline=(240, 222, 180, 160), width=4)
        return pane

    def small_mark(self, px, rot):
        key = (int(px / 6) * 6, int(rot / 10) * 10)
        if key not in self.mark_small:
            self.mark_small[key] = draw_mark(max(8, key[0]), self.mark_color, rot=key[1])
        return self.mark_small[key]

    # ── phases ──────────────────────────────────────────────
    def frame(self, t, plan):
        """plan: dict phase→(t_start, t_end) in scene-local seconds. Keys: hold, pull, fan, align, tilt, rise."""
        W, H = self.W, self.H
        frame = Image.new("RGBA", (W, H), (10, 8, 14, 255))
        ph = lambda k: (t - plan[k][0]) / max(0.01, plan[k][1] - plan[k][0])  # noqa: E731
        if t < plan["pull"][0]:
            return self.phase_hero(frame, t, plan)
        if t < plan["fan"][0]:
            return self.phase_pull(frame, ease(ph("pull")))
        return self.phase_stack(frame, t, plan, ph)

    def phase_hero(self, frame, t, plan):
        W, H = self.W, self.H
        hero = ImageOps.contain(self.hero.convert("RGBA"), (int(W * 0.86), int(H * 0.62)))
        k = 1 + 0.03 * ease(t / max(0.1, plan["pull"][0]))
        hero = hero.resize((int(hero.width * k), int(hero.height * k)), Image.LANCZOS)
        hx, hy = (W - hero.width) // 2, int(H * 0.53 - hero.height / 2)
        frame.alpha_composite(hero, (hx, hy))
        pulse = 0.85 + 0.15 * math.sin(2 * math.pi * t / 3.0)
        prog = min(1.0, t / 1.2)
        m = draw_mark(int(W * 0.30), self.mark_color, progress=prog)
        frame.alpha_composite(m, (W // 2 - m.width // 2, int(H * 0.55) - m.height // 2))
        if t > plan["hold"][0]:
            e = ember_sprite(int(W * 0.16 * pulse))
            frame.alpha_composite(e, (W // 2 - e.width // 2, int(H * 0.55) - e.height // 2))
        return frame

    def phase_pull(self, frame, p):
        W, H = self.W, self.H
        L = self.lineage
        cx, cy, tw, th = self.center_cell
        # zoom from the centre cell filling the frame width to the whole lineage fitting the frame
        s0 = W * 0.86 / tw
        # end framed inside TikTok's uncovered area (x < W−140/1080·W, 220/1920·H < y < 1440/1920·H)
        bx0, bx1, by0, by1 = 0.0, W * (1 - 140 / 1080), H * 220 / 1920, H * 1440 / 1920
        s1 = min((bx1 - bx0) / L.width, (by1 - by0) / L.height) * 0.98
        s = s0 * (s1 / s0) ** p                      # exponential zoom (constant rate, Powers-of-Ten style)
        fx, fy = W / 2 + ((bx0 + bx1) / 2 - W / 2) * p, H / 2 + ((by0 + by1) / 2 - H / 2) * p
        ox = fx - (cx + (L.width / 2 - cx) * p) * s
        oy = fy - (cy + (L.height / 2 - cy) * p) * s
        # crop the visible part before scaling
        x0, y0 = max(0, int(-ox / s)), max(0, int(-oy / s))
        x1, y1 = min(L.width, int((W - ox) / s) + 1), min(L.height, int((H - oy) / s) + 1)
        crop = L.crop((x0, y0, x1, y1))
        crop = crop.resize((max(1, int((x1 - x0) * s)), max(1, int((y1 - y0) * s))), Image.BILINEAR)
        frame.alpha_composite(crop, (int(ox + x0 * s), int(oy + y0 * s)))
        return frame

    def phase_stack(self, frame, t, plan, ph):
        W, H = self.W, self.H
        fan, align, tilt, rise = ease(ph("fan")), ease(ph("align")), ease(ph("tilt")), ph("rise")
        L = self.lineage
        pane_w = 2.0
        pane_d = pane_w * L.height / L.width
        spacing = 0.62 * fan
        # camera: from straight above pane 0 (fills frame) → oblique view of the stack → rising up the column
        fit_h = (pane_d / 2) * self.cam.f / (H / 2 * 0.98)
        cam_start = np.array([0.0, fit_h, 0.0])
        pitch0 = 90.0
        cam_obl = np.array([0.0, 3.4, -8.6])
        pitch_obl = 6.0
        pos = cam_start + (cam_obl - cam_start) * ease(min(1.0, ph("fan") * 1.3))
        pitch = pitch0 + (pitch_obl - pitch0) * ease(min(1.0, ph("fan") * 1.3))
        # tilt up the column: camera rises and pitches upward
        top_y = spacing * 14
        if tilt > 0:
            pos = pos + np.array([0, (top_y * 0.55) * tilt, 2.2 * tilt])
            pitch = pitch + (-22 - pitch) * tilt
        if rise > 0:
            pos = pos + np.array([0, 2.6 * max(0.0, rise), 0])
        self.cam.set(pos, pitch)
        # Doré light backdrop, revealed as the camera looks up
        if self.dore is not None:
            vis = max(0.0, min(1.0, (tilt * 1.15)))
            if vis > 0.01:
                bd = ImageOps.fit(self.dore, (W, H))
                bd = ImageEnhance.Brightness(bd).enhance(0.35 + 0.9 * vis * (1 - 0.35 * max(0.0, rise)))
                bd = bd.convert("RGBA")
                bd.putalpha(int(255 * vis))
                off = int(H * 0.35 * (1 - vis))
                frame.alpha_composite(bd, (0, -off) if off < H else (0, 0))
        # panes, back to front (sorted by camera depth), translucent; new panes appear above while rising
        n_vis = 1 + int(round(15 * fan)) + int(6 * max(0.0, rise))
        items = []
        for i in range(min(n_vis, len(self.panes))):
            k = i if i % 2 == 0 else -(i // 2 + 1) * 0.0 + i       # stack upward
            y = k * spacing
            jitter = (1 - align) * 0.0 + align * 0.0
            sx = (self.rng.random() if False else 0) + math.sin(i * 1.7 + t * (0.25 + 0.05 * i)) * 0.28 * fan * (0.4 + 0.6 * (1 - align) + 0.6 * max(0.0, align - 0.0))
            sz = math.cos(i * 2.3 + t * 0.2) * 0.18 * fan
            corners = [(-pane_w / 2 + sx, y, pane_d / 2 + sz), (pane_w / 2 + sx, y, pane_d / 2 + sz),
                       (pane_w / 2 + sx, y, -pane_d / 2 + sz), (-pane_w / 2 + sx, y, -pane_d / 2 + sz)]
            proj = [self.cam.project(c) for c in corners]
            if any(p is None for p in proj):
                continue
            depth = sum(p[2] for p in proj) / 4
            items.append((depth, i, proj, sx, sz, y))
        items.sort(key=lambda it: -it[0])
        col_pts = []
        for depth, i, proj, sx, sz, y in items:
            alpha = 1.0 if (i == 0 and fan < 0.15) else 0.62
            warp_onto(frame, self.panes[i], [(p[0], p[1]) for p in proj], alpha=alpha)
            # each pane's mark: varied offset → snaps to the column on align
            mx0, mz0, rot, ms = self.mark_offsets[i]
            mx = (sx + mx0 * pane_w * 0.4) * (1 - align)
            mz = (sz + mz0 * pane_d * 0.4) * (1 - align)
            c = self.cam.project((mx, y + 0.01, mz))
            if c is None:
                continue
            px = max(10, (self.cam.f * 0.32 / c[2]) * ms * (1 - 0.25 * align))
            m = self.small_mark(px, rot * (1 - align))
            frame.alpha_composite(m, (int(c[0] - m.width / 2), int(c[1] - m.height / 2)))
            col_pts.append((c[0], c[1]))
        # the column of light through the aligned marks, stopping short of the light
        if align > 0.05 and col_pts:
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(glow)
            xs = sum(p[0] for p in col_pts) / len(col_pts)
            ytop = min(p[1] for p in col_pts) - H * 0.04
            ybot = max(p[1] for p in col_pts)
            if tilt > 0:
                ytop = max(H * 0.12, ytop)
            a = int(200 * align)
            for wdt, al in ((W * 0.05, a // 5), (W * 0.022, a // 2), (W * 0.008, a)):
                d.rectangle([xs - wdt / 2, ytop, xs + wdt / 2, ybot], fill=(255, 210, 130, al))
            glow = glow.filter(ImageFilter.GaussianBlur(W * 0.012))
            frame.alpha_composite(glow)
        return frame


def default_plan(dur, reprise=False):
    """Phase windows (scene-local seconds) for a stack of length `dur`."""
    if reprise:
        return {"hold": (-9, -8), "pull": (-8, -7), "fan": (-7, -6), "align": (-6, -5), "tilt": (0.0, dur * 0.65), "rise": (dur * 0.45, dur * 1.4)}
    return {"hold": (dur * 0.08, dur * 0.18), "pull": (dur * 0.20, dur * 0.36), "fan": (dur * 0.36, dur * 0.55),
            "align": (dur * 0.55, dur * 0.66), "tilt": (dur * 0.66, dur * 0.84), "rise": (dur * 0.84, dur * 1.25)}


if __name__ == "__main__":
    import sys
    W, H = 540, 960
    heroes = [Image.new("RGBA", (300, 400), (200, 60, 60, 255))]
    arts = [Image.new("RGB", (400, 300), (60, 90, 140))]
    st = Stack(W, H, heroes, arts)
    t = float(sys.argv[1]) if len(sys.argv) > 1 else 20
    st.frame(t, default_plan(42)).convert("RGB").save("/tmp/stack_test.png")
