"""Wind provider interface (PLAN section 5, phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Wind:
    u10: float  # m/s, eastward
    v10: float  # m/s, northward
    product: str
    product_version: str

    @property
    def speed(self) -> float:
        return (self.u10**2 + self.v10**2) ** 0.5


class WindProvider(Protocol):
    def get(self, lon: float, lat: float, time_utc: datetime) -> Wind: ...
