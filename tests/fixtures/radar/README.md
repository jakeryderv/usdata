# NEXRAD format fixtures

These files are copied unchanged from [ARM-DOE/Py-ART commit
5310bd21b7316e90d36828610f792c95054fd899](https://github.com/ARM-DOE/pyart/tree/5310bd21b7316e90d36828610f792c95054fd899/pyart/testing/data).
They contain NOAA observations, not synthesized moment values. The upstream
BSD-style redistribution license is retained in [PYART-LICENSE.txt](PYART-LICENSE.txt).

| File | Upstream preparation | SHA-256 |
|---|---|---|
| `example_nexrad_archive_msg1.bz2` | Bzip2-compressed `KLOT20030101_000921`, per upstream `make_small_nexrad_archive_msg1.sh`; seven legacy message-1 sweeps | `7d6dcaa737d564195b1ac16675fd28b93195766cea42b02baf427b83cee3d82f` |
| `example_nexrad_archive_msg31_compressed.ar2v` | First 254 records (120 rays) of `Level2_KATX_20130717_1950.ar2v`, per upstream `make_small_nexrad_archive_msg31_compressed.py`; retains internal archive compression | `5feb92f7275cb8617d31031e7c0b263058313e2069bf4b82905df2b1db2b1014` |

The second file is deliberately an incomplete sweep, useful for detecting silent
loss of rays: xradar pads 600 absent rays with NaN and warns about recovering the
azimuth grid. It is not a complete science volume. The legacy fixture lacks
modern location metadata; do not use it as a geolocation reference. A complete
modern volume is exercised separately in the live radar notebook.

Tests never fetch these files. To update, download the named files from a pinned
upstream revision and verify their SHA-256 and expected decoded observations;
do not regenerate dummy replacements or refresh them during unit tests.
