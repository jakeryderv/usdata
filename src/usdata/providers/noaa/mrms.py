"""MRMS gridded CONUS products from the ``noaa-mrms-pds`` public S3 bucket.

Multi-Radar Multi-Sensor merges every NEXRAD radar with other sensors onto one
fixed CONUS grid every two minutes. Each object is one whole gzipped GRIB2 file
under ``CONUS/<PRODUCT>/<YYYYMMDD>/MRMS_<PRODUCT>_<YYYYMMDD>-<HHMMSS>.grib2.gz``.
Require ``product`` from the allowlist below and both timestamps at most one
day apart; files are selected by their inclusive UTC stamp. Asset ids keep the
upstream filename because the GRIB2 reader names MRMS variables from the
product segment: ecCodes has no parameter tables for MRMS's local discipline.
The public archive begins on 2020-10-14. Only the CONUS domain is served.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import s3
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError

BUCKET = "noaa-mrms-pds"
DOMAIN = "CONUS"
MEDIA_TYPE = "application/x-grib2"
ARCHIVE_START = datetime(2020, 10, 14, tzinfo=UTC)
MAX_WINDOW = timedelta(days=1)
KEY_RE = re.compile(r"MRMS_(?P<product>[A-Za-z0-9_.-]+)_(?P<day>\d{8})-(?P<time>\d{6})\.grib2\.gz")

PRODUCTS: Mapping[str, str] = {
    "RotationTrack30min_00.50": "30-minute maximum low-level azimuthal shear, 0.005 degree grid",
    "RotationTrack60min_00.50": "60-minute maximum low-level azimuthal shear, 0.005 degree grid",
    "RotationTrack120min_00.50": "2-hour maximum low-level azimuthal shear, hourly files",
    "RotationTrackML30min_00.50": "30-minute maximum mid-level azimuthal shear, 0.005 degree grid",
    "RotationTrackML60min_00.50": "60-minute maximum mid-level azimuthal shear, 0.005 degree grid",
    "RotationTrackML120min_00.50": "2-hour maximum mid-level azimuthal shear, hourly files",
    "MergedReflectivityQCComposite_00.50": "quality-controlled composite reflectivity",
    "MergedReflectivityComposite_00.50": "composite reflectivity without quality control",
    "ReflectivityAtLowestAltitude_00.50": "reflectivity at the lowest altitude with data",
    "MergedBaseReflectivityQC_00.50": "quality-controlled base reflectivity",
    "MESH_00.50": "maximum estimated size of hail",
    "MESH_Max_30min_00.50": "30-minute maximum estimated hail size",
    "MESH_Max_60min_00.50": "60-minute maximum estimated hail size",
    "VIL_00.50": "vertically integrated liquid",
    "VIL_Density_00.50": "vertically integrated liquid density",
    "EchoTop_18_00.50": "18 dBZ echo top height",
    "EchoTop_30_00.50": "30 dBZ echo top height",
    "EchoTop_50_00.50": "50 dBZ echo top height",
    "PrecipRate_00.00": "radar precipitation rate",
    "LightningProbabilityNext30minGrid_scale_1": "probability of lightning in the next 30 minutes",
}


def file_time(name: str) -> tuple[str, datetime] | None:
    """``(product, UTC stamp)`` parsed from one MRMS filename, or None for other objects."""
    match = KEY_RE.fullmatch(name)
    if match is None:
        return None
    try:
        stamp = datetime.strptime(match["day"] + match["time"], "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return match["product"], stamp.replace(tzinfo=UTC)


class MrmsParams(BaseModel):
    """Which one of the gridded CONUS products an MRMS query downloads."""

    model_config = ConfigDict(extra="forbid")

    product: str = Field(
        description="Required product directory name, for example RotationTrackML30min_00.50; "
        "see the dataset guide for the supported list."
    )

    @field_validator("product", mode="before")
    @classmethod
    def _one_directory_name(cls, value: object) -> object:
        """A product names one bucket directory, so only a non-empty string can be one."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty string, for example RotationTrackML30min_00.50")
        return value.strip()

    @model_validator(mode="after")
    def _product_is_served(self) -> MrmsParams:
        """Directory names are case-sensitive upstream, so a near miss is named, not accepted."""
        if self.product not in PRODUCTS:
            hint = next(
                (name for name in PRODUCTS if name.lower() == self.product.lower()),
                None,
            )
            suggestion = f"; did you mean {hint}?" if hint else ""
            raise ValueError(
                f"unknown MRMS product {self.product!r}{suggestion}; supported products are "
                + ", ".join(PRODUCTS)
            )
        return self


class Mrms(_HttpProvider):
    """Whole two-minute MRMS CONUS GRIB2 files; params: product."""

    params_model = MrmsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """List files of one product whose stamps fall inside the inclusive UTC interval."""
        params = self.parse_params(query, MrmsParams)
        self.reject(
            query,
            "bbox",
            "text",
            "variables",
            hint="MRMS files are whole CONUS grids; select a product and a window",
        )
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError("MRMS requests must span at most 1 day; split longer intervals")
        product = params.product
        if end < ARCHIVE_START:
            raise QueryError(
                f"the {BUCKET} archive begins on {ARCHIVE_START:%Y-%m-%d}; "
                f"earlier MRMS products are not available here"
            )
        start = max(start, ARCHIVE_START)
        assets: dict[str, Asset] = {}
        day = start.date()
        while day <= end.date():
            prefix = f"{DOMAIN}/{product}/{day:%Y%m%d}/"
            for obj in s3.list_objects(BUCKET, prefix, self._http()):
                if not obj.key.startswith(prefix):
                    continue
                name = obj.key.removeprefix(prefix)
                parsed = file_time(name)
                if parsed is None or parsed[0] != product or not start <= parsed[1] <= end:
                    continue
                assets[obj.key] = Asset(
                    id=name,
                    dataset_id=self.dataset.id,
                    href=f"s3://{BUCKET}/{obj.key}",
                    protocol=Protocol.S3,
                    media_type=MEDIA_TYPE,
                    size=obj.size,
                    time=TimeRange(start=parsed[1], end=parsed[1]),
                )
            day += timedelta(days=1)
        return sorted(assets.values(), key=lambda asset: asset.id)

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the complete gzipped GRIB2 object without modification."""
        return s3.download(asset.href, dest, self._http())
