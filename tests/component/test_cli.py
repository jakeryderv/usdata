import json
from pathlib import Path

from typer.testing import CliRunner

from usdata.cli import app
from usdata.registry import default_registry

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


def test_datasets_prints_an_aligned_table() -> None:
    result = runner.invoke(app, ["datasets", "--domain", "weather-radar"])
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert len(lines) == 3
    assert lines[0].startswith("noaa:nexrad-level2  available (since 0.2)")
    assert "NEXRAD radar scans" in lines[0]
    assert len({line.index("weather-radar") for line in lines}) == 1
    summaries = [ds.summary or ds.title for ds in default_registry().list(domain="weather-radar")]
    assert len({line.index(s) for line, s in zip(lines, summaries, strict=True)}) == 1


def test_datasets_filters_by_format_reader_and_capability() -> None:
    result = runner.invoke(app, ["datasets", "--format", "csv", "--reader", "pandas"])
    assert result.exit_code == 0
    assert "noaa:storm-events" in result.stdout and "noaa:nexrad-level2" not in result.stdout
    grib = runner.invoke(app, ["datasets", "--capability", "variable_subset", "--reader", "grib"])
    assert grib.exit_code == 0 and "noaa:mrms" in grib.stdout


def test_datasets_status_selects_planned_entries() -> None:
    result = runner.invoke(app, ["datasets", "--status", "planned", "--provider", "usgs"])
    assert result.exit_code == 0
    assert "usgs:earthquakes" in result.stdout and "target later" in result.stdout
    assert runner.invoke(app, ["datasets", "--provider", "usgs"]).stdout.count("planned") == 0


def test_datasets_exits_1_when_nothing_matches() -> None:
    result = runner.invoke(app, ["datasets", "--provider", "noaa", "--domain", "air-quality"])
    assert result.exit_code == 1 and "No datasets matched." in result.stdout


def test_datasets_rejects_unknown_filter_values() -> None:
    bad_capability = runner.invoke(app, ["datasets", "--capability", "subset"])
    assert bad_capability.exit_code == 2 and "unknown capability" in bad_capability.output
    bad_status = runner.invoke(app, ["datasets", "--status", "retired"])
    assert bad_status.exit_code == 2 and "unknown status" in bad_status.output


def test_datasets_json_emits_only_dataset_records() -> None:
    result = runner.invoke(app, ["datasets", "--domain", "weather-radar", "--json"])
    assert result.exit_code == 0
    records = json.loads(result.stdout)
    assert [r["id"] for r in records] == [
        "noaa:nexrad-level2",
        "noaa:mrms",
        "noaa:nexrad-level3",
    ]
    assert records[0]["status"] == "available" and "score" not in records[0]


def test_datasets_json_is_an_empty_array_when_nothing_matches() -> None:
    result = runner.invoke(app, ["datasets", "--domain", "nope", "--json"])
    assert result.exit_code == 1 and json.loads(result.stdout) == []


def test_search_takes_the_listing_filters() -> None:
    result = runner.invoke(app, ["search", "radar", "--reader", "grib"])
    assert result.exit_code == 0 and result.stdout.splitlines() == [
        line for line in result.stdout.splitlines() if "noaa:mrms" in line
    ]
    assert runner.invoke(app, ["search", "radar", "--domain", "air-quality"]).exit_code == 1


def test_search_status_supersedes_the_planned_flag() -> None:
    result = runner.invoke(app, ["search", "earthquakes", "--status", "all"])
    assert result.exit_code == 0 and "usgs:earthquakes" in result.stdout


def test_search_json_adds_the_score_to_each_record() -> None:
    result = runner.invoke(app, ["search", "nexrad", "--json"])
    assert result.exit_code == 0
    records = json.loads(result.stdout)
    assert records[0]["id"] == "noaa:nexrad-level2" and records[0]["score"] > 0
    assert all(record["status"] == "available" for record in records)


def test_info() -> None:
    result = runner.invoke(app, ["info", "noaa:ghcn-daily"])
    assert result.exit_code == 0
    assert "GHCN-Daily" in result.stdout
    assert runner.invoke(app, ["info", "nope:x"]).exit_code == 2


def test_info_lists_adapter_parameters() -> None:
    result = runner.invoke(app, ["info", "noaa:climate-normals"])
    assert result.exit_code == 0
    listed = [line.strip() for line in result.stdout.splitlines() if line.startswith("    ")]
    assert [line.split("  ", 1)[0] for line in listed] == ["period", "stations", "units"]
    assert all(len(line.split("  ", 1)) == 2 and line.split("  ", 1)[1].strip() for line in listed)


def test_info_says_none_when_an_adapter_takes_no_parameters() -> None:
    result = runner.invoke(app, ["info", "noaa:storm-events"])
    assert result.exit_code == 0 and "params:    none" in result.stdout


def test_info_omits_parameters_for_planned_datasets() -> None:
    result = runner.invoke(app, ["info", "usgs:earthquakes"])
    assert result.exit_code == 0 and "params:" not in result.stdout


def test_info_shows_what_a_dataset_delivers_and_needs() -> None:
    result = runner.invoke(app, ["info", "noaa:ghcn-daily"])
    assert result.exit_code == 0
    assert "formats:   CSV" in result.stdout
    assert "reader:    usdata[pandas]" in result.stdout
    assert "selection: Station observations within inclusive calendar dates" in result.stdout
    assert "inputs:    Both dates; station IDs or a geographic query" in result.stdout
    assert "examples:  examples/weather-and-streamflow/example.ipynb" in result.stdout


def test_info_says_none_for_a_dataset_with_no_reader() -> None:
    result = runner.invoke(app, ["info", "noaa:nexrad-level3"])
    assert result.exit_code == 0
    assert "formats:   NEXRAD Level III (no reader)" in result.stdout
    assert "reader:    none" in result.stdout


def test_info_omits_usage_lines_for_planned_datasets() -> None:
    result = runner.invoke(app, ["info", "usgs:earthquakes"])
    assert result.exit_code == 0
    assert "formats:" not in result.stdout and "examples:" not in result.stdout


def test_fetch_reports_unimplemented_adapter() -> None:
    result = runner.invoke(app, ["fetch", "usgs:earthquakes", "--state", "OK"])
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


def test_fetch_rejects_invalid_point_without_contacting_provider() -> None:
    result = runner.invoke(
        app,
        [
            "fetch",
            "noaa:ghcn-daily",
            "--lat",
            "91",
            "--lon",
            "0",
            "--radius-km",
            "200",
            "--start",
            "2024-05-06",
            "--end",
            "2024-05-07",
        ],
    )
    assert result.exit_code == 2
    assert "lat must be finite and between -90 and 90" in result.output


def test_pull_rejects_unknown_dataset_and_planned(tmp_path: Path) -> None:
    m = tmp_path / "dataset.yaml"
    m.write_text("name: t\nsources:\n  - dataset: nope:x\n")
    assert runner.invoke(app, ["pull", str(m)]).exit_code == 2
    m.write_text("name: t\nsources:\n  - dataset: usgs:earthquakes\n")
    assert runner.invoke(app, ["pull", str(m), "--cache-dir", str(tmp_path)]).exit_code == 3


def test_verify_without_lockfile_exits_2(tmp_path: Path) -> None:
    m = tmp_path / "dataset.yaml"
    m.write_text("name: t\nsources:\n  - dataset: noaa:ghcn-daily\n")
    result = runner.invoke(app, ["verify", str(m)])
    assert result.exit_code == 2 and "run pull first" in result.output


def test_location_alias_accepts_counties_and_reports_ambiguity() -> None:
    county = runner.invoke(app, ["search", "radar", "--location", "Cleveland County, OK"])
    fips = runner.invoke(app, ["search", "radar", "--state", "40027"])
    assert county.exit_code == fips.exit_code == 0
    assert county.stdout == fips.stdout
    ambiguous = runner.invoke(app, ["search", "radar", "--location", "Washington County"])
    assert ambiguous.exit_code == 2 and "ambiguous" in ambiguous.output
    fetch = runner.invoke(
        app, ["fetch", "noaa:ghcn-daily", "--location", "Washington County", "--dry-run"]
    )
    assert fetch.exit_code == 2 and "ambiguous" in fetch.output
