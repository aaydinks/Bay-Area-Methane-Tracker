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


def _check_row(**kw) -> dict:
    return {
        "check_id": "c1",
        "site_id": "sonoma-central",
        "check_type": "air-district-notice",
        "repair_kind": None,
        "date_start": "2023-06-15",
        "date_end": None,
        "date_confidence": "exact",
        "description": "surface monitoring round with leaks above the limit",
        "source_doc": "air-district-notice-2023-06.pdf",
        "source_doc_title": "Notice of Violation A12345",
        "source_url": None,
        "source_page": None,
    } | kw


def test_checks_need_a_source_document():
    with pytest.raises(pandera.errors.SchemaError):
        schemas.checks.validate(pd.DataFrame([_check_row(source_doc="")]))
    schemas.checks.validate(pd.DataFrame([_check_row()]))


@pytest.mark.parametrize("check_type", schemas.CHECK_TYPES)
def test_every_check_type_is_accepted(check_type):
    kind = "cover" if check_type == "operator-repair" else None
    schemas.checks.validate(pd.DataFrame([_check_row(check_type=check_type, repair_kind=kind)]))


def test_unknown_check_type_and_repair_without_kind_are_rejected():
    with pytest.raises(pandera.errors.SchemaError):
        schemas.checks.validate(pd.DataFrame([_check_row(check_type="epa-inspection")]))
    with pytest.raises(pandera.errors.SchemaError):
        schemas.checks.validate(pd.DataFrame([_check_row(check_type="operator-repair")]))
    schemas.checks.validate(
        pd.DataFrame([_check_row(check_type="operator-repair", repair_kind="leak-repair")])
    )
