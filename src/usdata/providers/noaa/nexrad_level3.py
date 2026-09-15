"""NEXRAD Level III products from the ``unidata-nexrad-level3`` public S3 bucket.

Keys are flat: ``SITE_PRODUCT_YYYY_MM_DD_HH_MM_SS``, where ``SITE`` is the radar's
ICAO id without its first letter (``KTLX`` is ``TLX``) and ``PRODUCT`` is a
three-character Level III code. The bucket begins on 2020-03-30 and holds every
product since; earlier products are archived at NCEI, which this adapter does not
reach. Each object is one product for one volume scan, and there is no reader:
``open()`` refuses these files and points at ``fetched.path`` for Py-ART.

Site selection reuses the Level II rules (``site``/``sites``, then radars inside
the bbox, then the nearest). ``products`` is required and validated against the
allowlist below, so every request names the products it downloads.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import Field, model_validator

from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.nexrad import MAX_WINDOW, NexradLevel2, NexradParams
from usdata.providers.params import UpperStrList

BUCKET = "unidata-nexrad-level3"
ARCHIVE_START = datetime(2020, 3, 30, tzinfo=UTC)
NCEI_ARCHIVE = "https://www.ncei.noaa.gov/products/radar"
KEY_RE = re.compile(
    r"^(?P<site>[A-Z0-9]{3})_(?P<product>[A-Z0-9]{3})_"
    r"(?P<stamp>\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})$"
)
TILTS = "0123AB"
TILTED_FAMILIES: Mapping[str, str] = {
    "B": "base reflectivity, super-resolution (since 2022-02-18)",
    "G": "base velocity, super-resolution (since 2022-02-18)",
    "Q": "base reflectivity, 256 levels (retired 2022-09-08; use B)",
    "U": "base velocity, 256 levels (retired 2022-09-08; use G)",
    "S": "storm-relative mean radial velocity",
    "C": "correlation coefficient",
    "X": "differential reflectivity",
    "K": "specific differential phase",
    "H": "hydrometeor classification",
}
SINGLE_PRODUCTS: Mapping[str, str] = {
    "NCR": "composite reflectivity",
    "EET": "enhanced echo tops",
    "DVL": "digital vertically integrated liquid",
    "NMD": "mesocyclone detection",
    "NST": "storm tracking information",
    "NTV": "tornado vortex signature (retired 2022-05-24)",
    "NVW": "VAD wind profile",
    "DHR": "digital hybrid-scan reflectivity",
    "HHC": "hybrid hydrometeor classification",
    "DAA": "digital one-hour precipitation accumulation",
    "DTA": "digital storm-total precipitation accumulation",
    "DSP": "digital storm-total precipitation",
    "OHA": "one-hour precipitation accumulation",
}
PRODUCTS: Mapping[str, str] = {
    **{
        f"N{tilt}{family}": f"{meaning}, elevation slot {tilt}"
        for family, meaning in TILTED_FAMILIES.items()
        for tilt in TILTS
    },
    **SINGLE_PRODUCTS,
}


def product_time(key: str) -> tuple[str, str, datetime] | None:
    """``(site, product, UTC time)`` from a flat key, or None for other objects."""
    m = KEY_RE.match(key)
    if not m:
        return None
    stamp = datetime.strptime(m["stamp"], "%Y_%m_%d_%H_%M_%S").replace(tzinfo=UTC)
    return m["site"], m["product"], stamp


def bucket_site(icao: str) -> str:
    """The three-character key prefix for a four-character ICAO radar id."""
    return icao.upper()[1:]


class NexradLevel3Params(NexradParams):
    """The Level II radar selection, plus the Level III product codes to download."""

    products: UpperStrList = Field(
        description="Required Level III product codes, comma-separated or a list, "
        "for example N0B,NMD."
    )

    @model_validator(mode="after")
    def _products_are_in_the_allowlist(self) -> NexradLevel3Params:
        """Every code is checked against the bucket's vocabulary before any request."""
        if unknown := [code for code in self.products if code not in PRODUCTS]:
            raise ValueError(
                f"unknown Level III products: {', '.join(unknown)}; "
                f"supported codes are {', '.join(sorted(PRODUCTS))}"
            )
        return self


class NexradLevel3(NexradLevel2):
    """NEXRAD Level III adapter. Params: Level II site selection plus ``products``."""

    params_model = NexradLevel3Params

    def list_assets(self, query: Query) -> list[Asset]:
        """Every selected product for the selected sites inside the UTC time window."""
        params = self.parse_params(query, NexradLevel3Params)
        self.reject(
            query, "text", "variables", hint="products and site select whole Level III files"
        )
        start, end = self.utc_window(query)
        if end - start > MAX_WINDOW:
            raise QueryError("NEXRAD requests must span at most 31 days; split longer intervals")
        if start < ARCHIVE_START:
            raise QueryError(
                f"the {BUCKET} bucket begins on {ARCHIVE_START:%Y-%m-%d}; earlier Level III "
                f"products are archived at NCEI ({NCEI_ARCHIVE}) and are not reachable here"
            )
        assets: list[Asset] = []
        for icao in self.select_sites(query, params):
            site = bucket_site(icao)
            for product in params.products:
                day = start.date()
                while day <= end.date():
                    prefix = f"{site}_{product}_{day:%Y_%m_%d}_"
                    for obj in s3.list_objects(BUCKET, prefix, self._http()):
                        parsed = product_time(obj.key)
                        if parsed is None or not (start <= parsed[2] <= end):
                            continue
                        assets.append(
                            Asset(
                                id=obj.key,
                                dataset_id=self.dataset.id,
                                href=f"s3://{BUCKET}/{obj.key}",
                                protocol=Protocol.S3,
                                media_type="application/octet-stream",
                                size=obj.size,
                                time=TimeRange(start=parsed[2], end=parsed[2]),
                            )
                        )
                    day += timedelta(days=1)
        assets.sort(key=lambda a: a.id)
        return assets

    def fetch(self, asset: Asset, dest: Path) -> Path:
        """Download one product object anonymously to ``dest``."""
        return s3.download(asset.href, dest, self._http())
