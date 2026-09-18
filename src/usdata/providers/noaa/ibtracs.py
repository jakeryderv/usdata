"""Whole IBTrACS best-track files from the NCEI archive directory.

The International Best Track Archive for Climate Stewardship merges every
agency's tropical cyclone best tracks into one global record and publishes it
as whole files under an anonymous HTTPS directory, one per subset and format.
``subset`` names one of the eleven files NCEI builds: the complete record, the
storms still active, the last three years, everything since 1980, or one of
the seven basins. ``format`` picks the CSV list or the NetCDF file, and
``version`` pins a product version, the newest published one by default.

There is no query interface, so dates, geographic filters, variables, and
text queries are rejected rather than silently ignored: every file holds the
complete record for its subset. The files are rebuilt in place under
unchanging names, so a lockfile's checksum is what pins the bytes and a
repeat pull reports upstream change rather than a new revision. Filter the
parsed table locally.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import http
from usdata.protocols.listing import directory_entries, directory_listing
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import choice

DIRECTORY_URL = (
    "https://www.ncei.noaa.gov/data/"
    "international-best-track-archive-for-climate-stewardship-ibtracs/"
)
# NCEI names the subsets in mixed case; the parameter folds them to these keys.
SUBSETS: Mapping[str, str] = {
    "all": "ALL",
    "active": "ACTIVE",
    "last3years": "last3years",
    "since1980": "since1980",
    "na": "NA",
    "ep": "EP",
    "wp": "WP",
    "ni": "NI",
    "si": "SI",
    "sp": "SP",
    "sa": "SA",
}
FORMATS: Mapping[str, tuple[str, str]] = {
    # format -> (directory, media type)
    "csv": ("csv", "text/csv"),
    "netcdf": ("netcdf", "application/x-netcdf"),
}
# The archive's first record, from the files' time_coverage_start attribute; a basin's own
# first record may be later. NCEI lists modified stamps in UTC, as the Last-Modified headers
# confirmed on 2026-09-17, and a build's records cannot postdate the build.
ARCHIVE_START = datetime(1842, 10, 25, 3, tzinfo=UTC)
SINCE_1980 = datetime(1980, 1, 1, tzinfo=UTC)
LAST_SEASONS = 3
"""``last3years`` holds the build year's season and this many before it."""
# Product versions are directories such as v04r01; the per-subset files begin with v4.
VERSION = re.compile(r"v(?P<major>\d{2})r(?P<release>\d{2})")
FIRST_SUBSET_VERSION = 4
FILE_NAMES: Mapping[str, str] = {
    "csv": "ibtracs.{subset}.list.{version}.csv",
    "netcdf": "IBTrACS.{subset}.{version}.nc",
}


def _subset(value: object) -> str:
    """Fold case and surrounding space; NCEI publishes exactly these eleven subsets."""
    key = value.strip().casefold() if isinstance(value, str) else ""
    if key not in SUBSETS:
        raise ValueError(f"must be one of {', '.join(SUBSETS)}, not {value!r}")
    return key


def _version(value: object) -> str:
    """A product version directory name, folded to lower case."""
    text = value.strip().lower() if isinstance(value, str) else ""
    match = VERSION.fullmatch(text)
    if match is None:
        raise ValueError(f"must be a product version such as v04r01, not {value!r}")
    if int(match["major"]) < FIRST_SUBSET_VERSION:
        raise ValueError(
            f"must be v04r00 or later; {text} publishes one file per storm in another layout"
        )
    return text


def version_key(version: str) -> tuple[int, int]:
    """Order product versions numerically: ``v04r01`` after ``v04r00`` after ``v03r09``."""
    match = VERSION.fullmatch(version)
    assert match is not None
    return int(match["major"]), int(match["release"])


def _subset_start(subset: str, built: datetime | None) -> datetime:
    """The bound a subset's definition puts on its records, or the archive's first record.

    ``since1980`` starts with that year, and ``last3years`` with the season three
    years before the build; the complete record, the basins, and the active
    storms are bounded only by the archive itself.
    """
    if subset == "since1980":
        return SINCE_1980
    if subset == "last3years" and built is not None:
        return datetime(built.year - LAST_SEASONS, 1, 1, tzinfo=UTC)
    return ARCHIVE_START


class IbtracsParams(BaseModel):
    """Which subset, format, and product version one IBTrACS query names."""

    model_config = ConfigDict(extra="forbid")

    subset: Annotated[str, BeforeValidator(_subset)] = Field(
        description="Required subset: all, active, last3years, since1980, or a basin "
        "(na, ep, wp, ni, si, sp, or sa), case-insensitive."
    )
    format: Annotated[str, choice(*FORMATS)] = Field(
        default="csv", description="File format: csv (default) or netcdf."
    )
    version: Annotated[str | None, BeforeValidator(_version)] = Field(
        default=None,
        description="Product version such as v04r01; the newest published one by default.",
    )


class Ibtracs(HttpProvider):
    """Resolve one whole IBTrACS subset file; preserve the original bytes."""

    params_model = IbtracsParams

    def list_assets(self, query: Query) -> list[Asset]:
        """Select the named subset and format from the chosen or newest product version."""
        params = self.parse_params(query, IbtracsParams)
        self.reject(
            query,
            "bbox",
            "variables",
            "text",
            hint="IBTrACS publishes whole files per subset; filter the parsed table locally",
        )
        self.reject(
            query,
            "time",
            hint="every file holds the complete record for its subset, so a date range would "
            "not change the download; remove start/end and filter the parsed time column "
            "locally, or choose the since1980 or last3years subset",
        )
        version = params.version or self._newest_version()
        directory, media_type = FORMATS[params.format]
        name = FILE_NAMES[params.format].format(subset=SUBSETS[params.subset], version=version)
        listing_url = f"{DIRECTORY_URL}{version}/access/{directory}/"
        page = http.get(listing_url, self._http()).text
        entries = directory_listing(page, re.compile(re.escape(name)))
        if not entries:
            raise QueryError(f"no {name} in the IBTrACS {version} {directory} directory listing")
        entry = entries[0]
        built = None if entry.modified is None else entry.modified.replace(tzinfo=UTC)
        return [
            Asset(
                id=name,
                dataset_id=self.dataset.id,
                href=listing_url + name,
                protocol=Protocol.HTTP,
                media_type=media_type,
                size=entry.size,
                time=TimeRange(start=_subset_start(params.subset, built), end=built),
            )
        ]

    def _newest_version(self) -> str:
        """The highest product version the archive directory lists with per-subset files."""
        page = http.get(DIRECTORY_URL, self._http()).text
        versions = [
            name.rstrip("/")
            for name, _ in directory_entries(page, re.compile(r"v\d{2}r\d{2}/?"))
            if version_key(name.rstrip("/"))[0] >= FIRST_SUBSET_VERSION
        ]
        if not versions:
            raise QueryError("no IBTrACS product version in the NCEI directory listing")
        return max(versions, key=version_key)

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the pinned file, without reformatting or subsetting it."""
        return http.download(asset.href, dest, self._http())
