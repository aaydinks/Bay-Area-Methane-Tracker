"""Fit the persistence model and write a run (docs/PLAN.md sections 6 and 13).

A run writes, under ``data/processed``:
- ``site_estimates/<run_id>.parquet``: one row per site (schemas.site_estimates)
- ``runs/<run_id>.json``: run manifest (code, config, diagnostics, kind, and for a real
  fit the sites chosen and the instruments left out because their plume search has not run)
- ``runs/<run_id>-detections.parquet``: the detections the fit used
- ``runs/<run_id>.zarr``: posterior draws

``kind`` is ``real`` for fits to ingested data and ``synthetic-demo`` for the
labelled demo used to preview the dashboard before real data exists.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch import features
from methanewatch.config import (
    InstrumentsConfig,
    ModelConfig,
    ProjectConfig,
    load_synthetic,
)
from methanewatch.model import persistence, searched, simulate, siteselect
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


def select_searched(
    interim: Path,
    det: pd.DataFrame,
    instruments: InstrumentsConfig,
    include_unsearched: Iterable[str] = (),
) -> searched.Selection:
    """The detections a real fit may use: ``searched.select`` on the current plume tables.

    Every real fit (this module, ``mw repair run``, the hold-out check) goes through here, so
    all of them leave out the same instruments (ADR 0016). Prints what was left out or kept on
    purpose; raises ConfigNotReadyError for an unknown instrument or when nothing is left.
    """
    tables = searched.plume_tables(interim)  # read errors are not config problems
    try:
        sel = searched.select(det, instruments, tables, include_unsearched=include_unsearched)
    except ValueError as exc:
        raise ConfigNotReadyError(str(exc)) from exc
    if not sel.used:
        raise ConfigNotReadyError(
            "no instrument's passes have been searched for plumes: "
            + ", ".join(sorted(sel.left_out))
        )
    for name, why in sel.left_out.items():
        print(f"left out {name}: {why['reason']} ({why['n_passes']} usable passes)")
    for name in sel.included_unsearched:
        print(f"included {name} although its plume search has not run (--include-unsearched)")
    return sel


def select_sites(
    interim: Path,
    det: pd.DataFrame,
    sites: Iterable[str] = (),
    tiers: Iterable[str] = (),
) -> siteselect.SiteSelection:
    """The detections of the sites a real fit covers: ``siteselect.select`` on the registry.

    ``mw model fit`` and ``mw repair run`` both go through here. With no choice, every site
    is taken while they are all of one tier; a registry of several tiers needs ``sites`` or
    ``tiers``. Prints an explicit choice; raises ConfigNotReadyError when it cannot be met.
    """
    try:
        chosen = siteselect.select(det, siteselect.site_tiers(interim), sites=sites, tiers=tiers)
    except ValueError as exc:
        raise ConfigNotReadyError(str(exc)) from exc
    if chosen.explicit:
        asked = [f"tier {t}" for t in chosen.tiers] + [f"site {s}" for s in chosen.sites]
        print(
            f"sites: {len(chosen.site_ids)} chosen ({', '.join(asked)}); "
            f"{len(chosen.not_selected)} with detections left out"
        )
    return chosen


def fit_real(
    project: ProjectConfig,
    cfg: ModelConfig,
    instruments: InstrumentsConfig,
    *,
    allow_unconfirmed: bool = False,
    include_unsearched: Iterable[str] = (),
    sites: Iterable[str] = (),
    tiers: Iterable[str] = (),
    covariates: Iterable[str] | None = None,
) -> str:
    """Fit ``interim/detections.parquet`` with the real instrument settings.

    ``sites`` (ids) and ``tiers`` (registry tiers) choose the sites to fit; see
    ``model.siteselect``. Instruments whose plume search has not run are left out (see
    ``model.searched``), unless named in ``include_unsearched``. The manifest names the
    choice of sites, and what was left out and why.

    ``covariates`` replaces the list in ``config/model.yaml`` for this fit. A fit whose sites
    lie in several regions must carry the region term (ADR 0023) and stops without it.
    """
    interim = project.resolve(project.paths.interim)
    path = interim / "detections.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run `mw coverage build` first")
    det = pd.read_parquet(path)
    if cfg.grid.q_min_kg_hr is None:
        raise ConfigNotReadyError("set model.grid.q_min_kg_hr (the emission floor) first")
    chosen = select_sites(interim, det, sites, tiers)
    sel = select_searched(interim, chosen.detections, instruments, include_unsearched)
    det = sel.detections
    used = sel.used
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
    names = tuple(cfg.covariates.names) if covariates is None else tuple(covariates)
    region_of = siteselect.site_regions(interim)
    if region_of is not None:
        regions = [r for r in region_of.reindex(data.site_ids).dropna() if r]
        missing = [t for t in features.region_terms(regions) if t not in names]
        if missing:
            raise ConfigNotReadyError(
                f"the chosen sites lie in several regions ({', '.join(sorted(set(regions)))}); "
                "a fit that pools regions carries the region term, so add "
                + " ".join(f"--covariate {t}" for t in missing)
            )
    cov = None
    if names:
        feat_path = interim / "site_features.parquet"
        if not feat_path.exists():
            raise FileNotFoundError(f"missing {feat_path}; run `mw features build` first")
        table = features.with_regions(pd.read_parquet(feat_path), region_of)
        try:
            cov = features.design(table[table["site_id"].isin(data.site_ids)], names)
            cov.rows(data.site_ids)  # every fitted site needs its row
        except ValueError as exc:
            raise ConfigNotReadyError(str(exc)) from exc
    model = persistence.build_model(data, cfg.priors, cov, beta_sd=cfg.covariates.beta_sd)
    pooled = bool(set(names) & set(features.REGION_TERMS))
    sampler = cfg.covariates.sampler(cfg.sampler, active=cov is not None, pooled=pooled)
    idata = persistence.fit(model, sampler)
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
            "covariates": cov.manifest() if cov is not None else None,
            "sampler": sampler.model_dump(),
            **chosen.manifest(),
            **sel.manifest(),
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
