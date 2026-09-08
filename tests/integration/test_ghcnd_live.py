"""Hits the live NCEI service. Run with ``just test-integration``."""

import logging
from pathlib import Path

import pytest

from usdata.fetch import fetch
from usdata.providers.noaa.ghcnd import GhcnDaily
from usdata.query import build_query
from usdata.registry import default_registry

pytestmark = pytest.mark.integration


def test_oklahoma_city_station_discovery(caplog: pytest.LogCaptureFixture) -> None:
    """Exercise search independently; failed tests include bounded page diagnostics."""
    caplog.set_level(logging.DEBUG, logger="usdata.providers.noaa.ghcnd")
    ds = default_registry().get("noaa:ghcn-daily")
    q = build_query(
        lat=35.39,
        lon=-97.60,
        radius_km=15,
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP"],
    )
    with GhcnDaily(ds) as adapter:
        stations = adapter.find_stations(q)
    assert "USW00013967" in stations, "expected Will Rogers World Airport in NCEI search"


def test_oklahoma_city_precip_explicit_station(tmp_path: Path) -> None:
    """Exercise data retrieval even when the independent search service is unhealthy."""
    ds = default_registry().get("noaa:ghcn-daily")
    q = build_query(
        stations="USW00013967",
        start="2024-05-06",
        end="2024-05-07",
        variables=["PRCP"],
    )
    fetched = fetch(ds, q, root=tmp_path)
    assert fetched, "expected an explicit-station CSV asset"
    header, _, body = fetched[0].path.read_text().partition("\n")
    assert "DATE" in header and "PRCP" in header
    assert "USW00013967" in body  # Will Rogers World Airport
    assert fetched[0].provenance.checksum.startswith("sha256:")
