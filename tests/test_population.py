import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from methanewatch import population

FX = Path(__file__).parent / "fixtures"
UTM = "EPSG:32610"


def test_parse_recorded_tigerweb_block_groups():
    groups = population.from_geojson(json.loads((FX / "tigerweb_block_groups.geojson").read_text()))
    assert list(groups["GEOID"].str.len().unique()) == [12]
    assert groups.geometry.is_valid.all()


def test_areal_weighting_on_simple_squares():
    # Two 1 km x 1 km block groups side by side; the area covers half of the first only.
    squares = gpd.GeoSeries(
        [box(590000, 4146000, 591000, 4147000), box(591000, 4146000, 592000, 4147000)], crs=UTM
    ).to_crs("EPSG:4326")
    groups = gpd.GeoDataFrame(
        {"GEOID": ["a", "b"], "STATE": "06", "COUNTY": "085"}, geometry=squares, crs="EPSG:4326"
    )
    pop = pd.DataFrame({"GEOID": ["a", "b"], "population": [1000, 400]})
    area = (
        gpd.GeoSeries([box(590000, 4146000, 590500, 4147000)], crs=UTM).to_crs("EPSG:4326").iloc[0]
    )
    assert population.areal_population(area, groups, pop, UTM) == pytest.approx(500, rel=0.01)


def test_residents_within_grows_with_radius():
    groups = population.from_geojson(json.loads((FX / "tigerweb_block_groups.geojson").read_text()))
    pop = pd.DataFrame({"GEOID": groups["GEOID"], "population": [1200, 800]})
    site = Point(-121.945, 37.462).buffer(0.002)
    out = population.residents_within(site, [0.5, 1.0], UTM, groups=groups, population=pop)
    assert 0 <= out[0.5] <= out[1.0] <= 2000


def test_population_needs_a_key(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    with pytest.raises(population.MissingCensusKeyError):
        population.acs_population("06", ["085"])
