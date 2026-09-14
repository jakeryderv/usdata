!!! note "Times are UTC"
    Timestamps without a timezone are treated as UTC, including queries built
    directly in Python; explicit offsets are converted to UTC. Both bounds are
    inclusive. A date-only end means midnight at the start of that day, so a
    window from `2024-05-07` to `2024-05-07` contains only that midnight. See
    [time and place](/concepts/time-and-place.md).
