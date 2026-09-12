# Selecting assets by time

Available since v0.9. `select_by_time` is a pure core helper: pass a finite
iterable of already-listed `Asset` objects. It performs no listing, downloading,
cache writes, or decoding, and requires no scientific extras.

```python
from datetime import UTC, datetime, timedelta

from usdata import select_by_time

# assets is the result of a provider's list_assets(query).
selection = select_by_time(
    assets,
    target=datetime(2024, 5, 10, 10, 50, tzinfo=UTC),
    tolerance=timedelta(minutes=5),
    direction="nearest",
)
if selection.asset is None:
    print("No matching start in the supplied candidates")
else:
    print(selection.asset.id, selection.offset_seconds)
print(selection.model_dump_json(indent=2))
```

The [executed event-context notebook](https://usdata.dev/examples/event-context/)
shows provider listing, both selection directions, manifest verification, and
source-time conversion together.

## Explicit policy

All three keyword arguments are required:

| Argument | Contract |
|---|---|
| `target` | A timezone-aware `datetime`; normalized to UTC for comparison and in the result. No timezone is guessed. |
| `tolerance` | A nonnegative `timedelta`, measured from the asset start. The boundary is inclusive; zero requires an exact instant. |
| `direction` | `"nearest"` admits either side of target; `"at_or_before"` admits only starts at or before target. |

The closest eligible start wins. Equal absolute offsets break ties lexically by
asset ID, then dataset ID. A nearest tie does not prefer the earlier observation.
Equivalent UTC instants compare equally, including across offsets or repeated
daylight-saving wall times. Asset timestamps and other input fields are unchanged.

Every supplied asset must have an aware `time.start`, including assets that would
not win. Missing/naive starts, invalid policy arguments, and duplicate
`(dataset_id, id)` identities raise `ValueError`. Repeated IDs in different
datasets are allowed. The helper does not silently skip invalid candidates or
deduplicate conflicting records. An asset's `time.end` is not used for selection.

## Result and no match

The returned `TemporalSelection` is available from `usdata` or `usdata.models`:

| Field | Meaning |
|---|---|
| `asset` | Selected input asset, or `None` when no candidate qualifies. |
| `offset_seconds` | Selected start minus target in seconds; negative is earlier. `None` for no match. |
| `candidate_count` | Number of supplied candidates, not the size of a remote catalog. |
| `eligible_count` | Number satisfying both tolerance and direction. Zero for no match. |
| `target`, `tolerance`, `direction` | The explicit policy used for this selection. |

Empty inputs and valid inputs entirely outside the policy return a no-match
result. Invalid metadata raises instead, even when an earlier candidate is an
exact match. The helper validates and consumes the whole iterable once.

Save `model_dump_json()` alongside your analysis to record the choice and policy.
This is selection metadata, not source-byte provenance or a complete listing
snapshot. Preserve the candidate list if you need to audit all alternatives;
retain manifests, lockfiles, and cached bytes for source reproducibility.

## Scientific boundaries

Set provider query bounds to include the candidate starts your policy needs.
The helper cannot discover omitted candidates or infer a radar site, report
segment, product, timezone-label convention, or spatial coverage. It can compare
assets from different datasets, but the caller must decide whether they are
meaningful alternatives.

`at_or_before` means **start at or before target**, not that acquisition ended or
the file was available by then. A scan can start earlier and include later
observations. Scan completion, pixel/ray timing, publication delay, and any
prediction-time availability cutoff require separate checks. Spatial alignment,
cloud parallax, radar geometry, and quality control are also outside this helper.
