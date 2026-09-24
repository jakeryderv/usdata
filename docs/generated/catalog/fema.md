# FEMA datasets

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

[Provider access notes](../../providers/fema.md).

**Released** is included in usdata 0.26.0. **Source only** is implemented in this checkout and requires a source installation. **Planned** cannot fetch data yet.

## Implemented datasets

| Dataset | Availability | Files | What gets selected |
|---|---|---|---|
| <span id="femadisaster-declarations"></span>[Federal disaster declarations by county](fema/disaster-declarations.md) | Released | CSV | Declarations whose incident period overlaps an inclusive UTC window, for a named state or county; a county also returns its state's statewide designations |

## Planned datasets

These entries are not implemented; they cannot fetch data.

### fema:nfhl

**National Flood Hazard Layer** · Planned · target later

Effective flood zones, base flood elevations, and related features from FEMA's flood insurance rate maps, available as county or state extracts and through ArcGIS services.

[Upstream information](https://www.fema.gov/flood-maps/national-flood-hazard-layer)
Domain: Natural hazards.
