# Severe weather labels

Two datasets supply severe weather reports that can label other data. They
overlap heavily and differ in shape, and both need care before they become a
training set.

```yaml
name: oklahoma-2024
sources:
  - dataset: noaa:storm-events
    start: 2024-01-01
    end: 2024-12-31
  - dataset: noaa:spc-tornado-reports
    start: 2024-01-01
    end: 2024-12-31
```

## Storm Events or SPC

**Storm Events** (`noaa:storm-events`) is NCEI's database of about fifty
event types, one gzipped CSV per year. Tornado, hail, and thunderstorm-wind
rows each carry a magnitude, timing, location, casualties, damage, and a
narrative. A tornado appears once per county it crossed, linked by
`EPISODE_ID`; `EVENT_ID` identifies the row.

**SPC tornado reports** (`noaa:spc-tornado-reports`) is the Storm Prediction
Center's tornado database: one row per tornado segment with a single
straight-line path, an F or EF rating, and casualties, from 1950. It has no
hail or wind rows and no narrative, but its columns are consistent across
seventy-five years.

For tornado-versus-not labels, Storm Events supplies all three classes and
SPC cross-checks the tornado rows.

## Local time

Storm Events rows are stamped in local time with a `CZ_TIMEZONE` column such
as `CST-6`. Convert before joining to radar, satellite, or model data, which
are all UTC. SPC rows carry a `tz` code where `3` means Central Standard
Time regardless of daylight saving. Never assume a timezone from the state.

## Several rows per storm

One storm can produce a tornado row, a hail row, and several wind rows minutes
apart, and one tornado can produce several county rows. Count events, not
rows, and decide whether your unit is the report, the episode, or the storm
before you aggregate.

## Absence is not evidence

A missing report does not establish that nothing happened. Reports depend on
population, spotters, and survey resources, and historical reporting practice
changed over the decades. Negative examples should come from hail and wind
rows, not from silence, and any climatology should state the reporting era it
covers.

The [tornado classification example](https://usdata.dev/examples/tornado-classification/)
builds a twelve-row labeled table this way and lists the caveats it could not
resolve; the [SPC tornadoes example](https://usdata.dev/examples/spc-tornadoes/)
counts one year by rating.
