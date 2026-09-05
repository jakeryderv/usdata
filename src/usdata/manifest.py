"""Declarative manifests (what a project needs) and lockfiles (what was actually fetched)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata._files import atomic_write_text
from usdata.models import Asset, BBox, Provenance, Query
from usdata.query import build_query
from usdata.registry import Registry, default_registry


class SourceSpec(BaseModel):
    """One entry under ``sources:`` in a manifest."""

    model_config = ConfigDict(extra="forbid")

    dataset: str
    allow_empty: bool = False
    location: str | None = None
    bbox: BBox | None = None
    start: str | date | datetime | None = None
    end: str | date | datetime | None = None
    variables: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _reserved_params(self) -> SourceSpec:
        reserved = {"location", "bbox", "start", "end", "variables"}
        if overlap := reserved.intersection(self.params):
            raise ValueError(f"params contains reserved query fields: {', '.join(sorted(overlap))}")
        return self

    def to_query(self) -> Query:
        """Build the Query this source resolves to."""
        return build_query(
            location=self.location,
            bbox=self.bbox,
            start=self.start,
            end=self.end,
            variables=self.variables,
            **self.params,
        )


class Manifest(BaseModel):
    """A declarative list of inputs a project needs: usdata pull fetches them."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str = "1.0"
    sources: list[SourceSpec] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        """Parse a manifest YAML file."""
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
    generated_at: datetime
    usdata_version: str
    assets: list[LockedAsset] = Field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> Lockfile:
        """Read a lockfile written by ``save``."""
        return cls.model_validate_json(path.read_text())

    def save(self, path: Path) -> None:
        """Write the lockfile as indented JSON."""
        atomic_write_text(path, self.model_dump_json(indent=2))


def lockfile_path(manifest_path: Path) -> Path:
    """The lockfile that pairs with a manifest: <manifest stem>.lock.json."""
    return manifest_path.with_suffix(".lock.json")
