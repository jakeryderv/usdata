# 0002: Anonymous S3 access over plain HTTPS, not an AWS SDK

Status: accepted. Date: 2026-09-05.

## Context

Several NOAA datasets (NEXRAD Level II, GOES, GHCN) live in public S3 buckets
under the Open Data program. The obvious way to read them is boto3 or
fsspec/s3fs. Both are large dependencies, both want credentials or explicit
unsigned-request configuration, and both bring their own retry, threading,
and configuration surfaces that leak into usdata's API.

Public buckets answer the S3 REST API without signatures: ListObjectsV2 via
`GET https://<bucket>.s3.amazonaws.com/?list-type=2&prefix=...` and objects
via plain `GET`. Continuation tokens handle pagination. Verified against
`unidata-nexrad-level2` during the v0.2 work.

## Decision

`usdata.protocols.s3` implements listing and download with the existing
`httpx` client and an XML parser from the standard library. It supports
public buckets only. No AWS SDK is a core dependency.

## Alternatives

- **boto3 with `UNSIGNED` config.** Works, but adds ~10 MB of dependencies
  and a second HTTP stack for a feature that needs two GET requests.
- **fsspec + s3fs.** Attractive if usdata later offers remote caches and
  xarray integration, both of which use fsspec. Deferred: if that happens,
  fsspec goes behind an extra and this module can delegate to it when present.
- **Per-provider HTTP mirrors.** Some datasets have HTTPS mirrors, but not all,
  and the S3 layout is the canonical one.

## Consequences

- Core dependencies stay at pydantic, pyyaml, typer, httpx.
- Requester-pays and private buckets are out of scope until a real dataset
  needs them. Adding signing then is a contained change inside `protocols.s3`.
- Region-specific endpoints are not handled; the buckets used so far resolve
  through the global endpoint. Revisit if a bucket requires a regional host.
