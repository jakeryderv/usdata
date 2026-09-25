A `Retry-After` header holding a non-ASCII digit such as `²` no longer escapes as a bare `ValueError`; like any unreadable value, it falls back to the usual retry backoff.
