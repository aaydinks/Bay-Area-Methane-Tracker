"""Gate 4 and the matched-pairs report: wiring the tests to data and writing reports.

- Hold-out prediction: real detections (``interim/detections.parquet``) or a
  SYNTHETIC dry run.
- Operator comparison: one model run's estimates against GHGRP figures.
- Matched pairs: Sentinel-2 against the reference instruments.

Every report goes to ``reports/validation/<name>/<run_id>.md`` with a run manifest.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch.config import (
    ProjectConfig,
    load_instruments,
    load_model,
    load_synthetic,
)
from methanewatch.model import simulate
from methanewatch.model.grid import LogRateGrid
from methanewatch.provenance import new_id, run_manifest
from methanewatch.validate import holdout, matched_pairs, operator


def _write(out_root: Path, name: str, run_id: str, lines: list[str], extra: dict) -> Path:
    out = out_root / name
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.dumps(run_manifest(run_id, extra=extra), indent=2, default=str)
    path = out / f"{run_id}.md"
    path.write_text("\n".join([*lines, "", "## Run manifest", "", "```json", manifest, "```", ""]))
    return path


def _holdout_report(
    results: pd.DataFrame,
    res: holdout.HoldoutResult,
    title: str,
    note: str,
    out_root: Path,
    run_id: str,
    extra: dict,
) -> Path:
    (out_root / "holdout").mkdir(parents=True, exist_ok=True)
    results.to_csv(out_root / "holdout" / f"{run_id}.csv", index=False)
    calib = (
        results.assign(
            bin=pd.cut(
                results["pred_mean"],
                [-0.01, 0.5, 2, 5, 10, np.inf],
                labels=["<0.5", "0.5-2", "2-5", "5-10", "10+"],
            )
        )
        .groupby("bin", observed=True)
        .agg(
            site_folds=("site_id", "size"),
            predicted=("pred_mean", "sum"),
            observed=("observed", "sum"),
        )
    )
    lines = [
        f"# {title} ({run_id})",
        "",
        f"**Result: {'PASS' if res.passed else 'FAIL'}**. Observed held-out detections fall inside "
        f"the 90% predictive interval for **{res.share_inside:.1%}** of {res.n_site_folds} "
        f"site-folds (target at least {res.target:.0%}).",
        "",
        note,
        "",
        "## Calibration: predicted vs observed detections",
        "",
        calib.to_markdown(floatfmt=".1f"),
        "",
        f"Fits failing diagnostics: {(~results.drop_duplicates('fold')['diag_ok']).sum()} "
        f"of {results['fold'].nunique()}.",
    ]
    return _write(out_root, "holdout", run_id, lines, {"holdout": asdict(res), **extra})


def holdout_synthetic(out_root: Path, n_folds: int = 5, seed: int = 21) -> holdout.HoldoutResult:
    """Dry run on SYNTHETIC sites drawn from the priors."""
    cfg, syn = load_model(), load_synthetic()
    rng = np.random.default_rng(seed)
    sites, _ = simulate.sites_from_prior(syn.n_sites, cfg.priors, syn, rng)
    det = simulate.simulate_detections(
        sites, simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng), syn, rng
    )
    results = holdout.run(
        det,
        grid=LogRateGrid.build(syn.q_min_kg_hr, syn.q_max_kg_hr, cfg.grid.n_points),
        curves={k: v.pod for k, v in syn.instruments.items()},
        release={k: v.release_prob for k, v in syn.instruments.items()},
        meas_sigma_log={k: v.meas_sigma_log for k, v in syn.instruments.items()},
        cfg=cfg,
        sampler=syn.sampler,
        n_folds=n_folds,
        rng=rng,
    )
    res = holdout.evaluate(results)
    run_id = new_id("holdout-synthetic")
    path = _holdout_report(
        results,
        res,
        "Hold-out prediction, SYNTHETIC dry run",
        "Dry run, not Gate 4: simulated sites drawn from the priors, instrument settings from "
        "`config/synthetic.yaml`. Gate 4 runs on real detections.",
        out_root,
        run_id,
        {"kind": "synthetic", "n_folds": n_folds},
    )
    print(f"wrote {path}")
    return res


def holdout_real(
    project: ProjectConfig, out_root: Path, n_folds: int = 5, *, allow_unconfirmed: bool = False
) -> holdout.HoldoutResult:
    from methanewatch.model.run import ConfigNotReadyError

    cfg, instruments = load_model(), load_instruments()
    path = project.resolve(project.paths.interim) / "detections.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run `mw coverage build` first")
    det = pd.read_parquet(path)
    if cfg.grid.q_min_kg_hr is None:
        raise ConfigNotReadyError("set model.grid.q_min_kg_hr (the emission floor) first")
    inst = {k: instruments.instruments[k] for k in sorted(det["instrument"].unique())}
    results = holdout.run(
        det,
        grid=LogRateGrid.build(cfg.grid.q_min_kg_hr, cfg.grid.q_max_kg_hr, cfg.grid.n_points),
        curves={k: v.pod for k, v in inst.items()},
        release={k: v.release_prob.value for k, v in inst.items()},
        meas_sigma_log={k: v.meas_sigma_log.value for k, v in inst.items()},
        cfg=cfg,
        sampler=cfg.sampler,
        n_folds=n_folds,
        rng=np.random.default_rng(cfg.sampler.seed),
        allow_unconfirmed=allow_unconfirmed,
    )
    res = holdout.evaluate(results)
    run_id = new_id("holdout")
    note = "Real detections." + (
        " Unconfirmed detection curves: PROVISIONAL." if allow_unconfirmed else ""
    )
    path = _holdout_report(
        results, res, "Hold-out prediction", note, out_root, run_id, {"kind": "real"}
    )
    print(f"wrote {path}")
    return res


def operator_report(project: ProjectConfig, out_root: Path, run_id: str) -> operator.OperatorResult:
    processed = project.resolve(project.paths.processed)
    est = pd.read_parquet(processed / "site_estimates" / f"{run_id}.parquet")
    det = pd.read_parquet(processed / "runs" / f"{run_id}-detections.parquet")
    rep_path = project.resolve(project.paths.interim) / "operator_reports.parquet"
    if not rep_path.exists():
        raise FileNotFoundError(f"missing {rep_path}; run `mw ingest ghgrp` first")
    t = pd.to_datetime(det["acquired_utc"], utc=True)
    table = operator.compare(est, pd.read_parquet(rep_path), (t.min().year, t.max().year))
    notes_path = project.resolve(project.paths.registry) / operator.GAP_NOTES
    notes = pd.read_csv(notes_path) if notes_path.exists() else None
    res = operator.evaluate(table, notes)

    report_id = new_id("operator")
    (out_root / "operator").mkdir(parents=True, exist_ok=True)
    table.to_csv(out_root / "operator" / f"{report_id}.csv", index=False)
    lines = [
        f"# Operator comparison ({report_id}, model run {run_id})",
        "",
        f"**Result: {'PASS' if res.passed else 'FAIL'}**. {res.n_compared} site-years compared, "
        f"{res.n_gaps} outside the model's 90% interval; every gap needs a written explanation "
        f"in `data/registry/{operator.GAP_NOTES}`.",
        "",
        *[f"- undocumented gap: {u}" for u in res.undocumented],
        "",
        "Standing caveats for every row:",
        *[f"- {c}" for c in operator.STANDING_CAVEATS],
        "",
        table.to_markdown(index=False, floatfmt=".3g")
        if len(table)
        else "_No overlapping site-years._",
    ]
    path = _write(
        out_root, "operator", report_id, lines, {"model_run": run_id, "operator": asdict(res)}
    )
    print(f"wrote {path}")
    return res


def matched_pairs_report(project: ProjectConfig, out_root: Path, max_days: float = 1.0) -> Path:
    path = project.resolve(project.paths.interim) / "detections.parquet"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}; run `mw coverage build` first")
    pairs = matched_pairs.pair(pd.read_parquet(path), max_days=max_days)
    summary = matched_pairs.summarize(pairs)
    report_id = new_id("matched-pairs")
    lines = [
        f"# Sentinel-2 matched pairs ({report_id})",
        "",
        f"{len(pairs)} Sentinel-2 overpasses paired with a reference overpass within "
        f"{max_days:g} day(s). No pass threshold; this measures what Sentinel-2 can see.",
        "",
        summary.to_markdown(index=False, floatfmt=".3f"),
    ]
    out = _write(
        out_root, "matched-pairs", report_id, lines, {"n_pairs": len(pairs), "max_days": max_days}
    )
    print(f"wrote {out}")
    return out
