from pathlib import Path

from typer.testing import CliRunner

from usdata.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.startswith("usdata ")


def test_search_lists_matching_datasets_with_status() -> None:
    result = runner.invoke(app, ["search", "radar", "--state", "OK"])
    assert result.exit_code == 0
    assert "noaa:nexrad-level2" in result.stdout and "available" in result.stdout


def test_search_planned_flag() -> None:
    hidden = runner.invoke(app, ["search", "earthquakes"])
    assert hidden.exit_code == 1
    shown = runner.invoke(app, ["search", "earthquakes", "--planned"])
    assert shown.exit_code == 0 and "target later" in shown.stdout


def test_fetch_planned_dataset_exits_3() -> None:
    result = runner.invoke(app, ["fetch", "usgs:earthquakes", "--state", "OK"])
    assert result.exit_code == 3
    assert "planned" in result.output


def test_search_unknown_state_exits_2() -> None:
    assert runner.invoke(app, ["search", "radar", "--state", "Atlantis"]).exit_code == 2


def test_info() -> None:
    result = runner.invoke(app, ["info", "noaa:ghcn-daily"])
    assert result.exit_code == 0
    assert "GHCN-Daily" in result.stdout
    assert runner.invoke(app, ["info", "nope:x"]).exit_code == 2


def test_fetch_reports_unimplemented_adapter() -> None:
    result = runner.invoke(app, ["fetch", "noaa:coastwatch-sst", "--state", "OK"])
    assert result.exit_code == 3


def test_fetch_rejects_bad_query() -> None:
    result = runner.invoke(app, ["fetch", "noaa:ghcn-daily", "--state", "OK"])
    assert result.exit_code == 2
    assert "start and end" in result.output
    assert runner.invoke(app, ["fetch", "noaa:ghcn-daily", "--bbox", "1,2"]).exit_code == 2
    assert runner.invoke(app, ["fetch", "noaa:ghcn-daily", "-p", "novalue"]).exit_code == 2


def test_fetch_dry_run_lists_assets() -> None:
    result = runner.invoke(
        app,
        [
            "fetch",
            "noaa:ghcn-daily",
            "-p",
            "stations=USW00013967",
            "--start",
            "2024-05-06",
            "--end",
            "2024-05-07",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "daily-summaries_2024-05-06_2024-05-07" in result.stdout
    assert "ncei.noaa.gov" in result.stdout


def test_pull_rejects_unknown_dataset_and_stub(tmp_path: Path) -> None:
    m = tmp_path / "dataset.yaml"
    m.write_text("name: t\nsources:\n  - dataset: nope:x\n")
    assert runner.invoke(app, ["pull", str(m)]).exit_code == 2
    m.write_text("name: t\nsources:\n  - dataset: noaa:coastwatch-sst\n")
    assert runner.invoke(app, ["pull", str(m), "--cache-dir", str(tmp_path)]).exit_code == 3


def test_verify_without_lockfile_exits_2(tmp_path: Path) -> None:
    m = tmp_path / "dataset.yaml"
    m.write_text("name: t\nsources:\n  - dataset: noaa:ghcn-daily\n")
    result = runner.invoke(app, ["verify", str(m)])
    assert result.exit_code == 2 and "run pull first" in result.output
