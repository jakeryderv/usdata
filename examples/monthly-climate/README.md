# Monthly airport climate

Open the [executed notebook](example.ipynb) to inspect May 2024 precipitation and
mean temperature at Will Rogers World Airport, plot both measurements, and verify
the manifest's locked inputs. See [examples setup](../README.md) to run it.

Requires usdata v0.7 or newer. The retained [manifest](dataset.yaml) requests
`units: metric`: PRCP is millimeters and TAVG is degrees Celsius. NCEI's CSV has
no units row; the notebook labels units from that documented request, while the
reader preserves identifiers and source provenance.

Every UTC calendar month touched by the query is selected in full. May 6–7 selects
May; May 31–June 1 selects both months. The notebook records retrieval times and
checksums and shows lockfile/cache reuse. See [NOAA access notes](../../docs/providers/noaa.md#global-summary-of-the-month)
for geographic queries and the bounded probes used to validate the adapter.
