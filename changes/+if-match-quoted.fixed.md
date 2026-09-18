Partial GRIB2 fetches send `If-Match` as a quoted entity-tag, as HTTP specifies, rather than the bare value that only S3 tolerates. Lockfiles and provenance records are unchanged.
