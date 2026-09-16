"""GOES Geostationary Lightning Mapper flash, group, and event detections.

Require ``satellite`` (16, 17, 18, or 19) and both timestamps at most one day
apart. Each asset is one whole 20-second ``GLM-L2-LCFA`` NetCDF file from the
same anonymous S3 buckets and ``PRODUCT/YYYY/DDD/HH/`` layout as ABI imagery,
selected by inclusive file-start time. A day is 4,320 files of roughly 300 kB
each, so the window is shorter than ABI's seven days. Geographic filtering of
the detections happens after opening the file, not in the query.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from usdata.models import Asset, Query
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.http import HttpProvider
from usdata.providers.noaa.goes import list_scans
from usdata.providers.params import int_range

PRODUCT = "GLM-L2-LCFA"
PUBLIC_START = datetime(2018, 2, 13, 16, 10, tzinfo=UTC)
MAX_WINDOW = timedelta(days=1)
KEY_RE = re.compile(
    r"OR_GLM-L2-LCFA_G(?P<satellite>1[6-9])_s(?P<start>\d{14})_e(?P<end>\d{14})_c\d{14}\.nc"
)


class GlmParams(BaseModel):
    """Which GOES satellite's lightning detections one GLM query selects."""

    model_config = ConfigDict(extra="forbid")

    satellite: Annotated[int, int_range(16, 19)] = Field(
        description="Required GOES satellite number: 16, 17, 18, or 19."
    )


class GoesGlm(HttpProvider):
    """Whole 20-second GLM detection files; params: satellite."""

    params_model = GlmParams

    def list_assets(self, query: Query) -> list[Asset]:
        """List 20-second files whose start stamps fall inside the inclusive UTC interval."""
        params = self.parse_params(query, GlmParams)
        self.reject(
            query,
            "bbox",
            "text",
            "variables",
            hint="GLM files are whole 20-second detection tables; select a satellite and window",
        )
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError("GLM requests must span at most 1 day; split longer intervals")
        satellite = params.satellite
        if end < PUBLIC_START:
            raise QueryError("GLM public detections begin on 2018-02-13T16:10Z")
        start = max(start, PUBLIC_START)
        return list_scans(
            self._http(),
            f"noaa-goes{satellite}",
            PRODUCT,
            start,
            end,
            KEY_RE,
            lambda m: int(m["satellite"]) == satellite,
            self.dataset.id,
        )

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download the complete archived NetCDF object without modification."""
        return s3.download(asset.href, dest, self._http())
