"""Local Climatological Data (LCD) through the NCEI Access Data Service.

Params: ``stations`` (list or comma string of eleven-digit LCD ids such as
``72353013967``) and ``units`` (metric or standard). Both dates are required
and select whole calendar days. Each row is one report at the station's local
standard time: hourly METAR (``FM-15``), special (``FM-16``), synoptic
(``FM-12``), a daily summary (``SOD``), and a monthly summary (``SOM``), with
125 columns unless ``variables`` narrows them. Stations are chunked ten per
asset because hourly rows are wide.
"""

from __future__ import annotations

from usdata.providers.noaa.ghcnd import GhcnDaily


class LocalClimatologicalData(GhcnDaily):
    """LCD CSV subsets, reusing NCEI station discovery and HTTP transport."""

    ncei_dataset = "local-climatological-data"

    def _chunk_size(self) -> int:
        return 10
