from pathlib import Path

from typer.testing import CliRunner

from usdata.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("usdata ")


def test_search_lists_matching_datasets() -> None:
    result = runner.invoke(app, ["search", "radar", "--state", "OK"])
    assert result.exit_code == 0
    assert "noaa:nexrad-level2" in result.stdout


def test_search_unknown_state_exits_2() -> None:
    assert runner.invoke(app, ["search", "radar", "--state", "Atlantis"]).exit_code == 2


def test_info() -> None:
    result = runner.invoke(app, ["info", "noaa:ghcn-daily"])
    assert result.exit_code == 0
    assert "GHCN-Daily" in result.stdout
    assert runner.invoke(app, ["info", "nope:x"]).exit_code == 2


def test_fetch_reports_unimplemented_adapter() -> None:
    result = runner.invoke(app, ["fetch", "noaa:nexrad-level2", "--state", "OK"])
    assert result.exit_code == 3


def test_pull_validates_manifest(tmp_path: Path) -> None:
    m = tmp_path / "dataset.yaml"
    m.write_text("name: t\nsources:\n  - dataset: noaa:ghcn-daily\n")
    assert runner.invoke(app, ["pull", str(m)]).exit_code == 3
    m.write_text("name: t\nsources:\n  - dataset: nope:x\n")
    assert runner.invoke(app, ["pull", str(m)]).exit_code == 2
