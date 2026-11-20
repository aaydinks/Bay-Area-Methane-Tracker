"""Screening-tier proposal from CalRecycle's records (ADR 0018), with no network.

``fixtures/calrecycle_landfill_boundaries.geojson`` was recorded on 2026-11-19 from the layer
``mw ingest calrecycle-boundaries`` reads, for three SWIS numbers, with
``geometryPrecision=4`` and ``maxAllowableOffset=0.0005`` so the outlines are coarse and small.
"""

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from methanewatch.ingest import calrecycle_boundaries as cb
from methanewatch.sites import registry, screening

FX = Path(__file__).parent / "fixtures"
UTM = "EPSG:32610"
REGIONS = {"Santa Clara": "bay-area", "San Joaquin": "north-valley"}


def _landfills(rows):
    cols = ["swis_number", "name", "county", "landfill_status", "regulatory_status", "x", "y"]
    df = pd.DataFrame(rows, columns=cols)
    lonlat = gpd.GeoSeries(gpd.points_from_xy(df["x"], df["y"]), crs=UTM).to_crs("EPSG:4326")
    return df.assign(longitude=lonlat.x, latitude=lonlat.y).drop(columns=["x", "y"])


def _no_layer():
    return gpd.GeoDataFrame({"swis_number": [], "layer_name": []}, geometry=[], crs="EPSG:4326")


def _no_sites():
    return gpd.GeoDataFrame({"site_id": []}, geometry=[], crs="EPSG:4326")


def _propose(landfills, layer=None, existing=None, existing_swis=None, overrides=None):
    return screening.propose(
        landfills,
        _no_layer() if layer is None else layer,
        county_region=REGIONS,
        existing=_no_sites() if existing is None else existing,
        existing_swis=existing_swis or {},
        boundaries_as_of="2021-09",
        overrides=overrides,
    )


def test_boundary_layer_fixture_reads_as_one_valid_outline_per_swis_number():
    out = cb.outlines(FX / "calrecycle_landfill_boundaries.geojson")
    assert out["swis_number"].tolist() == ["39-AA-0015", "43-AN-0001", "43-AN-0003"]
    assert out.set_index("swis_number").loc["43-AN-0003", "layer_name"].startswith("Newby Island")
    assert out.crs == "EPSG:4326" and out.is_valid.all()


def test_boundary_layer_errors_are_refused(tmp_path):
    bad = tmp_path / "x.geojson"
    bad.write_text(json.dumps({"error": {"code": 400, "message": "Invalid query"}}))
    with pytest.raises(ValueError, match="Invalid query"):
        cb.outlines(bad)
    cut = json.loads((FX / "calrecycle_landfill_boundaries.geojson").read_text())
    bad.write_text(json.dumps(cut | {"exceededTransferLimit": True}))
    with pytest.raises(ValueError, match="cut short"):
        cb.outlines(bad)


def test_pull_writes_a_manifest(tmp_path, monkeypatch):
    fixture = (FX / "calrecycle_landfill_boundaries.geojson").read_bytes()
    monkeypatch.setattr(cb, "_get", lambda client, url: fixture)
    pull_dir = cb.pull(tmp_path)
    manifest = json.loads((pull_dir / "manifest.json").read_text())
    assert manifest["source"] == "calrecycle-boundaries" and manifest["n_records"] == 3
    assert cb.latest(tmp_path) == pull_dir / cb.FILE
    assert cb.latest(tmp_path / "nothing") is None


def test_only_permitted_landfills_are_selected_unless_overridden():
    lf = _landfills(
        [
            ("43-AA-0001", "Alpha Landfill", "Santa Clara", "Active", "Permitted", 590000, 4146000),
            ("43-AA-0002", "Beta Dump", "Santa Clara", "Closed", "Unpermitted", 600000, 4146000),
            ("43-AA-0003", "Gamma Waste Unit", "Santa Clara", "Active", "Exempt", 610000, 4146000),
            (
                "43-AA-0004",
                "Delta Steel Unit",
                "Santa Clara",
                "Closing",
                "Permitted",
                620000,
                4146000,
            ),
        ]
    )
    picked = screening.select(lf).set_index("swis_number")
    assert picked["included"].tolist() == [True, False, False, True]
    assert picked.loc["43-AA-0002", "reason"] == "regulatory status: Unpermitted"

    overrides = pd.DataFrame(
        {
            "swis_number": ["43-AA-0004", "43-AA-0002"],
            "include": ["no", "yes"],
            "reason": ["industrial unit", "listed by the district"],
        }
    )
    picked = screening.select(lf, overrides).set_index("swis_number")
    assert picked["included"].tolist() == [True, True, False, False]
    assert picked.loc["43-AA-0004", "reason"] == "override: industrial unit"

    with pytest.raises(ValueError, match="not in the list"):
        screening.select(lf, overrides.assign(swis_number=["99-ZZ-0001", "43-AA-0002"]))
    with pytest.raises(ValueError, match="yes or no"):
        screening.select(lf, overrides.assign(include=["maybe", "yes"]))


def test_proposed_rows_carry_region_status_and_a_provisional_source():
    lf = _landfills(
        [
            (
                "43-AA-0001",
                "Alpha Landfill & Recycling",
                "Santa Clara",
                "Active",
                "Permitted",
                590000,
                4146000,
            ),
            ("39-AA-0002", "Delta Site", "San Joaquin", "Closing", "Permitted", 650000, 4200000),
            ("15-AA-0003", "Far Away Landfill", "Kern", "Active", "Permitted", 700000, 4000000),
        ]
    )
    p = _propose(lf)
    rows = p.sites.set_index("site_id")
    assert list(rows.index) == ["alpha-landfill-and-recycling", "delta-site"]
    assert rows["region"].tolist() == ["bay-area", "north-valley"]
    assert rows["tier"].eq("screen").all()
    assert rows["status"].tolist() == ["active", ""]  # "Closing" is left for a person
    assert rows.loc["delta-site", "notes"] == "SWIS landfill status: Closing"
    assert rows["polygon_source"].str.startswith("provisional 750 m buffer").all()
    assert any("county Kern is in no region" in x for x in p.problems)
    assert p.outlines["part"].eq("boundary").all() and p.outlines.crs == "EPSG:4326"
    assert len(p.review) == 3


def test_two_buffers_closer_than_their_width_are_cut_halfway_and_pass_registry_qa():
    # 613 m apart, like two San Jose sites in the real list
    lf = _landfills(
        [
            ("43-AN-0001", "West Site", "Santa Clara", "Active", "Permitted", 590000, 4146000),
            ("43-AN-0007", "East Site", "Santa Clara", "Active", "Permitted", 590613, 4146000),
        ]
    )
    p = _propose(lf)
    assert p.problems == []
    m = p.outlines.to_crs(UTM).set_index("site_id").geometry
    assert m["west-site"].intersection(m["east-site"]).area < 1.0
    assert m["west-site"].bounds[2] == pytest.approx(590306.5, abs=0.5)  # the halfway line
    assert m["west-site"].contains(Point(590000, 4146000))
    assert registry.qa_overlaps(p.outlines.to_crs("EPSG:4326"), UTM) == []


def test_a_drawn_outline_is_used_and_buffers_give_way_to_it():
    lf = _landfills(
        [
            ("43-AA-0001", "Drawn Landfill", "Santa Clara", "Active", "Permitted", 590000, 4146000),
            (
                "43-AA-0002",
                "Buffered Landfill",
                "Santa Clara",
                "Closed",
                "Permitted",
                591200,
                4146000,
            ),
        ]
    )
    drawn = box(589500, 4145500, 590600, 4146500)
    layer = gpd.GeoDataFrame(
        {"swis_number": ["43-AA-0001"], "layer_name": ["Drawn"]}, geometry=[drawn], crs=UTM
    ).to_crs("EPSG:4326")
    p = _propose(lf)
    assert p.sites["polygon_source"].str.startswith("provisional").all()
    p = _propose(lf, layer=layer)
    rows = p.sites.set_index("site_id")
    assert rows.loc["drawn-landfill", "polygon_source"].startswith("CalRecycle LandfillBoundaries")
    assert "2021-09" in rows.loc["drawn-landfill", "polygon_source"]
    assert rows.loc["buffered-landfill", "polygon_source"].startswith("provisional")
    m = p.outlines.to_crs(UTM).set_index("site_id").geometry
    assert m["drawn-landfill"].area == pytest.approx(drawn.area, rel=1e-3)
    assert m["buffered-landfill"].intersection(m["drawn-landfill"]).area < 1.0
    assert m["buffered-landfill"].area < Point(0, 0).buffer(750).area
    assert registry.qa_overlaps(p.outlines.to_crs("EPSG:4326"), UTM) == []


def test_sites_already_in_the_registry_are_not_proposed_again_and_keep_their_ground():
    lf = _landfills(
        [
            (
                "43-AN-0003",
                "Newby Island Sanitary Landfill",
                "Santa Clara",
                "Active",
                "Permitted",
                590000,
                4146000,
            ),
            (
                "43-AA-0002",
                "Neighbour Landfill",
                "Santa Clara",
                "Active",
                "Permitted",
                591000,
                4146000,
            ),
        ]
    )
    pilot = Point(590000, 4146000).buffer(500)
    existing = gpd.GeoDataFrame({"site_id": ["newby-island"]}, geometry=[pilot], crs=UTM).to_crs(
        "EPSG:4326"
    )
    p = _propose(lf, existing=existing, existing_swis={"43-AN-0003": "newby-island"})
    assert p.sites["site_id"].tolist() == ["neighbour-landfill"]
    review = p.review.set_index("swis_number")
    assert review.loc["43-AN-0003", "site_id"] == "newby-island"
    assert review.loc["43-AN-0003", "outline"] == "already in the registry"
    m = p.outlines.to_crs(UTM).geometry.iloc[0]
    assert m.intersection(pilot).area < 1.0


def test_things_a_person_must_settle_are_reported_not_guessed():
    lf = _landfills(
        [
            ("43-AA-0001", "Twin Landfill", "Santa Clara", "Active", "Permitted", 590000, 4146000),
            ("43-AA-0002", "Twin Landfill", "Santa Clara", "Closed", "Permitted", 595000, 4146000),
            ("43-AA-0003", "Same Point A", "Santa Clara", "Active", "Permitted", 600000, 4146000),
            ("43-AA-0004", "Same Point B", "Santa Clara", "Active", "Permitted", 600000, 4146000),
            ("43-AA-0005", "Inside Unit", "Santa Clara", "Active", "Permitted", 610000, 4146000),
            ("43-AA-0006", "Big Landfill", "Santa Clara", "Active", "Permitted", 610100, 4146000),
        ]
    )
    lf.loc[lf["swis_number"] == "43-AA-0004", ["latitude", "longitude"]] = lf.loc[
        lf["swis_number"] == "43-AA-0003", ["latitude", "longitude"]
    ].to_numpy()
    layer = gpd.GeoDataFrame(
        {"swis_number": ["43-AA-0006"], "layer_name": ["Big"]},
        geometry=[box(609000, 4145000, 611000, 4147000)],
        crs=UTM,
    ).to_crs("EPSG:4326")
    p = _propose(lf, layer=layer)
    text = " | ".join(p.problems)
    assert "site ids not unique" in text and "twin-landfill" in text
    assert "share one SWIS point" in text
    assert "inside-unit: its SWIS point lies inside the outline of big-landfill" in text
    assert "twin-landfill" not in p.sites["site_id"].tolist()


def test_site_slug():
    assert screening.site_slug("Tri Cities Recycling & Disposal Fac") == (
        "tri-cities-recycling-and-disposal-fac"
    )
    assert screening.site_slug("  Forward Landfill, Inc. ") == "forward-landfill-inc"
