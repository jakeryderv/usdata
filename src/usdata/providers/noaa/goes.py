"""GOES ABI CONUS Cloud and Moisture Imagery from anonymous NOAA S3 buckets.

Require ``satellite`` (16, 17, 18, or 19), ``channel`` (1--16 or C01--C16), and
both timestamps at most seven days apart. The optional ``product`` must be
``ABI-L2-CMIPC``. Select whole single-channel NetCDF files by inclusive
scan-start time, never by scan overlap.
Geographic and variable subsetting are not available for these archived files.
``list_scans`` is shared with the GLM adapter, which selects files under the
same bucket layout by the same inclusive start-time rule.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import httpx

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import s3
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

PRODUCT = "ABI-L2-CMIPC"
PUBLIC_START = datetime(2017, 2, 28, tzinfo=UTC)
MAX_WINDOW = timedelta(days=7)
KEY_RE = re.compile(
    r"OR_ABI-L2-CMIPC-M[346]C(?P<channel>0[1-9]|1[0-6])_G(?P<satellite>1[6-9])"
    r"_s(?P<start>\d{14})_e(?P<end>\d{14})_c\d{14}\.nc"
)


def _timestamp(raw: str) -> datetime:
    stamp = datetime.strptime(raw, "%Y%j%H%M%S%f").replace(tzinfo=UTC)
    # strptime accepts day 366 in a non-leap year by spilling into the next year.
    if stamp.strftime("%Y%j%H%M%S") + str(stamp.microsecond // 100000) != raw:
        raise ValueError("invalid GOES timestamp")
    return stamp


def number(raw: object, label: str, low: int, high: int) -> int:
    """Parse a bounded integer parameter, accepting ``C``-prefixed channel labels."""
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise QueryError(f"{label} must be an integer from {low} to {high}")
    text = str(raw).strip()
    if label == "channel" and text.startswith("C"):
        text = text[1:]
    if not text.isascii() or not text.isdigit() or not low <= int(text) <= high:
        raise QueryError(f"{label} must be an integer from {low} to {high}")
    return int(text)


def list_scans(
    client: httpx.Client,
    bucket: str,
    product: str,
    start: datetime,
    end: datetime,
    key_re: re.Pattern[str],
    keep: Callable[[re.Match[str]], bool],
    dataset_id: str,
) -> list[Asset]:
    """List whole GOES product files whose start stamps fall in the inclusive UTC window.

    Every hourly ``PRODUCT/YYYY/DDD/HH/`` prefix touching the window is listed.
    ``key_re`` must name ``start`` and ``end`` groups; ``keep`` decides whether a
    matching filename belongs to the query. Files are selected by their start
    stamp only, never because they overlap the window.
    """
    hour = start.replace(minute=0, second=0, microsecond=0)
    assets: dict[str, Asset] = {}
    while hour <= end:
        prefix = f"{product}/{hour:%Y/%j/%H}/"
        for obj in s3.list_objects(bucket, prefix, client):
            if not obj.key.startswith(prefix):
                continue
            name = obj.key.removeprefix(prefix)
            match = key_re.fullmatch(name)
            if match is None or not keep(match):
                continue
            try:
                scan_start, scan_end = _timestamp(match["start"]), _timestamp(match["end"])
            except ValueError:
                continue
            if scan_end < scan_start or not start <= scan_start <= end:
                continue
            assets[obj.key] = Asset(
                id=name,
                dataset_id=dataset_id,
                href=f"s3://{bucket}/{obj.key}",
                protocol=Protocol.S3,
                media_type="application/x-netcdf",
                size=obj.size,
                time=TimeRange(start=scan_start, end=scan_end),
            )
        hour += timedelta(hours=1)
    return sorted(assets.values(), key=lambda asset: asset.id)


class GoesAbi(_HttpProvider):
    """Single-channel CONUS ABI imagery; params: satellite, channel, product."""

    accepted_params: ClassVar[Mapping[str, str]] = {
        "satellite": "Required GOES satellite number: 16, 17, 18, or 19.",
        "channel": "Required ABI channel, 1 to 16 or C01 to C16.",
        "product": f"ABI product; only {PRODUCT} is supported.",
    }

    def list_assets(self, query: Query) -> list[Asset]:
        """List complete scenes whose scan starts fall inside the inclusive UTC interval."""
        self.check_params(query)
        if query.params.get("product", PRODUCT) != PRODUCT:
            raise QueryError(f"only product={PRODUCT} is supported")
        self.reject(
            query,
            "bbox",
            "text",
            "variables",
            hint="archived GOES scenes are whole files; select satellite and channel",
        )
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError("GOES requests must span at most 7 days; split longer intervals")
        satellite = number(query.params.get("satellite"), "satellite", 16, 19)
        channel = number(query.params.get("channel"), "channel", 1, 16)
        if end < PUBLIC_START:
            raise QueryError("GOES CMIPC public observations begin on 2017-02-28")
        start = max(start, PUBLIC_START)
        return list_scans(
            self._http(),
            f"noaa-goes{satellite}",
            PRODUCT,
            start,
            end,
            KEY_RE,
            lambda m: int(m["satellite"]) == satellite and int(m["channel"]) == channel,
            self.dataset.id,
        )

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the complete archived NetCDF object without modification."""
        return s3.download(asset.href, dest, self._http())
