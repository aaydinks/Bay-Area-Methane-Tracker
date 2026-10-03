"""Carbon Mapper plume ingest (PLAN section 5, phase 2a).

Endpoints and fields are recorded in docs/decisions/0001-carbonmapper-api.md
after reading the product guide and API docs. Do not guess them. Data are
free for non-commercial use only; raw pulls are never committed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def pull_plumes(site_id: str, radius_km: float, since: date | None = None) -> Path:
    raise NotImplementedError("Carbon Mapper pull: week 1, after the API spike (ADR 0001)")


def normalize(pull_dir: Path) -> pd.DataFrame:
    raise NotImplementedError("normalize to schemas.plumes: week 2")
