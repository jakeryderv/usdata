# 0029: Committed example lockfiles, restored on a schedule

Status: accepted. Date: 2026-09-16. Extends
[ADR 0018](0018-selective-lockfile-updates.md) and
[ADR 0025](0025-examples-as-usage-review.md).

## Context

The README says the lockfile is what a methods section cites, and the
pin-inputs guide tells a reader to commit `dataset.yaml` and
`dataset.lock.json` together. The repository does neither: `.gitignore`
excludes `examples/**/*.lock.json`, every example resolves its manifest afresh
when its notebook runs, and the notebook runner copies only the manifest into
its working directory. No shipped example demonstrates a committed lockfile
being restored later than the run that wrote it, which is the one thing the
lockfile exists for.

The drift documentation states that every source revises and the provider
notes say how, but the project has no measurement behind either sentence.
Restoration against a pin older than a few minutes happens only when a person
does it by hand.

Not every example is a candidate. Sixteen examples have manifests. Ten of them
name query-shaped services (NCEI station data, CO-OPS, ERDDAP subsets) or
whole-file archives that are replaced in place (Storm Events, SPC, HURDAT2),
which the provider notes document as revising. Six name only object archives
on public buckets, whose objects are written once and republished rarely.
Their listings on 2026-09-16:

| Example | Dataset | Assets | Bytes |
|---|---|---|---|
| `goes-imagery` | `noaa:goes-abi` | 1 | 3,821,830 |
| `glm-flashes` | `noaa:goes-glm` | 180 | 90,506,951 |
| `hrrr-environment` | `noaa:hrrr` | 1 | 150,114,757 |
| `mrms-rotation` | `noaa:mrms` | 11 | 2,028,483 |
| `gfs-environment` | `noaa:gfs` | 1 | 42,362,644 |
| `radar-products` | `noaa:nexrad-level3` | 16 | 49,432 |

Together: 210 assets and 289 MB, restorable in a few minutes on a CI runner.

## Decision

The six archive-backed examples commit their lockfiles. The ignore rule stays
for every other example, and the examples index says which is which and why.

A `restore` job joins the weekly Integration workflow beside `live` and
`notebooks`, discovered from the committed lockfiles by the same inventory
script. For each one it runs `usdata pull` into an empty cache and then
`usdata verify`, and the run fails when either exits non-zero. Drifted assets
are listed per example in the step summary, so the workflow history becomes
the record of how often each archive republishes.

The notebook runner copies a committed lockfile beside the manifest, so a
notebook that calls `pull` restores the pinned inputs rather than resolving
its query again. Re-pinning is explicit: `usdata pull --force` in the example
directory, with the lockfile diff reviewed in the pull request that carries it.

`just check` validates each committed lockfile offline: it parses, its manifest
checksum matches the manifest beside it, and every entry's checksum is present.
Nothing in the offline gate touches the network.

## Alternatives

- **Commit every example's lockfile.** The query-service examples would turn
  the weekly job red at the first upstream revision and keep it red until
  someone re-pinned, which measures nothing after the first failure. Their
  drift is already visible when the notebook run re-resolves them.
- **Restore inside the notebook job.** The notebooks re-resolve on purpose so
  their saved outputs track current upstream behaviour. A restore is a
  different question, against a pin that is deliberately old, and it needs no
  kernel or reader extra.
- **Let the restore job re-pin on drift.** That would make the job always
  pass and would move a pin without anyone deciding to. ADR 0018 settled that
  pins move only when named.

## Consequences

The repository holds the artifact its README describes, and a restore against
a pin that is weeks or months old runs every Monday. When an archive
republishes an object, the failure names the example and the asset, and the
fix is a reviewed `--update` or `--force` that shows exactly which bytes
changed.

Committed lockfiles add 210 entries of JSON to the tree and change only when a
manifest changes or a pin is deliberately moved. A manifest edit without a
re-pin fails the offline gate, so the two cannot drift apart silently.

The job proves that pinned bytes are still served. It cannot recover bytes
that are not, which is [ADR 0030](0030-content-addressed-mirror.md).
