"""Rows bound for the database: nested values read back from parquet must become plain JSON."""

import json

import pandas as pd

from methanewatch.publish.load import _rows


def test_nested_arrays_from_parquet_become_plain_json(tmp_path):
    metrics = [
        {"wilson": [0.084, 0.193], "rates": {"model": {"false_usable": [0.1, 0.2]}}},
        {"wilson": None, "rates": None, "labels": ["closed", "log_area"]},
    ]
    path = tmp_path / "t.parquet"
    pd.DataFrame({"metrics": metrics}).to_parquet(path, index=False)
    back = pd.read_parquet(path)

    rows = _rows(back, ["metrics"], {})
    plain = [json.loads(json.dumps(r[0].obj)) for r in rows]

    assert plain[0]["wilson"] == [0.084, 0.193]
    assert plain[0]["rates"]["model"]["false_usable"] == [0.1, 0.2]
    assert plain[1]["labels"] == ["closed", "log_area"]
    assert plain[1]["wilson"] is None
