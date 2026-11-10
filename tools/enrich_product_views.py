"""Add verified Akoni studio views without replacing the supplied originals."""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/data/catalog.json"
PUBLIC = ROOT / "docs/media/products"
ORIGINALS = ROOT.parents[1] / "output/akoni-originals/media/products"
MANIFEST = ROOT / "data/product-views-manifest.json"


def alternate_urls(source: str) -> list[tuple[str, str]]:
    parts = urlsplit(source)
    name = Path(parts.path).name
    match = re.search(r"([_-])1(?=(_HD(?:_HiRes)?|_HiRes)?\.(?:jpe?g|png)$)", name, re.I)
    if not match:
        return []
    prefix = parts.path[: -len(name)]
    return [
        (view, urlunsplit((parts.scheme, parts.netloc, prefix + name[:match.start()] + match.group(1) + digit + name[match.end():], "", "")))
        for view, digit in (("front", "2"), ("side", "3"))
    ]


def download(url: str) -> dict | None:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    ext = Path(urlsplit(url).path).suffix.lower()
    original = ORIGINALS / f"akoni-view-{digest}{ext}"
    web = PUBLIC / f"akoni-view-{digest}.webp"
    if not web.exists():
        for attempt in range(2):
            try:
                response = requests.get(url, timeout=35)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                if not response.headers.get("content-type", "").startswith("image/"):
                    return None
                raw = response.content
                with Image.open(BytesIO(raw)) as image:
                    image.verify()
                ORIGINALS.mkdir(parents=True, exist_ok=True)
                PUBLIC.mkdir(parents=True, exist_ok=True)
                original.write_bytes(raw)
                with Image.open(BytesIO(raw)) as image:
                    image.thumbnail((1400, 1400))
                    image.convert("RGB").save(web, "WEBP", quality=85, method=5)
                break
            except (requests.RequestException, OSError):
                if attempt:
                    return None
                time.sleep(1)
    if not web.exists():
        return None
    with Image.open(web) as image:
        background = image.convert("RGB").getpixel((0, 0))
    return {
        "source": url,
        "path": "media/products/" + web.name,
        "originalSha256": hashlib.sha256(original.read_bytes()).hexdigest() if original.exists() else None,
        "webSha256": hashlib.sha256(web.read_bytes()).hexdigest(),
        "background": list(background),
        "webBytes": web.stat().st_size,
    }


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    candidates = {
        url
        for model in catalog
        for variant in model["variants"]
        for _, url in alternate_urls(variant.get("imageSource", ""))
        if urlsplit(url).netloc == "cdn.shopify.com"
    }
    found = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(download, url): url for url in sorted(candidates)}
        for future in as_completed(futures):
            result = future.result()
            if result:
                found[futures[future]] = result
    for model in catalog:
        for variant in model["variants"]:
            extra = dict(alternate_urls(variant.get("imageSource", "")))
            front = found.get(extra.get("front"))
            side = found.get(extra.get("side"))
            gallery = []
            if front:
                gallery.append({"view": "front", "path": front["path"]})
            if variant.get("image"):
                gallery.append({"view": "angle" if front else "front", "path": variant["image"]})
            if side:
                gallery.append({"view": "side", "path": side["path"]})
            if variant.get("side") and (not side or variant["side"] != side["path"]):
                gallery.append({"view": "side" if not side else "detail", "path": variant["side"]})
            if gallery:
                variant["gallery"] = gallery
    paths = {entry["path"] for model in catalog for variant in model["variants"] for entry in variant.get("gallery", [])}
    def background(path: str) -> tuple[str, str]:
        with Image.open(ROOT / "docs" / path) as image:
            red, green, blue = image.convert("RGB").getpixel((0, 0))
        return path, f"#{red:02x}{green:02x}{blue:02x}"
    with ThreadPoolExecutor(max_workers=6) as pool:
        backgrounds = dict(pool.map(background, sorted(paths)))
    for model in catalog:
        for variant in model["variants"]:
            for entry in variant.get("gallery", []):
                entry["background"] = backgrounds[entry["path"]]
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    MANIFEST.write_text(json.dumps({"source": "Akoni official product photo series", "assets": sorted(found.values(), key=lambda x: x["path"]), "candidateCount": len(candidates), "downloadedCount": len(found), "unavailable": sorted(candidates - found.keys())}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Verified {len(found)} of {len(candidates)} additional studio views; {sum(x['webBytes'] for x in found.values()) / 1e6:.1f} MB web assets")


if __name__ == "__main__":
    main()
