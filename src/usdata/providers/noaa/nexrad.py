"""NEXRAD Level II archive from the ``unidata-nexrad-level2`` public S3 bucket.

Key layout: ``YYYY/MM/DD/SITE/SITEYYYYMMDD_HHMMSS[_V06][.gz]``. One object per
volume scan. ``_MDM`` objects are metadata sidecars and are skipped. There is
no server-side subsetting; a query selects sites and a time window of at most
31 days, and every whole scan in that window is an asset.

Site selection, in order: ``site=``/``sites=`` params, then radars located
inside the query bbox, then the single radar nearest the bbox centre.
``nearest=N`` forces the N nearest radars to the bbox centre instead.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import s3
from usdata.providers._http import _HttpProvider
from usdata.providers.base import QueryError
from usdata.providers.noaa import sites
from usdata.providers.params import OptionalUpperStrList, positive_int

BUCKET = "unidata-nexrad-level2"
MAX_WINDOW = timedelta(days=31)
KEY_RE = re.compile(r"^(?P<site>[A-Z]{4})(?P<stamp>\d{8}_\d{6})(?:_V0[36])?(?:\.gz)?$")


def scan_time(key: str) -> datetime | None:
    """UTC timestamp encoded in an object key, or None for non-scan objects."""
    m = KEY_RE.match(key.rsplit("/", 1)[-1])
    if not m:
        return None
    return datetime.strptime(m["stamp"], "%Y%m%d_%H%M%S").replace(tzinfo=UTC)


class NexradParams(BaseModel):
    """Which radars one NEXRAD query names, or how many to take from the query centre."""

    model_config = ConfigDict(extra="forbid")

    site: OptionalUpperStrList = Field(
        default=None, description="One radar ICAO id, for example KTLX."
    )
    sites: OptionalUpperStrList = Field(
        default=None, description="Several radar ICAO ids, comma-separated or a list."
    )
    nearest: Annotated[int, positive_int()] | None = Field(
        default=None,
        description="Take the N radars nearest the query centre instead of naming sites.",
    )

    @model_validator(mode="after")
    def _one_way_of_choosing_radars(self) -> NexradParams:
        """site, sites, and nearest are three alternatives, so only one may be given."""
        if self.site is not None and self.sites is not None:
            raise ValueError("pass only one of site or sites")
        if self.nearest is not None and (self.site is not None or self.sites is not None):
            raise ValueError("nearest cannot be combined with site or sites")
        return self

    @property
    def named(self) -> list[str] | None:
        """The radar ids the query named through either key, or None when it named none."""
        return self.sites if self.sites is not None else self.site


class NexradLevel2(_HttpProvider):
    """NEXRAD Level II adapter. Params: ``site``/``sites`` (ICAO ids), ``nearest`` (int)."""

    params_model = NexradParams

    def select_sites(self, query: Query, params: NexradParams) -> list[str]:
        """Radar site ids the query refers to; see the module docstring for the rules."""
        if (named := params.named) is not None:
            for sid in named:
                try:
                    sites.get_site(sid)
                except KeyError as e:
                    raise QueryError(str(e)) from e
            return named
        if query.bbox is None:
            raise QueryError(f"{self.dataset.id} needs a location, bbox, lat/lon, or site=...")
        b = query.bbox
        lat, lon = (b.south + b.north) / 2, (b.west + b.east) / 2
        if params.nearest is not None:
            return [s.id for s in sites.nearest(lat, lon, params.nearest)]
        inside = sites.sites_in(b)
        if inside:
            return [s.id for s in inside]
        return [s.id for s in sites.nearest(lat, lon, 1)]

    def list_assets(self, query: Query) -> list[Asset]:
        """Every volume scan for the selected sites inside the query's UTC time window."""
        params = self.parse_params(query, NexradParams)
        self.reject(
            query, "text", "variables", hint="whole volume scans are selected by site and time"
        )
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError("NEXRAD requests must span at most 31 days; split longer intervals")
        assets: list[Asset] = []
        for site in self.select_sites(query, params):
            day = start.date()
            while day <= end.date():
                prefix = f"{day:%Y/%m/%d}/{site}/"
                for obj in s3.list_objects(BUCKET, prefix, self._http()):
                    ts = scan_time(obj.key)
                    if ts is None or not (start <= ts <= end):
                        continue
                    assets.append(
                        Asset(
                            id=obj.key.rsplit("/", 1)[-1],
                            dataset_id=self.dataset.id,
                            href=f"s3://{BUCKET}/{obj.key}",
                            protocol=Protocol.S3,
                            media_type="application/octet-stream",
                            size=obj.size,
                            time=TimeRange(start=ts, end=ts),
                        )
                    )
                day += timedelta(days=1)
        assets.sort(key=lambda a: a.id)
        return assets

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one scan object anonymously to ``dest``."""
        return s3.download(asset.href, dest, self._http())
