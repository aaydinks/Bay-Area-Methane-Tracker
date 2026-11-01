"""Per-site cloud shares on pilot passes and the ADR 0014 transfer check, on synthetic data.

No network: band files are small local GeoTIFFs and the catalogue is a stand-in.
"""

import json
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from shapely.geometry import box
from typer.testing import CliRunner

from methanewatch.sentinel2 import cloudrecent as cr
from methanewatch.sentinel2 import crops
from methanewatch.sentinel2 import sitecloud as sc
from methanewatch.sentinel2.cloudmodel import BANDS, CLEAR, CLOUD

ULX, ULY = 499980.0, 4200000.0
TILE_M = 12000


def tile_files(tmp_path, value=lambda b, res, rows, cols: cols + 1):
    """One GeoTIFF per band at its native resolution, all on the same tile origin."""
    paths = {}
    for b in BANDS:
        res = sc.NATIVE_M[b]
        n = TILE_M // res
        rows, cols = np.mgrid[0:n, 0:n]
        arr = value(b, res, rows, cols).astype("uint16")
        p = tmp_path / f"{b}.tif"
        profile = {"driver": "GTiff", "height": n, "width": n, "count": 1, "dtype": "uint16"}
        profile |= {
            "crs": "EPSG:32610",
            "transform": rasterio.transform.from_origin(ULX, ULY, res, res),
        }
        with rasterio.open(p, "w", **profile) as dst:
            dst.write(arr[None])
        paths[b] = str(p)
    return paths


METADATA = "<QUANTIFICATION_VALUE unit='none'>10000</QUANTIFICATION_VALUE>" + "".join(
    f'<RADIO_ADD_OFFSET band_id="{i}">-1000</RADIO_ADD_OFFSET>' for i in range(13)
)


@pytest.fixture
def local_tile(tmp_path, monkeypatch):
    paths = tile_files(tmp_path)
    monkeypatch.setattr(crops, "band_urls", lambda uri, bands: {**paths, "metadata": "m"})
    monkeypatch.setattr(crops, "_get", lambda url: SimpleNamespace(text=METADATA))
    monkeypatch.setattr(crops, "_vsi", lambda url: url)
    return paths


def test_window_edges_lie_on_the_60m_grid_and_span_6km():
    b = sc.snapped_bounds(ULX, ULY, 505017.3, 4193981.9)
    assert (b[2] - b[0], b[3] - b[1]) == (6000, 6000)
    assert (b[0] - ULX) % 60 == 0 and (ULY - b[3]) % 60 == 0
    assert abs((b[0] + b[2]) / 2 - 505017.3) <= 30 and abs((b[1] + b[3]) / 2 - 4193981.9) <= 30


def test_ten_metre_bands_average_and_sixty_metre_bands_repeat(local_tile):
    x, y = ULX + 6000, ULY - 6000
    w = sc.read_l1c("S2C_MSIL1C_20250601T185921_N0511_R013_T10SEG_x.SAFE", x, y)
    assert w["dn"].shape == (13, sc.WINDOW_PX, sc.WINDOW_PX)
    col0 = round((w["bounds"][0] - ULX) / 10)  # first 10 m column of the window
    b02 = w["dn"][BANDS.index("B02")]
    assert b02[0, 0] == np.rint((col0 + 1 + col0 + 2) / 2)  # mean of two 10 m columns
    b01 = w["dn"][BANDS.index("B01")]
    assert (b01[:, 0] == b01[:, 2]).all() and (b01[0, 0:3] == b01[0, 0]).all()
    assert b01[0, 3] == b01[0, 0] + 1  # next 60 m pixel
    b11 = w["dn"][BANDS.index("B11")]
    assert b11[0, 1] - b11[0, 0] == 1  # 20 m bands read as they are
    assert w["valid"].all()
    assert w["consts"]["offset_B12"] == -1000


def test_window_outside_the_tile_is_refused(local_tile):
    with pytest.raises(ValueError, match="not inside tile"):
        sc.read_l1c("S2A_MSIL1C_20250601T185921_N0511_R013_T10SEG_x.SAFE", ULX + 1000, ULY - 1000)


def test_reflectance_applies_the_offset_after_marking_no_data():
    dn = np.full((13, 2, 2), 1500, np.uint16)
    dn[:, 0, 0] = 0
    dn[:, 1, 1] = 900  # below the offset: floored, still data
    valid = dn.min(axis=0) > 0
    consts = {"quantification": 10000.0, **{f"offset_{b}": -1000.0 for b in BANDS}}
    r = sc.reflectance(dn, valid, consts)
    assert np.isnan(r[:, 0, 0]).all()
    assert np.allclose(r[:, 0, 1], 0.05)
    assert np.allclose(r[:, 1, 1], sc.MIN_REFLECTANCE)
    old = sc.reflectance(dn, valid, {"quantification": 10000.0})  # pre-04.00: no offset
    assert np.allclose(old[:, 0, 1], 0.15)


class StubModel:
    """Calls a fixed block cloud, everything else clear."""

    def __init__(self, cloud):
        self.cloud = cloud

    def predict(self, refl):
        out = np.full(refl.shape[1:], CLEAR, np.uint8)
        out[self.cloud] = CLOUD
        return out


def window(scl=None, valid=None):
    n = sc.WINDOW_PX
    return sc.Window13(
        dn=np.full((13, n, n), 2000, np.uint16),
        valid=np.ones((n, n), bool) if valid is None else valid,
        scl=scl,
        bounds=np.array([ULX, ULY - 6000, ULX + 6000, ULY]),
        consts={"quantification": 10000.0},
        scl_source=None,
    )


def test_shares_cover_the_central_area_only():
    n = sc.WINDOW_PX
    cloud = np.zeros((n, n), bool)
    cloud[:10, :] = True  # outer ring only
    row, _ = sc.score(window(), StubModel(cloud))
    assert row["clear_model"] == 1.0 and row["scored"]
    rs, cs = sc.scored_slice()
    cloud[rs, cs] = False
    cloud[rs.start : rs.start + sc.SCORE_PX // 2, cs] = True
    row, _ = sc.score(window(), StubModel(cloud))
    assert row["clear_model"] == pytest.approx(0.5)


def test_sen2cor_cloud_and_shadow_classes_are_unusable_and_zero_is_no_data():
    n = sc.WINDOW_PX
    rs, cs = sc.scored_slice()
    scl = np.full((n, n), 4, np.uint8)
    block = scl[rs, cs]
    block[:64] = 9
    block[64:96] = 3
    block[96:127] = 0
    row, _ = sc.score(window(scl=scl), StubModel(np.zeros((n, n), bool)))
    assert row["scl_nodata_share"] == pytest.approx(31 / 254)
    assert row["clear_scl"] == pytest.approx(1 - 96 / (254 - 31))


def test_windows_with_more_than_one_percent_no_data_are_not_scored():
    n = sc.WINDOW_PX
    valid = np.ones((n, n), bool)
    rs, cs = sc.scored_slice()
    valid[rs.start : rs.start + 5, cs] = False  # 2% of the scored area
    row, _ = sc.score(window(valid=valid), StubModel(np.zeros((n, n), bool)))
    assert not row["scored"] and row["nodata_share"] == pytest.approx(5 / 254)


def test_window_round_trips_through_its_cache_file(tmp_path):
    w = window(scl=np.zeros((sc.WINDOW_PX,) * 2, np.uint8))
    w.scl_source = {"collection": "sentinel-2-c1-l2a", "item": "i", "href": "h"}
    again = sc.Window13.load(w.save(tmp_path / "a" / "w.npz"))
    assert (again.dn == w.dn).all() and again.scl_source == w.scl_source
    assert sc.Window13.load(window().save(tmp_path / "b.npz")).scl is None


class StubCatalogue:
    def __init__(self, by_collection):
        self.by_collection = by_collection

    def search(self, collections, **_):
        items = self.by_collection.get(collections[0], [])
        return SimpleNamespace(items=lambda: iter(items))


def item(uri):
    return SimpleNamespace(
        id=uri[:30], properties={"s2:product_uri": uri}, assets={"scl": SimpleNamespace(href=uri)}
    )


def test_sen2cor_match_needs_the_same_platform_and_sensing_time():
    l1c = "S2C_MSIL1C_20250601T185921_N0511_R013_T10SEG_20250601T204525.SAFE"
    other = item("S2A_MSIL2A_20250601T185921_N0511_R013_T10SEG_20250601T215011.SAFE")
    later = item("S2C_MSIL2A_20250601T190921_N0511_R013_T10SEG_20250601T215011.SAFE")
    right = item("S2C_MSIL2A_20250601T185921_N0511_R013_T10SEG_20250601T215011.SAFE")
    cat = StubCatalogue({"sentinel-2-c1-l2a": [other, later], "sentinel-2-l2a": [right]})
    hit = sc.find_scl(l1c, cat)
    assert hit["collection"] == "sentinel-2-l2a" and hit["href"] == right.assets["scl"].href
    assert sc.find_scl(l1c, StubCatalogue({"sentinel-2-c1-l2a": [other]})) is None


def test_scene_holding_the_whole_window_is_chosen():
    x, y = 590000.0, 4150000.0
    win = gpd.GeoSeries([box(x - 3000, y - 3000, x + 3000, y + 3000)], crs=sc.METRIC_CRS)
    big = win.buffer(5000).to_crs(4326).iloc[0]
    half = gpd.GeoSeries([box(x - 9000, y - 9000, x, y + 9000)], crs=sc.METRIC_CRS)
    fp = gpd.GeoDataFrame(
        {"scene_id": ["a", "b"]}, geometry=[half.to_crs(4326).iloc[0], big], crs=4326
    ).set_index("scene_id")
    assert sc.choose_scene(["a", "b"], fp, x, y) == "b"
    assert sc.choose_scene(["a"], fp, x, y) == "a"


# --- the ADR 0014 check -------------------------------------------------------------------


def days_frame(n_days=40, per_day=5, p_event=0.1, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        hit = rng.random() < p_event  # weather is shared by every site that day
        for s in range(per_day):
            rows.append({"day": f"D{d:02d}", "site_id": f"s{s}", "given": True, "event": hit})
    return pd.DataFrame(rows)


def test_day_rate_resamples_days_so_shared_weather_widens_the_range():
    df = days_frame()
    r = cr.day_rate(df, "event", "given")
    assert r["n_days"] == 40 and r["n_windows"] == 200
    assert r["interval"][0] <= r["value"] <= r["interval"][1]
    # Same data treated as 200 independent days gives a narrower range
    flat = df.assign(day=[f"X{i}" for i in range(len(df))])
    f = cr.day_rate(flat, "event", "given")
    assert f["value"] == r["value"]
    assert (f["interval"][1] - f["interval"][0]) < (r["interval"][1] - r["interval"][0])


def test_platform_gap_is_sentinel_2c_minus_the_others():
    df = pd.DataFrame(
        {
            "day": ["a", "b", "c", "d"],
            "platform": ["sentinel-2c", "sentinel-2c", "sentinel-2a", "sentinel-2b"],
            "clear_model": [0.9, 0.8, 0.5, 0.5],
            "clear_scl": [0.7, 0.6, 0.5, 0.5],
        }
    )
    g = cr.platform_gap(df)
    assert g["value"] == pytest.approx(0.2) and g["n_s2c"] == 2


def eye_windows():
    rng = np.random.default_rng(1)
    n = 60
    return pd.DataFrame(
        {
            "overpass_id": [f"o{i}" for i in range(n)],
            "scored": True,
            "clear_model": rng.random(n),
            "clear_scl": rng.random(n),
        }
    )


def test_eye_draw_takes_each_group_and_numbers_them_shuffled():
    draw = cr.eye_draw(eye_windows())
    counts = draw["group"].value_counts().to_dict()
    assert counts == cr.EYE_DRAW
    assert sorted(draw["thumb"]) == list(range(1, 25))
    assert len(set(draw["group"].iloc[:8])) > 1  # not in group order
    again = cr.eye_draw(eye_windows())
    assert (again["overpass_id"] == draw["overpass_id"]).all()


def test_recent_check_runs_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "RESULTS_DIR", tmp_path)
    (tmp_path / "s2-cloud-recent-earlier.json").write_text("{}")
    with pytest.raises(FileExistsError):
        cr.run(tmp_path)


def pending_result(site_passed):
    sites = {s: {"passed": ok, "n_clear_days": 30} for s, ok in site_passed.items()}
    sites = {
        s: {**v, "area_share_flagged": 0.0, "site_share_flagged": 0.0} for s, v in sites.items()
    }
    crit = {
        "1_scale": {"passed": True, "water_b12_median": 0.01, "limits": [-0.02, 0.03]},
        "2_clear_kept": {"passed": True, "value": 0.05, "interval": [0.03, 0.07]},
        "3_cloudy_rejected": {"passed": True, "value": 0.05, "interval": [0.03, 0.07]},
        "4_platform": {"passed": True, "value": 0.01, "interval": [-0.01, 0.03], "limit": 0.05},
        "5_false_clouds": {"sites": sites, "passed": all(site_passed.values())},
        "6_eye": {"status": "pending"},
    }
    for k in ("2_clear_kept", "3_cloudy_rejected"):
        crit[k] |= {"n_windows": 50, "limit": 0.15}
    windows = {"site_days": 5, "acquisition_days": 1, "scored": 5, "partial": 0}
    return {
        "run_id": "s2-cloud-recent-x",
        "created_at": "t",
        "git_sha": "g",
        "git_dirty": False,
        "model_sha256": "m",
        "windows": windows | {"read_errors": 0, "no_scl": 0},
        "criteria": crit,
        "per_site": {},
    }


def write_pending(tmp_path, site_passed, labels):
    res = tmp_path / "reports"
    res.mkdir()
    (res / "s2-cloud-recent-x.json").write_text(json.dumps(pending_result(site_passed)))
    key = pd.DataFrame(
        {
            "thumb": [1, 2, 3, 4],
            "overpass_id": ["a", "b", "c", "d"],
            "group": ["model_only", "scl_only", "both_usable", "both_unusable"],
            "clear_model": [0.9, 0.2, 0.9, 0.1],
            "clear_scl": [0.2, 0.9, 0.9, 0.1],
        }
    )
    kd = cr._key_dir(tmp_path)
    kd.mkdir(parents=True)
    key.to_json(kd / "s2-cloud-recent-x-eye-key.json", orient="records")
    body = "thumb,usable,note\n" + "".join(f"{t},{u},\n" for t, u in enumerate(labels, 1))
    (res / "eye-labels.csv").write_text(body)
    return res


def test_a_site_with_fixed_false_clouds_falls_back_to_sen2cor(tmp_path, monkeypatch):
    res = write_pending(tmp_path, {"a": True, "b": False}, ["yes", "no", "yes", "no"])
    monkeypatch.setattr(cr, "RESULTS_DIR", res)
    out = json.loads(cr.finish(tmp_path).read_text())
    assert out["criteria"]["6_eye"]["passed"]
    assert out["criteria"]["6_eye"]["model_matches_eye"] == 2
    assert out["verdict"] == {"holds": False, "model_sites": ["a"], "sen2cor_sites": ["b"]}
    assert "Verdict" in (res / "s2-cloud-recent-x.md").read_text()
    with pytest.raises(FileExistsError):
        cr.finish(tmp_path)


def test_losing_the_eye_check_sends_every_site_to_sen2cor(tmp_path, monkeypatch):
    res = write_pending(tmp_path, {"a": True, "b": True}, ["no", "yes", "yes", "no"])
    monkeypatch.setattr(cr, "RESULTS_DIR", res)
    out = json.loads(cr.finish(tmp_path).read_text())
    assert not out["criteria"]["6_eye"]["passed"]
    assert out["verdict"] == {"holds": False, "model_sites": [], "sen2cor_sites": ["a", "b"]}


def test_every_thumbnail_needs_a_label(tmp_path, monkeypatch):
    res = write_pending(tmp_path, {"a": True}, ["yes", "", "yes", "no"])
    monkeypatch.setattr(cr, "RESULTS_DIR", res)
    with pytest.raises(ValueError, match="usable = yes or no"):
        cr.finish(tmp_path)


def test_cli_lists_the_recent_commands():
    from methanewatch.cli import app

    res = CliRunner().invoke(app, ["s2", "cloud", "--help"])
    assert "recent" in res.output and "recent-eye" in res.output
