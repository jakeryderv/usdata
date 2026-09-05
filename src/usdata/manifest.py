"""Declarative manifests (what a project needs) and lockfiles (what was actually fetched)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from usdata.models import Asset, BBox, Provenance, Query
from usdata.query import build_query
from usdata.registry import Registry, default_registry


class SourceSpec(BaseModel):
    """One entry under ``sources:`` in a manifest."""

    dataset: str
    location: str | None = None
    bbox: BBox | None = None
    start: str | date | datetime | None = None
    end: str | date | datetime | None = None
    variables: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

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

    name: str
    version: str = "1.0"
    sources: list[SourceSpec] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        """Parse a manifest YAML file."""
        return cls.model_validate(yaml.safe_load(path.read_text()) or {})

    def validate_against(self, registry: Registry | None = None) -> list[str]:
        """Return the dataset ids referenced by this manifest that the registry lacks."""
        reg = registry or default_registry()
        return [s.dataset for s in self.sources if s.dataset not in reg]


class LockedAsset(BaseModel):
    """One resolved asset and the provenance of the copy that was fetched."""

    asset: Asset
    provenance: Provenance


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
        path.write_text(self.model_dump_json(indent=2))


def lockfile_path(manifest_path: Path) -> Path:
    """The lockfile that pairs with a manifest: <manifest stem>.lock.json."""
    return manifest_path.with_suffix(".lock.json")
