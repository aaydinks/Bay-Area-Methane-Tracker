from typer.testing import CliRunner

from methanewatch.cli import app

runner = CliRunner()


def test_config_check():
    result = runner.invoke(app, ["config", "check"])
    assert result.exit_code == 0
    assert "unconfirmed" in result.output
    assert "model.grid.q_min_kg_hr" in result.output


def test_unbuilt_steps_exit_with_code_2(tmp_path, monkeypatch):
    # Point data paths at an empty folder so local builds in data/ don't matter
    from methanewatch import config

    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    result = runner.invoke(app, ["validate", "gate1"])
    assert result.exit_code == 2


def test_fit_refuses_unconfirmed_pod_curves():
    result = runner.invoke(app, ["model", "fit"])
    assert result.exit_code == 1


def test_repair_synthetic_command_is_registered():
    import typer.main

    validate = typer.main.get_command(app).commands["validate"]
    params = {p.name for p in validate.commands["repair-synthetic"].params}
    assert {"worlds", "per_world", "power"} <= params


def test_fit_passes_allow_unconfirmed_through(monkeypatch):
    # The flag must reach fit_real, whose allow_unconfirmed is keyword-only
    from methanewatch.model import run

    seen = {}

    def fake_fit_real(project, cfg, instruments, *, allow_unconfirmed=False, include_unsearched=()):
        seen["allow_unconfirmed"] = allow_unconfirmed
        seen["include_unsearched"] = include_unsearched
        return "fit-test"

    monkeypatch.setattr(run, "fit_real", fake_fit_real)
    result = runner.invoke(app, ["model", "fit", "--allow-unconfirmed"])
    assert result.exit_code == 0, result.output
    assert seen == {"allow_unconfirmed": True, "include_unsearched": ()}
    assert "run fit-test" in result.output


def test_fit_passes_include_unsearched_through(monkeypatch):
    # ADR 0016: keeping an unsearched instrument is a deliberate, named choice per instrument
    from methanewatch.model import run

    seen = {}

    def fake_fit_real(project, cfg, instruments, *, allow_unconfirmed=False, include_unsearched=()):
        seen["include_unsearched"] = include_unsearched
        return "fit-test"

    monkeypatch.setattr(run, "fit_real", fake_fit_real)
    result = runner.invoke(
        app,
        [
            "model",
            "fit",
            "--allow-unconfirmed",
            "--include-unsearched",
            "sentinel2",
            "--include-unsearched",
            "emit",
        ],
    )
    assert result.exit_code == 0, result.output
    assert seen == {"include_unsearched": ("sentinel2", "emit")}
