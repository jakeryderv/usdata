from pathlib import Path

import pytest
from typer.testing import CliRunner

from usdata.cli import app
from usdata.manifest import lockfile_path

MANIFEST = """name: test
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: {stations: USW00013967}
"""


@pytest.mark.parametrize(
    "args",
    [
        ["search", "--start", "not-a-date"],
        ["search", "--start", "2025-01-01", "--end", "2024-01-01"],
        [
            "fetch",
            "noaa:nexrad-level2",
            "-p",
            "site=XXXX",
            "--start",
            "2024-05-06",
            "--end",
            "2024-05-07",
        ],
    ],
)
def test_cli_input_errors_are_explained(args: list[str]) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert result.output.strip()


def test_cli_malformed_manifest_and_lockfile(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("name: [")
    result = CliRunner().invoke(app, ["pull", str(manifest)])
    assert result.exit_code == 2 and "invalid manifest YAML" in result.output
    manifest.write_text(MANIFEST)
    lockfile_path(manifest).write_text("{")
    result = CliRunner().invoke(app, ["verify", str(manifest)])
    assert result.exit_code == 2 and result.output.strip()
