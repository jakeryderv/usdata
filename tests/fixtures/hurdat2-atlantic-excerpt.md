# HURDAT2 fixture attribution

`hurdat2-atlantic-excerpt.txt` contains four complete storm blocks copied from
the National Hurricane Center's public-domain Atlantic best-track file:

https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-02272026.txt

Retrieved 2026-09-12 UTC. The whole source file is 7,082,381 bytes; SHA-256:
`1b9b0c7beed5b4505838658b1d30e159fc84330c60891a58cfcf43ae55c37202`.
The extracted fixture is 3,554 bytes; SHA-256:
`ff39c8a087aeb026d736a7657fdcec53b26f3b02562fba689b4a19a9a5e0fca1`.

The excerpt preserves source spacing, field order, and the declared track-point
counts; unlike the whole source file, it ends with a terminating LF. The storms
were chosen to cover the format's variation: AL011851 and AL021851 have no wind radii
(`-999`) and a landfall record at a synoptic time, AL021971 ends with the `-99`
unassigned intensity of a 1967-era non-developing depression, and AL042021 has
best-tracked radii, a radius of maximum wind, and an asynoptic landfall.
Directory listings and malformed layouts are synthetic in the tests, so they can
cover revision selection, unsafe links, and truncated files without mirroring
upstream errors.
