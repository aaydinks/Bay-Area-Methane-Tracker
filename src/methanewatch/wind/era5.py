"""ERA5 10 m wind via the Copernicus Climate Data Store (``wind`` extra).

About 31 km, hourly. Needs a CDS account and ``~/.cdsapirc``. Kept as a
cross-check on HRRR in the Bay Area's sea-breeze terrain (ADR 0002).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import xarray as xr

from methanewatch.wind.base import Wind

DATASET = "reanalysis-era5-single-levels"


def request(lon: float, lat: float, hour: pd.Timestamp) -> dict:
    """CDS request for one hour over a 0.5-degree box around the site."""
    return {
        "product_type": ["reanalysis"],
        "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
        "year": [f"{hour.year}"],
        "month": [f"{hour.month:02d}"],
        "day": [f"{hour.day:02d}"],
        "time": [f"{hour.hour:02d}:00"],
        "area": [lat + 0.25, lon - 0.25, lat - 0.25, lon + 0.25],  # N, W, S, E
        "data_format": "netcdf",
    }


class Era5Provider:
    product = "era5-single-levels"

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def get(self, lon: float, lat: float, time_utc: datetime) -> Wind:
        import cdsapi

        hour = pd.Timestamp(time_utc).tz_convert("UTC").round("h")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target = self.cache_dir / f"era5_{lat:.2f}_{lon:.2f}_{hour:%Y%m%dT%H}.nc"
        if not target.exists():
            cdsapi.Client().retrieve(DATASET, request(lon, lat, hour), str(target))
        point = xr.open_dataset(target).sel(latitude=lat, longitude=lon, method="nearest")
        point = point.squeeze()
        return Wind(
            u10=float(point["u10"]),
            v10=float(point["v10"]),
            product=self.product,
            product_version=str(hour),
        )
