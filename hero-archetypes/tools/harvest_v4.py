"""Draft 4 assets: candidates for each specific image the script needs (open-access APIs), credits recorded on download.

    python tools/harvest_v4.py cand      → assets/v4/cand/*.jpg + draft4/candidates.json, contact sheet draft4/build/candidates.jpg
    python tools/harvest_v4.py pick      → copies the picks in draft4/picks.yaml to assets/v4/<role>.jpg + draft4/asset_credits.json
"""
import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
import harvest_esoteric as H  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
D4 = ROOT / "draft4"
CAND = ROOT / "assets" / "v4" / "cand"
NEEDS = {
    "achilles": [("Achilles", "cleveland"), ("Achilles", "aic"), ("Achilles", "wellcome")],
    "knight": [("knight", "cleveland"), ("knight on horseback", "aic"), ("knight armour", "wellcome")],
    "cuneiform": [("cuneiform", "cleveland"), ("cuneiform tablet", "aic")],
    "oracle_bone": [("oracle bone", "cleveland"), ("oracle bone", "aic"), ("oracle bones", "wellcome")],
    "maya": [("Maya glyphs", "cleveland"), ("Maya inscription", "aic"), ("Maya hieroglyphic", "wellcome")],
    "famine": [("famine", "wellcome")],
    "disease": [("cholera", "wellcome"), ("plague", "wellcome")],
    "monster": [("sea monster", "wellcome"), ("monster", "cleveland")],
    "world_map": [("world map", "wellcome"), ("map of the world", "aic")],
    "route_map": [("road map route", "wellcome"), ("map", "aic")],
}


def cand():
    CAND.mkdir(parents=True, exist_ok=True)
    cred_p = D4 / "candidates.json"
    cred = json.loads(cred_p.read_text()) if cred_p.exists() else {}
    fn = {"wellcome": H.wellcome, "cleveland": H.cleveland, "aic": H.aic}
    for role, qs in NEEDS.items():
        for q, src in qs:
            try:
                items = fn[src](q, 5)
            except Exception as ex:
                print("  ✗", role, q, ex)
                continue
            got = 0
            for it in items:
                dest = CAND / f"{it['id']}.jpg"
                if not dest.exists():
                    r = H.get(it["img"])
                    if not r or not r.headers.get("content-type", "").startswith("image"):
                        continue
                    dest.write_bytes(r.content)
                cred[it["id"]] = {**it, "role": role, "query": q, "local": str(dest.relative_to(ROOT))}
                got += 1
            print(f"  {role:12} {q:22} {src:9} {got}", flush=True)
        cred_p.write_text(json.dumps(cred, indent=1, ensure_ascii=False))
    sheet(cred)


def sheet(cred):
    (D4 / "build").mkdir(parents=True, exist_ok=True)
    roles = list(NEEDS)
    rows = []
    for role in roles:
        ks = [k for k, v in cred.items() if v["role"] == role][:12]
        rows.append((role, ks))
    tw, th = 200, 200
    W = 160 + 12 * tw
    sh = Image.new("RGB", (W, len(rows) * (th + 30)), (30, 30, 30))
    d = ImageDraw.Draw(sh)
    for r, (role, ks) in enumerate(rows):
        y = r * (th + 30)
        d.text((8, y + 90), role, fill=(255, 255, 255))
        for i, k in enumerate(ks):
            try:
                im = ImageOps.contain(Image.open(ROOT / cred[k]["local"]).convert("RGB"), (tw - 6, th - 6))
            except Exception:
                continue
            sh.paste(im, (160 + i * tw, y))
            d.text((160 + i * tw, y + th + 4), k[:28], fill=(220, 220, 120))
    sh.save(D4 / "build" / "candidates.jpg", quality=85)
    print("sheet:", D4 / "build" / "candidates.jpg")


def pick():
    cred = json.loads((D4 / "candidates.json").read_text())
    picks = yaml.safe_load((D4 / "picks.yaml").read_text())
    out = {}
    for role, k in picks.items():
        im = Image.open(ROOT / cred[k]["local"]).convert("RGB")
        im.save(ROOT / "assets" / "v4" / f"{role}.jpg", quality=92)
        out[role] = {**cred[k], "local": f"assets/v4/{role}.jpg", "source_id": k}
    (D4 / "asset_credits.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("picked", len(out))


if __name__ == "__main__":
    {"cand": cand, "pick": pick}[sys.argv[1]]()
