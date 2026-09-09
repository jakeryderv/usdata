"""Annual station summaries through the NCEI Access Data Service.

Params: ``stations`` (list or comma string) and ``units`` (metric or standard).
Both dates are required; every UTC calendar year touched by the interval is
selected in full. Geographic discovery uses the same normalized year bounds.
"""

from datetime import UTC

from usdata.models import Asset, Query, TimeRange
from usdata.providers.base import QueryError
from usdata.providers.noaa.ghcnd import GhcnDaily


class GlobalSummaryYearly(GhcnDaily):
    """GSOY CSV subsets, reusing NCEI station discovery and HTTP transport."""

    ncei_dataset = "global-summary-of-the-year"

    def _yearly_query(self, query: Query) -> Query:
        if query.text is not None:
            raise QueryError(f"{self.dataset.id} does not support text queries")
        if "stations" in query.params and query.bbox is not None:
            raise QueryError("pass stations or a location/bbox, not both")
        if query.time is None or query.time.start is None or query.time.end is None:
            raise QueryError(f"{self.dataset.id} requires both start and end dates")
        start = query.time.start.replace(tzinfo=query.time.start.tzinfo or UTC).astimezone(UTC)
        end = query.time.end.replace(tzinfo=query.time.end.tzinfo or UTC).astimezone(UTC)
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
