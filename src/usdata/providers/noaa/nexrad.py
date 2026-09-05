"""NEXRAD Level II archive from the ``unidata-nexrad-level2`` public S3 bucket.

Key layout: ``YYYY/MM/DD/SITE/SITEYYYYMMDD_HHMMSS[_V06][.gz]``. One object per
volume scan. ``_MDM`` objects are metadata sidecars and are skipped. There is
no server-side subsetting; a query selects sites and a time window and every
whole scan in that window is an asset.

Site selection, in order: ``site=``/``sites=`` params, then radars located
inside the query bbox, then the single radar nearest the bbox centre.
``nearest=N`` forces the N nearest radars to the bbox centre instead.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from usdata.models import Asset, Dataset, Protocol, Query, TimeRange
from usdata.protocols import http, s3
from usdata.providers.base import Provider, QueryError
from usdata.providers.noaa import sites

BUCKET = "unidata-nexrad-level2"
KEY_RE = re.compile(r"^(?P<site>[A-Z]{4})(?P<stamp>\d{8}_\d{6})(?:_V0[36])?(?:\.gz)?$")


def _sites_param(raw: object) -> list[str]:
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, (list, tuple)) or not all(isinstance(s, str) for s in raw):
        raise QueryError("sites must be a string or list of strings")
    ids = list(dict.fromkeys(s.strip().upper() for s in raw if s.strip()))
    if not ids:
        raise QueryError("sites must not be empty")
    return ids


def scan_time(key: str) -> datetime | None:
    """UTC timestamp encoded in an object key, or None for non-scan objects."""
    m = KEY_RE.match(key.rsplit("/", 1)[-1])
    if not m:
        return None
    return datetime.strptime(m["stamp"], "%Y%m%d_%H%M%S").replace(tzinfo=UTC)


class NexradLevel2(Provider):
    """NEXRAD Level II adapter. Params: ``site``/``sites`` (ICAO ids), ``nearest`` (int)."""

    def __init__(self, dataset: Dataset, client: httpx.Client | None = None) -> None:
        super().__init__(dataset)
        self._client = client
        self._owns_client = client is None

    def close(self) -> None:
        """Close an internally created HTTP client; injected clients belong to the caller."""
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = http.client()
        return self._client

    def select_sites(self, query: Query) -> list[str]:
        """Radar site ids the query refers to; see the module docstring for the rules."""
        if unknown := set(query.params) - {"site", "sites", "nearest"}:
            raise QueryError(f"unsupported NEXRAD params: {', '.join(sorted(unknown))}")
        if "site" in query.params and "sites" in query.params:
            raise QueryError("pass only one of site or sites")
        if "nearest" in query.params and {"site", "sites"}.intersection(query.params):
            raise QueryError("nearest cannot be combined with site or sites")
        raw = query.params.get("sites", query.params.get("site"))
        if {"site", "sites"}.intersection(query.params):
            ids = _sites_param(raw)
            for sid in ids:
                try:
                    sites.get_site(sid)
                except KeyError as e:
                    raise QueryError(str(e)) from e
            return ids
        if query.bbox is None:
            raise QueryError(f"{self.dataset.id} needs a location, bbox, lat/lon, or site=...")
        b = query.bbox
        lat, lon = (b.south + b.north) / 2, (b.west + b.east) / 2
        if "nearest" in query.params:
            count = query.params["nearest"]
            if isinstance(count, bool) or not isinstance(count, (int, str)):
                raise QueryError("nearest must be a positive integer")
            try:
                count = int(count)
            except ValueError:
                raise QueryError("nearest must be a positive integer") from None
            if count < 1:
                raise QueryError("nearest must be a positive integer")
            return [s.id for s in sites.nearest(lat, lon, count)]
        inside = sites.sites_in(b)
        if inside:
            return [s.id for s in inside]
        return [s.id for s in sites.nearest(lat, lon, 1)]

    def list_assets(self, query: Query) -> list[Asset]:
        """Every volume scan for the selected sites inside the query's UTC time window."""
        if query.time is None or query.time.start is None or query.time.end is None:
            raise QueryError(f"{self.dataset.id} requires both start and end times")
        start = query.time.start.astimezone(UTC)
        end = query.time.end.astimezone(UTC)
        assets: list[Asset] = []
        for site in self.select_sites(query):
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
