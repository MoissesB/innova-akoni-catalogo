"""Build the Akoni catalog from the supplied ecommerce workbook and official sitemap."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

import openpyxl
import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "akoni-ecom-info.xlsx"
DRIVE = ROOT / "data" / "drive-inventory.json"
OUT = ROOT / "docs" / "data" / "catalog.json"
MEDIA = ROOT / "docs" / "media" / "products"
SITEMAP = "https://akoni.com/sitemap_products_1.xml?from=9714514297179&to=10856116486491"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9", "i": "http://www.google.com/schemas/sitemap-image/1.1"}


def norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().replace("\ufffd", "’")


def get_sitemap() -> list[dict]:
    response = requests.get(SITEMAP, timeout=45)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    records = []
    for node in root.findall("s:url", NS):
        product_url = node.findtext("s:loc", default="", namespaces=NS)
        image_url = node.findtext("i:image/i:loc", default="", namespaces=NS)
        if image_url and "/products/" in product_url:
            records.append({"productUrl": product_url, "imageUrl": image_url, "file": urlsplit(image_url).path.split("/")[-1]})
    return records


def download_one(record: dict) -> dict:
    name = hashlib.sha256(record["imageUrl"].encode()).hexdigest()[:16] + Path(record["file"]).suffix.lower()
    target = MEDIA / name
    if not target.exists():
        response = requests.get(record["imageUrl"], timeout=45)
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("image/"):
            raise ValueError(f"Not an image: {record['imageUrl']}")
        target.write_bytes(response.content)
    return {**record, "path": f"media/products/{name}", "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "size": target.stat().st_size}


def main() -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sitemap = get_sitemap()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        downloaded = list(pool.map(download_one, sitemap))
    drive = json.loads(DRIVE.read_text(encoding="utf-8"))
    drive_files = drive["stills"] + drive["white"]
    worksheet = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True).active
    groups: dict[tuple[str, str], dict] = {}
    drive_plan: dict[str, dict] = {}
    used_sitemap: set[str] = set()
    for row in list(worksheet.values)[6:]:
        if not row[0] or not row[2]:
            continue
        name = clean(row[0]).replace("  ", " ").upper()
        sku = clean(row[2]).upper()
        category_raw = clean(row[21]).upper()
        category = "sol" if category_raw == "SUNGLASS" or sku.startswith("AKS-") else "optica"
        key = (name, category)
        group = groups.setdefault(key, {"id": slug(name + "-" + category), "name": name, "category": category, "descriptionEn": clean(row[3]), "season": clean(row[22]), "variants": []})
        sku_key = norm(sku)
        exact = next((item for item in downloaded if sku_key in norm(item["file"])), None)
        if exact:
            used_sitemap.add(exact["imageUrl"])
        candidates = [f for f in drive_files if sku_key in norm(f["name"]) and re.search(r"(?:-FR|_FR|FRONT)", f["name"].upper())]
        drive_front = candidates[0] if candidates else None
        if not exact and drive_front:
            drive_plan[drive_front["id"]] = {"id": drive_front["id"], "name": drive_front["name"], "size": drive_front["size"], "path": f"media/products/drive-{drive_front['id']}.jpg"}
        sides = [f for f in drive_files if sku_key in norm(f["name"]) and re.search(r"(?:-SIDE|_SIDE)", f["name"].upper())]
        side = sides[0] if sides else None
        if side and (exact or drive_front):
            drive_plan[side["id"]] = {"id": side["id"], "name": side["name"], "size": side["size"], "path": f"media/products/drive-{side['id']}.jpg"}
        group["variants"].append({
            "sku": sku, "ean": clean(row[1]), "color": clean(row[4]), "colorCode": clean(row[5]),
            "size": clean(row[7]), "bridge": clean(row[8]), "temple": clean(row[9]),
            "frontMaterial": clean(row[10]), "templeMaterial": clean(row[11]),
            "lensMaterial": clean(row[12]), "lensCategory": clean(row[14]),
            "madeIn": clean(row[15]), "season": clean(row[22]),
            "image": exact["path"] if exact else (f"media/products/drive-{drive_front['id']}.jpg" if drive_front else ""),
            "imageSource": exact["imageUrl"] if exact else (f"https://drive.google.com/file/d/{drive_front['id']}/view" if drive_front else ""),
            "side": f"media/products/drive-{side['id']}.jpg" if side else "",
            "officialUrl": exact["productUrl"] if exact else "",
        })
    # New public products absent from the workbook remain visible with only fields verified in the sitemap.
    for item in downloaded:
        if item["imageUrl"] in used_sitemap:
            continue
        image_name = norm(item["file"])
        if not ("AKS" in image_name or "AKX" in image_name):
            continue
        handle = item["productUrl"].rstrip("/").split("/")[-1]
        name = handle.split("-aks-")[0].split("-akx-")[0].replace("akoni-", "").replace("-", " ").upper()
        sku_match = re.search(r"(AK[XS])[_-]?(\d{3}[A-Z])[_-]?(\d{2})", item["file"].upper())
        sku = "-".join(sku_match.groups()) if sku_match else ""
        category = "sol" if "AKS" in image_name else "optica"
        key = (name, category)
        group = groups.setdefault(key, {"id": slug(name + "-" + category), "name": name, "category": category, "descriptionEn": "", "season": "", "variants": []})
        if sku and any(v["sku"] == sku for v in group["variants"]):
            continue
        group["variants"].append({"sku": sku, "ean": "", "color": "", "colorCode": "", "size": "", "bridge": "", "temple": "", "frontMaterial": "", "templeMaterial": "", "lensMaterial": "", "lensCategory": "", "madeIn": "", "season": "", "image": item["path"], "imageSource": item["imageUrl"], "side": "", "officialUrl": item["productUrl"]})
    products = list(groups.values())
    translations_path = ROOT / "data" / "descriptions-es.json"
    translations = json.loads(translations_path.read_text(encoding="utf-8")) if translations_path.exists() else {}
    for product in products:
        product["descriptionEs"] = translations.get(product["descriptionEn"], "")
    products.sort(key=lambda p: (not any(v["season"] == "FW26" for v in p["variants"]), p["name"], p["category"]))
    manifest = {"sourceWorkbook": "data/akoni-ecom-info.xlsx", "sourceSitemap": SITEMAP, "sitemapImages": downloaded, "driveCandidates": list(drive_plan.values()), "models": len(products), "variants": sum(len(p["variants"]) for p in products)}
    (ROOT / "data" / "media-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "data" / "drive-download-plan.json").write_text(json.dumps(list(drive_plan.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    OUT.write_text(json.dumps(products, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(products)} models, {manifest['variants']} variants, {len(downloaded)} official site images, {len(drive_plan)} Drive images planned")


if __name__ == "__main__":
    main()
