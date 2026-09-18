"""RAP adapter: file families, the 21 and 51 hour schedules, listing, and partial fetch."""

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from usdata.protocols import s3
from usdata.providers.base import QueryError
from usdata.providers.noaa.rap import BUCKET, FILES, Rap
from usdata.pull import pull, verify
from usdata.query import build_query
from usdata.registry import default_registry

LIST_URL = f"https://{BUCKET}.s3.amazonaws.com/"
RUN = "rap.20240506/rap.t20z."
KEY = f"{RUN}awp130pgrbf00.grib2"
OBJECT_URL = s3.https_url(BUCKET, KEY)
ETAG = "1ccf185b07bb3deab2a061e560b98895"
OBJECT = b"".join(b"GRIB" + bytes([number]) * 36 for number in (1, 2))
INDEX = "1:0:d=2024050620:REFC:entire atmosphere:anl:\n2:40:d=2024050620:CAPE:surface:anl:\n"


def listing(keys, token=None):
    items = "".join(f"<Contents><Key>{k}</Key><Size>{s}</Size></Contents>" for k, s in keys)
    trunc = (
        f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>"
        if token
        else "<IsTruncated>false</IsTruncated>"
    )
    return f'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{trunc}{items}</ListBucketResult>'


def run_listing(variant="awp130pgrb", hours: Iterable[int] = range(22), size=18_000_000):
    keys = []
    for hour in hours:
        keys.append((f"{RUN}{variant}f{hour:02d}.grib2", size + hour))
        keys.append((f"{RUN}{variant}f{hour:02d}.grib2.idx", 16000))
    return listing(keys)


def ranged(content: bytes = OBJECT, *, etag: str = ETAG):
    def respond(request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-Match") != f'"{etag}"':
            return httpx.Response(412)
        start, end = (int(value) for value in request.headers["Range"][6:].split("-"))
        return httpx.Response(
            206,
            content=content[start : end + 1],
            headers={"Content-Range": f"bytes {start}-{end}/{len(content)}"},
        )

    return respond


@pytest.fixture
def adapter():
    with httpx.Client() as client:
        yield Rap(default_registry().get("noaa:rap"), client=client)


def query(**kwargs):
    args: dict[str, Any] = {
        "start": "2024-05-06T20:00Z",
        "end": "2024-05-06T20:00Z",
        "cycle": 20,
        "forecast_hour": 0,
    }
    args.update(kwargs)
    return build_query(**args)


def test_lists_requested_hours_with_sizes_and_valid_times(adapter):
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=run_listing())
        assets = adapter.list_assets(query(forecast_hour="3, 0,3"))
    assert route.call_count == 1
    assert route.calls[0].request.url.params["prefix"] == RUN + "awp130pgrbf"
    assert [a.id for a in assets] == [
        "rap.20240506.t20z.awp130pgrbf03.grib2",
        "rap.20240506.t20z.awp130pgrbf00.grib2",
    ]
    analysis = assets[1]
    assert analysis.href == f"s3://{BUCKET}/{KEY}"
    assert analysis.size == 18_000_000 and analysis.media_type == "application/x-grib2"
    assert analysis.time and analysis.time.start == datetime(2024, 5, 6, 20, tzinfo=UTC)
    assert assets[0].time and assets[0].time.start == datetime(2024, 5, 6, 23, tzinfo=UTC)


@pytest.mark.parametrize("file", [None, *FILES])
def test_file_family_selects_prefix(adapter, file):
    params = {} if file is None else {"file": file}
    variant = FILES[file or "awp130"]
    with respx.mock() as mock:
        route = mock.get(LIST_URL).respond(200, text=run_listing(variant, hours=[0]))
        (asset,) = adapter.list_assets(query(**params))
    assert route.calls[0].request.url.params["prefix"] == f"{RUN}{variant}f"
    assert asset.id == f"rap.20240506.t20z.{variant}f00.grib2"


def test_extended_cycle_accepts_hour_51(adapter):
    run = "rap.20240506/rap.t03z."
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(
            200, text=listing([(f"{run}awp130pgrbf{h:02d}.grib2", 10) for h in range(52)])
        )
        assets = adapter.list_assets(
            query(start="2024-05-06T03:00Z", end="2024-05-06T03:00Z", cycle=3, forecast_hour=51)
        )
    assert [a.id for a in assets] == ["rap.20240506.t03z.awp130pgrbf51.grib2"]


def test_missing_run_and_missing_hour_are_named(adapter):
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([]))
        with pytest.raises(QueryError, match="no RAP awp130pgrb files for the 2024-05-06 20Z run"):
            adapter.list_assets(query())
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=run_listing(hours=range(3)))
        with pytest.raises(QueryError, match="2024-05-06 20Z run has no forecast hour\\(s\\) 05"):
            adapter.list_assets(query(forecast_hour=[1, 5]))


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"forecast_hour": 22}, "forecast_hour must be an integer from 0 to 21"),
        ({"forecast_hour": [0, 30]}, "forecast_hour must be an integer from 0 to 21"),
        ({"cycle": 3, "forecast_hour": 52}, "must be an integer from 0 to 51"),
        ({"file": "sfc"}, "file must be awp130, awp130b, prs, or nat"),
    ],
)
def test_schedule_and_family_rejections_name_the_rule(adapter, params, message):
    with respx.mock() as mock, pytest.raises(QueryError, match=message):
        adapter.list_assets(query(**params))
    assert not mock.calls


@pytest.mark.parametrize(
    "params",
    [
        {"start": None},
        {"cycle": None},
        {"cycle": 24},
        {"forecast_hour": None},
        {"forecast_hour": ""},
        {"resolution": "1p00"},
        {"location": "ok"},
        {"variables": ["cape"]},
        {"text": "forecast"},
        {"start": "2021-02-21T00:00", "end": "2021-02-21T20:00"},
        {"start": "2024-05-06T00:00", "end": "2024-05-07T00:01"},
        {"start": "2024-05-06T01:00Z", "end": "2024-05-06T05:00Z"},
    ],
)
def test_bad_queries_fail_before_network(adapter, params):
    with respx.mock() as mock, pytest.raises(QueryError):
        adapter.list_assets(query(**params))
    assert not mock.calls


def test_messages_resolve_to_one_partial_asset(adapter) -> None:
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, len(OBJECT))]))
        mock.head(OBJECT_URL).respond(
            200, headers={"Content-Length": str(len(OBJECT)), "ETag": f'"{ETAG}"'}
        )
        index = mock.get(f"{OBJECT_URL}.idx").respond(200, text=INDEX)
        (asset,) = adapter.list_assets(query(messages="CAPE:surface"))
    assert str(index.calls[0].request.url).endswith("awp130pgrbf00.grib2.idx")
    assert asset.id == "rap.20240506.t20z.awp130pgrbf00.part-d4735e3a265e.grib2"
    assert asset.href == f"s3://{BUCKET}/{KEY}#messages=2" and asset.size == 40


@pytest.mark.l2
def test_manifest_round_trips_a_partial_fetch(tmp_path: Path) -> None:
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text("""name: rap-messages
sources:
  - dataset: noaa:rap
    start: 2024-05-06T20:00Z
    end: 2024-05-06T20:00Z
    params: {cycle: 20, forecast_hour: 0, messages: "CAPE:surface"}
""")
    root = tmp_path / "cache"
    with respx.mock() as mock:
        mock.get(LIST_URL).respond(200, text=listing([(KEY, len(OBJECT))]))
        mock.head(OBJECT_URL).respond(
            200, headers={"Content-Length": str(len(OBJECT)), "ETag": f'"{ETAG}"'}
        )
        mock.get(f"{OBJECT_URL}.idx").respond(200, text=INDEX)
        mock.get(OBJECT_URL).side_effect = ranged()
        first = pull(manifest, root=root)
    (item,) = first.fetched
    assert item.path.read_bytes() == OBJECT[40:80]
    item.path.unlink()
    with respx.mock(assert_all_called=False) as mock:
        listed = mock.get(LIST_URL)
        mock.get(OBJECT_URL).side_effect = ranged()
        restored = pull(manifest, root=root)
    assert restored.from_lockfile and listed.call_count == 0
    assert verify(manifest, root=root) == []
