"""Keep the supplied originals locally and publish browser-sized copies."""
from __future__ import annotations

import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ROOT.parents[1] / "output" / "akoni-originals"
PUBLIC = ROOT / "docs"
CATALOG = PUBLIC / "data" / "catalog.json"
PLAN = ROOT / "data" / "drive-download-plan.json"


def optimize(entry: dict) -> dict:
    relative = Path(entry["path"])
    source = PUBLIC / relative
    archived = ORIGINALS / relative
    target = source.with_suffix(".webp")
    archived.parent.mkdir(parents=True, exist_ok=True)
    if source.exists() and not archived.exists():
        shutil.move(str(source), str(archived))
    if not archived.exists():
        raise FileNotFoundError(archived)
    if not target.exists():
        with Image.open(archived) as image:
            image.thumbnail((1800, 1400))
            image.convert("RGB").save(target, "WEBP", quality=83, method=5)
    return {**entry, "webPath": str(target.relative_to(PUBLIC)).replace("\\", "/"),
            "originalSha256": hashlib.sha256(archived.read_bytes()).hexdigest(),
            "webSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "webSize": target.stat().st_size}


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        optimized = list(pool.map(optimize, plan))
    mapping = {x["path"]: x["webPath"] for x in optimized}
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for model in catalog:
        for variant in model["variants"]:
            for field in ("image", "side"):
                if variant.get(field) in mapping:
                    variant[field] = mapping[variant[field]]
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ROOT / "data" / "optimized-assets.json").write_text(json.dumps(optimized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Optimized {len(optimized)} images from {sum(x['size'] for x in optimized)/1e6:.1f} MB to {sum(x['webSize'] for x in optimized)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
