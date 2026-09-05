# Security Policy

## Supported versions

Only the latest release on PyPI receives fixes. Before 1.0 there are no
maintenance branches.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository
(Security tab → Report a vulnerability), or email jakervanslyke@gmail.com.
Please do not open a public issue for security problems.

You will get an acknowledgement within a week. Fixes ship as a patch release
with a changelog entry crediting the reporter unless they prefer otherwise.

## Scope

usdata fetches files from public government services and writes them to a
local cache. The parts that matter for security are:

- URL and object-key construction from registry entries and user input.
  Adapters must not let user-supplied values escape the intended host or
  bucket.
- Cache paths derived from asset ids. Ids are sanitized before use; a
  registry entry or upstream listing must not be able to write outside the
  cache directory.
- Provenance and lockfile records. These are meant to be trustworthy; changes
  that could let them misreport a source or checksum are security relevant.

usdata sends no telemetry and needs no credentials for the datasets it
currently supports.
