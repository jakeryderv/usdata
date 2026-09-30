<!-- Generated from src/usdata/data/registry.yaml by `just docs`. Do not edit by hand. -->

## Reference

`noaa:nws-damage-photos` · **Released** · Included since usdata 0.34. NWS Damage Survey Photos.

### At a glance

- Files: JPEG, PNG
- Selection: Each JPEG or PNG attached to a damage point with storm time in an inclusive UTC window of at most 7 days
- Required inputs: Both timestamps; optionally a bbox, offices, EF ratings, undated points, or as_of
- Open locally: Local files; no bundled reader for this format
- On usdata.dev: [Photos from NWS damage surveys, one file per damage point attachment](https://usdata.dev/datasets/noaa/nws-damage-photos/), with a walkthrough

### Parameters

Pass these as `--param name=value` to the CLI, as `params:` entries in a manifest, or as keyword arguments to `build_query`.

| Parameter | Meaning |
|---|---|
| `as_of` | Read the service as it stood at this UTC instant, no earlier than its archive's start on 2020-11-25 and not in the future, so pages cannot drift; the live service by default. |
| `efscale` | Rating(s) as the toolkit writes them: EF0 to EF5, EF3+, EFU, UNKNOWN, N/A, TSTM/Wind, or Tropical; case does not matter. |
| `include_undated` | Also return features with no storm time, which match every window; false by default. |
| `office` | NWS office code(s) that surveyed the damage, such as TSA or OUN; points and lines only, and a track shared by offices matches each of them. |

### Variables

| Variable | Units | Meaning |
|---|---|---|
| `image` | — | The attached photograph, JPEG or PNG, as served |

### Catalog facts

- Availability: since 0.34
- Domain: Severe weather
- Spatial resolution: One photo or more per surveyed damage point
- Temporal resolution: The storm time of the point the photo is attached to, in UTC
- Updates: As offices finish surveys, with no schedule: "Once quality-controlled, the data becomes available externally via a public web portal, as well as public Geographic Information System (GIS) services"
- Longest query window: 7 days
- Terms of use: <https://www.weather.gov/disclaimer>
- Citation: NOAA National Weather Service, Damage Assessment Toolkit (DamageViewer feature service) damage point photographs, accessed via usdata
- Catalog date range: 1974-04-03 to open-ended
- Coverage varies by station, product, and date; the range above does not guarantee observations.
- [Upstream documentation](https://apps.dat.noaa.gov/StormDamage/DamageViewer/)
- License: Public domain as NWS information; third-party images are used under their providers' licenses
- Transport: `http`
- Adapter: `usdata.providers.noaa.nws_damage:NwsDamagePhotos`
