"""HRRR 10 m wind via herbie (``wind`` extra).

HRRR analyses (fxx=0) are about 3 km and hourly over CONUS, archived on public
cloud buckets. herbie downloads only the U/V 10 m GRIB messages through
byte-range requests, cached under the provider's ``cache_dir``. The value at a
site is the nearest grid point in the analysis for the nearest hour.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch.wind.base import Wind

SEARCH = ":(?:UGRD|VGRD):10 m above ground"


def nearest(ds, lon: float, lat: float) -> tuple[float, float]:
    """U and V at the grid point nearest (lon, lat); HRRR longitudes are 0-360."""
    lons = ds["longitude"].values
    lons = np.where(lons > 180, lons - 360, lons)
    d2 = (lons - lon) ** 2 + (ds["latitude"].values - lat) ** 2
    iy, ix = np.unravel_index(np.argmin(d2), d2.shape)
    return float(ds["u10"].values[iy, ix]), float(ds["v10"].values[iy, ix])


class HrrrProvider:
    product = "hrrr-sfc-analysis"

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def get(self, lon: float, lat: float, time_utc: datetime) -> Wind:
        from herbie import Herbie

        hour = pd.Timestamp(time_utc).tz_convert("UTC").round("h").tz_localize(None)
        h = Herbie(hour, model="hrrr", product="sfc", fxx=0, save_dir=self.cache_dir, verbose=False)
        ds = h.xarray(SEARCH, remove_grib=False)
        if isinstance(ds, list):  # herbie returns one dataset per hypercube
            ds = next(d for d in ds if "u10" in d)
        u, v = nearest(ds, lon, lat)
        return Wind(u10=u, v10=v, product=self.product, product_version=str(hour))
