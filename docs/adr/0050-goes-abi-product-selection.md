# 0050: GOES ABI products are named by directory, and a channel or sector only where the product has one

Status: accepted. Date: 2026-09-29.

## Context

`noaa:goes-abi` served single-channel Cloud and Moisture Imagery for CONUS
(`ABI-L2-CMIPC`) and mesoscale (`ABI-L2-CMIPM`), with `channel` always
required and `sector` required for mesoscale. A CNN over GOES imagery wants all
16 channels of a scene, which meant 16 fetches and a regrid, while NOAA
publishes the same scene as one 16-band file, `ABI-L2-MCMIP`. Studies of cloud
tops want NOAA's height, temperature, pressure, and phase retrievals rather than
deriving them from imagery.

These products share the buckets, the `PRODUCT/YYYY/DDD/HH/` layout, and the
filename grammar, so one adapter can list them all. They differ in two ways
that the parameters have to express. Only CMIP has a channel: an MCMIP file
holds all 16, and a cloud-top file holds none. And NOAA does not produce every
product for every sector. Listings of all four buckets on 2026-09-29, matching
NCEI's product table, found cloud-top temperature for full disk and mesoscale
only, and cloud-top pressure for CONUS and full disk only.

## Decision

The products stay in `noaa:goes-abi`, whose id is stable. `product` names one
bucket directory exactly, such as `ABI-L2-MCMIPF` or `ABI-L2-ACHTM`, from a
closed list of the 16 directories that exist; it defaults to `ABI-L2-CMIPC`, so
earlier queries and manifests keep their meaning. There is no separate family
and sector pair, and no alias or case folding: the value is the directory the
files come from, and the list refuses `ABI-L2-ACHTC` because NOAA makes none.

`channel` is required for the three CMIP products and refused for every other
product. `sector` (`M1` or `M2`) is required for the products ending in `M` and
refused for the rest. A refused selector is an error, not ignored: a channel on
an MCMIP query means the caller expected one band and would get sixteen. All of
these are checked by the parameter model before any request, with messages
naming the product.

Each product has its own first archived day, the earliest scene in any bucket:
2017-02-28 for CMIP and MCMIP, 2017-05-16 for CONUS and full-disk phase,
2019-12-02 for height and mesoscale phase, and 2019-12-05 for temperature and
pressure. A window ending before that day is refused, and an earlier start is
moved to it. This keeps the GOES-16 year-2000 placeholder scenes out as before.
Later satellites start later, and that is left to the listing, which returns
nothing, rather than encoded per satellite.

The seven-day window stays the same for every product. It bounds the hourly
listings a query makes, which do not depend on the product. Bytes do: a week of
full-disk MCMIP is about 307 GB, but a week of CONUS channel 2 was already
122 GB under the old rules, and a single product spans a 30-fold range of file
sizes by channel. `usdata fetch --dry-run` prices a query before it downloads.
One constant also keeps the registry's `limits.max_window` true for every query.

The 2 km cloud-top height directories (`ACHA2KMC/F/M`) are left out. Their
files have the same shape, but GOES-17 has none and the rest begin in 2023, so
the product would exist only for some satellites and years.

## Alternatives

- **A new dataset per product family.** The capabilities, transport, selection
  rule, and reader are the same, so separate entries would repeat one adapter
  with a different default, and split the GOES guide.
- **`family` and `sector` parameters** (`family=ACHT`, `sector=C`). The pair
  admits combinations that do not exist, which then need their own table, and
  the directory name is what the NCEI page, the bucket, and the filename use.
- **A shorter window for full disk.** The registry states one window, and the
  byte range within a product already exceeds the range between products.
- **Ignore a channel on MCMIP.** Silent fallbacks after a mistaken selector are
  what the adding-a-dataset guide asks adapters to refuse.

## Consequences

One `noaa:goes-abi` query can fetch a 16-band scene or a cloud-top retrieval, and
existing manifests restore unchanged. The product list is a fact about the
archive, so a new NOAA directory, or a sector NOAA starts producing, needs an
adapter change and a probe. Full-disk queries can be very large, and only the
dry run warns about it.
