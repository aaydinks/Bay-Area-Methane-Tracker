"""EPA Landfill Methane Outreach Program (LMOP) database: how each landfill is run (ADR 0025).

Checked live on 2026-11-27:

- ``https://www.epa.gov/lmop/project-and-landfill-data-state`` links one workbook per state as
  ``/system/files/documents/<YYYY-MM>/lmopdata<st>.xlsx``. The folder is the edition; the newest
  that day was 2024-09, and EPA says it updates the files two to three times a year.
- The sheet ``LMOP Database`` has one row per landfill and energy project. Every landfill has at
  least one row, and its landfill-level columns repeat on each of its rows.
- A landfill is keyed by EPA's own ``Landfill ID``. The file has no SWIS number, so each
  landfill is matched to the registry by hand in ``data/registry/lmop_crosswalk.csv``.

Figures are written as EPA publishes them, in its units. Nothing is converted and nothing is
estimated. EPA notes that not every figure is updated each year.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch import schemas
from methanewatch.provenance import PullManifest

SOURCE = "epa-lmop"  # the key of this source in config/data_terms.yaml
PAGE = "https://www.epa.gov/lmop/project-and-landfill-data-state"
STATE = "ca"
SHEET = "LMOP Database"
FILE = "lmopdata.xlsx"

# Column names as the workbook writes them
C_ID = "Landfill ID"
C_NAME = "Landfill Name"
C_COUNTY = "County"
C_GHGRP = "GHGRP ID"
C_WASTE = "Waste in Place (tons)"
C_WASTE_YEAR = "Waste in Place Year"
C_SYSTEM = "LFG Collection System In Place?"
C_COLLECTED = "LFG Collected (mmscfd)"
C_FLARED = "LFG Flared (mmscfd)"
C_PROJECT_STATUS = "Current Project Status"
C_PROJECT_TYPE = "LFG Energy Project Type"
LANDFILL_COLUMNS = (
    C_NAME,
    C_COUNTY,
    C_GHGRP,
    C_WASTE,
    C_WASTE_YEAR,
    C_SYSTEM,
    C_COLLECTED,
    C_FLARED,
)
COLUMNS = (C_ID, *LANDFILL_COLUMNS, C_PROJECT_STATUS, C_PROJECT_TYPE)
OPERATIONAL = "Operational"

# Measure ids in config/metrics.yaml, each with the unit EPA publishes it in
WASTE = "lmop_waste_in_place"
WASTE_YEAR = "lmop_waste_in_place_year"
SYSTEM = "lmop_gas_system"
COLLECTED = "lmop_gas_collected"
FLARED = "lmop_gas_flared"
PROJECTS = "lmop_projects_running"
PROJECT_TYPES = "lmop_project_types"
UNITS = {
    WASTE: "short tons",
    WASTE_YEAR: "year",
    SYSTEM: "yes or no",
    COLLECTED: "million standard cubic feet a day",
    FLARED: "million standard cubic feet a day",
    PROJECTS: "count",
    PROJECT_TYPES: "list",
}


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, url: str) -> httpx.Response:
    r = client.get(url, timeout=120)
    r.raise_for_status()
    return r


def state_file(page: str, state: str = STATE) -> tuple[str, str]:
    """The state workbook's address and its edition (``YYYY-MM``), as EPA's page links it.

    The page must link exactly one edition of the file. Anything else stops the pull: the
    edition is the period every figure is published under, so it is never guessed.
    """
    pattern = rf'href="([^"]*/(\d{{4}}-\d{{2}})/lmopdata{state}\.xlsx)"'
    # The page links the file twice, once from its map and once from its list.
    found = sorted({(str(httpx.URL(PAGE).join(p)), ed) for p, ed in re.findall(pattern, page)})
    if len(found) != 1:
        raise ValueError(
            f"expected one edition of lmopdata{state}.xlsx on {PAGE}, found {len(found)}"
        )
    return found[0]


def read_workbook(content: bytes | Path) -> pd.DataFrame:
    """The ``LMOP Database`` sheet, checked for the columns the measures are read from."""
    source = io.BytesIO(content) if isinstance(content, bytes) else content
    table = pd.read_excel(source, sheet_name=SHEET)
    missing = [c for c in COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"EPA's workbook has no column {missing}; its layout has changed")
    return table


def pull(raw_root: Path) -> Path:
    """Download EPA's California workbook into its own raw folder.

    Everything is fetched and checked before the folder is made, so a failed pull leaves
    nothing behind.
    """
    manifest = PullManifest.start(SOURCE, PAGE, {"state": STATE.upper()})
    with httpx.Client(headers={"User-Agent": "methanewatch"}, follow_redirects=True) as client:
        url, edition = state_file(_get(client, PAGE).text)
        response = _get(client, url)
    table = read_workbook(response.content)
    manifest.params |= {
        "file_url": url,
        "edition": edition,
        "last_modified": response.headers.get("last-modified"),
    }
    pull_dir = raw_root / SOURCE / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    path = pull_dir / FILE
    path.write_bytes(response.content)
    manifest.finish(pull_dir, [path], n_records=len(table))
    return pull_dir


def finished_pulls(raw_root: Path) -> list[Path]:
    """Pull directories with a manifest, oldest first."""
    pulls = sorted((raw_root / SOURCE).glob(f"{SOURCE}-*"))
    return [p for p in pulls if (p / "manifest.json").exists()]


def pull_details(pull_dir: Path) -> dict:
    """The edition and file address a pull recorded."""
    return json.loads((pull_dir / "manifest.json").read_text())["params"]


def landfills(table: pd.DataFrame) -> pd.DataFrame:
    """One row per EPA landfill: its landfill-level columns, the number of energy projects
    EPA lists as operational, and their types.

    The landfill-level columns repeat on each of a landfill's rows. If they ever differ, the
    file no longer means what this step assumes, so it stops.
    """
    differing = table.groupby(C_ID)[list(LANDFILL_COLUMNS)].nunique(dropna=False)
    bad = sorted(differing.index[(differing > 1).any(axis=1)])
    if bad:
        raise ValueError(f"EPA landfills {bad} carry differing landfill figures on their rows")
    out = table.drop_duplicates(C_ID).set_index(C_ID)[list(LANDFILL_COLUMNS)].copy()
    running = table[table[C_PROJECT_STATUS] == OPERATIONAL]
    out["projects_running"] = running.groupby(C_ID).size().reindex(out.index, fill_value=0)
    known = running[running[C_PROJECT_TYPE].notna() & (running[C_PROJECT_TYPE] != "Unknown")]
    types = known.groupby(C_ID)[C_PROJECT_TYPE].agg(lambda s: ", ".join(sorted(set(s))))
    out["project_types"] = types.reindex(out.index)
    return out


def read_crosswalk(path: Path) -> pd.DataFrame:
    """The hand-kept match of registry sites to EPA landfills. One EPA landfill may belong to
    one site only."""
    xw = pd.read_csv(path, dtype={"site_id": str, "lmop_landfill_id": "Int64", "notes": str})
    xw["confirmed"] = xw["confirmed"].astype(str).str.lower() == "true"
    matched = xw.dropna(subset=["lmop_landfill_id"])
    repeated = sorted(matched.loc[matched["lmop_landfill_id"].duplicated(), "lmop_landfill_id"])
    if repeated:
        raise ValueError(f"EPA landfills {repeated} are matched to more than one site")
    return xw


def measures(
    table: pd.DataFrame, crosswalk: pd.DataFrame, *, edition: str, url: str, pull_id: str
) -> tuple[pd.DataFrame, list[int]]:
    """``site_metrics`` rows for every matched landfill, under the file's edition.

    A figure EPA leaves blank gives no row, which the pages read as "not listed", never as
    zero. The count of running projects is the one exception: a landfill EPA lists with no
    operational project has a true zero. A row is ``confirmed`` when its landfill's match is.

    Returns the rows and the EPA ids in the crosswalk that this edition no longer lists.
    """
    listed = landfills(table)
    matched = crosswalk.dropna(subset=["lmop_landfill_id"])
    gone = sorted(int(i) for i in matched["lmop_landfill_id"] if i not in listed.index)
    rows = []

    def add(match, metric_id: str, value=None, text=None) -> None:
        rows.append(
            {
                "site_id": match.site_id,
                "metric_id": metric_id,
                "period": edition,
                "source": SOURCE,
                "value": value,
                "value_text": text,
                "unit": UNITS[metric_id],
                "kind": "reported",
                "confirmed": bool(match.confirmed),
                "source_id": str(int(match.lmop_landfill_id)),
                "url": url,
                "pull_id": pull_id,
            }
        )

    for match in matched.itertuples():
        if match.lmop_landfill_id not in listed.index:
            continue
        lf = listed.loc[match.lmop_landfill_id]
        if pd.notna(lf[C_WASTE]):
            add(match, WASTE, float(lf[C_WASTE]))
            if pd.notna(lf[C_WASTE_YEAR]):
                add(match, WASTE_YEAR, float(lf[C_WASTE_YEAR]))
        if lf[C_SYSTEM] in ("Yes", "No"):
            add(match, SYSTEM, text=lf[C_SYSTEM])
        if pd.notna(lf[C_COLLECTED]):
            add(match, COLLECTED, float(lf[C_COLLECTED]))
        if pd.notna(lf[C_FLARED]):
            add(match, FLARED, float(lf[C_FLARED]))
        add(match, PROJECTS, float(lf["projects_running"]))
        if pd.notna(lf["project_types"]):
            add(match, PROJECT_TYPES, text=lf["project_types"])
    out = pd.DataFrame(rows, columns=[*schemas.site_metrics.columns, "pull_id"])
    return schemas.site_metrics.validate(out), gone
