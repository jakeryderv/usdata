"""HRRR forecast output from the anonymous ``noaa-hrrr-bdp-pds`` S3 bucket.

One model run is identified by its UTC initialization day and ``cycle`` hour;
each run writes one GRIB2 file per forecast hour under
``hrrr.YYYYMMDD/conus/hrrr.tHHz.<variant>fNN.grib2``. The query window selects
runs by initialization time, ``cycle`` names the run's hour, ``forecast_hour``
names the files, and ``file`` chooses the surface, pressure-level, or native
variant. Files are whole CONUS grids of hundreds of fields; there is no
server-side subsetting, so message selection happens after download with the
GRIB2 reader's ``select``.

The run-selection helpers (:func:`select_runs`, :func:`list_run_files`) and the
:class:`ModelRuns` listing base are shared with the GFS adapter.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, ClassVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.params import choice, int_list, int_range

BUCKET = "noaa-hrrr-bdp-pds"
DOMAIN = "conus"
MEDIA_TYPE = "application/x-grib2"
ARCHIVE_START = datetime(2014, 7, 30, 18, tzinfo=UTC)
MAX_WINDOW = timedelta(days=1)
FILES: Mapping[str, str] = {"sfc": "wrfsfcf", "prs": "wrfprsf", "nat": "wrfnatf"}
LONG_CYCLES = frozenset({0, 6, 12, 18})
MAX_HOUR = 18
LONG_MAX_HOUR = 48
KEY_RE = re.compile(r"hrrr\.t(?P<cycle>\d{2})z\.(?P<variant>wrf[a-z]+f)(?P<hour>\d{2,3})\.grib2")


class HrrrParams(BaseModel):
    """Which run, which forecast hours, and which file variant one HRRR query names."""

    model_config = ConfigDict(extra="forbid")

    cycle: Annotated[int, int_range(0, 23)] = Field(
        description="Required UTC initialization hour of the run, 0 to 23."
    )
    forecast_hour: Annotated[list[int], int_list(0, LONG_MAX_HOUR)] = Field(
        description="Required forecast hour(s): an integer, list, or comma-separated "
        "string; 0 to 18, or 0 to 48 for the 00, 06, 12, and 18 UTC runs."
    )
    file: Annotated[str, choice(*FILES)] = Field(
        default="sfc",
        description="File variant: sfc (default, 2-D fields), prs (pressure levels), or nat "
        "(native levels).",
    )

    @field_validator("file", mode="before")
    @classmethod
    def _reject_subhourly(cls, value: object) -> object:
        """Name the one variant this adapter leaves out, rather than listing it as a typo."""
        if value == "subh":
            raise ValueError("file=subh (15-minute output) is out of scope; use sfc, prs, or nat")
        return value

    @model_validator(mode="after")
    def _hours_fit_the_cycle(self) -> HrrrParams:
        """Only the 00, 06, 12, and 18 UTC runs reach 48 hours; the others stop at 18."""
        ceiling = LONG_MAX_HOUR if self.cycle in LONG_CYCLES else MAX_HOUR
        if any(hour > ceiling for hour in self.forecast_hour):
            raise ValueError(f"forecast_hour must be an integer from 0 to {ceiling}")
        return self

    @property
    def variant(self) -> str:
        """The key fragment naming the chosen file variant, for example ``wrfsfcf``."""
        return FILES[self.file]


def select_runs(start: datetime, end: datetime, cycle: int) -> list[datetime]:
    """Initialization times at ``cycle`` inside the inclusive UTC window, in order."""
    candidates = {
        datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=cycle)
        for day in (start.date(), end.date())
    }
    return sorted(init for init in candidates if start <= init <= end)


def list_run_files(
    client: httpx.Client,
    bucket: str,
    prefix: str,
    key_re: re.Pattern[str],
    hours: list[int],
) -> dict[int, s3.S3Object]:
    """Objects under ``prefix`` whose parsed forecast hour is requested, keyed by hour."""
    found: dict[int, s3.S3Object] = {}
    wanted = set(hours)
    for obj in s3.list_objects(bucket, prefix, client):
        match = key_re.fullmatch(obj.key.rsplit("/", 1)[-1])
        if match is None:
            continue
        hour = int(match["hour"])
        if hour in wanted:
            found[hour] = obj
    return found


class ModelRuns(HttpProvider):
    """Shared listing for models that publish one whole GRIB2 file per run and forecast hour.

    Subclasses validate their own parameters in :meth:`resolve` and describe the
    bucket layout through :meth:`run_prefix`, :meth:`asset_id`, and
    :meth:`files_label`; the window, run selection, listing, and missing-file
    errors are identical for HRRR and GFS.
    """

    name: ClassVar[str]
    bucket: ClassVar[str]
    archive_start: ClassVar[datetime]
    key_re: ClassVar[re.Pattern[str]]
    hint: ClassVar[str]
    hour_width: ClassVar[int] = 2

    def resolve(self, query: Query) -> tuple[int, str, list[int]]:
        """Validated ``(cycle, variant, forecast hours)`` from the provider parameters."""
        raise NotImplementedError

    def run_prefix(self, init: datetime, variant: str) -> str:
        """The S3 key prefix that lists one run's files of ``variant``."""
        raise NotImplementedError

    def asset_id(self, init: datetime, variant: str, hour: int) -> str:
        """A stable, day-qualified id for one file, used as the cache filename."""
        raise NotImplementedError

    def files_label(self, variant: str) -> str:
        """How a missing run's files are named in errors, for example ``HRRR conus wrfsfcf``."""
        raise NotImplementedError

    def list_assets(self, query: Query) -> list[Asset]:
        """One asset per requested forecast hour of each run initialized inside the window."""
        self.reject(query, "bbox", "text", "variables", hint=self.hint)
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError(
                f"{self.name} requests must span at most 1 day; split longer intervals"
            )
        cycle, variant, hours = self.resolve(query)
        if end < self.archive_start:
            raise QueryError(
                f"the {self.bucket} archive begins with the {self.archive_start:%Y-%m-%d %HZ} run"
            )
        runs = select_runs(start, end, cycle)
        if not runs:
            raise QueryError(
                f"no {cycle:02d}Z initialization falls inside {start.isoformat()} to "
                f"{end.isoformat()}; widen the window or change cycle"
            )
        assets: list[Asset] = []
        for init in runs:
            prefix = self.run_prefix(init, variant)
            found = list_run_files(self._http(), self.bucket, prefix, self.key_re, hours)
            if not found:
                raise QueryError(
                    f"no {self.files_label(variant)} files for the {init:%Y-%m-%d %H}Z run; "
                    "the run may be missing from the archive or predate this variant"
                )
            if missing := [f"{hour:0{self.hour_width}d}" for hour in hours if hour not in found]:
                raise QueryError(
                    f"the {init:%Y-%m-%d %H}Z run has no forecast hour(s) {', '.join(missing)}"
                )
            for hour in hours:
                obj = found[hour]
                valid = init + timedelta(hours=hour)
                assets.append(
                    Asset(
                        id=self.asset_id(init, variant, hour),
                        dataset_id=self.dataset.id,
                        href=f"s3://{self.bucket}/{obj.key}",
                        protocol=Protocol.S3,
                        media_type=MEDIA_TYPE,
                        size=obj.size,
                        time=TimeRange(start=valid, end=valid),
                    )
                )
        return assets

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one whole GRIB2 object anonymously to ``dest``."""
        return s3.download(asset.href, dest, self._http())


class Hrrr(ModelRuns):
    """Whole HRRR CONUS GRIB2 files; params: cycle, forecast_hour, file."""

    name = "HRRR"
    bucket = BUCKET
    archive_start = ARCHIVE_START
    key_re = KEY_RE
    hint = "HRRR files are whole CONUS grids; download, then open(select=...) picks fields"
    params_model = HrrrParams

    def resolve(self, query: Query) -> tuple[int, str, list[int]]:
        """Validated cycle, file variant, and forecast hours for one HRRR query."""
        params = self.parse_params(query, HrrrParams)
        return params.cycle, params.variant, params.forecast_hour

    def run_prefix(self, init: datetime, variant: str) -> str:
        """Key prefix listing one run's files of the chosen variant."""
        return f"hrrr.{init:%Y%m%d}/{DOMAIN}/hrrr.t{init:%H}z.{variant}"

    def asset_id(self, init: datetime, variant: str, hour: int) -> str:
        """Cache filename: the upstream name with the run day inserted."""
        return f"hrrr.{init:%Y%m%d}.t{init:%H}z.{variant}{hour:02d}.grib2"

    def files_label(self, variant: str) -> str:
        """Name for these files in missing-run errors."""
        return f"HRRR {DOMAIN} {variant}"
