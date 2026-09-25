"""Declarative manifests (what a project needs) and lockfiles (what was actually fetched)."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from usdata._files import atomic_write_text
from usdata.models import Asset, AwareUTC, BBox, Provenance, Query, TemporalSelection
from usdata.query import build_query
from usdata.registry import Registry, default_registry
from usdata.selection import select_by_time

_SOURCE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_SHORT_DURATION = re.compile(r"(?P<count>\d+)(?P<unit>[smhd])")
_ISO_DURATION = re.compile(
    r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?"
)
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


def parse_tolerance(value: object) -> object:
    """Read a tolerance such as ``90s``, ``5m``, ``1h``, ``1d``, or ISO 8601 ``PT5M``.

    A ``timedelta`` passes through, and zero is allowed: it asks for an exact
    start. Anything else is left for validation to refuse.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    if short := _SHORT_DURATION.fullmatch(text):
        return timedelta(**{_UNITS[short["unit"]]: int(short["count"])})
    if (iso := _ISO_DURATION.fullmatch(text.upper())) and text.upper() not in ("P", "PT"):
        return timedelta(**{name: int(raw) for name, raw in iso.groupdict().items() if raw})
    raise ValueError(f"invalid duration {value!r}: use 90s, 5m, 1h, 1d, or ISO 8601 such as PT5M")


Tolerance = Annotated[timedelta, BeforeValidator(parse_tolerance)]


class TimeSelect(BaseModel):
    """Keep the one asset whose start is nearest an instant, or the latest at or before it.

    The source is listed over the window the rule implies, ``time`` plus or
    minus ``within`` for ``nearest`` and the ``within`` before ``time`` for
    ``at_or_before``, and ``select_by_time`` chooses among what was listed. For
    files acquired back to back, such as radar volumes and satellite scans,
    the latest start at or before an instant is the file covering it. See ADR 0044.
    """

    model_config = ConfigDict(extra="forbid")

    time: AwareUTC = Field(description="The instant to select for; a naive value means UTC")
    within: Tolerance = Field(
        description="How far an asset's start may be from time: 90s, 5m, 1h, 1d, or ISO 8601"
    )
    direction: Literal["nearest", "at_or_before"] = Field(
        description="'nearest' admits starts on either side of time; 'at_or_before' only earlier"
    )

    @model_validator(mode="after")
    def _nonnegative(self) -> TimeSelect:
        if self.within < timedelta(0):
            raise ValueError("within must not be negative")
        return self

    def window(self) -> tuple[datetime, datetime]:
        """The listing window this rule needs, inclusive at both ends."""
        end = self.time if self.direction == "at_or_before" else self.time + self.within
        return self.time - self.within, end

    def choose(self, assets: Iterable[Asset]) -> TemporalSelection:
        """Apply the rule to a listing; the result's ``asset`` is the winner, or None."""
        return select_by_time(
            assets, target=self.time, tolerance=self.within, direction=self.direction
        )


class SourceSpec(BaseModel):
    """One entry under ``sources:`` in a manifest."""

    model_config = ConfigDict(extra="forbid")

    dataset: str
    name: str | None = Field(
        default=None, description="Optional label that keys this source in results and lockfiles"
    )
    allow_empty: bool = False
    location: str | None = None
    bbox: BBox | None = None
    start: str | date | datetime | None = None
    end: str | date | datetime | None = None
    variables: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    select: TimeSelect | None = Field(
        default=None,
        description="Keep only the asset nearest an instant; replaces start and end (ADR 0044)",
    )

    @model_validator(mode="after")
    def _reserved_params(self) -> SourceSpec:
        reserved = {"location", "bbox", "start", "end", "variables", "select"}
        if overlap := reserved.intersection(self.params):
            raise ValueError(f"params contains reserved query fields: {', '.join(sorted(overlap))}")
        if self.select is not None and (self.start is not None or self.end is not None):
            raise ValueError("a source with select takes its window from it; drop start and end")
        return self

    def to_query(self) -> Query:
        """Build the Query this source resolves to; ``select`` supplies the window when set."""
        start, end = (self.start, self.end) if self.select is None else self.select.window()
        return build_query(
            location=self.location,
            bbox=self.bbox,
            start=start,
            end=end,
            variables=self.variables,
            **self.params,
        )


class Manifest(BaseModel):
    """A declarative list of inputs a project needs: usdata pull fetches them."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str = "1.0"
    sources: list[SourceSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _distinct_source_keys(self) -> Manifest:
        for source in self.sources:
            if source.name is not None and not _SOURCE_NAME.match(source.name):
                raise ValueError(
                    f"source name {source.name!r} must use only letters, digits, "
                    "hyphens, and underscores"
                )
        keys = self.source_keys()
        if repeated := sorted({key for key in keys if keys.count(key) > 1}):
            raise ValueError(f"duplicate source names: {', '.join(repeated)}")
        return self

    def source_keys(self) -> list[str]:
        """Each source's key: its ``name`` when set, otherwise its one-based position."""
        return [source.name or str(position) for position, source in enumerate(self.sources, 1)]

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> Manifest:
        """Parse a manifest YAML file."""
        path = Path(path)
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise ValueError(f"invalid manifest YAML in {path}: {e}") from e
        return cls.model_validate(raw or {})

    def validate_against(self, registry: Registry | None = None) -> list[str]:
        """Return the dataset ids referenced by this manifest that the registry lacks."""
        reg = registry or default_registry()
        return [s.dataset for s in self.sources if s.dataset not in reg]


class LockedAsset(BaseModel):
    """One resolved asset and the provenance of the copy that was fetched."""

    asset: Asset
    provenance: Provenance
    source: str | None = Field(
        default=None, description="Key of the manifest source that resolved this asset"
    )

    @model_validator(mode="after")
    def _consistent(self) -> LockedAsset:
        if (
            self.asset.dataset_id != self.provenance.dataset_id
            or self.asset.href != self.provenance.source_url
        ):
            raise ValueError("locked asset and provenance must identify the same source")
        if self.asset.checksum is not None and self.asset.checksum != self.provenance.checksum:
            raise ValueError("locked asset and provenance checksums must agree")
        return self


class Lockfile(BaseModel):
    """Exactly what a manifest resolved to, with checksums, so it can be reproduced."""

    manifest: str
    manifest_checksum: str = Field(description="sha256 of the manifest file when it was resolved")
    generated_at: AwareUTC
    usdata_version: str
    assets: list[LockedAsset] = Field(default_factory=list)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> Lockfile:
        """Read a lockfile written by ``save``."""
        return cls.model_validate_json(Path(path).read_text())

    def save(self, path: str | os.PathLike[str]) -> None:
        """Write the lockfile as indented JSON."""
        atomic_write_text(Path(path), self.model_dump_json(indent=2))


def lockfile_path(manifest_path: str | os.PathLike[str]) -> Path:
    """The lockfile that pairs with a manifest: <manifest stem>.lock.json."""
    return Path(manifest_path).with_suffix(".lock.json")
