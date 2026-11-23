"""Download every image in assets/image_manifest.yaml and record its licence/credit.

Usage:  python tools/fetch_images.py [id ...]     (no ids = everything missing)
Writes: assets/public_domain/<id>.<ext>, assets/stills/<id>.<ext>, build/image_credits.json

Wikimedia files are fetched straight from upload.wikimedia.org (the file path is
derived from the MD5 of the file name), which avoids the API's strict rate limits.
"""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
MAN = yaml.safe_load((ROOT / "assets" / "image_manifest.yaml").read_text(encoding="utf-8"))
CREDITS = ROOT / "build" / "image_credits.json"
UA = {"User-Agent": "HeroArchetypesExplainer/1.0 (educational video build)"}
THUMB_W = 1920  # standard Wikimedia thumbnail width; plenty for 1080p cutouts


def wm_urls(name, wiki):
    n = name.replace(" ", "_")
    h = hashlib.md5(n.encode("utf-8")).hexdigest()
    q = quote(n)
    base = f"https://upload.wikimedia.org/wikipedia/{wiki}"
    thumb_name = q + (".jpg" if n.lower().endswith((".tif", ".tiff")) else "")
    orig = f"{base}/{h[0]}/{h[:2]}/{q}"
    # standard thumbnail steps are cached and allowed; big originals get throttled
    return [f"{base}/thumb/{h[0]}/{h[:2]}/{q}/{w}px-{thumb_name}" for w in (1280, 960)] + [orig]


def page_url(name, wiki):
    host = "commons.wikimedia.org" if wiki == "commons" else "en.wikipedia.org"
    return f"https://{host}/wiki/File:{quote(name.replace(' ', '_'))}"


def try_get(url, tries=int(__import__("os").environ.get("FETCH_TRIES", "3"))):
    import time
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=90)
        except requests.RequestException:
            time.sleep(3 + 2 * attempt)
            continue
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("image/"):
            time.sleep(1.0)
            return r
        if r.status_code == 429 or r.status_code >= 500:
            if attempt == tries - 1:
                return None
            ra = r.headers.get("retry-after", "")
            time.sleep((float(ra) if ra.replace(".", "").isdigit() else 4) + 2 * attempt)
            continue
        return None  # 404 etc.
    return None


def main():
    credits = json.loads(CREDITS.read_text()) if CREDITS.exists() else {}
    want = sys.argv[1:] or list(MAN)
    for iid in want:
        e = MAN[iid]
        d = ROOT / "assets" / ("public_domain" if e["kind"] == "pd" else "stills")
        d.mkdir(parents=True, exist_ok=True)
        if any(d.glob(f"{iid}.*")) and iid in credits and len(sys.argv) == 1:
            continue
        got, page = None, None
        if e["source"] in ("commons", "enwiki"):
            order = ["commons", "en"] if e["source"] == "commons" else ["en", "commons"]
            for wiki in order:
                for url in wm_urls(e["file"], wiki):
                    r = try_get(url)
                    if r:
                        got, page = (r, url), page_url(e["file"], wiki)
                        break
                if got:
                    break
        elif e["source"] == "cleveland":
            j = requests.get(f"https://openaccess-api.clevelandart.org/api/artworks/{e['id']}", headers=UA, timeout=60).json()["data"]
            imgs = j.get("images") or {}
            for k in ("print", "web"):
                if imgs.get(k):
                    r = try_get(imgs[k]["url"])
                    if r:
                        got, page = (r, imgs[k]["url"]), j.get("url")
                        e = {**e, "subject": e["subject"].split(" (Cleveland")[0] + f" (Cleveland Museum of Art {j.get('accession_number')})"}
                        break
        elif e["source"] == "aic":
            j = requests.get(f"https://api.artic.edu/api/v1/artworks/{e['id']}", params={"fields": "id,title,image_id,artist_display,date_display"},
                             headers=UA, timeout=60).json()["data"]
            for w in (2400, 1686, 843):
                url = f"https://www.artic.edu/iiif/2/{j['image_id']}/full/{w},/0/default.jpg"
                r = try_get(url)
                if r:
                    got, page = (r, url), f"https://www.artic.edu/artworks/{e['id']}"
                    break
        elif e["source"] == "ghibli":
            url = f"https://www.ghibli.jp/gallery/{e['file']}"
            r = try_get(url)
            if r:
                got, page = (r, url), "https://www.ghibli.jp/info/013344/"
        if not got:
            print(f"  ✗ {iid}: not found ({e.get('file')})", flush=True)
            continue
        r, url = got
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(
            r.headers["content-type"].split(";")[0], ".jpg")
        for old in d.glob(f"{iid}.*"):
            old.unlink()
        dest = d / f"{iid}{ext}"
        dest.write_bytes(r.content)
        try:  # keep working copies at a sane size (long side ≤ 2400 px)
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            im = Image.open(dest)
            if max(im.size) > 2400:
                im.thumbnail((2400, 2400), Image.LANCZOS)
                if dest.suffix == ".jpg":
                    im.convert("RGB").save(dest, quality=92)
                else:
                    im.save(dest)
        except Exception as ex:
            print("   (resize skipped:", ex, ")")
        credits[iid] = {
            "subject": e["subject"], "kind": e["kind"], "source": e["source"], "file": e.get("file"),
            "licence": e.get("licence") or ("Studio Ghibli free-use stills" if e["source"] == "ghibli" else "see source page"),
            "page": page, "url": url, "local": str(dest.relative_to(ROOT)),
        }
        print(f"  ✓ {iid:16} {len(r.content)//1024:6d} KB  {credits[iid]['licence'][:50]}", flush=True)
        CREDITS.parent.mkdir(exist_ok=True)
        CREDITS.write_text(json.dumps(credits, indent=1, ensure_ascii=False), encoding="utf-8")
    missing = [i for i in MAN if not any((ROOT / "assets" / ("public_domain" if MAN[i]["kind"] == "pd" else "stills")).glob(f"{i}.*"))]
    print("missing:", missing or "none")


if __name__ == "__main__":
    main()
