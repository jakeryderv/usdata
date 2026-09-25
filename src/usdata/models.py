"""Core data model shared by every provider, protocol, and the CLI.

The shapes are deliberately STAC-like: a ``Dataset`` corresponds to a STAC
Collection, an ``Asset`` to a file-level STAC Asset. Keeping this alignment
lets STAC-backed sources map in without translation layers.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def as_utc(value: datetime) -> datetime:
    """The shared time policy: a naive datetime means UTC, an aware one converts to UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


AwareUTC = Annotated[datetime, AfterValidator(as_utc)]
"""A datetime field stored as aware UTC whatever it was given; see :func:`as_utc`."""


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


def as_sha256(value: str) -> str:
    """A checksum in the one form usdata computes and compares: ``sha256:`` and lowercase hex."""
    algorithm, sep, digest = value.partition(":")
    normal = f"{algorithm.lower()}{sep}{digest.lower()}"
    if not _SHA256.fullmatch(normal):
        raise ValueError(f"checksum must be 'sha256:' and 64 hex digits, not {value!r}")
    return normal


Sha256 = Annotated[str, AfterValidator(as_sha256)]
"""A checksum field holding ``sha256:<hex>``, lowercased; see :func:`as_sha256`."""


class Protocol(StrEnum):
    """Access mechanism used to reach a dataset's files."""

    HTTP = "http"
    S3 = "s3"
    ERDDAP = "erddap"


class Status(StrEnum):
    """How far along a dataset's support is."""

    AVAILABLE = "available"  # adapter implemented and tested
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


class SystemInfo(BaseModel):
    """A product family or service one provider publishes several datasets through.

    Ids are conventionally ``provider:name``; ``provider`` is what the registry
    checks an entry against.
    """

    id: str
    name: str
    homepage: str | None = None
    provider: str


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
        if not math.isfinite(lat) or not -90 <= lat <= 90:
            raise ValueError("lat must be finite and between -90 and 90")
        if not math.isfinite(lon) or not -180 <= lon <= 180:
            raise ValueError("lon must be finite and between -180 and 180")
        if not math.isfinite(radius_km) or radius_km < 0:
            raise ValueError("radius_km must be finite and nonnegative")
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

    start: AwareUTC | None = None
    end: AwareUTC | None = None

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
    """Which query dimensions a source honours when selecting what to fetch.

    ``spatial_subset`` and ``variable_subset`` mean the request narrows the
    bytes served, so a bbox or a variable list changes the files.
    ``place_subset`` means a named state or county selects what is served, which
    is a separate question: a source keyed by FIPS code honours a place and
    must refuse a bare rectangle, which names no place (ADR 0034).
    ``temporal_subset`` means the time window chooses which assets are fetched,
    whether the source crops files to it or serves whole files that cover it.
    ``partial_fetch`` means selected byte ranges of an object can be fetched on
    their own. A false value means the adapter refuses that query field. The
    adapter contract tests verify each declaration against the adapter.
    """

    spatial_subset: bool = False
    place_subset: bool = False
    temporal_subset: bool = False
    variable_subset: bool = False
    partial_fetch: bool = False


READER_EXTRAS = ("pandas", "radar", "netcdf", "grib")
READER_EXTRAS_TEXT = ", ".join(READER_EXTRAS)


def _check_line(value: str | None, field: str) -> None:
    if value is not None and (not value.strip() or "\n" in value):
        raise ValueError(f"{field} must be a nonempty single line")


def _check_repo_path(value: str, field: str, parent: str, suffixes: set[str]) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.is_relative_to(parent):
        raise ValueError(f"{field} must be a repository-relative path inside {parent}")
    if path.suffix not in suffixes:
        raise ValueError(f"{field} must name a {' or '.join(sorted(suffixes))} file")


def describe_duration(value: timedelta) -> str:
    """A duration in words: '1 day', '28 days', '6 hours', down to whole seconds."""
    seconds = int(value.total_seconds())
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)):
        if seconds % size == 0:
            count = seconds // size
            return f"{count} {unit}" if count == 1 else f"{count} {unit}s"
    return f"{value.total_seconds():g} seconds"


class Resolution(BaseModel):
    """How fine a dataset is in space and time, in the source's own words.

    Free text on purpose: agencies describe grids, station spacing, and scan
    cadence differently, and no filter needs the values structured yet.
    """

    spatial: str | None = Field(default=None, description="Grid spacing, footprint, or sampling")
    temporal: str | None = Field(default=None, description="Spacing between successive values")

    @model_validator(mode="after")
    def _single_lines(self) -> Resolution:
        _check_line(self.spatial, "resolution.spatial")
        _check_line(self.temporal, "resolution.temporal")
        return self


class Variable(BaseModel):
    """One variable a dataset delivers, named as the source names it."""

    name: str
    units: str | None = Field(default=None, description="Units as delivered, not as converted")
    description: str | None = Field(default=None, description="What the variable measures")

    @model_validator(mode="after")
    def _single_lines(self) -> Variable:
        _check_line(self.name, "variable name")
        _check_line(self.units, "variable units")
        _check_line(self.description, "variable description")
        return self

    @property
    def label(self) -> str:
        """'name (units)' where units are known, otherwise the bare name."""
        return f"{self.name} ({self.units})" if self.units else self.name


CREDENTIAL_VARIABLE = re.compile(r"USDATA_[A-Z0-9]+(?:_[A-Z0-9]+)+")
"""How a credential variable is named: ``USDATA_<SYSTEM>_<FIELD>``, such as ``USDATA_AQS_KEY``."""


class CredentialSpec(BaseModel):
    """The environment variables a source needs before it can be contacted, and where to get a key.

    Declared in the registry entry so the catalog, ``info``, and ``doctor`` can
    say what a dataset needs, and so the core can check it before any request
    (ADR 0039). Values never appear here or anywhere else the core writes.
    """

    variables: list[str] = Field(
        min_length=1, description="Environment variables that must be set, USDATA_<SYSTEM>_<FIELD>"
    )
    signup: str = Field(description="https URL where the agency issues a key")

    @model_validator(mode="after")
    def _named(self) -> CredentialSpec:
        for name in self.variables:
            if not CREDENTIAL_VARIABLE.fullmatch(name):
                raise ValueError(
                    f"credential variable {name!r} must be named USDATA_<SYSTEM>_<FIELD>"
                )
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("credentials.variables entries must be distinct")
        if not self.signup.startswith("https://"):
            raise ValueError("credentials.signup must be an https URL")
        return self


class Limits(BaseModel):
    """Request limits the adapter enforces, declared here and verified by the adapter tests."""

    max_window: timedelta | None = Field(
        default=None, description="Longest query interval, as an ISO 8601 duration such as 'P1D'"
    )

    @model_validator(mode="after")
    def _positive(self) -> Limits:
        if self.max_window is not None and self.max_window <= timedelta(0):
            raise ValueError("limits.max_window must be a positive duration")
        return self


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
    summary: str | None = Field(
        default=None, max_length=80, description="One-line label shown by the docs, site, and CLI"
    )
    formats: list[str] = Field(
        default_factory=list, description="File formats this dataset delivers, as delivered"
    )
    selection: str | None = Field(
        default=None, max_length=160, description="What one query selects, in a single sentence"
    )
    inputs: str | None = Field(
        default=None, max_length=200, description="What a caller must supply to fetch anything"
    )
    reader: str | None = Field(
        default=None,
        description=f"Extra that opens the files ({READER_EXTRAS_TEXT}); None means bytes only",
    )
    guide: str | None = Field(
        default=None, description="Repository-relative path to the handwritten usage guide"
    )
    examples: list[str] = Field(
        default_factory=list,
        description="Repository-relative paths to worked examples using this dataset",
    )
    resolution: Resolution | None = Field(
        default=None, description="How fine the data are in space and time"
    )
    update_frequency: str | None = Field(
        default=None, description="How often the source publishes new data"
    )
    latency: str | None = Field(
        default=None,
        description="How far behind real time the source runs, as the agency states it",
    )
    citation: str | None = Field(
        default=None, description="How the agency asks to be cited, in one line"
    )
    terms: str | None = Field(
        default=None, description="https URL of the source's stated conditions of use"
    )
    variables: list[Variable] = Field(
        default_factory=list,
        description="Variables the dataset delivers; a sample where the set is open-ended",
    )
    limits: Limits | None = Field(
        default=None, description="Request limits the adapter enforces, such as the longest window"
    )
    credentials: CredentialSpec | None = Field(
        default=None,
        description="Environment variables the source needs before it can be contacted (ADR 0039)",
    )
    system: str | None = Field(
        default=None,
        description="Id of a system declared in the registry, for datasets that belong to one",
    )
    domain: str = Field(description="Id of a domain declared in the registry")
    status: Status
    since: str | None = Field(default=None, description="Version an available dataset shipped in")
    target: str | None = Field(
        default=None, description="Version a planned dataset is aimed at, or 'later'"
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
        self._check_usage()
        return self

    def _check_usage(self) -> None:
        """Documentation metadata: single lines, known extras, and safe relative paths."""
        _check_line(self.summary, "summary")
        _check_line(self.selection, "selection")
        _check_line(self.inputs, "inputs")
        for value in self.formats:
            _check_line(value, "formats entries")
        if self.reader is not None and self.reader not in READER_EXTRAS:
            raise ValueError(f"reader must name a known extra ({READER_EXTRAS_TEXT})")
        if self.guide is not None:
            _check_repo_path(self.guide, "guide", "docs/providers", {".md"})
        for example in self.examples:
            _check_repo_path(example, "examples entries", "examples", {".md", ".ipynb"})
        if self.status is Status.AVAILABLE and not (self.summary and self.formats):
            raise ValueError("available datasets need a summary and at least one format")
        self._check_description()

    def _check_description(self) -> None:
        """Descriptive metadata: single lines, an https terms URL, and distinct variable names."""
        _check_line(self.update_frequency, "update_frequency")
        _check_line(self.latency, "latency")
        _check_line(self.citation, "citation")
        _check_line(self.terms, "terms")
        if self.terms is not None and not self.terms.startswith("https://"):
            raise ValueError("terms must be an https URL")
        names = [variable.name for variable in self.variables]
        if len(set(names)) != len(names):
            raise ValueError("variables entries must have distinct names")

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


class Place(BaseModel):
    """The state or county a ``location`` named, as the bundled Census table identifies it.

    A rectangle cannot be turned back into the place it was drawn around, so a
    query keeps this beside its ``bbox`` for the sources that are keyed by FIPS
    code rather than by coordinates. See ADR 0034.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["state", "county"]
    geoid: str = Field(
        pattern=r"^\d{2}(\d{3})?$",
        description="Census GEOID: the two-digit state FIPS code, or the five-digit county one",
    )
    label: str = Field(description="The place as the table names it, such as 'Osage County, OK'")
    state: str = Field(
        pattern=r"^[A-Z]{2}$",
        description=(
            "Two-letter postal code of the state, or of the state a county lies in, such as OK; "
            "some sources key places by it rather than by the state FIPS code"
        ),
    )

    @model_validator(mode="after")
    def _kind_matches_geoid(self) -> Place:
        if (self.kind == "state") is not (len(self.geoid) == 2):
            raise ValueError(f"a {self.kind} geoid cannot be {self.geoid!r}")
        return self

    @property
    def state_fips(self) -> str:
        """The two-digit FIPS code of the state, or of the state a county lies in."""
        return self.geoid[:2]

    @property
    def county_fips(self) -> str | None:
        """The three-digit county FIPS code within its state, or None for a state."""
        return self.geoid[2:] or None


class Query(BaseModel):
    """Normalized, provider-agnostic request. Providers translate this into their own terms."""

    text: str | None = None
    provider: str | None = None
    bbox: BBox | None = None
    place: Place | None = Field(
        default=None,
        description=(
            "The state or county the spatial filter named, set only when it was given as a "
            "location; bbox still holds that place's rectangle"
        ),
    )
    time: TimeRange | None = None
    variables: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific passthrough parameters"
    )

    @model_validator(mode="after")
    def _place_has_its_box(self) -> Query:
        # Most adapters read only bbox, so a place without one would select nothing for them.
        if self.place is not None and self.bbox is None:
            raise ValueError("a query naming a place must carry that place's bbox")
        return self


class Asset(BaseModel):
    """A single retrievable object (file, granule, or subset request) from a dataset."""

    id: str
    dataset_id: str
    href: str
    protocol: Protocol
    media_type: str | None = None
    size: int | None = Field(default=None, ge=0)
    checksum: Sha256 | None = Field(default=None, description="'sha256:<hex>' of the file's bytes")
    time: TimeRange | None = None
    bbox: BBox | None = None
    properties: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Facts of the request the bytes do not state, such as the unit system, datum, "
            "or station, keyed in lowercase snake case; readers copy them into "
            "attrs['usdata']['properties'] (ADR 0043)"
        ),
    )


class ByteRange(BaseModel):
    """One inclusive byte interval of a remote object, as an HTTP ``Range`` names it."""

    model_config = ConfigDict(frozen=True)

    start: int = Field(ge=0)
    end: int = Field(ge=0, description="Last byte of the interval, inclusive, as HTTP counts it")

    @model_validator(mode="after")
    def _ordered(self) -> ByteRange:
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self

    @property
    def length(self) -> int:
        """How many bytes the interval covers."""
        return self.end - self.start + 1

    @property
    def header(self) -> str:
        """The interval as an HTTP ``Range`` header value."""
        return f"bytes={self.start}-{self.end}"


PARTIAL_FRAGMENT = "messages"
"""Href fragment key naming the GRIB2 messages a partial asset selects."""


class PartialFetch(BaseModel):
    """The byte ranges one partial asset resolved to, and the object they were read from.

    An adapter builds this while listing, the core records it in the provenance
    sidecar, and a restore rebuilds it from that sidecar, so re-fetching a pinned
    partial asset never re-reads an index.
    """

    object_url: str = Field(description="The whole object the ranges are read from")
    object_size: int = Field(ge=0, description="Size of that object when the ranges were resolved")
    object_etag: str = Field(description="ETag sent as ``If-Match`` on every range request")
    index_url: str = Field(description="The index sidecar the ranges were resolved through")
    index_checksum: Sha256 = Field(description="'sha256:<hex>' of the index text as fetched")
    messages: list[int] = Field(description="Selected message numbers, ascending and distinct")
    ranges: list[ByteRange] = Field(description="Byte ranges of those messages, in the same order")
    selectors: list[str] = Field(
        default_factory=list,
        description="Index selector naming each of those messages, in the same order",
    )

    @model_validator(mode="after")
    def _aligned(self) -> PartialFetch:
        if not self.messages or len(self.messages) != len(self.ranges):
            raise ValueError("a partial fetch needs one byte range per selected message")
        if self.selectors and len(self.selectors) != len(self.messages):
            raise ValueError("a partial fetch needs one selector per selected message")
        if sorted(set(self.messages)) != self.messages:
            raise ValueError("selected messages must be ascending and distinct")
        return self

    @property
    def size(self) -> int:
        """Total bytes the selected ranges cover."""
        return sum(part.length for part in self.ranges)

    @property
    def fragment(self) -> str:
        """The href fragment that names this selection, such as ``messages=71,170``."""
        return f"{PARTIAL_FRAGMENT}={','.join(str(number) for number in self.messages)}"

    def describe(self) -> str:
        """The ``transformations`` entry a provenance record carries for this fetch."""
        numbers = ",".join(str(number) for number in self.messages)
        return f"grib2 messages {numbers} concatenated from {self.object_url}"


PARTIAL_TRANSFORMATION = "grib2 messages "
"""Prefix of the ``transformations`` entry :meth:`PartialFetch.describe` writes."""


class TemporalSelection(BaseModel):
    """A start-time selection and its explicit policy; not source provenance.

    No match has ``asset=None``, ``offset_seconds=None``, and zero eligible
    candidates. Counts refer to the supplied candidates, not a remote catalog.
    """

    target: AwareUTC
    tolerance: timedelta
    direction: Literal["nearest", "at_or_before"]
    asset: Asset | None
    offset_seconds: float | None
    candidate_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)


class Provenance(BaseModel):
    """Everything needed to say where a local file came from and re-fetch it."""

    dataset_id: str
    provider: str
    source_url: str
    retrieved_at: AwareUTC
    checksum: Sha256
    size: int = Field(ge=0)
    license: str | None = None
    usdata_version: str
    transformations: list[str] = Field(default_factory=list)
    index_url: str | None = Field(
        default=None, description="Index sidecar a partial fetch resolved its ranges through"
    )
    index_checksum: Sha256 | None = Field(
        default=None, description="'sha256:<hex>' of that index text as it was fetched"
    )
    ranges: list[ByteRange] = Field(
        default_factory=list, description="Byte ranges a partial fetch concatenated, in order"
    )
    selectors: list[str] = Field(
        default_factory=list,
        description="Index selector each of those ranges was fetched for, in the same order",
    )
    object_size: int | None = Field(
        default=None, ge=0, description="Size of the whole object those ranges came from"
    )
    object_etag: str | None = Field(
        default=None, description="ETag that object carried, re-sent as ``If-Match`` on a restore"
    )
    mirror: str | None = Field(
        default=None,
        description=(
            "Mirror object that served these bytes in place of the source (ADR 0030, ADR 0039)"
        ),
    )
    credentials: list[str] = Field(
        default_factory=list,
        description=(
            "Environment variables the source requires to fetch this file, never their values "
            "(ADR 0039); empty for an anonymous source"
        ),
    )

    @property
    def is_partial(self) -> bool:
        """Whether this record describes selected byte ranges rather than a whole object."""
        return any(entry.startswith(PARTIAL_TRANSFORMATION) for entry in self.transformations)

    @property
    def object_messages(self) -> list[int]:
        """The source object's own message numbers, in the order the local file holds them.

        A partial fetch concatenated one message per recorded range, so the nth
        number here numbers the nth message on disk as the index sidecar numbers
        it, one-based. Empty for a whole file, and empty rather than wrong when
        the href fragment and the recorded ranges disagree.
        """
        if not self.is_partial:
            return []
        _, _, fragment = self.source_url.partition("#")
        try:
            numbers = [
                int(number) for number in fragment.removeprefix(f"{PARTIAL_FRAGMENT}=").split(",")
            ]
        except ValueError:
            return []
        return numbers if len(numbers) == len(self.ranges) else []
