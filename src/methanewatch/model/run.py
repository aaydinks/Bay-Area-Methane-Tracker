"""Fit the persistence model and write a run (docs/PLAN.md sections 6 and 13).

A run writes, under ``data/processed``:
- ``site_estimates/<run_id>.parquet``: one row per site (schemas.site_estimates)
- ``runs/<run_id>.json``: run manifest (code, config, diagnostics, kind)
- ``runs/<run_id>-detections.parquet``: the detections the fit used
- ``runs/<run_id>.zarr``: posterior draws

``kind`` is ``real`` for fits to ingested data and ``synthetic-demo`` for the
labelled demo used to preview the dashboard before real data exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch.config import (
    InstrumentsConfig,
    ModelConfig,
    ProjectConfig,
    load_synthetic,
)
from methanewatch.model import persistence, simulate
from methanewatch.model.grid import LogRateGrid
from methanewatch.model.summarize import summarize
from methanewatch.provenance import new_id, run_manifest


class ConfigNotReadyError(ValueError):
    pass


def _write_run(
    project: ProjectConfig,
    run_id: str,
    detections: pd.DataFrame,
    data: persistence.ModelData,
    idata,
    estimates: pd.DataFrame,
    diag: persistence.Diagnostics,
    extra: dict,
) -> Path:
    processed = project.resolve(project.paths.processed)
    (processed / "site_estimates").mkdir(parents=True, exist_ok=True)
    runs = processed / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    estimates.to_parquet(processed / "site_estimates" / f"{run_id}.parquet")
    detections.to_parquet(runs / f"{run_id}-detections.parquet")
    idata.to_zarr(runs / f"{run_id}.zarr", mode="w")
    manifest = run_manifest(
        run_id,
        extra={
            "sites": data.site_ids,
            "instruments": data.instruments,
            "n_overpasses": int(data.n_overpasses.sum()),
            "n_detections": int(data.n_overpasses.sum() - data.n_nondetect.sum()),
            "diagnostics": diag.__dict__,
            **extra,
        },
    )
    path = runs / f"{run_id}.json"
    path.write_text(json.dumps(manifest, indent=2, default=str))
    return path


def fit_real(
    project: ProjectConfig,
    cfg: ModelConfig,
    instruments: InstrumentsConfig,
    *,
    allow_unconfirmed: bool = False,
) -> str:
    """Fit ``interim/detections.parquet`` with the real instrument settings."""
    path = project.resolve(project.paths.interim) / "detections.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run `mw coverage build` first")
    det = pd.read_parquet(path)
    if cfg.grid.q_min_kg_hr is None:
        raise ConfigNotReadyError("set model.grid.q_min_kg_hr (the emission floor) first")
    used = sorted(det["instrument"].unique())
    inst = {k: instruments.instruments[k] for k in used}
    unset = [k for k, v in inst.items() if not v.pod.is_set or v.meas_sigma_log.value is None]
    if unset:
        raise ConfigNotReadyError(f"instrument settings missing for: {unset}")

    grid = LogRateGrid.build(cfg.grid.q_min_kg_hr, cfg.grid.q_max_kg_hr, cfg.grid.n_points)
    data = persistence.prepare(
        det,
        grid,
        {k: v.pod for k, v in inst.items()},
        release={k: v.release_prob.value for k, v in inst.items()},
        meas_sigma_log={k: v.meas_sigma_log.value for k, v in inst.items()},
        allow_unconfirmed=allow_unconfirmed,
    )
    run_id = new_id("fit")
    idata = persistence.fit(persistence.build_model(data, cfg.priors), cfg.sampler)
    diag = persistence.diagnostics(idata, cfg)
    provisional = bool(instruments.unconfirmed(used))
    est = summarize(idata, data, diag, cfg, run_id=run_id, provisional=provisional)
    _write_run(
        project,
        run_id,
        det,
        data,
        idata,
        est,
        diag,
        {
            "kind": "real",
            "provisional": provisional,
            "unconfirmed_pod": instruments.unconfirmed(used),
        },
    )
    return run_id


def fit_synthetic_demo(project: ProjectConfig, cfg: ModelConfig, seed: int = 11) -> str:
    """Simulate and fit SYNTHETIC sites so the dashboard can be previewed. Never real data."""
    syn = load_synthetic()
    rng = np.random.default_rng(seed)
    sites, _ = simulate.sites_from_prior(syn.n_sites - 3, cfg.priors, syn, rng)
    sites = pd.concat([simulate.sites_from_scenarios(syn), sites], ignore_index=True)
    sites["site_id"] = "synthetic-" + sites["site_id"].str.replace("synth-", "", regex=False)
    schedule = simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng)
    det = simulate.simulate_detections(sites, schedule, syn, rng)
    grid = LogRateGrid.build(syn.q_min_kg_hr, syn.q_max_kg_hr, cfg.grid.n_points)
    data = persistence.prepare(
        det,
        grid,
        {k: v.pod for k, v in syn.instruments.items()},
        release={k: v.release_prob for k, v in syn.instruments.items()},
        meas_sigma_log={k: v.meas_sigma_log for k, v in syn.instruments.items()},
    )
    run_id = new_id("demo")
    idata = persistence.fit(persistence.build_model(data, cfg.priors), syn.sampler, seed=seed)
    diag = persistence.diagnostics(idata, cfg)
    est = summarize(idata, data, diag, cfg, run_id=run_id)
    truth = sites.set_index("site_id")["E_t_yr"].to_dict()
    _write_run(
        project,
        run_id,
        det,
        data,
        idata,
        est,
        diag,
        {"kind": "synthetic-demo", "provisional": True, "truth_E_t_yr": truth},
    )
    return run_id
