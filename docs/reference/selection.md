# Time selection

What `select_by_time` is for and what its policy means is explained in
[time and place](../concepts/time-and-place.md#choosing-one-file-by-time).
It is imported from `usdata` and takes a finite iterable of already-listed
`Asset` objects.

```python
from datetime import UTC, datetime, timedelta

from usdata import select_by_time

selection = select_by_time(
    assets,
    target=datetime(2024, 5, 10, 10, 50, tzinfo=UTC),
    tolerance=timedelta(minutes=5),
    direction="nearest",
)
```

## Arguments

All three keyword arguments are required.

| Argument | Contract |
|---|---|
| `target` | A timezone-aware `datetime`; normalized to UTC for comparison and in the result. No timezone is guessed. |
| `tolerance` | A nonnegative `timedelta`, measured from each asset's start. The boundary is inclusive; zero requires an exact instant. |
| `direction` | `"nearest"` admits either side of the target; `"at_or_before"` admits only starts at or before it. |

The closest eligible start wins. Equal absolute offsets break ties lexically by
asset id, then dataset id. Equivalent UTC instants compare equally across
offsets and repeated daylight-saving wall times. An asset's `time.end` is not
used.

Every supplied asset must have an aware `time.start`, including assets that
would not win. Missing or naive starts, invalid arguments, and duplicate
`(dataset_id, id)` pairs raise `ValueError`; the helper does not skip or
deduplicate. Repeated ids in different datasets are allowed.

## Result

The returned `TemporalSelection` is available from `usdata` or `usdata.models`.

| Field | Meaning |
|---|---|
| `asset` | The selected `Asset`, or `None` when nothing qualifies. |
| `offset_seconds` | Selected start minus target, in seconds; negative is earlier. `None` for no match. |
| `candidate_count` | Number of supplied candidates. |
| `eligible_count` | Number satisfying both tolerance and direction; zero for no match. |
| `target`, `tolerance`, `direction` | The policy used. |

Empty inputs and inputs entirely outside the policy return a no-match result.
Invalid metadata raises even when an earlier candidate is an exact match.
`model_dump_json()` serializes the result for your records.
