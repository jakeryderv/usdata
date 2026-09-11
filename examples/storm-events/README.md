# Oklahoma Storm Events reports

Available since v0.8. Open the [executed notebook](example.ipynb) to
fetch the annual 2024 details archive, open its gzip CSV locally, and describe
Oklahoma tornado, hail, and thunderstorm-wind reports beginning in May. See
[examples setup](../README.md) to run it.

The [manifest](dataset.yaml) selects one complete annual file (~13 MB compressed),
not a server-side May or Oklahoma subset. Unsupported geographic, variable, and
provider parameters raise errors. Filtering uses reported local calendar dates;
source `CZ_TIMEZONE` labels remain visible, with no assumed UTC conversion.

The plots count event records and reported tornado ratings, not distinct storms
or direct wind measurements. The notebook explains reporting, segmentation,
and historical-coverage limits, preserves unknown rating categories, and records
the exact source URL/retrieval time/checksum. Saved outputs are one revision's
snapshot; current values can differ. The raw gzip file and its provenance stay
unchanged after opening, plotting, and cache verification.

See [NOAA access notes](../../docs/content/providers/noaa-storm-events.md)
for revision selection, missing-year errors, and preservation limits.
