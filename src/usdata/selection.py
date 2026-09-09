"""Pure selection among listed assets; no provider, cache, or reader operations."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Literal

from usdata.models import Asset, TemporalSelection


def _utc(value: datetime | None, label: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{label} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def select_by_time(
    candidates: Iterable[Asset],
    *,
    target: datetime,
    tolerance: timedelta,
    direction: Literal["nearest", "at_or_before"],
) -> TemporalSelection:
    """Select an asset by start time using an explicit tolerance and direction.

    ``nearest`` admits starts on either side of target; ``at_or_before`` admits
    only starts no later than target. The tolerance boundary is inclusive.
    Equal distances break ties lexically by asset ID, then dataset ID. Duplicate
    (dataset_id, id) identities and missing/naive starts raise ValueError, even
    for candidates that would not win. All supplied candidates are validated.

    Target is normalized to UTC for comparison and in the result. The signed
    offset is asset start minus target, in seconds. If no candidate qualifies,
    the result has no asset/offset and eligible_count=0. Inputs are not modified.
    Matching by start does not establish acquisition completion or availability.
    """
    target = _utc(target, "target")
    if not isinstance(tolerance, timedelta) or tolerance < timedelta(0):
        raise ValueError("tolerance must be a nonnegative timedelta")
    if direction not in ("nearest", "at_or_before"):
        raise ValueError("direction must be 'nearest' or 'at_or_before'")

    seen: set[tuple[str, str]] = set()
    best: Asset | None = None
    best_offset: timedelta | None = None
    best_key: tuple[timedelta, str, str] | None = None
    eligible_count = 0
    for asset in candidates:
        if not isinstance(asset, Asset):
            raise ValueError("candidates must contain Asset instances")
        identity = (asset.dataset_id, asset.id)
        if identity in seen:
            raise ValueError(f"duplicate candidate identity: {identity!r}")
        seen.add(identity)
        start = _utc(asset.time.start if asset.time is not None else None, f"{identity!r} start")
        offset = start - target
        if abs(offset) > tolerance or (direction == "at_or_before" and offset > timedelta(0)):
            continue
        eligible_count += 1
        key = (abs(offset), asset.id, asset.dataset_id)
        if best_key is None or key < best_key:
            best, best_offset, best_key = asset, offset, key

    return TemporalSelection(
        target=target,
        tolerance=tolerance,
        direction=direction,
        asset=best,
        offset_seconds=best_offset.total_seconds() if best_offset is not None else None,
        candidate_count=len(seen),
        eligible_count=eligible_count,
    )
