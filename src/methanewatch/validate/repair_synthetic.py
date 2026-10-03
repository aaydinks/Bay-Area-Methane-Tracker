"""Dry run of the repair test on synthetic data: placebo false-positive rate and power.

This is NOT Gate 5. Gate 5 runs placebos on the real overpass schedules once
they exist. The synthetic dry run shows whether the method is calibrated and how
large a drop it can see with schedules like the ones in config/synthetic.yaml.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch.config import (
    SyntheticConfig,
    load_model,
    load_project,
    load_synthetic,
)
from methanewatch.model import simulate
from methanewatch.provenance import new_id, run_manifest
from methanewatch.repair import placebo
from methanewatch.repair.model import Repair, RepairResult, verify_repair
from methanewatch.validate.synthetic import model_grid

REPAIR_YEARS = 3.0  # two 12-month windows plus the gap need more than 2 years of data
TREATED = "typical"


def repair_world(syn: SyntheticConfig) -> SyntheticConfig:
    return syn.model_copy(update={"years": REPAIR_YEARS})


def make_verifier(syn: SyntheticConfig):
    cfg, project = load_model(), load_project()
    grid = model_grid(syn, cfg)
    curves = {k: v.pod for k, v in syn.instruments.items()}
    release = {k: v.release_prob for k, v in syn.instruments.items()}
    tau = {k: v.meas_sigma_log for k, v in syn.instruments.items()}

    def verify(det: pd.DataFrame, rep: Repair, controls: list[str], seed: int) -> RepairResult:
        return verify_repair(
            det,
            rep,
            controls,
            grid=grid,
            curves=curves,
            release=release,
            meas_sigma_log=tau,
            cfg=cfg,
            windows=project.repair,
            sampler=syn.sampler,
            seed=seed,
        )

    return verify


def control_sites(syn: SyntheticConfig, n: int, rng: np.random.Generator) -> pd.DataFrame:
    sites, _ = simulate.sites_from_prior(n, load_model().priors, syn, rng)
    return sites


def with_drop(
    sites: pd.DataFrame,
    syn: SyntheticConfig,
    rng: np.random.Generator,
    treated: str,
    date: pd.Timestamp,
    factor: float,
) -> pd.DataFrame:
    """Simulate the full span twice and splice: f at ``treated`` times ``factor`` after ``date``."""
    schedule = simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng)
    before = simulate.simulate_detections(sites, schedule, syn, rng)
    changed = sites.copy()
    changed.loc[changed["site_id"] == treated, "f"] *= factor
    after = simulate.simulate_detections(changed, schedule, syn, rng)
    is_t_b = before["site_id"] == treated
    is_t_a = after["site_id"] == treated
    keep = pd.concat(
        [
            before[~is_t_b],
            before[is_t_b & (before["acquired_utc"] < date)],
            after[is_t_a & (after["acquired_utc"] >= date)],
        ]
    )
    return keep.reset_index(drop=True)


def run(
    n_worlds: int,
    placebos_per_world: int,
    n_power: int,
    factors: tuple[float, ...],
    seed: int = 3,
) -> Path:
    syn = repair_world(load_synthetic())
    windows = load_project().repair
    rng = np.random.default_rng(seed)
    verify = make_verifier(syn)

    # Placebo: independent worlds where nothing changes, a few pseudo-repairs in each
    frames = []
    for w in range(n_worlds):
        sites = control_sites(syn, syn.n_sites, rng)
        schedule = simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng)
        det = simulate.simulate_detections(sites, schedule, syn, rng)
        pl = placebo.run_placebos(
            det, sites["site_id"].tolist(), placebos_per_world, verify, windows, rng
        )
        frames.append(pl.assign(world=w))
        done = pd.concat(frames)
        hits = done["call"].isin(["drop", "rise"]).sum()
        print(f"world {w + 1}/{n_worlds}  false positives so far {hits}/{len(done)}", flush=True)
    placebos = pd.concat(frames, ignore_index=True)
    fpr = placebo.false_positive_rate(placebos, block="world")
    print("placebo", fpr, flush=True)

    # Power: one "typical" site with a known drop, the rest as controls; a new world per fit
    date = simulate.START + timedelta(days=REPAIR_YEARS * 365.25 / 2)
    rows = []
    for factor in factors:
        for i in range(n_power):
            ctrl = control_sites(syn, syn.n_sites - 1, rng)
            world = pd.concat(
                [simulate.sites_from_scenarios(syn, [TREATED]), ctrl], ignore_index=True
            )
            det = with_drop(world, syn, rng, TREATED, pd.Timestamp(date), factor)
            rep = Repair(site_id=TREATED, date_start=date, repair_id=f"power-{factor}-{i}")
            res = verify(det, rep, ctrl["site_id"].tolist(), int(rng.integers(2**31)))
            rows.append({**res.__dict__, "factor": factor, "true_effect": float(np.log(factor))})
        print("power", factor, flush=True)
    power = pd.DataFrame(rows)
    return write_report(placebos, fpr, power, syn, windows.call_probability)


def minimum_detectable(summary: pd.DataFrame, target: float = 0.8) -> str:
    """Mildest injected drop detected in at least ``target`` of fits."""
    ok = summary[summary["p_drop"] >= target]
    if ok.empty:
        mildest = summary.index.min()
        return (
            f"none of the tested drops reached {target:.0%} power; even a "
            f"{1 - mildest:.0%} drop was called in {summary.loc[mildest, 'p_drop']:.0%} of fits"
        )
    factor = ok.index.max()
    share = ok.loc[factor, "p_drop"]
    return f"a {1 - factor:.0%} drop (factor {factor:g}) is called in {share:.0%} of fits"


def write_report(
    placebos: pd.DataFrame,
    fpr: dict,
    power: pd.DataFrame,
    syn: SyntheticConfig,
    call_probability: float,
) -> Path:
    project = load_project()
    run_id = new_id("repair-synthetic")
    out = project.resolve(project.paths.reports) / "validation" / "repair-synthetic"
    out.mkdir(parents=True, exist_ok=True)
    placebos.drop(columns=["controls"]).to_csv(out / f"{run_id}-placebo.csv", index=False)
    power.drop(columns=["controls"]).to_csv(out / f"{run_id}-power.csv", index=False)

    usable = power[power["call"] != "insufficient_data"]
    summary = usable.groupby("factor").agg(
        fits=("call", "size"),
        p_drop=("call", lambda c: (c == "drop").mean()),
        p_rise=("call", lambda c: (c == "rise").mean()),
        p_decrease_median=("p_decrease", "median"),
        effect_median=("effect_med", "median"),
        true_effect=("true_effect", "first"),
        covered=("effect_lo", "size"),
    )
    cover = (
        usable.assign(
            c=(usable["effect_lo"] <= usable["true_effect"])
            & (usable["true_effect"] <= usable["effect_hi"])
        )
        .groupby("factor")["c"]
        .mean()
    )
    summary["covered"] = cover
    calls = placebos["call"].value_counts().to_dict()
    mde = minimum_detectable(summary)
    manifest = run_manifest(
        run_id,
        extra={"fpr": fpr, "years": syn.years, "call_probability": call_probability},
    )
    lines = [
        f"# Repair test on synthetic data ({run_id})",
        "",
        "Dry run, not Gate 5. Gate 5 runs placebos on the real overpass schedules. "
        "Instrument settings come from `config/synthetic.yaml` (SYNTHETIC), over "
        f"{syn.years:g} years of simulated overpasses.",
        "",
        f"Call rule: drop if P(decrease) >= {call_probability}, rise if P(decrease) <= "
        f"{1 - call_probability:.3f} (two-sided, nominal false-positive rate "
        f"{2 * (1 - call_probability):.0%}); intervals reported at 90%. See ADR 0006.",
        "",
        f"**Minimum detectable effect (80% power):** {mde}.",
        "",
        "## Placebo false-positive rate",
        "",
        f"Pseudo-repairs at sites where nothing changed, in {fpr['n_blocks']} independent "
        f"simulated worlds: {fpr['n_usable']} usable fits, {fpr['n_insufficient']} "
        f"insufficient. Calls: {calls}.",
        "",
        f"- False-positive rate (drop or rise): **{fpr['fpr']:.3f}**",
        f"- 95% Wilson interval: {fpr['wilson_lo']:.3f} to {fpr['wilson_hi']:.3f} "
        "(optimistic: pseudo-dates at the same sites overlap)",
        f"- Bootstrap over worlds: {fpr['bootstrap_lo']:.3f} to {fpr['bootstrap_hi']:.3f}",
        "- Gate 5 threshold: 0.10",
        "",
        "## Power: injected drops at one site",
        "",
        "The treated site is the `typical` scenario (f = 0.3, Qbar = 500 kg/hr); "
        "its emitting fraction is multiplied by the factor after the repair date.",
        "",
        summary.to_markdown(floatfmt=".3f"),
        "",
        "`p_drop` is the share of fits calling a drop; `covered` is the share whose 90% "
        "interval for the log effect contains the injected log(factor).",
        "",
        "## Run manifest",
        "",
        "```json",
        json.dumps(manifest, indent=2, default=str),
        "```",
        "",
    ]
    path = out / f"{run_id}.md"
    path.write_text("\n".join(lines))
    print(f"wrote {path}")
    return path
