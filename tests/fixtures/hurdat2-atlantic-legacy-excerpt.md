# HURDAT2 archived-revision fixture attribution

`hurdat2-atlantic-legacy-excerpt.txt` contains one complete storm block copied
from an archived revision of the National Hurricane Center's public-domain
Atlantic best-track file:

https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2020-020922.txt

Retrieved 2026-09-12 UTC. The whole source file is 6,473,552 bytes; SHA-256:
`88f93ef2d55ef5d9465ae06f8f7709a404ceae5db21a830e4fd25cd92b7534fd`.
The extracted fixture is 4,152 bytes; SHA-256:
`cb63e8610755bfba327dc37bdcf757f02f1689d718312156c4773e126a5c4df7`.

The excerpt preserves source spacing, field order, and the declared track-point
count. It exists so the suite exercises a real archived revision rather than only
the current one, which is what a restored lockfile actually fetches. `AL211969`
covers two things the current files do not:

- the pre-2021 layout, whose data lines carry 20 values and a terminating comma
  with no radius of maximum wind;
- four track points east of Greenwich written in the unwrapped 0-360 west
  convention (`358.0W`, `352.5W`, `347.0W`, `342.0W`), continuing a track whose
  previous point is `3.3W`. Of the 41 files the directory listed on 2026-09-12,
  10 contain such longitudes and the current Atlantic and Pacific files do not.
  The NHC rewrote these same four points as `2.0E`, `7.5E`, `13.0E`, and `18.0E`
  in `hurdat2-1851-2024-040425.txt`, which is what the reader's normalization
  produces from the unwrapped form.
