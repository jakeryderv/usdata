!!! warning "Upstream revisions"
    Agencies revise files in place. A locked restore downloads each pinned URL
    and fails with a checksum mismatch when the bytes have changed; accept the
    new bytes for chosen entries with `pull --update`, or re-resolve the whole
    manifest with `pull --force`. A lockfile detects changed data; it does not
    archive it. Keep the cache with the manifest and lockfile. See
    [provenance and drift](/concepts/provenance-and-drift.md).
