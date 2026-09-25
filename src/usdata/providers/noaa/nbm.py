"""National Blend of Models guidance from the anonymous ``noaa-nbm-grib2-pds`` S3 bucket.

The NBM is NOAA's statistically blended, bias-corrected forecast guidance,
issued hourly. Each run writes one GRIB2 ``core`` file per forecast hour and
region under ``blend.YYYYMMDD/HH/core/blend.tHHz.core.fFFF.<region>.grib2``,
beside a ``.grib2.idx`` sidecar. The query window selects runs by
initialization time, ``cycle`` names the run's hour, ``forecast_hour`` names
the files, and ``region`` chooses the grid: the 2.5 km CONUS grid by default,
or Alaska, Hawaii, Puerto Rico, or Guam. Forecast hours begin at 1 and the
schedule thins with lead time and varies by cycle, so an hour a run does not
publish is reported by name after the listing rather than rejected before it.
Files are whole regional grids of hundreds of fields; the CONUS file is about
170 MB per hour, so message selection with ``messages`` is the usual way in.
The ``core`` layout begins with the 12 UTC run of 2020-09-29; earlier runs use
another layout and are not reachable here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from usdata.models import Query
from usdata.providers.noaa.hrrr import MESSAGES, MessageList, ModelRuns, RunSelection
from usdata.providers.params import choice, int_list, int_range

BUCKET = "noaa-nbm-grib2-pds"
ARCHIVE_START = datetime(2020, 9, 29, 12, tzinfo=UTC)
REGIONS: Mapping[str, str] = {
    "co": "CONUS",
    "ak": "Alaska",
    "hi": "Hawaii",
    "pr": "Puerto Rico",
    "gu": "Guam",
}
MAX_HOUR = 264
KEY_RE = re.compile(
    r"blend\.t(?P<cycle>\d{2})z\.core\.f(?P<hour>\d{3})\.(?P<variant>co|ak|hi|pr|gu)\.grib2"
)


class NbmParams(BaseModel):
    """Which run, which forecast hours, and which region one NBM query names."""

    model_config = ConfigDict(extra="forbid")

    cycle: Annotated[int, int_range(0, 23)] = Field(
        description="Required UTC initialization hour of the run, 0 to 23."
    )
    forecast_hour: Annotated[list[int], int_list(1, MAX_HOUR)] = Field(
        description="Required forecast hour(s): an integer, list, or comma-separated string, "
        "1 to 264; hourly to 36, then every 3 hours, then every 6, on a schedule that "
        "varies by cycle."
    )
    region: Annotated[str, choice(*REGIONS)] = Field(
        default="co",
        description="Grid: co (default, 2.5 km CONUS), ak (Alaska), hi (Hawaii), pr (Puerto "
        "Rico), or gu (Guam).",
    )

    messages: MessageList | None = Field(default=None, description=MESSAGES)


class Nbm(ModelRuns):
    """NBM core GRIB2 files, whole or by message; params: cycle, forecast_hour, region, messages."""

    name = "NBM"
    bucket = BUCKET
    archive_start = ARCHIVE_START
    key_re = KEY_RE
    hint = (
        "NBM files are whole regional grids; fetch with messages=..., or download and let "
        "open_grib2(select=...) pick fields"
    )
    hour_width = 3
    suffix = ".grib2"
    params_model = NbmParams

    def resolve(self, query: Query) -> RunSelection:
        """Validated cycle, region, forecast hours, and messages for one NBM query."""
        params = self.parse_params(query, NbmParams)
        return RunSelection(
            params.cycle, params.region, params.forecast_hour, params.messages or []
        )

    def run_prefix(self, init: datetime, variant: str) -> str:
        """Key prefix listing one run's core files; every region shares it (see ``key_pattern``)."""
        return f"blend.{init:%Y%m%d}/{init:%H}/core/blend.t{init:%H}z.core.f"

    def key_pattern(self, variant: str) -> re.Pattern[str]:
        """The core files of one region, which the key names after the forecast hour."""
        return re.compile(
            rf"blend\.t(?P<cycle>\d{{2}})z\.core\.f(?P<hour>\d{{3}})\.{variant}\.grib2"
        )

    def asset_id(self, init: datetime, variant: str, hour: int) -> str:
        """Cache filename: the upstream name with the run day inserted."""
        return f"blend.{init:%Y%m%d}.t{init:%H}z.core.f{hour:03d}.{variant}.grib2"

    def files_label(self, variant: str) -> str:
        """Name for these files in missing-run errors."""
        return f"NBM core {variant}"
