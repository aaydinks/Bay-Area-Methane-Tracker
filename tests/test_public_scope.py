"""What the public website may show (ADR 0021): the allowlist and the stamp on each row."""

import geopandas as gpd
import pandas as pd
import pytest

from methanewatch import config
from methanewatch.config import PublicScope, load_data_terms, load_impact
from methanewatch.publish import schemas as pub
from methanewatch.publish import snapshot as snap
from tests.test_publish_snapshot import _project, _write_inputs

PILOTS_ONLY = PublicScope(regions=("bay-area",), tiers=("pilot",))


def _build(tmp_path, scope=None):
    return snap.build(
        _project(tmp_path),
        load_data_terms(),
        load_impact(),
        model_run_id="model-1",
        check_run_id="repairs-1",
        publish_id="pub-scope",
        scope=scope,
    )


def _sonoma_under_review(tmp_path):
    """Make Sonoma Central a screening site, tie one plume to it, and put one plume in the
    North Valley (just east of the Bay Area box) and one east of every region."""
    interim = tmp_path / "interim"
    sites = gpd.read_parquet(interim / "sites.parquet")
    sites["tier"] = ["pilot", "screen"]
    sites.to_parquet(interim / "sites.parquet")
    plumes = pd.read_parquet(interim / "plumes_attributed.parquet")
    extra = plumes.iloc[[0, 0, 0]].copy()
    extra["plume_id"] = ["e-sonoma", "e-valley", "e-east"]
    extra["site_id"] = ["sonoma-central", None, None]
    extra["attribution"] = ["buffer", "none", "none"]
    extra["distance_m"] = [120.0, None, None]
    extra["origin_lon"] = [-122.75, -121.196, -119.9]
    extra["origin_lat"] = [38.30, 37.872, 37.3]
    pd.concat([plumes, extra], ignore_index=True).to_parquet(interim / "plumes_attributed.parquet")


def test_committed_allowlist_is_exactly_what_is_public_today():
    scope = config.load_public_scope()
    assert scope.regions == ("bay-area",) and scope.tiers == ("pilot",)
    assert scope.unknown_regions(config.load_project()) == []
    assert scope.allows("bay-area", "pilot")
    assert not scope.allows("bay-area", "screen")
    assert not scope.allows("north-valley", "pilot")
    assert not scope.allows(None, "pilot") and not scope.allows("bay-area", None)


def test_allowlist_refuses_an_unknown_tier_and_reports_an_unknown_region():
    with pytest.raises(ValueError):
        PublicScope(regions=("bay-area",), tiers=("everything",))
    assert PublicScope(regions=("mars",), tiers=("pilot",)).unknown_regions(
        config.load_project()
    ) == ["mars"]


def test_region_of_a_county_and_of_a_point():
    project = config.load_project()
    assert project.region_of_county("Santa Clara") == "bay-area"
    assert project.region_of_county(" sonoma ") == "bay-area"
    assert project.region_of_county("San Joaquin") == "north-valley"
    assert project.region_of_county("Kern") is None
    assert project.region_of_county(None) is None
    assert project.region_of_county(float("nan")) is None
    assert project.region_at(-121.94, 37.46) == "bay-area"
    # The two boxes overlap. A point in both counts as the Bay Area, as it did before the
    # North Valley was added, so the plumes the public map shows stay the same.
    assert project.region_at(-121.29, 37.96) == "bay-area"  # Stockton
    assert project.region_at(-121.196, 37.872) == "north-valley"  # just east of the Bay Area box
    assert project.region_at(-119.9, 37.3) is None  # east of every region


def test_with_only_pilots_every_row_is_in_scope(tmp_path):
    _write_inputs(tmp_path)
    tables = _build(tmp_path).tables
    assert tables["sites"]["region"].tolist() == ["bay-area", "bay-area"]
    for name, cols in pub.SCOPE_COLUMNS.items():
        key = {"population_context": "population"}.get(name, name)
        if key == "update_log":
            continue  # written when the snapshot is pushed
        for col in set(cols) - {"region"}:
            assert tables[key][col].all(), (key, col)
            assert tables[key][col].dtype == bool, (key, col)
    assert tables["plumes"]["region"].eq("bay-area").all()
    assert "public_scope" not in tables["validation_results"]


def test_rows_of_a_site_under_review_are_out_and_its_plume_keeps_only_its_place(tmp_path):
    _write_inputs(tmp_path)
    _sonoma_under_review(tmp_path)
    tables = _build(tmp_path, PILOTS_ONLY).tables
    sites = tables["sites"].set_index("site_id")
    assert sites["public_scope"].to_dict() == {"newby-island": True, "sonoma-central": False}
    assert snap.open_sites(tables["sites"]) == {"newby-island"}
    for name in ("passes", "site_estimates", "site_features"):
        by_site = tables[name].groupby("site_id")["public_scope"].all().to_dict()
        assert by_site == {"newby-island": True, "sonoma-central": False}, name
    for name in ("checks", "check_results", "operator_reports"):
        assert tables[name]["public_scope"].all(), name  # all at Newby Island

    plumes = tables["plumes"].set_index("plume_id")
    assert plumes.loc["e1", ["public_scope", "site_public"]].tolist() == [True, True]
    # In an allowed region, tied to a site under review: shown, but not its tie to the site
    assert plumes.loc["e-sonoma", ["public_scope", "site_public"]].tolist() == [True, False]
    # In a region that is not on the allowlist: not shown
    assert plumes.loc["e-valley", ["public_scope", "site_public"]].tolist() == [False, True]
    assert plumes.loc["e-valley", "region"] == "north-valley"
    # In no region: not shown
    assert plumes.loc["e-east", ["public_scope", "site_public"]].tolist() == [False, True]
    assert plumes.loc["e-east", "region"] is None


def test_a_wider_allowlist_opens_the_screening_site(tmp_path):
    _write_inputs(tmp_path)
    _sonoma_under_review(tmp_path)
    scope = PublicScope(regions=("bay-area",), tiers=("pilot", "screen"))
    tables = _build(tmp_path, scope).tables
    assert tables["sites"]["public_scope"].all()
    assert tables["plumes"].set_index("plume_id").loc["e-sonoma", "site_public"]


def test_stamp_survives_writing_and_reading_a_snapshot(tmp_path):
    _write_inputs(tmp_path)
    _sonoma_under_review(tmp_path)
    folder = _build(tmp_path, PILOTS_ONLY).write(tmp_path / "out")
    back = snap.Snapshot.read(folder).tables
    assert back["sites"].set_index("site_id")["public_scope"].to_dict() == {
        "newby-island": True,
        "sonoma-central": False,
    }
    assert snap.open_sites(back["sites"]) == {"newby-island"}


def test_a_snapshot_from_before_the_scope_counts_every_site_as_open():
    old = pd.DataFrame({"site_id": ["a", "b"]})
    assert snap.open_sites(old) == {"a", "b"}
