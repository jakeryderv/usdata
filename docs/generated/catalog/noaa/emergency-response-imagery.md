<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:emergency-response-imagery` · **Released** · Included since usdata 0.34. NGS Emergency Response Imagery.

### At a glance

- Files: GeoTIFF
- Selection: Whole GeoTIFFs of one event folder, optionally by subfolder and by the footprint that tile names give
- Required inputs: An event folder; optionally collection folders and a bbox
- Open locally: Local files; no bundled reader for this format
- On usdata.dev: [Post-event aerial imagery tiles](https://usdata.dev/datasets/noaa/emergency-response-imagery/), with a walkthrough

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `collection` | Folder(s) under the event, such as the flight 20200307a_RGB: one, a list, or comma-separated; default every folder. |
| `event` | Required event folder, exactly as the bucket names it, such as 2020_Nashville_Tornado. |
| `max_gb` | Refuse a selection larger than this many gigabytes (10^9 bytes); default 25. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `Red` | — | Red band, 8-bit |
| `Green` | — | Green band, 8-bit |
| `Blue` | — | Blue band, 8-bit |
| `Alpha` | — | Transparency band marking imaged pixels, in the collections that carry one |

### Catalog facts

- Availability: since 0.34
- Domain: Natural hazards
- Spatial resolution: Approximate ground sample distance stated per event, such as 35 cm (1.14 feet) for Katrina and Joplin, ~15 cm for Nashville, and 15 - 30 cm for Helene
- Temporal resolution: One or more flights per event, one folder per flight
- Updates: Manually when needed
- Terms of use: <https://www.noaa.gov/information-technology/open-data-dissemination>
- Citation: National Geodetic Survey, NOAA Emergency Response Imagery, accessed via usdata from https://registry.opendata.aws/noaa-eri
- Geographic bounds (WGS84): west -124.8°, south 17.6°, east -64.5°, north 48.5°
- Catalog date range: 2005-08-30 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://storms.ngs.noaa.gov/)
- License: US Government Work (public domain)
- Transport: `s3`
- Adapter: `usdata.providers.noaa.eri:EmergencyResponseImagery`
