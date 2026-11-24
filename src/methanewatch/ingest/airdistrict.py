"""Hand-entered regulator and operator records (PLAN section 5, phase 2f).

Dated checks live in ``data/registry/checks.csv``: air district inspections and notices, operator
repairs and CARB plume notices. Every row cites a source document. There is no scraping; rows are
entered by hand from the records and validated by ``schemas.checks`` when the test runs.

Sites fall under several air districts (ADR 0018), so a record says which regulator it came from
in its ``regulator`` column (ADR 0020). For an air district record that is CARB's name for the
district, the same name ``sites.csv`` uses in ``air_district``. The pages name the regulator of
such a record from its site's district, so the two must agree: ``regulator_problems`` lists every
record where they do not, and a publication is not built while there is one.
"""

from __future__ import annotations

import pandas as pd

# Record types whose regulator is the air district the site sits in.
AIR_DISTRICT_TYPES = ("air-district-inspection", "air-district-notice")


def _text(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def regulator_problems(checks: pd.DataFrame, sites: pd.DataFrame) -> list[str]:
    """What is wrong with the ``regulator`` column of the dated checks, in plain words.

    An air district record must name its regulator, and the name must be the air district of
    its site (``sites["air_district"]``, checked by a person or read from CARB's outlines). A
    site with no district on file is not compared. Other record types may leave it blank.
    """
    problems: list[str] = []
    if not len(checks):
        return problems
    regulator = checks["regulator"] if "regulator" in checks else pd.Series("", index=checks.index)
    district = {}
    if "air_district" in sites:
        district = {
            s: _text(d) for s, d in zip(sites["site_id"], sites["air_district"], strict=True)
        }
    rows = zip(checks["check_id"], checks["site_id"], checks["check_type"], regulator, strict=True)
    for check_id, site_id, check_type, given in rows:
        if check_type not in AIR_DISTRICT_TYPES:
            continue
        given = _text(given)
        expected = district.get(site_id, "")
        if not given:
            hint = f" ({expected})" if expected else ""
            problems.append(
                f"{check_id}: an air district record needs its regulator, "
                f"CARB's name for the district{hint}"
            )
        elif expected and given != expected:
            problems.append(
                f"{check_id}: regulator is {given} but {site_id} sits in the {expected} air "
                "district; correct the record, or air_district in sites.csv"
            )
    return problems
