"""Procedural paper-cut illustrations used as stand-ins (clearly drawn, not copied artwork).

  assets/cutouts/sword_stone_art.png   a sword in a stone (fallback if the Pyle illustration is unavailable)
"""
import random
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import collage as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())


def sword_stone(h=900):
    w = int(h * 0.8)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rng = random.Random(2)
    # anvil-topped stone
    stone = [(w * 0.08, h), (w * 0.12, h * 0.72), (w * 0.22, h * 0.62), (w * 0.45, h * 0.58), (w * 0.70, h * 0.60),
             (w * 0.86, h * 0.68), (w * 0.93, h)]
    d.polygon(stone, fill=(128, 120, 108, 255))
    for _ in range(40):  # speckles / cracks
        x, y = rng.uniform(w * 0.15, w * 0.85), rng.uniform(h * 0.66, h * 0.98)
        r = rng.uniform(3, 12)
        d.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=(100 + rng.randint(-15, 15),) * 3 + (255,))
    d.rectangle([w * 0.30, h * 0.52, w * 0.70, h * 0.60], fill=(70, 66, 64, 255))   # anvil
    d.polygon([(w * 0.26, h * 0.52), (w * 0.74, h * 0.52), (w * 0.68, h * 0.48), (w * 0.32, h * 0.48)], fill=(84, 80, 78, 255))
    # sword
    d.polygon([(w * 0.47, h * 0.52), (w * 0.53, h * 0.52), (w * 0.525, h * 0.20), (w * 0.475, h * 0.20)], fill=(205, 214, 222, 255))
    d.line([(w * 0.50, h * 0.52), (w * 0.50, h * 0.21)], fill=(160, 170, 180, 255), width=max(2, h // 220))
    d.rectangle([w * 0.36, h * 0.17, w * 0.64, h * 0.20], fill=(196, 160, 60, 255))   # guard
    d.rectangle([w * 0.485, h * 0.07, w * 0.515, h * 0.17], fill=(92, 52, 30, 255))   # grip
    d.ellipse([w * 0.47, h * 0.035, w * 0.53, h * 0.08], fill=(196, 160, 60, 255))     # pommel
    st = CFG["sticker"]
    return C.make_sticker(C.apply_tint(im, "aged"), border=st["border_px"], shadow_offset=tuple(st["shadow_offset"]),
                          shadow_blur=st["shadow_blur"], shadow_opacity=st["shadow_opacity"])


if __name__ == "__main__":
    out = ROOT / "assets" / "cutouts"
    out.mkdir(parents=True, exist_ok=True)
    sword_stone().save(out / "sword_stone_art.png")
    print("wrote assets/cutouts/sword_stone_art.png")
