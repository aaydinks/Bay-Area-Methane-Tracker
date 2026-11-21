"""The project's regions (ADR 0018): one definition in config, read by every module."""

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from methanewatch import config
from methanewatch.ingest import ghgrp

NINE = {
    "001": "Alameda",
    "013": "Contra Costa",
    "041": "Marin",
    "055": "Napa",
    "075": "San Francisco",
    "081": "San Mateo",
    "085": "Santa Clara",
    "095": "Solano",
    "097": "Sonoma",
}


def _raw() -> dict:
    return yaml.safe_load((config.CONFIG_DIR / "project.yaml").read_text())


def test_bay_area_region_matches_the_values_the_code_used_before():
    project = config.load_project()
    bay = next(r for r in project.regions if r.id == "bay-area")
    assert bay.bbox == (-123.64, 36.89, -121.20, 38.87)
    assert {c.fips: c.name for c in bay.counties} == NINE
    assert bay.carb_districts == ("BA",)


FIVE = {
    "047": "Merced",
    "067": "Sacramento",
    "077": "San Joaquin",
    "099": "Stanislaus",
    "113": "Yolo",
}


def test_north_valley_region_is_the_five_counties():
    project = config.load_project()
    assert [r.id for r in project.regions] == ["bay-area", "north-valley"]  # overlap: first wins
    valley = project.regions[1]
    assert {c.fips: c.name for c in valley.counties} == FIVE
    # the five counties' extent in the Census 2025 county file, rounded outwards
    west, south, east, north = valley.bbox
    assert west <= -122.4220 and south <= 36.7404 and east >= -120.0521 and north >= 38.9259
    assert east < config.UTM10_EAST_LON
    assert valley.carb_districts == ()
    assert project.bbox == (-123.64, 36.74, -120.05, 38.93)
    assert project.county_fips == dict(sorted((NINE | FIVE).items()))
    assert project.carb_districts == ("BA",)


def test_project_box_and_counties_cover_every_region():
    raw = _raw()
    raw["regions"] = raw["regions"][:1]
    raw["regions"].append(
        {
            "id": "north-valley",
            "label": "North Valley",
            "bbox": [-121.9, 36.7, -120.05, 38.95],
            "carb_districts": ["SJV", "BA"],
            "counties": [{"name": "San Joaquin", "fips": "077"}],
        }
    )
    project = config.ProjectConfig.model_validate(raw)
    assert project.bbox == (-123.64, 36.7, -120.05, 38.95)
    assert list(project.county_fips)[-2:] == ["095", "097"]  # FIPS order
    assert project.county_fips["077"] == "San Joaquin"
    assert project.carb_districts == ("BA", "SJV")  # each code once, in first-seen order


def test_region_east_of_120w_is_refused():
    raw = _raw()
    raw["regions"][0]["bbox"] = [-123.64, 36.89, -119.5, 38.87]
    with pytest.raises(ValidationError, match="outside UTM zone 10N"):
        config.ProjectConfig.model_validate(raw)


def test_duplicate_region_or_county_is_refused():
    raw = _raw()
    raw["regions"].append(dict(raw["regions"][0], id="copy"))
    with pytest.raises(ValidationError, match="more than one region"):
        config.ProjectConfig.model_validate(raw)
    raw = _raw()
    raw["regions"].append(dict(raw["regions"][0], counties=[{"name": "Kern", "fips": "029"}]))
    with pytest.raises(ValidationError, match="duplicate region id"):
        config.ProjectConfig.model_validate(raw)


def test_ghgrp_county_filter_ignores_the_word_county(monkeypatch):
    rows = [
        {"facility_id": 1, "county": "SAN JOAQUIN COUNTY"},
        {"facility_id": 2, "county": "San Joaquin"},
        {"facility_id": 3, "county": "KERN COUNTY"},
        {"facility_id": 4, "county": None},
    ]
    extra = {"facility_name": "x", "city": "y", "latitude": 0, "longitude": 0, "year": 2023}
    monkeypatch.setattr(ghgrp, "_get", lambda client, path: [r | extra for r in rows])
    out = ghgrp.facilities_in(["San Joaquin"], 2023)
    assert out["facility_id"].tolist() == [1, 2]
    assert isinstance(out, pd.DataFrame)
