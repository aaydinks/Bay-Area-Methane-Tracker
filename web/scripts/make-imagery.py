"""Pictures for the home page, made once and committed under src/assets/imagery/.

- bay.jpg: the Bay Area from Sentinel-2 (true colour, 17 June 2025, tiles 10SEG and 10SEH), read
  from the open Earth Search copy of the Copernicus archive. Free to use with the Copernicus
  credit line.
- <site_id>.jpg: an aerial close-up of each landfill from the USGS NAIP Plus image service
  (USDA NAIP and other orthoimagery from The National Map), credited as the service asks.
- imagery.json: credits, sources and where each landfill sits on bay.jpg (as fractions of its
  width and height), so the page can place markers without a projection library.

Nothing here runs at build time. Run from the repository root after the site list changes:

    uv run --with pillow python web/scripts/make-imagery.py

Site centres come from the published snapshot (web/src/data/snapshot.json, written by
`npm run fetch`). No site outline is drawn: the outlines are still provisional.
"""

from __future__ import annotations

import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.merge import merge

WEB = Path(__file__).resolve().parent.parent
OUT = WEB / "src" / "assets" / "imagery"
SNAPSHOT = WEB / "src" / "data" / "snapshot.json"

SCENE = "S2C_T10S{tile}_20250617T190057_L2A"
TCI = (
    "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/"
    "sentinel-2-c1-l2a/10/S/{tile}/2025/6/" + SCENE + "/TCI.tif"
)
BAY_BOUNDS = (-122.84, 37.34, -121.78, 38.36)  # lon/lat: Petaluma to Milpitas, coast to Suisun
BAY_RES_M = 50.0
NAIP = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer/exportImage"
CLOSEUP_WIDTH_M = 2600.0
CLOSEUP_PX = (1600, 1200)
SAVED_WIDTH = 1200  # wide enough for a sharp picture at twice its largest size on the page

CREDITS = {
    # The Copernicus credit line, and the credit the USGS service names in its own description.
    "bay": "Contains modified Copernicus Sentinel data 2025.",
    "sites": "USGS, USDA, The National Map: Orthoimagery.",
}


def save(img: Image.Image, path: Path) -> None:
    height = round(img.height * SAVED_WIDTH / img.width)
    img.resize((SAVED_WIDTH, height), Image.Resampling.LANCZOS).save(
        path, quality=82, optimize=True, progressive=True
    )


def bay(sites: list[dict]) -> dict:
    to_utm = Transformer.from_crs(4326, 32610, always_xy=True)
    x0, y0 = to_utm.transform(BAY_BOUNDS[0], BAY_BOUNDS[1])
    x1, y1 = to_utm.transform(BAY_BOUNDS[2], BAY_BOUNDS[3])
    sources = [rasterio.open(TCI.format(tile=t)) for t in ("EG", "EH")]
    arr, _ = merge(sources, bounds=(x0, y0, x1, y1), res=BAY_RES_M, resampling=Resampling.average)
    img = np.moveaxis(arr, 0, -1)
    if (img.max(axis=2) == 0).mean() > 0.001:
        sys.exit("make-imagery: the Sentinel-2 mosaic has empty pixels; pick a fully covered scene")
    save(Image.fromarray(img), OUT / "bay.jpg")
    marks = {}
    for s in sites:
        e, n = to_utm.transform(s["lon"], s["lat"])
        marks[s["site_id"]] = {
            "x": round((e - x0) / (x1 - x0), 4),
            "y": round((y1 - n) / (y1 - y0), 4),
        }
    return {
        "file": "bay.jpg",
        "scene": [SCENE.format(tile=t) for t in ("EG", "EH")],
        "date": "2025-06-17",
        "bounds_lonlat": BAY_BOUNDS,
        "width": SAVED_WIDTH,
        "height": round(img.shape[0] * SAVED_WIDTH / img.shape[1]),
        "sites": marks,
    }


def closeup(site: dict) -> dict:
    to_merc = Transformer.from_crs(4326, 3857, always_xy=True)
    cx, cy = to_merc.transform(site["lon"], site["lat"])
    # Web Mercator stretches ground distance by 1/cos(latitude)
    w = CLOSEUP_WIDTH_M / math.cos(math.radians(site["lat"]))
    h = w * CLOSEUP_PX[1] / CLOSEUP_PX[0]
    query = urllib.parse.urlencode(
        {
            "bbox": f"{cx - w / 2},{cy - h / 2},{cx + w / 2},{cy + h / 2}",
            "bboxSR": 3857,
            "imageSR": 3857,
            "size": f"{CLOSEUP_PX[0]},{CLOSEUP_PX[1]}",
            "format": "jpg",
            "f": "image",
        }
    )
    data = None
    for attempt in range(8):
        try:
            data = urllib.request.urlopen(f"{NAIP}?{query}", timeout=180).read()
            break
        except OSError as err:  # the service often answers 502 or 504; it recovers
            print(f"make-imagery: {site['site_id']} attempt {attempt + 1}: {err}", file=sys.stderr)
            time.sleep(10)
    if data is None:
        sys.exit(f"make-imagery: no aerial image for {site['site_id']}")
    save(Image.open(io.BytesIO(data)).convert("RGB"), OUT / f"{site['site_id']}.jpg")
    return {
        "file": f"{site['site_id']}.jpg",
        "width_m": CLOSEUP_WIDTH_M,
        "centre": [site["lon"], site["lat"]],
    }


def main() -> None:
    sites = [
        {"site_id": s["site_id"], "lon": s["lon"], "lat": s["lat"]}
        for s in json.loads(SNAPSHOT.read_text())["sites"]
        if s.get("lon") is not None and s.get("lat") is not None
    ]
    if not sites:
        sys.exit("make-imagery: no site centres in the snapshot; run `npm run fetch` first")
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"credits": CREDITS, "bay": bay(sites), "sites": {}}
    for s in sites:
        meta["sites"][s["site_id"]] = closeup(s)
        print(f"make-imagery: {s['site_id']}")
    (OUT / "imagery.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"make-imagery: wrote bay.jpg and {len(sites)} close-ups to {OUT}")


if __name__ == "__main__":
    main()
