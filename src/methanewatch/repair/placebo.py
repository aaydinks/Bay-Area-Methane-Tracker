"""Placebo repairs at control sites (Gate 5: false-positive rate <= 10%).

The pseudo-treated site is removed from the control set in each fit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def run_placebos(controls: list[str], n: int, rng: np.random.Generator) -> pd.DataFrame:
    raise NotImplementedError("placebo test: week 10")
