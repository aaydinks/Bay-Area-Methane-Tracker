"""Synthetic sites with known truth for the coverage test (PLAN section 8.1).

Truths are drawn from the prior's hyperparameters; overpass schedules are
resampled from the real overpasses table once it exists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from methanewatch.config import ModelConfig


def simulate(
    n_sites: int, schedule: pd.DataFrame, cfg: ModelConfig, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raise NotImplementedError("simulator: week 3-5")
