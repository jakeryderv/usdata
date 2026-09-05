"""Core data model shared by every provider, protocol, and the CLI.

The shapes are deliberately STAC-like: a ``Dataset`` corresponds to a STAC
Collection, an ``Asset`` to a file-level STAC Asset. Keeping this alignment
lets STAC-backed sources map in without translation layers.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Protocol(StrEnum):
    """Access mechanism used to reach a dataset's files."""

    HTTP = "http"
    S3 = "s3"
    ERDDAP = "erddap"
    OPENDAP = "opendap"
    THREDDS = "thredds"


class Status(StrEnum):
    """How far along a dataset's support is."""

    AVAILABLE = "available"  # adapter implemented and tested
    STUB = "stub"  # registered with an adapter class that is not implemented yet
    PLANNED = "planned"  # registry entry only; no adapter


class ProviderInfo(BaseModel):
    """An agency or program that publishes datasets."""

    id: str
    name: str
    homepage: str | None = None


class DomainInfo(BaseModel):
    """A subject area datasets are grouped under, shared across providers."""

    id: str
    name: str


VERSION_RE = re.compile(r"^\d+\.\d+$")
LATER = "later"


def _check_version(value: str | None, field: str) -> None:
    if value is not None and value != LATER and not VERSION_RE.match(value):
        raise ValueError(f"{field} must be a minor version like '0.4' or '{LATER}'")


class BBox(BaseModel):
    """Geographic bounding box in WGS84 degrees. Antimeridian crossing is not supported yet."""

    model_config = ConfigDict(frozen=True)

    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def _ordered(self) -> BBox:
        if self.west > self.east:
            raise ValueError("west must be <= east (antimeridian crossing unsupported)")
        if self.south > self.north:
            raise ValueError("south must be <= north")
        return self

    @classmethod
    def from_point(cls, lat: float, lon: float, radius_km: float = 0.0) -> BBox:
        """Box around a point. Uses a flat-earth approximation, fine for small radii."""
        dlat = radius_km / 111.0
        dlon = radius_km / (111.0 * max(math.cos(math.radians(lat)), 1e-6))
        return cls(
            west=max(lon - dlon, -180),
            south=max(lat - dlat, -90),
            east=min(lon + dlon, 180),
            north=min(lat + dlat, 90),
        )

    def intersects(self, other: BBox) -> bool:
        """True if the boxes share any area, edges included."""
        return not (
            other.west > self.east
            or other.east < self.west
            or other.south > self.north
            or other.north < self.south
        )

    def contains_point(self, lat: float, lon: float) -> bool:
        """True if the point lies inside or on the edge of the box."""
        return self.west <= lon <= self.east and self.south <= lat <= self.north

    def as_tuple(self) -> tuple[float, float, float, float]:
        """The box as (west, south, east, north)."""
        return (self.west, self.south, self.east, self.north)


class TimeRange(BaseModel):
    """Half-open-agnostic time interval. Either bound may be None to mean unbounded."""

    model_config = ConfigDict(frozen=True)

    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode="after")
    def _ordered(self) -> TimeRange:
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start must be <= end")
        return self

    def overlaps(self, other: TimeRange) -> bool:
        """True if the ranges share any instant; open bounds match everything on that side."""
        starts_after = self.start is not None and other.end is not None and self.start > other.end
        ends_before = self.end is not None and other.start is not None and self.end < other.start
        return not (starts_after or ends_before)


class Capabilities(BaseModel):
    """What a source can do server-side. Anything False means usdata fetches whole files."""

    spatial_subset: bool = False
    temporal_subset: bool = False
    variable_subset: bool = False


class Dataset(BaseModel):
    """A registry entry. One per curated dataset, identified as ``provider:name``."""

    id: str
    provider: str
    title: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    protocol: Protocol
    homepage: str | None = None
    license: str | None = None
    spatial_extent: BBox | None = None
    temporal_extent: TimeRange | None = None
    capabilities: Capabilities = Field(default_factory=Capabilities)
    domain: str = Field(description="Id of a domain declared in the registry")
    status: Status
    since: str | None = Field(default=None, description="Version an available dataset shipped in")
    target: str | None = Field(
        default=None, description="Version a stub or planned dataset is aimed at, or 'later'"
    )
    adapter: str | None = Field(
        default=None,
        description="'package.module:ClassName' of the Provider; required unless planned",
    )

    @model_validator(mode="after")
    def _consistent(self) -> Dataset:
        prefix = f"{self.provider}:"
        if not self.id.startswith(prefix) or len(self.id) <= len(prefix):
            raise ValueError(f"dataset id {self.id!r} must be '{self.provider}:<name>'")
        if self.status is Status.PLANNED:
            if self.adapter is not None:
                raise ValueError("planned datasets must not name an adapter")
        elif self.adapter is None or ":" not in self.adapter:
            raise ValueError(
                f"{self.status.value} datasets need adapter 'package.module:ClassName'"
            )
        _check_version(self.since, "since")
        _check_version(self.target, "target")
        if self.status is Status.AVAILABLE:
            if self.since is None or self.since == LATER:
                raise ValueError("available datasets must state the version they shipped in")
            if self.target is not None:
                raise ValueError("available datasets have no target")
        elif self.target is None:
            raise ValueError(f"{self.status.value} datasets need a target version or 'later'")
        return self

    @property
    def version_label(self) -> str:
        """'since 0.2' for shipped datasets, 'target 0.4' or 'target later' otherwise."""
        if self.status is Status.AVAILABLE:
            return f"since {self.since}"
        return f"target {self.target}"

    @property
    def name(self) -> str:
        """The dataset name without the provider prefix."""
        return self.id.split(":", 1)[1]


class Query(BaseModel):
    """Normalized, provider-agnostic request. Providers translate this into their own terms."""

    text: str | None = None
    provider: str | None = None
    bbox: BBox | None = None
    time: TimeRange | None = None
    variables: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific passthrough parameters"
    )


class Asset(BaseModel):
    """A single retrievable object (file, granule, or subset request) from a dataset."""

    id: str
    dataset_id: str
    href: str
    protocol: Protocol
    media_type: str | None = None
    size: int | None = Field(default=None, ge=0)
    checksum: str | None = Field(default=None, description="'<algo>:<hex>', e.g. 'sha256:ab12...'")
    time: TimeRange | None = None
    bbox: BBox | None = None


class Provenance(BaseModel):
    """Everything needed to say where a local file came from and re-fetch it."""

    dataset_id: str
    provider: str
    source_url: str
    retrieved_at: datetime
    checksum: str
    size: int = Field(ge=0)
    license: str | None = None
    usdata_version: str
    transformations: list[str] = Field(default_factory=list)
