"""Before/after repair model with control sites (PLAN section 7).

Call rule: drop if the 90% interval of the control-adjusted log ratio is below 0,
rise if above, inconclusive otherwise.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def count_overpasses(site_id: str, repair_date: date) -> pd.DataFrame:
    raise NotImplementedError("repair overpass count: week 2, right after Gate 1")


def verify_repair(site_id: str, repair_id: str, controls: list[str]) -> dict:
    raise NotImplementedError("repair test: week 9-10")
