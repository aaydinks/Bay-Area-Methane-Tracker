"""``mw s2 cloud``: the Sentinel-2 cloud model (ADR 0012, ADR 0013)."""

from __future__ import annotations

import json
from typing import Annotated

import typer

cloud_app = typer.Typer(no_args_is_help=True, help="Cloud model for the Sentinel-2 retrieval.")


@cloud_app.command("fetch")
def cloud_fetch(
    train_sites: Annotated[int, typer.Option(help="Training sites to download")] = 600,
    workers: Annotated[int, typer.Option(help="Parallel downloads")] = 8,
) -> None:
    """Cache CloudSEN12+ patches (CC0) at 20 m under data/raw/cloudsen12/."""
    from methanewatch.sentinel2 import cloudrun

    typer.echo(json.dumps(cloudrun.fetch(train_sites, workers)))


@cloud_app.command("train")
def cloud_train() -> None:
    """Fit on training sites; choose settings on validation sites."""
    from methanewatch.sentinel2 import cloudrun

    try:
        typer.echo(json.dumps(cloudrun.train(), indent=2, default=str))
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc


@cloud_app.command("evaluate")
def cloud_evaluate(
    rehearsal: Annotated[
        bool, typer.Option(help="Run on validation sites only, into data/processed/s2cloud/")
    ] = False,
) -> None:
    """Run the ADR 0013 held-out test once and write reports/validation/s2-cloud-model/."""
    from methanewatch.sentinel2 import cloudrun

    try:
        out = cloudrun.evaluate(rehearsal=rehearsal)
    except (FileNotFoundError, FileExistsError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(str(out))
