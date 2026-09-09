"""GOES ABI CONUS Cloud and Moisture Imagery from anonymous NOAA S3 buckets.

Require ``satellite`` (16, 17, 18, or 19), ``channel`` (1--16 or C01--C16), and
both timestamps. The optional ``product`` must be ``ABI-L2-CMIPC``. Select whole
single-channel NetCDF files by inclusive scan-start time, never by scan overlap.
Geographic and variable subsetting are not available for these archived files.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from usdata.models import Asset, Dataset, Protocol, Query, TimeRange
from usdata.protocols import http, s3
from usdata.providers.base import Provider, QueryError

PRODUCT = "ABI-L2-CMIPC"
PUBLIC_START = datetime(2017, 2, 28, tzinfo=UTC)
KEY_RE = re.compile(
    r"OR_ABI-L2-CMIPC-M[346]C(?P<channel>0[1-9]|1[0-6])_G(?P<satellite>1[6-9])"
    r"_s(?P<start>\d{14})_e(?P<end>\d{14})_c\d{14}\.nc"
)


def _timestamp(raw: str) -> datetime:
    stamp = datetime.strptime(raw, "%Y%j%H%M%S%f").replace(tzinfo=UTC)
    # strptime accepts day 366 in a non-leap year by spilling into the next year.
    if stamp.strftime("%Y%j%H%M%S") + str(stamp.microsecond // 100000) != raw:
        raise ValueError("invalid ABI timestamp")
    return stamp


def _number(raw: object, label: str, low: int, high: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise QueryError(f"{label} must be an integer from {low} to {high}")
    text = str(raw).strip()
    if label == "channel" and text.startswith("C"):
        text = text[1:]
    if not text.isascii() or not text.isdigit() or not low <= int(text) <= high:
        raise QueryError(f"{label} must be an integer from {low} to {high}")
    return int(text)


class GoesAbi(Provider):
    """Single-channel CONUS ABI imagery; params: satellite, channel, product."""

    def __init__(self, dataset: Dataset, client: httpx.Client | None = None) -> None:
        super().__init__(dataset)
        self._client = client
        self._owns_client = client is None

    def close(self) -> None:
        """Close the owned HTTP client, leaving injected clients to their caller."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = http.client()
        return self._client

    def list_assets(self, query: Query) -> list[Asset]:
        """List complete scenes whose scan starts fall inside the inclusive UTC interval."""
        if unknown := set(query.params) - {"satellite", "channel", "product"}:
            raise QueryError(f"unsupported GOES params: {', '.join(sorted(unknown))}")
        if query.params.get("product", PRODUCT) != PRODUCT:
            raise QueryError(f"only product={PRODUCT} is supported")
        if query.bbox is not None:
            raise QueryError(
                "GOES imagery has no geographic subsetting; omit location/bbox/lat/lon"
            )
        if query.text:
            raise QueryError("GOES imagery has no text filtering; select satellite and channel")
        if query.variables:
            raise QueryError("GOES imagery has no variable subsetting; select a channel instead")
        if query.time is None or query.time.start is None or query.time.end is None:
            raise QueryError(f"{self.dataset.id} requires both start and end times")
        satellite = _number(query.params.get("satellite"), "satellite", 16, 19)
        channel = _number(query.params.get("channel"), "channel", 1, 16)
        start = query.time.start.replace(tzinfo=query.time.start.tzinfo or UTC).astimezone(UTC)
        end = query.time.end.replace(tzinfo=query.time.end.tzinfo or UTC).astimezone(UTC)
        if end < PUBLIC_START:
            raise QueryError("GOES CMIPC public observations begin on 2017-02-28")
        start = max(start, PUBLIC_START)
        hour = start.replace(minute=0, second=0, microsecond=0)
        bucket = f"noaa-goes{satellite}"
        assets: dict[str, Asset] = {}
        while hour <= end:
            prefix = f"{PRODUCT}/{hour:%Y/%j/%H}/"
            for obj in s3.list_objects(bucket, prefix, self._http()):
                if not obj.key.startswith(prefix):
                    continue
                name = obj.key.removeprefix(prefix)
                match = KEY_RE.fullmatch(name)
                if (
                    match is None
                    or int(match["satellite"]) != satellite
                    or int(match["channel"]) != channel
                ):
                    continue
                try:
                    scan_start, scan_end = _timestamp(match["start"]), _timestamp(match["end"])
                except ValueError:
                    continue
                if scan_end < scan_start or not start <= scan_start <= end:
                    continue
                assets[obj.key] = Asset(
                    id=name,
                    dataset_id=self.dataset.id,
                    href=f"s3://{bucket}/{obj.key}",
                    protocol=Protocol.S3,
                    media_type="application/x-netcdf",
                    size=obj.size,
                    time=TimeRange(start=scan_start, end=scan_end),
                )
            hour += timedelta(hours=1)
        return sorted(assets.values(), key=lambda asset: asset.id)

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the complete archived NetCDF object without modification."""
        return s3.download(asset.href, dest, self._http())
