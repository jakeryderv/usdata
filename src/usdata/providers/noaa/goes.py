"""GOES ABI Level 2 imagery and cloud-top products from anonymous NOAA S3 buckets.

Require ``satellite`` (16, 17, 18, or 19) and both timestamps at most seven days
apart. ``product`` names one bucket directory exactly and defaults to CONUS
``ABI-L2-CMIPC``. The single-channel ``ABI-L2-CMIP*`` products require
``channel`` (1--16 or C01--C16); every other product holds no channel choice and
refuses one. Products ending in ``M`` are mesoscale and require ``sector=M1`` or
``M2``; the rest refuse a sector. Select whole NetCDF files by inclusive
scan-start time, never by scan overlap, from the first archived day of the
product onward. Geographic and variable subsetting are not available for these
archived files. ``list_scans`` is shared with the GLM adapter, which selects files
under the same bucket layout by the same inclusive start-time rule.
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
PUBLIC_START = datetime(2017, 2, 28, tzinfo=UTC)
HEIGHT_START = datetime(2019, 12, 2, tzinfo=UTC)
TEMPERATURE_PRESSURE_START = datetime(2019, 12, 5, tzinfo=UTC)
PHASE_START = datetime(2017, 5, 16, tzinfo=UTC)
# The first UTC day each product directory holds a scene in any of the four buckets, found
# by listing every bucket on 2026-09-29 (docs/providers/noaa-services.md). GOES-16 holds
# each earliest scene; the year-2000 placeholder scenes sit before every one of these days.
PRODUCT_START: dict[str, datetime] = {
    "ABI-L2-CMIPC": PUBLIC_START,
    "ABI-L2-CMIPF": PUBLIC_START,
    "ABI-L2-CMIPM": PUBLIC_START,
    "ABI-L2-MCMIPC": PUBLIC_START,
    "ABI-L2-MCMIPF": PUBLIC_START,
    "ABI-L2-MCMIPM": PUBLIC_START,
    "ABI-L2-ACHAC": HEIGHT_START,
    "ABI-L2-ACHAF": HEIGHT_START,
    "ABI-L2-ACHAM": HEIGHT_START,
    "ABI-L2-ACHTF": TEMPERATURE_PRESSURE_START,
    "ABI-L2-ACHTM": TEMPERATURE_PRESSURE_START,
    "ABI-L2-CTPC": TEMPERATURE_PRESSURE_START,
    "ABI-L2-CTPF": TEMPERATURE_PRESSURE_START,
    "ABI-L2-ACTPC": PHASE_START,
    "ABI-L2-ACTPF": PHASE_START,
    "ABI-L2-ACTPM": HEIGHT_START,  # Mesoscale phase began with cloud-top height.
}
CHANNEL_PRODUCTS = frozenset({"ABI-L2-CMIPC", "ABI-L2-CMIPF", "ABI-L2-CMIPM"})
MAX_WINDOW = timedelta(days=7)
KEY_RE = re.compile(
    r"OR_(?P<family>ABI-L2-(?:M?CMIP|ACHA|ACHT|CTP|ACTP))(?P<sector>[CF]|M[12])-M[346]"
    r"(?:C(?P<channel>0[1-9]|1[0-6]))?"
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
    """Which satellite, product, and channel or mesoscale sector one GOES query selects."""

    model_config = ConfigDict(extra="forbid")

    satellite: Annotated[int, int_range(16, 19)] = Field(
        description="Required GOES satellite number: 16, 17, 18, or 19."
    )
    product: Annotated[str, choice(*PRODUCT_START)] = Field(
        default=PRODUCT,
        description=(
            "ABI product directory, such as ABI-L2-MCMIPC: CMIP (one channel) or MCMIP "
            "(16 channels) imagery, or cloud-top ACHA height, ACHT temperature (F and M only), "
            "CTP pressure (C and F only), or ACTP phase, ending in C (CONUS), F (full disk), "
            "or M (mesoscale). Default ABI-L2-CMIPC."
        ),
    )
    channel: Annotated[int, int_range(1, 16)] | None = Field(
        default=None,
        description="ABI channel, 1 to 16 or C01 to C16. Required for ABI-L2-CMIP products only.",
    )
    sector: Annotated[str, choice("M1", "M2")] | None = Field(
        default=None,
        description="Mesoscale sector M1 or M2. Required for products ending in M only.",
    )

    @field_validator("channel", mode="before")
    @classmethod
    def _drop_the_channel_prefix(cls, value: object) -> object:
        """``C06`` is how the filenames spell channel 6; both reach the same integer."""
        text = value.strip() if isinstance(value, str) else value
        return text[1:] if isinstance(text, str) and text.startswith("C") else text

    @model_validator(mode="after")
    def _selectors_match_product(self) -> Self:
        product = self.product
        problems: list[str] = []
        if product in CHANNEL_PRODUCTS and self.channel is None:
            problems.append(f"channel (1 to 16 or C01 to C16) is required for product={product}")
        if product not in CHANNEL_PRODUCTS and self.channel is not None:
            hint = " (its file holds all 16 bands)" if "MCMIP" in product else ""
            problems.append(
                f"channel is only supported with ABI-L2-CMIPC, CMIPF, or CMIPM, not {product}{hint}"
            )
        if product.endswith("M") and self.sector is None:
            problems.append(f"sector=M1 or M2 is required for mesoscale product={product}")
        if not product.endswith("M") and self.sector is not None:
            problems.append(f"sector is only supported with mesoscale products, not {product}")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def scene(self) -> str:
        """The filename's sector code: C, F, M1, or M2."""
        return self.sector or self.product[-1]


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
    """Whole ABI product files with an explicit product and, where it has one, channel or sector."""

    params_model = GoesAbiParams

    def list_assets(self, query: Query) -> list[Asset]:
        """List complete scenes whose scan starts fall inside the inclusive UTC interval."""
        params = self.parse_params(query, GoesAbiParams)
        self.reject(
            query,
            "bbox",
            "text",
            "variables",
            hint="archived GOES scenes are whole files; select satellite, product, and channel",
        )
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError("GOES requests must span at most 7 days; split longer intervals")
        product, satellite, channel = params.product, params.satellite, params.channel
        first = PRODUCT_START[product]
        if end < first:
            raise QueryError(f"{product} files begin on {first:%Y-%m-%d}")
        family, scene = product[:-1], params.scene
        return list_scans(
            self._http(),
            f"noaa-goes{satellite}",
            product,
            max(start, first),
            end,
            KEY_RE,
            lambda m: (
                m["family"] == family
                and m["sector"] == scene
                and int(m["satellite"]) == satellite
                and (int(m["channel"]) if m["channel"] else None) == channel
            ),
            self.dataset.id,
        )

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the complete archived NetCDF object without modification."""
        return s3.download(asset.href, dest, self._http())
