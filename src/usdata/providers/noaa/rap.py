"""RAP forecast output from the anonymous ``noaa-rap-pds`` S3 bucket.

The Rapid Refresh is the hourly-cycled 13 km North American model HRRR nests
inside. Each run writes one GRIB2 file per forecast hour and grid family under
``rap.YYYYMMDD/rap.tHHz.<family>fNN.grib2``, beside a ``.grib2.idx`` sidecar.
The query window selects runs by initialization time, ``cycle`` names the
run's hour, ``forecast_hour`` names the files, and ``file`` chooses the
family: the 13 km CONUS pressure-level grid by default, its secondary fields,
or the native-grid pressure and hybrid-level files. Runs reach 21 hours, or 51
from the 03, 09, 15, and 21 UTC runs. Files are whole grids of hundreds of
fields; message selection happens before download with ``messages`` or after
it with the GRIB2 reader's ``select``. The bucket's ``rap.`` day prefixes begin
on 2021-02-22; earlier days hold only NARRE files.
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

BUCKET = "noaa-rap-pds"
ARCHIVE_START = datetime(2021, 2, 22, 0, tzinfo=UTC)
FILES: Mapping[str, str] = {
    "awp130": "awp130pgrb",
    "awp130b": "awp130bgrb",
    "prs": "wrfprs",
    "nat": "wrfnat",
}
LONG_CYCLES = frozenset({3, 9, 15, 21})
MAX_HOUR = 21
LONG_MAX_HOUR = 51
KEY_RE = re.compile(
    r"rap\.t(?P<cycle>\d{2})z\.(?P<variant>awp130pgrb|awp130bgrb|wrfprs|wrfnat)f(?P<hour>\d{2})\.grib2"
)


class RapParams(BaseModel):
    """Which run, which forecast hours, and which file family one RAP query names."""

    model_config = ConfigDict(extra="forbid")

    cycle: Annotated[int, int_range(0, 23)] = Field(
        description="Required UTC initialization hour of the run, 0 to 23."
    )
    forecast_hour: Annotated[list[int], int_list(0, LONG_MAX_HOUR)] = Field(
        description="Required forecast hour(s): an integer, list, or comma-separated "
        "string; 0 to 21, or 0 to 51 for the 03, 09, 15, and 21 UTC runs."
    )
    file: Annotated[str, choice(*FILES)] = Field(
        default="awp130",
        description="File family: awp130 (default, 13 km CONUS pressure levels), awp130b "
        "(its secondary fields), prs (native-grid pressure levels), or nat (native levels).",
    )

    messages: MessageList | None = Field(default=None, description=MESSAGES)

    @model_validator(mode="after")
    def _hours_fit_the_cycle(self) -> RapParams:
        """Only the 03, 09, 15, and 21 UTC runs reach 51 hours; the others stop at 21."""
        ceiling = LONG_MAX_HOUR if self.cycle in LONG_CYCLES else MAX_HOUR
        if any(hour > ceiling for hour in self.forecast_hour):
            raise ValueError(f"forecast_hour must be an integer from 0 to {ceiling}")
        return self

    @property
    def variant(self) -> str:
        """The key fragment naming the chosen family, for example ``awp130pgrb``."""
        return FILES[self.file]


class Rap(ModelRuns):
    """RAP GRIB2 files, whole or by message; params: cycle, forecast_hour, file, messages."""

    name = "RAP"
    bucket = BUCKET
    archive_start = ARCHIVE_START
    key_re = KEY_RE
    hint = (
        "RAP files are whole grids; fetch with messages=..., or download and let "
        "open(select=...) pick fields"
    )
    suffix = ".grib2"
    params_model = RapParams

    def resolve(self, query: Query) -> RunSelection:
        """Validated cycle, file family, forecast hours, and messages for one RAP query."""
        params = self.parse_params(query, RapParams)
        return RunSelection(
            params.cycle, params.variant, params.forecast_hour, params.messages or []
        )

    def run_prefix(self, init: datetime, variant: str) -> str:
        """Key prefix listing one run's files of the chosen family."""
        return f"rap.{init:%Y%m%d}/rap.t{init:%H}z.{variant}f"

    def asset_id(self, init: datetime, variant: str, hour: int) -> str:
        """Cache filename: the upstream name with the run day inserted."""
        return f"rap.{init:%Y%m%d}.t{init:%H}z.{variant}f{hour:02d}.grib2"

    def files_label(self, variant: str) -> str:
        """Name for these files in missing-run errors."""
        return f"RAP {variant}"
