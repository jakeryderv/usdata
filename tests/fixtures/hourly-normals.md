# Hourly normals fixture

`hourly-normals.csv` is the unchanged NCEI Access Data Service response for
Will Rogers World Airport (`USW00013967`), May 6, `HLY-TEMP-NORMAL`, metric
units, retrieved on 2026-09-21. NOAA data is a U.S. Government work (public domain).

```sh
curl --get 'https://www.ncei.noaa.gov/access/services/data/v1' \
  --data-urlencode 'dataset=normals-hourly-1991-2020' \
  --data-urlencode 'stations=USW00013967' \
  --data-urlencode 'startDate=2020-05-06' --data-urlencode 'endDate=2020-05-06' \
  --data-urlencode 'dataTypes=HLY-TEMP-NORMAL' --data-urlencode 'units=metric' \
  --data-urlencode 'format=csv' --data-urlencode 'includeStationLocation=1'
```

The 24 rows carry month-day-hour labels in local standard time and temperatures
in degrees Celsius. The fixture checks that local CSV opening preserves those
labels and that locked restoration preserves the source bytes.
