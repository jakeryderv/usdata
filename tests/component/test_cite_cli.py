import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from usdata import __version__
from usdata.cli import app
from usdata.providers.noaa.ghcnd import DATA_URL
from usdata.pull import pull

MANIFEST = """
name: okc-precip
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    variables: [PRCP]
    params: { stations: "USW00013967" }
"""
CSV = b'"DATE","STATION","PRCP"\n"2024-05-06","USW00013967","10.9"\n'

runner = CliRunner()


@pytest.fixture
def pulled(tmp_path: Path) -> Path:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    with respx.mock() as mock:
        mock.get(DATA_URL).mock(return_value=httpx.Response(200, content=CSV))
        pull(manifest, root=tmp_path)
    return manifest


def test_cite_a_dataset_id_prints_the_registry_citation() -> None:
    result = runner.invoke(app, ["cite", "noaa:ghcn-daily"])
    assert result.exit_code == 0
    assert result.stdout.startswith("noaa:ghcn-daily\n  Menne, M.J.,")
    assert "license: US Government Work (public domain)" in result.stdout
    assert "retrieved:" not in result.stdout


def test_cite_a_manifest_reports_what_the_lockfile_pins(pulled: Path) -> None:
    result = runner.invoke(app, ["cite", str(pulled)])
    assert result.exit_code == 0
    assert "noaa:ghcn-daily" in result.stdout and "Menne, M.J.," in result.stdout
    assert "  retrieved: " in result.stdout
    summary = f"1 checksummed asset ({len(CSV):,} bytes) pinned by usdata {__version__}"
    assert summary in result.stdout
    assert "sources: 1" in result.stdout


def test_cite_a_manifest_as_bibtex(pulled: Path) -> None:
    result = runner.invoke(app, ["cite", str(pulled), "--format", "bibtex"])
    assert result.exit_code == 0
    assert result.stdout.startswith("@misc{noaa-ghcn-daily,")
    assert "howpublished = {Menne, M.J.," in result.stdout
    assert "note         = {Retrieved " in result.stdout and "checksummed asset" in result.stdout
    assert "url          = {https://www.ncei.noaa.gov/products/" in result.stdout


def test_cite_json_emits_only_citation_records(pulled: Path) -> None:
    result = runner.invoke(app, ["cite", str(pulled), "--json"])
    assert result.exit_code == 0
    records = json.loads(result.stdout)
    assert [r["dataset_id"] for r in records] == ["noaa:ghcn-daily"]
    assert records[0]["asset_count"] == 1 and records[0]["total_bytes"] == len(CSV)
    assert records[0]["usdata_version"] == __version__ and records[0]["sources"] == ["1"]
    assert records[0]["retrieved"]["start"] == records[0]["retrieved"]["end"]


def test_cite_rejects_an_unknown_dataset() -> None:
    result = runner.invoke(app, ["cite", "nope:x"])
    assert result.exit_code == 2 and "Unknown dataset: nope:x" in result.output


def test_cite_without_a_lockfile_says_to_pull_first(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(MANIFEST)
    result = runner.invoke(app, ["cite", str(manifest)])
    assert result.exit_code == 2 and "run pull first" in result.output


def test_cite_reports_a_missing_manifest(tmp_path: Path) -> None:
    result = runner.invoke(app, ["cite", str(tmp_path / "absent.yaml")])
    assert result.exit_code == 2 and "no manifest at" in result.output


def test_cite_refuses_a_manifest_edited_after_the_lockfile(pulled: Path) -> None:
    pulled.write_text(MANIFEST.replace("2024-05-07", "2024-05-08"))
    result = runner.invoke(app, ["cite", str(pulled)])
    assert result.exit_code == 2 and "changed" in result.output
