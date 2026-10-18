import numpy as np
import pandas as pd
import pytest
import xarray as xr

from methanewatch.sentinel2 import detect, masks, retrieval

N, PX = 120, 20.0
COORDS = {"y": np.arange(N) * PX, "x": np.arange(N) * PX}


def surface(seed=0):
    rng = np.random.default_rng(seed)
    base = 0.2 + 0.1 * np.sin(np.arange(N)[:, None] / 9) * np.cos(np.arange(N)[None, :] / 13)
    return base + rng.normal(0, 0.002, (N, N))


def scene(b11, b12, **extra):
    data = {"B11": (("y", "x"), b11), "B12": (("y", "x"), b12)}
    data.update({k: (("y", "x"), v) for k, v in extra.items()})
    return xr.Dataset(data, coords=COORDS)


def plume_shape(cx=60, cy=60, sx=8, sy=4):
    yy, xx = np.mgrid[0:N, 0:N]
    return np.exp(-((xx - cx) ** 2) / (2 * sx**2) - ((yy - cy) ** 2) / (2 * sy**2))


def pair(absorption_peak=0.05, seed=1):
    rng = np.random.default_rng(seed)
    s = surface()
    ref = scene(s * 1.1, s * 0.85 * (1 + rng.normal(0, 0.003, s.shape)))
    tgt_b12 = s * 0.85 * (1 + rng.normal(0, 0.003, s.shape)) * (1 - absorption_peak * plume_shape())
    tgt = scene(s * 1.1 * 0.97, tgt_b12 * 0.97)  # 3% brighter or dimmer pass overall is fine
    return tgt, ref


def all_valid():
    return xr.DataArray(np.ones((N, N), bool), coords=COORDS, dims=("y", "x"))


def test_mbmp_recovers_injected_absorption():
    tgt, ref = pair()
    dr = retrieval.mbmp(tgt, ref, all_valid(), all_valid())
    a = retrieval.fractional_absorption(dr)
    assert float(a.values[60, 60]) == pytest.approx(0.05, rel=0.2)
    assert abs(float(np.nanmedian(a.values[:20, :20]))) < 0.005


def test_masks_flag_dark_water_and_cloud():
    s = surface()
    b12 = s.copy()
    b12[:10, :10] = 0.02  # dark
    b03 = np.full((N, N), 0.05)
    b08 = np.full((N, N), 0.25)
    b08[20:30, 20:30] = 0.01  # water: NDWI > 0
    b02 = np.full((N, N), 0.1)
    b02[40:45, 40:45] = 0.4  # cloud
    valid = masks.artifact_mask(scene(s, b12, B02=b02, B03=b03, B08=b08))
    assert not valid.values[:10, :10].any()
    assert not valid.values[20:30, 20:30].any()
    assert not valid.values[40:45, 40:45].any()
    assert valid.values[60:, 60:].all()


def site_box(x0, x1, y0, y1):
    m = np.zeros((N, N), bool)
    m[y0:y1, x0:x1] = True
    return xr.DataArray(m, coords=COORDS, dims=("y", "x"))


def test_detection_finds_plume_at_site_and_ignores_elsewhere():
    tgt, ref = pair()
    a = retrieval.fractional_absorption(retrieval.mbmp(tgt, ref, all_valid(), all_valid()))
    hit = detect.detect_plume(a, all_valid(), site_box(45, 75, 45, 75))
    assert hit is not None and hit.n_pixels > 20
    assert abs(hit.origin_x - 60 * PX) <= 2 * PX and abs(hit.origin_y - 60 * PX) <= 2 * PX
    assert detect.detect_plume(a, all_valid(), site_box(0, 20, 0, 20)) is None


def test_detection_with_wind_picks_upwind_end():
    tgt, ref = pair()
    a = retrieval.fractional_absorption(retrieval.mbmp(tgt, ref, all_valid(), all_valid()))
    hit = detect.detect_plume(a, all_valid(), site_box(0, N, 0, N), wind_uv=(1.0, 0.0))
    assert hit.origin_x < 60 * PX - 5 * PX  # well left of the peak for a wind blowing to +x


def test_no_plume_no_detection():
    tgt, ref = pair(absorption_peak=0.0)
    a = retrieval.fractional_absorption(retrieval.mbmp(tgt, ref, all_valid(), all_valid()))
    assert detect.detect_plume(a, all_valid(), site_box(40, 80, 40, 80)) is None


def test_ppb_lookup(tmp_path):
    a = xr.DataArray(np.array([[0.0, 0.01, np.nan]]), dims=("y", "x"))
    with pytest.raises(retrieval.MissingLookupTableError):
        retrieval.to_ppb(a, None)
    table = tmp_path / "lut.csv"
    pd.DataFrame({"fractional_absorption": [0.0, 0.02], "delta_xch4_ppb": [0.0, 2000.0]}).to_csv(
        table, index=False
    )
    out = retrieval.to_ppb(a, table).values[0]
    assert out[0] == 0 and out[1] == pytest.approx(1000.0) and np.isnan(out[2])
