!!! note "Times are UTC"
    Timestamps without a timezone are treated as UTC, including queries built
    directly in Python; explicit offsets are converted to UTC. Both bounds are
    inclusive. A date alone as the end means the last instant of that UTC day,
    so a window from `2024-05-07` to `2024-05-07` is that whole day; give the
    end a time to stop earlier. See [time and place](/concepts/time-and-place.md).
