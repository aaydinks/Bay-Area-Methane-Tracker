"""Gate 3: synthetic recovery (docs/PLAN.md section 8.1).

Each replicate draws hyperparameters and site parameters from the model's
priors, simulates overpasses with the SYNTHETIC instrument settings, fits the
model, and records whether each site's 90% interval contains the truth for
f, Qbar and E. Pass when pooled coverage of every quantity is inside the
target band and few fits fail diagnostics.

At scale (ADR 0023) the simulated sites take the shape of a real fit instead of the
ten sites in ``config/synthetic.yaml``: as many sites, in the same regions, each with
the number of passes the real table has for it, and the model carries the region
term. The instrument settings stay the SYNTHETIC ones. Coverage is then also read
region by region, and each region must be inside the band.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch import features
from methanewatch.config import ModelConfig, Sampler, SyntheticConfig, load_model, load_synthetic
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
    # At scale: coverage of each quantity within each region, and the site fits behind it
    coverage_by_region: dict[str, dict[str, float]] = field(default_factory=dict)
    n_site_fits_by_region: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Layout:
    """The shape of a real fit without its data.

    How many sites, which region each is in, and how many passes each instrument made over
    each one. Site ids are made up (``synth-00`` ...), so a report names no landfill.
    """

    sites: pd.DataFrame  # site_id, region, and one yes/no column per region term
    schedule: pd.DataFrame  # site_id, instrument, n_overpasses
    source: str  # where the counts come from, in words, for the report

    @property
    def covariates(self) -> tuple[str, ...]:
        return tuple(c for c in self.sites.columns if c in features.REGION_TERMS)


def layout_from_detections(det: pd.DataFrame, region_of: pd.Series, source: str) -> Layout:
    """The layout of the fit these detections would get: their sites, regions and pass counts.

    ``det`` is a ``schemas.detections`` table already cut down to the sites and instruments of
    the fit; ``region_of`` gives each site's region. Only the counts are kept.
    """
    real_ids = sorted(det["site_id"].unique())
    regions = region_of.reindex(real_ids)
    missing = sorted(regions.index[regions.isna() | (regions == "")])
    if missing:
        raise ValueError(f"no region for: {missing}")
    order = sorted(real_ids, key=lambda s: (regions[s], s))
    width = max(2, len(str(len(order) - 1)))
    new_id = {s: f"synth-{i:0{width}d}" for i, s in enumerate(order)}
    sites = pd.DataFrame({"site_id": [new_id[s] for s in order], "region": regions[order].tolist()})
    for term in features.region_terms(sites["region"].tolist()):
        sites[term] = sites["region"] == features.REGION_TERMS[term]
    counts = det.groupby(["site_id", "instrument"]).size().rename("n_overpasses").reset_index()
    counts["site_id"] = counts["site_id"].map(new_id)
    schedule = counts.sort_values(["site_id", "instrument"]).reset_index(drop=True)
    return Layout(sites, schedule, source)


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
    schedule: pd.DataFrame | None = None,
    sampler: Sampler | None = None,
) -> pd.DataFrame:
    """Simulate, fit and score one replicate; one row per site.

    ``schedule`` fixes the passes per site and instrument; without it they are drawn from the
    rates in ``config/synthetic.yaml``. ``sampler`` replaces that file's shorter chains.
    """
    if schedule is None:
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
    sampler = cfg.covariates.sampler(sampler or syn.sampler, active=bool(covariates))
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
    if "region" in truth:
        out.insert(1, "region", truth["region"].to_numpy())
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
    layout: Layout | None = None,
) -> pd.DataFrame:
    """Fit ``n_replicates`` simulated worlds.

    With ``layout``, each has that layout's sites, regions and passes, the region terms are the
    covariates, and the chains are as long as a real fit's (``config/model.yaml``): the test
    stands in for that fit, and there are few enough fits to afford it.
    """
    cfg, syn = load_model(), load_synthetic()
    if layout is not None:
        if covariates:
            raise ValueError("a layout brings its own region terms; give no other covariates")
        unknown = sorted(set(layout.schedule["instrument"]) - set(syn.instruments))
        if unknown:
            raise ValueError(f"no SYNTHETIC settings for: {unknown} (config/synthetic.yaml)")
        covariates = layout.covariates
    n_sites = syn.n_sites if layout is None else len(layout.sites)
    rng = np.random.default_rng(syn.sampler.seed if seed is None else seed)
    frames = []
    t0 = time.time()
    for r in range(n_replicates):
        sites, hyper = simulate.sites_from_prior(
            n_sites,
            cfg.priors,
            syn,
            rng,
            covariates=covariates,
            beta_sd=cfg.covariates.beta_sd,
            columns=None if layout is None else layout.sites,
        )
        if layout is not None:
            sites = sites.assign(site_id=layout.sites["site_id"], region=layout.sites["region"])
        res = fit_replicate(
            sites,
            syn,
            cfg,
            rng,
            seed=int(rng.integers(2**31)),
            covariates=covariates,
            schedule=None if layout is None else layout.schedule,
            sampler=None if layout is None else cfg.sampler,
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
    by_region: dict[str, dict[str, float]] = {}
    n_by_region: dict[str, int] = {}
    if "region" in results:
        for region, part in results.groupby("region"):
            by_region[region] = {n: float(part[f"{n}_covered"].mean()) for n in QUANTITIES}
            n_by_region[region] = len(part)
    every = [*coverage.values(), *(c for part in by_region.values() for c in part.values())]
    passed = all(lo <= c <= hi for c in every) and fail_share <= MAX_DIAGNOSTIC_FAILURE_SHARE
    return GateResult(
        passed, coverage, ci, len(fits), len(results), fail_share, by_region, n_by_region
    )


def write_report(
    results: pd.DataFrame,
    scenarios: pd.DataFrame | None,
    gate: GateResult,
    out_dir: Path,
    run_id: str,
    covariates: Sequence[str] = (),
    layout: Layout | None = None,
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
    n_sites = gate.n_site_fits // gate.n_fits
    extra = {"n_replicates": gate.n_fits, "gate": asdict(gate), "covariates": list(covariates)}
    shape: list[str] = []
    if layout is not None:
        per_site = (
            layout.schedule.merge(layout.sites[["site_id", "region"]], on="site_id")
            .pivot_table(
                index="region",
                columns="instrument",
                values="n_overpasses",
                aggfunc="sum",
                fill_value=0,
            )
            .div(layout.sites.groupby("region").size(), axis=0)
        )
        totals = layout.schedule.groupby("site_id")["n_overpasses"].sum()
        by_site = layout.sites.assign(passes=layout.sites["site_id"].map(totals))
        spread = by_site.groupby("region")["passes"].agg(sites="size", fewest="min", most="max")
        extra["layout"] = {
            "source": layout.source,
            "sites_by_region": {k: int(v) for k, v in spread["sites"].items()},
            "mean_passes_per_site": {
                region: {k: round(float(v), 2) for k, v in row.items()}
                for region, row in per_site.iterrows()
            },
        }
        shape = [
            "## The shape of the simulated sites",
            "",
            f"Sites, regions and pass counts are those of a real fit: {layout.source}. Only the "
            "counts are used; every rate, detection and truth is simulated, and the site ids are "
            "made up.",
            "",
            "Mean passes per site, by instrument:",
            "",
            per_site.to_markdown(floatfmt=".2f"),
            "",
            "Sites, and the fewest and most passes at one site:",
            "",
            spread.to_markdown(),
            "",
            "## Coverage by region",
            "",
            "Each region must be inside the band as well.",
            "",
            "| Region | Site fits | f | qbar | E_t_yr |",
            "|---|---|---|---|---|",
            *[
                f"| {region} | {gate.n_site_fits_by_region[region]} | "
                + " | ".join(f"{part[n]:.3f}" for n in names)
                + " |"
                for region, part in gate.coverage_by_region.items()
            ],
            "",
        ]
    manifest = run_manifest(run_id, extra=extra)
    title = "Gate 3 at the real site count" if layout is not None else "Gate 3: synthetic recovery"
    lines = [
        f"# {title} ({run_id})",
        "",
        f"**Result: {'PASS' if gate.passed else 'FAIL'}**. Target: pooled coverage of 90% "
        f"intervals in [{band[0]:.2f}, {band[1]:.2f}] for f, Qbar and E, and at most "
        f"{MAX_DIAGNOSTIC_FAILURE_SHARE:.0%} of fits failing diagnostics.",
        "",
        f"{gate.n_fits} replicates x {n_sites} sites = {gate.n_site_fits} site fits. "
        "Truths drawn from the model's priors; instrument settings from "
        "`config/synthetic.yaml` (SYNTHETIC, not measured values)."
        + (" Chains as long as a real fit's (`config/model.yaml`)." if layout is not None else ""),
        "",
        f"Site covariates: {', '.join(covariates)} "
        f"({'each site in its real region' if layout is not None else 'made-up values'}; "
        f"coefficients drawn from their Normal(0, {cfg.covariates.beta_sd}) prior, ADR 0008)."
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
        *shape,
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
    layout: Layout | None = None,
) -> GateResult:
    """Run the test and write its report under ``out_root``: ``synthetic/`` for the ten made-up
    sites, ``synthetic-scale/`` with a ``layout``."""
    run_id = new_id("synthetic")
    results = run(n_replicates, covariates=covariates, layout=layout)
    scenarios = run_scenarios(n_scenario_replicates) if n_scenario_replicates else None
    result = evaluate(results, load_synthetic())
    if layout is not None:
        covariates = layout.covariates
    folder = "synthetic" if layout is None else "synthetic-scale"
    report = write_report(results, scenarios, result, out_root / folder, run_id, covariates, layout)
    print(f"wrote {report}")
    return result
