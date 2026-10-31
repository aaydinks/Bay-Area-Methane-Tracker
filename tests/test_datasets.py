"""Builders for datasets/ and the new parsers, on small made-up inputs (no network).

Carbon Mapper rows here are invented: its data must not be redistributed, so no
recorded response is kept as a fixture.
"""

from datetime import date
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin
from shapely.geometry import box

from methanewatch import datasets
from methanewatch.ingest import carbonmapper
from methanewatch.sentinel2 import crops
from methanewatch.sentinel2 import search as s2

PRODUCT = "S2B_MSIL1C_20240408T184919_N0510_R113_T10SEG_20240409T135916.SAFE"


def test_emit_outage_days_are_flagged():
    t = pd.Series(
        pd.to_datetime(
            ["2022-09-12T23:00Z", "2022-09-13T01:00Z", "2023-01-06T20:00Z", "2023-01-07T00:00Z"],
            utc=True,
        )
    )
    assert datasets.in_emit_outage(t).tolist() == [False, True, True, False]


def test_carbonmapper_plumes_table_drops_asset_links(tmp_path):
    csv = tmp_path / "plumes.csv"
    pd.DataFrame(
        {
            "plume_id": ["tan20990101t000000x-B", "tan20990101t000000x-A"],
            "datetime": ["2099-01-01T00:00:00.5+00", "2099-01-01T00:00:00.5+00"],
            "emission_auto": [100.0, None],
            "plume_tif": ["https://example.invalid/a.tif", "https://example.invalid/b.tif"],
        }
    ).to_csv(csv, index=False)
    df = carbonmapper.plumes_table(csv)
    assert "plume_tif" not in df.columns
    assert str(df["datetime"].dt.tz) == "UTC"
    assert df["plume_id"].tolist() == ["tan20990101t000000x-A", "tan20990101t000000x-B"]


def test_carbonmapper_scenes_table_reads_detection_quantiles():
    item = {
        "id": "tan20990101t000000x",
        "geometry": box(-122.1, 37.4, -122.0, 37.5).__geo_interface__,
        "properties": {
            "datetime": "2099-01-01T00:00:00Z",
            "platform": "tan",
            "version": "v9",
            "gsd": 30.0,
            "cm:pod": {"0.1": 1.0, "0.5": 2.0, "0.9": 3.0},
        },
    }
    no_pod = {**item, "id": "x2", "properties": {**item["properties"], "cm:pod": None}}
    sc = carbonmapper.scenes_table([item, no_pod]).set_index("scene_id")
    assert sc.loc["tan20990101t000000x", "pod50_kg_hr"] == 2.0
    assert pd.isna(sc.loc["x2", "pod50_kg_hr"])


def test_sentinel2_relative_orbit_falls_back_to_product_name():
    assert s2._relative_orbit({"s2:product_uri": PRODUCT}) == 113
    assert s2._relative_orbit({"sat:relative_orbit": 13, "s2:product_uri": PRODUCT}) == 13
    assert s2._relative_orbit({}) is None


def test_gcs_prefix_from_product_name():
    assert crops.product_prefix(PRODUCT) == f"tiles/10/S/EG/{PRODUCT}/"
    with pytest.raises(ValueError):
        crops.product_prefix("not-a-product")


def test_radiometric_constants_from_metadata():
    xml = "<QUANTIFICATION_VALUE unit='none'>10000</QUANTIFICATION_VALUE>" + "".join(
        f'<RADIO_ADD_OFFSET band_id="{i}">-1000</RADIO_ADD_OFFSET>' for i in range(13)
    )
    c = crops.radiometric_constants(xml)
    assert c["quantification"] == 10000
    assert c["offset_B12"] == -1000
    # Products before baseline 04.00 have no offset
    assert crops.radiometric_constants(xml.split("<RADIO")[0])["offset_B11"] == 0


def test_scene_search_asks_for_pages_of_100(monkeypatch):
    import pystac_client

    seen = {}

    class FakeClient:
        def search(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(items=lambda: [])

    monkeypatch.setattr(pystac_client.Client, "open", staticmethod(lambda url: FakeClient()))
    assert s2.search_scenes((-122.0, 37.4, -121.9, 37.5), date(2025, 1, 1), date(2025, 2, 1)) == []
    assert seen["limit"] == s2.PAGE_SIZE == 100
    assert seen["datetime"] == "2025-01-01/2025-02-01"


def test_crop_reads_bands_in_parallel_and_keeps_their_order(tmp_path, monkeypatch):
    # Five local band files on a 20 m UTM grid, band i filled with 100 * (i + 1)
    urls = {}
    origin = from_origin(585000, 4150000, crops.RES_M, crops.RES_M)
    for i, b in enumerate(crops.BANDS):
        path = tmp_path / f"{b}.tif"
        with rasterio.open(
            path, "w", driver="GTiff", height=500, width=500, count=1, dtype="uint16",
            crs="EPSG:32610", transform=origin,
        ) as dst:  # fmt: skip
            dst.write(np.full((1, 500, 500), 100 * (i + 1), dtype="uint16"))
        urls[b] = str(path)
    urls["metadata"] = "metadata"
    xml = "<QUANTIFICATION_VALUE unit='none'>10000</QUANTIFICATION_VALUE>"
    monkeypatch.setattr(crops, "band_urls", lambda product: urls)
    monkeypatch.setattr(crops, "_get", lambda url: SimpleNamespace(text=xml))
    monkeypatch.setattr(crops, "_vsi", lambda url: url)

    lon, lat = Transformer.from_crs(32610, 4326, always_xy=True).transform(590000, 4145000)
    out = crops.crop(PRODUCT, lon, lat, 1000, tmp_path / "crop.tif", {"site_id": "a"})
    with rasterio.open(out) as src:
        data = src.read()
        assert src.descriptions == tuple(crops.BANDS)
        assert src.tags()["site_id"] == "a"
    assert data.shape == (5, 100, 100)
    assert [int(np.unique(layer)[0]) for layer in data] == [100, 200, 300, 400, 500]


def _scene(day: str, orbit: int, cloud: float, name: str) -> dict:
    return {
        "acquired_utc": pd.Timestamp(f"{day}T19:00Z"),
        "relative_orbit": orbit,
        "cloud_cover_pct": cloud,
        "product_uri": name,
        "geometry": box(-122.5, 37.0, -121.5, 38.0),
    }


def test_choose_targets_pairs_plume_days_with_quiet_references():
    sites = gpd.GeoDataFrame(
        {"site_id": ["s1"]}, geometry=gpd.points_from_xy([-122.0], [37.5]), crs="EPSG:4326"
    )
    scenes = gpd.GeoDataFrame(
        [
            _scene("2024-04-08", 113, 0, "plume"),
            _scene("2024-04-06", 113, 0, "too-close"),  # within 3 days of the plume
            _scene("2024-03-24", 113, 10, "ref1"),
            _scene("2024-03-19", 13, 0, "other-orbit"),
            _scene("2024-03-14", 113, 0, "ref2"),
            _scene("2024-03-09", 113, 50, "cloudy"),
            _scene("2024-03-04", 113, 1, "ref3"),
            _scene("2024-05-01", 113, 0, "after"),
        ],
        crs="EPSG:4326",
    )
    plumes = pd.DataFrame(
        {
            "plume_id": ["p1", "far"],
            "acquired_utc": pd.to_datetime(["2024-04-08T19:00Z", "2024-05-01T19:00Z"]),
            "lon": [-122.001, -121.6],
            "lat": [37.5, 37.9],
            "source": "test",
        }
    )
    t = crops.choose_targets(sites, plumes, scenes)
    plume_rows = t[t["role"] == "plume_day"]
    assert plume_rows["product_uri"].tolist() == ["plume"]
    assert plume_rows["plume_ids"].iloc[0] == "p1"
    refs = t[t["role"] == "reference"]
    assert refs["product_uri"].tolist() == ["ref1", "ref2", "ref3"]
    assert (refs["for_day"] == date(2024, 4, 8)).all()


def test_swis_details_page_parsing():
    from methanewatch.ingest import calrecycle

    page = (
        "<div>Site Location Address</div><div>1 Example Rd<br>Town, CA 90000</div>"
        "<div>County</div><div>Nowhere</div><div>Site Coordinates</div>"
        "<div>Latitude: 37.5 Longitude: -122.25</div>"
    )
    d = calrecycle.parse_details(page)
    assert d == {"address": "1 Example Rd Town, CA 90000", "latitude": 37.5, "longitude": -122.25}
    assert calrecycle.parse_details("<p>nothing</p>")["latitude"] is None
