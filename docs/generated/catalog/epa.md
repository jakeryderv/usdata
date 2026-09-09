# EPA dataset catalog

[Provider access notes](../../providers/epa.md). Status describes this source checkout; see version labels for release support.

Generated from `src/usdata/data/registry.yaml` by `just docs`. Do not edit by hand.

| Dataset | Domain | Status | Version | Description | Protocol |
|---|---|---|---|---|---|
| [`epa:aqs-daily`](#epaaqs-daily) | Air quality | planned | target later | Daily pollutant summaries (ozone, PM2.5, NO2, and others) from regulatory monitors via the AQS Data API. | http |

### epa:aqs-daily

**Air Quality System Daily Summaries** · planned · target later

Daily pollutant summaries (ozone, PM2.5, NO2, and others) from regulatory monitors via the AQS Data API. Requires a free API key issued by email.

- Domain: Air quality
- Server-side subsetting: spatial, temporal, variable
- Homepage: https://aqs.epa.gov/aqsweb/documents/data_api.html
- License: US Government Work (public domain)
- Extent: not stated
- Keywords: air quality, pollution, ozone, pm2.5, monitors, aqs
- Adapter: none yet
