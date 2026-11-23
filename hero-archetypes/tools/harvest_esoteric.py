"""Harvest themed public-domain / open-access art for the draft-2 collage.

Sources: Wellcome Collection (public domain mark + CC BY), Cleveland Museum of Art (CC0),
Art Institute of Chicago (public domain). Each query is tagged with collage themes.

Output: assets/collage/<source>_<id>.jpg and draft2/collage_credits.json
Usage:  python tools/harvest_esoteric.py [per_query]
"""
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "collage"
CREDITS = ROOT / "draft2" / "collage_credits.json"
UA = {"User-Agent": "HeroArchetypesExplainer/1.0 (educational video build)"}
W = 1100  # download width

# (query, source, themes)
QUERIES = [
    # cosmos / esoteric core
    ("alchemy", "wellcome", ["esoteric", "cycle"]),
    ("alchemical emblem", "wellcome", ["esoteric", "cycle"]),
    ("ouroboros", "wellcome", ["cycle", "infinity"]),
    ("Robert Fludd macrocosm", "wellcome", ["esoteric", "cosmos"]),
    ("zodiac", "wellcome", ["cosmos", "campbell"]),
    ("astrology wheel", "wellcome", ["cosmos", "campbell"]),
    ("celestial map constellations", "wellcome", ["cosmos", "infinity"]),
    ("sun face", "wellcome", ["cosmos"]),
    ("moon", "cleveland", ["cosmos"]),
    ("comet", "wellcome", ["cosmos"]),
    ("eclipse", "wellcome", ["guts", "cosmos"]),
    ("armillary sphere", "wellcome", ["chief", "cycle"]),
    ("Saturn rings planet", "wellcome", ["chief", "cosmos"]),
    ("kabbalah tree", "wellcome", ["esoteric", "wisdom"]),
    ("tarot", "wellcome", ["esoteric", "question"]),
    ("playing card", "cleveland", ["esoteric", "question"]),
    ("mask", "cleveland", ["question", "infinite"]),
    ("face", "aic", ["question", "infinite"]),
    ("mirror", "cleveland", ["question", "infinite"]),
    ("labyrinth", "wellcome", ["campbell", "link"]),
    ("map", "aic", ["campbell"]),
    ("illuminated manuscript", "cleveland", ["campbell", "wisdom"]),
    ("book of hours", "cleveland", ["wisdom"]),
    ("hourglass", "wellcome", ["link", "cycle"]),
    ("forest", "cleveland", ["link", "nausicaa"]),
    ("tree of life", "wellcome", ["link", "wisdom"]),
    ("wolf", "cleveland", ["link"]),
    ("ship sea", "aic", ["link"]),
    ("sword", "cleveland", ["link", "aragorn"]),
    # Gilgamesh
    ("cylinder seal", "cleveland", ["gilgamesh"]),
    ("Assyrian relief", "cleveland", ["gilgamesh"]),
    ("Noah flood ark", "wellcome", ["gilgamesh"]),
    ("serpent", "wellcome", ["gilgamesh", "cycle"]),
    ("sleep", "cleveland", ["gilgamesh"]),
    ("city walls", "aic", ["gilgamesh"]),
    # Chief
    ("armour", "cleveland", ["chief", "guts"]),
    ("plague", "wellcome", ["chief"]),
    ("parasite", "wellcome", ["chief"]),
    ("helmet", "cleveland", ["chief"]),
    # Guts
    ("Durer apocalypse", "cleveland", ["guts", "shadow"]),
    ("Knight Death and the Devil", "cleveland", ["guts"]),
    ("dance of death skeleton", "wellcome", ["guts", "shadow"]),
    ("demon", "wellcome", ["guts", "shadow"]),
    ("temptation of saint anthony", "cleveland", ["guts", "shadow"]),
    # Aragorn
    ("crown king", "cleveland", ["aragorn"]),
    ("star", "wellcome", ["aragorn", "cosmos"]),
    ("mountain", "aic", ["aragorn", "frodo"]),
    # Frodo & Sam
    ("volcano", "wellcome", ["frodo"]),
    ("ring", "cleveland", ["frodo"]),
    ("fire", "wellcome", ["frodo"]),
    ("pilgrims", "cleveland", ["frodo"]),
    # wisdom & shadow
    ("sage scholar", "cleveland", ["wisdom"]),
    ("hermit", "cleveland", ["wisdom"]),
    ("dragon", "cleveland", ["shadow"]),
    ("devil", "wellcome", ["shadow"]),
    # Nausicaa
    ("Haeckel", "wellcome", ["nausicaa"]),
    ("fungi mushroom", "wellcome", ["nausicaa"]),
    ("insects", "wellcome", ["nausicaa"]),
    ("microscope", "wellcome", ["nausicaa", "cycle"]),
    ("botanical", "cleveland", ["nausicaa"]),
    # K
    ("automaton", "wellcome", ["k"]),
    ("anatomy", "wellcome", ["k"]),
    ("horse toy", "cleveland", ["k"]),
    ("rain", "aic", ["k"]),
    ("memory", "wellcome", ["k"]),
    # Popper & Deutsch
    ("scientific instrument", "wellcome", ["cycle", "explain"]),
    ("astronomer", "wellcome", ["explain", "cosmos"]),
    ("geometry diagram", "wellcome", ["explain", "infinity"]),
    ("telescope", "wellcome", ["explain"]),
    # infinite faces
    ("portrait", "cleveland", ["infinite"]),
    ("crowd", "aic", ["infinite"]),
    ("angel", "cleveland", ["infinite", "esoteric"]),
    ("mandala", "cleveland", ["esoteric", "infinity"]),
    ("thangka", "cleveland", ["esoteric", "wisdom"]),
]


def get(url, **kw):
    for a in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503):
                time.sleep(3 + 3 * a)
                continue
            return None
        except requests.RequestException:
            time.sleep(3)
    return None


def wellcome(q, n):
    r = get("https://api.wellcomecollection.org/catalogue/v2/images",
            params={"query": q, "locations.license": "pdm,cc-by,cc-0", "pageSize": n * 2})
    out = []
    for im in (r.json().get("results", []) if r else []):
        loc = im["locations"][0]
        lic = loc.get("license", {}).get("label") or loc.get("license", {}).get("id")
        base = loc["url"].replace("/info.json", "")
        out.append({"id": f"wellcome_{im['id']}", "img": f"{base}/full/{W},/0/default.jpg",
                    "title": im.get("source", {}).get("title", ""), "licence": f"{lic} (Wellcome Collection)",
                    "page": f"https://wellcomecollection.org/works/{im.get('source', {}).get('id', '')}"})
    return out[:n]


def cleveland(q, n):
    r = get("https://openaccess-api.clevelandart.org/api/artworks/", params={"q": q, "has_image": 1, "cc0": 1, "limit": n * 2})
    out = []
    for a in (r.json().get("data", []) if r else []):
        web = (a.get("images") or {}).get("web")
        if not web:
            continue
        out.append({"id": f"cma_{a['id']}", "img": web["url"], "title": f"{a['title']} ({a.get('creation_date') or ''})",
                    "licence": "CC0 (Cleveland Museum of Art)", "page": a.get("url")})
    return out[:n]


def aic(q, n):
    r = get("https://api.artic.edu/api/v1/artworks/search",
            params={"q": q, "limit": n * 2, "fields": "id,title,image_id,date_display,artist_title,is_public_domain",
                    "query[term][is_public_domain]": "true"})
    out = []
    for a in (r.json().get("data", []) if r else []):
        if not a.get("image_id") or not a.get("is_public_domain"):
            continue
        out.append({"id": f"aic_{a['id']}", "img": f"https://www.artic.edu/iiif/2/{a['image_id']}/full/843,/0/default.jpg",
                    "title": f"{a['title']} ({a.get('date_display') or ''}) {a.get('artist_title') or ''}".strip(),
                    "licence": "Public domain (Art Institute of Chicago)", "page": f"https://www.artic.edu/artworks/{a['id']}"})
    return out[:n]


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    OUT.mkdir(parents=True, exist_ok=True)
    credits = json.loads(CREDITS.read_text()) if CREDITS.exists() else {}
    fn = {"wellcome": wellcome, "cleveland": cleveland, "aic": aic}
    for q, src, themes in QUERIES:
        try:
            items = fn[src](q, per)
        except Exception as ex:
            print("  ✗", q, ex)
            continue
        got = 0
        for it in items:
            dest = OUT / f"{it['id']}.jpg"
            if it["id"] in credits and dest.exists():
                credits[it["id"]]["themes"] = sorted(set(credits[it["id"]]["themes"]) | set(themes))
                continue
            r = get(it["img"])
            if not r or not r.headers.get("content-type", "").startswith("image"):
                continue
            dest.write_bytes(r.content)
            credits[it["id"]] = {**it, "themes": themes, "query": q, "local": str(dest.relative_to(ROOT))}
            got += 1
        print(f"  {q:32} {src:9} +{got}", flush=True)
        CREDITS.write_text(json.dumps(credits, indent=1, ensure_ascii=False), encoding="utf-8")
    print("total images:", len(credits))


if __name__ == "__main__":
    main()
