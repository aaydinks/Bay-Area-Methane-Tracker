"""Hierarchical persistence model in PyMC (PLAN section 6).

Likelihood per usable overpass, marginalized over rate on the log grid:
  non-detection: log(1 - f_s * sum_k w_k POD_j(q_k) h_s(x_k))
  detection:     log f_s + log sum_k w_k POD_j(q_k) h_s(x_k) LogNormal(q_obs | x_k, tau_i)
Non-centered priors on logit f_s and mu_s; sigma shared to start.
"""

from __future__ import annotations

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm

from methanewatch.config import ModelConfig
from methanewatch.model.grid import LogRateGrid


def build_model(
    detections: pd.DataFrame,
    grid: LogRateGrid,
    pod: np.ndarray,
    instruments: list[str],
    cfg: ModelConfig,
) -> pm.Model:
    raise NotImplementedError("persistence model: week 5")


def fit(model: pm.Model, cfg: ModelConfig) -> az.InferenceData:
    raise NotImplementedError("sampling + diagnostics gate: week 5")
