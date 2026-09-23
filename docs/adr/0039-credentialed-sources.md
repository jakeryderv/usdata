# 0039: Credentials come from the environment and never reach a pin

Status: accepted. Date: 2026-09-23. Extends
[ADR 0027](0027-provider-contract.md) and
[ADR 0030](0030-content-addressed-mirror.md).

## Context

Every source so far is anonymous. The 1.0 criteria in
[versioning](../versioning.md) ask for one that is not, so the contract covers
how a key is supplied, where it is kept, and what provenance records about it.
[Issue 222](https://github.com/jakeryderv/usdata/issues/222) picks the EPA AQS
Data API as the probe: free, public-domain data, and a key issued by email with
no login flow or SDK. NASA through earthaccess would decide the same questions
plus a dependency and an interactive login, so it comes second.

AQS authenticates with two query parameters on every request, `email` and
`key`. Probing the public test account on 2026-09-23 with the documented
`dailyData/bySite` example found three things that an anonymous source never
raised:

- **The response echoes the credential.** The JSON `Header` carries the request
  `url`, `email` and `key` included. Caching the response as received would put
  the key at rest in the cache, in any copy of it, and in the content-addressed
  mirror ([ADR 0030](0030-content-addressed-mirror.md)).
- **The response is not byte-stable.** Two identical requests seconds apart
  differed in `Header.request_time` and in the order of the 66 `Data` rows. A
  checksum pin on the bytes as received could never restore.
- **Transport errors echo it too.** An `httpx.HTTPStatusError` message is
  `Client error '403 Forbidden' for url 'https://…?email=me%40x.org&key=…'`, so
  an unhandled HTTP error prints the key to a terminal, a log, or CI output.

The core already has the places a credential could leak into: `Asset.href` is
the lockfile's pinned URL and the provenance `source_url`, and it is printed by
`fetch --dry-run` and `pull --dry-run`; `doctor` prints the value of each
environment variable it reports.

## Decision

**Where keys live.** Credentials come from environment variables only, named
`USDATA_<SYSTEM>_<FIELD>`: `USDATA_AQS_EMAIL` and `USDATA_AQS_KEY`. A manifest
never holds one; an adapter's parameter model has no field for them, so
`-p key=…` or `params: {key: …}` is the usual unknown-parameter error, with a
hint naming the variable. A credentials file, keyring support, and `.env`
loading are left to the user's shell or secret manager: `op run`, direnv, and
CI secrets all deliver environment variables already. Because the core
resolves credentials, a file can be added later without changing an adapter.

**The registry declares them.** A dataset entry gains an optional `credentials`
block: the variable names it requires and the URL where a key is issued. The
catalog, `search`, and the generated pages show "requires a free key" from it,
and the registry-schema check (ADR 0026) holds the entry and adapter together.

**The core resolves them; the adapter receives them.** `load_adapter` reads the
declared variables and passes them to the constructor as
`Provider(dataset, *, credentials=...)`. The value is a small `Credentials`
mapping whose `repr` and `str` redact every value, so a traceback or a debug
print of an adapter shows `Credentials(USDATA_AQS_KEY=***)`. Adapters never read
`os.environ`. That keeps the policy in one place and lets offline tests pass
sentinel values.

**Missing credentials fail before any request.** If a declared variable is unset
or empty, `load_adapter` raises `MissingCredentials`, a `QueryError` subclass
(CLI exit 2). Its message names the missing variables and the signup URL.
`pull` checks every source that will contact its service before fetching any
source, as it already does for parameters. A locked restore that the cache
satisfies contacts nothing and needs no key.

**A pinned entry can restore from the mirror without a key.** When a locked
restore reaches an entry the cache cannot supply, its source's credentials are
missing, and `USDATA_MIRROR_URL` is set, restore skips the source and fetches
`<mirror>/sha256/<checksum>` directly. It verifies the object against the same
pin and reports it under `mirrored`, as ADR 0030 does for a source that no longer
serves its bytes. Only an entry the mirror also lacks raises
`MissingCredentials`. Resolution, `--update`, and `--force` always need the key,
since they must ask the service. The key authorizes contact with the service,
not the data: the data is public domain, and the pinned bytes are credential-free
and checksummed. Without a key, restore cannot check whether upstream has
changed, which is the drift ADR 0030 refused to hide by serving the mirror
first. The result therefore says those entries were not checked against their
source.

**Credentials never reach a pin, a file, or a message.** Four rules follow, and
the contract checks in `usdata.testing` verify all of them for any adapter whose
entry declares credentials. The checks run the adapter with sentinel values, then
search every asset, provenance sidecar, lockfile, fetched file, dry-run line,
and raised exception for those values:

1. `Asset.href` and every other `Asset` field are credential-free. The adapter
   adds credentials to the request when it sends it, never to the URL it
   returns. The pinned URL then shows exactly what was requested, and anyone
   can repeat the request with their own key.
2. The bytes written by `fetch` are credential-free and deterministic. When a
   service echoes the request or varies the bytes between identical requests,
   `fetch` writes a canonical form and says so. For AQS that form keeps the
   JSON structure, drops `Header.url` and `Header.request_time`, sorts `Data`
   by the columns that identify a row, and serializes with sorted keys and fixed
   separators. The step is recorded in `Provenance.transformations`, as a
   partial fetch's range selection already is. This is a documented exception to
   "exact bytes", allowed only where bytes as received cannot be pinned. A real
   data revision upstream (AQS stamps `date_of_last_change` on each row) still
   changes the canonical bytes, and still surfaces as drift.
3. Transport errors are re-raised with credentials redacted from the URL and the
   message, inside the adapter, before they leave `list_assets` or `fetch`.
4. `Provenance` gains `credentials: list[str]`: the names of the variables
   the source requires to fetch this file, never their values. The names are
   fixed by convention and identical for every user, so they reveal nothing
   about who fetched the file. They tell a reader of one standalone sidecar
   what they would need to fetch it again, even if the registry later changes.
   The list is the same whether the bytes came from the service or the mirror.
   It is empty for anonymous sources, so earlier lockfiles and sidecars read
   unchanged.

**Diagnostics.** `doctor` reports each declared credential variable as set or
unset for the datasets that need it, and never prints its value. `cite` needs no
key: a citation comes from the registry and the lockfile.

**Tests and CI.** Offline adapter tests use sentinel credentials and mocked HTTP.
Live tests read `USDATA_AQS_EMAIL` and `USDATA_AQS_KEY` from repository secrets,
and skip with the variable names when they are unset. The documented AQS test
account is not used; it is shared and rate-limited for the documentation's
examples. The adapter paces its own requests to AQS's terms: one at a time, at
most ten per minute, with a pause between them.

## Alternatives

- **Credentials in the manifest.** Simplest to read, and wrong: a manifest is
  meant to be committed and shared, and a lockfile beside it would be one
  `git push` from publishing the key.
- **Adapters read the environment themselves.** No contract change, but every
  adapter would reimplement the missing-key check, and nothing could guarantee
  it happens before the first request.
- **Cache the bytes as received and redact only provenance.** Leaves the key at
  rest in the cache and the mirror, and the checksum could never restore.
- **Convert AQS responses to CSV.** It would reuse the CSV reader, but it is a
  format normalization the roadmap keeps out of scope. The canonical JSON stays
  what the service sent, minus two header fields.
- **A credentials file or keyring from the start.** A file needs a format, a
  default location, permission checks, and rules for which source wins: a
  second source of truth. Keyring adds a dependency. Environment variables work
  with every secret manager and CI system, and a file can be added later in the
  core alone.
- **Fail a keyless restore instead of using the mirror.** Stricter, but it would
  make the AQS example the only one a reader cannot restore without
  registering, for bytes that are public and already verified by checksum.
- **Record a boolean in provenance.** Smaller, but its only advantage was
  revealing less about local setup, and fixed variable names reveal nothing.

## Consequences

The `Provider` constructor changes, so the release that ships this changes the
published contract (ADR 0027). The versioning page's "two minor releases
without contract changes" clock for 1.0 starts after it. Anonymous adapters are
unaffected: `credentials` defaults to empty, and their bytes stay exact.

A shared manifest and lockfile stay useful to someone without a key: the cache,
or the mirror for the objects it holds, restores every pinned file. The project
mirror holds what the committed example lockfiles pin, so the AQS example and
the weekly restore job need no key to restore. Only contacting the service needs
a key of one's own.

The canonical-bytes rule is the first time the core accepts bytes an adapter
reshaped for a reason other than subsetting. It is limited to what cannot be
pinned otherwise, and recorded per file. A reader of the cache sees JSON that
parses the same way as the service's, not the service's exact text.

Census (a key on every request) and NASA (earthaccess) are expected to fit these
rules. If one does not, that is a later amendment, not a reason to widen this
one in advance.
