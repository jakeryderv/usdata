"""`usdata.testing` seen from outside: it passes a bundled adapter and rejects a broken one."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from usdata.models import Asset, Capabilities, Dataset, Protocol, Query, Status, TimeRange, Variable
from usdata.protocols import http
from usdata.providers import HttpProvider, Provider
from usdata.providers.noaa.storm_events import DIRECTORY_URL, StormEvents
from usdata.query import build_query
from usdata.registry import default_registry
from usdata.testing import check_provider_contract

pytestmark = pytest.mark.l2

DATA = b"source bytes\n"
STORM_ID = "noaa:storm-events"
STORM_NAME = "StormEvents_details-ftp_v1.0_d2024_c20260323.csv.gz"
SYNTHETIC_URL = "https://example.invalid/demo/2024.csv"
# A registry entry an outside adapter would write for itself, not one usdata ships.
SYNTHETIC = Dataset(
    id="demo:sidecar-writer",
    provider="demo",
    title="Synthetic whole-year files",
    protocol=Protocol.HTTP,
    domain="surface-weather",
    status=Status.PLANNED,
    target="later",
    capabilities=Capabilities(temporal_subset=True),
    variables=[Variable(name="PRCP", units="mm", description="Precipitation total")],
)


def scenario_query() -> Query:
    """The window both scenarios resolve to exactly one asset."""
    return build_query(start="2024-05-06T12:00Z", end="2024-05-06T12:05Z")


def storm_transport(downloads: set[str], *, fail: bool = False) -> httpx.MockTransport:
    """Answer the directory listing the Storm Events adapter reads, then the file it chose."""

    def respond(request: httpx.Request) -> httpx.Response:
        if str(request.url) in downloads:
            return httpx.Response(503 if fail else 200, content=DATA)
        assert str(request.url) == DIRECTORY_URL, request.url
        return httpx.Response(
            200,
            text=f'<table><tr><td><a href="{STORM_NAME}">{STORM_NAME}</a></td>'
            f'<td>2026-03-23</td><td align="right">{len(DATA)}</td></tr></table>',
        )

    return httpx.MockTransport(respond)


class SidecarWriter(HttpProvider):
    """Correct apart from one rule: it writes a sidecar beside the asset it fetched."""

    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve the one synthetic asset, refusing what the synthetic entry does not declare."""
        self.check_params(query)
        self.reject(query, "text", "bbox", "variables", hint="this source publishes one file")
        start, _ = self.utc_window(query)
        return [
            Asset(
                id="demo-2024",
                dataset_id=self.dataset.id,
                href=SYNTHETIC_URL,
                protocol=Protocol.HTTP,
                size=len(DATA),
                time=TimeRange(start=datetime(start.year, 1, 1, tzinfo=UTC)),
            )
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the asset and, against the contract, record what it did beside it."""
        written = http.download(asset.href, dest, self._http())
        dest.with_suffix(".provenance").write_text(asset.href)
        return written


def test_the_shared_checks_pass_against_a_bundled_adapter(tmp_path) -> None:
    dataset = default_registry().get(STORM_ID)
    downloads: set[str] = set()

    def build(client: httpx.Client | None = None) -> Provider:
        return StormEvents(dataset, client)

    check_provider_contract(
        dataset,
        build,
        scenario_query(),
        client_factory=lambda: httpx.Client(transport=storm_transport(downloads)),
        expected_bytes=DATA,
        arm_download=downloads.add,
        failing_client_factory=lambda: httpx.Client(
            transport=storm_transport(downloads, fail=True)
        ),
        work_dir=tmp_path,
    )


def test_an_adapter_that_writes_a_sidecar_is_rejected(tmp_path) -> None:
    """The one rule this adapter breaks is the one the checks have to catch."""
    downloads: set[str] = set()

    def build(client: httpx.Client | None = None) -> Provider:
        return SidecarWriter(SYNTHETIC, client)

    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) in downloads, request.url
        return httpx.Response(200, content=DATA)

    with pytest.raises(AssertionError):
        check_provider_contract(
            SYNTHETIC,
            build,
            scenario_query(),
            client_factory=lambda: httpx.Client(transport=httpx.MockTransport(respond)),
            expected_bytes=DATA,
            arm_download=downloads.add,
            work_dir=tmp_path,
        )
