# 0044: A manifest source can keep the asset nearest an instant

Status: accepted. Date: 2026-09-25.

## Context

Three worked examples recorded the same friction
([issue 330](https://github.com/jakeryderv/usdata/issues/330)): pinning one
NEXRAD volume or GOES scene meant already knowing its start to a fraction of a
second. The event-context study copied `04:41:17.300000` into its manifest from
a listing it had run first. The GOES example did the same with `12:01:18.1Z`.
The NEXRAD example chose a five-minute window instead, which holds one volume
in clear-air mode and can hold two in precipitation mode, and nothing in the
manifest said which mode the radar was in.

`select_by_time` already makes this choice for assets a caller has listed: a
target, a tolerance measured from each asset's start, a direction of `nearest`
or `at_or_before`, and ties broken by asset id. A manifest could not ask for
it. It could only name a window and take everything that started inside it.

## Decision

A manifest source takes an optional `select` block:

```yaml
- dataset: noaa:nexrad-level2
  params: {site: KTLX}
  select:
    time: 2024-05-07T04:41:00Z
    within: 5m
    direction: at_or_before
```

- **The rule gives the window.** The core lists the source over `time` plus
  or minus `within` for `nearest`, and the `within` before `time` for
  `at_or_before`. It then applies `select_by_time` to the listing and keeps the
  one asset it chooses. `start` and `end` beside `select` are refused, so a
  window has one spelling.
- **Every field is required.** `within` takes `90s`, `5m`, `1h`, `1d`, or an
  ISO 8601 duration, and zero asks for an exact start. `direction` has no
  default, as in `select_by_time`. A naive `time` means UTC, as it does
  everywhere else.
- **Nearest and at-or-before, not covering.** A mode that keeps the asset
  whose acquisition covers the instant would need true end times, and NEXRAD
  assets carry none: a volume's listed end is its start. For files acquired
  back to back, as radar volumes and satellite scans are, the latest start at
  or before an instant is the file under way at that instant, so
  `at_or_before` answers the covering question without new data.
- **The core applies it, not the adapters.** Selection is by start time and
  needs nothing an adapter knows, so any dataset whose assets carry a start
  can use it. That covers NEXRAD Level II and III, GOES ABI and GLM, and MRMS.
  An asset listed without a start fails the selection, as `select_by_time`
  already requires. No adapter changes.
- **Nothing new is pinned.** The manifest states the rule and the lockfile
  pins the asset it chose. The manifest checksum already ties the two
  together, so editing the rule makes the lockfile stale, as editing a window
  does. Restore never re-selects. A forced re-resolve applies the rule again,
  which picks the same file unless the archive changed.
- **No match is an empty source.** When nothing starts within the tolerance,
  the source is empty and the pull fails unless the source sets `allow_empty`.
  The error names the instant and the tolerance.

## Consequences

The three examples select by instant rather than by a copied start time. A
manifest now reads as the question it answers: the scan under way when a
tornado report was logged, not a timestamp found by listing first.

Listing costs are unchanged. The window a rule implies is no wider than the one
an author would have written by hand, and the adapters' window limits still
apply. A `within` larger than an adapter allows fails as a wider window would.

`plan` and `pull --dry-run` show the one chosen asset, since selection happens
where the listing does.

Not done here: a `fetch` flag for the same rule, and several instants in one
source. Several sources express the second; the first can follow if the SDK or
CLI shows a need for it.
