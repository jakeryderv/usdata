# 0024: Trust verified cache hits without re-hashing

Status: accepted. Date: 2026-09-15.

## Context

Every cache hit in `fetch` re-read the whole cached file and compared its
sha256 against the provenance sidecar, after the sidecar had already been
checked for dataset id, provider, source URL, size, and any checksum the
adapter declared. For a station CSV that cost nothing. For a 150 MB HRRR
GRIB2 file, or a day of NEXRAD volumes, it meant re-hashing gigabytes on
every re-run of a notebook that fetches the same assets it fetched a minute
earlier. The hash was paying for a case the surrounding checks had already
made unlikely: a file changed underneath the cache without its size changing
and without its sidecar being rewritten.

The cache and the lockfile answer different questions. The cache is a local
convenience that avoids a download. The lockfile is the reproducibility
contract: it says these exact bytes are the inputs, and `restore` and `verify`
exist to prove that claim. Charging the contract's price on every ordinary
fetch made large datasets slower without making the contract stronger.

## Decision

`fetch` trusts a cache hit without hashing when every existing sidecar check
passes and the cached file's `st_mtime_ns` is less than or equal to the
sidecar's. Everything else is unchanged: the same checks run in the same
order, the same progress events are emitted, and any other outcome hashes the
file, compares it with the sidecar, and refetches on a mismatch.

Modification time ordering is the signal because the core always writes the
sidecar after the data file lands, so on an untouched pair the sidecar is
never older. A data file that is newer than its sidecar was written by
something other than this fetch, which is exactly the case the hash catches. A
copied or restored cache directory that preserves timestamps keeps the same
ordering, and one that flattens both to a single instant compares equal and is
still trusted.

The failure direction is deliberate: unsure means hash. A missing or
unreadable sidecar, a stat that raises, a clock that moved backwards, or an
extraction that gives the data file the later timestamp all fall back to the
full hash, which is today's behaviour. The only way to lose is a file replaced
in place, with an identical size, whose mtime is left at or before the
sidecar's, and that requires deliberately rewriting timestamps.

`restore` and `verify` stay strict and re-hash every file. They are the
reproducibility path, they run once per environment rather than once per cell,
and their cost is the point. Extending this rule to `restore` waits on real
workload experience. The sidecar format is unchanged and `Provenance` gains no
fields; the decision uses filesystem metadata that already existed.

## Consequences

Repeated fetches of large cached assets return immediately instead of reading
the whole file, so notebooks and CLI loops over GRIB2 and NEXRAD stop paying a
per-run hashing cost that grows with the data. `fetch` and `verify` now differ
on purpose, and the guides say so: a cache hit is checked against its
provenance record, while `usdata verify` is what re-reads the bytes.

A user who edits a cached file and restores its old timestamps gets a trusted
hit where they previously got a refetch; `--force`, `usdata verify`, and
`pull` all still catch it. Cached bytes silently corrupted by hardware or a
filesystem are also caught later rather than at the next fetch, which is the
same guarantee a checksum gave: it tells you the bytes changed, not when.
