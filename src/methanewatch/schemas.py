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

CHECK_TYPES = [
    "air-district-inspection",
    "air-district-notice",
    "operator-repair",
    "carb-plume-notice",
    "other",
]
REPAIR_KINDS = ["well-field", "cover", "leak-repair", "other"]
DATE_CONFIDENCE = ["exact", "week", "month"]

# Dated records at a landfill (data/registry/checks.csv, ADR 0010): Air District inspections and
# notices, operator repairs, CARB plume notices. No row without a source document. The before/after
# test runs on every type; the result is the change after the date, never a cause.
checks = pa.DataFrameSchema(
    {
        "check_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "check_type": pa.Column(str, pa.Check.isin(CHECK_TYPES)),
        "repair_kind": pa.Column(str, pa.Check.isin(REPAIR_KINDS), nullable=True),
        "date_start": pa.Column("datetime64[ns]"),
        "date_end": pa.Column("datetime64[ns]", nullable=True),
        "date_confidence": pa.Column(str, pa.Check.isin(DATE_CONFIDENCE)),
        "description": pa.Column(str),
        "source_doc": pa.Column(str, pa.Check.str_length(min_value=1)),
        "source_doc_title": pa.Column(str, nullable=True),
        "source_url": pa.Column(str, nullable=True),
        "source_page": pa.Column(str, nullable=True),
    },
    checks=pa.Check(
        lambda df: (df["check_type"] != "operator-repair") | df["repair_kind"].notna(),
        error="an operator repair needs a repair_kind",
    ),
    strict=False,
    coerce=True,
)

REPAIR_CALLS = ["drop", "rise", "inconclusive", "insufficient_data"]

# The engineered outcome: one row per dated check (PLAN section 7, ADR 0010).
# effect = log(E_after / E_counterfactual); mde_pct = smallest tested drop called in at
# least 80% of simulated fits on this repair's own pass schedule (null when none was).
repair_outcomes = pa.DataFrameSchema(
    {
        "repair_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "check_type": pa.Column(str, pa.Check.isin(CHECK_TYPES)),
        "date_start": pa.Column("datetime64[ns]"),
        "date_confidence": pa.Column(str, pa.Check.isin(DATE_CONFIDENCE)),
        "call": pa.Column(str, pa.Check.isin(REPAIR_CALLS)),
        "effect_med": pa.Column(float, nullable=True),
        "effect_lo": pa.Column(float, nullable=True),
        "effect_hi": pa.Column(float, nullable=True),
        "p_decrease": pa.Column(float, _frac, nullable=True),
        "dE_t_yr_med": pa.Column(float, nullable=True),
        "dE_t_yr_lo": pa.Column(float, nullable=True),
        "dE_t_yr_hi": pa.Column(float, nullable=True),
        "mde_pct": pa.Column(float, pa.Check.in_range(0, 100), nullable=True),
        "n_before": pa.Column(int, _nonneg),
        "n_after": pa.Column(int, _nonneg),
        "controls": pa.Column(str),
        "diag_ok": pa.Column("boolean", nullable=True),
        "reason": pa.Column(str),
        "run_id": pa.Column(str),
    },
    checks=pa.Check(
        lambda df: (df["call"] == "insufficient_data") | df["effect_med"].notna(),
        error="an outcome other than insufficient_data needs an effect",
    ),
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
