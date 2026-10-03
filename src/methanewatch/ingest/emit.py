"""NASA EMIT v2 CH4 plume complexes and granule footprints (PLAN section 5, phase 2b).

Uses earthaccess (Earthdata login via ~/.netrc). Version 1 was decommissioned
March 26, 2026: reject any v1 granule. Record collection short names in an ADR.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def search_granules(bbox: tuple[float, float, float, float], start: date, end: date) -> list[dict]:
    raise NotImplementedError("EMIT CMR search: week 1-2")


def pull_plumes(site_id: str, radius_km: float) -> Path:
    raise NotImplementedError("EMIT plume pull: week 2")


def normalize(pull_dir: Path) -> pd.DataFrame:
    raise NotImplementedError("normalize to schemas.plumes: week 2")
