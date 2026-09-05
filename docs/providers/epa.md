# EPA

Provider id `epa`. Homepage: https://www.epa.gov/

## Access notes

No notes yet. Add how this agency publishes data, authentication requirements, quirks, and links to its own documentation as adapters get built.

## Datasets

<!-- datasets:start -->
Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Status | Description | Protocol | Server-side subsetting |
|---|---|---|---|---|
| [`epa:aqs-daily`](#epaaqs-daily) | planned | Daily pollutant summaries (ozone, PM2.5, NO2, and others) from regulatory monitors via the AQS Data API. | http | spatial, temporal, variable |

### epa:aqs-daily

**Air Quality System Daily Summaries** · planned

Daily pollutant summaries (ozone, PM2.5, NO2, and others) from regulatory monitors via the AQS Data API. Requires a free API key issued by email.

- Homepage: https://aqs.epa.gov/aqsweb/documents/data_api.html
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: air quality, pollution, ozone, pm2.5, monitors, aqs
- Adapter: none yet
<!-- datasets:end -->
