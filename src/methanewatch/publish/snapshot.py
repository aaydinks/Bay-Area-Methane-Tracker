"""Assemble one publication from the pipeline's outputs.

A snapshot is everything the website needs for one run: sites, passes, plumes, estimates,
checks and their labelled results, operator figures, residents nearby, the method checks and
the run manifests. It is written to ``data/processed/publications/<publish_id>/`` as Parquet
tables plus ``manifest.json``, validated against ``publish.schemas`` and the wording check.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from methanewatch.config import DataTermsConfig, ImpactConfig, ProjectConfig
from methanewatch.provenance import git_dirty, git_sha, new_id, utcnow
from methanewatch.publish import schemas as pub
from methanewatch.publish.labels import label_result
from methanewatch.publish.validation import validation_rows
from methanewatch.report.lint import check_text


class SimulatedRunError(ValueError):
    """A synthetic run was offered for publication without ``allow_simulated``."""


class WordingError(ValueError):
    """A text field contains a banned phrase."""


@dataclass
class Snapshot:
    publication: dict[str, Any]
    runs: list[dict[str, Any]]
    data_terms: list[dict[str, Any]]
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)

    @property
    def publish_id(self) -> str:
        return self.publication["publish_id"]

    def write(self, root: Path) -> Path:
        out = root / self.publish_id
        out.mkdir(parents=True, exist_ok=True)
        for name, df in self.tables.items():
            df.to_parquet(out / f"{name}.parquet", index=False)
        (out / "manifest.json").write_text(
            json.dumps(
                {
                    "publication": self.publication,
                    "runs": self.runs,
                    "data_terms": self.data_terms,
                    "tables": {k: len(v) for k, v in self.tables.items()},
                },
                indent=2,
                default=str,
            )
        )
        return out

    @classmethod
    def read(cls, folder: Path) -> Snapshot:
        manifest = json.loads((folder / "manifest.json").read_text())
        tables = {
            name: pd.read_parquet(folder / f"{name}.parquet")
            for name in manifest["tables"]
            if (folder / f"{name}.parquet").exists()
        }
        return cls(manifest["publication"], manifest["runs"], manifest["data_terms"], tables)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _none(x: Any) -> Any:
    """NaN and pandas NA as None, for manifests and labels."""
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x


def _day(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts, utc=True).dt.strftime("%Y-%m-%d")


def _pass_detections(ov: pd.DataFrame, det: pd.DataFrame) -> pd.DataFrame:
    """``detected``, ``q_obs_kg_hr`` and ``n_plumes`` for every overpass; nothing seen if absent."""
    cols = ["detected", "q_obs_kg_hr", "n_plumes"]
    d = det.set_index("overpass_id") if len(det) else pd.DataFrame(columns=cols)
    d = d.reindex(index=ov["overpass_id"], columns=cols)
    return pd.DataFrame(
        {
            "detected": d["detected"].eq(True).to_numpy(),
            "q_obs_kg_hr": pd.to_numeric(d["q_obs_kg_hr"]).to_numpy(dtype=float),
            "n_plumes": pd.to_numeric(d["n_plumes"]).fillna(0).astype(int).to_numpy(),
        },
        index=ov.index,
    )


def _emit_complexes(project: ProjectConfig, interim: Path, sites) -> pd.DataFrame | None:
    """NASA's own EMIT plume complexes as attributed plume rows, or None if there are none.

    The complex metadata has an outline but no rate, so the origin is the outline's centroid
    and the rate stays empty. Attribution uses the coverage step's rule and inputs.
    """
    import geopandas as gpd

    from methanewatch.attribution import attribute_plumes

    path = interim / "emit_plume_outlines.parquet"
    if not path.exists():
        return None
    outlines = gpd.read_parquet(path).reset_index(drop=True)
    if outlines.empty:
        return None
    nb_path = interim / "neighbors.parquet"
    neighbors = gpd.read_parquet(nb_path) if nb_path.exists() else sites.iloc[0:0]
    centre = outlines.geometry.to_crs(project.crs_metric).centroid.to_crs("EPSG:4326")
    complexes = pd.DataFrame(
        {
            "plume_id": outlines["plume_id"],
            "source": "emit-v2",
            "instrument": "emit",
            "acquired_utc": pd.to_datetime(outlines["acquired_utc"], utc=True),
            "origin_lon": centre.x,
            "origin_lat": centre.y,
            "q_kg_hr": math.nan,
            "q_sigma_kg_hr": math.nan,
            "data_version": outlines["granule_ur"].str.extract(r"_CH4PLM_(\d+)_")[0],
        }
    )
    return attribute_plumes(
        complexes,
        sites,
        neighbors,
        buffer_m=project.attribution.buffer_m,
        search_radius_m=project.attribution.search_radius_km * 1000,
        metric_crs=project.crs_metric,
    )


def latest_refresh(interim: Path) -> dict | None:
    path = interim / "refresh" / "latest.json"
    return _read_json(path) if path.exists() else None


def check_wording(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Every banned phrase in a text column, as ``table.column[row]: phrase``."""
    problems = []
    for name, columns in pub.TEXT_COLUMNS.items():
        df = tables.get(name)
        if df is None:
            continue
        for col in columns:
            if col not in df.columns:
                continue
            for i, value in df[col].items():
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    continue
                for p in check_text(str(value), field=col):
                    problems.append(f"{name}.{col}[{i}]: {p}")
    return problems


def build(
    project: ProjectConfig,
    terms: DataTermsConfig,
    impact: ImpactConfig,
    *,
    model_run_id: str | None = None,
    check_run_id: str | None = None,
    refresh_id: str | None = None,
    reports_root: Path | None = None,
    allow_simulated: bool = False,
    publish_id: str | None = None,
    notes: str | None = None,
) -> Snapshot:
    """The snapshot for one run. Raises on a simulated run or a wording hit."""
    interim = project.resolve(project.paths.interim)
    processed = project.resolve(project.paths.processed)
    registry = project.resolve(project.paths.registry)
    reports_root = reports_root or project.resolve(project.paths.reports)
    restricted_instruments = set(terms.restricted_instruments())
    restricted_sources = set(terms.restricted_sources())

    # --- runs and flags -------------------------------------------------------------------
    runs: list[dict] = []
    simulated = False
    provisional = False
    refresh = (
        _read_json(interim / "refresh" / f"{refresh_id}.json")
        if refresh_id
        else latest_refresh(interim)
    )
    if refresh:
        refresh_id = refresh["run_id"]
        runs.append({"run_id": refresh_id, "kind": "refresh", "manifest": refresh})
    model_manifest = None
    if model_run_id:
        model_manifest = _read_json(processed / "runs" / f"{model_run_id}.json")
        simulated = model_manifest.get("kind") == "synthetic-demo"
        provisional = provisional or bool(model_manifest.get("provisional"))
        runs.append({"run_id": model_run_id, "kind": "model", "manifest": model_manifest})
    check_manifest = None
    if check_run_id:
        path = processed / "repair_outcomes" / f"{check_run_id}.json"
        check_manifest = _read_json(path) if path.exists() else {}
        provisional = provisional or bool(check_manifest.get("provisional"))
        runs.append({"run_id": check_run_id, "kind": "repair", "manifest": check_manifest})
    if simulated and not allow_simulated:
        raise SimulatedRunError(
            f"{model_run_id} is a simulated run; pass allow_simulated to publish it as a draft"
        )

    tables: dict[str, pd.DataFrame] = {}

    # --- sites and neighbours --------------------------------------------------------------
    import geopandas as gpd

    sites_path = interim / "sites.parquet"
    if not sites_path.exists():
        raise FileNotFoundError(f"missing {sites_path}; run `mw refresh` or `mw sites build` first")
    sites = gpd.read_parquet(sites_path)
    feats_path = interim / "site_features.parquet"
    feats = (
        pd.read_parquet(feats_path) if feats_path.exists() else pd.DataFrame(columns=["site_id"])
    )
    area = feats.set_index("site_id")["area_km2"] if "area_km2" in feats else pd.Series(dtype=float)
    tables["sites"] = pd.DataFrame(
        {
            "site_id": sites["site_id"],
            "name": sites["name"],
            "city": sites.get("city"),
            "county": sites.get("county"),
            "operator": sites.get("operator"),
            "tier": sites.get("tier"),
            "status": sites.get("status"),
            "swis_number": sites.get("swis_number"),
            "ghgrp_facility_id": sites.get("ghgrp_facility_id"),
            "outline_wkt": sites.geometry.to_wkt(),
            "polygon_source": sites.get("polygon_source"),
            "provisional": sites.get("polygon_source", pd.Series("", index=sites.index))
            .fillna("")
            .str.lower()
            .str.startswith("provisional"),
            "area_km2": sites["site_id"].map(area).astype(float),
        }
    ).replace({"": None})

    nb_path = interim / "neighbors.parquet"
    if nb_path.exists():
        nb = gpd.read_parquet(nb_path)
        nb = nb[nb.get("part", "neighbor") == "neighbor"] if len(nb) else nb
        tables["neighbours"] = pd.DataFrame(
            {
                "neighbour_id": [
                    f"{r.site_id}:neighbour:{i}" for i, r in enumerate(nb.itertuples())
                ],
                "name": nb.get("source", pd.Series(dtype=str))
                .fillna("neighbouring source")
                .to_numpy(),
                "kind": "other",
                "geom_wkt": nb.geometry.to_wkt().to_numpy(),
                "nearest_site_id": nb["site_id"].to_numpy(),
                "distance_m": None,
                "source": nb.get("source", pd.Series(dtype=str)).to_numpy(),
            }
        )
    else:
        tables["neighbours"] = pd.DataFrame(columns=list(pub.neighbours.columns)).astype(
            {"distance_m": float}
        )

    # --- passes --------------------------------------------------------------------------
    from methanewatch.coverage.overpasses import build_detections

    ov = pd.read_parquet(interim / "overpasses.parquet")
    det_path = interim / "detections.parquet"
    det = pd.read_parquet(det_path) if det_path.exists() else pd.DataFrame(columns=["overpass_id"])
    pl_path = interim / "plumes_attributed.parquet"
    pl = pd.read_parquet(pl_path) if pl_path.exists() else None
    # detections.parquet pools plumes from every source, so a pass by an open instrument can
    # carry a rate from Carbon Mapper's copy of the same plume. Those passes are counted again
    # from the plumes of unrestricted sources only, with the coverage step's own rule.
    pass_restricted = ov["instrument"].isin(restricted_instruments)
    recorded = _pass_detections(ov, det)
    open_only = _pass_detections(
        ov,
        build_detections(ov, pl[~pl["source"].isin(restricted_sources)])[0]
        if pl is not None
        else pd.DataFrame(),
    )
    seen = {c: recorded[c].where(pass_restricted, open_only[c]) for c in recorded.columns}
    tables["passes"] = pd.DataFrame(
        {
            "overpass_id": ov["overpass_id"],
            "site_id": ov["site_id"],
            "instrument": ov["instrument"],
            "acquired_utc": pd.to_datetime(ov["acquired_utc"], utc=True),
            "usable": ov["usable"],
            "coverage_frac": ov["coverage_frac"],
            "valid_frac": ov["valid_frac"],
            "coverage_source": ov["coverage_source"],
            "detected": seen["detected"],
            "q_obs_kg_hr": seen["q_obs_kg_hr"],
            "n_plumes": seen["n_plumes"],
            "restricted": pass_restricted,
        }
    )

    # --- plumes --------------------------------------------------------------------------
    # NASA's complexes are listed here only; they have no rate, so they never mark a pass.
    frames = [f for f in (pl, _emit_complexes(project, interim, sites)) if f is not None]
    if frames:
        pl = pd.concat(frames, ignore_index=True)
        key = pl["site_id"].fillna("") + ":" + pl["instrument"] + ":" + _day(pl["acquired_utc"])
        known = set(ov["overpass_id"])
        tables["plumes"] = pd.DataFrame(
            {
                "plume_id": pl["plume_id"],
                "source": pl["source"],
                "instrument": pl["instrument"],
                "acquired_utc": pd.to_datetime(pl["acquired_utc"], utc=True),
                "lon": pl["origin_lon"],
                "lat": pl["origin_lat"],
                "q_kg_hr": pl["q_kg_hr"],
                "q_sigma_kg_hr": pl["q_sigma_kg_hr"],
                "site_id": pl["site_id"],
                "attribution": pl["attribution"],
                "distance_m": pl["distance_m"],
                "data_version": pl.get("data_version"),
                "overpass_id": key.where(key.isin(known)),
                "restricted": pl["source"].isin(restricted_sources),
                "new_in_update": False,
            }
        )
    else:
        tables["plumes"] = pd.DataFrame(columns=list(pub.plumes.columns))

    # Estimates and check results use every pass, so they are restricted whenever a restricted
    # instrument contributed, until that source's terms are confirmed.
    derived_restricted = bool(set(ov["instrument"]) & restricted_instruments)

    # --- estimates -----------------------------------------------------------------------
    if model_run_id:
        est = pd.read_parquet(processed / "site_estimates" / f"{model_run_id}.parquet")
        est = est.rename(
            columns={"E_t_yr_med": "e_t_yr_med", "E_t_yr_lo": "e_t_yr_lo", "E_t_yr_hi": "e_t_yr_hi"}
        )
        insufficient = est["status"] == "insufficient_data"
        tables["site_estimates"] = est.assign(
            model_run_id=model_run_id,
            period=est.get("period", "all"),
            insufficient_reason=insufficient.map(
                {True: "too few usable passes or a fit that failed its diagnostics", False: None}
            ),
            provisional=bool(model_manifest and model_manifest.get("provisional")),
            restricted=derived_restricted,
        )[list(pub.site_estimates.columns)]
    else:
        tables["site_estimates"] = pd.DataFrame(columns=list(pub.site_estimates.columns))

    # --- checks and results --------------------------------------------------------------
    checks_path = registry / "checks.csv"
    if checks_path.exists():
        ck = pd.read_csv(checks_path, dtype=str)
        if "entered_on" not in ck:
            ck["entered_on"] = None
        tables["checks"] = ck
    else:
        tables["checks"] = pd.DataFrame(columns=list(pub.checks.columns))
    if check_run_id:
        oc = pd.read_parquet(processed / "repair_outcomes" / f"{check_run_id}.parquet")
        labelled = [
            label_result({k: _none(v) for k, v in r.items()}, project.checks.severity)
            for r in oc.to_dict("records")
        ]
        tables["check_results"] = (
            pd.concat([oc.reset_index(drop=True), pd.DataFrame(labelled)], axis=1)
            .rename(
                columns={
                    "repair_id": "check_id",
                    "dE_t_yr_med": "de_t_yr_med",
                    "dE_t_yr_lo": "de_t_yr_lo",
                    "dE_t_yr_hi": "de_t_yr_hi",
                }
            )
            .assign(
                check_run_id=check_run_id,
                provisional=bool(check_manifest and check_manifest.get("provisional")),
                restricted=derived_restricted,
            )[list(pub.check_results.columns)]
        )
    else:
        tables["check_results"] = pd.DataFrame(columns=list(pub.check_results.columns))

    # --- operator reports, residents, features -------------------------------------------
    op_path = interim / "operator_reports.parquet"
    if op_path.exists():
        op = pd.read_parquet(op_path)
        tables["operator_reports"] = op.assign(gwp_confirmed=impact.ghgrp_gwp_ch4.confirmed)[
            list(pub.operator_reports.columns)
        ]
    else:
        tables["operator_reports"] = pd.DataFrame(columns=list(pub.operator_reports.columns))
    pop_path = interim / "population.csv"
    tables["population"] = (
        pd.read_csv(pop_path)[list(pub.population.columns)]
        if pop_path.exists()
        else pd.DataFrame(columns=list(pub.population.columns))
    )
    tables["site_features"] = (
        feats[list(pub.site_features.columns)]
        if len(feats) and "closed" in feats
        else pd.DataFrame(columns=list(pub.site_features.columns))
    )

    # --- method checks -------------------------------------------------------------------
    tables["validation_results"] = pd.DataFrame(
        validation_rows(reports_root), columns=list(pub.validation_results.columns)
    )
    tables["update_log"] = pd.DataFrame(columns=list(pub.update_log.columns))

    # --- validate, check wording ---------------------------------------------------------
    for name, schema in pub.TABLES.items():
        tables[name] = schema.validate(tables[name]) if len(tables[name]) else tables[name]
    problems = check_wording(tables)
    if problems:
        raise WordingError("wording check failed: " + "; ".join(problems))

    data_through = None
    if refresh and refresh.get("window", {}).get("end"):
        data_through = str(refresh["window"]["end"])
    elif len(tables["passes"]):
        data_through = tables["passes"]["acquired_utc"].max().strftime("%Y-%m-%d")

    publication = {
        "publish_id": publish_id or new_id("pub"),
        "created_at": utcnow().isoformat(),
        "visibility": "draft",
        "simulated": simulated,
        "provisional": provisional,
        "refresh_id": refresh_id,
        "model_run_id": model_run_id,
        "check_run_id": check_run_id,
        "data_through": data_through,
        "source_lag_days": project.publish.source_lag_days,
        "git_sha": git_sha(),
        "git_dirty": git_dirty(),
        "notes": notes,
    }
    data_terms = [
        {
            "source": name,
            "display_name": t.display_name,
            "raw_publishable": t.raw_publishable,
            "derived_publishable": t.derived_publishable,
            "confirmed": t.confirmed,
            "checked_on": str(t.checked_on) if t.checked_on else None,
            "terms_url": t.terms_url,
            "credit_line": t.credit_line,
        }
        for name, t in terms.sources.items()
    ]
    return Snapshot(publication, runs, data_terms, tables)
