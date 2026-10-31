"""Shapes of the published tables, matching ``supabase/migrations/0002_tables.sql``.

Every snapshot table is validated against these before it is written or loaded.
"""

from __future__ import annotations

import pandera.pandas as pa

from methanewatch import schemas as base

UTC_TS = base.UTC_TS
_nonneg = pa.Check.ge(0)
_frac = pa.Check.in_range(0, 1)

VISIBILITY = ["draft", "review", "public"]
EVIDENCE = ["strong", "weak", "none"]
SIZES = ["slight", "moderate", "severe"]
COLOURS = ["red", "orange", "yellow", "green", "grey"]
UPDATE_KINDS = [
    "new-plumes",
    "new-record",
    "new-model-run",
    "new-check-run",
    "gate-result",
    "outline-change",
    "note",
]

sites = pa.DataFrameSchema(
    {
        "site_id": pa.Column(str, unique=True),
        "name": pa.Column(str),
        "city": pa.Column(str, nullable=True),
        "county": pa.Column(str, nullable=True),
        "operator": pa.Column(str, nullable=True),
        "tier": pa.Column(str, pa.Check.isin(["pilot", "screen"]), nullable=True),
        "status": pa.Column(str, nullable=True),
        "swis_number": pa.Column(str, nullable=True),
        "ghgrp_facility_id": pa.Column(str, nullable=True),
        "outline_wkt": pa.Column(str, nullable=True),
        "polygon_source": pa.Column(str, nullable=True),
        "provisional": pa.Column(bool),
        "area_km2": pa.Column(float, pa.Check.gt(0), nullable=True),
    },
    strict=False,
    coerce=True,
)

neighbours = pa.DataFrameSchema(
    {
        "neighbour_id": pa.Column(str, unique=True),
        "name": pa.Column(str),
        "kind": pa.Column(
            str, pa.Check.isin(["compost", "wastewater", "refinery", "landfill", "other"])
        ),
        "geom_wkt": pa.Column(str),
        "nearest_site_id": pa.Column(str, nullable=True),
        "distance_m": pa.Column(float, _nonneg, nullable=True),
        "source": pa.Column(str, nullable=True),
    },
    strict=False,
    coerce=True,
)

plumes = pa.DataFrameSchema(
    {
        "plume_id": pa.Column(str),
        "source": pa.Column(str, pa.Check.isin(base.PLUME_SOURCES)),
        "instrument": pa.Column(str, pa.Check.isin(base.INSTRUMENTS)),
        "acquired_utc": pa.Column(UTC_TS),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180)),
        "lat": pa.Column(float, pa.Check.in_range(-90, 90)),
        "q_kg_hr": pa.Column(float, _nonneg, nullable=True),
        "q_sigma_kg_hr": pa.Column(float, _nonneg, nullable=True),
        "site_id": pa.Column(str, nullable=True),
        "attribution": pa.Column(str, pa.Check.isin(base.ATTRIBUTION)),
        "distance_m": pa.Column(float, _nonneg, nullable=True),
        "data_version": pa.Column(str, nullable=True),
        "overpass_id": pa.Column(str, nullable=True),
        "restricted": pa.Column(bool),
        "new_in_update": pa.Column(bool),
    },
    unique=["source", "plume_id"],
    strict=False,
    coerce=True,
)

passes = pa.DataFrameSchema(
    {
        "overpass_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "instrument": pa.Column(str, pa.Check.isin(base.INSTRUMENTS)),
        "acquired_utc": pa.Column(UTC_TS),
        "usable": pa.Column(bool),
        "coverage_frac": pa.Column(float, _frac, nullable=True),
        "valid_frac": pa.Column(float, _frac, nullable=True),
        "coverage_source": pa.Column(str, pa.Check.isin(base.COVERAGE_SOURCES), nullable=True),
        "detected": pa.Column(bool),
        "q_obs_kg_hr": pa.Column(float, pa.Check.gt(0), nullable=True),
        "n_plumes": pa.Column(int, _nonneg),
        "restricted": pa.Column(bool),
    },
    strict=False,
    coerce=True,
)

site_estimates = pa.DataFrameSchema(
    {
        "model_run_id": pa.Column(str),
        "site_id": pa.Column(str),
        "period": pa.Column(str),
        "n_usable_overpasses": pa.Column(int, _nonneg),
        "n_detections": pa.Column(int, _nonneg),
        "f_med": pa.Column(float, _frac, nullable=True),
        "f_lo": pa.Column(float, _frac, nullable=True),
        "f_hi": pa.Column(float, _frac, nullable=True),
        "qbar_kg_hr_med": pa.Column(float, _nonneg, nullable=True),
        "qbar_kg_hr_lo": pa.Column(float, _nonneg, nullable=True),
        "qbar_kg_hr_hi": pa.Column(float, _nonneg, nullable=True),
        "e_t_yr_med": pa.Column(float, _nonneg, nullable=True),
        "e_t_yr_lo": pa.Column(float, _nonneg, nullable=True),
        "e_t_yr_hi": pa.Column(float, _nonneg, nullable=True),
        "status": pa.Column(str, pa.Check.isin(base.ESTIMATE_STATUS)),
        "insufficient_reason": pa.Column(str, nullable=True),
        "rhat_max": pa.Column(float, nullable=True),
        "ess_bulk_min": pa.Column(float, nullable=True),
        "divergences": pa.Column(float, nullable=True),
        "provisional": pa.Column(bool),
        "restricted": pa.Column(bool),
    },
    unique=["site_id", "period"],
    strict=False,
    coerce=True,
)

checks = pa.DataFrameSchema(
    {
        "check_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "check_type": pa.Column(str, pa.Check.isin(base.CHECK_TYPES)),
        "repair_kind": pa.Column(str, pa.Check.isin(base.REPAIR_KINDS), nullable=True),
        "date_start": pa.Column("datetime64[ns]"),
        "date_end": pa.Column("datetime64[ns]", nullable=True),
        "date_confidence": pa.Column(str, pa.Check.isin(base.DATE_CONFIDENCE)),
        "description": pa.Column(str),
        "source_doc": pa.Column(str, pa.Check.str_length(min_value=1)),
        "source_doc_title": pa.Column(str, nullable=True),
        "source_url": pa.Column(str, nullable=True),
        "source_page": pa.Column(str, nullable=True),
        "entered_on": pa.Column("datetime64[ns]", nullable=True),
    },
    strict=False,
    coerce=True,
)

check_results = pa.DataFrameSchema(
    {
        "check_run_id": pa.Column(str),
        "check_id": pa.Column(str, unique=True),
        "site_id": pa.Column(str),
        "call": pa.Column(str, pa.Check.isin(base.REPAIR_CALLS)),
        "effect_med": pa.Column(float, nullable=True),
        "effect_lo": pa.Column(float, nullable=True),
        "effect_hi": pa.Column(float, nullable=True),
        "change_pct_med": pa.Column(float, nullable=True),
        "change_pct_lo": pa.Column(float, nullable=True),
        "change_pct_hi": pa.Column(float, nullable=True),
        "de_t_yr_med": pa.Column(float, nullable=True),
        "de_t_yr_lo": pa.Column(float, nullable=True),
        "de_t_yr_hi": pa.Column(float, nullable=True),
        "p_decrease": pa.Column(float, _frac, nullable=True),
        "mde_pct": pa.Column(float, pa.Check.in_range(0, 100), nullable=True),
        "n_before": pa.Column(int, _nonneg),
        "n_after": pa.Column(int, _nonneg),
        "controls": pa.Column(str, nullable=True),
        "diag_ok": pa.Column("boolean", nullable=True),
        "reason": pa.Column(str, nullable=True),
        "evidence": pa.Column(str, pa.Check.isin(EVIDENCE)),
        "size": pa.Column(str, pa.Check.isin(SIZES), nullable=True),
        "colour": pa.Column(str, pa.Check.isin(COLOURS)),
        "plain_reading": pa.Column(str, pa.Check.str_length(min_value=1)),
        "provisional": pa.Column(bool),
        "restricted": pa.Column(bool),
    },
    checks=pa.Check(
        lambda df: (df["call"] == "insufficient_data") | df["effect_med"].notna(),
        error="a result other than insufficient_data needs an effect",
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
        "reported_co2e_t": pa.Column(float, _nonneg, nullable=True),
        "gwp_used": pa.Column(float, nullable=True),
        "gwp_confirmed": pa.Column(bool),
        "facility_id": pa.Column(str),
        "url": pa.Column(str),
    },
    unique=["site_id", "year", "source"],
    strict=False,
    coerce=True,
)

population = pa.DataFrameSchema(
    {
        "site_id": pa.Column(str),
        "radius_km": pa.Column(float, pa.Check.gt(0)),
        "residents": pa.Column(int, _nonneg),
        "label": pa.Column(str),
    },
    unique=["site_id", "radius_km"],
    strict=False,
    coerce=True,
)

site_features = pa.DataFrameSchema(
    {
        "site_id": pa.Column(str, unique=True),
        "closed": pa.Column(bool),
        "area_km2": pa.Column(float, pa.Check.gt(0), nullable=True),
        "ghgrp_reporter": pa.Column(bool),
        "dist_neighbor_m": pa.Column(float, _nonneg, nullable=True),
    },
    strict=False,
    coerce=True,
)

validation_results = pa.DataFrameSchema(
    {
        "report_id": pa.Column(str, unique=True),
        "gate": pa.Column(str),
        "run_id": pa.Column(str, nullable=True),
        "result": pa.Column(str, pa.Check.isin(["pass", "fail", "dry-run"])),
        "metrics": pa.Column(object),
        "superseded": pa.Column(bool),
        "note": pa.Column(str, nullable=True),
        "created_at": pa.Column(str, nullable=True),
    },
    strict=False,
    coerce=True,
)

update_log = pa.DataFrameSchema(
    {
        "item_order": pa.Column(int, pa.Check.ge(1), unique=True),
        "kind": pa.Column(str, pa.Check.isin(UPDATE_KINDS)),
        "site_id": pa.Column(str, nullable=True),
        "event_date": pa.Column("datetime64[ns]", nullable=True),
        "count": pa.Column(float, _nonneg, nullable=True),
        "text": pa.Column(str, pa.Check.str_length(min_value=1)),
    },
    strict=False,
    coerce=True,
)

TABLES = {
    "sites": sites,
    "neighbours": neighbours,
    "plumes": plumes,
    "passes": passes,
    "site_estimates": site_estimates,
    "checks": checks,
    "check_results": check_results,
    "operator_reports": operator_reports,
    "population": population,
    "site_features": site_features,
    "validation_results": validation_results,
    "update_log": update_log,
}

# Text columns that go through the wording check before a snapshot is written.
TEXT_COLUMNS = {
    "sites": ["name", "city", "county", "operator", "status", "polygon_source"],
    "neighbours": ["name"],
    "checks": ["description", "source_doc", "source_doc_title"],
    "check_results": ["plain_reading", "reason"],
    "site_estimates": ["insufficient_reason"],
    "population": ["label"],
    "validation_results": ["note"],
    "update_log": ["text"],
}
