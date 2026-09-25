# NBM index fixture attribution

`nbm-co-f001.grib2.idx` is the complete, unmodified wgrib2 index sidecar of the
National Blend of Models 2024-05-06 20Z CONUS core f001 file, public domain:

https://noaa-nbm-grib2-pds.s3.amazonaws.com/blend.20240506/20/core/blend.t20z.core.f001.co.grib2.idx

Retrieved 2026-09-25 UTC. 21,877 bytes and 300 lines; ETag
`209042124a0302a9ed6ee1026d1f69a2`, last modified 2024-05-06 20:39:05 GMT;
SHA-256: `9a7ae5167731464e5d8c93e28bc8cd2b57c083fc92feaa0ea1707f4eae4a0a2f`.

It holds every index dialect NBM publishes: plain fields, ensemble statistics
(`ens std dev`, `10% level`), probability thresholds whose further text holds
colons (`prob >0.254:prob fcst 255/255`), and levels wgrib2 cannot name
(`reserved`), which repeat one label across several messages.
