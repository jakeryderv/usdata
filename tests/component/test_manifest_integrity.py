from pathlib import Path

import pytest
from typer.testing import CliRunner

from usdata.cli import app
from usdata.manifest import Manifest, SourceSpec

MANIFEST = """name: test
sources:
  - dataset: noaa:ghcn-daily
    start: 2024-05-06
    end: 2024-05-07
    params: {stations: USW00013967}
"""


@pytest.mark.parametrize("body", [MANIFEST + "    variable: [PRCP]\n", MANIFEST + "typo: true\n"])
def test_manifest_rejects_unknown_fields(tmp_path: Path, body: str) -> None:
    path = tmp_path / "dataset.yaml"
    path.write_text(body)
    with pytest.raises(ValueError, match="Extra inputs"):
        Manifest.load(path)
    result = CliRunner().invoke(app, ["pull", str(path)])
    assert result.exit_code == 2 and "Extra inputs" in result.output


def test_provider_params_remain_supported() -> None:
    source = SourceSpec(dataset="noaa:ghcn-daily", params={"stations": "X", "units": "metric"})
    assert source.to_query().params == {"stations": "X", "units": "metric"}
    with pytest.raises(ValueError, match="reserved"):
        SourceSpec(dataset="noaa:ghcn-daily", params={"start": "2024-01-01"})
