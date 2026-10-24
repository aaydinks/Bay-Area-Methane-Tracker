"""Run the repair test over every documented repair (the remediation outcome).

For each row of ``data/registry/repairs.csv`` this calls ``verify_repair`` with
every other site as a control and adds the minimum detectable drop (MDE) for
that repair's own pass schedule:

1. Fit the persistence model to every site's "before" window to get typical
   parameters (posterior medians of f, mu, sigma).
2. Re-simulate detections on the real passes (same sites, instruments, times),
   cutting the treated site's emitting share by a factor after the repair date.
3. Run the same repair test on each simulation; the MDE is the mildest drop
   called in at least ``target`` of the fits.

An "inconclusive" outcome then reads as "a drop smaller than the MDE could not
have been seen", not "nothing changed". The outcomes are screening indications
for investigation; they say whether measured emissions fell after the dated
repair, never why.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.stats import truncnorm

from methanewatch import schemas
from methanewatch.config import (
    InstrumentsConfig,
    ModelConfig,
    PodCurve,
    ProjectConfig,
    RepairWindows,
    Sampler,
)
from methanewatch.model import persistence
from methanewatch.model.grid import LogRateGrid
from methanewatch.model.pod import pod
from methanewatch.repair.model import Repair, RepairResult, assign_periods, to_utc, verify_repair

POWER_FACTORS = (0.25, 0.5, 0.75)  # emitting share after / before: 75%, 50%, 25% drops
POWER_TARGET = 0.8


@dataclass(frozen=True)
class Settings:
    """Everything ``verify_repair`` needs besides the data."""

    grid: LogRateGrid
    curves: dict[str, PodCurve]
    release: dict[str, float]
    meas_sigma_log: dict[str, float]
    cfg: ModelConfig
    windows: RepairWindows
    sampler: Sampler
    allow_unconfirmed: bool = False

    def verify(self, det: pd.DataFrame, rep: Repair, controls: list[str], seed: int):
        return verify_repair(
            det,
            rep,
            controls,
            grid=self.grid,
            curves=self.curves,
            release=self.release,
            meas_sigma_log=self.meas_sigma_log,
            cfg=self.cfg,
            windows=self.windows,
            sampler=self.sampler,
            seed=seed,
            allow_unconfirmed=self.allow_unconfirmed,
        )


def load_repairs(table: pd.DataFrame) -> list[Repair]:
    """Validated registry rows as ``Repair`` objects."""
    df = schemas.repairs.validate(table)
    return [
        Repair(
            site_id=r.site_id,
            date_start=r.date_start.to_pydatetime(),
            date_end=None if pd.isna(r.date_end) else r.date_end.to_pydatetime(),
            repair_id=r.repair_id,
            date_confidence=r.date_confidence,
        )
        for r in df.itertuples()
    ]


def baseline_params(labelled: pd.DataFrame, settings: Settings, seed: int) -> pd.DataFrame:
    """Posterior medians of f, mu and sigma per site from the "before" window."""
    before = labelled[labelled["period"] == "before"]
    data = persistence.prepare(
        before,
        settings.grid,
        settings.curves,
        release=settings.release,
        meas_sigma_log=settings.meas_sigma_log,
        allow_unconfirmed=settings.allow_unconfirmed,
    )
    idata = persistence.fit(
        persistence.build_model(data, settings.cfg.priors), settings.sampler, seed=seed
    )
    f = np.median(persistence.posterior_draws(idata, "f"), axis=0)
    mu = np.median(persistence.posterior_draws(idata, "mu"), axis=0)
    sigma = float(np.median(persistence.posterior_draws(idata, "sigma")))
    return pd.DataFrame({"site_id": data.site_ids, "f": f, "mu": mu, "sigma": sigma})


def simulate_on_schedule(
    passes: pd.DataFrame,
    params: pd.DataFrame,
    settings: Settings,
    rng: np.random.Generator,
    *,
    treated: str | None = None,
    after: pd.Timestamp | None = None,
    factor: float = 1.0,
) -> pd.DataFrame:
    """New detections on the real passes; ``treated``'s f times ``factor`` from ``after``."""
    p = params.set_index("site_id").loc[passes["site_id"]]
    f = p["f"].to_numpy().copy()
    if treated is not None:
        cut = (passes["site_id"] == treated).to_numpy() & (
            passes["acquired_utc"] >= after
        ).to_numpy()
        f[cut] *= factor
    mu, sigma = p["mu"].to_numpy(), p["sigma"].to_numpy()
    lo, hi = settings.grid.x[0], settings.grid.x[-1]
    log_q = truncnorm.rvs(
        (lo - mu) / sigma, (hi - mu) / sigma, loc=mu, scale=sigma, random_state=rng
    )
    q = np.exp(log_q)
    inst = passes["instrument"]
    q50 = inst.map(lambda j: settings.curves[j].q50_kg_hr).to_numpy(float)
    w = inst.map(lambda j: settings.curves[j].w).to_numpy(float)
    rel = inst.map(settings.release).to_numpy(float)
    tau = inst.map(settings.meas_sigma_log).to_numpy(float)
    emitting = rng.random(len(passes)) < f
    detected = emitting & (rng.random(len(passes)) < rel * pod(q, q50, w))
    q_obs = np.where(detected, q * np.exp(rng.normal(0, tau)), np.nan)
    return passes[["overpass_id", "site_id", "instrument", "acquired_utc"]].assign(
        detected=detected,
        q_obs_kg_hr=q_obs,
        q_sigma_log=np.where(detected, tau, np.nan),
    )


def power_curve(
    passes: pd.DataFrame,
    repair: Repair,
    controls: list[str],
    params: pd.DataFrame,
    settings: Settings,
    rng: np.random.Generator,
    *,
    factors: Sequence[float] = POWER_FACTORS,
    n_fits: int = 15,
) -> pd.DataFrame:
    """Share of simulated fits called "drop" for each injected factor."""
    after = to_utc(repair.date_end or repair.date_start)
    rows = []
    for factor in factors:
        calls = []
        for _ in range(n_fits):
            sim = simulate_on_schedule(
                passes, params, settings, rng, treated=repair.site_id, after=after, factor=factor
            )
            res = settings.verify(sim, repair, controls, int(rng.integers(2**31)))
            calls.append(res.call)
        rows.append(
            {
                "factor": factor,
                "n_fits": n_fits,
                "p_drop": float(np.mean([c == "drop" for c in calls])),
                "n_insufficient": int(sum(c == "insufficient_data" for c in calls)),
            }
        )
    return pd.DataFrame(rows)


def mde_pct(power: pd.DataFrame, target: float = POWER_TARGET) -> float | None:
    """Mildest tested drop (in %) called in at least ``target`` of fits; None if none was."""
    ok = power[power["p_drop"] >= target]
    if ok.empty:
        return None
    return float(round((1 - ok["factor"].max()) * 100, 1))


def outcome_row(rep: Repair, res: RepairResult, mde: float | None, run_id: str) -> dict:
    d = asdict(res)
    d["controls"] = ";".join(d["controls"])
    return {
        **d,
        "date_start": pd.Timestamp(rep.date_start),
        "date_confidence": rep.date_confidence,
        "mde_pct": mde,
        "run_id": run_id,
    }


def run_all(
    repairs: list[Repair],
    detections: pd.DataFrame,
    settings: Settings,
    *,
    run_id: str,
    seed: int = 0,
    n_power_fits: int = 15,
    progress: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Outcomes (one row per repair) and the power curves behind each MDE."""
    rng = np.random.default_rng(seed)
    sites = sorted(detections["site_id"].unique())
    rows, curves = [], []
    for rep in repairs:
        controls = [s for s in sites if s != rep.site_id]
        res = settings.verify(detections, rep, controls, int(rng.integers(2**31)))
        mde = None
        if res.call != "insufficient_data":
            passes = assign_periods(
                detections[detections["site_id"].isin([rep.site_id, *controls])],
                rep,
                settings.windows,
            )
            params = baseline_params(passes, settings, int(rng.integers(2**31)))
            passes = passes[passes["site_id"].isin(params["site_id"])]
            curve = power_curve(passes, rep, controls, params, settings, rng, n_fits=n_power_fits)
            curves.append(curve.assign(repair_id=rep.repair_id))
            mde = mde_pct(curve)
        rows.append(outcome_row(rep, res, mde, run_id))
        if progress:
            print(f"{rep.repair_id}: {res.call}, MDE {mde}", flush=True)
    outcomes = schemas.repair_outcomes.validate(pd.DataFrame(rows))
    power = pd.concat(curves, ignore_index=True) if curves else pd.DataFrame()
    return outcomes, power


def run_real(
    project: ProjectConfig,
    cfg: ModelConfig,
    instruments: InstrumentsConfig,
    *,
    allow_unconfirmed: bool = False,
    n_power_fits: int = 15,
    seed: int = 0,
) -> str:
    """Outcomes for ``data/registry/repairs.csv`` on ``interim/detections.parquet``."""
    import json

    from methanewatch.model.run import ConfigNotReadyError
    from methanewatch.provenance import new_id, run_manifest

    registry = project.resolve(project.paths.registry)
    repairs = load_repairs(pd.read_csv(registry / "repairs.csv"))
    if not repairs:
        raise FileNotFoundError(
            f"no repairs in {registry / 'repairs.csv'}; every row needs a source"
        )
    det_path = project.resolve(project.paths.interim) / "detections.parquet"
    if not det_path.exists():
        raise FileNotFoundError(f"missing {det_path}; run `mw coverage build` first")
    det = pd.read_parquet(det_path)
    if cfg.grid.q_min_kg_hr is None:
        raise ConfigNotReadyError("set model.grid.q_min_kg_hr (the emission floor) first")
    used = sorted(det["instrument"].unique())
    inst = {k: instruments.instruments[k] for k in used}
    unset = [k for k, v in inst.items() if not v.pod.is_set or v.meas_sigma_log.value is None]
    if unset:
        raise ConfigNotReadyError(f"instrument settings missing for: {unset}")
    settings = Settings(
        grid=LogRateGrid.build(cfg.grid.q_min_kg_hr, cfg.grid.q_max_kg_hr, cfg.grid.n_points),
        curves={k: v.pod for k, v in inst.items()},
        release={k: v.release_prob.value for k, v in inst.items()},
        meas_sigma_log={k: v.meas_sigma_log.value for k, v in inst.items()},
        cfg=cfg,
        windows=project.repair,
        sampler=cfg.sampler,
        allow_unconfirmed=allow_unconfirmed,
    )
    run_id = new_id("repairs")
    outcomes, power = run_all(
        repairs, det, settings, run_id=run_id, seed=seed, n_power_fits=n_power_fits
    )
    out = project.resolve(project.paths.processed) / "repair_outcomes"
    out.mkdir(parents=True, exist_ok=True)
    outcomes.to_parquet(out / f"{run_id}.parquet")
    if len(power):
        power.to_parquet(out / f"{run_id}-power.parquet")
    provisional = bool(instruments.unconfirmed(used))
    manifest = run_manifest(
        run_id,
        extra={
            "kind": "repair_outcomes",
            "provisional": provisional,
            "unconfirmed_pod": instruments.unconfirmed(used),
            "n_repairs": len(repairs),
            "n_power_fits": n_power_fits,
            "power_factors": list(POWER_FACTORS),
            "power_target": POWER_TARGET,
        },
    )
    (out / f"{run_id}.json").write_text(json.dumps(manifest, indent=2, default=str))
    return run_id


def latest_outcomes(project: ProjectConfig) -> pd.DataFrame | None:
    """The newest outcome table, or None when no repair run exists yet."""
    out = project.resolve(project.paths.processed) / "repair_outcomes"
    runs = sorted(p for p in out.glob("repairs-*.parquet") if not p.stem.endswith("-power"))
    return pd.read_parquet(runs[-1]) if runs else None
