# 0031: Stage refreshed files and commit the lockfile first

Status: accepted. Date: 2026-09-18.

## Context

`pull` with `update` re-fetches the entries it names and lets whatever bytes
arrive become their new pins ([ADR 0018](0018-selective-lockfile-updates.md)).
That decision promised that a run either succeeds completely or leaves the
lockfile as it was, and it kept the promise for the lockfile only. Each
refreshed file was written straight over its cached copy as the run went, so a
run that failed afterwards had already replaced cached files with bytes the
untouched lockfile did not pin.

Reproduced on two pinned files, `A` cached and valid and `B` missing, both
changed upstream: `pull(update=[A])` raised `UpstreamChanged` for `B`, left the
lockfile alone, and left `A` holding the new bytes. `verify` reported one
problem before the run and two after it. The failed run had destroyed a good
copy of a pinned input.

Two failures reach this state. Drift in an unselected entry is the one ADR 0018
describes. The other is anything that interrupts the refreshes themselves: a
network error, a full disk, or a killed process partway through a dataset's
entries.

## Decision

Restore settles every unselected entry before it refreshes any selected one. A
refresh accepts whatever upstream serves, so it can never be drift; holding the
refreshes back means a run that will fail on drift raises before it has
downloaded anything it would discard.

Refreshed files are then fetched into a staging root,
`<cache root>/.staging/<random>/`, through the same fetch path with that root
in place of the cache. The cache is not written during the refresh pass. When
every entry has succeeded the run commits in this order: the lockfile is saved,
and then each staged data file and its sidecar are renamed into the cache, data
before sidecar as an ordinary fetch writes them. The staging directory is
removed when the run ends, however it ends.

Staging lives inside the cache root so the commit is a rename on one
filesystem rather than a copy. Its name begins with a dot, which no provider id
can, so nothing that reads the cache as `<provider>/<name>/<asset id>` takes a
staged file for a cached one; `usdata cache` neither lists nor prunes it.

The lockfile moves first because something has to, and the two orders fail
differently. With the lockfile first, a crash before the renames leaves the
lockfile pinning the new bytes and the cache holding the old ones: a stale
cache, which is the case restore exists to repair, and the next `pull`
re-fetches bytes upstream was serving moments earlier. With the files first,
the same crash leaves cached bytes that nothing pins, which is the defect this
decision removes, and the next `pull` reports drift and asks for `update`
again. The lockfile is the record and the cache is a convenience, so the
record leads.

Only refreshes are staged. A pinned re-fetch or a mirror restore can only write
bytes the lockfile already pins, so it is correct to keep whether or not the
run succeeds, and keeping it spares the retry a download, as ADR 0018 intended.

The guarantee this buys: a `pull` that fails, for any reason, leaves the
lockfile as it was and every cached file either absent or matching it.

## Consequences

`update` needs room for the refreshed files beside the ones they replace until
the commit, where it previously overwrote in place. For a dataset of large
GRIB2 files that is a real, temporary doubling of those entries' footprint.

The commit is a sequence of renames, not one atomic step. The window in which
a crash leaves the cache stale is now the renames, milliseconds, rather than
the downloads, which can be minutes; and what it leaves is repaired by the
next `pull` with no `update`.

A process killed outright cannot clean up after itself, so it can leave a
directory under `.staging/`. Nothing reads it and it is safe to delete. It is
also invisible to `usdata cache`, including its size total; if that proves to
matter, pruning stale staging directories belongs with `cache prune`.

`FetchedAsset.path` for a refreshed entry names the file's home in the cache,
as before, and is valid once `pull` returns. `_fetch_asset` and the provider
contract are unchanged; staging is a choice of root, made in `restore`.
