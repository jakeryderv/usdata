# 0033: Convert only the bare Storm Events timezone labels that name one offset

Status: accepted. Date: 2026-09-18.

## Context

The pandas reader derives `BEGIN_UTC` and `END_UTC` for a Storm Events frame by
shifting each local timestamp by the whole-hour offset its `CZ_TIMEZONE` label
ends with, so `CST-6` is UTC−6. A label with no trailing offset gave `NaT`.

Files through 2006 write every label bare. Sampling the archive showed the
derived columns were empty for all of them:

| File year | Rows | `BEGIN_UTC` derived |
| --- | --- | --- |
| 1950 | 223 | 0 |
| 1965 | 2,835 | 0 |
| 1999 | 46,383 | 0 |
| 2006 | 56,400 | 7,838 |
| 2007 | 59,011 | all |

The instant is the join key between a Storm Events row and radar, satellite,
or model output, so the reader produced nothing for the first fifty-seven years
of the record.

A second defect sat behind the first. Local timestamps carry two-digit years
(`28-APR-50`), parsed with `%y`, whose pivot reads `50` to `68` as 2050 to 2068.
It did no harm only because those rows were already `NaT`; converting the bare
labels would have dated the archive's first nineteen years a century late.

The bare labels, counted across fourteen sampled years from 1950 to 2006:

| Label | Rows | Where |
| --- | --- | --- |
| `CST` | 145,537 | |
| `EST` | 95,428 | |
| `MST` | 24,827 | |
| `PST` | 7,887 | Pacific states and waters, and 21 Arizona rows |
| `AST` | 2,861 | Alaska 1,600; Puerto Rico 1,131; Virgin Islands 71; marine zones 59 |
| `HST` | 1,725 | Hawaii and Hawaiian waters |
| `SST` | 208 | American Samoa 101; Guam 106 |
| `CDT`, `EDT`, `MDT` | 24 | |
| `UNK` | 2 | |

## Decision

A bare label is converted only when it names one offset wherever it appears in
the archive: `CST` −6, `EST` −5, `MST` −7, `PST` −8, `HST` −10. Those five
cover 98.9 percent of the bare-label rows sampled.

`AST` and `SST` are left unconverted because each names two. `AST` is Alaska
Standard Time on Alaska rows and Atlantic Standard Time on Puerto Rico and
Virgin Islands rows, five hours apart. `SST` is Samoa Standard Time on American
Samoa rows and appears on as many Guam rows, where the modern files say `GST10`:
converting those by the label would be wrong by twenty-one hours. Bare daylight
labels are left unconverted because the archive documents local standard time
and a bare label states no offset to settle the contradiction. A row the reader
cannot convert with confidence gets `NaT`, which is the project's rule
elsewhere: unsure means say so.

Every label that gave no offset is listed, with its row count, under
`labels_without_offset` beside the existing `unparsed` count, so a caller sees
what was left and how much rather than meeting unexplained gaps.

Two-digit years are given their century from the archive's first year before
parsing: `50` to `99` are 1950 to 1999 and `00` to `49` are 2000 to 2049. A
column the caller already parsed with `parse_dates` is moved back a century
where pandas placed it past that pivot. Against the live archive the derived
years agree with each file's own `YEAR` column, apart from the expected
rollover of events late on 31 December.

## Alternatives

- **Resolve `AST` and `SST` by `STATE`.** Puerto Rico is always UTC−4, so the
  pair (`AST`, `PUERTO RICO`) is unambiguous. It makes the derivation depend on
  a fourth column that `usecols` may have dropped, it needs a table of states
  and marine zones, and Alaska observed four zones before 1983, so `AST` on an
  early Alaska row is ambiguous even with the state. Deferred until a use case
  needs those rows; the provider page says how to convert them by hand.
- **Read a bare daylight label at its word**, as the reader already does for
  `CDT-5`, where the label states the offset. A defensible reading, and one
  table entry per label if it is wanted. Left out because a bare `CDT` states
  nothing, and twenty-four rows do not justify choosing between the label and
  the archive's documentation.
- **Anchor the century to the `YEAR` column.** More direct, but `END_DATE_TIME`
  can fall in the following year and `usecols` may drop `YEAR`. The fixed pivot
  needs no other column and holds until 2050.
- **Use named zones such as `America/Chicago`.** They apply daylight saving,
  which the archive's standard-time stamps do not use.

## Consequences

`BEGIN_UTC` and `END_UTC` are populated for 98 to 100 percent of rows in files
through 2006, where they were empty. Files from 2007 on are unaffected. The
`derived` entries gain one key, `labels_without_offset`; existing keys keep
their meaning, though `unparsed` is now far smaller for early files.

A label is still taken at its word. The 21 Arizona rows labelled `PST` convert
as UTC−8 although Arizona keeps Mountain Standard Time; the local columns and
the label stay in the frame, untouched, for anyone who needs to second-guess a
row.
