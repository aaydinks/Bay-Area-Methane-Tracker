"""EPA GHGRP subpart HH operator-reported landfill emissions (PLAN section 5, phase 2e).

Download path (FLIGHT export or Envirofacts) is confirmed in week 8.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def pull_reports(facility_ids: list[str]) -> Path:
    raise NotImplementedError("GHGRP pull: week 8")


def normalize(pull_dir: Path, crosswalk: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError("normalize to schemas.operator_reports: week 8")
