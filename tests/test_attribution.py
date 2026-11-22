import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from methanewatch.attribution import attribute_plumes, classify

SITES = {"landfill-a": box(0, 0, 1000, 1000), "landfill-b": box(5000, 0, 6000, 1000)}
NEIGHBORS = {"compost": box(1800, 0, 2200, 400)}
KW = {"buffer_m": 500, "search_radius_m": 5000}


@pytest.mark.parametrize(
    "point, site, label",
    [
        (Point(500, 500), "landfill-a", "inside"),
        (Point(500, 1300), "landfill-a", "buffer"),
        (Point(1400, 200), "landfill-a", "ambiguous"),  # compost facility also within buffer
        (Point(500, 3000), "landfill-a", "nearby"),
        (Point(500, 20_000), None, "none"),
    ],
)
def test_classify(point, site, label):
    got = classify(point, SITES, NEIGHBORS, **KW)
    assert (got.site_id, got.label) == (site, label)
    assert got.feeds_model == (label in ("inside", "buffer"))


def _plumes(sectors):
    # One plume on landfill-a, one in its buffer, one 2 km away, one far from everything
    points = [Point(500, 500), Point(500, 1300), Point(500, 3000), Point(500, 20_000)]
    lonlat = gpd.GeoSeries(points, crs="EPSG:32610").to_crs("EPSG:4326")
    df = pd.DataFrame({"origin_lon": lonlat.x, "origin_lat": lonlat.y})
    return df if sectors is None else df.assign(ipcc_sector=sectors)


def _attribute(plumes, **kw):
    sites = gpd.GeoDataFrame(
        {"site_id": list(SITES)}, geometry=list(SITES.values()), crs="EPSG:32610"
    )
    return attribute_plumes(plumes, sites, sites.iloc[0:0], metric_crs="EPSG:32610", **KW, **kw)


WASTE = ("Solid Waste (6A)",)


def test_a_plume_tagged_with_another_sector_is_ambiguous_and_keeps_its_site():
    got = _attribute(_plumes(["Other", "Livestock (4B)", "Oil & Gas (1B2)", "Livestock (4B)"]),
                     waste_sectors=WASTE)  # fmt: skip
    # On the landfill or in its buffer: listed beside the site, never counted for it.
    assert got["attribution"].tolist() == ["ambiguous", "ambiguous", "nearby", "none"]
    assert got["site_id"].tolist()[:3] == ["landfill-a"] * 3 and pd.isna(got["site_id"][3])
    assert got["distance_m"].tolist()[:2] == pytest.approx([0.0, 300.0], abs=1.0)


@pytest.mark.parametrize("sectors", [["Solid Waste (6A)"] * 4, [None, "", " ", None], None])
def test_waste_tags_missing_tags_and_untagged_sources_follow_distance_alone(sectors):
    got = _attribute(_plumes(sectors), waste_sectors=WASTE)
    assert got["attribution"].tolist() == ["inside", "buffer", "nearby", "none"]


def test_without_the_setting_sector_tags_are_ignored():
    got = _attribute(_plumes(["Other"] * 4))
    assert got["attribution"].tolist() == ["inside", "buffer", "nearby", "none"]
