# CO-OPS water-level CSV

`coops-water-levels.csv` preserves the three-row raw response observed on
2026-09-09 in the hosted preflight. It includes NOAA's original header spacing.

Request: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter` with
`station=8518750`, `product=water_level`, `begin_date=20240506 00:00`,
`end_date=20240506 00:12`, `datum=MLLW`, `units=metric`, `time_zone=gmt`,
`format=csv`, and `application=usdata`.

NOAA data is a U.S. Government work in the public domain. This is a fixed test
fixture, not a claim that future upstream revisions will return identical bytes.
