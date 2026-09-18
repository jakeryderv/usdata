"""IEM events adapter: the county code, the explicit window, the refusals, and the CSV path."""

import httpx
import pytest
import respx

from usdata import build_query, get
from usdata.models import Query
from usdata.providers.base import QueryError
from usdata.providers.noaa.nws_vtec import SERVICE_URL, NwsVtecEvents, VtecEventsParams

CSV = (
    b"vtec_year,iso_issued,issued,iso_expired,expired,eventid,phenomena,significance,"
    b"hvtec_nwsli,wfo,ugc,product_id,name,ph_name,sig_name,url\n"
    b"2024,2024-05-07T01:34:00Z,2024-05-07 01:34,2024-05-07T02:00:00Z,2024-05-07 02:00,44,TO,W,"
    b",TSA,OKC113,202405070134-KTSA-WFUS54-TORTSA,Tornado Warning,Tornado,Warning,"
    b"/vtec/?year=2024&wfo=KTSA&phenomena=TO&significance=W&eventid=0044\n"
)
EVENING = {"start": "2024-05-06T18:00Z", "end": "2024-05-07T12:00Z"}


def adapter() -> NwsVtecEvents:
    return NwsVtecEvents(get("noaa:nws-vtec-events"))


def query(**kwargs):
    return build_query(**{**EVENING, "location": "Osage County, OK", **kwargs})


def listed(**kwargs) -> httpx.URL:
    """The URL a query's one asset names; listing itself makes no request."""
    with adapter() as provider, respx.mock() as mock:
        (asset,) = provider.list_assets(query(**kwargs))
        assert not mock.calls
    return httpx.URL(asset.href)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start": None, "end": None},
        {"end": None},
        {"text": "tornado"},
        {"variables": ["phenomena"]},
        {"location": None},
        {"location": None, "bbox": (-97.1, 36.1, -96.0, 37.0)},
        {"location": None, "lat": 36.6, "lon": -96.4},
        {"location": "Oklahoma"},
        {"ugc": "OKC113"},
        {"location": None, "ugc": "OK113"},
        {"location": None, "ugc": "OKX113"},
        {"location": None, "ugc": "OKC1134"},
        {"location": None, "ugc": 113},
        {"phenomena": "TO"},
        {"significance": "W"},
        {"phenomena": "TOR", "significance": "W"},
        {"phenomena": "TO", "significance": "WW"},
        {"phenomena": "T&", "significance": "W"},
        {"typo": 1},
    ],
)
def test_bad_queries_fail_before_network(kwargs) -> None:
    with adapter() as provider, pytest.raises(QueryError), respx.mock() as mock:
        provider.list_assets(query(**kwargs))
    assert not mock.calls


def message(**params: object) -> str:
    with adapter() as provider, pytest.raises(QueryError) as raised:
        provider.parse_params(Query(params=params), VtecEventsParams)
    return str(raised.value)


def test_refusals_say_what_to_do_instead() -> None:
    assert "such as OKC113" in message(ugc="OK113")
    assert "phenomena and significance must be given together" in message(phenomena="TO")
    assert "phenomena must be two letters" in message(phenomena="TOR", significance="W")
    assert "significance must be one letter" in message(phenomena="TO", significance="WW")
    cases = {
        "does not support bbox or lat/lon": {"location": None, "lat": 36.6, "lon": -96.4},
        "Oklahoma is a state; name a county": {"location": "Oklahoma"},
        "requires a county location or a ugc": {"location": None},
        "a location and a ugc; pass one of them": {"ugc": "OKC113"},
    }
    for expected, kwargs in cases.items():
        with adapter() as provider, pytest.raises(QueryError, match=expected):
            provider.list_assets(query(**kwargs))


def test_a_county_becomes_its_postal_code_c_and_county_fips() -> None:
    assert listed().params["ugc"] == "OKC113"
    assert listed(location="40113").params["ugc"] == "OKC113"
    assert listed(location="Cleveland County, OK").params["ugc"] == "OKC027"
    # The District and the territories have postal codes too, so their counties resolve.
    assert listed(location="District of Columbia, DC").params["ugc"] == "DCC001"


def test_an_explicit_ugc_reaches_a_forecast_zone_a_county_cannot_name() -> None:
    url = listed(location=None, ugc="okz054")
    assert url.params["ugc"] == "OKZ054"


def test_the_window_is_sent_as_explicit_utc_datetimes_never_as_dates() -> None:
    params = listed().params
    assert params["sts"] == "2024-05-06T18:00:00Z"
    # ets is exclusive where a usdata end is inclusive, so one second is added.
    assert params["ets"] == "2024-05-07T12:00:01Z"
    assert "sdate" not in params and "edate" not in params and params["fmt"] == "csv"
    whole_days = listed(start="2024-05-06", end="2024-05-07").params
    assert (whole_days["sts"], whole_days["ets"]) == (
        "2024-05-06T00:00:00Z",
        "2024-05-08T00:00:00Z",
    )
    offset = listed(start="2024-05-06T13:00-05:00", end="2024-05-07T07:00-05:00").params
    assert (offset["sts"], offset["ets"]) == (params["sts"], params["ets"])


def test_an_event_type_is_sent_only_as_the_pair_the_service_requires() -> None:
    assert "phenomena" not in listed().params
    narrowed = listed(phenomena="to", significance="w").params
    assert (narrowed["phenomena"], narrowed["significance"]) == ("TO", "W")


def test_one_asset_with_a_stable_id_that_names_the_county() -> None:
    with adapter() as provider:
        (first,) = provider.list_assets(query())
        (again,) = provider.list_assets(query())
        (other,) = provider.list_assets(query(location="Cleveland County, OK"))
        (narrowed,) = provider.list_assets(query(phenomena="TO", significance="W"))
    assert first == again and first.id.startswith("vtec_OKC113_20240506_20240507_")
    assert first.id.endswith(".csv") and first.media_type == "text/csv" and first.size is None
    assert first.bbox is not None and first.time is not None
    assert len({first.id, other.id, narrowed.id}) == 3


@pytest.mark.l2
def test_fetch_writes_the_csv_and_the_reader_opens_it(tmp_path) -> None:
    from usdata import fetch

    with respx.mock() as mock:
        route = mock.get(SERVICE_URL).respond(200, content=CSV)
        (item,) = fetch(get("noaa:nws-vtec-events"), query(), root=tmp_path)
    assert route.call_count == 1 and item.path.read_bytes() == CSV
    pandas = pytest.importorskip("pandas")
    frame = item.open(parse_dates=["iso_issued", "iso_expired"])
    assert isinstance(frame, pandas.DataFrame)
    assert frame.ugc.tolist() == ["OKC113"] and frame.name.tolist() == ["Tornado Warning"]
    assert frame.iso_issued.iloc[0] == pandas.Timestamp("2024-05-07T01:34:00Z")


@pytest.mark.l2
def test_a_window_with_no_events_fetches_a_header_and_no_rows(tmp_path) -> None:
    from usdata import fetch

    header = CSV.split(b"\n", 1)[0] + b"\n"
    with respx.mock() as mock:
        mock.get(SERVICE_URL).respond(200, content=header)
        (item,) = fetch(get("noaa:nws-vtec-events"), query(), root=tmp_path)
    # There is no count to ask for, so an empty window is an empty file, not an empty listing.
    assert item.path.read_bytes() == header
