<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:nws-damage-surveys` · **Source only** · Install from [source](../install.md#source-installation) to use this dataset. NWS Damage Survey Points, Tornado Tracks, and Damage Areas.

### At a glance

- Files: GeoJSON
- Selection: One layer's features with storm time in an inclusive UTC window, optionally in a box; one page per object-id run
- Required inputs: Both timestamps and a layer; optionally a bbox, offices, EF ratings, undated features, or as_of
- Open locally: Local files; no bundled reader for this format
- On usdata.dev: [NWS damage survey points, tornado tracks, and damage areas](https://usdata.dev/datasets/noaa/nws-damage-surveys/), with a walkthrough

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `as_of` | Read the service as it stood at this UTC instant, no earlier than its archive's start on 2020-11-25 and not in the future, so pages cannot drift; the live service by default. |
| `efscale` | Rating(s) as the toolkit writes them: EF0 to EF5, EF3+, EFU, UNKNOWN, N/A, TSTM/Wind, or Tropical; case does not matter. |
| `include_undated` | Also return features with no storm time, which match every window; false by default. |
| `layer` | Required layer: points (rated damage points), lines (tornado tracks), or polygons (damage areas). |
| `office` | NWS office code(s) that surveyed the damage, such as TSA or OUN; points and lines only, and a track shared by offices matches each of them. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `objectid` | — | Feature id, unique within its layer; pages are cut by it |
| `globalid` | — | Feature GUID, unique across the service |
| `stormdate` | milliseconds since 1970-01-01 UTC | Storm time; null on a few features, and the 1970-01-01T00:00Z placeholder on eleven points |
| `starttime` | milliseconds since 1970-01-01 UTC | Lines: when the tornado began; the window's field on lines |
| `endtime` | milliseconds since 1970-01-01 UTC | Lines: when the tornado ended |
| `efscale` | — | Rating as text: EF0 to EF5, EF3+, EFU, UNKNOWN, N/A, TSTM/Wind, or Tropical |
| `efnum` | — | Lines: EF number, -99 when unknown |
| `office` | — | Points: surveying NWS office code |
| `wfo` | — | Lines: surveying NWS office code, or several joined by commas |
| `event_id` | — | An office's label for the event; often empty |
| `damage_txt` | — | Points: EF-scale damage indicator, such as One- or Two-Family Residences (FR12) |
| `dod_txt` | — | Points: degree of damage to that indicator, in words |
| `windspeed` | — | Points: estimated wind speed as text; the service states no unit |
| `length` | — | Lines and polygons: path length; the service states no unit |
| `width` | — | Lines and polygons: path width; the service states no unit |
| `injuries` | count | Injuries |
| `fatalities` | count | Lines and polygons: fatalities; points call it deaths |
| `image` | — | Points: file name of a photo taken there, often empty; the photos are noaa:nws-damage-photos |
| `comments` | — | Surveyor's notes |

### Catalog facts

- Availability: Source only · intended for 0.34
- Domain: Severe weather
- Spatial resolution: One feature per surveyed damage point, tornado track, or damage area
- Temporal resolution: Storm time to the minute, in UTC
- Updates: As offices finish surveys, with no schedule: "Once quality-controlled, the data becomes available externally via a public web portal, as well as public Geographic Information System (GIS) services"
- Terms of use: <https://www.weather.gov/disclaimer>
- Citation: NOAA National Weather Service, Damage Assessment Toolkit (DamageViewer feature service), accessed via usdata
- Catalog date range: 1855-05-22 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://apps.dat.noaa.gov/StormDamage/DamageViewer/)
- License: US Government Work (public domain)
- Transport: `http`
- Adapter: `usdata.providers.noaa.nws_damage:NwsDamageSurveys`
