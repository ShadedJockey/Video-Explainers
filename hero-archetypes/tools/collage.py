"""Collage graphics: paper textures, sticker cutouts, caption labels, dotted path, paper tears.

Everything is drawn at the output resolution chosen in config.yaml; sizes in the
config are given for 1080p and scaled by `S` (frame height / 1080).
"""
import math
import random
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ── noise ────────────────────────────────────────────────────
def value_noise(w, h, scale, seed, octaves=4):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale / (2 ** o)))
        gw, gh = w // s + 2, h // s + 2
        g = rng.random((gh, gw)).astype(np.float32)
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((gw * s, gh * s), Image.BICUBIC)
        out += np.asarray(im, np.float32)[:h, :w] / 255.0 * amp
        total += amp
        amp *= 0.5
    return out / total


# ── paper backgrounds ───────────────────────────────────────
def paper_texture(w, h, palette, style="paper", seed=1):
    base = np.array(hex_rgb(palette["paper"]), np.float32)
    n1 = value_noise(w, h, 260, seed)
    n2 = value_noise(w, h, 18, seed + 1, octaves=2)
    img = np.ones((h, w, 3), np.float32) * base
    img *= (0.90 + 0.14 * n1)[..., None]
    img *= (0.96 + 0.06 * n2)[..., None]
    rng = np.random.default_rng(seed + 7)
    # fibres
    fib = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(fib)
    for _ in range(int(w * h / 2500)):
        x, y = rng.random() * w, rng.random() * h
        a = rng.random() * math.pi
        L = 6 + rng.random() * 26
        d.line([(x, y), (x + L * math.cos(a), y + L * math.sin(a))], fill=int(40 + rng.random() * 60), width=1)
    fib = np.asarray(fib.filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    img *= (1 - 0.10 * fib)[..., None]
    if style in ("parchment", "ancient"):
        stains = value_noise(w, h, 420, seed + 3, octaves=3)
        stains = np.clip((stains - 0.55) * 3.0, 0, 1)
        img *= (1 - 0.22 * stains)[..., None]
        img[..., 2] *= 0.94
    if style == "cardboard":
        yy = np.arange(h, dtype=np.float32)[:, None]
        img *= (0.988 + 0.012 * np.sin(yy / 7.0))[..., None]
    # vignette
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    img *= (1 - 0.28 * np.clip(r - 0.55, 0, 1) ** 1.5)[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def grain_frames(w, h, n=6, strength=10, seed=5):
    """Pre-generated film-grain layers to multiply over frames (cheap per-frame texture)."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        g = rng.normal(0, strength, (h // 2, w // 2)).astype(np.float32)
        g = np.asarray(Image.fromarray(np.clip(g + 128, 0, 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.int16) - 128
        out.append(g)
    return out


# ── stickers ────────────────────────────────────────────────
def clean_alpha(alpha, thresh=110, keep_largest=True, min_frac=0.02):
    a = np.asarray(alpha, np.uint8)
    m = (a > thresh).astype(np.uint8)
    if keep_largest:
        try:
            from scipy import ndimage
            lab, n = ndimage.label(m)
            if n > 1:
                sizes = ndimage.sum(m, lab, range(1, n + 1))
                keep = [i + 1 for i, s in enumerate(sizes) if s >= max(sizes) * min_frac]
                m = np.isin(lab, keep).astype(np.uint8)
                m = ndimage.binary_fill_holes(m).astype(np.uint8)
        except ImportError:
            pass
    soft = Image.fromarray(m * 255).filter(ImageFilter.GaussianBlur(1.0))
    return soft


def rough_rect_mask(w, h, inset, seed=0, jag=6):
    """A slightly irregular, hand-cut rectangle mask."""
    rng = random.Random(seed)
    m = Image.new("L", (w, h), 0)
    pts = []
    def edge(x0, y0, x1, y1, n):
        for i in range(n):
            t = i / n
            pts.append((x0 + (x1 - x0) * t + rng.uniform(-jag, jag) * (y1 != y0),
                        y0 + (y1 - y0) * t + rng.uniform(-jag, jag) * (x1 != x0)))
    n = 18
    edge(inset, inset, w - inset, inset, n)
    edge(w - inset, inset, w - inset, h - inset, n)
    edge(w - inset, h - inset, inset, h - inset, n)
    edge(inset, h - inset, inset, inset, n)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


def make_sticker(rgba, border=14, shadow_offset=(10, 14), shadow_blur=14, shadow_opacity=0.45,
                 tint=None, seed=0):
    """White sticker border + soft drop shadow around an RGBA cutout."""
    rgba = rgba.convert("RGBA")
    if tint is not None:
        rgba = apply_tint(rgba, tint)
    pad = border * 2 + shadow_blur * 3 + max(abs(shadow_offset[0]), abs(shadow_offset[1]))
    W, H = rgba.width + pad * 2, rgba.height + pad * 2
    alpha = Image.new("L", (W, H), 0)
    alpha.paste(rgba.getchannel("A"), (pad, pad))
    # border: dilate alpha (wobbly, like scissors)
    k = border * 2 + 1
    small = alpha.resize((W // 2, H // 2), Image.BILINEAR)
    dil = small.filter(ImageFilter.MaxFilter(max(3, (k // 2) | 1))).resize((W, H), Image.BILINEAR)
    dil = dil.filter(ImageFilter.GaussianBlur(border * 0.35)).point(lambda v: 255 if v > 90 else int(v * 255 / 90) if v > 60 else 0)
    shadow = dil.filter(ImageFilter.GaussianBlur(shadow_blur)).point(lambda v: int(v * shadow_opacity))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), (20, 12, 6, 0))
    sh.putalpha(shadow)
    out.alpha_composite(sh, (shadow_offset[0], shadow_offset[1]))
    white = Image.new("RGBA", (W, H), (252, 250, 244, 0))
    white.putalpha(dil)
    out.alpha_composite(white)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(rgba, (pad, pad))
    out.alpha_composite(layer)
    bbox = out.getbbox()
    return out.crop(bbox)


def apply_tint(rgba, tint):
    """tint: 'sepia' | 'aged' | None — warm, slightly faded print look."""
    a = rgba.getchannel("A")
    rgb = np.asarray(rgba.convert("RGB"), np.float32)
    if tint == "sepia":
        g = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        sep = np.stack([g * 1.07 + 18, g * 0.95 + 8, g * 0.78], -1)
        rgb = rgb * 0.35 + sep * 0.65
    elif tint == "aged":
        rgb = rgb * np.array([1.02, 0.98, 0.88], np.float32) + np.array([8, 4, -4], np.float32)
        rgb = rgb * 0.9 + 18
    out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    out.putalpha(a)
    return out


def card(rgb, max_side=None, seed=0, border=None):
    """Rectangular photo/print cutout with a hand-cut edge (for scenes & posters)."""
    im = rgb.convert("RGBA")
    if max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    m = rough_rect_mask(im.width, im.height, inset=2, seed=seed, jag=max(1.5, im.width / 300))
    im.putalpha(m)
    return im


# ── fonts ───────────────────────────────────────────────────
@lru_cache(maxsize=64)
def font(path, size, bold=False):
    f = ImageFont.truetype(str(ROOT / path), int(size))
    if bold:
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
    return f


# ── caption labels ──────────────────────────────────────────
def _text_block(text, fnt, fill, spacing=0.08, align="center"):
    lines = text.split("\n")
    asc, desc = fnt.getmetrics()
    lh = asc + desc
    widths = [fnt.getbbox(l)[2] for l in lines]
    W = max(widths)
    H = int(lh * len(lines) + lh * spacing * (len(lines) - 1))
    im = Image.new("RGBA", (W + 4, H + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = 0
    for l, w in zip(lines, widths):
        x = (W - w) // 2 if align == "center" else 0
        d.text((x + 2, y + 2), l, font=fnt, fill=fill)
        y += int(lh * (1 + spacing))
    return im


def caption_image(text, style, cfg, S, palette, size=64, seed=0):
    """Render a caption label as an RGBA image (unrotated)."""
    rng = random.Random(seed)
    F = cfg["fonts"]
    ink = hex_rgb(palette["ink"])
    accent = hex_rgb(palette["accent"])
    if style == "stamp":
        accent = hex_rgb(palette.get("stamp", palette["accent"]))
        fnt = font(F["caption"], size * S)
        t = _text_block(text.upper(), fnt, accent + (255,))
        p = int(size * S * 0.35)
        im = Image.new("RGBA", (t.width + p * 2, t.height + p * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        lw = max(3, int(size * S * 0.07))
        d.rounded_rectangle([lw, lw, im.width - lw, im.height - lw], radius=int(p * 0.6), outline=accent + (255,), width=lw)
        im.alpha_composite(t, (p, p))
        # ink texture: knock out speckles
        n = value_noise(im.width, im.height, max(3, int(6 * S)), seed + 11, octaves=2)
        knock = Image.fromarray((np.clip((n - 0.16) * 5, 0.25, 1) * 255).astype(np.uint8))
        im.putalpha(ImageChops.multiply(im.getchannel("A"), knock))
        return im
    if style == "tape":   # bold black text on a torn white paper strip
        fnt = font(F["caption"], size * S)
        t = _text_block(text.upper(), fnt, ink + (255,))
        px, py = int(size * S * 0.45), int(size * S * 0.22)
        W, H = t.width + px * 2, t.height + py * 2
        strip = Image.new("RGBA", (W, H), (250, 248, 240, 255))
        strip.putalpha(rough_rect_mask(W, H, 1, seed=seed, jag=max(1.5, 3 * S)))
        out = Image.new("RGBA", (W + int(30 * S), H + int(30 * S)), (0, 0, 0, 0))
        sh = Image.new("RGBA", strip.size, (0, 0, 0, 0))
        sh.putalpha(strip.getchannel("A").point(lambda v: v // 3))
        out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6 * S)), (int(10 * S), int(12 * S)))
        out.alpha_composite(strip, (int(4 * S), int(4 * S)))
        out.alpha_composite(t, (int(4 * S) + px, int(4 * S) + py))
        # tape pieces
        tw, th = int(70 * S), int(26 * S)
        for cx in (int(4 * S) + int(W * 0.06), int(4 * S) + W - int(W * 0.06) - tw):
            tape = Image.new("RGBA", (tw, th), (235, 228, 200, 150))
            tape = tape.rotate(rng.uniform(-12, 12), expand=True, resample=Image.BICUBIC)
            out.alpha_composite(tape, (max(0, cx), 0))
        return out
    if style == "title":  # big bold title with offset print shadow
        fnt = font(F["caption"], size * S)
        t = _text_block(text.upper(), fnt, ink + (255,))
        sh = _text_block(text.upper(), fnt, accent + (255,))
        o = max(3, int(size * S * 0.06))
        out = Image.new("RGBA", (t.width + o + 4, t.height + o + 4), (0, 0, 0, 0))
        out.alpha_composite(sh, (o, o))
        out.alpha_composite(t, (0, 0))
        return out
    if style == "type":   # typewriter label on a small paper tag
        fnt = font(F["type"], size * S)
        t = _text_block(text, fnt, ink + (255,))
        px, py = int(size * S * 0.5), int(size * S * 0.3)
        W, H = t.width + px * 2, t.height + py * 2
        tag = Image.new("RGBA", (W, H), (244, 236, 214, 255))
        tag.putalpha(rough_rect_mask(W, H, 1, seed=seed, jag=2 * S))
        out = Image.new("RGBA", (W + int(12 * S), H + int(12 * S)), (0, 0, 0, 0))
        sh = Image.new("RGBA", tag.size, (0, 0, 0, 0))
        sh.putalpha(tag.getchannel("A").point(lambda v: v // 3))
        out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4 * S)), (int(6 * S), int(8 * S)))
        out.alpha_composite(tag, (0, 0))
        out.alpha_composite(t, (px, py))
        return out
    if style == "marker":  # hand-written marker note, no backing
        fnt = font(F["label"], size * S)
        return _text_block(text, fnt, ink + (255,))
    if style == "quote":   # quote card: big text + attribution line (split by ' — ')
        body, _, who = text.partition(" — ")
        fb = font(F["body"], size * S, bold=True)
        fw = font(F["type"], size * S * 0.55)
        b = _text_block(body, fb, ink + (255,))
        w = _text_block("— " + who, fw, accent + (255,)) if who else None
        px, py = int(size * S * 0.7), int(size * S * 0.55)
        W = max(b.width, w.width if w else 0) + px * 2
        H = b.height + (w.height + int(size * S * 0.3) if w else 0) + py * 2
        cardim = Image.new("RGBA", (W, H), (251, 248, 238, 255))
        cardim.putalpha(rough_rect_mask(W, H, 1, seed=seed, jag=3 * S))
        out = Image.new("RGBA", (W + int(24 * S), H + int(24 * S)), (0, 0, 0, 0))
        sh = Image.new("RGBA", cardim.size, (0, 0, 0, 0))
        sh.putalpha(cardim.getchannel("A").point(lambda v: v // 3))
        out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8 * S)), (int(12 * S), int(14 * S)))
        out.alpha_composite(cardim, (0, 0))
        out.alpha_composite(b, ((W - b.width) // 2, py))
        if w:
            out.alpha_composite(w, (W - px - w.width, py + b.height + int(size * S * 0.3)))
        return out
    raise ValueError(style)


# ── dotted journey path ─────────────────────────────────────
def catmull_rom(points, n=40):
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = map(np.array, pts[i - 1:i + 3])
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(np.array(points[-1]))
    return np.array(out)


def path_dots(points_px, spacing, seed=0):
    """Evenly spaced dot positions along a smooth hand-drawn curve (with slight jitter)."""
    curve = catmull_rom(points_px, 60)
    seg = np.linalg.norm(np.diff(curve, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    L = cum[-1]
    rng = np.random.default_rng(seed)
    dots = []
    for s in np.arange(0, L, spacing):
        i = np.searchsorted(cum, s) - 1
        i = max(0, min(i, len(curve) - 2))
        t = (s - cum[i]) / max(seg[i], 1e-6)
        p = curve[i] * (1 - t) + curve[i + 1] * t
        dots.append(p + rng.normal(0, spacing * 0.06, 2))
    return np.array(dots), L


def draw_path(img, dots, progress, radius, color, stops=(), stop_progress=None, S=1.0):
    """Draw the first `progress` fraction of the dots, plus ring markers at stops."""
    d = ImageDraw.Draw(img)
    n = int(len(dots) * max(0.0, min(1.0, progress)))
    for i, (x, y) in enumerate(dots[:n]):
        r = radius * (0.85 + 0.3 * ((i * 7919) % 13) / 13)
        d.ellipse([x - r, y - r * 0.9, x + r, y + r * 0.9], fill=color)
    for j, (x, y) in enumerate(stops):
        sp = 1.0 if stop_progress is None else stop_progress[j]
        if sp <= 0:
            continue
        R = radius * 3.2 * min(1.0, sp * 1.3)
        w = max(2, int(radius * 0.9))
        d.ellipse([x - R, y - R, x + R, y + R], outline=color, width=w)
        d.ellipse([x - R * 0.35, y - R * 0.35, x + R * 0.35, y + R * 0.35], fill=color)


# ── paper tear transition ───────────────────────────────────
@lru_cache(maxsize=4)
def tear_profile(h, seed=3):
    rng = np.random.default_rng(seed)
    y = np.arange(h, dtype=np.float32)
    prof = np.zeros(h, np.float32)
    for f, a in ((h / 3, 40), (h / 9, 18), (h / 40, 7), (h / 120, 3)):
        ph = rng.random() * 6.28
        prof += a * np.sin(y / f * 6.28 + ph)
    prof += np.convolve(rng.normal(0, 4, h), np.ones(5) / 5, mode="same")
    return prof


def paper_tear(old, new, p, S=1.0):
    """Reveal `new` from the left behind a torn edge of `old` (p in 0..1). Inputs: uint8 HxWx3."""
    h, w = old.shape[:2]
    prof = tear_profile(h) * S
    slope = np.linspace(-0.12, 0.12, h, dtype=np.float32) * w
    ease = p * p * (3 - 2 * p)
    edge = (ease * (w * 1.35) - w * 0.15 + prof + slope).astype(np.int32)   # x of the tear per row
    xs = np.arange(w)[None, :]
    reveal = xs < edge[:, None]
    fibre = (xs >= edge[:, None]) & (xs < edge[:, None] + int(9 * S) + (np.abs(prof[:, None]) % (5 * S)).astype(int))
    shadow = (xs >= edge[:, None]) & (xs < edge[:, None] + int(36 * S))
    out = old.copy()
    sh = np.clip(1 - (shadow * (1 - (xs - edge[:, None]) / (36 * S))) * 0.35, 0.6, 1)
    out = (out * sh[..., None]).astype(np.uint8)
    out[reveal] = new[reveal]
    out[fibre] = np.array([246, 242, 232], np.uint8)
    return out


# ── easing ──────────────────────────────────────────────────
def ease_out_back(t, s=1.6):
    t = max(0.0, min(1.0, t)) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_in_out(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3
