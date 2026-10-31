"""The latest-update feed is a difference of two snapshots."""

from datetime import date

import pandas as pd

from methanewatch.publish.feed import update_items

TODAY = date(2026, 10, 31)


def _plumes(ids):
    return pd.DataFrame(
        {
            "source": "emit-v2",
            "plume_id": ids,
            "site_id": "newby-island",
            "acquired_utc": pd.Timestamp("2026-09-18", tz="UTC"),
        }
    )


def test_first_publication_counts_everything_as_new():
    current = {
        "plumes": _plumes(["a", "b"]),
        "checks": pd.DataFrame(
            {"check_id": ["c1"], "site_id": ["sonoma-central"], "date_start": ["2023-06-15"]}
        ),
        "validation_results": pd.DataFrame(
            {
                "report_id": ["g3"],
                "gate": ["gate3"],
                "result": ["pass"],
                "run_id": ["r"],
                "created_at": [None],
            }
        ),
        "sites": pd.DataFrame({"site_id": ["newby-island"], "polygon_source": ["provisional"]}),
    }
    items, new = update_items(
        current,
        None,
        current_runs={"model_run_id": "m1", "check_run_id": None},
        previous_runs=None,
        site_names={"newby-island": "Newby Island Landfill"},
        today=TODAY,
    )
    kinds = [i["kind"] for i in items]
    assert kinds == ["new-plumes", "new-record", "new-model-run", "gate-result"]
    assert items[0]["text"] == "2 new plumes near Newby Island Landfill." and items[0]["count"] == 2
    assert new == {("emit-v2", "a"), ("emit-v2", "b")}
    assert [i["item_order"] for i in items] == [1, 2, 3, 4]


def test_unchanged_snapshot_has_no_items_and_outline_changes_are_noticed():
    sites_before = pd.DataFrame({"site_id": ["newby-island"], "polygon_source": ["provisional"]})
    sites_after = pd.DataFrame(
        {"site_id": ["newby-island"], "polygon_source": ["traced from imagery"]}
    )
    base = {
        "plumes": _plumes(["a"]),
        "checks": pd.DataFrame(columns=["check_id", "site_id", "date_start"]),
        "validation_results": pd.DataFrame(
            columns=["report_id", "gate", "result", "run_id", "created_at"]
        ),
    }
    runs = {"model_run_id": "m1", "check_run_id": "c1"}
    items, new = update_items(
        {**base, "sites": sites_before},
        {**base, "sites": sites_before},
        current_runs=runs,
        previous_runs=runs,
        today=TODAY,
    )
    assert items == [] and new == set()
    items, _ = update_items(
        {**base, "sites": sites_after},
        {**base, "sites": sites_before},
        current_runs=runs,
        previous_runs=runs,
        today=TODAY,
    )
    assert [i["kind"] for i in items] == ["outline-change"]
