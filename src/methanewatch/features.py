"""Site traits for the persistence model (ADR 0008).

``build_site_features`` turns the registry into one row per site. A few of the
traits can enter the model as site-level covariates; ``design`` turns the
chosen ones into a standardized matrix:

  logit f_s = alpha_f  + X_s . beta_f  + tau_f  z_f[s]
  mu_s      = alpha_mu + X_s . beta_mu + tau_mu z_mu[s]

With about 5 pilot and 36 screening sites, more than two or three covariates
only trades one prior for another, so the list in ``config/model.yaml`` is
short and empty by default. County and operator stay descriptive, and nearby
population is context only: it is never a model input.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd

from methanewatch import schemas
from methanewatch.config import ProjectConfig

# Covariates the model accepts, and how each is built from the feature table.
BINARY = {"closed", "ghgrp_reporter"}
CONTINUOUS = {"log_area", "log_dist_neighbor"}
COVARIATES = BINARY | CONTINUOUS

CLOSED_STATUSES = {"closed", "closing"}


@dataclass(frozen=True)
class Covariates:
    """Standardized site covariates, rows aligned to ``site_ids``."""

    names: tuple[str, ...]
    site_ids: tuple[str, ...]
    X: np.ndarray  # (S, P)
    center: tuple[float, ...]
    scale: tuple[float, ...]

    def rows(self, site_ids: Sequence[str]) -> np.ndarray:
        """X re-ordered (and repeated) to match ``site_ids``."""
        idx = pd.Index(self.site_ids).get_indexer(list(site_ids))
        if (idx < 0).any():
            missing = sorted({s for s, i in zip(site_ids, idx, strict=True) if i < 0})
            raise ValueError(f"no covariates for: {missing}")
        return self.X[idx]

    def manifest(self) -> dict:
        return {
            "names": list(self.names),
            "center": dict(zip(self.names, self.center, strict=True)),
            "scale": dict(zip(self.names, self.scale, strict=True)),
        }


def _status(registry_status: pd.Series, fallback: pd.Series) -> pd.Series:
    s = registry_status.fillna("").str.strip().str.lower()
    fb = fallback.reindex(s.index).fillna("").str.strip().str.lower()
    return s.where(s != "", fb).replace("", "unknown")


def build_site_features(
    sites: gpd.GeoDataFrame,
    neighbors: gpd.GeoDataFrame,
    crosswalk: pd.DataFrame,
    status_fallback: pd.DataFrame | None = None,
    *,
    metric_crs: str = "EPSG:32610",
) -> pd.DataFrame:
    """One row per site with a boundary.

    ``sites`` is ``interim/sites.parquet`` (``site_id``, ``status``, boundary);
    ``neighbors`` holds other methane sources (``part = neighbor``);
    ``crosswalk`` maps ``site_id`` to a GHGRP facility; ``status_fallback``
    (``site_id``, ``status``) fills a blank registry status, for example from
    CalRecycle.
    """
    m = sites.to_crs(metric_crs).set_index("site_id")
    fb = (
        status_fallback.set_index("site_id")["status"]
        if status_fallback is not None
        else pd.Series(dtype=str)
    )
    status = _status(m["status"] if "status" in m else pd.Series("", index=m.index), fb)

    neigh = (
        neighbors.to_crs(metric_crs).geometry if len(neighbors) else gpd.GeoSeries(crs=metric_crs)
    )
    dist = {}
    for sid, geom in m.geometry.items():
        pool = pd.concat([neigh, m.geometry.drop(sid)])
        dist[sid] = float(pool.distance(geom).min()) if len(pool) else np.nan

    reporters = set(crosswalk.dropna(subset=["ghgrp_facility_id"])["site_id"])
    out = pd.DataFrame(
        {
            "site_id": m.index,
            "status": status.to_numpy(),
            "closed": status.isin(CLOSED_STATUSES).to_numpy(),
            "area_km2": (m.geometry.area / 1e6).to_numpy(),
            "ghgrp_reporter": m.index.isin(reporters),
            "dist_neighbor_m": [dist[s] for s in m.index],
        }
    )
    return schemas.site_features.validate(out.sort_values("site_id").reset_index(drop=True))


def _column(features: pd.DataFrame, name: str) -> np.ndarray:
    if name == "closed":
        return features["closed"].astype(float).to_numpy()
    if name == "ghgrp_reporter":
        return features["ghgrp_reporter"].astype(float).to_numpy()
    if name == "log_area":
        return np.log(features["area_km2"].astype(float).to_numpy())
    if name == "log_dist_neighbor":
        return np.log1p(features["dist_neighbor_m"].astype(float).to_numpy())
    raise ValueError(f"unknown covariate {name!r}; choose from {sorted(COVARIATES)}")


def design(features: pd.DataFrame, names: Sequence[str]) -> Covariates:
    """Centre binary covariates and standardize continuous ones over these sites.

    Refuses missing values and covariates that do not vary: either would let the
    prior alone decide the coefficient while looking like evidence.
    """
    names = tuple(names)
    unknown = set(names) - COVARIATES
    if unknown:
        raise ValueError(
            f"unknown covariate(s) {sorted(unknown)}; choose from {sorted(COVARIATES)}"
        )
    cols, center, scale = [], [], []
    for name in names:
        x = _column(features, name)
        if np.isnan(x).any():
            missing = features.loc[np.isnan(x), "site_id"].tolist()
            raise ValueError(f"covariate {name!r} is missing for {missing}")
        c = float(x.mean())
        sd = 1.0 if name in BINARY else float(x.std())
        if np.ptp(x) == 0 or sd == 0:
            raise ValueError(f"covariate {name!r} does not vary across these sites")
        cols.append((x - c) / sd)
        center.append(c)
        scale.append(sd)
    X = np.column_stack(cols) if cols else np.zeros((len(features), 0))
    return Covariates(names, tuple(features["site_id"]), X, tuple(center), tuple(scale))


def synthetic_columns(names: Sequence[str], n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Made-up feature values for simulated sites (Gate 3 with covariates). Never real."""
    data = {}
    for name in names:
        if name in BINARY:
            x = rng.random(n) < 0.5
            x[0], x[-1] = True, False  # both levels present
            data[name] = x
        elif name in CONTINUOUS:
            data[name] = rng.normal(size=n)
        else:
            raise ValueError(f"unknown covariate {name!r}")
    return pd.DataFrame(data)


def design_synthetic(sites: pd.DataFrame, names: Sequence[str]) -> Covariates:
    """``design`` for simulated sites whose columns already hold covariate values."""
    cols, center, scale = [], [], []
    for name in names:
        x = sites[name].astype(float).to_numpy()
        c, sd = float(x.mean()), (1.0 if name in BINARY else float(x.std()))
        cols.append((x - c) / sd)
        center.append(c)
        scale.append(sd)
    X = np.column_stack(cols) if cols else np.zeros((len(sites), 0))
    return Covariates(tuple(names), tuple(sites["site_id"]), X, tuple(center), tuple(scale))


def write_site_features(project: ProjectConfig) -> pd.DataFrame:
    """One row of traits per registry site -> ``interim/site_features.parquet``."""
    interim = project.resolve(project.paths.interim)
    path = interim / "sites.parquet"
    if not path.exists():
        raise FileNotFoundError("run `mw sites build` first")
    sites = gpd.read_parquet(path)
    if sites.empty:
        raise FileNotFoundError("no site polygons yet")
    neighbors_path = interim / "neighbors.parquet"
    neighbors = (
        gpd.read_parquet(neighbors_path)
        if neighbors_path.exists()
        else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    )
    registry = project.resolve(project.paths.registry)
    crosswalk = pd.read_csv(registry / "operator_crosswalk.csv", dtype=str)
    swis = project.resolve(project.paths.datasets) / "calrecycle" / "swis_pilot_sites.csv"
    fallback = (
        pd.read_csv(swis).rename(columns={"operational_status": "status"})[["site_id", "status"]]
        if swis.exists()
        else None
    )
    table = build_site_features(
        sites, neighbors, crosswalk, fallback, metric_crs=project.crs_metric
    )
    table.to_parquet(interim / "site_features.parquet")
    return table
