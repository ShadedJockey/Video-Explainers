"""Draft 3 credits: draft3/collage_sources.md (named works, themed collage art, hero stills)."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "draft3"


def rows(credits, excl):
    out = []
    for k, v in sorted(credits.items()):
        if k in excl:
            continue
        title = re.sub(r"\s+", " ", v.get("title", "")).replace("|", "/")[:110]
        out.append(f"| `{k}` | {title} | {v['licence']} | [link]({v.get('page') or v.get('img', '')}) |")
    return out


def main():
    cfg = yaml.safe_load((D3 / "config.yaml").read_text())
    excl = set()
    for p in cfg["collage"]["exclude"]:
        f = ROOT / p
        if f.exists():
            excl |= {l.split("#")[0].strip() for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")}
    named = json.loads((D3 / "named_credits.json").read_text())
    d3 = json.loads((D3 / "collage_credits.json").read_text())
    img1 = json.loads((ROOT / "build" / "image_credits.json").read_text())
    heroes = sorted({h["id"] for h in cfg["heroes"]} | set(cfg["cascade"]["heroes"]) | {"link_botw", "zelda", "link_oot"})
    head = ["| Id | Title | Licence | Source |", "|---|---|---|---|"]
    md = ["# Image credits (draft 3)", "",
          "Every image used in draft 3, with its licence, recorded at download time. Draft 3 also reuses the draft 2 collage pool, "
          "credited in [`draft2/collage_sources.md`](../draft2/collage_sources.md).", "",
          "## Named public-domain works (DESIGN.md → Visual references)", ""] + head + rows(named, excl)
    if not (ROOT / "assets" / "v3" / "dore_paradiso_31.jpg").exists():
        md += ["", "Not found: Gustave Doré's *Paradiso* Canto 31 (Wikimedia rate limits); the stack ends on a procedural light instead."]
    md += ["", "## Themed collage art (draft 3 harvest)", ""] + head + rows(d3, excl)
    md += ["", "## Hero images (copyrighted, used as commentary while the narration discusses them)", "", head[0], head[1]]
    for h in heroes:
        v = img1.get(h)
        if v:
            md.append(f"| `{h}` | {v['subject']} | {v['licence']} | [link]({v.get('page') or v.get('url')}) |")
    md += ["", "Not used, by design: the *Blade Runner 2049* and *Star Wars* posters. No K image exists on Wikipedia "
           "(no infobox image; the character list has no picture), so beat 9 shows no copyrighted image of K.",
           "The Great Deku Tree is a drawn illustration, not Nintendo artwork."]
    (D3 / "collage_sources.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("wrote draft3/collage_sources.md")


if __name__ == "__main__":
    main()
