"""EPA GHGRP subpart HH (municipal landfills) operator-reported methane (PLAN 5, phase 2e).

Source: EPA Envirofacts REST API (public, no key), tables
``pub_dim_facility`` and ``pub_facts_subp_ghg_emission``. Emissions are
published in t CO2e, so methane tonnes depend on the GWP EPA applied for the
reporting year (``config/impact.yaml: ghgrp_gwp_ch4``; unconfirmed until
checked against EPA's documentation). See docs/decisions/0007-public-sources.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch import schemas
from methanewatch.provenance import PullManifest

BASE = "https://data.epa.gov/efservice"
SUBPART_HH = 31
GAS_CH4 = 2
BAY_AREA_COUNTIES = {
    "ALAMEDA",
    "CONTRA COSTA",
    "MARIN",
    "NAPA",
    "SAN FRANCISCO",
    "SAN MATEO",
    "SANTA CLARA",
    "SOLANO",
    "SONOMA",
}


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, path: str) -> list[dict]:
    r = client.get(f"{BASE}/{path}/JSON", timeout=120)
    r.raise_for_status()
    return r.json()


def bay_area_facilities(year: int, client: httpx.Client | None = None) -> pd.DataFrame:
    """Facilities in the nine Bay Area counties that reported subpart HH in ``year``."""
    with client or httpx.Client() as c:
        rows = _get(c, f"pub_dim_facility/state/=/CA/reported_subparts/CONTAINING/HH/year/=/{year}")
    df = pd.DataFrame(rows)
    county = df["county"].fillna("").str.upper().str.replace(" COUNTY", "", regex=False)
    keep = df[county.isin(BAY_AREA_COUNTIES)]
    return keep[["facility_id", "facility_name", "city", "county", "latitude", "longitude", "year"]]


def pull_reports(facility_ids: list[str], raw_root: Path) -> Path:
    """Download subpart HH methane rows for each facility into a raw pull directory."""
    manifest = PullManifest.start(
        "ghgrp", f"{BASE}/pub_facts_subp_ghg_emission", {"facility_ids": facility_ids}
    )
    pull_dir = raw_root / "ghgrp" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    files, n = [], 0
    with httpx.Client() as c:
        for fid in facility_ids:
            rows = _get(c, f"pub_facts_subp_ghg_emission/facility_id/=/{fid}")
            path = pull_dir / f"{fid}.json"
            path.write_text(json.dumps(rows, indent=1))
            files.append(path)
            n += len(rows)
    manifest.finish(pull_dir, files, n_records=n)
    return pull_dir


def normalize(
    pull_dir: Path, crosswalk: pd.DataFrame, gwp_by_year: dict[int, float]
) -> pd.DataFrame:
    """Rows for subpart HH methane, mapped to ``site_id`` via the crosswalk."""
    files = [p for p in sorted(pull_dir.glob("*.json")) if p.name != "manifest.json"]
    rows = [r for p in files for r in json.loads(p.read_text())]
    df = pd.DataFrame(rows)
    df = df[(df["sub_part_id"] == SUBPART_HH) & (df["gas_id"] == GAS_CH4)].copy()
    xw = crosswalk.dropna(subset=["ghgrp_facility_id"]).astype({"ghgrp_facility_id": str})
    df["facility_id"] = df["facility_id"].astype(str)
    df = df.merge(
        xw[["site_id", "ghgrp_facility_id"]], left_on="facility_id", right_on="ghgrp_facility_id"
    )
    # Years without a configured GWP are left out rather than converted with a guess.
    df = df[df["year"].isin(gwp_by_year)]
    df["reported_co2e_t"] = df["co2e_emission"].astype(float)
    df["gwp_used"] = df["year"].map(gwp_by_year)
    df["reported_ch4_t"] = df["reported_co2e_t"] / df["gwp_used"]
    df["source"] = "GHGRP"
    df["url"] = BASE + "/pub_facts_subp_ghg_emission/facility_id/=/" + df["facility_id"]
    df["pull_id"] = pull_dir.name
    out = df[
        [
            "site_id",
            "year",
            "source",
            "reported_ch4_t",
            "reported_co2e_t",
            "gwp_used",
            "facility_id",
            "url",
            "pull_id",
        ]
    ]
    return schemas.operator_reports.validate(out.reset_index(drop=True))
