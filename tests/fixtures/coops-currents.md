# CO-OPS currents fixture

`coops-currents.csv` is the unchanged anonymous NOAA response for Cape Henry
LB 2CH (`cb0102`), bin 4, 6 May 2025 00:02–00:14 UTC, retrieved on
2026-09-22. NOAA data is a U.S. Government work (public domain); acknowledge
NOAA National Ocean Service. The three observations carry speed in cm/s,
direction in degrees, and bin number. Header spaces are retained.

```sh
curl --get 'https://api.tidesandcurrents.noaa.gov/api/prod/datagetter' \
  --data-urlencode 'station=cb0102' --data-urlencode 'product=currents' \
  --data-urlencode 'begin_date=20250506 00:02' --data-urlencode 'end_date=20250506 00:14' \
  --data-urlencode 'bin=4' --data-urlencode 'units=metric' \
  --data-urlencode 'time_zone=gmt' --data-urlencode 'format=csv' \
  --data-urlencode 'application=usdata'
```

SHA256: `b6ed194f63663fd5883968201ab41cf33e3768efb10bd6a27a398b2bcf3e342f`.
See [API fields](https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html)
and [terms](https://tidesandcurrents.noaa.gov/disclaimers.html).
