"""CalRecycle Solid Waste Information System (SWIS): landfill list for the screening tier.

Checked live on 2026-10-17. The SWIS site search, a site's activities and its
details page are public, with no login:

- ``POST /SolidWaste/Site/_GridRead`` with ``filter=County~eq~'<name>'``: sites by county.
- ``POST /SolidWaste/SiteActivity/_GridRead`` with ``siteID``: the site's activities
  (for example "Solid Waste Landfill", category "Disposal").
- ``GET /SolidWaste/Site/Details/<id>``: address and coordinates (HTML).

A site enters the screening list when one of its activities is "Solid Waste
Landfill", active or closed. This is a sourced stand-in until the Air District
supplies its Rule 8-34 facility list.
"""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch.provenance import PullManifest

BASE = "https://www2.calrecycle.ca.gov/SolidWaste"
LANDFILL = "Solid Waste Landfill"
BAY_AREA_COUNTIES = [
    "Alameda",
    "Contra Costa",
    "Marin",
    "Napa",
    "San Francisco",
    "San Mateo",
    "Santa Clara",
    "Solano",
    "Sonoma",
]


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _request(client: httpx.Client, method: str, path: str, **kw) -> httpx.Response:
    r = client.request(method, f"{BASE}{path}", timeout=60, **kw)
    r.raise_for_status()
    return r


def parse_details(page: str) -> dict:
    """Address and coordinates from a SWIS details page."""
    text = re.sub(r"<script.*?</script>", "", page, flags=re.S)
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text)))
    m = re.search(
        r"Site Location Address (.*?) County .*?Latitude: ([-\d.]+) Longitude: ([-\d.]+)", text
    )
    if not m:
        return {"address": None, "latitude": None, "longitude": None}
    return {
        "address": m.group(1).strip(),
        "latitude": float(m.group(2)),
        "longitude": float(m.group(3)),
    }


def pull(raw_root: Path, pause_s: float = 0.2) -> Path:
    manifest = PullManifest.start(
        "calrecycle",
        f"{BASE}/Site/_GridRead; {BASE}/SiteActivity/_GridRead; {BASE}/Site/Details",
        {"counties": BAY_AREA_COUNTIES, "activity": LANDFILL},
    )
    pull_dir = raw_root / "calrecycle" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    sites, activities, details = [], {}, {}
    with httpx.Client(follow_redirects=True) as client:
        for county in BAY_AREA_COUNTIES:
            data = {"page": 1, "pageSize": 2000, "filter": f"County~eq~'{county}'"}
            sites += _request(client, "POST", "/Site/_GridRead", data=data).json()["Data"]
        for s in sites:
            data = {"page": 1, "pageSize": 200, "siteID": s["ID"]}
            acts = _request(client, "POST", "/SiteActivity/_GridRead", data=data).json()["Data"]
            activities[s["ID"]] = acts
            if any(a["Activity"] == LANDFILL for a in acts):
                page = _request(client, "GET", f"/Site/Details/{s['ID']}").text
                details[s["ID"]] = parse_details(page)
            time.sleep(pause_s)
    files = []
    for name, obj in [("sites", sites), ("activities", activities), ("details", details)]:
        path = pull_dir / f"{name}.json"
        path.write_text(json.dumps(obj, indent=1))
        files.append(path)
    manifest.finish(pull_dir, files, n_records=len(sites))
    return pull_dir


def landfills(pull_dir: Path) -> pd.DataFrame:
    """One row per site with a Solid Waste Landfill activity."""
    sites = json.loads((pull_dir / "sites.json").read_text())
    acts = json.loads((pull_dir / "activities.json").read_text())
    details = json.loads((pull_dir / "details.json").read_text())
    rows = []
    for s in sites:
        lf = [a for a in acts.get(str(s["ID"]), []) if a["Activity"] == LANDFILL]
        if not lf:
            continue
        d = details.get(str(s["ID"]), {})
        rows.append(
            {
                "swis_number": s["SWISNumber"],
                "name": s["Name"],
                "county": s["County"],
                "site_status": s["SiteOperationalStatus"],
                "landfill_status": lf[0]["OperationalStatus"],
                "regulatory_status": lf[0]["RegulatoryStatus"],
                "address": d.get("address"),
                "latitude": d.get("latitude"),
                "longitude": d.get("longitude"),
                "swis_url": f"{BASE}/Site/Details/{s['ID']}",
            }
        )
    return pd.DataFrame(rows).sort_values(["county", "swis_number"]).reset_index(drop=True)
