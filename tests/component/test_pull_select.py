"""A manifest source can keep only the asset nearest an instant (ADR 0044)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from usdata.manifest import Lockfile, Manifest, SourceSpec, lockfile_path
from usdata.models import Asset, Protocol, Query, TimeRange
from usdata.providers.base import Provider
from usdata.pull import EmptySource, plan, pull
from usdata.registry import Registry, default_registry

SCANS = {
    "KTLX20240507_043610": datetime(2024, 5, 7, 4, 36, 10, tzinfo=UTC),
    "KTLX20240507_044053": datetime(2024, 5, 7, 4, 40, 53, tzinfo=UTC),
    "KTLX20240507_044530": datetime(2024, 5, 7, 4, 45, 30, tzinfo=UTC),
}
WINDOWS: list[TimeRange] = []


class Scans(Provider):
    """Lists the scans that start inside the query's window, as a radar archive does."""

    def list_assets(self, query: Query) -> list[Asset]:
        assert query.time is not None and query.time.start and query.time.end
        WINDOWS.append(query.time)
        return [
            Asset(
                id=scan_id,
                dataset_id="noaa:ghcn-daily",
                href=f"https://example.test/{scan_id}",
                protocol=Protocol.HTTP,
                time=TimeRange(start=start, end=start),
            )
            for scan_id, start in SCANS.items()
            if query.time.start <= start <= query.time.end
        ]

    def fetch(self, asset: Asset, dest: Path) -> Path:
        dest.write_bytes(asset.id.encode())
        return dest


@pytest.fixture
def registry() -> Registry:
    WINDOWS.clear()
    reg = default_registry()
    dataset = reg.get("noaa:ghcn-daily").model_copy(update={"adapter": f"{__name__}:Scans"})
    return Registry(
        [dataset if d.id == dataset.id else d for d in reg],
        providers=[reg.provider(provider_id) for provider_id in sorted(reg.providers())],
        domains=reg.domains(),
        systems=reg.systems(),
    )


def manifest(tmp_path: Path, select: str, *, allow_empty: bool = False) -> Path:
    path = tmp_path / "dataset.yaml"
    path.write_text(
        "name: scans\nsources:\n  - dataset: noaa:ghcn-daily\n"
        + ("    allow_empty: true\n" if allow_empty else "")
        + f"    select: {select}\n"
    )
    return path


def test_nearest_keeps_the_one_scan_closest_to_the_instant(
    tmp_path: Path, registry: Registry
) -> None:
    path = manifest(tmp_path, "{time: 2024-05-07T04:41:17Z, within: 5m, direction: nearest}")
    result = pull(path, root=tmp_path / "cache", registry=registry)
    assert [item.asset.id for item in result.fetched] == ["KTLX20240507_044053"]
    # The window is the rule's: the instant, five minutes either side.
    assert [
        TimeRange(
            start=datetime(2024, 5, 7, 4, 36, 17, tzinfo=UTC),
            end=datetime(2024, 5, 7, 4, 46, 17, tzinfo=UTC),
        )
    ] == WINDOWS
    (entry,) = Lockfile.load(lockfile_path(path)).assets
    assert entry.asset.id == "KTLX20240507_044053"


def test_at_or_before_keeps_the_scan_in_progress_at_the_instant(
    tmp_path: Path, registry: Registry
) -> None:
    # 04:45:00 is nearer the 04:45:30 scan, but the one under way then began at 04:40:53.
    path = manifest(tmp_path, "{time: 2024-05-07T04:45:00Z, within: 10m, direction: at_or_before}")
    result = pull(path, root=tmp_path / "cache", registry=registry)
    assert [item.asset.id for item in result.fetched] == ["KTLX20240507_044053"]
    assert WINDOWS[0].end == datetime(2024, 5, 7, 4, 45, tzinfo=UTC)


def test_a_restore_pins_the_choice_and_never_lists_again(
    tmp_path: Path, registry: Registry
) -> None:
    path = manifest(tmp_path, "{time: 2024-05-07T04:41:17Z, within: 5m, direction: nearest}")
    first = pull(path, root=tmp_path / "cache", registry=registry)
    restored = pull(path, root=tmp_path / "cache", registry=registry)
    assert restored.from_lockfile and len(WINDOWS) == 1
    assert [item.asset.id for item in restored.fetched] == [first.fetched[0].asset.id]


def test_plan_prices_only_the_chosen_asset(tmp_path: Path, registry: Registry) -> None:
    path = manifest(tmp_path, "{time: 2024-05-07T04:44:00Z, within: 1h, direction: nearest}")
    (source,) = plan(path, registry=registry).sources
    assert [asset.id for asset in source.assets] == ["KTLX20240507_044530"]


def test_nothing_within_tolerance_is_an_empty_source(tmp_path: Path, registry: Registry) -> None:
    path = manifest(tmp_path, "{time: 2024-05-07T04:50:00Z, within: 90s, direction: nearest}")
    with pytest.raises(EmptySource, match=r"no asset starting within 0:01:30 of 2024-05-07T04:50"):
        pull(path, root=tmp_path / "cache", registry=registry)
    assert not lockfile_path(path).exists()
    allowed = manifest(
        tmp_path, "{time: 2024-05-07T04:50:00Z, within: 90s, direction: nearest}", allow_empty=True
    )
    assert pull(allowed, root=tmp_path / "cache", registry=registry).fetched == []


def test_equal_distances_break_by_asset_id(tmp_path: Path, registry: Registry) -> None:
    SCANS["KTLX20240507_044053b"] = SCANS["KTLX20240507_044053"]
    try:
        path = manifest(tmp_path, "{time: 2024-05-07T04:40:53Z, within: 0s, direction: nearest}")
        result = pull(path, root=tmp_path / "cache", registry=registry)
    finally:
        del SCANS["KTLX20240507_044053b"]
    assert [item.asset.id for item in result.fetched] == ["KTLX20240507_044053"]


@pytest.mark.parametrize(
    ("within", "expected"),
    [
        ("90s", timedelta(seconds=90)),
        ("5m", timedelta(minutes=5)),
        ("1h", timedelta(hours=1)),
        ("1d", timedelta(days=1)),
        ("PT2M30S", timedelta(minutes=2, seconds=30)),
        ("0s", timedelta(0)),
    ],
)
def test_within_reads_short_and_iso_durations(within: str, expected: timedelta) -> None:
    source = SourceSpec.model_validate(
        {
            "dataset": "noaa:nexrad-level2",
            "select": {"time": "2024-05-07T04:41Z", "within": within, "direction": "nearest"},
        }
    )
    assert source.select is not None and source.select.within == expected


@pytest.mark.parametrize(
    ("select", "extra", "message"),
    [
        ({"time": "2024-05-07T04:41Z", "within": "5m"}, {}, "direction"),
        ({"time": "2024-05-07T04:41Z", "direction": "nearest"}, {}, "within"),
        ({"time": "2024-05-07T04:41Z", "within": "5 min", "direction": "nearest"}, {}, "90s"),
        ({"time": "2024-05-07T04:41Z", "within": "P", "direction": "nearest"}, {}, "90s"),
        ({"time": "2024-05-07T04:41Z", "within": "5m", "direction": "after"}, {}, "direction"),
        (
            {"time": "2024-05-07T04:41Z", "within": "5m", "direction": "nearest"},
            {"start": "2024-05-07"},
            "drop start and end",
        ),
    ],
)
def test_a_select_rule_must_be_whole_and_alone(select: dict, extra: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Manifest.model_validate(
            {"name": "x", "sources": [{"dataset": "noaa:nexrad-level2", "select": select, **extra}]}
        )


def test_a_naive_select_time_means_utc() -> None:
    source = SourceSpec.model_validate(
        {
            "dataset": "noaa:nexrad-level2",
            "select": {"time": "2024-05-07T04:41:00", "within": "5m", "direction": "nearest"},
        }
    )
    assert source.select is not None
    assert source.select.time == datetime(2024, 5, 7, 4, 41, tzinfo=UTC)
