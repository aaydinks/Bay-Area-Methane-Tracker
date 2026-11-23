"""Shapes of the published tables, matching ``supabase/migrations/0002_tables.sql`` and the
migrations that add to it.

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
        # The air district is read from CARB's 2004 outlines until a person has checked it
        "air_district": pa.Column(str, nullable=True),
        "air_district_confirmed": pa.Column(bool),
        "district_facility_id": pa.Column(str, nullable=True),
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
        "display_only": pa.Column(bool, required=False),
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
        # ADR 0014 (migration 0006). Null when the overpass table predates them, and optional
        # so snapshots written before them still load.
        "valid_frac_tile": pa.Column(float, _frac, nullable=True, required=False),
        "valid_frac_source": pa.Column(
            str, pa.Check.isin(base.VALID_FRAC_SOURCES), nullable=True, required=False
        ),
        "coverage_source": pa.Column(str, pa.Check.isin(base.COVERAGE_SOURCES), nullable=True),
        "detected": pa.Column(bool),
        "q_obs_kg_hr": pa.Column(float, pa.Check.gt(0), nullable=True),
        "n_plumes": pa.Column(int, _nonneg),
        "restricted": pa.Column(bool),
        "display_only": pa.Column(bool, required=False),
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
        "display_only": pa.Column(bool, required=False),
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
        "display_only": pa.Column(bool, required=False),
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

# Measures beside the methane estimate (ADR 0019). ``restricted`` and ``display_only`` follow
# the source's terms, as they do for plumes.
site_metrics = pa.DataFrameSchema(
    {
        "site_id": pa.Column(str),
        "metric_id": pa.Column(str, pa.Check.str_length(min_value=1)),
        "period": pa.Column(str, pa.Check.str_length(min_value=1)),
        "source": pa.Column(str, pa.Check.str_length(min_value=1)),
        "value": pa.Column(float, nullable=True),
        "value_text": pa.Column(str, nullable=True),
        "unit": pa.Column(str, pa.Check.str_length(min_value=1)),
        "kind": pa.Column(str, pa.Check.isin(base.METRIC_KINDS)),
        "confirmed": pa.Column(bool),
        "source_id": pa.Column(str, nullable=True),
        "url": pa.Column(str, nullable=True),
        "restricted": pa.Column(bool),
        "display_only": pa.Column(bool),
    },
    checks=pa.Check(
        lambda df: df["value"].notna() | df["value_text"].notna(),
        error="a measure needs a number or a text value",
    ),
    unique=["site_id", "metric_id", "period", "source"],
    strict=False,
    coerce=True,
)

# The catalogue of measures (config/metrics.yaml) as each publication carries it, so a page
# shows the labels its figures were published with.
metric_catalogue = pa.DataFrameSchema(
    {
        "metric_id": pa.Column(str, pa.Check.str_length(min_value=1), unique=True),
        "label": pa.Column(str, pa.Check.str_length(min_value=1)),
        "unit": pa.Column(str, pa.Check.str_length(min_value=1)),
        "kind": pa.Column(str, pa.Check.isin(base.METRIC_KINDS)),
        "source": pa.Column(str, pa.Check.str_length(min_value=1)),
        "caveat": pa.Column(str, nullable=True),
        "sort_order": pa.Column(int, pa.Check.ge(1), unique=True),
    },
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

# Columns `mw publish build` stamps on the assembled tables (ADR 0021), keyed by database
# table. They are not in the schemas above: a snapshot written before the public scope
# existed has none of them, and the load then uses the database's "in scope" defaults.
#   region        the project region a site (by county) or a plume (by place) falls in
#   public_scope  the public website may show the row
#   site_public   plumes only: the public website may show which site the plume is tied to
SCOPE_COLUMNS = {
    "sites": ["region", "public_scope"],
    "neighbours": ["public_scope"],
    "plumes": ["region", "public_scope", "site_public"],
    "passes": ["public_scope"],
    "site_estimates": ["public_scope"],
    "checks": ["public_scope"],
    "check_results": ["public_scope"],
    "operator_reports": ["public_scope"],
    "population_context": ["public_scope"],
    "site_features": ["public_scope"],
    "site_metrics": ["public_scope"],
    "update_log": ["public_scope"],
}
SCOPE_DEFAULTS = {"region": None, "public_scope": True, "site_public": True}

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
    "site_metrics": site_metrics,
    "metric_catalogue": metric_catalogue,
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
    "site_metrics": ["value_text", "unit"],
    "metric_catalogue": ["label", "unit", "caveat"],
    "validation_results": ["note"],
    "update_log": ["text"],
}
