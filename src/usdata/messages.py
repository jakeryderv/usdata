"""The GRIB2 messages a query's files hold, read from their index sidecars.

A dataset declaring ``partial_fetch`` takes a ``messages`` parameter spelled in
its objects' index vocabulary, and this is where that vocabulary is listed.
Listing resolves the query as a fetch would and reads each object's index,
which is a few kilobytes; nothing else is downloaded, and nothing is cached or
recorded. See ADR 0046.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from usdata.models import Asset, Dataset, IndexEntry, Query
from usdata.providers import QueryError, load_adapter

PARTIAL_PARAM = "messages"
"""The parameter a ``partial_fetch`` dataset selects messages through."""


class MessageListing(BaseModel):
    """One file a query resolved to, and every field its index describes."""

    asset: Asset = Field(description="The whole-file asset, as a fetch without messages lists it")
    messages: list[IndexEntry] = Field(description="Every field in the object's index, in order")


def list_messages(dataset: Dataset, query: Query) -> list[MessageListing]:
    """List each file a query resolves to with the fields its index describes.

    Each entry's ``selector`` is a ``messages`` value that names exactly that
    field. A selector may stop after its level text, as ``CAPE:surface``, to
    name that field at whatever step each file holds.

    Args:
        dataset: A dataset declaring ``partial_fetch``.
        query: The query a fetch would take, without ``messages``.

    Returns:
        One listing per file, in the order a fetch would list them.

    Raises:
        QueryError: The dataset selects no messages, the query names
            ``messages``, or a file publishes no readable index.
    """
    if not dataset.capabilities.partial_fetch:
        raise QueryError(
            f"{dataset.id} fetches whole files, so it has no messages to list; "
            "only datasets that declare partial_fetch do"
        )
    if PARTIAL_PARAM in query.params:
        raise QueryError(
            f"drop {PARTIAL_PARAM}: the listing shows every message each file holds, "
            "whatever a selection would keep"
        )
    with load_adapter(dataset) as adapter:
        return [
            MessageListing(asset=asset, messages=adapter.list_messages(asset))
            for asset in adapter.list_assets(query)
        ]
