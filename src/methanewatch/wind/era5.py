"""ERA5 10 m wind via cdsapi (install with the ``wind`` extra)."""

from __future__ import annotations

from datetime import datetime

from methanewatch.wind.base import Wind


def get(lon: float, lat: float, time_utc: datetime) -> Wind:
    raise NotImplementedError("ERA5 provider: week 3 (ADR 0002)")
