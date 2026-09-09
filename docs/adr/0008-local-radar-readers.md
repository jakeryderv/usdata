# 0008: Local radar readers use xradar DataTree

Status: accepted. Date: 2026-09-08.

## Context

NEXRAD files were fetchable but not directly usable through `FetchedAsset.open()`.
The proposed Py-ART backend's current NEXRAD decoder is deprecated in favor of
xradar. Probing xradar 0.12 verified legacy message-1 and current message-31
archives on Python 3.11 and 3.14. A radar volume has differently sized sweeps and
cannot faithfully be represented as a single tabular frame.

## Decision

Add `usdata[radar]` with a lazy xradar dependency. Return a fully loaded
`xarray.DataTree` with each sweep in its own child node. Infer `nexrad-level2`
from the fetched asset's dataset ID because its media type is opaque binary;
allow explicit reader selection. Keep CSV options specific to CSV. No registry
lookup or provider import is needed to open a restored asset.

Read only local bytes, decompress whole-file gzip/bzip2 in memory, and pass bytes
to xradar. Its file-object path is consumed across repeated sweep openings;
passing bytes avoids those failures and remote-path interpretation. Eagerly load
and close decoder resources before returning, including on load failure. Input
files, checksums, and provenance sidecars remain unchanged.

Use `incomplete_sweep="pad"` so received rays are not silently dropped. Absent
rays become NaN; retain xradar's geometry warnings. Mask reserved integer codes
for known NEXRAD moments after scaling, using each variable's own scale/offset:
0–1 for DBZH, VRADH, WRADH, ZDR, PHIDP, and RHOHV; 0–7 for CCORH. These are flags,
not physical measurements ([NOAA ICD 2620002Y](https://www.roc.noaa.gov/public-documents/icds/2620002Y.pdf),
Table III note 10 and Table XVII-I notes 21/30). xradar 0.12 does not attach fill
values for these codes. Preserve coordinates, units, encoding factors, and
unknown fields; discard only the backend's binary `source` encoding buffer.

Attach copied source provenance at `radar.attrs["usdata"]`. This describes the
input; callers must record their own analysis/export provenance. No generic
plugin reader registry or provider-specific model hints are introduced.

## Consequences

Core installation and imports stay lightweight. Radar environments are tested
on Linux Python 3.11 and 3.14, including installed wheels outside the checkout.
Small attributed offline fixtures test real compressed archive decoding and
flag masking; an executed notebook checks a full live current volume and plot.

Eager decoding can use substantially more memory than the compressed archive.
Incomplete sweeps may require approximate angle reconstruction, and legacy
files can lack site coordinates. Missing site coordinates are not filled in, and no rainfall
retrieval, clutter removal, velocity unfolding, or other scientific quality
control is performed. Advanced readers can use xradar directly on `item.path`.
