"""Pricing a manifest: pull --dry-run lists every source and downloads nothing."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
import respx
from typer.testing import CliRunner

from usdata.cli import app
from usdata.manifest import lockfile_path
from usdata.providers.noaa.hrrr import BUCKET
from usdata.providers.noaa.spc import DATA_URL as SPC_DATA_URL
from usdata.providers.noaa.spc import PAGE_URL as SPC_PAGE_URL
from usdata.pull import plan

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
RUN = "hrrr.20240506/conus/hrrr.t20z."
KEYS = [(f"{RUN}wrfsfcf{hour:02d}.grib2", 150_000_000 + hour) for hour in (0, 1)]
TORNADO_FILE = "2024_torn.csv"
MANIFEST = """name: storm-inputs
sources:
  - name: hrrr
    dataset: noaa:hrrr
    start: 2024-05-06T20:00Z
    end: 2024-05-06T20:00Z
    params: { cycle: 20, forecast_hour: "0,1" }
  - name: tornadoes
    dataset: noaa:spc-tornado-reports
    start: 2024-04-01
    end: 2024-04-30
"""
HRRR_LINES = [
    f"hrrr.20240506.t20z.wrfsfcf{hour:02d}.grib2\t{150_000_000 + hour}\t"
    f"s3://{BUCKET}/{RUN}wrfsfcf{hour:02d}.grib2"
    for hour in (0, 1)
]
SPC_LINE = f"{TORNADO_FILE}\t?\t{SPC_DATA_URL}{TORNADO_FILE}"
TOTAL = (
    "2 source(s), 3 asset(s), at least 300000001 bytes; "
    "size unknown for 1 asset(s) from tornadoes; nothing downloaded\n"
)


def _listing() -> str:
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in KEYS)
    return (
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<IsTruncated>false</IsTruncated>{items}</ListBucketResult>"
    )


def _spc_page() -> str:
    return (
        f'<html><body><table><tr><td><a href="data/{TORNADO_FILE}">'
        f"{TORNADO_FILE} (0.2 mb)</a></td></tr></table></body></html>"
    )


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    path = tmp_path / "dataset.yaml"
    path.write_text(MANIFEST)
    return path


@pytest.fixture
def listings() -> Iterator[respx.MockRouter]:
    """Serve both listings, and refuse to let any asset itself be downloaded."""
    with respx.mock(assert_all_called=False) as mock:
        mock.get(LIST_URL).respond(200, text=_listing())
        mock.get(SPC_PAGE_URL).respond(200, text=_spc_page())
        mock.get(f"{LIST_URL}{KEYS[0][0]}").respond(200, content=b"grib")
        mock.get(f"{SPC_DATA_URL}{TORNADO_FILE}").respond(200, content=b"om,yr\n")
        yield mock


def _downloads(mock: respx.MockRouter) -> list[bool]:
    return [mock.routes[2].called, mock.routes[3].called]


def test_plan_prices_every_source_without_downloading(
    manifest: Path, listings: respx.MockRouter
) -> None:
    priced = plan(manifest)
    assert [s.source for s in priced.sources] == ["hrrr", "tornadoes"]
    assert [s.dataset_id for s in priced.sources] == ["noaa:hrrr", "noaa:spc-tornado-reports"]
    hrrr, tornadoes = priced.sources
    assert [a.size for a in hrrr.assets] == [150_000_000, 150_000_001]
    assert hrrr.known_bytes == 300_000_001 and hrrr.unknown_sizes == 0
    assert [a.id for a in tornadoes.assets] == [TORNADO_FILE]
    assert tornadoes.known_bytes == 0 and tornadoes.unknown_sizes == 1
    assert priced.manifest == "storm-inputs" and priced.asset_count == 3
    assert priced.known_bytes == 300_000_001 and priced.unknown_sizes == 1
    assert priced.unsized_sources == ["tornadoes"]
    assert _downloads(listings) == [False, False]
    assert not lockfile_path(manifest).exists()


def test_cli_dry_run_prints_assets_subtotals_and_an_honest_total(
    manifest: Path, listings: respx.MockRouter
) -> None:
    result = CliRunner().invoke(app, ["pull", str(manifest), "--dry-run"])
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        *HRRR_LINES,
        "hrrr (noaa:hrrr): 2 asset(s), 300000001 bytes",
        SPC_LINE,
        "tornadoes (noaa:spc-tornado-reports): 1 asset(s), "
        "at least 0 bytes; size unknown for 1 asset(s)",
    ]
    assert result.stderr == TOTAL
    assert "0 bytes;" not in result.stderr
    assert _downloads(listings) == [False, False]
    assert not lockfile_path(manifest).exists()


def test_cli_dry_run_quiet_keeps_only_the_subtotals(
    manifest: Path, listings: respx.MockRouter
) -> None:
    result = CliRunner().invoke(app, ["pull", str(manifest), "--dry-run", "--quiet"])
    assert result.exit_code == 0
    assert [line.split(":")[0] for line in result.stdout.splitlines()] == [
        "hrrr (noaa",
        "tornadoes (noaa",
    ]
    assert result.stderr == TOTAL


def test_cli_dry_run_json_emits_the_plan(manifest: Path, listings: respx.MockRouter) -> None:
    result = CliRunner().invoke(app, ["pull", str(manifest), "--dry-run", "--json"])
    assert result.exit_code == 0
    priced = json.loads(result.stdout)
    assert priced["manifest"] == "storm-inputs"
    assert priced["asset_count"] == 3 and priced["known_bytes"] == 300_000_001
    assert priced["unknown_sizes"] == 1 and priced["unsized_sources"] == ["tornadoes"]
    assert [s["source"] for s in priced["sources"]] == ["hrrr", "tornadoes"]
    assert [a["id"] for a in priced["sources"][1]["assets"]] == [TORNADO_FILE]
    assert priced["sources"][1]["known_bytes"] == 0
    assert result.stderr == TOTAL
    assert _downloads(listings) == [False, False]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--json"], "--json applies to --dry-run only"),
        (["--dry-run", "--update", "noaa:hrrr"], "cannot update pins"),
    ],
)
def test_cli_dry_run_rejects_incompatible_flags(
    manifest: Path, listings: respx.MockRouter, args: list[str], message: str
) -> None:
    result = CliRunner().invoke(app, ["pull", str(manifest), *args])
    assert result.exit_code == 2 and message in result.output
    assert not listings.calls
