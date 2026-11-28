"""EPA's air monitors: the nearest fine-particle and NO2 monitor to each landfill (ADR 0027).

Checked live on 2026-11-28:

- EPA's AirData page of pre-generated files needs no login. It lists one file a year,
  ``annual_conc_by_monitor_<year>.zip``: one row per monitor, pollutant, way of summarising
  and treatment of event days, for the whole country (65,709 rows for 2025).
- The page says the files are refreshed twice a year, "once in June to capture the complete
  data for the prior year" and once in December. The files on the page were dated 2026-06-25.
- A monitor's agency has until May 1 of the following year to certify a year's data. In the
  2025 file the Bay Area's nine counties have no fine-particle or NO2 rows at all; most of
  their 2023 and 2024 rows read "Certification not required", and 2022 is the newest year most
  of them are certified for. The project's other districts have certified rows for 2025. So
  one year cannot serve every landfill, and each monitor is read at its own newest good year.
- EPA's advisory beside the files (posted 2024-08-26) says to leave out fine-particle data
  from the Teledyne T640 and T640X instruments under their original method names.

These are context measures (ADR 0020): they describe the air at a monitor near a landfill and
are never attributed to the landfill. Figures are written as EPA publishes them. Nothing is
averaged across monitors, and nothing is compared with a standard.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch import schemas
from methanewatch.provenance import PullManifest

SOURCE = "epa-aqs"  # the key of this source in config/data_terms.yaml
BASE = "https://aqs.epa.gov/aqsweb/airdata"
PAGE = f"{BASE}/download_files.html"
YEARS = 5  # a monitor's figure may come from the newest full year or the four before it

# Column names as EPA's annual file writes them
C_STATE = "State Code"
C_COUNTY = "County Code"
C_SITE = "Site Num"
C_PARAMETER = "Parameter Code"
C_POC = "POC"
C_LAT = "Latitude"
C_LON = "Longitude"
C_DATUM = "Datum"
C_STANDARD = "Pollutant Standard"
C_METHOD = "Method Name"
C_YEAR = "Year"
C_UNITS = "Units of Measure"
C_EVENTS = "Event Type"
C_COMPLETE = "Completeness Indicator"
C_DAYS = "Valid Day Count"
C_CERTIFIED = "Certification Indicator"
C_MEAN = "Arithmetic Mean"
C_NAME = "Local Site Name"
COLUMNS = (
    C_STATE, C_COUNTY, C_SITE, C_PARAMETER, C_POC, C_LAT, C_LON, C_DATUM, C_STANDARD,
    C_METHOD, C_YEAR, C_UNITS, C_EVENTS, C_COMPLETE, C_DAYS, C_CERTIFIED, C_MEAN, C_NAME,
)  # fmt: skip
STATION = [C_STATE, C_COUNTY, C_SITE]  # one monitoring station
MONITOR = [*STATION, C_POC]  # one instrument at a station

# A year's row counts every valid day when EPA marks it one of these: no event day happened,
# or event days (wildfire smoke, for example) happened and are included.
ALL_DAYS = ("No Events", "Events Included")
CERTIFIED = "Certified"
# EPA's advisory: leave these two out. The same instruments under their "Network Data
# Alignment" or "(Corrected)" names are kept.
SUPERSEDED_METHODS = (
    "Teledyne T640 at 5.0 LPM - Broadband spectroscopy",
    "Teledyne T640X at 16.67 LPM - Broadband spectroscopy",
)
DATUMS = {"WGS84": "EPSG:4326", "NAD83": "EPSG:4269", "NAD27": "EPSG:4267"}


@dataclass(frozen=True)
class Pollutant:
    """One pollutant as EPA's file names it, and the measures written from it."""

    key: str
    parameter: str  # EPA's parameter code
    standard: str  # the rule EPA summarises the year by; its row holds the annual mean
    file_units: str  # what the file must say the mean is measured in
    unit: str  # the same unit as the catalogue writes it

    @property
    def monitor(self) -> str:
        return f"aqs_{self.key}_monitor"

    @property
    def distance(self) -> str:
        return f"aqs_{self.key}_distance"

    @property
    def year(self) -> str:
        return f"aqs_{self.key}_year"

    @property
    def days(self) -> str:
        return f"aqs_{self.key}_days"

    @property
    def mean(self) -> str:
        return f"aqs_{self.key}_mean"

    @property
    def units(self) -> dict[str, str]:
        return {
            self.monitor: "monitor",
            self.distance: "km",
            self.year: "year",
            self.days: "days",
            self.mean: self.unit,
        }


PM25 = Pollutant("pm25", "88101", "PM25 Annual 2024", "Micrograms/cubic meter (LC)", "µg/m³")
NO2 = Pollutant("no2", "42602", "NO2 Annual 1971", "Parts per billion", "ppb")
POLLUTANTS = (PM25, NO2)
# Measure ids in config/metrics.yaml, each with its unit
UNITS = {metric_id: unit for p in POLLUTANTS for metric_id, unit in p.units.items()}


def newest_full_year(today: date) -> int:
    """The newest year EPA's files hold in full: last year once the June refresh has run."""
    return today.year - 1 if today.month >= 7 else today.year - 2


def years_read(last_year: int, n_years: int = YEARS) -> list[int]:
    return list(range(last_year - n_years + 1, last_year + 1))


def file_name(year: int) -> str:
    return f"annual_conc_by_monitor_{year}.zip"


def period(years: list[int]) -> str:
    """The years searched, which is the period every row is published under."""
    return f"{min(years)}-{max(years)}"


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, url: str) -> httpx.Response:
    r = client.get(url, timeout=300)
    r.raise_for_status()
    return r


def read_year(source: Path | bytes, year: int) -> pd.DataFrame:
    """The fine-particle and NO2 rows of one year's file, every column as text.

    The file is refused when a column is missing, when it holds another year, or when a
    pollutant has no row under the summary this step reads: each means EPA changed the layout,
    and which rows to read instead is not guessed.
    """
    data = source if isinstance(source, bytes) else source.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected one table in EPA's {year} file, found {len(names)}")
        table = pd.read_csv(io.BytesIO(archive.read(names[0])), dtype=str)
    missing = [c for c in COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"EPA's {year} file has no column {missing}; its layout has changed")
    if set(table[C_YEAR]) != {str(year)}:
        raise ValueError(f"EPA's {year} file holds rows for other years; its layout has changed")
    table = table[table[C_PARAMETER].isin([p.parameter for p in POLLUTANTS])]
    for p in POLLUTANTS:
        rows = table[(table[C_PARAMETER] == p.parameter) & (table[C_STANDARD] == p.standard)]
        if rows.empty or set(rows[C_UNITS]) != {p.file_units}:
            raise ValueError(
                f"EPA's {year} file has no '{p.standard}' rows in {p.file_units}; "
                "its layout has changed"
            )
    return table[list(COLUMNS)].reset_index(drop=True)


def pull(raw_root: Path, last_year: int | None = None) -> Path:
    """Download EPA's annual file for each of the years read into one raw folder.

    Every file is fetched and read before the folder is made, so a failed pull leaves nothing
    behind.
    """
    last_year = last_year or newest_full_year(date.today())
    years = years_read(last_year)
    manifest = PullManifest.start(SOURCE, PAGE, {"years": years})
    files = {}
    with httpx.Client(headers={"User-Agent": "methanewatch"}, follow_redirects=True) as client:
        for year in years:
            url = f"{BASE}/{file_name(year)}"
            response = _get(client, url)
            n_rows = len(read_year(response.content, year))
            files[year] = (url, response, n_rows)
    manifest.params |= {
        "files": {
            str(year): {"url": url, "last_modified": response.headers.get("last-modified")}
            for year, (url, response, _) in files.items()
        }
    }
    pull_dir = raw_root / SOURCE / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for year, (_, response, _) in files.items():
        path = pull_dir / file_name(year)
        path.write_bytes(response.content)
        paths.append(path)
    manifest.finish(pull_dir, paths, n_records=sum(n for _, _, n in files.values()))
    return pull_dir


def finished_pulls(raw_root: Path) -> list[Path]:
    """Pull directories with a manifest, oldest first."""
    pulls = sorted((raw_root / SOURCE).glob(f"{SOURCE}-*"))
    return [p for p in pulls if (p / "manifest.json").exists()]


def pull_years(pull_dir: Path) -> list[int]:
    """The years a pull downloaded."""
    return [int(y) for y in json.loads((pull_dir / "manifest.json").read_text())["params"]["years"]]


def read_pull(pull_dir: Path) -> pd.DataFrame:
    """Every year of a pull as one table."""
    years = pull_years(pull_dir)
    return pd.concat([read_year(pull_dir / file_name(y), y) for y in years], ignore_index=True)


def full_years(table: pd.DataFrame, pollutant: Pollutant) -> pd.DataFrame:
    """One row per monitor and year for the years that can be listed.

    A year can be listed when EPA marks it complete, the monitor's agency has certified it,
    and the row counts every valid day. A fine-particle monitor that ran under one of the
    method names EPA's advisory says to leave out is dropped for that year.
    """
    rows = table[table[C_PARAMETER] == pollutant.parameter]
    superseded = rows.loc[rows[C_METHOD].isin(SUPERSEDED_METHODS), [*MONITOR, C_YEAR]]
    superseded = superseded.drop_duplicates().assign(superseded=True)
    rows = rows[(rows[C_STANDARD] == pollutant.standard) & rows[C_EVENTS].isin(ALL_DAYS)]
    if rows.duplicated([*MONITOR, C_YEAR]).any():
        raise ValueError(
            f"EPA's file gives a monitor two '{pollutant.standard}' rows that count every "
            "day of one year; its layout has changed"
        )
    rows = rows.merge(superseded, how="left", on=[*MONITOR, C_YEAR])
    keep = (rows[C_COMPLETE] == "Y") & (rows[C_CERTIFIED] == CERTIFIED) & rows["superseded"].isna()
    return rows[keep].drop(columns="superseded").reset_index(drop=True)


def stations(table: pd.DataFrame, pollutant: Pollutant, metric_crs: str) -> gpd.GeoDataFrame:
    """Each monitoring station at its newest year that can be listed, as a point.

    Where a station ran more than one instrument that year, the one with the most valid days
    is read, and the lower instrument number on a tie.
    """
    rows = full_years(table, pollutant)
    rows = rows.assign(
        year=rows[C_YEAR].astype(int),
        days=rows[C_DAYS].astype(float),
        mean=rows[C_MEAN].astype(float),
        poc=rows[C_POC].astype(int),
    )
    rows = rows.sort_values(["year", "days", "poc"], ascending=[False, False, True])
    rows = rows.drop_duplicates(STATION).reset_index(drop=True)
    unknown = sorted(set(rows[C_DATUM]) - set(DATUMS))
    if unknown:
        raise ValueError(
            f"EPA's file places a monitor on a datum this step does not know: {unknown}"
        )
    parts = [
        gpd.GeoDataFrame(
            part,
            geometry=gpd.points_from_xy(part[C_LON].astype(float), part[C_LAT].astype(float)),
            crs=DATUMS[datum],
        ).to_crs(metric_crs)
        for datum, part in rows.groupby(C_DATUM)
    ]
    if not parts:
        return gpd.GeoDataFrame(rows, geometry=[], crs=metric_crs)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=metric_crs)


def measures(
    table: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    *,
    metric_crs: str,
    pull_id: str,
    years: list[int],
    near_km: float,
    url: str = PAGE,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """``site_metrics`` rows for the nearest monitor of each pollutant to every site.

    The nearest monitor is the station closest to the site's outline among those with a year
    that can be listed. A station further than ``near_km`` (``context.monitor_limit_km`` in
    ``config/project.yaml``) is not listed: the site then has no
    rows for that pollutant, which the pages read as "none close enough", never as a reading.

    A row is ``confirmed`` when the site's outline is not a provisional one: the distance is
    measured from the outline.

    Returns the rows and, for each pollutant, the sites with no monitor close enough.
    """
    sites = sites.to_crs(metric_crs)
    rows = []
    none_near: dict[str, list[str]] = {}

    def add(site, monitor_id: str, metric_id: str, value=None, text=None) -> None:
        rows.append(
            {
                "site_id": site.site_id,
                "metric_id": metric_id,
                "period": period(years),
                "source": SOURCE,
                "value": value,
                "value_text": text,
                "unit": UNITS[metric_id],
                "kind": "context",
                "confirmed": not str(site.polygon_source or "").startswith("provisional"),
                "source_id": monitor_id,
                "url": url,
                "pull_id": pull_id,
            }
        )

    for pollutant in POLLUTANTS:
        points = stations(table, pollutant, metric_crs)
        none_near[pollutant.key] = []
        for site in sites.itertuples():
            distance_km = points.distance(site.geometry) / 1000.0
            if points.empty or distance_km.min() > near_km:
                none_near[pollutant.key].append(site.site_id)
                continue
            station = points.loc[distance_km.idxmin()]
            station_id = "-".join(station[c] for c in STATION)
            monitor_id = f"{station_id}-{pollutant.parameter}-{station['poc']}"
            name = station[C_NAME] if pd.notna(station[C_NAME]) else "unnamed monitor"
            add(site, monitor_id, pollutant.monitor, text=f"{name} ({station_id})")
            add(site, monitor_id, pollutant.distance, float(distance_km.min()))
            add(site, monitor_id, pollutant.year, float(station["year"]))
            add(site, monitor_id, pollutant.days, float(station["days"]))
            add(site, monitor_id, pollutant.mean, float(station["mean"]))
    out = pd.DataFrame(rows, columns=[*schemas.site_metrics.columns, "pull_id"])
    return schemas.site_metrics.validate(out), none_near
