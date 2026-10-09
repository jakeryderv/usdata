<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:spc-outlooks` · **Source only** · Install from [source](../install.md#source-installation) to use this dataset. SPC Convective and Fire Weather Outlooks.

### At a glance

- Files: zipped shapefile (no reader)
- Selection: Outlooks issued inside an inclusive UTC window, one zip per UTC month; optionally outlook types, days, and geometry form
- Required inputs: Both timestamps; optionally outlooks (convective, fire), days, and geometry
- Open locally: Local files; no bundled reader for this format
- On usdata.dev: [SPC convective and fire weather outlook areas](https://usdata.dev/datasets/noaa/spc-outlooks/), with a walkthrough

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `days` | Outlook day(s) from 1 to 8; every day by default. |
| `geometry` | cake_layer (the default), where each threshold's area includes the higher ones inside it, or cookie_cutter, where each area excludes them. |
| `outlooks` | Outlook type(s): convective (the default), fire, or both. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `ISSUE` | UTC, YYYYMMDDHHMM | Start of the outlook's valid period |
| `EXPIRE` | UTC, YYYYMMDDHHMM | End of the outlook's valid period |
| `PRODISS` | UTC, YYYYMMDDHHMM | When SPC issued the product; the window's field |
| `TYPE` | — | C for convective, F for fire weather |
| `DAY` | — | Outlook day, 1 to 8 |
| `THRESHOLD` | — | Threshold label: a risk such as TSTM, MRGL, SLGT, ENH, MDT, or HIGH, a probability such as 0.05, SIGN, or a fire risk such as ELEV or CRIT; empty for an outlook that drew no area |
| `CATEGORY` | — | What the threshold measures: CATEGORICAL, TORNADO, WIND, HAIL, ANY SEVERE, or FIRE WEATHER CATEGORICAL; empty for an outlook that drew no area |
| `CYCLE` | — | IEM's canonical issuance hour for the outlook, or -1 for one it superseded |

### Catalog facts

- Availability: Source only · intended for 0.35
- Domain: Severe weather
- Spatial resolution: One outlook area per row
- Temporal resolution: Each issuance; the Day 1 convective outlook at 01, 06, 13, 1630, and 20 UTC
- Updates: Not stated by IEM, which processes SPC's outlook products as they are issued
- Terms of use: <https://mesonet.agron.iastate.edu/disclaimer.php>
- Citation: NOAA/NWS Storm Prediction Center outlooks, as archived and served by the Iowa Environmental Mesonet of Iowa State University, accessed via usdata
- Catalog date range: 1987-01-01 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://mesonet.agron.iastate.edu/request/gis/outlooks.phtml)
- License: Public domain (NWS products; IEM materials are public domain, attribution appreciated)
- Transport: `http`
- Adapter: `usdata.providers.noaa.spc_outlooks:SpcOutlooks`
