"""GOES ABI Cloud and Moisture Imagery from anonymous NOAA S3 buckets.

Require ``satellite`` (16, 17, 18, or 19), ``channel`` (1--16 or C01--C16), and
both timestamps at most seven days apart. ``product`` defaults to CONUS
``ABI-L2-CMIPC``; ``ABI-L2-CMIPM`` requires ``sector=M1`` or ``M2``.
Select whole single-channel NetCDF files by inclusive
scan-start time, never by scan overlap.
Geographic and variable subsetting are not available for these archived files.
``list_scans`` is shared with the GLM adapter, which selects files under the
same bucket layout by the same inclusive start-time rule.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import choice, int_range

PRODUCT = "ABI-L2-CMIPC"
MESOSCALE_PRODUCT = "ABI-L2-CMIPM"
PUBLIC_START = datetime(2017, 2, 28, tzinfo=UTC)
MAX_WINDOW = timedelta(days=7)
KEY_RE = re.compile(
    r"OR_ABI-L2-CMIP(?P<sector>C|M[12])-M[346]C(?P<channel>0[1-9]|1[0-6])"
    r"_G(?P<satellite>1[6-9])"
    r"_s(?P<start>\d{14})_e(?P<end>\d{14})_c\d{14}\.nc"
)


def _timestamp(raw: str) -> datetime:
    stamp = datetime.strptime(raw, "%Y%j%H%M%S%f").replace(tzinfo=UTC)
    # strptime accepts day 366 in a non-leap year by spilling into the next year.
    if stamp.strftime("%Y%j%H%M%S") + str(stamp.microsecond // 100000) != raw:
        raise ValueError("invalid GOES timestamp")
    return stamp


class GoesAbiParams(BaseModel):
    """Which satellite, which ABI channel, and which product one GOES query selects."""

    model_config = ConfigDict(extra="forbid")

    satellite: Annotated[int, int_range(16, 19)] = Field(
        description="Required GOES satellite number: 16, 17, 18, or 19."
    )
    channel: Annotated[int, int_range(1, 16)] = Field(
        description="Required ABI channel, 1 to 16 or C01 to C16."
    )
    product: Annotated[str, choice(PRODUCT, MESOSCALE_PRODUCT)] = Field(
        default=PRODUCT,
        description="ABI-L2-CMIPC (CONUS, default) or ABI-L2-CMIPM (mesoscale).",
    )
    sector: Annotated[str, choice("M1", "M2")] | None = Field(
        default=None,
        description="Required for ABI-L2-CMIPM: M1 or M2. Omit for CONUS.",
    )

    @field_validator("channel", mode="before")
    @classmethod
    def _drop_the_channel_prefix(cls, value: object) -> object:
        """``C06`` is how the filenames spell channel 6; both reach the same integer."""
        text = value.strip() if isinstance(value, str) else value
        return text[1:] if isinstance(text, str) and text.startswith("C") else text

    @model_validator(mode="after")
    def _sector_matches_product(self) -> Self:
        if self.product == MESOSCALE_PRODUCT and self.sector is None:
            raise ValueError("sector=M1 or M2 is required for product=ABI-L2-CMIPM")
        if self.product == PRODUCT and self.sector is not None:
            raise ValueError("sector is only supported with product=ABI-L2-CMIPM")
        return self


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


class GoesAbi(HttpProvider):
    """Single-channel CONUS or mesoscale ABI imagery with explicit sector selection."""

    params_model = GoesAbiParams

    def list_assets(self, query: Query) -> list[Asset]:
        """List complete scenes whose scan starts fall inside the inclusive UTC interval."""
        params = self.parse_params(query, GoesAbiParams)
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
        satellite, channel = params.satellite, params.channel
        if end < PUBLIC_START:
            raise QueryError("GOES ABI public observations begin on 2017-02-28")
        start = max(start, PUBLIC_START)
        return list_scans(
            self._http(),
            f"noaa-goes{satellite}",
            params.product,
            start,
            end,
            KEY_RE,
            lambda m: (
                int(m["satellite"]) == satellite
                and int(m["channel"]) == channel
                and m["sector"] == (params.sector or "C")
            ),
            self.dataset.id,
        )

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the complete archived NetCDF object without modification."""
        return s3.download(asset.href, dest, self._http())
