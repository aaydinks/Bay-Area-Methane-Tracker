"""Gate 3: synthetic recovery (docs/PLAN.md section 8.1).

Each replicate draws hyperparameters and site parameters from the model's
priors, simulates overpasses with the SYNTHETIC instrument settings, fits the
model, and records whether each site's 90% interval contains the truth for
f, Qbar and E. Pass when pooled coverage of every quantity is inside the
target band and few fits fail diagnostics.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch import features
from methanewatch.config import ModelConfig, SyntheticConfig, load_model, load_synthetic
from methanewatch.model import persistence, simulate
from methanewatch.model.grid import LogRateGrid
from methanewatch.model.summarize import quantiles
from methanewatch.provenance import new_id, run_manifest

QUANTITIES = {"f": "f", "qbar": "qbar", "E_t_yr": "E_t_yr"}
MAX_DIAGNOSTIC_FAILURE_SHARE = 0.10


@dataclass(frozen=True)
class GateResult:
    passed: bool
    coverage: dict[str, float]
    coverage_ci: dict[str, tuple[float, float]]
    n_fits: int
    n_site_fits: int
    diagnostic_failure_share: float


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return (float(centre - half), float(centre + half))


def model_grid(syn: SyntheticConfig, cfg: ModelConfig) -> LogRateGrid:
    return LogRateGrid.build(syn.q_min_kg_hr, syn.q_max_kg_hr, cfg.grid.n_points)


def fit_replicate(
    sites: pd.DataFrame,
    syn: SyntheticConfig,
    cfg: ModelConfig,
    rng: np.random.Generator,
    seed: int,
    covariates: Sequence[str] = (),
) -> pd.DataFrame:
    """Simulate, fit and score one replicate; one row per site."""
    schedule = simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng)
    det = simulate.simulate_detections(sites, schedule, syn, rng)
    data = persistence.prepare(
        det,
        model_grid(syn, cfg),
        {k: v.pod for k, v in syn.instruments.items()},
        release={k: v.release_prob for k, v in syn.instruments.items()},
        meas_sigma_log={k: v.meas_sigma_log for k, v in syn.instruments.items()},
    )
    cov = features.design_synthetic(sites, covariates) if covariates else None
    model = persistence.build_model(data, cfg.priors, cov, beta_sd=cfg.covariates.beta_sd)
    sampler = cfg.covariates.sampler(syn.sampler, active=bool(covariates))
    idata = persistence.fit(model, sampler, seed=seed)
    diag = persistence.diagnostics(idata, cfg)

    truth = sites.set_index("site_id").loc[data.site_ids]
    out = pd.DataFrame(
        {
            "site_id": data.site_ids,
            "n_overpasses": data.n_overpasses.sum(axis=1),
            "n_detections": data.n_overpasses.sum(axis=1) - data.n_nondetect.sum(axis=1),
            "diag_ok": diag.ok,
            "rhat_max": diag.rhat_max,
            "ess_bulk_min": diag.ess_bulk_min,
            "divergences": diag.divergences,
        }
    )
    for name in QUANTITIES:
        med, lo, hi = quantiles(persistence.posterior_draws(idata, name), cfg.interval_mass)
        true = truth[name].to_numpy()
        out[f"{name}_true"], out[f"{name}_med"] = true, med
        out[f"{name}_lo"], out[f"{name}_hi"] = lo, hi
        out[f"{name}_covered"] = (lo <= true) & (true <= hi)
    return out


def run(
    n_replicates: int,
    *,
    seed: int | None = None,
    progress: bool = True,
    covariates: Sequence[str] = (),
) -> pd.DataFrame:
    cfg, syn = load_model(), load_synthetic()
    rng = np.random.default_rng(syn.sampler.seed if seed is None else seed)
    frames = []
    t0 = time.time()
    for r in range(n_replicates):
        sites, hyper = simulate.sites_from_prior(
            syn.n_sites,
            cfg.priors,
            syn,
            rng,
            covariates=covariates,
            beta_sd=cfg.covariates.beta_sd,
        )
        res = fit_replicate(
            sites, syn, cfg, rng, seed=int(rng.integers(2**31)), covariates=covariates
        )
        frames.append(res.assign(replicate=r, **{f"hyper_{k}": v for k, v in hyper.items()}))
        if progress:
            cov = pd.concat(frames)["E_t_yr_covered"].mean()
            print(
                f"replicate {r + 1}/{n_replicates}  E coverage so far {cov:.3f}  "
                f"elapsed {time.time() - t0:.0f}s",
                flush=True,
            )
    return pd.concat(frames, ignore_index=True)


def run_scenarios(n_replicates: int, *, seed: int = 1) -> pd.DataFrame:
    """Fixed-truth cases (reported, not gated)."""
    cfg, syn = load_model(), load_synthetic()
    rng = np.random.default_rng(seed)
    sites = simulate.sites_from_scenarios(syn)
    frames = [
        fit_replicate(sites, syn, cfg, rng, seed=int(rng.integers(2**31))).assign(replicate=r)
        for r in range(n_replicates)
    ]
    return pd.concat(frames, ignore_index=True)


def evaluate(results: pd.DataFrame, syn: SyntheticConfig) -> GateResult:
    lo, hi = syn.coverage_target
    coverage, ci = {}, {}
    for name in QUANTITIES:
        k, n = int(results[f"{name}_covered"].sum()), len(results)
        coverage[name], ci[name] = k / n, wilson(k, n)
    fits = results.drop_duplicates("replicate")
    fail_share = float((~fits["diag_ok"]).mean())
    passed = all(lo <= c <= hi for c in coverage.values()) and (
        fail_share <= MAX_DIAGNOSTIC_FAILURE_SHARE
    )
    return GateResult(passed, coverage, ci, len(fits), len(results), fail_share)


def write_report(
    results: pd.DataFrame,
    scenarios: pd.DataFrame | None,
    gate: GateResult,
    out_dir: Path,
    run_id: str,
    covariates: Sequence[str] = (),
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    syn, cfg = load_synthetic(), load_model()
    out_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_dir / f"{run_id}.csv", index=False)
    if scenarios is not None:
        scenarios.to_csv(out_dir / f"{run_id}-scenarios.csv", index=False)

    # Coverage by number of detections at the site
    edges, labels = [-1, 0, 4, 14, np.inf], ["0", "1-4", "5-14", "15+"]
    bins = pd.cut(results["n_detections"], edges, labels=labels)
    by_det = results.groupby(bins, observed=True).agg(
        sites=("site_id", "size"),
        f=("f_covered", "mean"),
        qbar=("qbar_covered", "mean"),
        E=("E_t_yr_covered", "mean"),
    )

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    names = list(QUANTITIES)
    covs = [gate.coverage[n] for n in names]
    errs = np.array(
        [
            [c - gate.coverage_ci[n][0], gate.coverage_ci[n][1] - c]
            for n, c in zip(names, covs, strict=True)
        ]
    ).T
    ax = axes[0]
    ax.axhspan(*syn.coverage_target, color="0.9", label="target band")
    ax.axhline(cfg.interval_mass, color="0.5", lw=0.8, ls="--")
    ax.errorbar(names, covs, yerr=errs, fmt="o", color="C0", capsize=4)
    ax.set_ylim(0.6, 1.0)
    ax.set_ylabel("share of 90% intervals containing the truth")
    ax.set_title("Pooled coverage (95% Wilson interval)")
    ax.legend(loc="lower right", frameon=False)

    ax = axes[1]
    sample = results.sample(min(300, len(results)), random_state=0)
    ok = sample["E_t_yr_covered"]
    for mask, color, label in [(ok, "C0", "covered"), (~ok, "C3", "missed")]:
        s = sample[mask]
        ax.errorbar(
            s["E_t_yr_true"],
            s["E_t_yr_med"],
            yerr=[s["E_t_yr_med"] - s["E_t_yr_lo"], s["E_t_yr_hi"] - s["E_t_yr_med"]],
            fmt="o",
            ms=2.5,
            lw=0.6,
            color=color,
            alpha=0.6,
            label=label,
        )
    lims = [
        max(1e-1, sample[["E_t_yr_lo", "E_t_yr_true"]].min().min()),
        sample[["E_t_yr_hi", "E_t_yr_true"]].max().max(),
    ]
    ax.plot(lims, lims, color="0.4", lw=0.8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("true E (t/yr)")
    ax.set_ylabel("posterior median and 90% interval (t/yr)")
    ax.set_title("Annual emissions: estimate vs truth")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig_path = out_dir / f"{run_id}.png"
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)

    band = syn.coverage_target
    manifest = run_manifest(
        run_id,
        extra={"n_replicates": gate.n_fits, "gate": asdict(gate), "covariates": list(covariates)},
    )
    lines = [
        f"# Gate 3: synthetic recovery ({run_id})",
        "",
        f"**Result: {'PASS' if gate.passed else 'FAIL'}**. Target: pooled coverage of 90% "
        f"intervals in [{band[0]:.2f}, {band[1]:.2f}] for f, Qbar and E, and at most "
        f"{MAX_DIAGNOSTIC_FAILURE_SHARE:.0%} of fits failing diagnostics.",
        "",
        f"{gate.n_fits} replicates x {syn.n_sites} sites = {gate.n_site_fits} site fits. "
        "Truths drawn from the model's priors; instrument settings from "
        "`config/synthetic.yaml` (SYNTHETIC, not measured values).",
        "",
        f"Site covariates: {', '.join(covariates)} (made-up values; coefficients drawn from "
        f"their Normal(0, {cfg.covariates.beta_sd}) prior, ADR 0008)."
        if covariates
        else "Site covariates: none.",
        "",
        "| Quantity | Coverage | 95% Wilson interval |",
        "|---|---|---|",
        *[
            f"| {n} | {gate.coverage[n]:.3f} | "
            f"{gate.coverage_ci[n][0]:.3f} to {gate.coverage_ci[n][1]:.3f} |"
            for n in names
        ],
        "",
        f"Fits failing diagnostics (r-hat > {cfg.diagnostics.rhat_max}, bulk ESS < "
        f"{cfg.diagnostics.ess_bulk_min}, or divergences): {gate.diagnostic_failure_share:.1%}.",
        "",
        "## Coverage by detections at the site",
        "",
        by_det.to_markdown(floatfmt=".3f"),
        "",
        f"![coverage]({fig_path.name})",
        "",
    ]
    if scenarios is not None:
        sc = scenarios.groupby("site_id").agg(
            replicates=("replicate", "nunique"),
            E_true=("E_t_yr_true", "first"),
            E_median_of_medians=("E_t_yr_med", "median"),
            E_coverage=("E_t_yr_covered", "mean"),
            f_coverage=("f_covered", "mean"),
            mean_detections=("n_detections", "mean"),
        )
        lines += [
            "## Fixed-truth scenarios (reported, not gated)",
            "",
            sc.to_markdown(floatfmt=".3g"),
            "",
        ]
    manifest_json = json.dumps(manifest, indent=2, default=str)
    lines += ["## Run manifest", "", "```json", manifest_json, "```", ""]
    report = out_dir / f"{run_id}.md"
    report.write_text("\n".join(lines))
    return report


def gate(
    n_replicates: int,
    out_root: Path,
    *,
    n_scenario_replicates: int = 0,
    covariates: Sequence[str] = (),
) -> GateResult:
    run_id = new_id("synthetic")
    results = run(n_replicates, covariates=covariates)
    scenarios = run_scenarios(n_scenario_replicates) if n_scenario_replicates else None
    result = evaluate(results, load_synthetic())
    report = write_report(
        results, scenarios, result, out_root / "synthetic", run_id, covariates=covariates
    )
    print(f"wrote {report}")
    return result
