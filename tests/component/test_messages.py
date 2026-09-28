import pytest
import respx

from usdata import MessageListing, get, list_messages
from usdata.protocols import s3
from usdata.providers import QueryError
from usdata.providers.noaa.hrrr import BUCKET
from usdata.query import build_query

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
RUN = "hrrr.20240506/conus/hrrr.t20z."
INDEX = "1:0:d=2024050620:REFC:entire atmosphere:{step}:\n2:40:d=2024050620:CAPE:surface:{step}:\n"


def listing(keys: list[tuple[str, int]]) -> str:
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    return (
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<IsTruncated>false</IsTruncated>{items}</ListBucketResult>"
    )


def query(**params):
    return build_query(
        start="2024-05-06T20:00Z", end="2024-05-06T20:00Z", cycle=20, forecast_hour="0,1", **params
    )


def test_each_file_a_query_resolves_to_lists_its_index() -> None:
    keys = [(f"{RUN}wrfsfcf{hour:02d}.grib2", 100) for hour in (0, 1)]
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing(keys))
        for (key, _), step in zip(keys, ("anl", "1 hour fcst"), strict=True):
            mock.get(f"{s3.https_url(BUCKET, key)}.idx").respond(200, text=INDEX.format(step=step))
        listings = list_messages(get("noaa:hrrr"), query())
    assert all(isinstance(listing, MessageListing) for listing in listings)
    assert [listing.asset.id for listing in listings] == [
        "hrrr.20240506.t20z.wrfsfcf00.grib2",
        "hrrr.20240506.t20z.wrfsfcf01.grib2",
    ]
    assert [[entry.selector for entry in listing.messages] for listing in listings] == [
        ["REFC:entire atmosphere:anl", "CAPE:surface:anl"],
        ["REFC:entire atmosphere:1 hour fcst", "CAPE:surface:1 hour fcst"],
    ]
    assert [entry.length for entry in listings[0].messages] == [40, 60]


def test_a_dataset_that_fetches_whole_files_is_refused_before_any_request() -> None:
    with respx.mock() as mock, pytest.raises(QueryError, match="no messages to list"):
        list_messages(get("noaa:ghcn-daily"), build_query(start="2024-05-06", end="2024-05-06"))
    assert not mock.calls


def test_a_query_naming_messages_is_refused_before_any_request() -> None:
    with respx.mock() as mock, pytest.raises(QueryError, match="drop messages"):
        list_messages(get("noaa:hrrr"), query(messages="CAPE:surface"))
    assert not mock.calls
