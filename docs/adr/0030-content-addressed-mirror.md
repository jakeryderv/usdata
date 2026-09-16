# 0030: A content-addressed mirror of pinned bytes

Status: accepted. Date: 2026-09-16. Extends
[ADR 0015](0015-separate-sites-and-data-storage.md),
[ADR 0018](0018-selective-lockfile-updates.md), and
[ADR 0029](0029-committed-example-lockfiles.md).

## Context

A lockfile pins a sha256, and the provenance page is explicit about what that
buys: a checksum proves the bytes you have are the bytes that were pinned, and
cannot recover bytes that are gone. Every source usdata serves revises. Once an
archive republishes an object, a lockfile that pinned the old bytes can only
report drift, and the analysis that cited it cannot be re-run from its record.

[ADR 0015](0015-separate-sites-and-data-storage.md) reserved the `usdata` R2
bucket for dataset files, served publicly at `data.usdata.dev` with GET and
HEAD CORS for the two site origins, and kept its upload credentials in GitHub
secrets. It deferred general remote caching until four questions were settled:
how an object is looked up, when a cached copy is fresh, who may upload, and
what may be evicted. Those questions are hard for a cache keyed by asset id,
where two runs can pin different bytes under one id and a republished object
would overwrite the bytes an older lockfile depends on. They were never
settled, so the bucket has held nothing but a probe object.

The six committed example lockfiles of ADR 0029 reference 289 MB. R2 charges
nothing for egress and its free allowance is 10 GB-months of storage.

## Decision

The mirror is keyed by content and by nothing else. An object lives at
`sha256/<hex>`, the lowercase hex of the checksum the lockfile already records
for it. That answers the four deferred questions without a schema change:

- **Lookup** is the lockfile entry's checksum. `Asset`, `Provenance`,
  `LockedAsset`, and `Lockfile` gain no field. An entry that pins byte ranges
  is covered the same way, because its checksum is over the concatenated bytes
  the file holds.
- **Freshness** does not arise. Two objects with one key have one content;
  an upload is idempotent and a re-upload is harmless.
- **Upload ownership** is CI only. The weekly restore job uploads any pinned
  object the mirror lacks, after the restore has passed, using the retained
  secrets. No developer machine, no notebook, and no browser holds upload
  credentials, and the SDK has no upload path.
- **Eviction** is a rule, not a policy: an object is kept while any lockfile
  committed on `main` references its checksum. Pruning is a manually invoked
  workflow that lists keys, subtracts every checksum in every committed
  lockfile, and deletes the rest. Nothing deletes automatically.

On the read side, restore is unchanged until the pinned URL fails to
reproduce the pin: the bytes differ, the object is gone, or a range request is
refused. Then, and only when a mirror is configured, restore fetches
`<mirror>/sha256/<checksum>`, verifies it against the same pin, and writes the
file. The provenance sidecar records that the mirror served the bytes in one
optional field, absent for every record written today, so existing sidecars
and lockfiles load unchanged and `LockedAsset` still requires the href to
equal the pinned source URL. Drift is still reported, so the caller learns the
agency moved on; the restore no longer fails.

The mirror is opt-in through one setting, `USDATA_MIRROR_URL`, unset by
default. The project's own mirror holds only the objects its committed
lockfiles pin, so a default would send every other user's checksums to a host
that cannot serve them.

The mirror stores bytes and a content type. Provenance stays in the lockfile
and sidecar; the mirror never becomes the record of where bytes came from.

## Alternatives

- **A general write-through remote cache (issue 11).** Keyed by asset id or
  URL, it needs every deferred question answered, and it turns the bucket into
  a second cache with its own drift. It stays in Later; this decision does not
  preclude it, and a later cache can sit beside a content-addressed store
  without touching it.
- **Mirror on first fetch.** Every fetch would upload, so every user would
  need write access or the SDK would need a relay. Uploading only what a
  committed lockfile pins keeps the mirror small and its contents reviewable.
- **Serve examples from the mirror first.** Faster, but it would hide upstream
  drift, which the restore job exists to measure. Upstream is always tried
  first.
- **Per-release archives.** ADR 0015 removed the last of those. Content
  addressing reuses identical bytes across releases by construction.

## Consequences

A committed lockfile becomes restorable after its archive republishes, from
the bytes it pinned, with the same verification. The examples can claim what
the README claims.

The mirror serves only checksums that exist in committed lockfiles, so it is
useful to anyone re-running a shipped example and to nobody else. A user who
wants the same guarantee for their own manifests runs their own mirror behind
the same setting; the layout is one directory of files named by hash, which
any static host can serve.

Storage grows only when a committed lockfile pins bytes the mirror lacks,
which after the first upload means a deliberate re-pin. Pruning is a decision
made by running a workflow, never a side effect.

Out of scope: uploads from the SDK, lookup by anything but checksum, the
general remote cache of issue 11, and any promise about retention beyond the
rule above.
