"""Which regulator a dated check came from (ADR 0020): the registry column and its check
against the air district of the record's site."""

import pandas as pd

from methanewatch import schemas
from methanewatch.ingest.airdistrict import regulator_problems
from tests.test_schemas import _check_row

SITES = pd.DataFrame(
    {
        "site_id": ["newby-island", "kiefer", "no-district"],
        "air_district": ["Bay Area", "Sacramento Metro", ""],
    }
)


def _checks(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame([_check_row(**r) for r in rows])


def test_the_checks_schema_takes_a_regulator_and_does_not_require_the_column():
    schemas.checks.validate(
        _checks({"regulator": "Bay Area"}, {"check_id": "c2", "regulator": None})
    )
    schemas.checks.validate(_checks({}))


def test_an_air_district_record_must_name_its_regulator():
    checks = _checks({"site_id": "kiefer", "check_type": "air-district-inspection"})
    assert regulator_problems(checks, SITES) == [
        "c1: an air district record needs its regulator, CARB's name for the district "
        "(Sacramento Metro)"
    ]
    blank = checks.assign(regulator=[" "])
    assert len(regulator_problems(blank, SITES)) == 1


def test_a_record_from_another_district_than_its_site_is_reported():
    checks = _checks({"site_id": "kiefer", "regulator": "Bay Area"})
    (problem,) = regulator_problems(checks, SITES)
    assert "regulator is Bay Area but kiefer sits in the Sacramento Metro air district" in problem


def test_a_record_that_agrees_with_its_site_passes():
    checks = _checks(
        {"site_id": "kiefer", "regulator": "Sacramento Metro"},
        {"check_id": "c2", "site_id": "newby-island", "regulator": "Bay Area"},
    )
    assert regulator_problems(checks, SITES) == []


def test_a_site_with_no_district_on_file_is_not_compared():
    checks = _checks({"site_id": "no-district", "regulator": "Bay Area"})
    assert regulator_problems(checks, SITES) == []
    assert regulator_problems(checks, SITES.drop(columns="air_district")) == []


def test_other_record_types_may_leave_the_regulator_blank():
    checks = _checks(
        {"check_type": "operator-repair", "repair_kind": "cover"},
        {"check_id": "c2", "check_type": "carb-plume-notice", "regulator": "CARB"},
        {"check_id": "c3", "check_type": "other"},
    )
    assert regulator_problems(checks, SITES) == []


def test_no_checks_means_no_problems():
    assert regulator_problems(pd.DataFrame(columns=["check_id"]), SITES) == []
