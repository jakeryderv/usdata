from datetime import UTC, datetime, timedelta, timezone, tzinfo
from itertools import permutations
from typing import Any

import pytest

from usdata import Asset, TemporalSelection, TimeRange, select_by_time
from usdata.models import Protocol

TARGET = datetime(2024, 5, 10, 10, 50, tzinfo=UTC)


def candidate(id: str, seconds: float = 0, dataset: str = "test:scenes") -> Asset:
    return Asset(
        id=id,
        dataset_id=dataset,
        href=f"https://example.test/{dataset}/{id}",
        protocol=Protocol.HTTP,
        time=TimeRange(start=TARGET + timedelta(seconds=seconds)),
    )


def test_nearest_and_prior_have_distinct_signed_offsets_and_counts():
    # Tallahassee's two observed GOES start offsets, plus an out-of-window item.
    candidates = [candidate("future", 77.4), candidate("prior", -222.6), candidate("old", -301)]
    before = [asset.model_dump_json() for asset in candidates]
    nearest = select_by_time(
        iter(candidates), target=TARGET, tolerance=timedelta(minutes=5), direction="nearest"
    )
    prior = select_by_time(
        candidates, target=TARGET, tolerance=timedelta(minutes=5), direction="at_or_before"
    )
    assert nearest.asset == candidates[0]
    assert nearest.offset_seconds == 77.4
    assert (nearest.candidate_count, nearest.eligible_count) == (3, 2)
    assert prior.asset == candidates[1]
    assert prior.offset_seconds == -222.6
    assert (prior.candidate_count, prior.eligible_count) == (3, 1)
    assert [asset.model_dump_json() for asset in candidates] == before
    assert TemporalSelection.model_validate_json(nearest.model_dump_json()) == nearest


@pytest.mark.parametrize("direction", ["nearest", "at_or_before"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_inclusive_microsecond_boundary(direction: Any, offset: int):
    asset = candidate("boundary", offset / 1_000_000)
    result = select_by_time(
        [asset], target=TARGET, tolerance=timedelta(microseconds=1), direction=direction
    )
    qualifies = direction == "nearest" or offset <= 0
    assert (result.asset is not None) == qualifies
    assert result.offset_seconds == (offset / 1_000_000 if qualifies else None)
    outside = select_by_time(
        [candidate("outside", -0.000002)],
        target=TARGET,
        tolerance=timedelta(microseconds=1),
        direction=direction,
    )
    assert outside.asset is None and outside.eligible_count == 0


def test_zero_tolerance_exact_match_and_complete_validation():
    result = select_by_time(
        [candidate("past", -0.000001), candidate("exact"), candidate("future", 0.000001)],
        target=TARGET,
        tolerance=timedelta(0),
        direction="at_or_before",
    )
    assert result.asset is not None and result.asset.id == "exact"
    assert result.offset_seconds == 0
    assert result.candidate_count == 3 and result.eligible_count == 1


def test_interval_overlap_or_completion_does_not_replace_start_selection():
    overlapping = candidate("overlapping", -600)
    overlapping.time = TimeRange(start=TARGET - timedelta(minutes=10), end=TARGET)
    unfinished = candidate("unfinished", -20)
    unfinished.time = TimeRange(
        start=TARGET - timedelta(seconds=20), end=TARGET + timedelta(minutes=2)
    )
    result = select_by_time(
        [overlapping, unfinished],
        target=TARGET,
        tolerance=timedelta(minutes=5),
        direction="at_or_before",
    )
    assert result.asset == unfinished and result.eligible_count == 1
    assert result.offset_seconds == -20


@pytest.mark.parametrize("candidates", [[], [candidate("old", -301)], [candidate("future", 1)]])
def test_no_match_retains_policy_and_counts(candidates):
    result = select_by_time(
        candidates, target=TARGET, tolerance=timedelta(minutes=5), direction="at_or_before"
    )
    assert result.asset is None and result.offset_seconds is None
    assert result.candidate_count == len(candidates) and result.eligible_count == 0
    assert result.target == TARGET
    assert result.tolerance == timedelta(minutes=5)
    assert result.direction == "at_or_before"
    assert TemporalSelection.model_validate_json(result.model_dump_json()) == result


def test_ties_are_order_independent_by_asset_then_dataset_id():
    candidates = [candidate("z", -10), candidate("a", 10, "b:scenes"), candidate("a", -10)]
    for ordered in permutations(candidates):
        result = select_by_time(
            ordered, target=TARGET, tolerance=timedelta(seconds=10), direction="nearest"
        )
        assert result.asset == candidates[1]  # 'b:scenes' sorts before 'test:scenes'.
        assert result.offset_seconds == 10  # A tie does not imply preferring the past.
        assert result.eligible_count == 3


def test_equivalent_instants_are_compared_in_utc_without_rewriting_assets():
    asset = candidate("exact")
    original_start = TARGET.astimezone(timezone(timedelta(hours=-5)))
    asset.time = TimeRange(start=original_start)
    result = select_by_time(
        [asset],
        target=TARGET.astimezone(timezone(timedelta(hours=9))),
        tolerance=timedelta(0),
        direction="nearest",
    )
    assert result.asset == asset and result.offset_seconds == 0
    assert result.target.tzinfo is UTC
    assert asset.time.start is original_start


class FoldTimezone(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=-4 if dt is None or dt.fold == 0 else -5)

    def dst(self, dt):
        return timedelta(0)


def test_shared_timezone_fold_compares_instants_not_wall_clock():
    zone = FoldTimezone()
    earlier = datetime(2024, 11, 3, 1, 30, tzinfo=zone, fold=0)
    later = earlier.replace(fold=1)
    asset = candidate("earlier")
    asset.time = TimeRange(start=earlier)
    result = select_by_time(
        [asset], target=later, tolerance=timedelta(hours=1), direction="at_or_before"
    )
    assert result.asset == asset and result.offset_seconds == -3600


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("target", TARGET.replace(tzinfo=None), "timezone-aware"),
        ("target", "2024-05-10", "timezone-aware"),
        ("target", None, "timezone-aware"),
        ("tolerance", timedelta(microseconds=-1), "nonnegative timedelta"),
        ("tolerance", 300, "nonnegative timedelta"),
        ("tolerance", float("nan"), "nonnegative timedelta"),
        ("direction", "before", "direction"),
        ("direction", None, "direction"),
    ],
)
def test_invalid_policy_rejected_even_with_no_candidates(field, value, match):
    options: dict[str, Any] = {
        "target": TARGET,
        "tolerance": timedelta(seconds=300),
        "direction": "nearest",
    }
    options[field] = value
    with pytest.raises(ValueError, match=match):
        select_by_time([], **options)


@pytest.mark.parametrize("time", [None, TimeRange(), TimeRange(start=TARGET.replace(tzinfo=None))])
def test_invalid_candidate_time_is_not_silently_skipped_after_exact_match(time):
    invalid = candidate("invalid")
    invalid.time = time
    with pytest.raises(ValueError, match="start must be a timezone-aware"):
        select_by_time(
            [candidate("exact"), invalid],
            target=TARGET,
            tolerance=timedelta(0),
            direction="nearest",
        )


def test_duplicate_identity_rejected_even_outside_selection_window():
    with pytest.raises(ValueError, match="duplicate candidate identity"):
        select_by_time(
            [candidate("duplicate", 400), candidate("duplicate", 500)],
            target=TARGET,
            tolerance=timedelta(0),
            direction="at_or_before",
        )


def test_invalid_candidate_type():
    candidates: Any = ["not an asset"]
    with pytest.raises(ValueError, match="Asset instances"):
        select_by_time(candidates, target=TARGET, tolerance=timedelta(0), direction="nearest")


@pytest.mark.parametrize(
    "seconds,limit,expected",
    [(-158, 120, False), (-158, 300, True), (77.4, 60, False), (77.4, 120, True)],
)
def test_observed_research_tolerance_cases(seconds, limit, expected):
    result = select_by_time(
        [candidate("scan", seconds)],
        target=TARGET,
        tolerance=timedelta(seconds=limit),
        direction="nearest",
    )
    assert (result.asset is not None) == expected
