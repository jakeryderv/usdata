"""Universal Transverse Mercator coordinates to latitude and longitude, northern hemisphere.

Krüger's series to third order in the third flattening, as given with the UTM
definition (scale 0.9996 on the central meridian, false easting 500 km, false
northing zero). Within a zone it agrees with a full-precision projection to well
under a millimetre, far finer than the few metres NGS states for the imagery it
serves. The ellipsoid is GRS 80; WGS 84 differs from it by a tenth of a
millimetre in the semi-minor axis, which does not matter at that scale.
"""

from __future__ import annotations

import math

A_AXIS = 6378137.0
FLATTENING = 1 / 298.257222101
SCALE = 0.9996
FALSE_EASTING = 500_000.0

_N = FLATTENING / (2 - FLATTENING)
_RECTIFYING = A_AXIS / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64)
_BETA = (
    _N / 2 - 2 * _N**2 / 3 + 37 * _N**3 / 96,
    _N**2 / 48 + _N**3 / 15,
    17 * _N**3 / 480,
)
_DELTA = (
    2 * _N - 2 * _N**2 / 3 - 2 * _N**3,
    7 * _N**2 / 3 - 8 * _N**3 / 5,
    56 * _N**3 / 15,
)


def to_lonlat(zone: int, easting: float, northing: float) -> tuple[float, float]:
    """Longitude and latitude in degrees of a northern-hemisphere UTM coordinate in metres.

    Raises:
        ValueError: ``zone`` is not 1 to 60.
    """
    if not 1 <= zone <= 60:
        raise ValueError(f"UTM zone must be 1 to 60, not {zone}")
    xi = northing / (SCALE * _RECTIFYING)
    eta = (easting - FALSE_EASTING) / (SCALE * _RECTIFYING)
    xi_prime = xi - sum(
        b * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, b in enumerate(_BETA, 1)
    )
    eta_prime = eta - sum(
        b * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, b in enumerate(_BETA, 1)
    )
    chi = math.asin(math.sin(xi_prime) / math.cosh(eta_prime))
    latitude = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(_DELTA, 1))
    central = 6 * zone - 183
    longitude = central + math.degrees(math.atan2(math.sinh(eta_prime), math.cos(xi_prime)))
    return longitude, math.degrees(latitude)
