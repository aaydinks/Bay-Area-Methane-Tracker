"""The denominator (docs/PLAN.md sections 4.2 and 5, phase 2c).

``overpasses`` has one row per (site, instrument, UTC day): every time an
instrument looked at a site, whether or not it saw a plume. Same-day repeat
passes collapse to one row so they are not counted as independent evidence.

Fallback ladder when an instrument's footprints are unavailable (Carbon
Mapper's Tanager-1 and aircraft, pending ADR 0001):
1. ask Carbon Mapper for acquisition lists;
2. use that instrument's detections for rates only, not for f;
3. last resort, inferred coverage (flagged ``coverage_source="inferred"``).

Plumes never create overpasses: adding an overpass only when something was
detected would bias the emitting fraction upward. Plumes without a matching
overpass are returned separately as coverage gaps.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from methanewatch import schemas
from methanewatch.config import Coverage


def from_footprints(
    footprints: gpd.GeoDataFrame,
    sites: gpd.GeoDataFrame,
    coverage: Coverage,
    *,
    source: str,
    metric_crs: str,
) -> pd.DataFrame:
    """Intersect scene footprints with site polygons.

    ``footprints`` needs ``scene_id``, ``instrument``, ``acquired_utc``, geometry and,
    optionally, ``valid_frac`` (cloud-free share; defaults to 1 when the source has
    no mask). ``sites`` needs ``site_id`` and geometry.
    """
    fp = footprints.to_crs(metric_crs)
    st = sites[["site_id", "geometry"]].to_crs(metric_crs)
    st = st.assign(site_area=st.geometry.area)
    if "valid_frac" not in fp:
        fp = fp.assign(valid_frac=1.0)

    pairs = gpd.sjoin(fp, st, predicate="intersects", how="inner")
    if pairs.empty:
        return _empty()
    site_geom = st.set_index("site_id").geometry
    inter = [
        g.intersection(site_geom[s]).area
        for g, s in zip(pairs.geometry, pairs["site_id"], strict=True)
    ]
    pairs = pairs.assign(coverage_frac=np.array(inter) / pairs["site_area"].to_numpy())
    pairs["day"] = pd.to_datetime(pairs["acquired_utc"], utc=True).dt.floor("D")

    # Collapse same-day passes: best coverage, first acquisition, all scene ids
    pairs = pairs.sort_values(["site_id", "instrument", "day", "acquired_utc"])
    out = pairs.groupby(["site_id", "instrument", "day"], as_index=False).agg(
        acquired_utc=("acquired_utc", "min"),
        scene_ids=("scene_id", lambda s: sorted(set(s))),
        coverage_frac=("coverage_frac", "max"),
        valid_frac=("valid_frac", "max"),
    )
    out["coverage_frac"] = out["coverage_frac"].clip(0, 1)
    out["usable"] = (out["coverage_frac"] >= coverage.min_coverage_frac) & (
        out["valid_frac"] >= coverage.min_valid_frac
    )
    out["coverage_source"] = source
    out["overpass_id"] = (
        out["site_id"] + ":" + out["instrument"] + ":" + out["day"].dt.strftime("%Y-%m-%d")
    )
    out = out.drop(columns="day")
    return schemas.overpasses.validate(out)


def _empty() -> pd.DataFrame:
    cols = [
        "overpass_id",
        "site_id",
        "instrument",
        "acquired_utc",
        "scene_ids",
        "coverage_frac",
        "valid_frac",
        "usable",
        "coverage_source",
    ]
    return pd.DataFrame(columns=cols)


def q_sigma_log(q: pd.Series, q_sigma: pd.Series) -> pd.Series:
    """Log-scale error from a reported absolute 1-sigma error (log-normal moment match)."""
    return np.sqrt(np.log1p((q_sigma / q) ** 2))


def build_detections(
    overpasses: pd.DataFrame, plumes: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join attributed plumes to usable overpasses on (site, instrument, UTC day).

    Returns ``(detections, unmatched_plumes)``. Several plumes from one site on one
    overpass are summed; their errors add in quadrature.
    """
    usable = overpasses[overpasses["usable"]].copy()
    usable["day"] = pd.to_datetime(usable["acquired_utc"], utc=True).dt.floor("D")

    pl = plumes[plumes["attribution"].isin(["inside", "buffer"])].copy()
    pl["day"] = pd.to_datetime(pl["acquired_utc"], utc=True).dt.floor("D")
    # A detection without a rate can't enter the likelihood; report it instead.
    no_rate = pl[pl["q_kg_hr"].isna()].assign(reason="no emission rate")
    pl = pl[pl["q_kg_hr"].notna()]
    pl["var"] = pl["q_sigma_kg_hr"] ** 2
    per_pass = pl.groupby(["site_id", "instrument", "day"], as_index=False).agg(
        q_obs_kg_hr=("q_kg_hr", "sum"),
        var=("var", "sum"),
        n_plumes=("plume_id", "size"),
    )
    per_pass["q_sigma_kg_hr"] = np.sqrt(per_pass["var"])

    keys = ["site_id", "instrument", "day"]
    det = usable.merge(per_pass, on=keys, how="left")
    det["detected"] = det["q_obs_kg_hr"].notna()
    # Missing reported errors stay NaN; the model falls back to the instrument default.
    det["q_sigma_log"] = q_sigma_log(det["q_obs_kg_hr"], det["q_sigma_kg_hr"])
    det["n_plumes"] = det["n_plumes"].fillna(0).astype(int)
    det["multi_plume"] = det["n_plumes"] > 1

    matched = per_pass.merge(usable[keys], on=keys, how="left", indicator=True)
    unmatched_keys = matched.loc[matched["_merge"] == "left_only", keys]
    unmatched = pl.merge(unmatched_keys, on=keys).assign(reason="no usable overpass")
    unmatched = pd.concat([unmatched, no_rate], ignore_index=True).drop(columns=["day", "var"])

    cols = [
        "overpass_id",
        "site_id",
        "instrument",
        "acquired_utc",
        "detected",
        "q_obs_kg_hr",
        "q_sigma_log",
        "n_plumes",
        "multi_plume",
    ]
    return schemas.detections.validate(det[cols]), unmatched
