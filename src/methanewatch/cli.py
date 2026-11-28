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
from methanewatch.sentinel2.cloud_cli import cloud_app

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
s2_app.add_typer(cloud_app, name="cloud")

Site = Annotated[str, typer.Option(help="site_id from the registry, e.g. newby-island")]
FitSites = Annotated[
    list[str] | None,
    typer.Option(
        "--site",
        help="Use this site (site_id). Repeat for several; adds to --tier. Recorded in the "
        "run manifest.",
    ),
]
FitTiers = Annotated[
    list[str] | None,
    typer.Option(
        "--tier",
        help="Use the sites of this registry tier, e.g. pilot. Repeat for several. Needed "
        "once the registry has sites of more than one tier. Recorded in the run manifest.",
    ),
]


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
    scope = config.load_public_scope()
    unknown = scope.unknown_regions(project)
    if unknown:
        typer.secho(
            f"public scope names regions that project.yaml does not have: {unknown}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(
        f"public scope: ok (regions {', '.join(scope.regions) or 'none'}; "
        f"tiers {', '.join(scope.tiers) or 'none'})"
    )

    metrics = config.load_metrics()
    unknown = metrics.unknown_sources(config.load_data_terms())
    if unknown:
        typer.secho(
            f"metrics.yaml names sources that data_terms.yaml does not have: {unknown}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"metrics:     ok ({len(metrics.measures)} measures)")

    pending = [f"instruments.{n}.pod" for n in instruments.unconfirmed()]
    pending += [
        f"impact.{k}"
        for k in ("gwp20", "gwp100", "usd_per_t_co2e")
        if not getattr(impact, k).confirmed
    ]
    if model.grid.q_min_kg_hr is None:
        pending.append("model.grid.q_min_kg_hr (unset)")
    elif not model.grid.q_min_confirmed:
        pending.append("model.grid.q_min_kg_hr")
    if pending:
        typer.secho("unconfirmed (outputs will be provisional):", fg=typer.colors.YELLOW)
        for p in pending:
            typer.echo(f"  - {p}")


@sites_app.command("screen")
def sites_screen() -> None:
    """Propose screening-tier sites and outlines from CalRecycle's records (ADR 0018).

    Writes a proposal and a review table to data/interim/screening/ for a person to check.
    It never changes data/registry.
    """
    import geopandas as gpd
    import pandas as pd

    from methanewatch.ingest import calrecycle_boundaries
    from methanewatch.sites import registry, screening

    project = config.load_project()
    datasets_dir = project.resolve(project.paths.datasets) / "calrecycle"
    registry_dir = project.resolve(project.paths.registry)
    boundary_file = calrecycle_boundaries.latest(project.resolve(project.paths.raw))
    for path, hint in [
        (datasets_dir / "swis_landfills.csv", "run `mw ingest calrecycle` and `mw datasets build`"),
        (boundary_file, "run `mw ingest calrecycle-boundaries`"),
    ]:
        if path is None or not path.exists():
            typer.secho(f"missing input; {hint}", fg=typer.colors.YELLOW, err=True)
            raise typer.Exit(code=2)
    built = registry.build_project_registry(project)
    existing = gpd.GeoDataFrame(built[["site_id", "geometry"]], crs="EPSG:4326")
    numbered = built[built["swis_number"] != ""]
    overrides_path = registry_dir / "screening_overrides.csv"
    proposal = screening.propose(
        pd.read_csv(datasets_dir / "swis_landfills.csv"),
        calrecycle_boundaries.outlines(boundary_file),
        county_region=project.county_region,
        existing=existing,
        existing_swis=dict(zip(numbered["swis_number"], numbered["site_id"], strict=True)),
        boundaries_as_of=calrecycle_boundaries.DATA_AS_OF,
        overrides=pd.read_csv(overrides_path, dtype=str) if overrides_path.exists() else None,
        metric_crs=project.crs_metric,
    )
    out = project.resolve(project.paths.interim) / "screening"
    out.mkdir(parents=True, exist_ok=True)
    proposal.sites.to_csv(out / "sites_proposed.csv", index=False)
    proposal.outlines.to_file(out / "sites_proposed.geojson", driver="GeoJSON")
    proposal.review.to_csv(out / "review.csv", index=False)
    review = proposal.review
    drawn = (~proposal.outlines["source"].str.startswith("provisional")).sum()
    typer.echo(
        f"{len(review)} landfills considered; {int(review['included'].sum())} selected, "
        f"{int(review['in_registry'].sum())} already in the registry; "
        f"{len(proposal.sites)} proposed ({int(drawn)} with a drawn outline, "
        f"{len(proposal.sites) - int(drawn)} with a provisional buffer)"
    )
    for problem in proposal.problems:
        typer.secho(f"to settle by hand: {problem}", fg=typer.colors.YELLOW)
    typer.echo(f"wrote {out}; nothing in data/registry was changed")


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
        sites = registry.build_project_registry(project)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"wrote {len(sites)} sites to data/interim/sites.parquet")
    for note in registry.district_notes(sites):
        typer.secho(note, fg=typer.colors.YELLOW)


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


@ingest_app.command("carbonmapper-co2")
def ingest_carbonmapper_co2(
    start: Annotated[str | None, typer.Option(help="YYYY-MM-DD, default the project start")] = None,
    end: Annotated[str | None, typer.Option(help="YYYY-MM-DD, default today")] = None,
    bbox: BBoxOpt = None,
    offline: Annotated[
        bool, typer.Option(help="Recount from the pulls on disk, no download")
    ] = False,
) -> None:
    """Carbon Mapper CO2 plumes and CO2 scenes, as counts per landfill and year
    (-> data/interim/site_metrics/carbonmapper-co2.parquet). Kept apart from the methane pulls;
    CO2 is counted, never modelled."""
    from methanewatch.ingest import pipeline

    project = config.load_project()
    if offline:
        counts = _run_or_exit(pipeline.write_carbonmapper_co2, project)
    else:
        first = date.fromisoformat(start) if start else project.ingest.start
        stop = date.fromisoformat(end) if end else date.today()
        counts = _run_or_exit(
            pipeline.ingest_carbonmapper_co2, project, _bbox(project, bbox), first, stop
        )
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@ingest_app.command("lmop")
def ingest_lmop(
    offline: Annotated[
        bool, typer.Option(help="Rebuild from the newest file on disk, no download")
    ] = False,
) -> None:
    """EPA's landfill gas program file for California: waste in place, gas collected and flared,
    and energy projects, for each landfill matched in data/registry/lmop_crosswalk.csv
    (-> data/interim/site_metrics/epa-lmop.parquet)."""
    from methanewatch.ingest import pipeline

    step = pipeline.write_lmop if offline else pipeline.ingest_lmop
    counts = _run_or_exit(step, config.load_project())
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@ingest_app.command("calenviroscreen")
def ingest_calenviroscreen(
    offline: Annotated[
        bool, typer.Option(help="Rebuild from the newest file on disk, no download")
    ] = False,
) -> None:
    """The state's CalEnviroScreen 5.0 file: the score of the census tract each landfill sits in
    and of the tracts within 1 km of its outline, as context only
    (-> data/interim/site_metrics/calenviroscreen.parquet)."""
    from methanewatch.ingest import pipeline

    step = pipeline.write_calenviroscreen if offline else pipeline.ingest_calenviroscreen
    counts = _run_or_exit(step, config.load_project())
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@ingest_app.command("aqs")
def ingest_aqs(
    offline: Annotated[
        bool, typer.Option(help="Rebuild from the newest files on disk, no download")
    ] = False,
    year: Annotated[
        int | None,
        typer.Option(help="Newest year to read (default: the newest year EPA holds in full)"),
    ] = None,
) -> None:
    """EPA's annual air monitor files: the nearest fine-particle and NO2 monitor within 25 km of
    each landfill's outline, at its newest certified full year, as context only
    (-> data/interim/site_metrics/epa-aqs.parquet)."""
    from methanewatch.ingest import pipeline

    project = config.load_project()
    if offline:
        counts = _run_or_exit(pipeline.write_aqs, project)
    else:
        counts = _run_or_exit(pipeline.ingest_aqs, project, year)
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
    """CalRecycle SWIS sites with a landfill activity in the project's counties (about 5 minutes
    for fourteen counties)."""
    from methanewatch.ingest import calrecycle

    project = config.load_project()
    counties = [c.name for c in project.counties]
    typer.echo(f"wrote {calrecycle.pull(project.resolve(project.paths.raw), counties)}")


@ingest_app.command("calrecycle-boundaries")
def ingest_calrecycle_boundaries() -> None:
    """CalRecycle's landfill boundary polygons, statewide, keyed by SWIS number (data as of
    2021; terms of reuse still to check)."""
    from methanewatch.ingest import calrecycle_boundaries

    project = config.load_project()
    typer.echo(f"wrote {calrecycle_boundaries.pull(project.resolve(project.paths.raw))}")


@ingest_app.command("air-districts")
def ingest_air_districts() -> None:
    """CARB's outlines of every air district that touches the project's regions (as of 2004;
    a district read from them stays unconfirmed until checked)."""
    from methanewatch.ingest import air_districts

    project = config.load_project()
    typer.echo(f"wrote {air_districts.pull(project.resolve(project.paths.raw), project.bbox)}")


@ingest_app.command("boundaries")
def ingest_boundaries() -> None:
    """Census 2025 counties, places, tracts, roads and water, and CARB's Bay Area district
    outline (as of 2004; check against current BAAQMD)."""
    from methanewatch.ingest import boundaries

    project = config.load_project()
    pull_dir = boundaries.pull(
        project.resolve(project.paths.raw), list(project.county_fips), project.carb_districts
    )
    typer.echo(f"wrote {pull_dir}")
    typer.secho(
        f"air district outline is CARB's as of {boundaries.DISTRICT_AS_OF}: "
        f"{boundaries.DISTRICT_CAVEAT}",
        fg=typer.colors.YELLOW,
    )


@ingest_app.command("ghgrp")
def ingest_ghgrp(year: Annotated[int, typer.Option(help="Facility-list year")] = 2023) -> None:
    """EPA GHGRP subpart HH facilities, and for crosswalked sites the operator-reported methane
    and every gas they reported (-> data/interim/site_metrics/ghgrp.parquet)."""
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


@s2_app.command("site-clear")
def s2_site_clear(
    workers: Annotated[int, typer.Option(help="Parallel reads")] = 8,
) -> None:
    """Sen2Cor's clear share over each site on each Sentinel-2 pass (ADR 0014).

    Reads Sen2Cor's scene classification for passes not yet cached and writes
    data/interim/s2_site_clear.parquet; `mw coverage build` then uses it. `mw refresh` runs
    this step itself.
    """
    from methanewatch.sentinel2 import siteclear

    project = config.load_project()
    counts = _run_or_exit(siteclear.pull, project, workers=workers)
    typer.echo(", ".join(f"{k}: {v}" for k, v in counts.items()))


@model_app.command("fit")
def model_fit(
    allow_unconfirmed: Annotated[
        bool, typer.Option(help="Fit with unconfirmed POD curves; stamps outputs provisional.")
    ] = False,
    include_unsearched: Annotated[
        list[str] | None,
        typer.Option(
            help="Keep this instrument's passes although its plume search has not run, so "
            "each one counts as a pass that saw nothing. Repeat for several. Recorded in the "
            "run manifest."
        ),
    ] = None,
    site: FitSites = None,
    tier: FitTiers = None,
    covariate: Annotated[
        list[str] | None,
        typer.Option(
            help="Site covariate for this fit, in place of the list in config/model.yaml. "
            "Repeat for several. A fit of sites in several regions needs the region term "
            "(north_valley). Recorded in the run manifest."
        ),
    ] = None,
) -> None:
    """Fit the persistence model to data/interim/detections.parquet.

    An instrument whose plume search has not run (no plume table from any of its sources in
    data/interim/plumes) is left out, and the run manifest says so (decision record 0016).

    --tier and --site choose the sites to fit. With neither, every site with detections is
    fit while they are all of one tier; a registry with several tiers needs a choice, so that
    sites added later do not join a fit, and move the other sites' estimates, unnoticed.
    """
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
            allow_unconfirmed=allow_unconfirmed,
            include_unsearched=tuple(include_unsearched or ()),
            sites=tuple(site or ()),
            tiers=tuple(tier or ()),
            covariates=tuple(covariate) if covariate else None,
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
    include_unsearched: Annotated[
        list[str] | None,
        typer.Option(
            help="Keep this instrument's passes although its plume search has not run, so "
            "each one counts as a pass that saw nothing. Repeat for several. Recorded in the "
            "run manifest."
        ),
    ] = None,
    site: FitSites = None,
    tier: FitTiers = None,
    fit: Annotated[
        str | None,
        typer.Option(
            "--fit",
            help="Use the sites of this model run (processed/runs), for example the official "
            "fit, in place of --tier and --site.",
        ),
    ] = None,
) -> None:
    """Outcome of every dated check in the registry, with its minimum detectable drop.

    Like `mw model fit`, it leaves out an instrument whose plume search has not run (decision
    record 0016), and --tier and --site choose the control sites the way that command chooses
    the sites to fit. --fit takes them from a model run, so the controls are the sites of the
    fit being tested (decision record 0021). A check at a site outside the choice is still
    tested, against them.
    """
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
            include_unsearched=tuple(include_unsearched or ()),
            sites=tuple(site or ()),
            tiers=tuple(tier or ()),
            fit_run_id=fit,
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
    at_scale: Annotated[
        bool,
        typer.Option(
            help="Simulate as many sites as the registry has, in their regions and with their "
            "real pass counts, and fit with the region term (200 replicates unless told "
            "otherwise). The report goes to reports/trials, which is not published."
        ),
    ] = False,
) -> None:
    """Gate 3: 90% intervals cover the truth 85-95% of the time on simulated data."""
    from methanewatch.validate import gates

    if at_scale:
        if covariates:
            typer.secho("--at-scale brings its own region term; drop --covariates", err=True)
            raise typer.Exit(code=1)
        _gate(_run_or_exit(gates.synthetic_recovery_at_scale, replicates or (5 if quick else 200)))
        return
    n = replicates or (20 if quick else 200)
    names = tuple(c.strip() for c in covariates.split(",") if c.strip()) if covariates else ()
    _gate(_run(gates.synthetic_recovery, n, 0 if quick else scenario_replicates, names))


@validate_app.command("holdout")
def validate_holdout(
    folds: Annotated[int, typer.Option()] = 5,
    synthetic: Annotated[bool, typer.Option(help="Dry run on SYNTHETIC sites.")] = False,
    allow_unconfirmed: Annotated[bool, typer.Option()] = False,
    include_unsearched: Annotated[
        list[str] | None,
        typer.Option(
            help="Keep this instrument's passes although its plume search has not run, so "
            "each one counts as a pass that saw nothing. Repeat for several. Recorded in the "
            "run manifest."
        ),
    ] = None,
) -> None:
    """Fit on 80% of overpasses, predict detections in the held-out 20%.

    On real data, an instrument whose plume search has not run is left out, as in
    `mw model fit` (decision record 0016).
    """
    from methanewatch.model.run import ConfigNotReadyError
    from methanewatch.validate import gates

    try:
        passed = _run_or_exit(
            gates.holdout,
            folds,
            synthetic=synthetic,
            allow_unconfirmed=allow_unconfirmed,
            include_unsearched=tuple(include_unsearched or ()),
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
            "air-districts, sentinel2-crops, emit-files"
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
        "census": lambda: datasets.build_census(
            raw, root / "census", sites, radius_km=6, county_fips=project.county_fips
        ),
        "boundaries": lambda: datasets.build_boundaries(
            raw, root / "boundaries", list(project.county_fips), project.carb_districts
        ),
        "air-districts": lambda: datasets.build_air_districts(raw, root / "boundaries"),
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
    screening_run: Annotated[
        str | None,
        typer.Option(
            help="A second model run for the sites --model-run does not have. Its rows are "
            "marked provisional."
        ),
    ] = None,
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
            screening_run_id=screening_run,
            check_run_id=check_run,
            refresh_id=refresh,
            allow_simulated=allow_simulated,
            notes=notes,
        )
    except (
        snap.SimulatedRunError,
        snap.WordingError,
        snap.MeasureError,
        snap.RegulatorError,
    ) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    out = s.write(_publications_dir())
    for name, df in s.tables.items():
        typer.echo(f"{name}: {len(df)} rows")
    used, left = s.model_instruments()
    if used:
        gaps = "; left out: " + ", ".join(f"{k} ({v})" for k, v in left.items()) if left else ""
        typer.echo(f"model run instruments: {', '.join(used)}{gaps}")
    if s.publication.get("screening_run_id"):
        est = s.tables["site_estimates"]
        n = int((est["model_run_id"] == s.publication["screening_run_id"]).sum())
        typer.echo(f"screening run {s.publication['screening_run_id']}: {n} provisional estimates")
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


@publish_app.command("prune")
def publish_prune(
    keep_review: Annotated[
        int, typer.Option(help="Newest review copies to keep (at least 1).")
    ] = 8,
    keep_draft: Annotated[int, typer.Option(help="Newest drafts to keep.")] = 2,
    apply: Annotated[
        bool, typer.Option("--apply", help="Delete them. Without this, only list them.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation.")] = False,
) -> None:
    """List old draft and review publications in the database, and with --apply remove them.

    A public publication and the newest review copy always stay (ADR 0021). The snapshot
    folders on disk are not touched, so a removed publication can be pushed again.
    """
    from methanewatch.publish.load import prune

    try:
        plan = prune(_dsn(), keep_review=keep_review, keep_draft=keep_draft)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    for p in plan["publications"]:
        typer.echo(f"{p['publish_id']}  {p['visibility']:7}  data through {p['data_through']}")
    n, total = len(plan["publications"]), sum(plan["rows"].values())
    kept = ", ".join(f"{v} {k}" for k, v in sorted(plan["kept"].items())) or "none"
    typer.echo(f"{n} publications and {total} rows could be removed; staying: {kept}")
    if not n:
        return
    if not apply:
        typer.echo("dry run: nothing was removed; add --apply to remove them")
        return
    if not yes:
        typer.confirm(f"Remove these {n} publications from the database?", abort=True)
    done = prune(_dsn(), keep_review=keep_review, keep_draft=keep_draft, apply=True)
    typer.echo(f"removed {done['deleted']} publications")


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

    The snapshot carries the official fit (publish.official_model_run) only while the refreshed
    detections still match it for the sites it covers; otherwise it is loaded as a draft and the
    run stops before review. Sites added to the registry after the fit do not stop it. A fit
    named in publish.screening_model_run fills in the sites the official fit lacks.
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
            no_estimates = result.get("no_estimates")
            no_screening = result.get("screening_no_estimates")
            typer.echo(
                f"{name}: ok ({result['seconds']} s)"
                + (f"; no estimates: {no_estimates}" if no_estimates else "")
                + (f"; no screening estimates: {no_screening}" if no_screening else "")
            )
        else:
            typer.secho(f"{name}: FAILED {result['error']}", fg=typer.colors.RED, err=True)
    touched = m["database_touch"]
    if touched.get("skipped"):
        typer.echo(f"database: not touched separately ({touched['reason']})")
    elif touched["ok"]:
        typer.echo(f"database: reachable (select 1, {touched['seconds']} s)")
    else:
        hint = f" ({touched['hint']})" if touched.get("hint") else ""
        typer.secho(f"database: {touched['error']}{hint}", fg=typer.colors.RED, err=True)
    typer.echo(f"manifest: data/processed/scheduled/{m['run_id']}.json")
    if not m["ok"]:
        typer.secho(f"stopped at {m['stopped_at']}: {m['reason']}", fg=typer.colors.RED, err=True)
        if notify:
            db = "" if touched["ok"] else f"{touched['error'].capitalize()}. "
            scheduled.notify(f"{db}Stopped at {m['stopped_at']}: {m['reason']}")
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
