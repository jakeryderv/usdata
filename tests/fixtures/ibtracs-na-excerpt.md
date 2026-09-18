# IBTrACS fixture attribution

`ibtracs-na-excerpt.csv` contains the header row, the units row, and thirteen
track-point rows copied from NCEI's public-domain IBTrACS v04r01 North Atlantic
CSV:

https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NA.list.v04r01.csv

Retrieved 2026-09-17 UTC, from the build stamped that day. The whole source
file is 57,169,545 bytes; SHA-256:
`cff31db40e816f949475639fc1359699ae597abac8c0b5e4972d7edffcb7418e`.
The extracted fixture is 8,995 bytes; SHA-256:
`01657856cb8223feeac7cd206ce3591ae215854945121b74b782f11f04369284`.

The rows preserve the source's 174 columns, its single-space missing cells, and
its line endings. They were chosen to cover what the reader has to get right:
five points of the unnamed 1876 storm `1876273N14301` cross from the `NA` basin
into `EP` inside the North Atlantic file, so the basin code `NA` must survive as
text rather than become missing; and eight points of Ida `2021239N17281` around
its Louisiana landfall carry the asynoptic `L` record at 16:55 UTC, interpolated
(`P`) and original (`O`) flags, a `LANDFALL` of 0, and Saffir-Simpson category 4.
Directory listings are synthetic in the tests, so they can cover version
selection and missing files without mirroring upstream errors.
