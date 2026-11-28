"""CalEnviroScreen 5.0: the state's score for the census tracts around each landfill (ADR 0026).

Checked live on 2026-11-28:

- OEHHA released the final CalEnviroScreen 5.0 on 2026-07-01. Its data download is the state
  data portal's dataset ``calenviroscreen-5-0``, which lists one geodatabase
  (``calenviroscreen50results_f_070126.gdb.zip``, about 22 MB).
- The geodatabase has one layer, ``CES5_final_results``: 9,106 census tracts (2020 Census
  outlines, EPSG:3310) with every indicator, the three percentiles used here and the tract's
  population (2024 five-year ACS).
- 73 tracts carry no overall score. OEHHA's data dictionary says a missing value usually means
  no population was reported or the estimate was unreliable.
- Neither the portal nor OEHHA's conditions of use state terms of reuse (the portal reads
  "License not specified"), so the source is unconfirmed in ``config/data_terms.yaml`` and its
  rows stay in review copies.

These are context measures (ADR 0020): they describe the area around a landfill and are never
attributed to it. Figures are written as OEHHA publishes them. Nothing is averaged across tracts.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch import schemas
from methanewatch.provenance import PullManifest

SOURCE = "calenviroscreen"  # the key of this source in config/data_terms.yaml
VERSION = "5.0"  # the period every figure is published under
DATASET = "calenviroscreen-5-0"
PACKAGE = "https://data.ca.gov/api/3/action/package_show"
PAGE = f"https://data.ca.gov/dataset/{DATASET}"
FORMAT = "GDB"
FILE = "results.gdb.zip"
NEAR_M = 1000.0  # tracts this close to the outline count as "around the landfill"

# Column names as the geodatabase writes them
C_TRACT = "tract"
C_POPULATION = "Population"
C_SCORE = "CIscoreP"
C_POLLUTION = "Pollution_Pctl"
C_POPCHAR = "PopCharPctl"
COLUMNS = (C_TRACT, C_POPULATION, C_SCORE, C_POLLUTION, C_POPCHAR)

# Measure ids in config/metrics.yaml, each with its unit
TRACT = "ces_tract"
TRACT_POPULATION = "ces_tract_population"
SCORE = "ces_score_percentile"
POLLUTION = "ces_pollution_percentile"
POPCHAR = "ces_population_percentile"
TRACTS_NEAR = "ces_tracts_nearby"
NEAR_LOWEST = "ces_nearby_lowest"
NEAR_HIGHEST = "ces_nearby_highest"
UNITS = {
    TRACT: "census tract",
    TRACT_POPULATION: "people",
    SCORE: "percentile",
    POLLUTION: "percentile",
    POPCHAR: "percentile",
    TRACTS_NEAR: "count",
    NEAR_LOWEST: "percentile",
    NEAR_HIGHEST: "percentile",
}


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    r = client.get(url, params=params, timeout=300)
    r.raise_for_status()
    return r


def geodatabase(package: dict) -> dict:
    """The dataset's one geodatabase, as the data portal lists it.

    Anything but exactly one stops the pull: a second file would mean a new edition, and which
    one to read is not guessed.
    """
    found = [r for r in package["result"]["resources"] if str(r.get("format")).upper() == FORMAT]
    if len(found) != 1:
        raise ValueError(
            f"expected one geodatabase in {DATASET} on the data portal, found {len(found)}"
        )
    return found[0]


def read_tracts(path: Path) -> gpd.GeoDataFrame:
    """Every census tract in the geodatabase with the columns the measures are read from.

    The tract number is written as the Census writes it, eleven digits with the state's
    leading zero, which the file drops by storing it as a number.
    """
    table = gpd.read_file(path)
    missing = [c for c in COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(
            f"the CalEnviroScreen file has no column {missing}; its layout has changed"
        )
    if table.empty or table.crs is None:
        raise ValueError("the CalEnviroScreen file holds no tracts, or names no map projection")
    table = table[[*COLUMNS, "geometry"]].copy()
    table[C_TRACT] = table[C_TRACT].astype("int64").astype(str).str.zfill(11)
    if table[C_TRACT].duplicated().any():
        raise ValueError("the CalEnviroScreen file lists a census tract more than once")
    return table


def pull(raw_root: Path) -> Path:
    """Download the CalEnviroScreen geodatabase into its own raw folder.

    The file is fetched and read before the folder is made, so a failed pull leaves nothing
    behind.
    """
    manifest = PullManifest.start(SOURCE, PACKAGE, {"id": DATASET, "version": VERSION})
    with httpx.Client(headers={"User-Agent": "methanewatch"}, follow_redirects=True) as client:
        resource = geodatabase(_get(client, PACKAGE, {"id": DATASET}).json())
        response = _get(client, resource["url"])
    with tempfile.TemporaryDirectory() as scratch:
        # The reader tells a zipped geodatabase by its name, so it is checked under that name.
        candidate = Path(scratch) / FILE
        candidate.write_bytes(response.content)
        n_tracts = len(read_tracts(candidate))
    manifest.params |= {
        "file_url": resource["url"],
        "resource_id": resource.get("id"),
        "resource_last_modified": resource.get("last_modified"),
        "last_modified": response.headers.get("last-modified"),
    }
    pull_dir = raw_root / SOURCE / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    path = pull_dir / FILE
    path.write_bytes(response.content)
    manifest.finish(pull_dir, [path], n_records=n_tracts)
    return pull_dir


def finished_pulls(raw_root: Path) -> list[Path]:
    """Pull directories with a manifest, oldest first."""
    pulls = sorted((raw_root / SOURCE).glob(f"{SOURCE}-*"))
    return [p for p in pulls if (p / "manifest.json").exists()]


def pull_details(pull_dir: Path) -> dict:
    """The version and file address a pull recorded."""
    return json.loads((pull_dir / "manifest.json").read_text())["params"]


def measures(
    tracts: gpd.GeoDataFrame,
    sites: gpd.GeoDataFrame,
    *,
    metric_crs: str,
    pull_id: str,
    near_m: float = NEAR_M,
    version: str = VERSION,
    url: str = PAGE,
) -> tuple[pd.DataFrame, list[str]]:
    """``site_metrics`` rows for every site whose outline lies on a census tract.

    A landfill's own tract is the one that holds the largest part of its outline. The tracts
    around it are those any part of which lies within ``near_m`` of the outline, its own
    included. Their lowest and highest overall percentiles are written as published; nothing
    is averaged. A tract the state gives no score has no percentile row, which the pages read
    as "no score", never as zero.

    A row is ``confirmed`` when the site's outline is not a provisional one: a provisional
    outline can put the landfill in a neighbouring tract.

    Returns the rows and the sites whose outline lies on no tract in the file.
    """
    tracts = tracts.to_crs(metric_crs)
    sites = sites.to_crs(metric_crs)
    rows = []
    outside = []

    def add(site, tract_id: str, metric_id: str, value=None, text=None) -> None:
        rows.append(
            {
                "site_id": site.site_id,
                "metric_id": metric_id,
                "period": version,
                "source": SOURCE,
                "value": value,
                "value_text": text,
                "unit": UNITS[metric_id],
                "kind": "context",
                "confirmed": not str(site.polygon_source or "").startswith("provisional"),
                "source_id": tract_id,
                "url": url,
                "pull_id": pull_id,
            }
        )

    for site in sites.itertuples():
        near = tracts[tracts.intersects(site.geometry.buffer(near_m))]
        share = near.geometry.intersection(site.geometry).area
        if near.empty or share.max() <= 0:
            outside.append(site.site_id)
            continue
        own = near.loc[share.idxmax()]
        tract_id = own[C_TRACT]
        add(site, tract_id, TRACT, text=tract_id)
        add(site, tract_id, TRACT_POPULATION, float(own[C_POPULATION]))
        for metric_id, column in ((SCORE, C_SCORE), (POLLUTION, C_POLLUTION), (POPCHAR, C_POPCHAR)):
            if pd.notna(own[column]):
                add(site, tract_id, metric_id, float(own[column]))
        add(site, tract_id, TRACTS_NEAR, float(len(near)))
        scored = near[C_SCORE].dropna()
        if len(scored):
            add(site, tract_id, NEAR_LOWEST, float(scored.min()))
            add(site, tract_id, NEAR_HIGHEST, float(scored.max()))
    out = pd.DataFrame(rows, columns=[*schemas.site_metrics.columns, "pull_id"])
    return schemas.site_metrics.validate(out), outside
