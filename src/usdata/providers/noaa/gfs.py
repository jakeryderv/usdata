"""GFS forecast output from the anonymous ``noaa-gfs-bdp-pds`` S3 bucket.

The Global Forecast System runs at 00, 06, 12, and 18 UTC and writes one GRIB2
file per forecast hour and grid resolution under
``gfs.YYYYMMDD/HH/atmos/gfs.tHHz.pgrb2.<resolution>.fNNN``. The query window
selects runs by initialization time, ``cycle`` names the run, ``forecast_hour``
names the files, and ``resolution`` chooses the 0.25, 0.5, or 1 degree grid.
The 0.25 degree files are hourly to 120 and three-hourly to 384; the coarser
grids are three-hourly throughout. Files are whole global grids of hundreds of
fields; message selection happens either before download with ``messages``, which
reads the object's ``.idx`` sidecar, or after it with the GRIB2 reader's
``select``. GFS keys carry no extension, so a sidecar is ``<key>.idx``. The
``atmos`` layout begins with the GFS v16 run of 2021-03-22 12 UTC; earlier runs
use another layout and are not reachable here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Query
from usdata.providers.noaa.hrrr import MESSAGES, MessageList, ModelRuns, RunSelection
from usdata.providers.params import choice, int_list, int_range

BUCKET = "noaa-gfs-bdp-pds"
ARCHIVE_START = datetime(2021, 3, 22, 12, tzinfo=UTC)
CYCLES = (0, 6, 12, 18)
MAX_HOUR = 384
RESOLUTIONS: Mapping[str, str] = {
    "0p25": "0.25 degree",
    "0p50": "0.5 degree",
    "1p00": "1 degree",
}
HOURLY_UNTIL: Mapping[str, int] = {"0p25": 120, "0p50": 0, "1p00": 0}
KEY_RE = re.compile(
    r"gfs\.t(?P<cycle>\d{2})z\.pgrb2\.(?P<resolution>0p25|0p50|1p00)\.f(?P<hour>\d{3})"
)


def forecast_hours(resolution: str) -> list[int]:
    """Every forecast hour a run publishes at ``resolution``: hourly, then every three hours."""
    hourly = HOURLY_UNTIL[resolution]
    return list(range(hourly + 1)) + list(range(hourly + 3 - hourly % 3, MAX_HOUR + 1, 3))


class GfsParams(BaseModel):
    """Which run, which forecast hours, and which grid one GFS query names."""

    model_config = ConfigDict(extra="forbid")

    cycle: Annotated[int, int_range(0, 23)] = Field(
        description="Required UTC initialization hour of the run: 0, 6, 12, or 18."
    )
    forecast_hour: Annotated[list[int], int_list(0, MAX_HOUR)] = Field(
        description="Required forecast hour(s): an integer, list, or comma-separated "
        "string, 0 to 384; hourly to 120 then every 3 hours at 0p25, every 3 hours at "
        "0p50 and 1p00."
    )
    resolution: Annotated[str, choice(*RESOLUTIONS)] = Field(
        default="0p25",
        description="Grid spacing: 0p25 (default, 0.25 degree), 0p50, or 1p00.",
    )

    messages: MessageList | None = Field(default=None, description=MESSAGES)

    @model_validator(mode="after")
    def _run_and_hours_are_published(self) -> GfsParams:
        """GFS runs four times a day, and each grid publishes its own forecast hours."""
        if self.cycle not in CYCLES:
            raise ValueError("cycle must be 0, 6, 12, or 18: GFS runs four times a day")
        published = set(forecast_hours(self.resolution))
        if unpublished := [f"{hour:03d}" for hour in self.forecast_hour if hour not in published]:
            step = (
                "hourly to 120, then every 3 hours to 384"
                if HOURLY_UNTIL[self.resolution]
                else "every 3 hours from 0 to 384"
            )
            raise ValueError(
                f"forecast hour(s) {', '.join(unpublished)} are not published at "
                f"{self.resolution}: files are {step}"
            )
        return self


class Gfs(ModelRuns):
    """GFS global GRIB2 files, whole or by message.

    Params: cycle, forecast_hour, resolution, messages.
    """

    name = "GFS"
    bucket = BUCKET
    archive_start = ARCHIVE_START
    key_re = KEY_RE
    hint = (
        "GFS files are whole global grids; fetch with messages=..., or download and let "
        "open_grib2(select=...) pick fields"
    )
    hour_width = 3
    params_model = GfsParams

    def resolve(self, query: Query) -> RunSelection:
        """Validated cycle, file variant, forecast hours, and messages for one GFS query."""
        params = self.parse_params(query, GfsParams)
        return RunSelection(
            params.cycle, params.resolution, params.forecast_hour, params.messages or []
        )

    def run_prefix(self, init: datetime, variant: str) -> str:
        """Key prefix listing one run's files of the chosen variant."""
        return f"gfs.{init:%Y%m%d}/{init:%H}/atmos/gfs.t{init:%H}z.pgrb2.{variant}.f"

    def asset_id(self, init: datetime, variant: str, hour: int) -> str:
        """Cache filename: the upstream name with the run day inserted."""
        return f"gfs.{init:%Y%m%d}.t{init:%H}z.pgrb2.{variant}.f{hour:03d}"

    def files_label(self, variant: str) -> str:
        """Name for these files in missing-run errors."""
        return f"GFS pgrb2 {variant}"
