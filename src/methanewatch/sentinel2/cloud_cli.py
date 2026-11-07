"""``mw s2 cloud``: the Sentinel-2 cloud model (ADR 0012, ADR 0013, ADR 0014)."""

from __future__ import annotations

import json
from pathlib import Path
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


@cloud_app.command("recent")
def cloud_recent(
    data_root: Annotated[
        Path | None, typer.Option(help="Checkout holding data/ (default: this one)")
    ] = None,
    model: Annotated[
        Path | None, typer.Option(help="Model weights (default: data/processed)")
    ] = None,
    workers: Annotated[int, typer.Option(help="Windows read at once")] = 6,
) -> None:
    """Run the ADR 0014 check on 2025 pilot passes once (reports/validation/s2-cloud-recent/)."""
    from methanewatch.config import REPO_ROOT
    from methanewatch.sentinel2 import cloudrecent

    try:
        out = cloudrecent.run(data_root or REPO_ROOT, model, workers)
    except (FileNotFoundError, FileExistsError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(f"{out}\nLabel the thumbnails in eye-labels.csv, then run `mw s2 cloud recent-eye`.")


@cloud_app.command("recent-eye")
def cloud_recent_eye(
    data_root: Annotated[
        Path | None, typer.Option(help="Checkout holding data/ (default: this one)")
    ] = None,
) -> None:
    """Score the blind eye check from eye-labels.csv and write the ADR 0014 verdict."""
    from methanewatch.config import REPO_ROOT
    from methanewatch.sentinel2 import cloudrecent

    try:
        out = cloudrecent.finish(data_root or REPO_ROOT)
    except (FileNotFoundError, FileExistsError, ValueError, StopIteration) as exc:
        typer.secho(str(exc) or "no ADR 0014 result to finish", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(str(out))
