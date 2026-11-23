"""Cut out every figure (rembg) or trim it as a hand-cut print, then add sticker border + shadow.

Spec: assets/cutouts.yaml      Output: assets/cutouts/<id>.png  +  build/contact_sheet.jpg

  mode: rembg  → background removed with rembg (isnet-general-use), largest shapes kept
  mode: alpha  → image already has transparency (official renders); just tidy it
  mode: card   → rectangular print with a hand-cut edge (paintings, posters, scenes)
  crop: [x0, y0, x1, y1] as fractions of the source image (applied first)
  tint: sepia | aged          (optional "old print" look)
  min_h: upscale small sources to at least this height before cutting (px)

Usage: python tools/make_cutouts.py [id ...]   (no ids = all; cached rembg masks reused)
"""
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
import collage as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
SPEC = yaml.safe_load((ROOT / "assets" / "cutouts.yaml").read_text(encoding="utf-8"))
OUT = ROOT / "assets" / "cutouts"
MASKS = ROOT / "build" / "masks"
Image.MAX_IMAGE_PIXELS = None
_session = {}


def source_path(img_id):
    for d in ("stills", "public_domain"):
        hits = sorted((ROOT / "assets" / d).glob(f"{img_id}.*"))
        hits = [h for h in hits if h.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif")]
        if hits:
            return hits[0]
    return None


def rembg_mask(im, key):
    MASKS.mkdir(parents=True, exist_ok=True)
    cache = MASKS / f"{key}.png"
    if cache.exists():
        m = Image.open(cache).convert("L")
        if m.size == im.size:
            return m
    from rembg import new_session, remove
    if "s" not in _session:
        _session["s"] = new_session("isnet-general-use")
    cut = remove(im.convert("RGB"), session=_session["s"], post_process_mask=True)
    m = cut.getchannel("A")
    m.save(cache)
    return m


def upscale(im, min_h):
    if min_h and im.height < min_h:
        f = min_h / im.height
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2))
    return im


def build(cid, spec):
    src = source_path(spec.get("img", cid))
    if src is None:
        print(f"  ✗ {cid}: source image missing")
        return None
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA") if has_alpha else im.convert("RGB")
    if "crop" in spec:
        x0, y0, x1, y1 = spec["crop"]
        W, H = im.size
        im = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    if max(im.size) > 1600:
        im.thumbnail((1600, 1600), Image.LANCZOS)
    im = upscale(im, spec.get("min_h", 760))
    mode = spec.get("mode", "rembg")
    st = CFG["sticker"]
    if mode == "card":
        cut = C.card(im.convert("RGB"), seed=hash(cid) % 1000)
        border = int(st["border_px"] * 0.8)
    else:
        if mode == "alpha" and im.mode == "RGBA":
            a = im.getchannel("A")
        else:
            a = rembg_mask(im.convert("RGB"), cid)
        a = C.clean_alpha(a, thresh=spec.get("thresh", 110), keep_largest=spec.get("keep_largest", True))
        cut = im.convert("RGBA")
        cut.putalpha(a)
        bbox = a.point(lambda v: 255 if v > 20 else 0).getbbox()
        if bbox:
            cut = cut.crop(bbox)
        border = st["border_px"]
    if spec.get("grey"):
        g = ImageOps.grayscale(cut.convert("RGB")).convert("RGBA")
        g.putalpha(cut.getchannel("A"))
        cut = g
    sticker = C.make_sticker(cut, border=border, shadow_offset=tuple(st["shadow_offset"]),
                             shadow_blur=st["shadow_blur"], shadow_opacity=st["shadow_opacity"],
                             tint=spec.get("tint"))
    OUT.mkdir(parents=True, exist_ok=True)
    sticker.save(OUT / f"{cid}.png")
    return sticker


def contact_sheet(ids):
    cell, cols = 340, 6
    rows = (len(ids) + cols - 1) // cols
    bg = C.paper_texture(cols * cell, rows * (cell + 34), CFG["palettes"]["title"], seed=4)
    d = ImageDraw.Draw(bg)
    f = ImageFont.truetype(str(ROOT / CFG["fonts"]["type"]), 18)
    for i, cid in enumerate(ids):
        p = OUT / f"{cid}.png"
        if not p.exists():
            continue
        im = Image.open(p)
        im.thumbnail((cell - 16, cell - 16), Image.LANCZOS)
        x, y = (i % cols) * cell, (i // cols) * (cell + 34)
        bg.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2), im)
        d.text((x + 10, y + cell + 6), cid, font=f, fill=(40, 30, 20))
    out = ROOT / "build" / "contact_sheet.jpg"
    bg.save(out, quality=90)
    return out


def main():
    ids = sys.argv[1:] or list(SPEC)
    for cid in ids:
        s = build(cid, SPEC[cid] or {})
        if s is not None:
            print(f"  ✓ {cid:16} {s.width}x{s.height}  ({(SPEC[cid] or {}).get('mode', 'rembg')})", flush=True)
    print("contact sheet:", contact_sheet(list(SPEC)).relative_to(ROOT))


if __name__ == "__main__":
    main()
