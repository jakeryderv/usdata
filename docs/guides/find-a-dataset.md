# Find a dataset

Search ranks the curated registry by keyword and can filter by provider,
place, and time. It runs offline and never queries an agency catalog, so
anything it returns as **available** can be fetched.

```console
$ usdata search precipitation --location "Cleveland County, OK"
noaa:ghcn-daily       available  since 0.2     GHCN-Daily Station Observations
noaa:climate-normals  available  since 0.11    U.S. Climate Normals 1991-2020
noaa:gsom             available  since 0.7     Global Summary of the Month
noaa:lcd              available  since 0.14    Local Climatological Data
noaa:nexrad-level2    available  since 0.2     NEXRAD Level II Radar
noaa:mrms             available  since 0.15    Multi-Radar Multi-Sensor (MRMS)
$ usdata info noaa:mrms
```

`info` prints a dataset's status, domain, license, extent, capabilities, and
every provider parameter it accepts with a one-line description. That list is
read from the adapter, so it is always current.

The [dataset browser](https://usdata.dev/datasets/) shows the same registry
with agency and support filters, each dataset's file format, how it selects
data, what inputs it requires, which reader extra opens it, and links to the
examples that use it. The
[catalog pages](../generated/catalog/index.md) here carry the same facts plus
endpoints and version history, and each links to the dataset's
[provider notes](../providers/README.md), where the quirks live: window
limits, local-time columns, sentinel values, and how the source revises.

Three things to read before fetching a dataset for the first time:

- **Selection rule.** A station query returns observations inside the window;
  Storm Events returns whole annual files; radar and satellite datasets return
  whole files whose start falls inside the window. The catalog's selection
  column says which.
- **Required inputs.** Some datasets need a station or site id, some need a
  satellite or product name, and some reject geographic selection entirely.
- **Maximum window.** Files that arrive every two minutes have one-day limits
  for a reason; use `--dry-run` to see the count and size before downloading.

--8<-- "_snippets/planned-datasets.md"

The [SPC tornadoes example](https://usdata.dev/examples/spc-tornadoes/) is a
one-file dataset with no parameters; the
[MRMS rotation example](https://usdata.dev/examples/mrms-rotation/) shows a
product parameter and a tight window.
