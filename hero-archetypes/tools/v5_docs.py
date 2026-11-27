"""Draft 5 credits: draft5/collage_sources.md (stage pictures, hero stills, background pool)."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
D4 = ROOT / "draft5"


def main():
    scenes = yaml.safe_load((D4 / "scenes.yaml").read_text())
    srcs = set()
    for sc in scenes:
        for it in sc.get("items", []):
            srcs.add(it["src"])
    import importlib.util
    spec = importlib.util.spec_from_file_location("r4", ROOT / "tools" / "render_v5.py")
    r4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r4)
    srcs |= set(r4.Renderer.FACES) | {"file:assets/public_domain/flood_tablet.jpg"}
    picks = json.loads((D4 / "asset_credits.json").read_text())
    img1 = json.loads((ROOT / "build" / "image_credits.json").read_text())
    md = ["# Image credits (draft 5)", "", "Every picture on the draft 5 stage, with its licence, recorded at download time. "
          "Background collage pieces come from the draft 2–3 pools (filtered: no religious, heavenly or occult subjects); "
          "they are credited in `draft2/collage_sources.md` and `draft3/collage_sources.md`.", "",
          "| Picture | Title | Licence | Source |", "|---|---|---|---|"]
    rows = []
    for s in sorted(srcs):
        kind, val = s.split(":", 1)
        if kind == "file" and val.startswith("assets/v4/"):
            role = Path(val).stem
            v = picks.get(role, {})
            rows.append((role, v.get("title", ""), v.get("licence", ""), v.get("page", "")))
        elif kind in ("file", "still", "hero"):
            hid = Path(val).stem
            v = img1.get(hid, {})
            rows.append((hid, v.get("subject", ""), v.get("licence", ""), v.get("page") or v.get("url", "")))
        elif kind == "pool":
            v = r4.ALLPOOL.get(val, {})
            rows.append((val, v.get("title", ""), v.get("licence", ""), v.get("page", "")))
    for k, title, lic, page in rows:
        md.append(f"| `{k}` | {re.sub(r'[|]', '/', title)[:110]} | {lic} | [link]({page}) |")
    md += ["", "Copyrighted characters (Link, Master Chief, Aragorn, Frodo, Sam, Nausicaä, Luke, Goku) appear mid-size, only while the "
           "narration discusses heroes in films and games, as commentary. Book covers appear only while the narration names the book."]
    (D4 / "collage_sources.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote draft5/collage_sources.md", len(rows), "pictures")


if __name__ == "__main__":
    main()
