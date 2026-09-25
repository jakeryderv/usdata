# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/) as described in
[docs/content/versioning.md](docs/versioning.md).

## [Unreleased]

Upcoming notes are maintained as [individual fragments](changes/README.md).
The documentation site assembles their preview automatically.

<!-- towncrier release notes start -->

## [0.27.0](https://github.com/jakeryderv/usdata/releases/tag/v0.27.0) - 2026-09-25


### Breaking

- `FetchedAsset.open()` no longer takes options. Open a file that needs them with the method for its format: `open_csv(dtype=, parse_dates=, usecols=, nrows=, units_row=)`, `open_nexrad(sweep=)`, `open_grib2(select=, strict=)`, or `open_netcdf()`, each typed with the pandas or xarray object it returns. `open(reader="csv")` and `open(reader="erddap-csv")` become `open_csv(units_row=False)` and `open_csv(units_row=True)`, and the other `reader` values become the method of the same format. `usdata.readers.open_asset` likewise takes only the fetched asset, beside new `open_csv`, `open_nexrad`, `open_grib2`, and `open_netcdf` functions.

### Added

- Every dataset has its own page on usdata.dev, with a preview, the facts at a glance, a quick start taken from a query that ran, its walkthrough, and the studies that use it. The dataset list is now a grid of cards grouped by topic, and question-driven examples are now Studies at usdata.dev/studies; old example links redirect.

### Changed

- The website and docs share one set of colours, fonts, and header styling, and every website page loads the same fonts.

### Fixed

- Links to former example pages now redirect to the matching dataset or study page instead of the studies index.
- The GRIB2 reader now reverses every second row of a grid whose adjacent rows scan in opposite directions, as the National Blend of Models CONUS grid does. Before, half the rows of every `noaa:nbm` field came back mirrored east to west, so values sat beside the wrong coordinates.
- The SPC tornado, hail, and wind reference now says that property and crop loss are in whole dollars from 2016, not millions.
- `pull` with `force` no longer overwrites cached files the existing lockfile pins when it fails partway: while a lockfile exists, its downloads are staged and move into the cache only after the new lockfile is saved.

### Documentation

- 1.0 is now a judgment of maturity (breadth across agencies, every dataset verified, a settled contract) rather than a count of releases without contract changes. The roadmap turns to building out coverage, with the Census Data API, NASA through earthaccess, and more USGS water data as the next candidates.
- Each dataset now has one page in the docs: its guide, which ends with the dataset's parameters, variables, and catalog facts. The separate generated reference pages redirect to it, and the docs' dataset index points to the website's dataset grid for browsing.
- Every dataset page on usdata.dev now has its walkthrough notebook and a preview from real data. The Level III guide no longer calls the late start of mesocyclone and storm-track files a feed gap: on the documented day it matches the radar leaving clear-air mode.
- The AQS daily summaries page has a walkthrough notebook: a year of PM2.5 at Queens College in 2023, one row per monitor-day chosen from the several AQS writes, with the June wildfire smoke standing out.
- The Coastal current speed and direction page has a walkthrough notebook: one day of flood and ebb at the mouth of Chesapeake Bay, drawn as an along-channel current with gaps kept.
- The Coastal tide predictions page has a walkthrough notebook: a month of predicted high and low waters at The Battery, showing the spring-neap cycle and the daily inequality.
- The Coastal water levels page has a walkthrough notebook: three days of six-minute water levels at The Battery, with the unequal daily tides and NOAA's quality flags read off one plot.
- The GFS model output page has a walkthrough notebook: one 1 degree global analysis, its message inventory, and a world map of surface CAPE on 6 May 2024.
- The GHCN-Daily page has a walkthrough notebook: a year of daily highs, lows, precipitation, and snowfall at Oklahoma City's airport.
- The GOES CONUS and mesoscale imagery page has a walkthrough notebook: one GOES-18 infrared scene, its quality flags, and its scan angles turned into latitude and longitude.
- The GOES lightning detections page has a walkthrough notebook: an hour of GOES-16 GLM files flattened into one flash table, mapped over the central United States, and counted minute by minute near an Oklahoma tornado report.
- The GOES mesoscale study follows the study template, with its fixed-region brightness-temperature summaries as the preview.
- The Global Summary of the Month page has a walkthrough notebook: five years of monthly precipitation and mean temperature at Oklahoma City's airport, month by month.
- The Global tropical cyclone best tracks page has a walkthrough notebook: the IBTrACS last-three-years file, opened with its units row and mapped to show every storm of category 4 or 5 since 2023.
- The HRRR model output page has a walkthrough notebook: one 20 UTC analysis over the contiguous United States, its message inventory, and a map of where surface CAPE and 0-3 km helicity overlapped on 6 May 2024.
- The Local Climatological Data page has a walkthrough notebook: three days of hourly, special, and daily summary reports at Oklahoma City's airport, including the 6 May 2024 evening storm.
- The MRMS gridded radar products page has a walkthrough notebook: eleven two-minute mid-level rotation grids cropped around an Oklahoma tornado report, their swaths mapped, and the thirty-minute accumulation explained.
- The NBM forecast guidance page has a walkthrough notebook: 2 m temperature from the first four hours of one run fetched as byte ranges, a CONUS map of the first hour, and Oklahoma City's evening on 6 May 2024.
- The NEXRAD derived radar products page has a walkthrough notebook: thirty minutes of KTLX echo-top, mesocyclone, and storm-track files, their headers read without a decoder, and a timeline of what the archive holds.
- The NEXRAD radar scans page has a walkthrough notebook: one KTLX volume from a manifest, its lowest sweep's moments, and reflectivity beside correlation coefficient separating distant storms from clear-air echo.
- The NWS warnings and watches by county page has a walkthrough notebook: a year of Osage County, Oklahoma events, what was in effect at one moment, and how long each kind lasted.
- The RAP model output page has a walkthrough notebook: two fields of one 13 km analysis fetched as byte ranges, their provenance, and a map of CAPE and helicity over the southern Plains on 6 May 2024.
- The SPC tornado reports page has a walkthrough notebook: the 2024 tornado file, counted once per tornado and plotted by month and rating.
- The Sea-surface temperature page has a walkthrough notebook: one day of the blended analysis off northeast Florida, mapped to show the Gulf Stream's warm core against the shelf and open ocean.
- The Storm Events page has a walkthrough notebook: the 2024 details file, opened with UTC times, and Oklahoma's May 2024 hail, wind, and tornado reports counted by day.
- The Streamflow and Water Daily Values page has a walkthrough notebook: a water year of daily mean flow for the Arkansas River at Tulsa, with estimated days marked.
- The Tropical cyclone best tracks page has a walkthrough notebook: the whole Atlantic HURDAT2 file, opened into a track table and drawn as the 2024 season against 175 years of landfall points.
- The U.S. Climate Normals page has a walkthrough notebook: the 1991 to 2020 monthly normal high, low, and precipitation at Oklahoma City's airport.
- The annual station climate page has a walkthrough notebook: thirty years of precipitation and mean temperature at Oklahoma City, pulled, opened, plotted, pinned, and cited.
- The climate-anomalies study is one notebook in the study template: Oklahoma City's 2024 monthly temperature and precipitation against 1991–2020 normals, with its friction list.
- The disaster-declarations study is now a notebook: it joins FEMA's Oklahoma declarations to the 6 May 2024 tornado reports by county and finds 7 of 15 tornado counties designated.
- The earthquake events page has a walkthrough notebook: 25 years of magnitude 3 and larger earthquakes in Oklahoma, counted by year through the 2015 peak and after.
- The event-context study follows the study template: one notebook with its data, the radar and infrared preview, citations, and a friction list.
- The federal disaster declarations page has a walkthrough notebook: 25 years of Oklahoma declarations, counted once per disaster and plotted by year and type.
- The hourly-anomalies study is one notebook in the study template: 6 May 2024 routine reports at Oklahoma City against hourly normals, with its friction list.
- The severe-weather case study follows the study template: one notebook with its data, analysis, citations, and friction list, and no separate README.
- The storm-surge study is one notebook in the study template: Hurricane Helene's 3.15 m peak residual at Cedar Key, timed against landfall, with its friction list.
- The tornado classification study follows the study template, with a preview that places each of the twelve reports by its rotation and lightning features.
- The warning-lead-time study is now a notebook: it finds the Tornado Warning in effect when the 6 May 2024 Osage County EF4 began, issued 16 minutes earlier, and plots the county's alerts that evening.
- The weather-and-streamflow study is one notebook in the study template and now covers May 2024, plotting Oklahoma City rain beside Arkansas River flow at Tulsa.
- The website and docs name the agencies usdata covers today, dataset pages link examples by their titles, and docs headings match the website.
- The wildfire-smoke study is now a notebook: New York City's regulatory PM2.5 monitors through 1 to 15 June 2023, one row per monitor-day, with the smoke days far above the daily standard.

## [0.26.0](https://github.com/jakeryderv/usdata/releases/tag/v0.26.0) - 2026-09-24


### Added

- The adapter contract now covers sources that need a key. A registry entry can declare `credentials`: the environment variables it reads, named `USDATA_<SYSTEM>_<FIELD>`, and where to request a key. The core reads them and passes them to the adapter as a `Credentials` mapping that never prints its values. A missing one raises `MissingCredentials` (CLI exit 2) before any request, and `pull` checks every source first. A locked restore without a key takes pinned files from the cache, or from a configured mirror, listing them in `PullResult.unchecked`. Provenance records the variable names, never the values, and any `transformations` an adapter declares. `usdata info` and the dataset pages name the variables, and `usdata doctor` reports whether they are set. `usdata pull` says on stderr when it restored files from the mirror without asking their source. For adapter authors, `usdata.providers` adds `Credentials` (with `from_environment` and `redact`), `MissingCredentials`, and `adapter_class`, which returns an adapter's class without building it; `Provider` and `HttpProvider` take a keyword-only `credentials`, `HttpProvider.redacted_errors()` strips credential values from an escaping error, and `usdata.testing` adds `sentinel_credentials`, `check_credentials_required`, and `check_credentials_contained`, which search every asset, fetched byte, httpx log line, and error for sentinel values.
- `epa:aqs-daily` fetches daily summaries of regulatory air monitoring data from EPA's Air Quality System, the first source that needs a key: set `USDATA_AQS_EMAIL` and `USDATA_AQS_KEY` after registering for a free one. A query names one to five AQS parameter codes, such as `88101` for PM2.5, and exactly one place: `sites`, a state or county `location` (selected exactly), or a `bbox`. Each calendar year of the window becomes its own JSON file. The file is stored in a canonical form, without the echoed request (key included) and with its rows in a fixed order, so a checksum can pin it. Requests are spaced six seconds apart, as EPA asks. The pandas reader returns one row per monitor, local day, and pollutant standard. A pinned New York City example measures the June 2023 wildfire smoke against the daily PM2.5 standard.
- `noaa:hurdat2` accepts a `revision` date to select a revision other than the newest, and an unreadable HURDAT2 file now names itself and that parameter in its error. The newest Atlantic revision, 2026-09-12, has two upstream typos, so the examples read 2026-02-27.

### Documentation

- ADR 0038 records why a HURDAT2 query can name a revision while the reader stays strict, and ADR 0040 records how AQS daily summaries are selected: by pollutant codes and one place, a year per request.
- ADR 0039 records how sources that need credentials work, starting with EPA AQS. Keys come from environment variables and are checked before any request. They never appear in assets, lockfiles, provenance, cached bytes, or error messages. A pinned entry can restore from the mirror without a key. The roadmap selects this as the last workstream before 1.0.

### Development

- The weekly live checks install pandas for the five live tests whose reader step needs it (AQS, FEMA declarations, earthquakes, HURDAT2, and NWS VTEC), so those steps run instead of being skipped and a passing test is no longer reported as skipped.

## [0.25.0](https://github.com/jakeryderv/usdata/releases/tag/v0.25.0) - 2026-09-23


### Added

- Select GOES ABI mesoscale imagery with `product: ABI-L2-CMIPM` and explicit `sector: M1` or `M2`. A fifteen-minute central Plains example checks scan timing, footprint stability, and quality flags, and restores its committed scene lockfile into an empty cache. ([#267](https://github.com/jakeryderv/usdata/issues/267))

## [0.24.0](https://github.com/jakeryderv/usdata/releases/tag/v0.24.0) - 2026-09-22


### Added

- Fetch observed CO-OPS current speed and direction with `noaa:coops-currents`, selecting one station and explicit bin in UTC. A Cape Henry worked example reports gaps, preserves dated depth metadata, and verifies byte-for-byte restoration into an empty cache. ([#264](https://github.com/jakeryderv/usdata/issues/264))

## [0.23.0](https://github.com/jakeryderv/usdata/releases/tag/v0.23.0) - 2026-09-22


### Added

- Select 1991–2020 hourly climate normals with `period: hourly`, using whole-day calendar windows, and compare them with airport observations in a new worked example that verifies locked restoration.

### Documentation

- Include the manifest in the README quick start so the CLI and Python examples can be followed without an existing dataset.yaml file.

## [0.22.0](https://github.com/jakeryderv/usdata/releases/tag/v0.22.0) - 2026-09-18


### Breaking

- `Place` now requires `state`, the two-letter postal code of the state or of the state a county lies in. `build_query` and `find_place` set it, so queries built from a `location` are unaffected; code that constructs a `Place` by hand must pass it.

### Added

- `noaa:storm-events` takes a `table` parameter: `details` (the default), `fatalities` (one row per death), or `locations` (points per event, with rows from 1996). All three follow the same year selection and revision rule and join on `EVENT_ID`, and the reader keeps `FATALITY_ID` as text. ([#133](https://github.com/jakeryderv/usdata/issues/133))
- `noaa:spc-tornado-reports` takes a `table` parameter: `torn` (the default), `hail`, or `wind`. SPC publishes all three in one layout on one page; hail and wind start in 1955 where tornadoes start in 1950, and `mag` is the F or EF rating, the stone size in inches, or the wind speed in knots. The dataset keeps its id. ([#134](https://github.com/jakeryderv/usdata/issues/134))
- `noaa:nws-vtec-events` fetches the National Weather Service watches, warnings, and advisories issued for one county, as CSV from the Iowa Environmental Mesonet's archive, which is the maintained one since the NWS API keeps none. `--location "Osage County, OK"` selects that county exactly and a bare `bbox` is refused; `ugc` names a code explicitly, which is the only way to reach a forecast zone, and `phenomena` with `significance` narrows to one event type. A window selects events by when they were issued, not by when they were in effect, and the guide gives the recipe for the second question. ([#252](https://github.com/jakeryderv/usdata/issues/252))

### Documentation

- The catalog entry for the planned `census:acs-5year` no longer says the Census Data API is anonymous for light use: probed on 2026-09-18, every data request is refused without a key, and only the metadata is served keyless. The entry now declares `place_subset` rather than `spatial_subset`, since its geography is a FIPS code. The roadmap records that Census waits with the credentialed sources.
- The roadmap is current through this release: the Storm Events and SPC sibling tables and NWS watches and warnings by county are recorded as shipped, and no workstream is selected.

## [0.21.0](https://github.com/jakeryderv/usdata/releases/tag/v0.21.0) - 2026-09-18


### Added

- A query built from a `location` now keeps the place it resolved, as `Query.place` with its FIPS code, beside the unchanged `bbox`, so a source keyed by state and county can honour `--location`; `usdata.query.find_place` returns both. `Capabilities` gains `place_subset`, `Provider` gains `place_of`, which refuses a box that names no place in the same words for every such source, and the contract checks hold the two together. Existing adapters, manifests, and lockfiles are unaffected.
- `fema:disaster-declarations` fetches FEMA's Disaster Declarations Summaries from the OpenFEMA API as CSV: declarations whose incident period overlaps a window, for a named state or county, with incident and declaration type filters. It is the first source selected by place rather than by box, so `--location "Osage County, OK"` means that county exactly and a bare `bbox` is refused; a county also returns its state's statewide designations, and incidents with no end date are left out unless `include_open=true`. The reader keeps the FIPS columns as text. `usdata.providers.flag` validates a boolean parameter.

### Fixed

- Storm Events rows with a bare daylight label (`CDT`, `EDT`, `MDT`) now get `BEGIN_UTC` and `END_UTC`, read at the label's word as `CDT-5` already was. `AST`, `SST`, and `UNK` remain unconverted.

### Documentation

- ADR 0034 records the decision to keep the place a `location` resolved to on the query, so sources keyed by state and county FIPS can honour `--location`, and ADR 0035 records the OpenFEMA window and place rules with the evidence for each.

## [0.20.0](https://github.com/jakeryderv/usdata/releases/tag/v0.20.0) - 2026-09-18


### Added

- `Provider` gains an optional `fetch_partial(asset, dest, partial)`. The core now hands the byte ranges `prepare_fetch` settles straight to it, so fetching selected GRIB2 messages no longer depends on earlier calls to the same adapter instance, and `fetch` on a partial asset raises instead of risking a whole-object download. `fetch`, lockfiles, and fetched bytes are unchanged.
- `noaa:ibtracs` fetches one whole IBTrACS file, the global tropical cyclone best-track archive NCEI merges from every agency: a required subset names the complete record, the active storms, the last three seasons, everything since 1980, or one of seven basins, a format picks the CSV list or the NetCDF file, and the newest product version wins unless one is pinned. The CSV opens with the units-row reader, which reads the file's single-space missing cells as missing and keeps the North Atlantic basin code `NA` as text. A manifest example ranks the strongest recent storms with provisional tracks labelled. Directory listings now also yield the modified stamp, which IBTrACS assets carry as their end bound. A cached file whose listed size has changed upstream is fetched again rather than served stale.
- `noaa:rap` and `noaa:nbm` join HRRR and GFS on the shared model-run listing: the 13 km Rapid Refresh by run, forecast hour, and file family, and the National Blend of Models core files by run, forecast hour, and region, both whole or by named GRIB2 message through the index sidecar. Two manifest examples read them at the grid point nearest Oklahoma City. The index selector grammar gained the further text NBM adds for ensemble spread and probability thresholds, and RAP's two-field wind messages are fetched whole and opened field by field.

### Changed

- `pull --update` now stages refreshed files under `<cache root>/.staging/` and moves them into the cache only after the lockfile is saved. A pull that fails for any reason, including a network error partway through an update, leaves the lockfile as it was and every cached file either absent or matching it, so it can simply be run again.

### Fixed

- A `pull --update` run that ends in `UpstreamChanged` no longer replaces the cached files of the entries named for update. Unselected entries are now checked first, so a failed run leaves the cache matching the lockfile it did not rewrite.
- Partial GRIB2 fetches send `If-Match` as a quoted entity-tag, as HTTP specifies, rather than the bare value that only S3 tolerates. Lockfiles and provenance records are unchanged.
- Storm Events frames from files through 2006 now get `BEGIN_UTC` and `END_UTC`. Those files write the timezone label bare, and the five bare labels that name one offset everywhere (`CST`, `EST`, `MST`, `PST`, `HST`) are converted; `AST`, `SST`, and bare daylight labels are ambiguous or contradictory and stay `NaT`, listed with row counts under a new `labels_without_offset` key. Two-digit years 50 to 99 are read as 1950 to 1999, where they were previously a century late.
- `usdata inspect` and `FetchedAsset.inspect()` no longer count the units row of an ERDDAP or IBTrACS CSV as data, so `row_count` matches the rows `open()` returns, and the units are reported per column as `CsvSummary.units` and beside each column name in the CLI. A cached path learns which datasets lay a units row from the registry.

### Documentation

- The README states the current number of available and planned datasets, and `just check` now fails when that sentence falls behind the registry.
- The roadmap no longer lists finished work as selected: the reproducible-inputs workstream is recorded as complete, no workstream is selected, and the open Storm Events and SPC dataset issues join the candidates under Next.

## [0.19.0](https://github.com/jakeryderv/usdata/releases/tag/v0.19.0) - 2026-09-16


### Breaking

- A date alone as a query, CLI, or manifest `end` now means the last instant of that UTC day rather than its first, so `--start 2024-05-07 --end 2024-05-07` is the whole day: listing-based sources such as GOES, GLM, MRMS, HRRR, and GFS gain the rest of the day, CO-OPS reads it as 23:59, and calendar-date sources are unchanged. Window limits are measured between instants, so two bare dates a day apart now span two days. ([#220](https://github.com/jakeryderv/usdata/issues/220))

### Added

- The six archive-backed examples commit their lockfiles, the offline checks hold each to its manifest, the example pages offer the lockfile for download, and a weekly `restore` job pulls every one into an empty cache and reports the assets that drifted. ([#218](https://github.com/jakeryderv/usdata/issues/218))
- A content-addressed mirror: with `USDATA_MIRROR_URL` set, `usdata pull` restores a pinned asset whose source no longer serves its bytes from `<mirror>/sha256/<checksum>`, verifies it against the same pin, reports it as `mirrored`, and records the mirror object in the provenance sidecar; the lockfile is unchanged and the SDK never uploads. The weekly restore job fills `data.usdata.dev` with the objects the committed example lockfiles pin, and a manual workflow prunes what none pins. ([#219](https://github.com/jakeryderv/usdata/issues/219))
- `PullResult.one(source)` returns the single asset of a manifest source and says how many it has otherwise, and every result now orders a source's assets by start time and then id, whatever order the adapter listed them, so `fetch`, `pull`, `by_source`, and `pull --dry-run` never need a defensive sort. ([#221](https://github.com/jakeryderv/usdata/issues/221))
- `usgs:earthquakes` fetches events from the ANSS Comprehensive Catalog through the FDSN event service: a UTC window, an optional box, and magnitude and depth bounds resolve to CSV pages of at most 20,000 events, counted first and ordered by time, opened with the pandas reader. A manifest example pulls Oklahoma's events on the May 2024 tornado days.

### Changed

- The package is now classified as Alpha rather than Pre-Alpha: releases are tested and lockfiles are stable, while the Python API and CLI can still change between minor versions.

### Documentation

- Every page on usdata.dev and docs.usdata.dev now declares an Open Graph card, so a pasted link unfurls with an image; the README shows the same card as its link to the site.
- The README is the front door: badges, the pitch, the four commands, and where to look; setup, commands, CI, and releases moved to CONTRIBUTING.md. The package now lists Python 3.11 to 3.14, atmospheric science and hydrology topics, and links to the examples, changelog, and issue tracker on PyPI.
- The README shows a preview of usdata.dev, the same four steps in Python, a docs badge, and one sentence on when another library is the better tool; a CITATION.cff file lets GitHub offer a software citation beside the dataset citations usdata prints.
- Two decision records plan reproducible inputs in fact: the archive-backed examples will commit their lockfiles and restore them weekly, and a content-addressed mirror on R2 will serve pinned bytes after an agency stops serving them. The README compares usdata with pooch, intake, DVC, Herbie, and dataretrieval, the roadmap selects that workstream, and the 1.0 criteria now ask for a provider that requires credentials.

## [0.18.0](https://github.com/jakeryderv/usdata/releases/tag/v0.18.0) - 2026-09-16


### Added

- HRRR and GFS accept a `messages` parameter that fetches only the GRIB2 messages you name, as byte ranges of the object resolved through its wgrib2 `.idx` sidecar, instead of the whole file: two HRRR fields are 1.8 MB rather than 150 MB. Selectors are the index's own `SHORTNAME:level text` spelling, such as `CAPE:surface`. The result is those messages concatenated, which is a valid GRIB2 file the reader opens without `select`, and a manifest pins its byte ranges and the object's ETag so a restore reproduces it without re-reading the index. ([#174](https://github.com/jakeryderv/usdata/issues/174))
- `usdata pull dataset.yaml --dry-run` prices a manifest before fetching it: it lists every source through its adapter, printing one line per asset in the same columns as `fetch --dry-run`, a subtotal per source, and the manifest total on stderr, and downloads nothing. `--json` emits the plan, and `usdata.pull.plan()` returns it from Python. Both dry runs now report a missing size honestly: the known bytes read `at least M bytes` and the sources whose adapters report no size are named, instead of a bare `0 bytes`. ([#194](https://github.com/jakeryderv/usdata/issues/194))
- `Citation` is exported from the package root and renders itself through `as_text()` and `as_bibtex()`, so citations no longer have to be produced by shelling out to the console script, and `python -m usdata` now runs the CLI. ([#196](https://github.com/jakeryderv/usdata/issues/196))
- Storm Events CSVs opened with the pandas reader gain `BEGIN_UTC` and `END_UTC` columns, derived from the local timestamps and the `CZ_TIMEZONE` offset label and recorded under `frame.attrs["usdata"]["derived"]`. ([#199](https://github.com/jakeryderv/usdata/issues/199))
- A partial GRIB2 fetch now records the index selector each message was fetched for. Provenance gains `selectors`, aligned with `ranges`; every entry of `dataset.attrs["usdata"]["messages"]` gains `selector`; `usdata inspect` prints a `selector` column for a partial file; and `Grib2Summary.variable_for(selector)` returns the variable name the reader's naming rule gives that message, so `CAPE:surface` can be looked up as `cape_entireAtmosphere_0` instead of guessed. ([#210](https://github.com/jakeryderv/usdata/issues/210))

### Changed

- The GRIB2 message key `index`, on `GribMessage`, in `readers.inventory`, and in `dataset.attrs["usdata"]["messages"]`, is now `file_index`: the message's zero-based position in the local file. A new `object_index` carries the one-based number the source object's index sidecar gave the same message, set for a partial fetch and `None` for a whole file, and `usdata inspect` prints both columns when a file has both. The old key was renamed before any release used it, so there is no alias. ([#211](https://github.com/jakeryderv/usdata/issues/211))

### Fixed

- `usdata cite` fills the literal `[date]` placeholder an agency's requested citation leaves with the retrieval date the lockfile records, as one date or `between A and B` across a span, so a BibTeX entry no longer publishes the placeholder; citing a dataset id alone keeps it and notes that a lockfile is what fills it. ([#195](https://github.com/jakeryderv/usdata/issues/195))
- GRIB2 variable names now follow only from the messages a `select` matched: every variable is named `shortName_typeOfLevel_level` when the selection spans more than one type of level or more than one level within a type, and every variable keeps its bare `shortName` when they all share one, so the same select always returns the same names instead of suffixing only the short names that happened to repeat. `dataset.attrs["usdata"]["messages"]` maps each variable name to its message's index, `shortName`, `typeOfLevel`, `level`, and `step`. A select that spans levels whose short names did not repeat now returns a suffixed name where it previously returned a bare one. ([#197](https://github.com/jakeryderv/usdata/issues/197))
- Public functions that take a filesystem path now accept a `str` as well as a `Path`, coercing once on entry, so the path `usdata inspect` prints can be pasted straight into `inspect_path` instead of raising `AttributeError`. This covers `inspect_path`, `readers.inventory`, `fetch`, `fetch_asset`, `cite_lockfile`, `pull`, `resolve`, `restore`, `plan`, `verify`, `Manifest.load`, `Lockfile.load`, `Lockfile.save`, and `Registry.from_yaml`. ([#209](https://github.com/jakeryderv/usdata/issues/209))

### Documentation

- ADR 0028 records how a partial GRIB2 fetch identifies, pins, and reads a subset of one object, with the S3 range and index behaviour it was verified against; the HRRR and GFS guides, the manifest reference, and the provenance page document the `messages` parameter and the new sidecar fields.
- The severe-weather case study was re-run on the features that landed since it was written: its HRRR source names the CAPE and helicity messages, so the manifest pins 84.9 MB instead of 216.3 MB; the README prices it with one `usdata pull dataset.yaml --dry-run`; the notebook reads the Storm Events `BEGIN_UTC` and `END_UTC` columns instead of converting `CZ_TIMEZONE` by hand, and opens the partial GRIB2 file once, taking its two variable names from `attrs["usdata"]["messages"]`.

### Development

- `just run-notebooks` accepts `--cache DIR` (or `USDATA_NOTEBOOK_CACHE`) to reuse a download cache across runs, so refreshing a large example does not fetch it again; the default is still a fresh cache per run. ([#198](https://github.com/jakeryderv/usdata/issues/198))
- The post-release walkthrough waits up to ten minutes for the new version to appear on the PyPI index before reporting a broken release, after the v0.17.0 upload lagged its first run.

## [0.17.0](https://github.com/jakeryderv/usdata/releases/tag/v0.17.0) - 2026-09-16


### Breaking

- The adapter contract is public. `usdata.providers` now exports `Provider`, `HttpProvider` (the HTTP client lifecycle previously named `providers._http._HttpProvider`), `QueryError`, `NotImplementedProvider`, `load_adapter`, and the parameter coercions, and the new `usdata.testing` module runs the contract checks -- listing, refusals before transport, exact bytes to an exact path, client ownership, and the entry's declared capabilities -- against any adapter, including one maintained outside this repository. `usdata.providers._http` is gone; import `HttpProvider` from `usdata.providers`. ([#171](https://github.com/jakeryderv/usdata/issues/171))


### Added

- Registry entries now carry spatial and temporal resolution, update frequency, latency, citation, terms of use, the variables a dataset delivers with their units, and the longest query window its adapter enforces. `usdata info` prints each of them when the entry states it, and the generated catalog pages gained a variables table and the same lines under their catalog reference. ([#161](https://github.com/jakeryderv/usdata/issues/161))
- `usdata datasets` lists the curated registry as a table of id, status, domain, formats, reader, and summary, filtered by `--provider`, `--domain`, `--format`, `--reader`, `--capability`, and `--status`; `usdata search` takes the same filters, both accept `--json` for a machine-readable array, and the SDK gains `usdata.datasets()` and the matching keyword arguments on `Registry.list` and `Registry.search`. ([#163](https://github.com/jakeryderv/usdata/issues/163))
- `usdata doctor` reports the interpreter, reader extras and the ecCodes library, the cache directory and its free space, the cache environment variables, and, with `--network`, whether the upstream hosts answer; it exits 1 when a check fails. ([#164](https://github.com/jakeryderv/usdata/issues/164))
- `usdata cache` reports the cache directory, lists cached files with their size and retrieval time, totals the space they use, and prunes them by age or dataset. Prune removes each file with its provenance sidecar and keeps whatever a lockfile in the current directory pins unless `--include-pinned` is given. ([#165](https://github.com/jakeryderv/usdata/issues/165))
- `usdata inspect <cache path | dataset id and asset id>` and `FetchedAsset.inspect()` summarize what a fetched file holds: provenance and size for any file, CSV columns and a capped row count with no extra installed, NetCDF4 variables with dims and units, and GRIB2 messages as a table of `shortName`, `typeOfLevel`, `level`, and step. A missing extra is reported as a note instead of an error, `--json` emits the summary, and the new `usdata.readers.inventory(path)` gives the GRIB2 message list that the reader's "pass select" error has been the only source of until now. ([#166](https://github.com/jakeryderv/usdata/issues/166))
- `open()` now reports GRIB2 `select` values that match no message: a `UserWarning` by default, naming the key, the unmatched values, and what was available for that key, or a `ValueError` with `strict=True`. ([#167](https://github.com/jakeryderv/usdata/issues/167))
- NetCDF4 and GRIB2 results now take `units` a file leaves missing or `unknown` and missing `long_name` values from the registry entry's variable table, never overwriting what the file provides; every fill is listed under `attrs["usdata"]["registry_attrs"]`. MRMS fields, which decode without the product's level suffix, gain the units the files omit. ([#168](https://github.com/jakeryderv/usdata/issues/168))
- Manifest sources take an optional `name`, and a pull result groups what it fetched under `by_source`, keyed by that name or by the source's one-based position; `fetched` stays in manifest order, then adapter listing order. ([#169](https://github.com/jakeryderv/usdata/issues/169))
- `usdata cite` prints how to cite a dataset, or the datasets a manifest's lockfile pins, as plain text, BibTeX, or JSON. Pinned citations carry the retrieval dates, checksummed asset count, total size, and the usdata version that pinned them; `cite_dataset` and `cite_lockfile` are available from the package root. ([#170](https://github.com/jakeryderv/usdata/issues/170))
- Registry entries can name the product family or service behind them, declared in a new `systems:` table; the generated provider catalog pages and the website catalog group datasets by system. ([#172](https://github.com/jakeryderv/usdata/issues/172))

### Changed

- `usdata info` now prints what a dataset delivers and takes: its file formats, the optional extra that opens them (or `none` for formats with no bundled reader), the selection rule, the required inputs, and the worked examples that use it. ([#160](https://github.com/jakeryderv/usdata/issues/160))

### Fixed

- The GLM provider notes and the radar and satellite guide now show a flash-table snippet that keeps the position and time coordinates, and `usdata info` links the GLM, MRMS, and HRRR examples to their executed notebooks. ([#156](https://github.com/jakeryderv/usdata/issues/156))
- `usdata fetch --dry-run` now prints each asset's size and a total, and `fetch --json` emits the asset or fetched records as JSON. ([#157](https://github.com/jakeryderv/usdata/issues/157))
- Corrected the capabilities four registry entries declared: `noaa:mrms` and `noaa:nexrad-level3` no longer advertise variable subsetting their adapters reject, `noaa:storm-events` and `noaa:spc-tornado-reports` now declare the temporal subsetting they perform, and the MRMS entry says its extent is the grid's coverage rather than an offer to crop. ([#158](https://github.com/jakeryderv/usdata/issues/158))
- The GFS environment example no longer calls its 00 UTC 2024-05-06 analysis "twenty hours before" Storm Events report 1184052. The gap is 28 hours 39 minutes, and the README now says so and states that a pre-convective analysis that old is not concurrent with the event. ([#159](https://github.com/jakeryderv/usdata/issues/159))
- `usdata pull` takes `--quiet` to print only the summary line instead of one line per asset, and its `--no-progress` flag no longer advertises a `--no-no-progress` counterpart; NEXRAD's `nearest` now rejects non-ASCII digit strings like the other integer parameters do. ([#175](https://github.com/jakeryderv/usdata/issues/175))

### Documentation

- The severe-weather case study is the flagship example: one manifest with six named sources pins the 2024 Storm Events archive, the SPC 2024 tornado file, two KTLX Level II volumes, five MRMS mid-level rotation grids, twenty minutes of GOES-16 GLM detections, and the 04 UTC HRRR analysis, 216.3 MB in all. The notebook derives one tornado report's UTC time and position from the archive instead of hard-coding them, checks them against the SPC row, reports what each remote-sensing and model source held within 25 km of that point, and ends with `usdata cite` in text and BibTeX. The six smaller severe-weather examples are linked from it as deeper dives. ([#173](https://github.com/jakeryderv/usdata/issues/173))
- ADR 0027 records the provider contract: the names an adapter may depend on, what stays internal, and what changing either costs. The adding-a-dataset guide points at `HttpProvider` and shows how to run the shared checks from an outside test suite.
- Every implemented dataset's provider guide ends with a "Metadata sources" list naming the upstream page behind each catalog value, and says which fields the agency does not publish rather than filling them with an estimate.
- Index the GLM flashes, MRMS rotation, and HRRR environment notebooks on the examples page with their sharpened questions, and point every example at the setup section on the examples index instead of a documentation page that no longer exists.
- Record the plan for one registry schema verified against the adapters (ADR 0026) and restate the roadmap around it: discovery, diagnostics, reader, manifest, contract, and flagship-example candidates each have an issue.
- Retire the per-release first-use review and record usage in the worked examples instead: each example README asks the question it answers and lists what was awkward while answering it. Existing review files remain as historical records. See ADR 0025.
- The GLM lightning flashes example is now a runnable notebook. It counts GOES-16 GLM flashes minute by minute in a two-degree box around the 2024-05-06 Oklahoma City tornado report for the hour ending at the report, compares that series with a same-size control box and with the whole field of view, and plots both. Its manifest now pins that hour instead of an afternoon hour that contained no flashes near Oklahoma City.
- The HRRR environment example now ships an executed notebook: it reads surface CAPE and 0-3 km storm-relative helicity from one 150 MB analysis file, compares the grid point nearest an Oklahoma tornado report with the largest values within 100 km, maps both fields, and states what an analysis is and is not.
- Turn the MRMS rotation tracks example into a runnable notebook: it pins eleven two-minute mid-level rotation grids around the 2024-05-06 Oklahoma tornado report, reports the peak azimuthal shear and its position in each grid inside a stated search box and storm box, maps the positions those peaks trace against the reported path start, and states what a thirty-minute accumulated shear maximum does and does not say about a tornado.

### Development

- An adapter contract test probes every available dataset with a bbox, a variable, and a window before any transport, so a capability the registry declares but the adapter refuses now fails the offline suite; the declared `limits.max_window` checks moved beside it. ([#162](https://github.com/jakeryderv/usdata/issues/162))
- The registry has one schema. The top-level `catalog` block is gone and its keys are typed, validated fields on `Dataset`: adapter authors declare `summary`, `formats`, `selection`, `inputs`, `reader` (the extra that opens the files, renamed from `reader_extra`, or null), `guide`, and `examples` on the dataset entry itself, and the documentation and website generators read the model. Loading a registry that still has a `catalog` key now fails with a message saying where the fields moved.
- Walk the published package through the getting-started guide after each release: the publish workflow installs the new version from PyPI and runs the guide's own commands, extracted from the guide itself, against live services.
- `just run-notebooks --notebook` accepts an example slug as well as a repository-relative path and names exactly what was typed when it matches nothing, and `npm run check` in `web/` builds `dist/` first so it passes on a clean checkout.

## [0.16.0](https://github.com/jakeryderv/usdata/releases/tag/v0.16.0) - 2026-09-15


### Breaking

- The `usdata.fetch` module is now private; import `fetch`, `fetch_asset`, `FetchedAsset`, and `ChecksumMismatch` from the `usdata` package root instead, where `usdata.fetch` is unambiguously the function.

### Removed

- Removed the `opendap` protocol value, which no transport or registry entry ever used.
- Removed the `thredds` protocol value, which no transport implemented.

### Added

- `fetch`, `fetch_asset`, and `FetchedAsset` are now importable directly from `usdata`, so a script needs one import line instead of two.

### Changed

- A cache hit whose provenance sidecar checks out and whose file has not been touched since is reused without re-hashing it, so repeated fetches of large GRIB2 or NEXRAD files return immediately; restore and `usdata verify` still re-hash every file.
- Provider parameters are now validated against each adapter's declared model, and `usdata pull` rejects a manifest source with bad parameters before fetching any source.

### Fixed

- A NEXRAD query that gives `nearest` an explicit null now reads it as not given, the same as leaving the key out, instead of failing.

### Documentation

- Add a Concepts section (how it works, manifests and lockfiles, readers, time and place, provenance and drift), five task guides (find a dataset, pin inputs, radar and satellite, model output, severe weather labels), and trim the reference pages to options and tables, with the recurring warnings about UTC windows, upstream revisions, large grids, and planned datasets defined once and included where they apply.
- Add five planned registry entries with verified endpoints for severe-weather research: RAP model output, IGRA radiosondes, the NWS watch and warning archive, NCEI billion-dollar disasters, and FEMA disaster declarations. Group the geospatial sources behind their shared reader decision on the roadmap.
- Give each website one audience: the documentation site now holds only user pages plus a new Install page with extras and platform notes, while contributor and project-record pages are read on GitHub from the README, which absorbs the former docs project page.
- Lay the documentation site out like uv's: sections and pages in a collapsible left sidebar with breadcrumbs and instant navigation, the logo linking back to the homepage, and Website, Datasets, and Examples in the header instead of the navigation.
- Record the v0.15.0 first-use review: the published walkthrough, one installed-package fetch from each of the six new datasets, the GRIB2 reader on MRMS and GFS grids, network-blocked validation for every new adapter, all twelve new live tests, and the tornado classification notebook passed.
- Restyle both websites and the documentation theme on a near-black, graphite, and cobalt palette with a matching light scheme and logo, and name the KTLX volume that the radar alignment guard rejects.
- Rewrite the two landing pages: the homepage now shows one complete result inline, Hurricane Helene's surge at Cedar Key with its pinned inputs, and the documentation front page opens with the four commands and their real output, with the walkthrough moved to its own Getting started page.

### Development

- Adapters declare their `query.params` as a pydantic model, so validation, `usdata info` help, and the generated catalog come from one declaration; see the shared coercions in `usdata.providers.params`.

## [0.15.0](https://github.com/jakeryderv/usdata/releases/tag/v0.15.0) - 2026-09-14


### Added

- Add `noaa:gfs`, Global Forecast System model output: whole global GRIB2 files selected by run initialization window, cycle hour, forecast hours, and 0.25, 0.5, or 1 degree grid resolution, with fields chosen after download by the GRIB2 reader.
- Add `noaa:goes-glm`, GOES Geostationary Lightning Mapper flash, group, and event detections: whole 20-second NetCDF files from GOES-16 through 19 selected by satellite and a file-start window of at most one day, opened with the NetCDF reader, plus a manifest example counting flashes near Oklahoma City around a reported tornado.
- Add `noaa:hrrr`, High-Resolution Rapid Refresh model output: whole CONUS GRIB2 files selected by run initialization window, cycle hour, forecast hours, and surface, pressure-level, or native file variant, with fields chosen after download by the GRIB2 reader.
- Add `noaa:mrms`, Multi-Radar Multi-Sensor gridded CONUS products: whole two-minute gzipped GRIB2 grids of one product (rotation tracks, reflectivity, hail size, echo tops, precipitation rate, lightning probability) selected by product name and a file-stamp window of at most one day, plus a manifest example locating the strongest rotation near a reported tornado.
- Add `noaa:nexrad-level3`, NEXRAD Level III derived products (super-resolution reflectivity and velocity, dual-polarization moments, mesocyclone and storm-track detections, echo tops, and accumulations) from the public archive that begins 2020-03-30, selected by radar, product codes, and UTC time; files are fetched whole with provenance and lockfiles but have no reader in this release.
- Add `noaa:spc-tornado-reports`, the Storm Prediction Center tornado database: whole annual CSV files from 2008 onward and decade or half-decade files back to 1950, selected by date range, opened with the CSV reader, and documented against Storm Events, plus a manifest example counting one year's tornadoes by rating.
- Add `usdata[grib]`, a GRIB2 reader on the ecCodes bindings: `item.open()` returns a float32 xarray Dataset with computed coordinates for regular and projected grids, decompresses gzipped MRMS files in memory, and takes `select={...}` with ecCodes keys to choose messages from multi-message model output such as HRRR.

### Documentation

- Add a runnable tornado classification example that converts one Storm Events report to UTC, joins it to the nearest NEXRAD Level II volume, MRMS rotation track, and GLM flashes, and builds a small labeled table of rotation and lightning features for tornado, hail, and wind reports from the same evening. Move the MRMS rotation example to the twenty minutes around that tornado so the Oklahoma City box shows rotation.
- Record the GRIB2 reader decision: decode through the ecCodes Python bindings and build xarray datasets in usdata, after gribberish panicked on every 0.005-degree MRMS rotation grid and cfgrib spent 19 seconds computing coordinates for one file.
- Record the v0.14.0 first-use review: the published walkthrough, live checks for the two datasets the release added, and their query validation all passed. Remove the shipped LCD and CO-OPS tide candidates from the roadmap.
- Select the v0.15.0 tornado research workstream on the roadmap: GLM, SPC tornado reports, NEXRAD Level III, a GRIB2 reader, MRMS, HRRR, GFS, and a tornado classification example, with the five existing planned entries targeted at 0.15.0.

### Development

- The scheduled live suite now installs the netcdf extra for the GLM module and the grib extra for the MRMS, HRRR, and GFS modules, so their reader steps run instead of skipping.

## [0.14.0](https://github.com/jakeryderv/usdata/releases/tag/v0.14.0) - 2026-09-12


### Removed

- Remove the never-used `stub` dataset status. Registry entries are either `planned` (no adapter) or `available`; the dataset-authoring guide no longer describes an intermediate scaffold phase.

### Added

- Add `noaa:coops-tide-predictions`, astronomical tide predictions for one CO-OPS station on a six-minute, other minute, hourly, or high/low interval, sharing the station, datum, units, and validation rules of the observed water levels. A new storm-surge example subtracts the predictions from Cedar Key's observations during Hurricane Helene and places the peak against the HURDAT2 track.
- Add `noaa:lcd`, NCEI Local Climatological Data: hourly, special, synoptic, and daily-summary reports from airport and first-order stations as CSV, with the GHCN family's station discovery, unit selection, and variable subsetting, plus a manifest example comparing hourly readings with the daily summary.

### Documentation

- Record the v0.13.0 first-use review: the published walkthrough, live checks for every adapter the release changed, and the new query-validation behaviour all passed.

## [0.13.0](https://github.com/jakeryderv/usdata/releases/tag/v0.13.0) - 2026-09-12


### Added

- Add a searchable dataset browser at https://usdata.dev/datasets/ with agency and support filters, download selection rules, required inputs, example links, and copyable inspection commands. Extend the climate-anomalies notebook with a calculated summary of warmer months and annual precipitation relative to the station normals.

### Changed

- GOES queries span at most 7 days and NEXRAD queries at most 31 days, rejected before any request instead of listing hour by hour or day by day without bound. USGS daily-value listing now probes one row per page instead of downloading every JSON page, so dry runs and manifest resolution no longer transfer the data twice.
- Move all twelve worked examples to https://usdata.dev/examples/ with a question-based index, source-dataset links, saved results, expandable notebook code, and exact notebook/manifest downloads. Keep their maintained sources in the repository's examples directory and update dataset and documentation links to the single published copy.

### Fixed

- Adapters now share one query-validation step, so every dataset rejects free text, unsupported location, variable, or date filters, and conflicting selectors the same way instead of some ignoring them. This fixes a crash when CoastWatch received timezone-naive datetimes from the SDK, GHCN-Daily silently preferring `stations` over a `location`, and NEXRAD, USGS, and CoastWatch ignoring `text` or `variables`.

## [0.12.0](https://github.com/jakeryderv/usdata/releases/tag/v0.12.0) - 2026-09-12


### Added

- Added `noaa:hurdat2`, the NHC HURDAT2 best-track database, with a `basin` parameter, whole-file revision selection, and a local reader that parses the fixed-format text into one pandas row per track point.
- `usdata info <dataset>` now lists the provider-specific `--param` keys each adapter accepts, with a one-line description each, and the generated catalog pages show the same table.

### Changed

- The optional CSV reader now accepts pandas 2.2 or newer instead of requiring pandas 3.0, so `usdata[pandas]` installs alongside existing pandas 2 environments.

### Documentation

- Add a runnable climate-anomalies notebook that compares a year of NOAA GSOM monthly observations against the 1991-2020 station normals, and document which NCEI normals data types `units=metric` converts correctly, including the uncorrected `MLY-TAVG-NORMAL` and the mis-converted diurnal-range and standard-deviation codes.

### Development

- CI now runs the offline suite against the oldest pandas the project declares, so the supported floor is tested rather than assumed.

## [0.11.0](https://github.com/jakeryderv/usdata/releases/tag/v0.11.0) - 2026-09-12


### Added

- Add `noaa:climate-normals`: 1991-2020 monthly, daily, or annual/seasonal station normals from the NCEI Access Data Service, selected with a `period` parameter, optional month-day windows, and station discovery.
- Add the project homepage at https://usdata.dev and current documentation at https://docs.usdata.dev, with separate automatic static-site deployments from main.
- Restoring a lockfile now reports every asset whose upstream bytes changed in one run and leaves the lockfile untouched; `usdata pull --update <asset or dataset id>` (or `pull(update=[...])`) accepts the new bytes and rewrites only those pins.

### Fixed

- Reject reserved query names passed through fetch --param with a clear input error and the appropriate dedicated flag, instead of crashing or bypassing provider-parameter validation.
- Treat timezone-free timestamps in direct NEXRAD SDK queries as UTC, matching build_query and the CLI regardless of the machine timezone.

### Documentation

- Build documentation directly from `docs/` with standard MkDocs commands and
  serve both websites as static assets. Remove custom staging, link rewriting,
  Worker scripts, and obsolete URL redirects. Documentation now uses clean
  `/guides/`, `/reference/`, and `/examples/` paths; retired URLs return 404.
- Define Now, Next, and Later planning by scope and readiness, with bounded acceptance criteria and no deadlines or promised releases.
- Fix GSOY and CO-OPS Python manifest examples to use pathlib.Path, support running them from a published installation, and demonstrate fresh-cache restoration in the first-use walkthrough.
- Reserve R2 at https://data.usdata.dev for dataset storage, with a manual credential, public-access, and CORS check. SDK remote caching remains future work.

### Development

- Check both hosting toolchains for weekly npm dependency updates, and point package homepage and documentation metadata to the public sites. Consolidate pending website notes around the current deployment setup.

## [0.10.0](https://github.com/jakeryderv/usdata/releases/tag/v0.10.0) - 2026-09-09


### Added

- CO-OPS observed water levels for one station, explicit datum and UTC interval, with raw CSV quality fields, response validation, and a reproducible manifest example.
- `noaa:gsoy` annual station CSVs with complete UTC year selection, shared NCEI geographic discovery, reproducible restoration, and a small manifest example.

### Documentation

- Keep generated catalog files separate from handwritten documentation and combine dataset reference facts with usage guides in the local docs site.
- Make the dataset catalog easier to browse with Released, Source only, and Planned labels; explicit file formats and selection behavior; and automatic dataset navigation.
- Make the first-use walkthrough the site home, separate NOAA dataset guides from service research, and clarify source installation and reproducibility.

### Development

- Add optional fast commit hooks, workflow linting, and PR-title validation; pin GitHub Actions to reviewed commits while retaining Dependabot updates.
- Allow focused manual live-test and notebook CI runs while retaining complete weekly coverage; summarize test failures, skips, and timings in Actions.
- Assemble release notes with Towncrier fragments, validate notes in PRs, and preview upcoming changes in the documentation.
- Generate the radar-site CSV with LF line endings so fresh worktrees stay clean, and apply lint fixes before formatting.
- Prepare releases on a branch before editing files, validate draft release PRs before review/merge, check navigation and notebook release notices, and provide guarded cleanup for merged local branches and worktrees.

## [0.9.0] - 2026-09-09

### Documentation

- Default the documentation site to dark mode, with a light-mode toggle.

- Add a local documentation site with navigation, Mermaid diagrams, generated API/CLI references, saved notebook previews, and strict CI link checks. Separate generated dataset catalogs from provider access notes.

### Added

- Per-dataset live checks, independent example jobs, retained test/coverage and
  failed-notebook diagnostics, and scheduled minimum-core-dependency validation.

- Shared adapter conformance scenarios for every available dataset, covering
  deterministic listing, fetch destinations, byte preservation, and client ownership.

- Documented L0–L4 test levels, responsibility-based suites, and `just test-live`
  selection; existing integration command and marker aliases remain supported.

- Pure `select_by_time` asset selection with explicit tolerance and nearest/prior
  direction, signed offsets, candidate counts, and an explicit no-match result.
- Explicit zero-based radar sweep selection with `FetchedAsset.open(sweep=...)`
  and an executed Storm Events / NEXRAD / GOES event-context notebook.

### Fixed

- Require Typer 0.18 or newer; the old declared minimum failed to construct the
  CLI with modern union annotations and lacked current Click compatibility.

- Reject truncated S3 listings with missing or cycling continuation tokens instead
  of returning incomplete assets or requesting pages indefinitely.

- Reject NEXRAD decoder tables that misalign moment and coordinate records,
  including equal-length sweeps following a missing interior end marker; valid
  explicitly selected sweeps remain readable without silently dropping others.
- Reject out-of-range or non-finite point coordinates and negative/non-finite
  radii before bounding-box clipping; complete the manifest provider options for
  GSOM, GOES ABI, and Storm Events.

## [0.8.0] - 2026-09-09

### Added

- Optional local NetCDF4 opening with eager xarray loading, CF decoding,
  closed file resources, source metadata, and an executed GOES infrared notebook.
- `noaa:goes-abi` CONUS Cloud and Moisture Imagery with explicit satellite/channel
  selection, precise scan times and sizes, and checksum-verified NetCDF downloads.
- Storm Events annual event-details gzip CSVs, selecting current creation-date
  revisions with exact source-byte provenance and locked restoration; local
  compressed CSV opening preserves event and geographic identifier strings.
- Executed Storm Events notebook with local Oklahoma/date filters, event-record
  and damage-rating plots, and source/reporting caveats.
- Optional NEXRAD Level II opening with xradar sweep DataTrees, native units and
  flag masking, source provenance, and an executed reflectivity notebook.

### Changed

- Replace example analysis scripts with executed Jupyter notebooks containing
  compact data previews, plots, and source provenance. Add an optional examples
  environment, offline notebook checks, and isolated live execution/refresh commands.
- Pin the development interpreter to Python 3.14.7 to avoid an upstream crash
  affecting NetCDF decoding in older Linux uv Python builds.

## [0.7.0] - 2026-09-08

### Added

- Opt-in GHCN station-search diagnostics with bounded response details, and
  independent live checks for geographic discovery and explicit-station downloads.
- `noaa:gsom` monthly station CSVs through NCEI, with geographic discovery,
  complete-month selection, reproducible restoration, and a pandas analysis example.
- Terminal progress for CLI fetch and pull, showing known asset sizes, HTTP download
  bytes and retry attempts, and validated cache hits. Disable with `--no-progress`;
  redirected output retains its existing format.

## [0.6.0] - 2026-09-08

### Added

- Optional `FetchedAsset.open()` CSV reading through `usdata[pandas]`, including
  ERDDAP units metadata, string identifiers/codes, explicit dtype/date/column/row
  options, and a fetch-to-analysis example. Opening leaves raw bytes and provenance intact.

### Changed

- Test core-only and pandas installations in CI and installed-wheel checks.
- Check versioned source-only documentation notices during validation so release
  PRs cannot carry known stale availability wording.
- Focus v0.6 on optional CSV readers and practical usage; NASA, model output,
  climate grids, and remote caching remain follow-up work.

## [0.5.0] - 2026-09-05

### Breaking

- Manifest pulls now fail when a required source resolves to no assets. Set
  `allow_empty: true` per source to permit an intentionally empty result.
- `verify` rejects a manifest edited since locking (exit 2), matching `pull`.
- NOAA adapters reject unknown provider parameters, empty explicit identifiers,
  invalid units, and conflicting or invalid radar selectors.

### Fixed

- Generated provider and roadmap docs distinguish unreleased implementations
  from support included in the declared package version.
- GET metadata and download requests retry transient failures up to three attempts,
  respecting bounded `Retry-After` delays and preserving existing files on failure.
- Release publishing promotes the distributions from successful CI for the exact
  release commit, with version checks, instead of rebuilding.

### Changed

- Narrow v0.5 to USGS, ERDDAP/CoastWatch, complete place lookup, and reliability;
  additional NOAA adapters and optional readers remain follow-up work.
- Enforce offline unit tests and smoke-test the installed wheel on Linux, macOS,
  and Windows. Add release-tool regression tests.
- Add a manifest reference and a small NOAA/USGS example with a live round-trip test.

### Added

- `noaa:coastwatch-sst`: bounded ERDDAP gridded CSV subsets by location, UTC
  time, and variable, with optional spatial stride and reproducible restoration.
- Census 2025 lookup for 56 states/DC/territories and 3,235 counties/equivalents,
  including county/state names and quoted FIPS. Add `--location` as an alias for
  `--state`. Generated bounds replace the six approximate seed boxes, so
  geographic queries may select different stations; existing lockfiles stay pinned.

- `usgs:water-daily`: the first non-NOAA adapter, using the modern USGS Water Data
  API for paginated CSV downloads by site or bbox, dates, parameter codes, and
  statistic. Preserves units and quality metadata; supports cached fetches,
  manifest pull, locked restoration, and verification without new dependencies.

## [0.4.0] - 2026-09-05

### Breaking

- Manifest and source fields reject unknown keys instead of silently ignoring them;
  provider-specific inputs remain supported under `params`.

### Fixed

- Verify cached bytes and source provenance before reuse or fresh lockfile creation.
- Reject unsafe cache paths, including symlinks escaping the cache root.
- Preserve existing files after failed downloads or checksum mismatches; replace downloads,
  provenance, and lockfiles atomically using unique temporary files.
- Reuse provider clients across downloads and close internally owned clients on success or failure.
- Report invalid dates, radar IDs, manifest YAML, and lockfiles with clear CLI input errors.
- Infer multiple domains correctly when constructing a custom registry without a domain catalog.
- Gate package publishing on successful CI for the exact main-branch release commit.

## [0.3.0] - 2026-09-05

### Added

- `usdata pull` fetches every source in a manifest and writes a lockfile pinning each asset's
  checksum and provenance; a later `pull` restores from the lockfile without re-resolving, and
  refuses (until `--force`) if the manifest changed. `usdata verify` reports missing or altered
  cached files. Python API: `usdata.pull`, `usdata.verify`.
- Datasets carry a `status` (available, stub, planned). `search` and `info` show it; fetching a
  planned dataset exits 3 with a clear message.
- Planned registry entries for USGS, NASA, EPA, FEMA, Census, USDA, and GOES so the roadmap is
  visible from `usdata search` and the docs.
- Provider metadata (name, homepage) in the registry; README gains a generated per-provider table.
- Datasets carry a `domain` (shared taxonomy across providers), `since` (version shipped) or
  `target` (planned phase or `later`). `search` and `info` show them; the roadmap lists
  datasets by target version, generated from the registry.

- 26 NOAA registry entries spanning 18 domains, each verified for anonymous access
  (except GHCN-Hourly, whose entry says its bulk path is unconfirmed), with target phases.
  The NOAA provider page gains a data-landscape table mapping domains to entries.

### Changed

- `usdata search` hides planned datasets unless `--planned` is given.

### Changed

- Dataset reference moved to `docs/providers/`: one page per provider with hand-written access notes and a generated dataset table, plus a generated index.

## [0.2.1] - 2026-09-05

### Added

- Type information is shipped (`py.typed`).
- Contributor docs: `CONTRIBUTING.md`, `SECURITY.md`, a guide to adding datasets, issue and PR templates.

## [0.2.0] - 2026-09-05

First usable release.

### Added

- Curated dataset registry with keyword search filtered by provider, bounding box, and time.
- `noaa:ghcn-daily` adapter: station observations via the NCEI search and data services.
- `noaa:nexrad-level2` adapter: Level II volume scans from the `unidata-nexrad-level2` bucket over anonymous S3.
- Local cache with sha256 verification and a provenance sidecar for every fetched file.
- CLI: `usdata search`, `info`, `fetch` (with `--dry-run`), and manifest validation in `pull`.

## [0.1.0] - 2026-09-05

- Placeholder release reserving the package name. No functionality.

[Unreleased]: https://github.com/jakeryderv/usdata/tree/main/changes
[0.9.0]: https://github.com/jakeryderv/usdata/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/jakeryderv/usdata/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/jakeryderv/usdata/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/jakeryderv/usdata/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/jakeryderv/usdata/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/jakeryderv/usdata/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jakeryderv/usdata/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/jakeryderv/usdata/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jakeryderv/usdata/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jakeryderv/usdata/releases/tag/v0.1.0
