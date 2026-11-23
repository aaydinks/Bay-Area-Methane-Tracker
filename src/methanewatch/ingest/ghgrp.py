"""EPA GHGRP operator-reported figures: landfill methane (subpart HH, PLAN 5, phase 2e) and
every gas a matched facility reports (ADR 0019).

Source: EPA Envirofacts REST API (public, no key), tables
``pub_dim_facility`` and ``pub_facts_subp_ghg_emission``. Emissions are
published in t CO2e, so methane tonnes depend on the GWP EPA applied for the
reporting year (``config/impact.yaml: ghgrp_gwp_ch4``; unconfirmed until
checked against EPA's documentation). See docs/decisions/0007-public-sources.md.

The per-gas rows of ``normalize_gases`` are kept in t CO2e exactly as EPA publishes them, so
they need no conversion factor.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch import schemas
from methanewatch.provenance import PullManifest

BASE = "https://data.epa.gov/efservice"
# Codes from Envirofacts' own lookup tables (pub_dim_subpart, pub_dim_ghg), checked 2026-11-23
SUBPART_C = 1  # stationary combustion
SUBPART_HH = 31  # municipal landfills
GAS_CO2 = 1
GAS_CH4 = 2
GAS_N2O = 3
GAS_BIOGENIC_CO2 = 8

SOURCE = "ghgrp"  # the key of this source in config/data_terms.yaml
UNIT = "t CO2e"
# (subpart, gas) -> the measure in config/metrics.yaml that holds it
GAS_MEASURES = {
    (SUBPART_HH, GAS_CH4): "epa_landfill_ch4",
    (SUBPART_C, GAS_BIOGENIC_CO2): "epa_combustion_biogenic_co2",
    (SUBPART_C, GAS_CO2): "epa_combustion_co2",
    (SUBPART_C, GAS_CH4): "epa_combustion_ch4",
    (SUBPART_C, GAS_N2O): "epa_combustion_n2o",
}


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, path: str) -> list[dict]:
    r = client.get(f"{BASE}/{path}/JSON", timeout=120)
    r.raise_for_status()
    return r.json()


def facilities_in(
    counties: Iterable[str], year: int, client: httpx.Client | None = None
) -> pd.DataFrame:
    """Facilities in the named counties that reported subpart HH in ``year``. EPA writes a
    county with or without the word "County", so names are compared without it."""
    wanted = {c.upper().replace(" COUNTY", "").strip() for c in counties}
    with client or httpx.Client() as c:
        rows = _get(c, f"pub_dim_facility/state/=/CA/reported_subparts/CONTAINING/HH/year/=/{year}")
    df = pd.DataFrame(rows)
    county = df["county"].fillna("").str.upper().str.replace(" COUNTY", "", regex=False)
    keep = df[county.str.strip().isin(wanted)]
    return keep[["facility_id", "facility_name", "city", "county", "latitude", "longitude", "year"]]


def pull_reports(facility_ids: list[str], raw_root: Path) -> Path:
    """Download subpart HH methane rows for each facility into a raw pull directory."""
    manifest = PullManifest.start(
        "ghgrp", f"{BASE}/pub_facts_subp_ghg_emission", {"facility_ids": facility_ids}
    )
    pull_dir = raw_root / "ghgrp" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    files, n = [], 0
    with httpx.Client() as c:
        for fid in facility_ids:
            rows = _get(c, f"pub_facts_subp_ghg_emission/facility_id/=/{fid}")
            path = pull_dir / f"{fid}.json"
            path.write_text(json.dumps(rows, indent=1))
            files.append(path)
            n += len(rows)
    manifest.finish(pull_dir, files, n_records=n)
    return pull_dir


def _rows(pull_dir: Path, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Every downloaded row of a pull, with the ``site_id`` its facility is matched to."""
    files = [p for p in sorted(pull_dir.glob("*.json")) if p.name != "manifest.json"]
    rows = [r for p in files for r in json.loads(p.read_text())]
    df = pd.DataFrame(
        rows, columns=["facility_id", "sub_part_id", "co2e_emission", "gas_id", "year"]
    )
    xw = crosswalk.dropna(subset=["ghgrp_facility_id"]).astype({"ghgrp_facility_id": str})
    df["facility_id"] = df["facility_id"].astype(str)
    return df.merge(
        xw[["site_id", "ghgrp_facility_id"]], left_on="facility_id", right_on="ghgrp_facility_id"
    )


def normalize(
    pull_dir: Path, crosswalk: pd.DataFrame, gwp_by_year: dict[int, float]
) -> pd.DataFrame:
    """Rows for subpart HH methane, mapped to ``site_id`` via the crosswalk."""
    df = _rows(pull_dir, crosswalk)
    df = df[(df["sub_part_id"] == SUBPART_HH) & (df["gas_id"] == GAS_CH4)].copy()
    # Years without a configured GWP are left out rather than converted with a guess.
    df = df[df["year"].isin(gwp_by_year)]
    df["reported_co2e_t"] = df["co2e_emission"].astype(float)
    df["gwp_used"] = df["year"].map(gwp_by_year)
    df["reported_ch4_t"] = df["reported_co2e_t"] / df["gwp_used"]
    df["source"] = "GHGRP"
    df["url"] = BASE + "/pub_facts_subp_ghg_emission/facility_id/=/" + df["facility_id"]
    df["pull_id"] = pull_dir.name
    out = df[
        [
            "site_id",
            "year",
            "source",
            "reported_ch4_t",
            "reported_co2e_t",
            "gwp_used",
            "facility_id",
            "url",
            "pull_id",
        ]
    ]
    return schemas.operator_reports.validate(out.reset_index(drop=True))


def normalize_gases(pull_dir: Path, crosswalk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every gas each matched facility reported, as ``site_metrics`` rows (ADR 0019).

    One row per site, measure and year, in t CO2e exactly as EPA publishes it; nothing is
    converted. A year in which a facility filed no combustion report has no combustion rows,
    which the pages read as "not reported", never as zero.

    Returns the rows and a count of the downloaded rows left out because their subpart and
    gas have no measure in ``GAS_MEASURES``, so nothing is dropped without being reported.
    """
    df = _rows(pull_dir, crosswalk)
    key = list(zip(df["sub_part_id"], df["gas_id"], strict=True))
    df["metric_id"] = [GAS_MEASURES.get(k) for k in key]
    left_out = (
        df[df["metric_id"].isna()]
        .groupby(["sub_part_id", "gas_id"])
        .size()
        .rename("rows")
        .reset_index()
    )
    df = df[df["metric_id"].notna()]
    out = pd.DataFrame(
        {
            "site_id": df["site_id"],
            "metric_id": df["metric_id"],
            "period": df["year"].astype(int).astype(str),
            "source": SOURCE,
            "value": df["co2e_emission"].astype(float),
            "value_text": None,
            "unit": UNIT,
            "kind": "reported",
            # EPA's published figure for a facility matched by hand in the crosswalk
            "confirmed": True,
            "source_id": df["facility_id"],
            "url": BASE + "/pub_facts_subp_ghg_emission/facility_id/=/" + df["facility_id"],
            "pull_id": pull_dir.name,
        }
    ).sort_values(["site_id", "metric_id", "period"])
    return schemas.site_metrics.validate(out.reset_index(drop=True)), left_out
