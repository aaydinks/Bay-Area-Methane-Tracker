from typer.testing import CliRunner

from methanewatch.cli import app

runner = CliRunner()


def test_config_check():
    result = runner.invoke(app, ["config", "check"])
    assert result.exit_code == 0
    assert "unconfirmed" in result.output


def test_unbuilt_steps_exit_with_code_2():
    result = runner.invoke(app, ["validate", "gate1"])
    assert result.exit_code == 2


def test_fit_refuses_unconfirmed_pod_curves():
    result = runner.invoke(app, ["model", "fit"])
    assert result.exit_code == 1
