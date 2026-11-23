"""Small helpers for polite access to Wikimedia, The Met and Ghibli (retry + backoff)."""
import re
import time

import requests

UA = {"User-Agent": "HeroArchetypesExplainer/1.0 (educational video build; python-requests)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"
ENWIKI = "https://en.wikipedia.org/w/api.php"
MET = "https://collectionapi.metmuseum.org/public/collection/v1"

_last = {"t": 0.0}


def get(url, params=None, stream=False, min_gap=1.2, tries=8):
    for attempt in range(tries):
        wait = _last["t"] + min_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last["t"] = time.time()
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60, stream=stream)
        except requests.RequestException:
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            ra = r.headers.get("retry-after")
            time.sleep(float(ra) + 1 if ra and ra.isdigit() else 5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"gave up on {url} {params}")


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def commons_info(title, api=COMMONS, thumb=None):
    """imageinfo + licence metadata for a File: title (Commons or en-wiki local)."""
    if not title.startswith("File:"):
        title = "File:" + title
    p = {"action": "query", "format": "json", "titles": title, "prop": "imageinfo",
         "iiprop": "url|size|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist|Credit|DateTimeOriginal|ImageDescription|NonFree"}
    if thumb:
        p["iiurlwidth"] = thumb
    pages = get(api, p).json()["query"]["pages"]
    page = next(iter(pages.values()))
    if "imageinfo" not in page:
        return None
    ii = page["imageinfo"][0]
    m = ii.get("extmetadata", {})
    return {
        "title": page["title"],
        "url": ii["url"],
        "thumb": ii.get("thumburl"),
        "page": ii.get("descriptionurl"),
        "width": ii["width"], "height": ii["height"],
        "licence": strip_html(m.get("LicenseShortName", {}).get("value", "")) or "unknown",
        "artist": strip_html(m.get("Artist", {}).get("value", ""))[:120],
        "date": strip_html(m.get("DateTimeOriginal", {}).get("value", ""))[:60],
        "nonfree": bool(m.get("NonFree", {}).get("value")),
    }


def wiki_page_image(article):
    """Lead image file name of an English Wikipedia article."""
    j = get(ENWIKI, {"action": "query", "format": "json", "titles": article, "prop": "pageimages",
                     "piprop": "name|original", "redirects": 1}).json()
    page = next(iter(j["query"]["pages"].values()))
    name = page.get("pageimage")
    return name


def met_object(oid):
    return get(f"{MET}/objects/{oid}", min_gap=0.2).json()


def download(url, dest, min_gap=1.0):
    r = get(url, stream=True, min_gap=min_gap)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    return dest
