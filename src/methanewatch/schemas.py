"""Table schemas (docs/PLAN.md section 4).

Times are UTC, rates are kg/hr, annual totals are t/yr. Validate every table
before it is written to ``data/interim`` or ``data/processed``.
"""

from __future__ import annotations

import pandera.pandas as pa

UTC_TS = "datetime64[ns, UTC]"

INSTRUMENTS = ["tanager1", "emit", "aircraft", "sentinel2"]
PLUME_SOURCES = ["carbonmapper", "emit-v2", "s2-local"]
ATTRIBUTION = ["inside", "buffer", "ambiguous", "nearby", "none"]
COVERAGE_SOURCES = ["stac-footprint", "cmr-granule", "s2-scene", "inferred"]
ESTIMATE_STATUS = ["estimate", "insufficient_data", "provisional"]

_nonneg = pa.Check.ge(0)
_frac = pa.Check.in_range(0, 1)


overpasses = pa.DataFrameSchema(
    {
        "overpass_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "instrument": pa.Column(str, pa.Check.isin(INSTRUMENTS)),
        "acquired_utc": pa.Column(UTC_TS),
        "coverage_frac": pa.Column(float, _frac),
        "valid_frac": pa.Column(float, _frac),
        "usable": pa.Column(bool),
        "coverage_source": pa.Column(str, pa.Check.isin(COVERAGE_SOURCES)),
    },
    strict=False,
    coerce=True,
)

plumes = pa.DataFrameSchema(
    {
        "plume_id": pa.Column(str),
        "source": pa.Column(str, pa.Check.isin(PLUME_SOURCES)),
        "instrument": pa.Column(str, pa.Check.isin(INSTRUMENTS)),
        "acquired_utc": pa.Column(UTC_TS),
        "origin_lon": pa.Column(float, pa.Check.in_range(-180, 180)),
        "origin_lat": pa.Column(float, pa.Check.in_range(-90, 90)),
        "q_kg_hr": pa.Column(float, _nonneg, nullable=True),
        "q_sigma_kg_hr": pa.Column(float, _nonneg, nullable=True),
        "data_version": pa.Column(str),
        "site_id": pa.Column(str, nullable=True),
        "attribution": pa.Column(str, pa.Check.isin(ATTRIBUTION)),
        "distance_m": pa.Column(float, _nonneg, nullable=True),
        "pull_id": pa.Column(str),
    },
    unique=["source", "plume_id"],
    strict=False,
    coerce=True,
)

detections = pa.DataFrameSchema(
    {
        "overpass_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "instrument": pa.Column(str, pa.Check.isin(INSTRUMENTS)),
        "detected": pa.Column(bool),
        "q_obs_kg_hr": pa.Column(float, pa.Check.gt(0), nullable=True),
        "q_sigma_log": pa.Column(float, pa.Check.gt(0), nullable=True),
    },
    checks=pa.Check(
        lambda df: df["detected"] == df["q_obs_kg_hr"].notna(),
        error="q_obs_kg_hr must be set exactly when detected is True",
    ),
    strict=False,
    coerce=True,
)

site_features = pa.DataFrameSchema(
    {
        "site_id": pa.Column(str, unique=True),
        "status": pa.Column(str),
        "closed": pa.Column(bool),
        "area_km2": pa.Column(float, pa.Check.gt(0)),
        "ghgrp_reporter": pa.Column(bool),
        "dist_neighbor_m": pa.Column(float, _nonneg, nullable=True),
    },
    strict=False,
    coerce=True,
)

repairs = pa.DataFrameSchema(
    {
        "repair_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "date_start": pa.Column("datetime64[ns]"),
        "date_end": pa.Column("datetime64[ns]", nullable=True),
        "kind": pa.Column(str, pa.Check.isin(["well-field", "cover", "leak-repair", "other"])),
        "description": pa.Column(str),
        "source_doc": pa.Column(str, pa.Check.str_length(min_value=1)),
        "source_page": pa.Column(str, nullable=True),
        "date_confidence": pa.Column(str, pa.Check.isin(["exact", "week", "month"])),
    },
    strict=False,
    coerce=True,
)

operator_reports = pa.DataFrameSchema(
    {
        "site_id": pa.Column(str),
        "year": pa.Column(int, pa.Check.in_range(2010, 2100)),
        "source": pa.Column(str, pa.Check.isin(["GHGRP", "CARB-MRR"])),
        "reported_ch4_t": pa.Column(float, _nonneg),
        "facility_id": pa.Column(str),
        "url": pa.Column(str),
    },
    unique=["site_id", "year", "source"],
    strict=False,
    coerce=True,
)

site_estimates = pa.DataFrameSchema(
    {
        "site_id": pa.Column(str),
        "period": pa.Column(str),
        "run_id": pa.Column(str),
        "n_usable_overpasses": pa.Column(int, _nonneg),
        "n_detections": pa.Column(int, _nonneg),
        "f_med": pa.Column(float, _frac, nullable=True),
        "f_lo": pa.Column(float, _frac, nullable=True),
        "f_hi": pa.Column(float, _frac, nullable=True),
        "E_t_yr_med": pa.Column(float, _nonneg, nullable=True),
        "E_t_yr_lo": pa.Column(float, _nonneg, nullable=True),
        "E_t_yr_hi": pa.Column(float, _nonneg, nullable=True),
        "status": pa.Column(str, pa.Check.isin(ESTIMATE_STATUS)),
    },
    unique=["site_id", "period", "run_id"],
    strict=False,
    coerce=True,
)
