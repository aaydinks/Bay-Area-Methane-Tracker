import pandas as pd
import pandera.errors
import pytest

from methanewatch import schemas


def test_detections_require_rate_exactly_when_detected():
    good = pd.DataFrame(
        {
            "overpass_id": ["a:emit:2025-01-01", "a:emit:2025-02-01"],
            "site_id": ["a", "a"],
            "instrument": ["emit", "emit"],
            "detected": [True, False],
            "q_obs_kg_hr": [450.0, None],
            "q_sigma_log": [0.3, None],
        }
    )
    schemas.detections.validate(good)
    bad = good.assign(q_obs_kg_hr=[None, 100.0])
    with pytest.raises(pandera.errors.SchemaError):
        schemas.detections.validate(bad)


def test_repairs_need_a_source_document():
    row = {
        "repair_id": "r1",
        "site_id": "sonoma-central",
        "date_start": "2023-06-15",
        "date_end": None,
        "kind": "leak-repair",
        "description": "surface leak repair",
        "source_doc": "",
        "source_page": None,
        "date_confidence": "exact",
    }
    with pytest.raises(pandera.errors.SchemaError):
        schemas.repairs.validate(pd.DataFrame([row]))
    schemas.repairs.validate(pd.DataFrame([{**row, "source_doc": "air-district-fine.pdf"}]))
