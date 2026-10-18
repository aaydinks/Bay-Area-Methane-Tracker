from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from methanewatch import quantify
from methanewatch.config import load_quantify
from methanewatch.wind import era5, hrrr


def test_ppb_to_column_mass():
    # 1 ppb over a standard-pressure dry column is about 5.7e-6 kg CH4 per m^2
    assert quantify.ppb_to_kg_m2(1.0, 101325) == pytest.approx(5.72e-6, rel=0.01)


def gaussian_plume(amplitude_ppb=200.0, sigma_px=6.0, pixel_m=20.0, n=200, noise_ppb=0.0, seed=0):
    x = np.arange(n) * pixel_m
    xx, yy = np.meshgrid(np.arange(n), np.arange(n))
    c = n / 2
    blob = amplitude_ppb * np.exp(-((xx - c) ** 2 + (yy - c) ** 2) / (2 * sigma_px**2))
    blob = blob + np.random.default_rng(seed).normal(0, noise_ppb, blob.shape)
    da = xr.DataArray(blob, coords={"y": x, "x": x}, dims=("y", "x"))
    true_mass = quantify.ppb_to_kg_m2(amplitude_ppb * 2 * np.pi * sigma_px**2, 101325) * pixel_m**2
    return da, float(true_mass)


def test_ime_recovers_known_mass():
    da, true_mass = gaussian_plume()
    mask = da > 0.01 * float(da.max())
    plume = quantify.measure_plume(da, mask)
    assert plume.ime_kg == pytest.approx(true_mass, rel=0.02)
    assert plume.n_pixels == int(mask.sum())
    assert plume.length_m == pytest.approx(np.sqrt(plume.n_pixels) * 20)


def test_rate_matches_formula_without_noise():
    cfg = load_quantify()
    quiet = cfg.model_copy(
        update={"ueff": cfg.ueff.model_copy(update={"relative_sigma": 0.0}), "n_draws": 500}
    )
    plume = quantify.Plume(ime_kg=100.0, area_m2=250_000.0, n_pixels=625, background_sigma_ppb=0.0)
    r = quantify.rate_kg_hr(plume, u10_ms=4.0, u10_sigma_ms=1e-6, cfg=quiet)
    ueff = cfg.ueff.a.value * 4.0 + cfg.ueff.b.value
    assert r.median_kg_hr == pytest.approx(ueff * 100.0 / 500.0 * 3600, rel=1e-3)
    assert not r.confirmed_calibration


def test_rate_interval_widens_with_noise():
    da, _ = gaussian_plume(noise_ppb=20.0)
    mask = gaussian_plume()[0] > 2.0
    plume = quantify.measure_plume(da, mask)
    assert plume.background_sigma_ppb == pytest.approx(20.0, rel=0.1)
    r = quantify.rate_kg_hr(plume, u10_ms=3.0)
    assert r.lo_kg_hr < r.median_kg_hr < r.hi_kg_hr


def test_hrrr_nearest_handles_0_360_longitudes():
    lat, lon = np.meshgrid([37.0, 37.5, 38.0], [237.5, 238.0, 238.5], indexing="ij")
    ds = xr.Dataset(
        {
            "u10": (("y", "x"), np.arange(9.0).reshape(3, 3)),
            "v10": (("y", "x"), -np.arange(9.0).reshape(3, 3)),
        },
        coords={"latitude": (("y", "x"), lat), "longitude": (("y", "x"), lon)},
    )
    u, v = hrrr.nearest(ds, lon=-122.0, lat=37.45)  # -122.0 == 238.0
    assert (u, v) == (4.0, -4.0)


def test_era5_request_box():
    req = era5.request(-122.0, 37.45, pd.Timestamp(datetime(2025, 6, 1, 18, tzinfo=UTC)))
    assert req["area"] == [37.7, -122.25, 37.2, -121.75]
    assert req["time"] == ["18:00"] and req["month"] == ["06"]
