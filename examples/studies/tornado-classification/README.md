# Labeled inputs for a tornado classifier

Open the [executed notebook](tornado-classification.ipynb) to reproduce one labeled feature row
for Oklahoma Storm Events tornado report 1184052 and a twelve-row table of
rotation and lightning features for tornado, hail, and thunderstorm-wind reports
from the same evening. The [manifest](dataset.yaml) pins the 2024 Storm Events
archive, one KTLX Level II volume at its discovered scan start, nine two-minute
MRMS `RotationTrackML30min_00.50` grids, and sixty-nine 20-second GOES-16 GLM
files. The notebook converts local report times to UTC with the source timezone
column, checks the locked radar and rotation selections against live listings,
computes each feature inside a stated neighbourhood, plots the rotation field
around the case with the report and radar marked, and verifies cached and
empty-cache restoration of all 80 locked assets.

Requires usdata v0.15.0 or later for the MRMS, GLM, and GRIB2 reader support,
and the repository's examples, radar, netcdf, and grib environments. Run
`just notebooks` from the repo root; see the
[examples guide](https://usdata.dev/studies/#run) for setup and fresh-kernel
checks. Expect about 68 MB of source downloads, another 68 MB for restoration,
and about 1.3 GB of peak memory while each MRMS grid is decoded and cropped.
Source revisions can change; preserve the manifest, its generated lockfile, and
cached bytes for your own analysis.

The table has one tornado, two hail, and nine wind rows from fourteen minutes
of one supercell's path. It demonstrates how the inputs are built and labeled;
it is not a dataset, the classes are not separable in it, and the notebook does
not train a model. The closing section lists the labeling caveats that a real
study must handle.
