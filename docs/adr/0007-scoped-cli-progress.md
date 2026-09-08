# 0007: Scoped internal events for CLI progress

Status: accepted. Date: 2026-09-08.

## Context

Fetch and pull need terminal progress while adapters own downloads and core owns
cache validation. Threading callbacks through the public Provider and fetch APIs
would expand their compatibility contract solely for CLI presentation. Core must
remain independent of providers and CLI rendering, with no new runtime dependency.

## Decision

Use private immutable events and a ContextVar observer installed around a CLI
operation. Core emits resolved batches and assets after validation; shared HTTP
transport emits bytes written per attempt. The context manager restores its prior
observer on success and failure, and supports nested observation. SDK calls have
no observer by default. Provider and public SDK signatures remain unchanged.

Render throttled progress using the standard library on stderr only when both
stdout and stderr are terminals. Support `--no-progress`; preserve redirected
output, exit codes, and stdout result records. Show known and unknown sizes
separately. Resolved byte estimates include assets that may already be cached.
Each manifest source forms its own batch; locked restoration forms one batch.

## Consequences

Events are an internal synchronous contract, not an SDK subscription API. A future
parallel downloader would need explicit context propagation and event coordination.
No new dependency or provider code is required. Providers that assemble files from
metadata requests receive asset-level reporting without byte reporting.

HTTP retries reset bytes to zero; previous failed attempts are never added to the
current file. Content-Length is a byte total only for identity encoding, because
HTTP writes decoded bytes. Unknown sizes are never converted to zero-byte totals.
Cached assets are counted only after validation and downloads only after checksum
and provenance success. Existing checksum, atomic file, and lockfile behavior stay
in core, independently of display state.
