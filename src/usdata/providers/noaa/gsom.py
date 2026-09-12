"""Monthly station summaries through the NCEI Access Data Service.

Params: ``stations`` (list or comma string) and ``units`` (metric or standard).
Both dates are required; every UTC calendar month touched by the interval is
selected in full. Geographic discovery uses the same normalized month bounds.
"""

from calendar import monthrange

from usdata.models import Asset, Query, TimeRange
from usdata.providers.noaa.ghcnd import GhcnDaily


class GlobalSummaryMonthly(GhcnDaily):
    """GSOM CSV subsets, sharing NCEI station discovery and transport with GHCN."""

    ncei_dataset = "global-summary-of-the-month"

    def _monthly_query(self, query: Query) -> Query:
        start, end = self.utc_window(query)
        return query.model_copy(
            update={
                "time": TimeRange(
                    start=start.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                    end=end.replace(
                        day=monthrange(end.year, end.month)[1],
                        hour=23,
                        minute=59,
                        second=59,
                        microsecond=999999,
                    ),
                )
            }
        )

    def find_stations(self, query: Query) -> list[str]:
        """Find stations overlapping the selected complete calendar months."""
        return super().find_stations(self._monthly_query(query))

    def list_assets(self, query: Query) -> list[Asset]:
        """Resolve monthly CSVs with stable URLs and complete-month asset bounds."""
        return super().list_assets(self._monthly_query(query))
