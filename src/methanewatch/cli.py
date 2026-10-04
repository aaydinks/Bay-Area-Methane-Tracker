"""Command-line entry point: ``mw <group> <command>``.

The Makefile and the end-to-end notebook call the same package functions.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated, Any

import typer

from methanewatch import __version__, config

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


def _run_or_exit(fn: Callable[..., Any], *args: Any) -> Any:
    """Like _run, but missing inputs exit with a message instead of a traceback."""
    try:
        return _run(fn, *args)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


def _gate(passed: bool) -> None:
    raise typer.Exit(code=0 if passed else 1)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


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


@ingest_app.command("carbonmapper")
def ingest_carbonmapper(
    site: Site,
    radius_km: Annotated[float, typer.Option()] = 5.0,
    since: Annotated[str | None, typer.Option(help="YYYY-MM-DD")] = None,
) -> None:
    """Pull Carbon Mapper plumes near a site."""
    from methanewatch.ingest import carbonmapper

    _run(carbonmapper.pull_plumes, site, radius_km, date.fromisoformat(since) if since else None)


BBoxOpt = Annotated[
    str | None,
    typer.Option(help="minlon,minlat,maxlon,maxlat; defaults to site polygons plus search radius"),
]


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
def validate_matched_pairs() -> None:
    """Sentinel-2 hit and false-positive rates by reference rate bin."""
    from methanewatch.validate import gates

    _gate(_run(gates.matched_pairs))


@validate_app.command("operator")
def validate_operator() -> None:
    """Compare model annual totals with operator-reported figures."""
    from methanewatch.validate import gates

    _gate(_run(gates.operator_comparison))


@validate_app.command("synthetic")
def validate_synthetic(
    quick: Annotated[bool, typer.Option(help="20 replicates instead of 200.")] = False,
    replicates: Annotated[int | None, typer.Option(help="Override the replicate count.")] = None,
    scenario_replicates: Annotated[int, typer.Option(help="Fixed-truth scenario fits.")] = 20,
) -> None:
    """Gate 3: 90% intervals cover the truth 85-95% of the time on simulated data."""
    from methanewatch.validate import gates

    n = replicates or (20 if quick else 200)
    _gate(_run(gates.synthetic_recovery, n, 0 if quick else scenario_replicates))


@validate_app.command("holdout")
def validate_holdout() -> None:
    """Fit on 80% of overpasses, predict detections in the held-out 20%."""
    from methanewatch.validate import gates

    _gate(_run(gates.holdout))


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


if __name__ == "__main__":
    app()
