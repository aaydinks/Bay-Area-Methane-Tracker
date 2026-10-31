"""Command-line entry point: ``mw <group> <command>``.

The Makefile and the end-to-end notebook call the same package functions.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import load_dotenv

from methanewatch import __version__, config

# API keys (Carbon Mapper, Census) live in the git-ignored .env at the repo root.
load_dotenv(config.REPO_ROOT / ".env")

app = typer.Typer(no_args_is_help=True, help="Bay Area Landfill Methane Watch pipeline.")
config_app = typer.Typer(no_args_is_help=True, help="Inspect configuration.")
sites_app = typer.Typer(no_args_is_help=True, help="Site registry (phase 1).")
ingest_app = typer.Typer(no_args_is_help=True, help="Raw data pulls (phase 2).")
coverage_app = typer.Typer(no_args_is_help=True, help="Overpasses table (phase 2c).")
s2_app = typer.Typer(no_args_is_help=True, help="Sentinel-2 retrieval (phase 3).")
model_app = typer.Typer(no_args_is_help=True, help="Persistence model (phase 5).")
repair_app = typer.Typer(no_args_is_help=True, help="Repair verification (phase 6).")
validate_app = typer.Typer(no_args_is_help=True, help="Validation tests and phase gates.")
report_app = typer.Typer(no_args_is_help=True, help="Dashboard and publications (phase 7).")
wind_app = typer.Typer(no_args_is_help=True, help="10 m wind for plume quantification (phase 4).")
population_app = typer.Typer(no_args_is_help=True, help="Residents near each site (context only).")
datasets_app = typer.Typer(no_args_is_help=True, help="Committed copy of each source dataset.")
features_app = typer.Typer(no_args_is_help=True, help="Site traits for model covariates.")
publish_app = typer.Typer(no_args_is_help=True, help="Publish one run to the website's database.")

for name, sub in [
    ("config", config_app),
    ("sites", sites_app),
    ("ingest", ingest_app),
    ("coverage", coverage_app),
    ("s2", s2_app),
    ("model", model_app),
    ("repair", repair_app),
    ("validate", validate_app),
    ("report", report_app),
    ("wind", wind_app),
    ("population", population_app),
    ("datasets", datasets_app),
    ("features", features_app),
    ("publish", publish_app),
]:
    app.add_typer(sub, name=name)

Site = Annotated[str, typer.Option(help="site_id from the registry, e.g. newby-island")]


def _run(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call a pipeline step; report unbuilt steps instead of printing a traceback."""
    try:
        return fn(*args, **kwargs)
    except NotImplementedError as exc:
        typer.secho(f"not implemented yet: {exc}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=2) from exc


def _run_or_exit(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Like _run, but missing inputs exit with a message instead of a traceback."""
    try:
        return _run(fn, *args, **kwargs)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


def _gate(passed: bool) -> None:
    raise typer.Exit(code=0 if passed else 1)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def refresh(
    end: Annotated[str | None, typer.Option(help="YYYY-MM-DD, default today")] = None,
    skip: Annotated[
        list[str] | None, typer.Option(help="Source to leave out: emit, sentinel2, carbonmapper")
    ] = None,
    csv: Annotated[bool, typer.Option(help="Also write CSV copies to data/interim/csv")] = True,
) -> None:
    """Pull every source again and rebuild the interim tables. Safe to repeat on a schedule.

    Exits 1 if any step failed; the tables then come from the earlier pulls on disk.
    """
    from methanewatch import refresh as refresh_mod

    project = config.load_project()
    try:
        manifest = refresh_mod.run(
            project,
            end=date.fromisoformat(end) if end else None,
            skip=skip or (),
            csv=csv,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for name, result in manifest["steps"].items():
        if not result["ok"]:
            typer.secho(f"{name}: FAILED {result['error']}", fg=typer.colors.RED, err=True)
            continue
        detail = {k: v for k, v in result.items() if k != "ok"}
        typer.echo(f"{name}: ok " + ", ".join(f"{k}={v}" for k, v in detail.items()))
    typer.echo(f"manifest: data/interim/refresh/{manifest['run_id']}.json")
    raise typer.Exit(code=0 if manifest["ok"] else 1)


@config_app.command("check")
def config_check() -> None:
    """Validate every config file and list constants that are still unconfirmed."""
    project = config.load_project()
    instruments = config.load_instruments()
    model = config.load_model()
    impact = config.load_impact()
    typer.echo(f"project:     ok (metric CRS {project.crs_metric})")
    typer.echo(f"instruments: ok ({', '.join(instruments.instruments)})")
    typer.echo(f"model:       ok (grid {model.grid.n_points} points)")
    typer.echo("impact:      ok")

    pending = [f"instruments.{n}.pod" for n in instruments.unconfirmed()]
    pending += [
        f"impact.{k}"
        for k in ("gwp20", "gwp100", "usd_per_t_co2e")
        if not getattr(impact, k).confirmed
    ]
    if model.grid.q_min_kg_hr is None:
        pending.append("model.grid.q_min_kg_hr (unset)")
    if pending:
        typer.secho("unconfirmed (outputs will be provisional):", fg=typer.colors.YELLOW)
        for p in pending:
            typer.echo(f"  - {p}")


@sites_app.command("build")
def sites_build() -> None:
    """Build data/interim/sites.parquet from data/registry and run QA checks."""
    from methanewatch.sites import registry

    project = config.load_project()
    registry_dir = project.resolve(project.paths.registry)
    missing = registry.missing_polygons(registry_dir)
    if missing:
        typer.secho(f"no boundary polygon yet: {', '.join(missing)}", fg=typer.colors.YELLOW)
    try:
        sites = registry.build_registry(
            registry_dir, project.resolve(project.paths.interim), metric_crs=project.crs_metric
        )
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"wrote {len(sites)} sites to data/interim/sites.parquet")


BBoxOpt = Annotated[
    str | None,
    typer.Option(help="minlon,minlat,maxlon,maxlat; defaults to site polygons plus search radius"),
]


@ingest_app.command("carbonmapper")
def ingest_carbonmapper(
    start: Annotated[str, typer.Option(help="YYYY-MM-DD")] = "2022-08-01",
    end: Annotated[str | None, typer.Option(help="YYYY-MM-DD, default today")] = None,
    bbox: BBoxOpt = None,
    offline: Annotated[
        bool, typer.Option(help="Rebuild the interim tables from the newest pull, no download")
    ] = False,
) -> None:
    """Carbon Mapper CH4 plumes (solid-waste and all sectors) and scene footprints."""
    from methanewatch.ingest import pipeline

    project = config.load_project()
    if offline:
        counts = pipeline.write_carbonmapper(project)
    else:
        stop = date.fromisoformat(end) if end else date.today()
        counts = pipeline.ingest_carbonmapper(
            project, _bbox(project, bbox), date.fromisoformat(start), stop
        )
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


def _bbox(project: config.ProjectConfig, bbox: str | None) -> tuple[float, float, float, float]:
    from methanewatch.ingest.pipeline import registry_bbox

    if bbox:
        parts = tuple(float(x) for x in bbox.split(","))
        if len(parts) != 4:
            raise typer.BadParameter("bbox needs four comma-separated numbers")
        return parts  # type: ignore[return-value]
    found = registry_bbox(project)
    if found is None:
        typer.secho("no site polygons yet; pass --bbox", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    return found


@ingest_app.command("emit")
def ingest_emit(
    start: Annotated[str, typer.Option(help="YYYY-MM-DD")] = "2022-08-01",
    end: Annotated[str | None, typer.Option(help="YYYY-MM-DD, default today")] = None,
    bbox: BBoxOpt = None,
) -> None:
    """EMIT v2 scene footprints and plume-complex outlines (CMR metadata, no login)."""
    from methanewatch.ingest import pipeline

    project = config.load_project()
    stop = date.fromisoformat(end) if end else date.today()
    counts = pipeline.ingest_emit(project, _bbox(project, bbox), date.fromisoformat(start), stop)
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@ingest_app.command("calrecycle")
def ingest_calrecycle() -> None:
    """CalRecycle SWIS sites with a landfill activity in the nine counties (about 2 minutes)."""
    from methanewatch.ingest import calrecycle

    project = config.load_project()
    typer.echo(f"wrote {calrecycle.pull(project.resolve(project.paths.raw))}")


@ingest_app.command("boundaries")
def ingest_boundaries() -> None:
    """Census 2025 counties, places, tracts, roads and water, and CARB's Bay Area district
    outline (as of 2004; check against current BAAQMD)."""
    from methanewatch.ingest import boundaries

    project = config.load_project()
    typer.echo(f"wrote {boundaries.pull(project.resolve(project.paths.raw))}")
    typer.secho(
        f"air district outline is CARB's as of {boundaries.DISTRICT_AS_OF}: "
        f"{boundaries.DISTRICT_CAVEAT}",
        fg=typer.colors.YELLOW,
    )


@ingest_app.command("ghgrp")
def ingest_ghgrp(year: Annotated[int, typer.Option(help="Facility-list year")] = 2023) -> None:
    """EPA GHGRP subpart HH facilities and operator-reported methane for crosswalked sites."""
    from methanewatch.ingest import pipeline

    counts = pipeline.ingest_ghgrp(config.load_project(), year)
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@coverage_app.command("build")
def coverage_build() -> None:
    """Build overpasses, attributed plumes and detections from interim footprints and plumes."""
    from methanewatch.coverage import build

    counts = _run_or_exit(build.build, config.load_project())
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@s2_app.command("search")
def s2_search(
    start: Annotated[str, typer.Option(help="YYYY-MM-DD")],
    end: Annotated[str, typer.Option(help="YYYY-MM-DD")],
    bbox: BBoxOpt = None,
    max_cloud: Annotated[float, typer.Option(help="Tile cloud cover limit, percent")] = 100.0,
) -> None:
    """Sentinel-2 L1C scene footprints from the public Earth Search catalog."""
    from methanewatch.ingest import pipeline

    project = config.load_project()
    counts = pipeline.ingest_sentinel2(
        project,
        _bbox(project, bbox),
        date.fromisoformat(start),
        date.fromisoformat(end),
        max_cloud=max_cloud,
    )
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@model_app.command("fit")
def model_fit(
    allow_unconfirmed: Annotated[
        bool, typer.Option(help="Fit with unconfirmed POD curves; stamps outputs provisional.")
    ] = False,
) -> None:
    """Fit the persistence model to data/interim/detections.parquet."""
    from methanewatch.model import run

    instruments = config.load_instruments()
    if instruments.unconfirmed() and not allow_unconfirmed:
        typer.secho(
            "unconfirmed POD curves: "
            + ", ".join(instruments.unconfirmed())
            + " (rerun with --allow-unconfirmed for provisional output)",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    try:
        run_id = _run_or_exit(
            run.fit_real,
            config.load_project(),
            config.load_model(),
            instruments,
            allow_unconfirmed,
        )
    except run.ConfigNotReadyError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"run {run_id}")


@model_app.command("demo")
def model_demo(seed: Annotated[int, typer.Option()] = 11) -> None:
    """Fit SYNTHETIC sites so the dashboard can be previewed (never real data)."""
    from methanewatch.model import run

    run_id = run.fit_synthetic_demo(config.load_project(), config.load_model(), seed=seed)
    typer.echo(f"run {run_id}")


@repair_app.command("run")
def repair_run(
    allow_unconfirmed: Annotated[
        bool, typer.Option(help="Use unconfirmed POD curves; stamps outputs provisional.")
    ] = False,
    power_fits: Annotated[int, typer.Option(help="Simulated fits per tested drop.")] = 15,
) -> None:
    """Outcome of every dated check in the registry, with its minimum detectable drop."""
    from methanewatch.model.run import ConfigNotReadyError
    from methanewatch.repair import run

    instruments = config.load_instruments()
    if instruments.unconfirmed() and not allow_unconfirmed:
        typer.secho(
            "unconfirmed POD curves: "
            + ", ".join(instruments.unconfirmed())
            + " (rerun with --allow-unconfirmed for provisional output)",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    try:
        run_id = _run_or_exit(
            run.run_real,
            config.load_project(),
            config.load_model(),
            instruments,
            allow_unconfirmed=allow_unconfirmed,
            n_power_fits=power_fits,
        )
    except ConfigNotReadyError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"run {run_id}")


@repair_app.command("count")
def repair_count(
    site: Site,
    date_: Annotated[str, typer.Option("--date", help="Repair start, YYYY-MM-DD")],
    end: Annotated[str | None, typer.Option(help="Repair end, YYYY-MM-DD")] = None,
) -> None:
    """Count usable overpasses per instrument in the before/after windows."""
    from datetime import datetime

    import pandas as pd

    from methanewatch.repair.model import Repair, assign_periods, window_counts

    project = config.load_project()
    path = project.resolve(project.paths.interim) / "overpasses.parquet"
    if not path.exists():
        typer.secho(f"missing {path}; run `mw coverage build` first", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    ov = pd.read_parquet(path)
    ov = ov[ov["usable"] & (ov["site_id"] == site)]
    rep = Repair(
        site_id=site,
        date_start=datetime.fromisoformat(date_),
        date_end=datetime.fromisoformat(end) if end else None,
    )
    counts = window_counts(assign_periods(ov, rep, project.repair))
    typer.echo(counts.to_string() if len(counts) else "no usable overpasses in either window")
    short = [
        p
        for p in ("before", "after")
        if counts.get("total", pd.Series()).get((site, p), 0)
        < project.repair.min_overpasses_per_window
    ]
    if short:
        typer.secho(f"too few overpasses: {', '.join(short)}", fg=typer.colors.YELLOW)


@validate_app.command("gate1")
def validate_gate1() -> None:
    """Plume and overpass counts per instrument per year for the pilot sites."""
    from methanewatch.validate import gates

    _gate(_run_or_exit(gates.gate1_plume_table))


@validate_app.command("gate2")
def validate_gate2() -> None:
    """Sentinel-2 reproduces a plume Carbon Mapper also shows, with a rate in range."""
    from methanewatch.validate import gates

    _gate(_run(gates.gate2_s2_reproduction))


@validate_app.command("matched-pairs")
def validate_matched_pairs(
    max_days: Annotated[float, typer.Option(help="Pairing window in days.")] = 1.0,
) -> None:
    """Sentinel-2 hit and false-positive rates by reference rate bin (no threshold)."""
    from methanewatch.validate import gates

    _gate(_run_or_exit(gates.matched_pairs, max_days))


@validate_app.command("operator")
def validate_operator(run_id: Annotated[str, typer.Option(help="Model run to compare.")]) -> None:
    """Compare a run's annual totals with GHGRP figures; every gap needs a written note."""
    from methanewatch.validate import gates

    _gate(_run_or_exit(gates.operator_comparison, run_id))


@validate_app.command("synthetic")
def validate_synthetic(
    quick: Annotated[bool, typer.Option(help="20 replicates instead of 200.")] = False,
    replicates: Annotated[int | None, typer.Option(help="Override the replicate count.")] = None,
    scenario_replicates: Annotated[int, typer.Option(help="Fixed-truth scenario fits.")] = 20,
    covariates: Annotated[
        str | None,
        typer.Option(help="Comma-separated site covariates to simulate and fit (ADR 0008)."),
    ] = None,
) -> None:
    """Gate 3: 90% intervals cover the truth 85-95% of the time on simulated data."""
    from methanewatch.validate import gates

    n = replicates or (20 if quick else 200)
    names = tuple(c.strip() for c in covariates.split(",") if c.strip()) if covariates else ()
    _gate(_run(gates.synthetic_recovery, n, 0 if quick else scenario_replicates, names))


@validate_app.command("holdout")
def validate_holdout(
    folds: Annotated[int, typer.Option()] = 5,
    synthetic: Annotated[bool, typer.Option(help="Dry run on SYNTHETIC sites.")] = False,
    allow_unconfirmed: Annotated[bool, typer.Option()] = False,
) -> None:
    """Fit on 80% of overpasses, predict detections in the held-out 20%."""
    from methanewatch.model.run import ConfigNotReadyError
    from methanewatch.validate import gates

    try:
        passed = _run_or_exit(
            gates.holdout, folds, synthetic=synthetic, allow_unconfirmed=allow_unconfirmed
        )
    except ConfigNotReadyError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    _gate(passed)


@validate_app.command("repair-synthetic")
def validate_repair_synthetic(
    worlds: Annotated[int, typer.Option(help="Independent simulated worlds.")] = 40,
    per_world: Annotated[int, typer.Option(help="Pseudo-repairs per world.")] = 4,
    power: Annotated[int, typer.Option(help="Fits per injected-drop factor.")] = 15,
) -> None:
    """Dry run of the repair test on synthetic data: placebo false-positive rate and power."""
    from methanewatch.validate import repair_synthetic

    _run(repair_synthetic.run, worlds, per_world, power, (0.75, 0.5, 0.25, 0.1))


@validate_app.command("placebo")
def validate_placebo() -> None:
    """Gate 5: placebo repair false-positive rate at or below 10%."""
    from methanewatch.validate import gates

    _gate(_run(gates.placebo))


@report_app.command("build")
def report_build(run_id: Annotated[str, typer.Option()]) -> None:
    """Build the static dashboard for a model run into reports/site."""
    from methanewatch.report import build

    project = config.load_project()
    out = project.resolve(project.paths.reports) / "site"
    try:
        index = _run_or_exit(build.build_site, project, run_id, out)
    except build.LintError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"wrote {index}")


@wind_app.command("get")
def wind_get(
    lon: Annotated[float, typer.Option()],
    lat: Annotated[float, typer.Option()],
    time: Annotated[str, typer.Option(help="UTC, e.g. 2025-06-27T19:04")],
    product: Annotated[str, typer.Option(help="hrrr or era5")] = "hrrr",
) -> None:
    """10 m wind at a point (downloads and caches a small GRIB or NetCDF subset)."""
    import pandas as pd

    from methanewatch.wind.era5 import Era5Provider
    from methanewatch.wind.hrrr import HrrrProvider

    project = config.load_project()
    cache = project.resolve(project.paths.raw) / "wind" / product
    providers = {"hrrr": HrrrProvider, "era5": Era5Provider}
    if product not in providers:
        raise typer.BadParameter("product must be hrrr or era5")
    w = providers[product](cache).get(lon, lat, pd.Timestamp(time, tz="UTC"))
    typer.echo(
        f"{w.product} {w.product_version}: u10 {w.u10:.2f} m/s, v10 {w.v10:.2f} m/s, "
        f"speed {w.speed:.2f} m/s"
    )


@population_app.command("build")
def population_build() -> None:
    """Residents within the configured radii of each site -> data/interim/population.csv."""
    import geopandas as gpd
    import pandas as pd

    from methanewatch.population import LABEL, MissingCensusKeyError, residents_within

    project = config.load_project()
    radii = config.load_impact().population_radius_km
    path = project.resolve(project.paths.interim) / "sites.parquet"
    if not path.exists():
        typer.secho("run `mw sites build` first", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    sites = gpd.read_parquet(path)
    if sites.empty:
        typer.secho("no site polygons yet", fg=typer.colors.YELLOW)
        raise typer.Exit(code=2)
    rows = []
    try:
        for site in sites.itertuples():
            counts = residents_within(site.geometry, radii, project.crs_metric)
            rows += [
                {"site_id": site.site_id, "radius_km": r, "residents": n} for r, n in counts.items()
            ]
    except MissingCensusKeyError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    out = project.resolve(project.paths.interim) / "population.csv"
    pd.DataFrame(rows).assign(label=LABEL).to_csv(out, index=False)
    typer.echo(f"wrote {out}")


@features_app.command("build")
def features_build() -> None:
    """One row of traits per site -> data/interim/site_features.parquet (ADR 0008)."""
    from methanewatch import features

    table = _run_or_exit(features.write_site_features, config.load_project())
    typer.echo(f"wrote {len(table)} sites to data/interim/site_features.parquet")


@datasets_app.command("build")
def datasets_build(
    only: Annotated[
        list[str] | None,
        typer.Option(
            help="emit, sentinel2, carbonmapper, ghgrp, calrecycle, census, boundaries, "
            "sentinel2-crops, emit-files"
        ),
    ] = None,
) -> None:
    """Write datasets/<source>/ from the raw pulls in data/raw.

    ``sentinel2-crops`` and ``emit-files`` read pixels over the network and run only when
    named; ``emit-files`` needs the Earthdata login in ~/.netrc.
    """
    from methanewatch import datasets

    project = config.load_project()
    raw = project.resolve(project.paths.raw)
    interim = project.resolve(project.paths.interim)
    root = project.resolve(project.paths.datasets)
    sites = datasets.reference_points(root / "calrecycle" / "swis_pilot_sites.csv")
    steps = {
        "emit": lambda: datasets.build_emit(raw, root / "emit"),
        "sentinel2": lambda: datasets.build_sentinel2(raw, root / "sentinel2"),
        "carbonmapper": lambda: datasets.build_carbonmapper(raw, root / "carbonmapper"),
        "ghgrp": lambda: datasets.build_ghgrp(raw, interim, root / "ghgrp"),
        "calrecycle": lambda: datasets.build_calrecycle(raw, root / "calrecycle"),
        "census": lambda: datasets.build_census(raw, root / "census", sites, radius_km=6),
        "boundaries": lambda: datasets.build_boundaries(raw, root / "boundaries"),
        "sentinel2-crops": lambda: datasets.build_sentinel2_crops(root, interim, sites),
        "emit-files": lambda: datasets.build_emit_files(raw, root, sites),
    }
    unknown = set(only or []) - set(steps)
    if unknown:
        raise typer.BadParameter(f"unknown dataset(s): {', '.join(sorted(unknown))}")
    network = {"sentinel2-crops", "emit-files"}
    for name in only or [s for s in steps if s not in network]:
        counts = _run_or_exit(steps[name])
        typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))
        if name == "boundaries":
            from methanewatch.ingest.boundaries import DISTRICT_AS_OF, DISTRICT_CAVEAT

            typer.secho(
                f"air district outline is as of {DISTRICT_AS_OF}: {DISTRICT_CAVEAT}",
                fg=typer.colors.YELLOW,
            )


if __name__ == "__main__":
    app()


# --- publish ------------------------------------------------------------------------------


def _publications_dir() -> Path:
    project = config.load_project()
    return project.resolve(project.paths.processed) / "publications"


def _dsn() -> str:
    from methanewatch.publish.load import NoDatabaseError, dsn_from_env

    try:
        return dsn_from_env()
    except NoDatabaseError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


@publish_app.command("build")
def publish_build(
    model_run: Annotated[str | None, typer.Option(help="Model run id (processed/runs).")] = None,
    check_run: Annotated[
        str | None, typer.Option(help="Check run id (processed/repair_outcomes).")
    ] = None,
    refresh: Annotated[str | None, typer.Option(help="Refresh id; default the latest.")] = None,
    allow_simulated: Annotated[
        bool, typer.Option(help="Accept a synthetic demo run (draft or review only).")
    ] = False,
    notes: Annotated[str | None, typer.Option(help="A note stored with the publication.")] = None,
) -> None:
    """Assemble a snapshot of one run, check it, and write it under processed/publications."""
    from methanewatch.publish import snapshot as snap

    project = config.load_project()
    try:
        s = _run_or_exit(
            snap.build,
            project,
            config.load_data_terms(),
            config.load_impact(),
            model_run_id=model_run,
            check_run_id=check_run,
            refresh_id=refresh,
            allow_simulated=allow_simulated,
            notes=notes,
        )
    except (snap.SimulatedRunError, snap.WordingError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    out = s.write(_publications_dir())
    for name, df in s.tables.items():
        typer.echo(f"{name}: {len(df)} rows")
    flags = ", ".join(k for k in ("simulated", "provisional") if s.publication[k])
    typer.echo(
        f"wrote {out} (data through {s.publication['data_through']}{', ' + flags if flags else ''})"
    )
    typer.echo(f"publication {s.publish_id}")


@publish_app.command("check")
def publish_check(
    publish_id: Annotated[str, typer.Argument(help="A built publication id.")],
) -> None:
    """Run the wording check again over a built snapshot's text fields."""
    from methanewatch.publish.snapshot import Snapshot, check_wording

    folder = _publications_dir() / publish_id
    if not folder.exists():
        typer.secho(f"no snapshot at {folder}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    problems = check_wording(Snapshot.read(folder).tables)
    for p in problems:
        typer.secho(p, fg=typer.colors.RED, err=True)
    if problems:
        raise typer.Exit(code=1)
    typer.echo("wording check passed")


@publish_app.command("push")
def publish_push(
    publish_id: Annotated[str, typer.Argument(help="A built publication id.")],
) -> None:
    """Load a built snapshot into the database as a draft, in one transaction."""
    from methanewatch.publish.load import push
    from methanewatch.publish.snapshot import Snapshot

    folder = _publications_dir() / publish_id
    if not folder.exists():
        typer.secho(
            f"no snapshot at {folder}; run `mw publish build` first", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=2)
    try:
        counts = push(Snapshot.read(folder), _dsn())
    except Exception as exc:  # psycopg errors carry the plain reason, e.g. a paused project
        typer.secho(f"push failed, nothing was loaded: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    for name, n in counts.items():
        typer.echo(f"{name}: {n} rows")
    typer.echo(f"loaded {publish_id} as draft")


@publish_app.command("set-visibility")
def publish_set_visibility(
    publish_id: Annotated[str, typer.Argument()],
    visibility: Annotated[str, typer.Argument(help="draft, review or public")],
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation for public.")] = False,
) -> None:
    """Promote a publication. Public needs confirmation and never accepts a simulated run."""
    from methanewatch.publish.load import set_visibility

    if visibility == "public" and not yes:
        typer.confirm(f"Make {publish_id} visible on the public website?", abort=True)
    try:
        result = set_visibility(_dsn(), publish_id, visibility)
    except (ValueError, LookupError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"{result['publish_id']}: {result['from']} -> {result['to']}")
    hook = os.environ.get(
        "CF_DEPLOY_HOOK_PUBLIC" if visibility == "public" else "CF_DEPLOY_HOOK_REVIEW"
    )
    if hook:
        import httpx

        r = httpx.post(hook, timeout=30)
        typer.echo(f"deploy hook: {r.status_code}")


@publish_app.command("list")
def publish_list() -> None:
    """Publications in the database, newest first."""
    from methanewatch.publish.load import list_publications

    for p in list_publications(_dsn()):
        flags = " ".join(k for k in ("simulated", "provisional") if p[k])
        typer.echo(
            f"{p['publish_id']}  {p['visibility']:7}  data through {p['data_through']}  {flags}"
        )


# --- scheduled run ------------------------------------------------------------------------


@app.command("scheduled-run")
def scheduled_run(
    push: Annotated[
        bool, typer.Option(help="Load the snapshot into the database and mark it review.")
    ] = True,
    datasets: Annotated[
        bool, typer.Option(help="Rewrite datasets/ for EMIT, Sentinel-2 and Carbon Mapper.")
    ] = True,
    skip: Annotated[
        list[str] | None, typer.Option(help="Source to leave out: emit, sentinel2, carbonmapper")
    ] = None,
    branch: Annotated[
        str | None, typer.Option(help="Stop unless the checkout is on this branch, e.g. main.")
    ] = None,
    notify: Annotated[
        bool, typer.Option(help="Show a macOS notification if the run stops.")
    ] = False,
) -> None:
    """Refresh, rebuild datasets, build and push a review snapshot, call the review deploy hook.

    Exits 0 when every step ran and 2 when the run stopped, with the step and the reason; both
    are kept in data/processed/scheduled/<run_id>.json. Never makes anything public.
    """
    from methanewatch import scheduled

    m = scheduled.run(
        config.load_project(),
        push=push,
        build_datasets=datasets,
        skip=skip or (),
        branch=branch,
    )
    for name, result in m["steps"].items():
        if result.get("not_run"):
            typer.echo(f"{name}: not run")
        elif result.get("skipped"):
            typer.echo(f"{name}: skipped ({result['reason']})")
        elif result["ok"]:
            typer.echo(f"{name}: ok ({result['seconds']} s)")
        else:
            typer.secho(f"{name}: FAILED {result['error']}", fg=typer.colors.RED, err=True)
    typer.echo(f"manifest: data/processed/scheduled/{m['run_id']}.json")
    if not m["ok"]:
        typer.secho(f"stopped at {m['stopped_at']}: {m['reason']}", fg=typer.colors.RED, err=True)
        if notify:
            scheduled.notify(f"Stopped at {m['stopped_at']}: {m['reason']}")
        raise typer.Exit(code=2)
    if m["visibility"] == "review":
        typer.echo(f"publication {m['publish_id']} is visible to the review build")
    else:
        typer.echo(f"publication {m['publish_id']} built, not loaded (--no-push)")


@app.command("scheduled-plist")
def scheduled_plist(
    out: Annotated[
        Path | None, typer.Option(help="Write the job here instead of printing it.")
    ] = None,
    datasets: Annotated[
        bool, typer.Option(help="Let the job rewrite datasets/ (left for you to commit).")
    ] = True,
) -> None:
    """The launchd job that runs `mw scheduled-run` on main twice a week from this checkout.

    Run it from the checkout the job should use. It only writes a file; loading the job is a
    separate `launchctl` command (README, "Scheduled run").
    """
    import sys

    from methanewatch import scheduled

    mw = Path(sys.executable).with_name("mw")
    if not mw.exists():
        typer.secho(f"no mw entry point next to {sys.executable}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    plist = scheduled.launchd_plist(config.REPO_ROOT, mw, datasets=datasets)
    if out is None:
        typer.echo(plist.decode())
        return
    out = out.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(plist)
    domain = "gui/$(id -u)"
    typer.echo(f"wrote {out}")
    typer.echo(f"load it:  launchctl bootstrap {domain} {out}")
    typer.echo(f"run now:  launchctl kickstart {domain}/{scheduled.LAUNCHD_LABEL}")
    typer.echo(f"remove:   launchctl bootout {domain}/{scheduled.LAUNCHD_LABEL}")
    typer.echo(f"log:      {scheduled.LAUNCHD_LOG}")
