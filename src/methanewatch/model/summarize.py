"""Posterior draws -> site_estimates table, applying the insufficient-data rule (PLAN 6.6)."""

from __future__ import annotations

import arviz as az
import pandas as pd


def summarize(idata: az.InferenceData, detections: pd.DataFrame, run_id: str) -> pd.DataFrame:
    raise NotImplementedError("summaries: week 7")
