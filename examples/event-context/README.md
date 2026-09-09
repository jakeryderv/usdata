# Event context across three archives

Open the [executed notebook](example.ipynb) to reproduce the selection of a KTLX
radar volume and GOES-16 infrared scene near Oklahoma Storm Events report 1184052.
The [manifest](dataset.yaml) records this case's discovered scan starts. The
notebook checks nearest-start matching within five minutes, opens the unaffected
first radar sweep, plots native coordinates with explicit spatial/time caveats,
and verifies cached and empty-cache restoration of the three locked archives.

Requires usdata v0.9 or later for the `select_by_time` and `open(sweep=...)` APIs. Run `just notebooks` from the repo
root; see the [examples guide](../README.md) for setup and fresh-kernel checks.
Expect about 36 MB of source downloads, another 36 MB for restoration, and several
hundred MB of decoding memory. Source revisions can change; preserve the manifest,
its generated lockfile, and cached bytes for your own analysis. The notebook
reports the full-volume decoder limitation without trying to repair the archive.
