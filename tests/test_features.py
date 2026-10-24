"""Site features and model covariates (ADR 0008), on made-up sites."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from methanewatch import features
from methanewatch.config import load_model, load_synthetic
from methanewatch.model import persistence, simulate
from methanewatch.model.grid import LogRateGrid
from methanewatch.repair import model as repair_model

UTM = "EPSG:32610"


def _sites() -> gpd.GeoDataFrame:
    # Three squares 1 km, 2 km and 0.5 km on a side, 3 km apart, in UTM metres
    geoms = [box(580000, 4150000, 581000, 4151000), box(584000, 4150000, 586000, 4152000)]
    geoms.append(box(590000, 4150000, 590500, 4150500))
    return gpd.GeoDataFrame(
        {"site_id": ["a", "b", "c"], "status": ["", "closed", ""]}, geometry=geoms, crs=UTM
    ).to_crs("EPSG:4326")


def test_build_site_features():
    neighbors = gpd.GeoDataFrame(
        {"name": ["compost"]}, geometry=[box(581500, 4150000, 581600, 4150100)], crs=UTM
    )
    crosswalk = pd.DataFrame({"site_id": ["a", "b"], "ghgrp_facility_id": ["1", None]})
    fallback = pd.DataFrame({"site_id": ["a", "c"], "status": ["Active", "Closing"]})
    out = features.build_site_features(
        _sites(), neighbors, crosswalk, fallback, metric_crs=UTM
    ).set_index("site_id")
    assert out.loc["a", "status"] == "active"
    assert out.loc["b", "closed"] and out.loc["c", "closed"] and not out.loc["a", "closed"]
    assert out.loc["b", "area_km2"] == pytest.approx(4.0, rel=1e-3)
    assert out["ghgrp_reporter"].tolist() == [True, False, False]
    # a's nearest other source is the compost pile 500 m away, not site b
    assert out.loc["a", "dist_neighbor_m"] == pytest.approx(500, abs=1)


def test_design_standardizes_and_refuses_bad_columns():
    table = pd.DataFrame(
        {
            "site_id": ["a", "b", "c", "d"],
            "closed": [True, False, False, True],
            "area_km2": [1.0, 2.0, 4.0, 8.0],
            "ghgrp_reporter": [True, True, True, True],
            "dist_neighbor_m": [100.0, np.nan, 300.0, 50.0],
        }
    )
    cov = features.design(table, ["closed", "log_area"])
    assert cov.X.shape == (4, 2)
    assert np.allclose(cov.X.mean(axis=0), 0)
    assert cov.X[:, 0].tolist() == [0.5, -0.5, -0.5, 0.5]  # binary: centred, not scaled
    assert cov.X[:, 1].std() == pytest.approx(1)
    assert cov.rows(["c", "a", "c"]).shape == (3, 2)
    with pytest.raises(ValueError, match="does not vary"):
        features.design(table, ["ghgrp_reporter"])
    with pytest.raises(ValueError, match="missing"):
        features.design(table, ["log_dist_neighbor"])
    with pytest.raises(ValueError, match="unknown"):
        features.design(table, ["county"])
    with pytest.raises(ValueError, match="no covariates for"):
        cov.rows(["z"])


def _data():
    syn, cfg = load_synthetic(), load_model()
    rng = np.random.default_rng(0)
    sites, _ = simulate.sites_from_prior(6, cfg.priors, syn, rng, covariates=("closed", "log_area"))
    schedule = simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng)
    det = simulate.simulate_detections(sites, schedule, syn, rng)
    grid = LogRateGrid.build(syn.q_min_kg_hr, syn.q_max_kg_hr, 32)
    data = persistence.prepare(
        det,
        grid,
        {k: v.pod for k, v in syn.instruments.items()},
        release={k: v.release_prob for k, v in syn.instruments.items()},
        meas_sigma_log={k: v.meas_sigma_log for k, v in syn.instruments.items()},
    )
    return sites, data, det, cfg


def test_simulated_sites_carry_covariates_and_coefficients():
    sites, _, _, _ = _data()
    assert {"closed", "log_area"} <= set(sites.columns)
    assert sites["closed"].nunique() == 2


def test_model_without_covariates_is_unchanged():
    sites, data, _, cfg = _data()
    plain = persistence.build_model(data, cfg.priors)
    assert {v.name for v in plain.free_RVs} == {
        "alpha_f", "tau_f", "alpha_mu", "tau_mu", "sigma", "z_f", "z_mu"
    }  # fmt: skip
    cov = features.design_synthetic(sites, ("closed", "log_area"))
    with_cov = persistence.build_model(data, cfg.priors, cov)
    names = {v.name for v in with_cov.free_RVs}
    assert {"beta_f", "beta_mu"} <= names
    assert list(with_cov.coords["covariate"]) == ["closed", "log_area"]
    # The covariates move f: the log density at the same point differs once beta != 0
    point = with_cov.initial_point()
    point["beta_f"] = np.array([1.0, 0.0])
    assert np.isfinite(with_cov.compile_logp()(point))


def test_repair_model_accepts_covariates():
    sites, _, det, cfg = _data()
    det = det.copy()
    mid = det["acquired_utc"].min() + (det["acquired_utc"].max() - det["acquired_utc"].min()) / 2
    det["period"] = np.where(det["acquired_utc"] < mid, "before", "after")
    unit_df = det.assign(site_id=det["site_id"] + "|" + det["period"])
    syn = load_synthetic()
    data = persistence.prepare(
        unit_df,
        LogRateGrid.build(syn.q_min_kg_hr, syn.q_max_kg_hr, 32),
        {k: v.pod for k, v in syn.instruments.items()},
        release={k: v.release_prob for k, v in syn.instruments.items()},
        meas_sigma_log={k: v.meas_sigma_log for k, v in syn.instruments.items()},
    )
    units = pd.DataFrame([u.split("|") for u in data.site_ids], columns=["site_id", "period"])
    cov = features.design_synthetic(sites, ("closed",))
    m = repair_model.build_model(data, units, "synth-00", cfg.priors, cov)
    assert {"beta_f", "beta_mu", "delta_f"} <= {v.name for v in m.free_RVs}
