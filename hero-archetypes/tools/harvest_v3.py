"""Draft 3 assets: themed public-domain art + named works from draft3/DESIGN.md (Visual references).

    python tools/harvest_v3.py themes [per_query]   themed searches (Wellcome, Cleveland, AIC) → assets/collage/
    python tools/harvest_v3.py named                named works by id → assets/v3/
    python tools/harvest_v3.py commons              Wikimedia-only items (Doré, Flammarion, K), single attempt each

Credits: draft3/collage_credits.json (themed) and draft3/named_credits.json (named works).
"""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent))
import harvest_esoteric as H  # noqa: E402  (reuses wellcome/cleveland/aic search functions)

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "draft3"
UA = {"User-Agent": "HeroArchetypesExplainer/1.0 (educational video build)"}

# (query, source, themes) — themes match draft3/config.yaml
THEMES = [
    ("hands", "cleveland", ["hands", "prologue"]),
    ("hand anatomy", "wellcome", ["hands", "prologue"]),
    ("torch", "wellcome", ["fire", "prologue", "tradition"]),
    ("torch", "cleveland", ["fire", "prologue", "tradition"]),
    ("fire flames", "cleveland", ["fire", "prologue"]),
    ("burning books", "wellcome", ["fire", "prologue"]),
    ("book burning", "aic", ["fire", "prologue"]),
    ("physiognomy faces", "wellcome", ["faces", "scripture"]),
    ("portrait engraving", "wellcome", ["faces", "portrait", "frontier"]),
    ("portrait", "aic", ["faces", "portrait", "frontier"]),
    ("mask", "aic", ["faces", "scripture"]),
    ("costume plate", "wellcome", ["costume", "scripture"]),
    ("costume", "cleveland", ["costume", "scripture"]),
    ("world map", "wellcome", ["map", "mythmaker", "frontier"]),
    ("map", "cleveland", ["map", "mythmaker"]),
    ("Saint George dragon", "cleveland", ["dragon", "mythmaker"]),
    ("Saint George dragon", "aic", ["dragon", "mythmaker"]),
    ("dragon", "wellcome", ["dragon", "mythmaker"]),
    ("eye anatomy", "wellcome", ["eyes", "rational"]),
    ("octopus", "wellcome", ["eyes", "rational"]),
    ("cuttlefish cephalopod", "wellcome", ["eyes", "rational"]),
    ("insect wings", "wellcome", ["wings", "rational"]),
    ("bird wing", "wellcome", ["wings", "rational"]),
    ("bat", "wellcome", ["wings", "rational"]),
    ("Haeckel radiolaria", "wellcome", ["haeckel", "rational", "nausicaa"]),
    ("Haeckel", "wellcome", ["haeckel", "rational", "nausicaa"]),
    ("fungi", "wellcome", ["haeckel", "nausicaa"]),
    ("soil section strata", "wellcome", ["soil", "nausicaa"]),
    ("geological section", "wellcome", ["soil", "nausicaa"]),
    ("microscope", "wellcome", ["microscope", "rational", "nausicaa"]),
    ("emblem", "wellcome", ["emblem", "rational"]),
    ("anchor emblem hope", "wellcome", ["emblem", "rational"]),
    ("scales balance", "wellcome", ["emblem", "rational"]),
    ("lion", "cleveland", ["emblem", "rational"]),
    ("telescope", "wellcome", ["emblem", "rational", "frontier"]),
    ("kneeling figure", "cleveland", ["emblem"]),
    ("castle walls", "cleveland", ["walls", "rational"]),
    ("fortress", "aic", ["walls"]),
    ("ruins", "cleveland", ["ruins", "stark"]),
    ("ruins", "aic", ["ruins", "stark"]),
    ("broken statue fragment", "cleveland", ["ruins", "stark"]),
    ("torch race runners", "wellcome", ["tradition"]),
    ("relay runners", "cleveland", ["tradition"]),
    ("tree of knowledge", "wellcome", ["tradition", "tree"]),
    ("genealogical tree", "wellcome", ["tradition", "tree"]),
    ("library", "wellcome", ["library", "labyrinth"]),
    ("library", "aic", ["library", "labyrinth"]),
    ("book", "wellcome", ["library", "labyrinth"]),
    ("night sky stars", "wellcome", ["stars", "frontier", "labyrinth"]),
    ("constellations", "wellcome", ["stars", "frontier", "labyrinth"]),
    ("rain", "cleveland", ["rain", "k"]),
    ("hero", "cleveland", ["faces", "frontier"]),
]

# named works from DESIGN.md → Visual references (Wellcome image ids found via the catalogue API)
NAMED_WELLCOME = {
    "michelspacher_1": ("rx6h6tux", "Steffan Michelspacher, three-tiered diagram of the art of alchemy (1616), plate 1", "wellcome.org/works/dawfnrzy"),
    "michelspacher_2": ("mgudvk6u", "Steffan Michelspacher, three-tiered diagram of the art of alchemy (1616), plate 2", "wellcome.org/works/dawfnrzy"),
    "michelspacher_3": ("fqyyrsbq", "Steffan Michelspacher, three-tiered diagram of the art of alchemy (1616), plate 3", "wellcome.org/works/dawfnrzy"),
    "flap_sheet_1683": ("f7qx2pek", "Female flap anatomy fugitive sheet with layered flaps (1683)", "wellcome.org/works/bm8nmgvu"),
    "bell_symbols": ("awvf2u5s", "Chemistry: various alchemical symbols, engraving by A. Bell", "wellcome.org/works/strv85ym"),
    "fludd_1": ("b7b2k69b", "Robert Fludd, Utriusque Cosmi (1617–21), plate", None),
    "fludd_2": ("fh9d443m", "Robert Fludd, Utriusque Cosmi (1617–21), plate", None),
    "fludd_3": ("fmqz8dtv", "Robert Fludd, Utriusque Cosmi (1617–21), plate", None),
    "fludd_4": ("pgc48yyj", "Robert Fludd, Utriusque Cosmi (1617–21), plate", None),
    "fludd_5": ("qcp3beqv", "Robert Fludd, Utriusque Cosmi (1617–21), plate", None),
    "fludd_6": ("rvm8r2e9", "Robert Fludd, Utriusque Cosmi (1617–21), plate", None),
    "remmelin_1": ("bfscmvwj", "Johann Remmelin, Survey of the Microcosme (flap anatomy)", None),
    "remmelin_2": ("dsgg4jv7", "Johann Remmelin, Survey of the Microcosme (flap anatomy)", None),
    "remmelin_3": ("crbruata", "Johann Remmelin, Catoptrum microcosmicum (1613 / 1619), flap plate", None),
    "remmelin_4": ("d6fgz5nj", "Johann Remmelin, Catoptrum microcosmicum, flap plate", None),
}
NAMED_COMMONS = {
    "dore_paradiso_31": ("Paradiso_Canto_31.jpg", "Gustave Doré, Paradiso Canto 31 (1867), the Empyrean", "Public domain"),
    "flammarion": ("Flammarion.jpg", "Flammarion engraving, from L'atmosphère: météorologie populaire (1888)", "Public domain"),
}
NAMED_WIKI = {"k_still": "K (Blade Runner 2049)"}   # tried as article titles for an infobox image


def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=60, **kw)
        return r if r.status_code == 200 else None
    except requests.RequestException:
        return None


def themes(per):
    H.CREDITS = D3 / "collage_credits.json"
    H.QUERIES = THEMES
    H.main.__globals__["CREDITS"] = H.CREDITS
    sys.argv = [sys.argv[0], str(per)]
    H.main()


def named():
    out = ROOT / "assets" / "v3"
    out.mkdir(parents=True, exist_ok=True)
    cred_p = D3 / "named_credits.json"
    cred = json.loads(cred_p.read_text()) if cred_p.exists() else {}
    for key, (iid, title, page) in NAMED_WELLCOME.items():
        if key in cred and (out / f"{key}.jpg").exists():
            continue
        r = get(f"https://api.wellcomecollection.org/catalogue/v2/images/{iid}")
        if not r:
            print("  ✗", key)
            continue
        j = r.json()
        loc = j["locations"][0]
        base = loc["url"].replace("/info.json", "")
        img = get(f"{base}/full/1600,/0/default.jpg") or get(f"{base}/full/1000,/0/default.jpg")
        if not img:
            print("  ✗ img", key)
            continue
        (out / f"{key}.jpg").write_bytes(img.content)
        work = j.get("source", {}).get("id", "")
        cred[key] = {"title": title, "licence": f"{loc.get('license', {}).get('label', 'Public Domain Mark')} (Wellcome Collection)",
                     "page": f"https://wellcomecollection.org/works/{work}" if work else f"https://{page}", "local": f"assets/v3/{key}.jpg"}
        print("  ✓", key)
    if (out / "valentine_symbols_1671.jpg").exists():
        cred["valentine_symbols_1671"] = {"title": "A table of the chymical and philosophical characters, with their signification (Basil Valentine, 1671)",
                                          "licence": "Public domain (Science History Institute)",
                                          "page": "https://digital.sciencehistory.org/works/9306sz691", "local": "assets/v3/valentine_symbols_1671.jpg"}
    cred_p.write_text(json.dumps(cred, indent=1, ensure_ascii=False))


def commons():
    out = ROOT / "assets" / "v3"
    cred_p = D3 / "named_credits.json"
    cred = json.loads(cred_p.read_text()) if cred_p.exists() else {}
    for key, (fname, title, lic) in NAMED_COMMONS.items():
        if (out / f"{key}.jpg").exists():
            continue
        n = fname.replace(" ", "_")
        h = hashlib.md5(n.encode()).hexdigest()
        q = quote(n)
        for url in (f"https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/1280px-{q}",
                    f"https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/960px-{q}",
                    f"https://upload.wikimedia.org/wikipedia/commons/{h[0]}/{h[:2]}/{q}"):
            r = get(url)
            if r and r.headers.get("content-type", "").startswith("image"):
                (out / f"{key}.jpg").write_bytes(r.content)
                cred[key] = {"title": title, "licence": lic, "page": f"https://commons.wikimedia.org/wiki/File:{q}", "local": f"assets/v3/{key}.jpg"}
                print("  ✓", key)
                break
        else:
            print("  ✗", key, "(rate-limited or missing)")
    cred_p.write_text(json.dumps(cred, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "themes"
    if mode == "themes":
        themes(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    elif mode == "named":
        named()
    elif mode == "commons":
        commons()
