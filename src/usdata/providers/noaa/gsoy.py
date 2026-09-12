"""Annual station summaries through the NCEI Access Data Service.

Params: ``stations`` (list or comma string) and ``units`` (metric or standard).
Both dates are required; every UTC calendar year touched by the interval is
selected in full. Geographic discovery uses the same normalized year bounds.
"""

from usdata.models import Asset, Query, TimeRange
from usdata.providers.noaa.ghcnd import GhcnDaily


class GlobalSummaryYearly(GhcnDaily):
    """GSOY CSV subsets, reusing NCEI station discovery and HTTP transport."""

    ncei_dataset = "global-summary-of-the-year"

    def _yearly_query(self, query: Query) -> Query:
        start, end = self.utc_window(query)
        return query.model_copy(
            update={
                "time": TimeRange(
                    start=start.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
                    end=end.replace(
                        month=12, day=31, hour=23, minute=59, second=59, microsecond=999999
                    ),
                )
            }
        )

    def find_stations(self, query: Query) -> list[str]:
        """Find stations overlapping the selected complete calendar years."""
        return super().find_stations(self._yearly_query(query))

    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve annual CSVs with stable URLs and complete-year asset bounds."""
        return super().list_assets(self._yearly_query(query))
