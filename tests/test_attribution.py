import pytest
from shapely.geometry import Point, box

from methanewatch.attribution import classify

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
