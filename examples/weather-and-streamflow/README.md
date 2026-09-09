# Weather and streamflow inputs

Open the [executed notebook](example.ipynb) to inspect a two-source manifest, fetch
NOAA weather and USGS streamflow, view their data and provenance, and verify and
restore the locked inputs. See [examples setup](../README.md) to run it.

The retained [manifest](dataset.yaml) requests two days of station weather near
Oklahoma City and streamflow at the Tulsa site. These are different locations;
the example does not infer a causal relationship between them. Manifest support
requires usdata v0.5 or newer; the notebook's pandas opening requires v0.6 or newer.

The restoration demonstration uses a disposable cache, leaving the earlier
downloads intact. Generated example lockfiles are ignored in this SDK checkout;
keep the manifest and lockfile together in your own analysis project and preserve
cached bytes when you need a durable archive. The [manifest reference](../../docs/reference/manifests.md)
describes empty sources, query semantics, `--force`, and failure codes.
