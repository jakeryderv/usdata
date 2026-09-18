# Which Oklahoma counties hit by a tornado on 6 May 2024 were under a federal disaster declaration?

Unreleased; available from source for v0.21. The [manifest](dataset.yaml) pins
two inputs: FEMA's major disaster declarations in force in Oklahoma on 6 May
2024, one row per designated county, and the 2024 Storm Events archive, which
holds that evening's tornado reports. Joining them by county answers the
question, and shows why this source is selected by a named place rather than by
a rectangle.

In an activated Python 3.11+ virtual environment, install the package from
[source](https://docs.usdata.dev/install/#source-installation) and run from
`examples/disaster-declarations/`, using `uv run usdata` and `uv run python`:

```sh
usdata pull dataset.yaml
usdata verify dataset.yaml
```

```python
from pathlib import Path

from usdata import pull, verify

manifest = Path("dataset.yaml")
result = pull(manifest)
declared = result.one("declarations").open()
reports = result.one("reports").open()

evening = reports.BEGIN_UTC.between("2024-05-06T18:00Z", "2024-05-07T12:00Z")
tornadoes = reports[(reports.EVENT_TYPE == "Tornado") & (reports.STATE == "OKLAHOMA") & evening]
counties = tornadoes.groupby(["STATE_FIPS", "CZ_FIPS", "CZ_NAME"], as_index=False).agg(
    tornadoes=("EVENT_ID", "count"), strongest=("TOR_F_SCALE", "max")
)
# Storm Events writes county 1 where FEMA writes 001.
counties["county"] = counties.CZ_FIPS.str.zfill(3)
joined = counties.merge(
    declared[["fipsStateCode", "fipsCountyCode", "femaDeclarationString"]],
    left_on=["STATE_FIPS", "county"],
    right_on=["fipsStateCode", "fipsCountyCode"],
    how="left",
)
print(joined[["CZ_NAME", "tornadoes", "strongest", "femaDeclarationString"]])
assert verify(manifest) == []
```

On 2026-09-18 FEMA returned 25 designated counties, all under DR-4776-OK, and
Storm Events held 19 tornado segments across 15 Oklahoma counties that evening.
Seven of those fifteen were designated: Kay, Lincoln, Okfuskee, Okmulgee,
Osage, Ottawa, and Washington. Osage County, where the evening's one EF4 struck,
is among them. Oklahoma County, where the EF1 that the
[severe-weather case study](https://usdata.dev/examples/severe-weather-case-study/)
follows touched down, is not, and neither are Adair, Alfalfa, Blaine, Creek,
Garfield, Kingfisher, or Major.

That is a statement about designation, not about damage. DR-4776 covers
incidents from 25 April to 9 May, so a county can be designated for a storm on
another day, and a tornado that did little harm earns no declaration. The
declaration was made on 30 April, before this outbreak; the window selects by
the incident period, which is why asking about 6 May finds it.

The declaration rows have no coordinates. They carry `fipsStateCode` and
`fipsCountyCode`, kept as text so `019` stays `019`, which is what makes the
join possible. It is also why a location means something different here: for a
radar or a station dataset `Osage County, OK` is a bounding box that takes in
parts of its neighbours, and for this one it is FIPS `40113` exactly.

FEMA revises rows as incidents close and programs are added, so a later pull
can report drift; `pull --update` accepts the revised rows. Keep the manifest,
lockfile, and cached bytes together. Query details are in the
[disaster declarations guide](https://docs.usdata.dev/providers/fema-disaster-declarations/).

## What was awkward

- The join silently matched only the counties whose code has three digits.
  Both sources keep their county code as text, which is right, but Storm Events
  writes `1` and `19` where FEMA writes `001` and `019`. Nothing fails; small
  counties simply drop out of an inner join. `str.zfill(3)` fixes it, and the
  reader does not do it for you, because it leaves a source's values as
  delivered.
- The first version of the FEMA query matched nothing at all, also silently. A
  full timestamp in an OpenFEMA filter is compared against its own
  percent-encoded text, so `ge '2024-05-01T00:00:00.000Z'` is never true and the
  service answers with a well-formed empty result. Only the filter echoed back
  in the response metadata, still reading `T00%3A00%3A00`, gave it away.
- Treating a missing `incidentEndDate` as "still open" tripled the Oklahoma
  result with fire declarations from 2005 that nobody ever closed. They are
  excluded by default, so a disaster genuinely under way needs
  `include_open: true` and brings the stale rows with it. There is no good
  default here, only a documented one.
- The program columns arrive as `0` and `1`, and the dates as midnight UTC
  timestamps although they are calendar dates. Neither is converted.
