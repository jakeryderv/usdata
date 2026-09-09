# Storm Events fixture attribution

`storm-details-1950.csv` contains the original CSV header and the first three
records, extracted after gzip decompression from NCEI's public-domain file:

https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/StormEvents_details-ftp_v1.0_d1950_c20260323.csv.gz

Retrieved 2026-09-09 UTC. The whole source archive is 10,508 bytes; SHA-256:
`1e35567c59a1d71795a307409f0a104c0056a8337a071adf97ef0e0d84849c54`.
The extracted fixture is 1,347 bytes; SHA-256:
`935e7968213e51247094020925dbabbf3344253be4241fa239a06f8b9badb9ba`.

The excerpt preserves source fields, quoting, row order, and the terminating LF.
Unit tests gzip this tiny excerpt with a fixed mtime; those generated test bytes
are not presented as the original full archive. Listing fixtures are deliberately
synthetic to cover revisions, unsafe links, unsupported schemas, and missing years.
