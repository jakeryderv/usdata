"""Hits the live NCEI service. Run with ``just test-integration``."""

from pathlib import Path

import pytest

from usdata.fetch import fetch
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.integration


def test_oklahoma_city_precip(tmp_path: Path) -> None:
    ds = default_registry().get("noaa:ghcn-daily")
    q = build_query(
        lat=35.39,
        lon=-97.60,
        radius_km=15,
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP"],
    )
    fetched = fetch(ds, q, root=tmp_path)
    assert fetched, "expected at least one station near OKC"
    header, _, body = fetched[0].path.read_text().partition("\n")
    assert "DATE" in header and "PRCP" in header
    assert "USW00013967" in body  # Will Rogers World Airport
    assert fetched[0].provenance.checksum.startswith("sha256:")
