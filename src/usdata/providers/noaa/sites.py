"""NEXRAD and TDWR radar site table, bundled from the NCEI HOMR station list."""

from __future__ import annotations

import csv
import math
from functools import lru_cache
from importlib import resources

from pydantic import BaseModel, ConfigDict

from usdata.models import BBox

EARTH_RADIUS_KM = 6371.0


class RadarSite(BaseModel):
    """A radar site from the bundled table. ``type`` is NEXRAD, TDWR, or TEST."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    state: str
    lat: float
    lon: float
    elev_ft: int | None = None
    type: str

    def distance_km(self, lat: float, lon: float) -> float:
        """Great-circle distance from this site to a point, in kilometres."""
        p1, p2 = math.radians(self.lat), math.radians(lat)
        dphi = p2 - p1
        dlam = math.radians(lon - self.lon)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def all_sites() -> dict[str, RadarSite]:
    """The bundled site table keyed by ICAO id."""
    text = (resources.files("usdata.data") / "nexrad_sites.csv").read_text()
    sites = {}
    for row in csv.DictReader(text.splitlines()):
        row["elev_ft"] = row["elev_ft"] or None
        site = RadarSite.model_validate(row)
        sites[site.id] = site
    return sites


def get_site(site_id: str) -> RadarSite:
    """Look up a site by ICAO id, case-insensitively."""
    try:
        return all_sites()[site_id.upper()]
    except KeyError:
        raise KeyError(f"unknown radar site {site_id!r}") from None


def sites_in(bbox: BBox, *, types: tuple[str, ...] = ("NEXRAD",)) -> list[RadarSite]:
    """Sites of the given types whose location lies inside ``bbox``, sorted by id."""
    return sorted(
        (s for s in all_sites().values() if s.type in types and bbox.contains_point(s.lat, s.lon)),
        key=lambda s: s.id,
    )


def nearest(
    lat: float, lon: float, n: int = 1, *, types: tuple[str, ...] = ("NEXRAD",)
) -> list[RadarSite]:
    """The ``n`` closest sites of the given types to a point, nearest first."""
    candidates = [s for s in all_sites().values() if s.type in types]
    return sorted(candidates, key=lambda s: s.distance_km(lat, lon))[:n]
